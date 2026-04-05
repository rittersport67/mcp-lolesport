from mcp.server.fastmcp import FastMCP
import httpx
import os
from typing import Any
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("riot")

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
if not RIOT_API_KEY:
    raise EnvironmentError("RIOT_API_KEY is not set in the environment variables.")

CHAMPION_MAP: dict[str, dict[int, str]] = {}  # language -> {champ_id: name}

# LoL Esports API (unofficial, used by lolesports.com)
ESPORTS_API_KEY = os.getenv("ESPORTS_API_KEY", "")
ESPORTS_BASE_URL = "https://esports-api.lolesports.com/persisted/gw"

# Common league slugs -> IDs
ESPORTS_LEAGUE_IDS: dict[str, str] = {
    "lck": "98767991310872058",
    "lec": "98767991302996019",
    "lcs": "98767991299243165",
    "lpl": "98767991314006698",
    "worlds": "98767975604431411",
    "msi": "98767991325878492",
    "cblol": "98767991332355509",
    "ljl": "98767991349978712",
    "vcs": "107213827295848783",
    "pcs": "104366947889790212",
}


async def esports_request(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any] | str:
    """Returns the parsed JSON on success, or an error string on failure."""
    headers = {"x-api-key": ESPORTS_API_KEY}
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(
                f"{ESPORTS_BASE_URL}/{endpoint}",
                headers=headers,
                params=params,
                timeout=30.0,
            )
            if res.status_code == 403:
                return f"[403 Forbidden] The LoL Esports API key is invalid or expired. Endpoint: {endpoint}"
            if res.status_code == 404:
                return f"[404 Not Found] Endpoint '{endpoint}' does not exist or params are wrong: {params}"
            if res.status_code >= 400:
                return f"[{res.status_code}] API error on '{endpoint}': {res.text[:200]}"
            res.raise_for_status()
            return res.json()
        except httpx.TimeoutException:
            return f"[Timeout] Request to '{endpoint}' timed out after 30s"
        except httpx.ConnectError as e:
            return f"[ConnectError] Cannot reach LoL Esports API: {e}"
        except Exception as e:
            return f"[Error] Unexpected error on '{endpoint}': {type(e).__name__}: {e}"


async def resolve_league_id(league_slug: str, language: str) -> str | None:
    """Resolves a league slug to its ID, checking the local map then the API."""
    league_id = ESPORTS_LEAGUE_IDS.get(league_slug.lower())
    if league_id:
        return league_id
    data = await esports_request("getLeagues", {"hl": language})
    if isinstance(data, str):  # error string
        return None
    leagues = data.get("data", {}).get("leagues", [])
    match = next((l for l in leagues if l.get("slug", "").lower() == league_slug.lower()), None)
    return match["id"] if match else None


