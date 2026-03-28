# CLAUDE.md — MCP Riot Server

## Project Overview

MCP-Riot is a [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol) server written in Python that exposes League of Legends data (via the Riot Games API) and LoL esports data (via the unofficial LoL Esports API) to AI assistants.

> Not affiliated with or endorsed by Riot Games.

---

## Architecture

```
mcp-riot/
├── src/
│   └── server.py       # Main MCP server — all tools defined here
├── .env                # API key (not committed)
├── .env.example        # Template for .env
├── pyproject.toml      # Python project config (uv)
└── uv.lock             # Lockfile
```

**Entry point:** `src/server.py`
**Framework:** [`FastMCP`](https://github.com/modelcontextprotocol/python-sdk) from `mcp[cli]`
**HTTP client:** `httpx` (async)
**Transport:** SSE (default, port 8000) or stdio (set via `MCP_TRANSPORT` env var)

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RIOT_API_KEY` | Yes | Riot Games API key from https://developer.riotgames.com/ |
| `MCP_TRANSPORT` | No | `sse` (default) or `stdio` |

---

## MCP Tools

### Player Tools (Riot Games API)

| Tool | Description |
|------|-------------|
| `get_player_summary` | Full profile: level, rank, top champions, recent matches |
| `get_top_champions_tool` | Top N champions by mastery points |
| `get_champion_mastery_tool` | Mastery details for a specific champion |
| `get_recent_matches_tool` | Recent match history (champion, K/D/A, result) |
| `get_match_summary` | Detailed stats for a specific match by match ID + puuid |

### Esports Tools (unofficial LoL Esports API)

| Tool | Description |
|------|-------------|
| `get_upcoming_esport_matches` | Upcoming/live competitive matches, filterable by league |
| `get_esport_teams` | Professional teams list, filterable by league |
| `get_esport_players` | Roster for a specific team (by team slug) |
| `get_esport_tournaments` | Tournaments with dates and IDs, filterable by league |

**Supported league slugs:** `lck`, `lec`, `lcs`, `lpl`, `worlds`, `msi`, `cblol`, `ljl`, `vcs`, `pcs`

---

## Key Implementation Details

### Riot API
- Region routing: account lookup → `asia.api.riotgames.com`, summoner/match → `kr.api.riotgames.com`
- Authentication: `X-Riot-Token` header
- Champion names resolved via Data Dragon (`ddragon.leagueoflegends.com`) — cached per language in `CHAMPION_MAP`

### Esports API
- Base URL: `https://esports-api.lolesports.com/persisted/gw`
- Authentication: hardcoded public key (`x-api-key` header) — this is the same key used by the lolesports.com website
- League resolution: slug → ID via `ESPORTS_LEAGUE_IDS` map or live API call

### Player Lookup Flow
1. `game_name` + `tag_line` → `get_puuid()` → PUUID
2. PUUID → summoner data, mastery, matches

---

## Running Locally

```bash
# Install dependencies
uv sync

# Set API key
cp .env.example .env
# Edit .env and add your RIOT_API_KEY

# Run SSE server (default, port 8000)
python src/server.py

# Or run as stdio server
MCP_TRANSPORT=stdio python src/server.py
```

## MCP Client Configuration

### Claude Desktop (SSE mode)
Start the server first (`python src/server.py`), then add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "riot": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Claude Desktop (stdio mode)
```json
{
  "mcpServers": {
    "riot": {
      "command": "/absolute/path/to/uv",
      "args": [
        "--directory", "/absolute/path/to/mcp-riot",
        "run",
        "--env-file", "/absolute/path/to/mcp-riot/.env",
        "server.py"
      ]
    }
  }
}
```

---

## Dependencies

- `mcp[cli] >= 1.6.0` — MCP server framework
- `httpx >= 0.28.1` — async HTTP client
- `python-dotenv >= 1.0.0` — `.env` file loading
- Python `>= 3.13`
