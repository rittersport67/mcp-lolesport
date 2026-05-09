[![smithery badge](https://smithery.ai/badge/@jifrozen0110/riot)](https://smithery.ai/server/@jifrozen0110/riot)

# MCP Riot Server

**MCP-Riot is a community-developed [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol) server that integrates with the Riot Games API** to provide League of Legends data to AI assistants via natural language queries.

This project enables AI models to retrieve player information, ranked stats, champion mastery, recent match summaries, and LoL esports data.

> **Disclaimer:** This is an open-source project *not affiliated with or endorsed by Riot Games.* League of Legends® is a registered trademark of Riot Games, Inc.

---
## Demo
![mcp-riot-lol](https://github.com/user-attachments/assets/ef0c62d7-f99b-4a74-bc7d-8b737bf8fe2a)


## ✨ Features

### 🧾 Player Summary
> "What's the current rank and top champions of Hide on bush?"

Provides the player's:
- Level
- Ranked Solo Tier
- Top champion masteries
- Recent match history

### 🔝 Top Champions
> "What champions is he best at?"

Returns the top N champions based on mastery points.

### 🎯 Champion Mastery
> "How good is this player with Ahri?"

Returns detailed champion mastery data for a specific champion.

### 🕹️ Recent Matches
> "Show the last 3 matches for this summoner"

Lists recent matches including champion used, K/D/A, and result.

### 📊 Match Summary
> "Summarize this match for a given match ID"

Returns the player's match stats, such as KDA, damage, wards, and result.

### 🗓️ Esports Schedule
> "What are the upcoming LCK matches?"

Returns upcoming and live competitive matches, filterable by league.

### 🛡️ Esports Teams & Players
> "Who are the players on T1?"

Returns professional team rosters and team lists, filterable by league.

### 🏆 Esports Tournaments
> "What tournaments are happening in the LPL?"

Returns tournaments with start/end dates, filterable by league.

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/rittersport67/mcp-lolesport.git
cd mcp-lolesport

# Install dependencies (using uv)
uv sync
```

### 2. Get Your API Key and Set Environment

Create a `.env` file with your Riot API key:

```ini
RIOT_API_KEY=your_riot_api_key
```

You can get your key from https://developer.riotgames.com/

### 3. Run the Server

```bash
python src/server.py
```

The server starts in StreamableHTTP mode on `http://localhost:8000/mcp` by default.

To run in stdio mode:
```bash
MCP_TRANSPORT=stdio python src/server.py
```

### 4. Configure MCP Client

#### Option A — StreamableHTTP (recommended)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "riot": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

#### Option B — stdio

```json
{
  "mcpServers": {
    "riot": {
      "command": "/ABSOLUTE/PATH/TO/uv",
      "args": [
        "--directory", "/ABSOLUTE/PATH/TO/mcp-riot",
        "run",
        "--env-file", "/ABSOLUTE/PATH/TO/mcp-riot/.env",
        "server.py"
      ]
    }
  }
}
```

> Replace `/ABSOLUTE/PATH/TO/` with the actual paths on your system.

---

## 🛠️ Tools

### Player Tools

#### `get_player_summary`
Summarizes level, rank, top champions, and recent matches.

#### `get_top_champions_tool`
Returns top champions by mastery points.

#### `get_champion_mastery_tool`
Returns mastery details for a specific champion.

#### `get_recent_matches_tool`
Returns recent matches for the given summoner.

#### `get_match_summary`
Returns match performance stats for a given match ID and puuid.

### Esports Tools

#### `get_upcoming_esport_matches`
Returns upcoming and live competitive matches.
Filter by league slug: `lck`, `lec`, `lcs`, `lpl`, `worlds`, `msi`, `cblol`, `pcs`, `vcs`, `ljl`

#### `get_esport_teams`
Returns professional teams with their region, code, and slug.
Optionally filter by league slug.

#### `get_esport_players`
Returns the current roster of a professional team by team slug.

#### `get_esport_tournaments`
Returns tournaments with start/end dates and IDs.
Optionally filter by league slug.

---

## 📚 References

- [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Riot Games API Docs](https://developer.riotgames.com/)
- [Data Dragon (static data)](https://developer.riotgames.com/docs/lol#data-dragon)

---

## 📝 License

MIT License © 2025 [jifrozen0110](https://github.com/jifrozen0110)
