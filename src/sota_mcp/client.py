"""SOTA API client — api2.sota.org.uk public endpoints only."""

from __future__ import annotations

import json
import math
import os
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

from . import __version__

_BASE = "https://api2.sota.org.uk"

# Cache TTLs
_SPOTS_TTL = 60.0  # 1 minute
_ALERTS_TTL = 300.0  # 5 minutes
_SUMMIT_TTL = 86400.0  # 24 hours
_REGION_TTL = 86400.0  # 24 hours
_NEAR_TTL = 300.0  # 5 minutes

# Rate limiting: 200ms minimum between requests
_MIN_DELAY = 0.2


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

_MOCK_SPOTS = [
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

_MOCK_ALERTS = [
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

_MOCK_SUMMIT = {
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

_MOCK_NEAR = [
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


class SOTAClient:
    """SOTA API client — all endpoints via api2.sota.org.uk."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request: float = 0.0
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
        """Enforce minimum delay between requests."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < _MIN_DELAY:
                time.sleep(_MIN_DELAY - elapsed)
            self._last_request = time.monotonic()

    def _get_json(self, url: str) -> Any:
        """HTTP GET, return parsed JSON."""
        self._rate_limit()
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", f"sota-mcp/{__version__}")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError):
            raise RuntimeError("SOTA API request failed")
        if not body or body.strip() == "":
            return None
        return json.loads(body)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_region_summits(self, assoc: str, region: str) -> list[dict[str, Any]]:
        """Fetch all summits in a region (cached 24h)."""
        key = f"region:{assoc}:{region}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        data = self._get_json(
            f"{_BASE}/api/regions/{urllib.parse.quote(assoc)}"
            f"/{urllib.parse.quote(region)}"
        )
        summits = (data or {}).get("summits", [])
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
        cached = self._cache_get(key)
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
        cached = self._cache_get(key)
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
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            data = dict(_MOCK_SUMMIT)
        else:
            try:
                data = self._get_json(
                    f"{_BASE}/api/summits/"
                    f"{urllib.parse.quote(code, safe='/')}"
                )
            except RuntimeError:
                data = None

        if not data:
            return {"summitCode": code, "error": "Not found"}

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
        cached = self._cache_get(key)
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

