"""SOTA API client — api2.sota.org.uk public endpoints only."""

from __future__ import annotations

import json
import math
import os
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import cache
from typing import Any

import certifi

from . import __version__

_BASE = "https://api2.sota.org.uk"


@cache
def _context() -> ssl.SSLContext:
    """A verifying context with a current root set. Built once.

    The roots come from ``certifi`` rather than whichever store the running
    Python was built against. On macOS that distinction is real: Apple ships
    ``/etc/ssl/cert.pem`` for OpenSSL — and therefore for Python — as a
    deliberately *reduced* file, 128 roots against the system keychain's 158.
    It is current, not stale. But a certificate chaining to one of the 30 it
    omits fails for Python while ``curl`` to the same URL succeeds
    (qso-graph-devel#73, found when meteor-mcp could not reach NASA at all).

    api2.sota.org.uk verifies fine against the reduced file today, so this is a
    latent defect rather than an outage. This server carries no credential, so
    a trust failure here costs an answer rather than a secret — but it would
    cost it invisibly: the user is told only that the request failed, with
    nothing pointing at trust as the cause, and that is expensive to debug
    under pressure.

    Verification is never disabled. ``ssl.CERT_NONE`` or ``check_hostname =
    False`` would also make a call "work", by accepting any certificate from
    anyone — a worse defect than this one, and an invisible one. The fix is a
    complete root set, not a relaxed check.
    """
    return ssl.create_default_context(cafile=certifi.where())


# Cache TTLs
_SPOTS_TTL = 60.0  # 1 minute
_ALERTS_TTL = 300.0  # 5 minutes
_SUMMIT_TTL = 86400.0  # 24 hours
_REGION_TTL = 86400.0  # 24 hours
_NEAR_TTL = 300.0  # 5 minutes

# Rate limiting: 200ms minimum between requests
_MIN_DELAY = 0.2

# What to do when SOTA says stop.
#
# A 429 carrying Retry-After is the provider stating its limit outright, and it
# is the most explicit form of the stated limit guarantee 8 requires honouring.
# The interval is bounded rather than taken verbatim: a header asking for a day
# would strand an interactive tool, and one asking for nothing would let us
# hammer. See qso-graph-devel/planning/MCP-SECURITY-FRAMEWORK.md.
_MIN_BACKOFF = 60.0
_MAX_BACKOFF = 3600.0


class RateLimited(RuntimeError):
    """SOTA asked us to stop. The message is safe to show a user.

    A RuntimeError subclass so callers that already handle this client's
    failures keep working, and so FastMCP flags the tool result isError either
    way.
    """

    def __init__(self, wait: float) -> None:
        self.retry_after = max(1, round(wait))
        super().__init__(
            "SOTA is rate limiting this client; try again in "
            f"{self.retry_after} s"
        )


def _retry_after(header: str | None) -> float:
    """Seconds to wait, from a Retry-After header, clamped to our bounds.

    Retry-After may also be an HTTP date. That form is not parsed and falls back
    to the floor rather than guessing, because a wrong parse would either hammer
    SOTA or strand the user.
    """
    try:
        seconds = float(header) if header else 0.0
    except ValueError:
        seconds = 0.0
    # "nan" and "inf" parse as floats, and nan defeats the clamp below: every
    # comparison against it is False, so it would survive to be added to a
    # deadline that is then never in the future, leaving the block off
    # altogether. A header we cannot make sense of means the floor.
    if not math.isfinite(seconds):
        seconds = 0.0
    return min(max(seconds, _MIN_BACKOFF), _MAX_BACKOFF)


def _is_mock() -> bool:
    return os.getenv("SOTA_MCP_MOCK") == "1"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great circle distance in km between two points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_MOCK_SPOTS: list[dict[str, Any]] = [
    {
        "id": 123456,
        "timeStamp": "2026-03-04T18:30:00",
        "activatorCallsign": "KI7MT",
        "associationCode": "W7I",
        "summitCode": "W7I/SI-001",
        "summitDetails": "Borah Peak, 3859m, 10 points",
        "frequency": "14.062",
        "mode": "CW",
        "comments": "CQ SOTA",
        "callsign": "KI7MT",
    },
    {
        "id": 123457,
        "timeStamp": "2026-03-04T19:15:00",
        "activatorCallsign": "G4YSS",
        "associationCode": "G",
        "summitCode": "G/LD-001",
        "summitDetails": "Helvellyn, 950m, 8 points",
        "frequency": "7.032",
        "mode": "CW",
        "comments": "QRV 40m CW",
        "callsign": "G4OBK",
    },
]

_MOCK_ALERTS: list[dict[str, Any]] = [
    {
        "id": 78901,
        "activatingCallsign": "W7RN",
        "associationCode": "W7N",
        "summitCode": "W7N/WP-001",
        "summitDetails": "Wheeler Peak, 3982m, 10 points",
        "dateActivated": "2026-03-05",
        "startTime": "1500",
        "endTime": "1800",
        "frequency": "14.285 SSB, 7.032 CW",
        "comments": "Weather permitting",
    },
]

