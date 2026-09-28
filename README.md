<!-- mcp-name: io.github.qso-graph/sota-mcp -->
# sota-mcp

[![PyPI](https://img.shields.io/pypi/v/sota-mcp?label=PyPI&color=blue)](https://pypi.org/project/sota-mcp/)
[![MCP Registry](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fregistry.modelcontextprotocol.io%2Fv0%2Fservers%3Fsearch%3Dio.github.qso-graph%2Fsota-mcp%26version%3Dlatest&query=%24.servers%5B0%5D.server.version&label=MCP%20Registry&color=blue)](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.qso-graph/sota-mcp&version=latest)

MCP server for [Summits on the Air (SOTA)](https://www.sota.org.uk/) — live spots, activation alerts, summit info, and nearby summits through any MCP-compatible AI assistant.

Part of the [QSO-Graph](https://qso-graph.io/) project. **No authentication required** — uses the public [SOTA API](https://api2.sota.org.uk/) exclusively.

## Install

```bash
uvx sota-mcp            # run it; nothing to install
pip install sota-mcp    # or install it into your own environment
```

## Tools

| Tool | Description |
|------|-------------|
| `sota_spots` | Current and recent spots with time window and association/mode filters |
| `sota_alerts` | Upcoming scheduled activation alerts |
| `sota_summit_info` | Summit details by SOTA reference code |
| `sota_summits_near` | Find summits near coordinates (geospatial search) |
| `get_version_info` | Service version + upstream spec version (fleet identity attestation) |

## Quick Start

No credentials needed — just install and configure your MCP client.

### Configure your MCP client

sota-mcp works with any MCP-compatible client. Add the server config and restart — tools appear automatically.

#### Claude Desktop

Add to `claude_desktop_config.json` (`~/Library/Application Support/Claude/` on macOS, `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "sota": {
      "command": "uvx",
      "args": ["sota-mcp"]
    }
  }
}
```

#### Claude Code

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "sota": {
      "command": "uvx",
      "args": ["sota-mcp"]
    }
  }
}
```

#### ChatGPT Desktop

```json
{
  "mcpServers": {
    "sota": {
      "command": "uvx",
      "args": ["sota-mcp"]
    }
  }
}
```

#### Cursor

Add to `.cursor/mcp.json` (project-level) or `~/.cursor/mcp.json` (global):

```json
{
  "mcpServers": {
    "sota": {
      "command": "uvx",
      "args": ["sota-mcp"]
    }
  }
}
```

#### VS Code / GitHub Copilot

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "sota": {
      "command": "uvx",
      "args": ["sota-mcp"]
    }
  }
}
```

#### Gemini CLI

Add to `~/.gemini/settings.json` (global) or `.gemini/settings.json` (project):

```json
{
  "mcpServers": {
    "sota": {
      "command": "uvx",
      "args": ["sota-mcp"]
    }
  }
}
```

Installed with pip instead? Use `"command": "sota-mcp"` in any config above.

### Ask questions

> "What SOTA spots are active right now?"

> "Tell me about summit W7I/SI-001"

> "What summits are near Boise, Idaho?"

> "Any SOTA alerts for this weekend?"

## Testing Without Network

For testing all tools without hitting the SOTA APIs:

```bash
SOTA_MCP_MOCK=1 sota-mcp
```

## MCP Inspector

```bash
sota-mcp --transport streamable-http --port 8007
```

Then open the MCP Inspector at `http://localhost:8007`.

## Development

```bash
git clone https://github.com/qso-graph/sota-mcp.git
cd sota-mcp
uv sync --group dev
uv run pytest
```

## License

GPL-3.0-or-later
