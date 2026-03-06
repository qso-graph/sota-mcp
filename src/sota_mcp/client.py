"""SOTA API client — SOTLAS + SOTALive public endpoints."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

from . import __version__

_SOTLAS = "https://api.sotl.as"
_SOTA_API = "https://api2.sota.org.uk"

# Cache TTLs
_SPOTS_TTL = 60.0  # 1 minute
_ALERTS_TTL = 300.0  # 5 minutes
_SUMMIT_TTL = 86400.0  # 24 hours
_STATS_TTL = 3600.0  # 1 hour
_NEAR_TTL = 300.0  # 5 minutes

# Rate limiting: 200ms minimum between requests
_MIN_DELAY = 0.2


def _is_mock() -> bool:
    return os.getenv("SOTA_MCP_MOCK") == "1"


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_MOCK_SPOTS = [
    {
        "id": 123456,
        "timestamp": "2026-03-04T18:30:00Z",
        "activatorCallsign": "KI7MT",
        "summitCode": "W7I/SI-001",
        "summitName": "Borah Peak",
        "frequency": "14.062",
        "mode": "CW",
        "comments": "CQ SOTA",
        "posterCallsign": "KI7MT",
        "association": "W7I",
        "points": 10,
    },
    {
        "id": 123457,
        "timestamp": "2026-03-04T19:15:00Z",
        "activatorCallsign": "G4YSS",
        "summitCode": "G/LD-001",
        "summitName": "Helvellyn",
        "frequency": "7.032",
        "mode": "CW",
        "comments": "QRV 40m CW",
        "posterCallsign": "G4OBK",
        "association": "G",
        "points": 8,
    },
]

_MOCK_ALERTS = [
    {
        "id": 78901,
        "activatorCallsign": "W7RN",
        "summitCode": "W7N/WP-001",
        "summitName": "Wheeler Peak",
        "dateActivated": "2026-03-05",
        "startTime": "1500",
        "endTime": "1800",
        "frequency": "14.285 SSB, 7.032 CW",
        "comments": "Weather permitting",
        "association": "W7N",
        "points": 10,
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
    "gridRef": "DN34cd",
    "points": 10,
    "bonusPoints": 3,
    "validFrom": "2012-07-01",
    "validTo": "9999-12-31",
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

_MOCK_ACTIVATOR = {
    "callsign": "KI7MT",
    "activations": 12,
    "uniqueSummits": 8,
    "totalQsos": 347,
    "points": 64,
    "bonusPoints": 12,
    "totalPoints": 76,
    "recentActivations": [
        {
            "summitCode": "W7I/SI-001",
            "summitName": "Borah Peak",
            "date": "2025-08-15",
            "qsos": 32,
            "points": 10,
        },
    ],
}


class SOTAClient:
    """SOTA API client using SOTLAS and SOTALive."""

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
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        if not body or body.strip() == "":
            return None
        return json.loads(body)

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
            data = self._get_json(f"{_SOTA_API}/api/spots/{hours}/all") or []

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
            data = self._get_json(f"{_SOTLAS}/alerts") or []

        # Client-side filtering
        if association:
            data = [
                a for a in data
                if (a.get("summitCode", "") or "").startswith(association.upper())
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
            # SOTLAS uses {association}/{code} format
            # e.g., W7I/SI-001 → summits/W7I/SI-001
            data = self._get_json(f"{_SOTLAS}/summits/{urllib.parse.quote(code, safe='/')}")

        if not data:
            return {"summitCode": code, "error": "Not found"}

        self._cache_set(key, data, _SUMMIT_TTL)
        return data

    def summits_near(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 50.0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Find summits near coordinates."""
        key = f"near:{latitude:.3f}:{longitude:.3f}:{radius_km}:{limit}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            data = list(_MOCK_NEAR)
        else:
            radius_m = int(radius_km * 1000)
            params = urllib.parse.urlencode({
                "lat": latitude,
                "lon": longitude,
                "limit": limit,
                "maxDistance": radius_m,
            })
            data = self._get_json(f"{_SOTLAS}/summits/near?{params}") or []

        self._cache_set(key, data, _NEAR_TTL)
        return data

    def activator_stats(self, callsign: str) -> dict[str, Any]:
        """Get activator profile and stats."""
        call = callsign.upper()
        key = f"activator:{call}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            data = dict(_MOCK_ACTIVATOR)
        else:
            data = self._get_json(
                f"{_SOTLAS}/activators/{urllib.parse.quote(call)}"
            )

        if not data:
            return {"callsign": call, "error": "Not found"}

        self._cache_set(key, data, _STATS_TTL)
        return data