_MOCK_SUMMIT: dict[str, Any] = {
    "summitCode": "W7I/SI-001",
    "name": "Borah Peak",
    "associationName": "USA - Idaho",
    "regionName": "Southern Idaho",
    "altM": 3859,
    "altFt": 12662,
    "latitude": 44.137,
    "longitude": -113.781,
    "locator": "DN34cd",
    "points": 10,
    "validFrom": "2012-07-01T00:00:00Z",
    "validTo": "2099-12-31T00:00:00Z",
    "activationCount": 15,
    "activationDate": "2025-08-15",
    "activationCall": "WB7ABP",
}

_MOCK_NEAR: list[dict[str, Any]] = [
    {
        "summitCode": "W7I/SI-001",
        "name": "Borah Peak",
        "altM": 3859,
        "latitude": 44.137,
        "longitude": -113.781,
        "points": 10,
        "activationCount": 15,
        "distance_km": 12.5,
    },
    {
        "summitCode": "W7I/SI-005",
        "name": "Leatherman Peak",
        "altM": 3652,
        "latitude": 44.078,
        "longitude": -113.701,
        "points": 10,
        "activationCount": 3,
        "distance_km": 18.7,
    },
]


class NotFound(LookupError):
    """SOTA answered 404: the thing asked for does not exist.

    Its own type because the alternative is what this client did until #22 —
    turn every failure into ``{"error": "Not found"}``. SOTA being unreachable,
    SOTA answering 500, and a summit genuinely not existing are three different
    facts, and reporting the third for all of them tells a caller a summit does
    not exist when the truth is that nobody could ask.
    """


