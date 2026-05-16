"""sota-mcp: MCP server for Summits on the Air — all public, no auth required."""

from __future__ import annotations

import sys
from typing import Any

from fastmcp import FastMCP

from . import __spec_version__, __version__
from .client import SOTAClient

mcp = FastMCP(
    "sota-mcp",
    version=__version__,
    instructions=(
        "MCP server for Summits on the Air (SOTA) — live spots, "
        "activation alerts, summit info, and nearby summits. "
        "All public endpoints, no authentication required."
    ),
)

_client: SOTAClient | None = None


def _get_client() -> SOTAClient:
    """Get or create the shared SOTA client."""
    global _client
    if _client is None:
        _client = SOTAClient()
    return _client


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def _version_info_payload() -> dict[str, Any]:
    """Build the version info envelope. Pulled into a helper so tests can
    call it directly without going through the FastMCP wrapper."""
    return {
        "service_name": "sota-mcp",
        "service_version": __version__,
        "spec_version": __spec_version__,
    }


@mcp.tool()
def get_version_info() -> dict[str, Any]:
    """Get sota-mcp service version and upstream spec version.

    Returns the running PyPI version of sota-mcp and the SOTA api2
    endpoint contract in use. Use this to confirm fleet alignment
    across MCP deployments — agents can compare service_version and
    spec_version across servers to detect drift without going outside
    the MCP protocol.

    Returns:
        service_name, service_version (PyPI), and spec_version (SOTA api2).
    """
    return _version_info_payload()


@mcp.tool()
def sota_spots(
    hours: int | None = 24,
    association: str | None = "",
    mode: str | None = "",
) -> dict[str, Any]:
    """Get current and recent SOTA spots.

    Returns live spot feed with summit details.

    Args:
        hours: Time window in hours (default 24).
        association: Filter by SOTA association (e.g., W7I, G, VK). Empty for all.
        mode: Filter by mode (e.g., CW, SSB, FT8). Empty for all.

    Returns:
        List of spots with activator, summit, frequency, mode, and comments.
    """
    try:
        # Coerce None → defaults (llama.cpp/mcpo sends null for optional params)
        hours = hours if hours is not None else 24
        association = association or ""
        mode = mode or ""
        spots = _get_client().spots(
            hours=hours,
            association=association or None,
            mode=mode or None,
        )
        return {"total": len(spots), "spots": spots}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def sota_alerts(
    hours: int | None = 16,
    association: str | None = "",
) -> dict[str, Any]:
    """Get upcoming SOTA activation alerts.

    Args:
        hours: Look-ahead window in hours (default 16).
        association: Filter by SOTA association (e.g., W7I). Empty for all.

    Returns:
        List of alerts with activator, summit, planned date/time,
        frequencies, and comments.
    """
    try:
        # Coerce None → defaults (llama.cpp/mcpo sends null for optional params)
        hours = hours if hours is not None else 16
        association = association or ""
        alerts = _get_client().alerts(
            hours=hours,
            association=association or None,
        )
        return {"total": len(alerts), "alerts": alerts}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def sota_summit_info(summit_code: str) -> dict[str, Any]:
    """Get detailed summit information by SOTA reference code.

    Args:
        summit_code: SOTA reference (e.g., W7I/SI-001, G/LD-001).

    Returns:
        Summit details including name, altitude, coordinates, grid,
        points, validity dates, and activation history.
    """
    try:
        return _get_client().summit_info(summit_code)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def sota_summits_near(
    latitude: float,
    longitude: float,
    radius_km: float | None = 50.0,
    limit: int | None = 20,
) -> dict[str, Any]:
    """Find SOTA summits near a geographic location.

    Args:
        latitude: Center latitude (decimal degrees).
        longitude: Center longitude (decimal degrees).
        radius_km: Search radius in km (default 50).
        limit: Maximum number of results (default 20).

    Returns:
        List of nearby summits sorted by distance with code, name,
        altitude, points, and activation count.
    """
    try:
        # Coerce None → defaults (llama.cpp/mcpo sends null for optional params)
        radius_km = radius_km if radius_km is not None else 50.0
        limit = limit if limit is not None else 20
        summits = _get_client().summits_near(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=limit,
        )
        return {"total": len(summits), "summits": summits}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the sota-mcp server."""
    transport = "stdio"
    port = 8007
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--transport" and i < len(sys.argv) - 1:
            transport = sys.argv[i + 1]
        if arg == "--port" and i < len(sys.argv) - 1:
            port = int(sys.argv[i + 1])

    if transport == "streamable-http":
        mcp.run(transport=transport, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