async def riot_request(
    url: str, region: str = "kr", params: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    headers = {
        "X-Riot-Token": RIOT_API_KEY,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        try:
            full_url = f"https://{region}.api.riotgames.com{url}"
            res = await client.get(full_url, headers=headers, params=params, timeout=30.0)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Riot API Error: {e}")
            return None


async def get_champion_map(language: str = "ko_KR") -> dict[int, str]:
    if language in CHAMPION_MAP:
        return CHAMPION_MAP[language]

    async with httpx.AsyncClient() as client:
        version_res = await client.get("https://ddragon.leagueoflegends.com/api/versions.json")
        version = version_res.json()[0]
        champ_res = await client.get(
            f"https://ddragon.leagueoflegends.com/cdn/{version}/data/{language}/champion.json"
        )
        data = champ_res.json()["data"]
        CHAMPION_MAP[language] = {int(c["key"]): c["name"] for c in data.values()}
        return CHAMPION_MAP[language]


async def get_puuid(game_name: str, tag_line: str) -> str | None:
    url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    headers = {
        "X-Riot-Token": RIOT_API_KEY,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers)
            res.raise_for_status()
            return res.json()["puuid"]
    except Exception:
        return None


async def get_summoner_by_puuid(puuid: str) -> dict[str, Any] | None:
    return await riot_request(f"/lol/summoner/v4/summoners/by-puuid/{puuid}")


async def get_rank_by_summoner_id(summoner_id: str) -> str:
    rank_data = await riot_request(f"/lol/league/v4/entries/by-puuid{summoner_id}")
    if not rank_data:
        return "No ranked data available."

    solo = next((q for q in rank_data if q["queueType"] == "RANKED_SOLO_5x5"), None)
    if solo:
        tier, rank = solo["tier"], solo["rank"]
        lp, wins, losses = solo["leaguePoints"], solo["wins"], solo["losses"]
        winrate = round(wins / (wins + losses) * 100)
        return f"{tier} {rank} ({lp} LP) - {wins}W {losses}L ({winrate}% WR)"
    return "Unranked in Solo Queue."


async def get_top_champions(puuid: str, champ_map: dict[int, str], count: int = 3) -> str:
    mastery_data = await riot_request(
        f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top", params={"count": count}
    )
    if not mastery_data:
        return "No champion mastery data found."

    return "\n".join(
        f"- {champ_map.get(c['championId'], f'ID({c['championId']})')}: Level {c['championLevel']}, {c['championPoints']} pts" # type: ignore
        for c in mastery_data
    )


@mcp.tool()
async def get_top_champions_tool(game_name: str, tag_line: str, language: str = "en_US", count: int = 3) -> str:
    """
    🔝 Get the player's top champion masteries.

    Returns a list of the player's most-played champions based on mastery points.
    """
    puuid = await get_puuid(game_name, tag_line)
    if not puuid:
        return "Failed to find player."

    champ_map = await get_champion_map(language)
    return await get_top_champions(puuid, champ_map, count)


async def get_recent_matches(puuid: str, count: int = 3) -> str:
    match_ids = await riot_request(
        f"/lol/match/v5/matches/by-puuid/{puuid}/ids", region="asia", params={"count": count}
    )
    if not match_ids:
        return "No recent matches found."

    matches = []
    for match_id in match_ids:
        match = await riot_request(f"/lol/match/v5/matches/{match_id}", region="asia")
        if match:
            participant = next((p for p in match["info"]["participants"] if p["puuid"] == puuid), None)
            if participant:
                champ = participant["championName"]
                k, d, a = participant["kills"], participant["deaths"], participant["assists"]
                result = "Win" if participant["win"] else "Loss"
                matches.append(f"{match_id} {champ}: {k}/{d}/{a} - {result}")
    return "\n".join(matches)


@mcp.tool()
async def get_recent_matches_tool(game_name: str, tag_line: str, count: int = 3) -> str:
    """
    🕹️ Get the player's recent match history.

    Returns a brief summary of the player's most recent matches, including champion, score, and result.
    """
    puuid = await get_puuid(game_name, tag_line)
    if not puuid:
        return "Failed to find player."
    return await get_recent_matches(puuid, count)



@mcp.tool()
async def get_champion_mastery_tool(game_name: str, tag_line: str, champion_name: str, language: str = "en_US") -> dict[str, Any] | str:
    """
    🎯 Get the player's mastery info for a specific champion.

    Returns detailed mastery data (level, points, last play time, etc.) for the requested champion.
    """
    puuid = await get_puuid(game_name, tag_line)
    if not puuid:
        return "Failed to find player."

    champion_map = await get_champion_map(language)
    champion_id = next((cid for cid, name in champion_map.items() if name.lower() == champion_name.lower()), None)
    if not champion_id:
        return f"Champion '{champion_name}' not found."

    mastery = await riot_request(
        f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{champion_id}"
    )
    if not mastery:
        return f"Could not find mastery data for {champion_name}."

    return {
        "game_name": game_name,
        "tag_line": tag_line,
        "puuid": puuid,
        "champion_name": champion_name,
        "champion_id": champion_id,
        "champion_mastery": mastery
    }


@mcp.tool()
async def get_player_summary(game_name: str, tag_line: str, language: str = "en_US") -> str:
    """
    🧾 Get a complete summary of a player's profile.

    Includes level, solo rank, top champion masteries, and recent matches in a single output.
    """
    puuid = await get_puuid(game_name, tag_line)
    if not puuid:
        return "Failed to find player."

    champ_map = await get_champion_map(language)
    summoner = await get_summoner_by_puuid(puuid)
    if not summoner:
        return "Failed to get summoner profile."

    level = summoner["summonerLevel"]
    rank = await get_rank_by_summoner_id(puuid)
    top_champs = await get_top_champions(puuid, champ_map, count=3)
    matches = await get_recent_matches(puuid)

    return f"""
👤 {game_name} (Level {level})

🏅 Rank: {rank}

🔥 Top Champions:
{top_champs}

🕹️ Recent Matches:
{matches}
"""

@mcp.tool()
async def get_match_summary(match_id: str, puuid: str) -> dict[str, Any] | str:
    """
    📊 Get a detailed summary of a specific match for a given player.

    Extracts and returns only the relevant stats (KDA, damage, vision, win/loss, etc.) from the match.
    """
    match = await riot_request(f"/lol/match/v5/matches/{match_id}", region="asia")
    if not match:
        return "Failed to load match data."

    participant = next((p for p in match["info"]["participants"] if p["puuid"] == puuid), None)
    if not participant:
        return f"No participant found with puuid: {puuid}"

    return {
        "championName": participant["championName"],
        "lane": participant["lane"],
        "role": participant["role"],
        "kills": participant["kills"],
        "deaths": participant["deaths"],
        "assists": participant["assists"],
        "kda": participant["challenges"].get("kda"),
        "killParticipation": participant["challenges"].get("killParticipation"),
        "totalDamageDealtToChampions": participant["totalDamageDealtToChampions"],
        "visionScore": participant["visionScore"],
        "wardsPlaced": participant["wardsPlaced"],
        "wardsKilled": participant["wardsKilled"],
        "win": participant["win"],
        "teamPosition": participant.get("teamPosition"),
        "timePlayed": participant["timePlayed"],
        "gameDuration": match["info"]["gameDuration"],
        "queueId": match["info"]["queueId"],
    }


@mcp.tool()
async def get_upcoming_esport_matches(
    league_slug: str | None = None,
    count: int = 5,
    language: str = "en-US",
) -> str:
    """
    🗓️ Get upcoming LoL esport matches.

    Returns a list of upcoming competitive matches with teams, date, and league.
    Filter by league slug (lck, lec, lcs, lpl, worlds, msi, cblol, pcs, vcs, ljl)
    and limit the number of results with count.
    """
    params: dict[str, Any] = {"hl": language}
    if league_slug:
        league_id = await resolve_league_id(league_slug, language)
        if not league_id:
            return f"League '{league_slug}' not found. Available slugs: {', '.join(ESPORTS_LEAGUE_IDS)}"
        params["leagueId"] = league_id

    data = await esports_request("getSchedule", params)
    if isinstance(data, str):
        return data  # propagate error message

    events = data.get("data", {}).get("schedule", {}).get("events", [])
    upcoming = [e for e in events if e.get("state") in ("unstarted", "inProgress")][:count]

    if not upcoming:
        return "No upcoming matches found."

    lines = []
    for event in upcoming:
        match = event.get("match", {})
        teams = match.get("teams", [])
        team1 = teams[0].get("name", "TBD") if len(teams) > 0 else "TBD"
        team2 = teams[1].get("name", "TBD") if len(teams) > 1 else "TBD"
        start_time = event.get("startTime", "TBD")
        league_name = event.get("league", {}).get("name", "Unknown")
        block_name = event.get("blockName", "")
        state = event.get("state", "")
        state_label = " 🔴 LIVE" if state == "inProgress" else ""
        lines.append(f"📅 {start_time}{state_label}\n   {league_name} — {block_name}\n   {team1} vs {team2}")

    return "\n\n".join(lines)


@mcp.tool()
async def get_esport_teams(
    league_slug: str | None = None,
    language: str = "en-US",
) -> str:
    """
    🛡️ Get LoL esport teams.

    Returns professional teams with their region, code, and slug.
    Optionally filter by league slug (lck, lec, lcs, lpl, worlds, msi, cblol, pcs, vcs, ljl).
    Team slugs returned here can be used with get_esport_players.
    """
    data = await esports_request("getTeams", {"hl": language})
    if isinstance(data, str):
        return data

    teams = data.get("data", {}).get("teams", [])
    if not teams:
        return "No teams found."

    # Keep only teams with a known homeLeague and at least one player (filters out disbanded/unknown teams)
    valid = [
        t for t in teams
        if t.get("slug")
        and t.get("slug") != "tbd"
        and (t.get("homeLeague") or {}).get("name")
        and t.get("players")
    ]

    if league_slug:
        valid = [
            t for t in valid
            if (t.get("homeLeague") or {}).get("name", "").lower() == league_slug.lower()
        ]
        if not valid:
            available = sorted({(t.get("homeLeague") or {}).get("name", "") for t in teams if (t.get("homeLeague") or {}).get("name")})
            return f"No teams found for league '{league_slug}'. Available leagues: {', '.join(available)}"

    lines = [
        f"- {t.get('name', '?')} ({t.get('code', '?')}) | {(t.get('homeLeague') or {}).get('name', '?')} [slug: {t.get('slug', '?')}]"
        for t in valid
    ]
    header = f"Teams in {league_slug.upper()}" if league_slug else "Professional LoL Teams"
    return f"{header} ({len(lines)}):\n" + "\n".join(lines)


@mcp.tool()
async def get_esport_players(team_slug: str, language: str = "en-US") -> str:
    """
    👥 Get the roster of a LoL esport team.

    Returns the current players of a professional team given its slug.
    Example slugs: t1, cloud9, fnatic, g2-esports, team-liquid, gen-g.
    Use get_esport_teams to discover available team slugs.
    """
    # slug param not supported by API → fetch all and filter
    data = await esports_request("getTeams", {"hl": language})
    if isinstance(data, str):
        return data

    all_teams = data.get("data", {}).get("teams", [])
    teams = [t for t in all_teams if t.get("slug", "").lower() == team_slug.lower()]
    if not teams:
        return f"Team '{team_slug}' not found. Use get_esport_teams to browse available teams."

    team = teams[0]
    players = team.get("players", [])
    if not players:
        return f"No players found for {team.get('name', team_slug)}."

    lines = [
        f"- {p.get('summonerName', '?')} | {p.get('role', 'Unknown role').capitalize()} | {p.get('firstName', '')} {p.get('lastName', '')}".strip()
        for p in players
    ]
    return f"🛡️ {team.get('name', team_slug)} Roster ({len(lines)} players):\n" + "\n".join(lines)


@mcp.tool()
async def get_esport_tournaments(league_slug: str | None = None, language: str = "en-US") -> str:
    """
    🏆 Get LoL esport tournaments.

    Returns tournaments with start/end dates and IDs.
    Filter by league slug (lck, lec, lcs, lpl, worlds, msi, cblol, pcs, vcs, ljl).
    Tournament IDs can be used with get_esport_teams to filter teams.
    """
    params: dict[str, Any] = {"hl": language}
    if league_slug:
        league_id = await resolve_league_id(league_slug, language)
        if not league_id:
            return f"League '{league_slug}' not found. Available slugs: {', '.join(ESPORTS_LEAGUE_IDS)}"
        params["leagueId"] = league_id

    data = await esports_request("getTournaments", params)
    if isinstance(data, str):
        return data

    # API returns data.tournaments (flat list) not data.leagues[].tournaments
    tournaments = data.get("data", {}).get("tournaments", [])
    lines = []
    for t in tournaments:
        start = t.get("startDate", "?")
        end = t.get("endDate", "?")
        slug = t.get("slug", "?")
        tid = t.get("id", "?")
        name = t.get("name", slug)
        lines.append(f"🏆 {name} [{slug}]\n   📅 {start} → {end}\n   ID: {tid}")

    if not lines:
        return "No tournaments found."

    return "\n\n".join(lines)


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "sse")
    if transport == "sse":
        mcp.settings.host = "127.0.0.1"
        mcp.settings.port = 8000
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")

