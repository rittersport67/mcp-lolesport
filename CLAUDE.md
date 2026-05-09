# CLAUDE.md — MCP Riot Server

## Project Overview

MCP-Riot is a [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol) server written in Python that exposes League of Legends data (via the Riot Games API) and LoL esports data (via the unofficial LoL Esports API) to AI assistants.

> Not affiliated with or endorsed by Riot Games.

---

## Architecture

```
mcp-riot/
├── src/
│   └── server.py       # Main MCP server — all tools, prompts, and schemas defined here
├── .env                # API keys (not committed)
├── .env.example        # Template for .env
├── pyproject.toml      # Python project config (uv)
└── uv.lock             # Lockfile
```

**Entry point:** `src/server.py`
**Framework:** [`FastMCP`](https://github.com/modelcontextprotocol/python-sdk) from `mcp[cli]`
**HTTP client:** `httpx` (async)
**Transport:** StreamableHTTP (default, port 8000, `/mcp`) or stdio (set via `MCP_TRANSPORT` env var)

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RIOT_API_KEY` | Yes | Riot Games API key from https://developer.riotgames.com/ |
| `ESPORTS_API_KEY` | Yes | LoL Esports API key (public key used by lolesports.com) |
| `MCP_TRANSPORT` | No | `streamable-http` (default) or `stdio` |

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
| `get_upcoming_esport_matches` | Upcoming/live competitive matches, filterable by `league` |
| `get_esport_teams` | Professional teams list, filterable by `league` |
| `get_esport_players` | Roster for a specific team (by `team` identifier) |
| `get_esport_tournaments` | Tournaments with dates and IDs, filterable by `league` |

**Supported league values:** `lck`, `lec`, `lcs`, `lpl`, `worlds`, `msi`, `cblol`, `ljl`, `vcs`, `pcs`

### Parameter conventions
- `league` — league identifier used across all esport tools
- `team` — team identifier used in `get_esport_players` (e.g. `t1`, `cloud9`, `fnatic`, `g2-esports`)
- `game_name` + `tag_line` — Riot ID components (e.g. `Faker` + `T1`)
- `region` — server region code: `kr`, `jp`, `euw`, `eune`, `na`, `br`, `lan`, `las`, `tr`, `ru`, `oce`

---

## MCP Prompts

| Prompt | Parameters | Description |
|--------|------------|-------------|
| `analyze_player` | `game_name`, `tag_line`, `region` | Full player analysis combining summary, top champions, and recent matches |
| `preview_competition` | `league` | Upcoming matches for a league with team rosters |
| `scout_team` | `team` | Detailed roster breakdown for a specific team |

---

## Key Implementation Details

### Riot API
- Region routing: account lookup → `asia.api.riotgames.com`, summoner/match → region-specific server
- Authentication: `X-Riot-Token` header
- Champion names resolved via Data Dragon (`ddragon.leagueoflegends.com`) — cached per language in `CHAMPION_MAP`

### Esports API
- Base URL: `https://esports-api.lolesports.com/persisted/gw`
- Authentication: `ESPORTS_API_KEY` env var (`x-api-key` header) — public key used by the lolesports.com website
- League resolution: `league` identifier → ID via `ESPORTS_LEAGUE_IDS` map or live API call
- Filtering: done at API level (via `leagueId` param) and client-side on the response

### Player Lookup Flow
1. `game_name` + `tag_line` → `get_puuid()` → PUUID
2. PUUID → summoner data, mastery, matches

---

## Running Locally

```bash
# Install dependencies
uv sync

# Set API keys
cp .env.example .env
# Edit .env and add your RIOT_API_KEY and ESPORTS_API_KEY

# Run StreamableHTTP server (default, port 8000, endpoint /mcp)
python src/server.py

# Or run as stdio server
MCP_TRANSPORT=stdio python src/server.py
```

## MCP Client Configuration

### Claude Desktop (StreamableHTTP mode)
Start the server first (`python src/server.py`), then add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "riot": {
      "url": "http://localhost:8000/mcp"
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

## MCP Inspector

To test tools interactively via the MCP inspector:

```bash
npx @modelcontextprotocol/inspector --config inspector.json --server riot
```

- API keys are loaded automatically from `.env` via `load_dotenv()`
- Open the generated URL in a browser (Chrome or Firefox recommended — Safari may have issues with localhost)
- Optional parameters must be explicitly activated in the inspector form before submitting

---

## Dependencies

- `mcp[cli] >= 1.9.0` — MCP server framework
- `httpx >= 0.28.1` — async HTTP client
- `python-dotenv >= 1.0.0` — `.env` file loading
- Python `>= 3.13`