class SOTAClient:
    """SOTA API client — all endpoints via api2.sota.org.uk."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request: float = 0.0
        # Set by a 429: no call goes out before this. Shared by every endpoint,
        # because the limit is the provider's view of this client, not of one
        # path.
        self._blocked_until: float = 0.0
        self._cache: dict[str, tuple[float, Any]] = {}

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_get(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        expires, value = entry
        if time.monotonic() > expires:
            del self._cache[key]
            return None
        return value

    def _cache_set(self, key: str, value: Any, ttl: float) -> None:
        self._cache[key] = (time.monotonic() + ttl, value)

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        """Space requests out, or refuse if SOTA has told us to stop.

        The gap between requests is slept, because that is what pacing is for. An interval
        asked for by a 429 is not: this server answers a synchronous tool call
        behind a client timeout, so sleeping out a minute or an hour inside one
        is a hang rather than restraint.

        The spacing sleep is taken *outside* the lock, and the loop re-reads
        the state after it. Without the re-read, a request that a 429 arriving
        during the sleep had just forbidden would still go out -- the check
        would have been made before the wait rather than before the request.
        """
        while True:
            with self._lock:
                now = time.monotonic()
                remaining = self._blocked_until - now
                if remaining > 0:
                    raise RateLimited(remaining)
                elapsed = now - self._last_request
                if elapsed >= _MIN_DELAY:
                    self._last_request = now
                    return
                delay = _MIN_DELAY - elapsed
            time.sleep(delay)

    def _get_json(self, url: str) -> Any:
        """HTTP GET, return parsed JSON."""
        self._rate_limit()
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", f"sota-mcp/{__version__}")
        try:
            with urllib.request.urlopen(req, timeout=15, context=_context()) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotFound(f"SOTA has no record at {url}") from exc
            # 503 counts only when it carries Retry-After, which is a provider
            # shedding load deliberately; a bare 503 is an outage and falls
            # through to the message below.
            if exc.code == 429 or (exc.code == 503 and exc.headers.get("Retry-After")):
                # An outstanding block is never shortened: a response asking for
                # 60 s that lands while a 300 s block is still running must not
                # release us at 60. The wait raised is the one actually in force.
                asked = _retry_after(exc.headers.get("Retry-After"))
                with self._lock:
                    now = time.monotonic()
                    self._blocked_until = max(self._blocked_until, now + asked)
                    wait = self._blocked_until - now
                raise RateLimited(wait) from exc
            # Named, because since #22 this message is what the client sees as
            # the tool's error, and "SOTA API request failed" says neither what
            # was asked for nor why.
            raise RuntimeError(f"SOTA API request failed ({url}): HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"SOTA API request failed ({url}): {exc.reason}") from exc
        if not body or body.strip() == "":
            return None
        return json.loads(body)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_region_summits(self, assoc: str, region: str) -> list[dict[str, Any]]:
        """Fetch all summits in a region (cached 24h)."""
        key = f"region:{assoc}:{region}"
        cached: list[dict[str, Any]] | None = self._cache_get(key)
        if cached is not None:
            return cached

        data = self._get_json(
            f"{_BASE}/api/regions/{urllib.parse.quote(assoc)}"
            f"/{urllib.parse.quote(region)}"
        )
        # Annotated: _get_json returns Any, so .get() on it is Any, and
        # handing that back from a function promising a list is unchecked.
        summits: list[dict[str, Any]] = (data or {}).get("summits", [])
        self._cache_set(key, summits, _REGION_TTL)
        return summits

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def spots(
        self,
        hours: int = 24,
        association: str | None = None,
        mode: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get current and recent spots."""
        key = f"spots:{hours}:{association}:{mode}"
        cached: list[dict[str, Any]] | None = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            data = list(_MOCK_SPOTS)
        else:
            data = self._get_json(f"{_BASE}/api/spots/{hours}/all") or []

        # Client-side filtering
        results = []
        for spot in data:
            if association:
                assoc = spot.get("associationCode", "")
                if assoc.upper() != association.upper():
                    continue
            if mode and spot.get("mode", "").upper() != mode.upper():
                continue
            # Build full summit code for display
            assoc = spot.get("associationCode", "")
            code = spot.get("summitCode", "")
            if assoc and code and "/" not in code:
                spot["summitCode"] = f"{assoc}/{code}"
            results.append(spot)

        self._cache_set(key, results, _SPOTS_TTL)
        return results

    def alerts(
        self,
        hours: int = 16,
        association: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get upcoming activation alerts."""
        key = f"alerts:{hours}:{association}"
        cached: list[dict[str, Any]] | None = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            data = list(_MOCK_ALERTS)
        else:
            data = self._get_json(f"{_BASE}/api/alerts") or []

        # Client-side filtering
        if association:
            data = [
                a for a in data
                if (a.get("associationCode", "") or "").upper()
                == association.upper()
            ]

        self._cache_set(key, data, _ALERTS_TTL)
        return data

    def summit_info(self, summit_code: str) -> dict[str, Any]:
        """Get summit details by SOTA reference code."""
        code = summit_code.upper()
        key = f"summit:{code}"
        cached: dict[str, Any] | None = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            data = dict(_MOCK_SUMMIT)
        else:
            # Only a 404 means "no such summit". A transport failure or a 500
            # propagates, so the caller is told the lookup could not be made
            # rather than that the summit does not exist.
            data = self._get_json(
                f"{_BASE}/api/summits/"
                f"{urllib.parse.quote(code, safe='/')}"
            )

        if not data:
            raise NotFound(f"SOTA has no summit {code}.")

        self._cache_set(key, data, _SUMMIT_TTL)
        return data

    def _bbox_overlaps(
        self,
        lat: float,
        lon: float,
        radius_km: float,
        min_lat: float | None,
        max_lat: float | None,
        min_lon: float | None,
        max_lon: float | None,
    ) -> bool:
        """Check if a point+radius overlaps a bounding box (rough filter)."""
        if any(v is None for v in (min_lat, max_lat, min_lon, max_lon)):
            return True  # No bbox data — include to be safe
        # ~111 km per degree latitude
        margin = radius_km / 111.0
        assert min_lat is not None and max_lat is not None
        assert min_lon is not None and max_lon is not None
        if lat + margin < min_lat or lat - margin > max_lat:
            return False
        if lon + margin < min_lon or lon - margin > max_lon:
            return False
        return True

    def summits_near(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 50.0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Find summits near coordinates using association bbox + haversine."""
        key = f"near:{latitude:.3f}:{longitude:.3f}:{radius_km}:{limit}"
        cached: list[dict[str, Any]] | None = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            data = list(_MOCK_NEAR)
            self._cache_set(key, data, _NEAR_TTL)
            return data

        # Step 1: Get all associations (cached 24h after first call)
        assoc_key = "associations:all"
        associations = self._cache_get(assoc_key)
        if associations is None:
            associations = self._get_json(f"{_BASE}/api/associations") or []
            self._cache_set(assoc_key, associations, _REGION_TTL)

        # Step 2: Filter associations by bounding box (fast — no API calls)
        nearby_assocs = []
        for assoc in associations:
            if self._bbox_overlaps(
                latitude, longitude, radius_km,
                assoc.get("minLat"), assoc.get("maxLat"),
                assoc.get("minLong"), assoc.get("maxLong"),
            ):
                nearby_assocs.append(assoc.get("associationCode", ""))

        # Step 3: For each matching association, get regions and summits
        candidates: list[dict[str, Any]] = []
        for assoc_code in nearby_assocs:
            regions_data = self._get_json(
                f"{_BASE}/api/associations/{urllib.parse.quote(assoc_code)}"
            ) or {}
            regions = regions_data.get("regions", [])
            for reg in regions:
                reg_code = reg.get("regionCode", "")
                summits = self._get_region_summits(assoc_code, reg_code)
                for s in summits:
                    slat = s.get("latitude")
                    slon = s.get("longitude")
                    if slat is None or slon is None:
                        continue
                    dist = _haversine_km(latitude, longitude, slat, slon)
                    if dist <= radius_km:
                        candidates.append({
                            "summitCode": s.get("summitCode", ""),
                            "name": s.get("name", ""),
                            "altM": s.get("altM"),
                            "altFt": s.get("altFt"),
                            "latitude": slat,
                            "longitude": slon,
                            "locator": s.get("locator", ""),
                            "points": s.get("points"),
                            "activationCount": s.get("activationCount"),
                            "distance_km": round(dist, 1),
                        })

        # Sort by distance, limit results
        candidates.sort(key=lambda x: x["distance_km"])
        data = candidates[:limit]

        self._cache_set(key, data, _NEAR_TTL)
        return data

