# sota-mcp

MCP server for [Summits on the Air (SOTA)](https://www.sota.org.uk/) — live spots, activation alerts, summit info, nearby summits, and activator stats through any MCP-compatible AI assistant.

Part of the [qso-graph](https://qso-graph.io/) project. **No authentication required** — uses public [SOTLAS](https://sotl.as/) and [SOTALive](https://www.sotalive.tk/) APIs.

## Install

```bash
pip install sota-mcp
```

## Tools

| Tool | Description |
|------|-------------|
| `sota_spots` | Current and recent spots with time window and association/mode filters |
| `sota_alerts` | Upcoming scheduled activation alerts |
| `sota_summit_info` | Summit details by SOTA reference code |
| `sota_summits_near` | Find summits near coordinates (geospatial search) |
| `sota_activator_stats` | Activator profile, stats, and recent activation history |

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
      "command": "sota-mcp"
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
      "command": "sota-mcp"
    }
  }
}
```

#### ChatGPT Desktop

```json
{
  "mcpServers": {
    "sota": {
      "command": "sota-mcp"
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
      "command": "sota-mcp"
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
      "command": "sota-mcp"
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
      "command": "sota-mcp"
    }
  }
}
```

### Ask questions

> "What SOTA spots are active right now?"

> "Tell me about summit W7I/SI-001"

> "What summits are near Boise, Idaho?"

> "Show me KI7MT's SOTA activator stats"

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
pip install -e .
```

## License

GPL-3.0-or-later
