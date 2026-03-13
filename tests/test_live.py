"""L3 live integration tests for sota-mcp — real SOTA API calls.

Requires --live flag: pytest tests/test_live.py --live

Test IDs: SOTA-L3-001 through SOTA-L3-010
"""

from __future__ import annotations

import pytest

from sota_mcp.client import SOTAClient

# Known-good reference data
KNOWN_SUMMIT = "W7I/CU-001"  # Borah Peak, Idaho — highest point in Idaho (Custer region)
BORAH_LAT = 44.137
BORAH_LON = -113.781


@pytest.fixture
def client():
    """Fresh SOTAClient instance for live API calls."""
    return SOTAClient()


# ---------------------------------------------------------------------------
# SOTA-L3-001..002: Spots
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_spots_live(client):
    """SOTA-L3-001: spots() returns a list from the live API."""
    result = client.spots()
    assert isinstance(result, list)
    if len(result) > 0:
        spot = result[0]
        for field in ("activatorCallsign", "summitCode", "frequency", "mode"):
            assert field in spot, f"Missing field: {field}"


@pytest.mark.live
def test_spots_filter_association_live(client):
    """SOTA-L3-002: spots(association=...) filters without error."""
    result = client.spots(association="W7I")
    assert isinstance(result, list)
    for spot in result:
        code = spot.get("associationCode", "") or spot.get("summitCode", "")
        assert "W7I" in code.upper()


# ---------------------------------------------------------------------------
# SOTA-L3-003..004: Alerts
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_alerts_live(client):
    """SOTA-L3-003: alerts() returns a list from the live API."""
    result = client.alerts()
    assert isinstance(result, list)
    if len(result) > 0:
        alert = result[0]
        for field in ("activatingCallsign", "summitCode"):
            assert field in alert, f"Missing field: {field}"


@pytest.mark.live
def test_alerts_filter_association_live(client):
    """SOTA-L3-004: alerts(association=...) filters without error."""
    result = client.alerts(association="W7I")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# SOTA-L3-005..007: Summit Info
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_summit_info_live(client):
    """SOTA-L3-005: summit_info('W7I/SI-001') returns Borah Peak data."""
    result = client.summit_info(KNOWN_SUMMIT)
    assert result.get("name") == "Borah Peak"
    assert result.get("altM", 0) >= 3800
    assert "latitude" in result
    assert "longitude" in result
    assert "points" in result


@pytest.mark.live
def test_summit_info_case_insensitive_live(client):
    """SOTA-L3-006: summit_info lowercased code still works."""
    result = client.summit_info(KNOWN_SUMMIT.lower())
    assert result.get("name") == "Borah Peak"


@pytest.mark.live
def test_summit_info_not_found_live(client):
    """SOTA-L3-007: summit_info with bogus code returns error dict."""
    result = client.summit_info("ZZ9/XX-999")
    assert "error" in result


# ---------------------------------------------------------------------------
# SOTA-L3-008..010: Summits Near
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_summits_near_live(client):
    """SOTA-L3-008: summits_near Borah Peak returns results with distance_km."""
    result = client.summits_near(BORAH_LAT, BORAH_LON, radius_km=50.0)
    assert isinstance(result, list)
    assert len(result) > 0
    for summit in result:
        assert "distance_km" in summit
        assert "summitCode" in summit
        assert "name" in summit


@pytest.mark.live
def test_summits_near_sorted_live(client):
    """SOTA-L3-009: summits_near results are sorted by distance ascending."""
    result = client.summits_near(BORAH_LAT, BORAH_LON, radius_km=50.0)
    assert len(result) > 0
    distances = [s["distance_km"] for s in result]
    assert distances == sorted(distances)


@pytest.mark.live
def test_summits_near_borah_first_live(client):
    """SOTA-L3-010: First result near Borah Peak is within 10 km."""
    result = client.summits_near(BORAH_LAT, BORAH_LON, radius_km=50.0)
    assert len(result) > 0
    assert result[0]["distance_km"] < 10.0
