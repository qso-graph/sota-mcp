"""MCP server for Summits on the Air — summit lookup, spots, alerts, nearby summits."""

from __future__ import annotations

try:
    from importlib.metadata import version

    __version__ = version("sota-mcp")
except Exception:
    __version__ = "0.0.0-dev"
