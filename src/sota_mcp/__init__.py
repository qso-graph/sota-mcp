"""MCP server for Summits on the Air — summit lookup, spots, alerts, nearby summits."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Final

try:
    _pkg_version = version("sota-mcp")
except PackageNotFoundError:  # local dev / editable installs without dist metadata
    _pkg_version = "0.0.0-dev"

__version__: Final[str] = _pkg_version

# Upstream data spec the server is bound to. Pinned to the SOTA api2.sota.org.uk
# endpoint contract we consume — bump this when SOTA publishes a new API
# revision. Reported by the get_version_info tool so agents can detect
# fleet drift without going outside the MCP protocol.
__spec_version__: Final[str] = "sota-api2-v1"
