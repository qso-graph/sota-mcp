"""L2 unit tests for sota-mcp — all 4 tools + helper functions.

Uses SOTA_MCP_MOCK=1 for tool-level tests (no SOTA API calls).
Direct unit tests on SOTAClient helper methods.

Test IDs: SOTA-L2-001 through SOTA-L2-035
"""

from __future__ import annotations

import os
import pytest

# Enable mock mode before importing anything
os.environ["SOTA_MCP_MOCK"] = "1"

from sota_mcp.client import SOTAClient, _haversine_km


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Fresh SOTAClient instance (no cache carryover)."""
    return SOTAClient()


# ---------------------------------------------------------------------------
# SOTA-L2-001..007: _haversine_km (distance calculation)
# ---------------------------------------------------------------------------


class TestHaversine:
    def test_zero_distance(self):
        """SOTA-L2-001: Same point → 0 km."""
        assert _haversine_km(44.137, -113.781, 44.137, -113.781) == 0.0

    def test_known_distance(self):
        """SOTA-L2-002: Borah Peak → Boise ~300 km."""
        dist = _haversine_km(44.137, -113.781, 43.617, -115.993)
        assert 180 < dist < 220

    def test_symmetry(self):
        """SOTA-L2-003: haversine(A,B) == haversine(B,A)."""
        d1 = _haversine_km(44.137, -113.781, 43.617, -115.993)
        d2 = _haversine_km(43.617, -115.993, 44.137, -113.781)
        assert abs(d1 - d2) < 0.01

    def test_antipodal(self):
        """SOTA-L2-004: Antipodal points ~20015 km."""
        dist = _haversine_km(0.0, 0.0, 0.0, 180.0)
        assert 20000 < dist < 20100

    def test_short_distance(self):
        """SOTA-L2-005: Two nearby summits from mock data."""
        # Borah Peak to Leatherman Peak
        dist = _haversine_km(44.137, -113.781, 44.078, -113.701)
        assert 5 < dist < 15

    def test_cross_hemisphere(self):
        """SOTA-L2-006: Idaho to England ~7500 km."""
        dist = _haversine_km(44.137, -113.781, 54.527, -3.024)
        assert 7000 < dist < 8000

    def test_equator_degree(self):
        """SOTA-L2-007: One degree at equator ≈ 111 km."""
        dist = _haversine_km(0.0, 0.0, 0.0, 1.0)
        assert 110 < dist < 112


# ---------------------------------------------------------------------------
# SOTA-L2-010..013: _bbox_overlaps (bounding box filter)
# ---------------------------------------------------------------------------


class TestBboxOverlaps:
    def test_point_inside_box(self, client):
        """SOTA-L2-010: Point inside bounding box → True."""
        assert client._bbox_overlaps(44.0, -114.0, 50.0, 40.0, 50.0, -120.0, -110.0) is True

    def test_point_outside_box(self, client):
        """SOTA-L2-011: Point far outside bounding box → False."""
        assert client._bbox_overlaps(0.0, 0.0, 50.0, 40.0, 50.0, -120.0, -110.0) is False

    def test_point_near_box_with_radius(self, client):
        """SOTA-L2-012: Point just outside box but within radius → True."""
        # Box is lat 40-50, point at 39.5 with 100km radius (~0.9 deg margin)
        assert client._bbox_overlaps(39.5, -115.0, 100.0, 40.0, 50.0, -120.0, -110.0) is True

    def test_none_bbox_returns_true(self, client):
        """SOTA-L2-013: Missing bbox values → True (inclusive)."""
        assert client._bbox_overlaps(44.0, -114.0, 50.0, None, None, None, None) is True


# ---------------------------------------------------------------------------
# SOTA-L2-020..027: Tool mock-mode tests
# ---------------------------------------------------------------------------


class TestSpotsTool:
    def test_all_spots(self, client):
        """SOTA-L2-020: spots() returns all mock spots."""
        result = client.spots()
        assert len(result) == 2

    def test_filter_by_association(self, client):
        """SOTA-L2-021: spots(association='W7I') filters correctly."""
        result = client.spots(association="W7I")
        assert len(result) == 1
        assert result[0]["activatorCallsign"] == "KI7MT"

    def test_filter_by_mode(self, client):
        """SOTA-L2-022: spots(mode='CW') returns both CW spots."""
        result = client.spots(mode="CW")
        assert len(result) == 2  # Both mock spots are CW

    def test_filter_no_match(self, client):
        """SOTA-L2-023: Filtering with non-matching criteria → empty."""
        result = client.spots(association="ZL")
        assert len(result) == 0

    def test_spot_fields(self, client):
        """SOTA-L2-024: Spots have expected fields."""
        spots = client.spots()
        spot = spots[0]
        for field in ("activatorCallsign", "summitCode", "frequency", "mode"):
            assert field in spot, f"Missing field: {field}"


class TestAlertsTool:
    def test_all_alerts(self, client):
        """SOTA-L2-025: alerts() returns mock alerts."""
        result = client.alerts()
        assert len(result) == 1
        assert result[0]["activatingCallsign"] == "W7RN"

    def test_filter_by_association(self, client):
        """SOTA-L2-026: alerts(association='W7N') filters correctly."""
        result = client.alerts(association="W7N")
        assert len(result) == 1

    def test_filter_no_match(self, client):
        """SOTA-L2-027: alerts(association='ZL') → empty."""
        result = client.alerts(association="ZL")
        assert len(result) == 0


class TestSummitInfoTool:
    def test_returns_summit(self, client):
        """SOTA-L2-028: summit_info returns mock summit data."""
        result = client.summit_info("W7I/SI-001")
        assert result["name"] == "Borah Peak"
        assert result["altM"] == 3859

    def test_summit_fields(self, client):
        """SOTA-L2-029: Summit info has expected fields."""
        result = client.summit_info("W7I/SI-001")
        for field in ("summitCode", "name", "altM", "altFt", "latitude", "longitude",
                       "locator", "points", "activationCount"):
            assert field in result, f"Missing field: {field}"

    def test_case_insensitive(self, client):
        """SOTA-L2-030: summit_info uppercases code."""
        result = client.summit_info("w7i/si-001")
        assert result["summitCode"] == "W7I/SI-001"


class TestSummitsNearTool:
    def test_returns_nearby(self, client):
        """SOTA-L2-031: summits_near returns mock data with distances."""
        result = client.summits_near(44.137, -113.781)
        assert len(result) == 2

    def test_sorted_by_distance(self, client):
        """SOTA-L2-032: summits_near returns sorted by distance."""
        result = client.summits_near(44.137, -113.781)
        if len(result) > 1:
            distances = [s["distance_km"] for s in result]
            assert distances == sorted(distances)

    def test_summit_near_fields(self, client):
        """SOTA-L2-033: Nearby summits have distance_km field."""
        result = client.summits_near(44.137, -113.781)
        for s in result:
            assert "distance_km" in s
            assert "summitCode" in s
            assert "name" in s


# ---------------------------------------------------------------------------
# SOTA-L2-034..035: Cache and edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_cache_expiry(self, client):
        """SOTA-L2-034: Cache entries expire after TTL."""
        client._cache_set("test_key", "test_value", 0.01)
        assert client._cache_get("test_key") == "test_value"
        import time
        time.sleep(0.02)
        assert client._cache_get("test_key") is None

    def test_cache_miss(self, client):
        """SOTA-L2-035: Cache miss returns None."""
        assert client._cache_get("nonexistent") is None
