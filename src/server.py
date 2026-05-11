from mcp.server.fastmcp import FastMCP, Context
from mcp.server.transport_security import TransportSecuritySettings
from contextlib import asynccontextmanager
from pydantic import BaseModel
import asyncio
import httpx
import json
import os
from typing import Any
from dotenv import load_dotenv

load_dotenv()


# --- Output schemas ---

class DependencyCheck(BaseModel):
    ok: bool
    status_code: int | None = None
    latency_ms: int | None = None
    error: str | None = None

class HealthStatus(BaseModel):
    status: str
    checks: dict[str, DependencyCheck]

class RankInfo(BaseModel):
    tier: str
    rank: str
    lp: int
    wins: int
    losses: int
    winrate: int

class ChampionMastery(BaseModel):
    champion: str
    champion_id: int
    level: int
    points: int

class RecentMatch(BaseModel):
    match_id: str
    champion: str
    kills: int
    deaths: int
    assists: int
    win: bool

class PlayerSummary(BaseModel):
    game_name: str
    tag_line: str
    level: int
    rank: RankInfo | None
    top_champions: list[ChampionMastery]
    recent_matches: list[RecentMatch]

class EsportMatch(BaseModel):
    start_time: str | None
    state: str | None
    league: str | None
    league_slug: str | None
    block: str | None
    team1: str | None
    team2: str | None
    match_id: str | None

class EsportTeam(BaseModel):
    name: str | None
    code: str | None
    slug: str | None
    league: str | None

class EsportPlayer(BaseModel):
    summoner_name: str | None
    role: str | None
    first_name: str | None
    last_name: str | None

class EsportTeamRoster(BaseModel):
    name: str | None
    code: str | None
    slug: str | None
    league: str | None
    players: list[EsportPlayer]

class EsportTournament(BaseModel):
    name: str | None
    slug: str | None
    id: str | None
    start_date: str | None
    end_date: str | None

class ChampionMasteryDetail(BaseModel):
    game_name: str
    tag_line: str
    champion_name: str
    champion_id: int
    level: int
    points: int
    last_play_time: int | None = None
    tokens_earned: int | None = None

class MatchSummary(BaseModel):
    champion: str
    lane: str
    role: str
    kills: int
    deaths: int
    assists: int
    kda: float | None
    kill_participation: float | None
    damage_dealt: int
    vision_score: int
    wards_placed: int
    wards_killed: int
    win: bool
    position: str | None
    time_played: int
    game_duration: int
    queue_id: int


@asynccontextmanager
async def lifespan(server):
    await get_champion_map("en_US")
    await get_champion_map("ko_KR")
    yield


_extra_hosts = [h for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h]
_extra_origins = [o for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o]

mcp = FastMCP("riot",
    lifespan=lifespan,
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["localhost:8000", "127.0.0.1:8000"] + _extra_hosts,
        allowed_origins=_extra_origins,
    ))


@mcp.prompt()
def analyze_player(game_name: str, tag_line: str, region: str = "kr") -> str:
    """
    Analyse complète d'un joueur League of Legends.

    Combine get_player_summary, get_top_champions_tool et get_recent_matches_tool
    pour dresser un profil détaillé du joueur.

    Args:
        game_name: Riot in-game name (e.g. "Faker").
        tag_line: Riot tag (e.g. "T1").
        region: Server region. Options: kr, jp, euw, eune, na, br, lan, las, tr, ru, oce. Default: kr.
    """
    return f"""
    Analyse le joueur {game_name}#{tag_line} sur la région {region}.

    1. Commence par get_player_summary pour avoir une vue d'ensemble (niveau, rang, top champions, matchs récents).
    2. Utilise get_top_champions_tool pour identifier ses champions de prédilection avec le détail des points de maîtrise.
    3. Utilise get_recent_matches_tool pour voir ses performances récentes match par match.
    4. Dresse un bilan : rang solo, champions favoris, tendances victoire/défaite, et style de jeu probable.
    """


@mcp.prompt()
def preview_competition(league: str) -> str:
    """
    Présentation des prochains matchs d'une ligue esport.

    Combine get_upcoming_esport_matches et get_esport_players pour présenter
    les confrontations à venir avec les rosters complets.

    Args:
        league: League identifier. Options: lck, lec, lcs, lpl, worlds, msi, cblol, ljl, vcs, pcs.
    """
    return f"""
    Présente les prochains matchs de la ligue {league}.

    1. Utilise get_upcoming_esport_matches avec league={league} pour lister les matchs à venir et en cours.
    2. Pour chaque match, utilise get_esport_players sur chacune des deux équipes pour récupérer leur roster.
    3. Présente chaque confrontation avec les équipes face à face, les joueurs et leurs rôles, et l'heure de début.
    """


@mcp.prompt()
def scout_team(team: str) -> str:
    """
    Analyse du roster d'une équipe professionnelle.

    Combine get_esport_teams et get_esport_players pour identifier et détailler
    les joueurs d'une équipe.

    Args:
        team: Team identifier (slug). Examples: t1, cloud9, fnatic, g2-esports, gen-g.
              Use get_esport_teams to discover available identifiers.
    """
    return f"""
    Analyse l'équipe {team}.

    1. Si le slug exact n'est pas connu, utilise get_esport_teams pour le trouver (filtre par league si nécessaire).
    2. Utilise get_esport_players avec team={team} pour récupérer le roster complet.
    3. Présente chaque joueur avec son rôle, son nom complet, et son pseudo en jeu.
    """


@mcp.resource("health://status")
async def health_status() -> str:
    """🩺 Connectivity status for all upstream dependencies (Riot API, Esports API, Data Dragon)."""
    import time
    checks: dict[str, DependencyCheck] = {}

    async with httpx.AsyncClient() as client:
        for name, url in [
            ("riot_api", "https://kr.api.riotgames.com/lol/status/v4/platform-data"),
            ("esports_api", f"{ESPORTS_BASE_URL}/getLeagues?hl=en-US"),
            ("ddragon", "https://ddragon.leagueoflegends.com/api/versions.json"),
        ]:
            try:
                t0 = time.time()
                headers = {}
                if name == "riot_api":
                    headers = {"X-Riot-Token": RIOT_API_KEY}
                elif name == "esports_api":
                    headers = {"x-api-key": ESPORTS_API_KEY}
                res = await client.get(url, headers=headers, timeout=5.0)
                checks[name] = DependencyCheck(ok=res.status_code < 400, status_code=res.status_code, latency_ms=round((time.time() - t0) * 1000))
            except Exception as e:
                checks[name] = DependencyCheck(ok=False, error=str(e))

    status = "degraded" if any(not c.ok for c in checks.values()) else "ok"
    return HealthStatus(status=status, checks=checks).model_dump_json(indent=2)

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

# Maps user-facing region slug to (account_routing, summoner_server, match_routing)
REGION_MAP: dict[str, tuple[str, str, str]] = {
    "kr":   ("asia",     "kr",    "asia"),
    "jp":   ("asia",     "jp1",   "asia"),
    "euw":  ("europe",   "euw1",  "europe"),
    "eune": ("europe",   "eune1", "europe"),
    "tr":   ("europe",   "tr1",   "europe"),
    "ru":   ("europe",   "ru",    "europe"),
    "na":   ("americas", "na1",   "americas"),
    "br":   ("americas", "br1",   "americas"),
    "lan":  ("americas", "la1",   "americas"),
    "las":  ("americas", "la2",   "americas"),
    "oce":  ("sea",      "oc1",   "sea"),
}
REGION_LIST = ", ".join(REGION_MAP)


async def esports_request(
    endpoint: str,
    params: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any] | str:
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
                msg = f"[403 Forbidden] The LoL Esports API key is invalid or expired. Endpoint: {endpoint}"
                if ctx:
                    await ctx.warning(msg, logger_name="esports-api")
                return msg
            if res.status_code == 404:
                msg = f"[404 Not Found] Endpoint '{endpoint}' does not exist or params are wrong: {params}"
                if ctx:
                    await ctx.warning(msg, logger_name="esports-api")
                return msg
            if res.status_code >= 400:
                msg = f"[{res.status_code}] API error on '{endpoint}': {res.text[:200]}"
                if ctx:
                    await ctx.warning(msg, logger_name="esports-api")
                return msg
            res.raise_for_status()
            data = res.json()
            if ctx:
                await ctx.debug(f"GET {endpoint} -> {res.status_code}", logger_name="esports-api")
                await ctx.debug(json.dumps(data, ensure_ascii=False, indent=2)[:2000], logger_name="esports-api")
            return data
        except httpx.TimeoutException:
            msg = f"[Timeout] Request to '{endpoint}' timed out after 30s"
            if ctx:
                await ctx.error(msg, logger_name="esports-api")
            return msg
        except httpx.ConnectError as e:
            msg = f"[ConnectError] Cannot reach LoL Esports API: {e}"
            if ctx:
                await ctx.error(msg, logger_name="esports-api")
            return msg
        except Exception as e:
            msg = f"[Error] Unexpected error on '{endpoint}': {type(e).__name__}: {e}"
            if ctx:
                await ctx.error(msg, logger_name="esports-api")
            return msg


async def resolve_league_id(league_slug: str, language: str, ctx: Context | None = None) -> str | None:
    """Resolves a league slug to its ID, checking the local map then the API."""
    league_id = ESPORTS_LEAGUE_IDS.get(league_slug.lower())
    if league_id:
        if ctx:
            await ctx.debug(f"League '{league_slug}' resolved from local map -> {league_id}", logger_name="esports-api")
        return league_id
    if ctx:
        await ctx.debug(f"League '{league_slug}' not in local map, fetching from API", logger_name="esports-api")
    data = await esports_request("getLeagues", {"hl": language}, ctx=ctx)
    if isinstance(data, str):
        return None
    leagues = data.get("data", {}).get("leagues", [])
    match = next((l for l in leagues if l.get("slug", "").lower() == league_slug.lower()), None)
    if not match and ctx:
        await ctx.warning(f"League slug '{league_slug}' not found in API response", logger_name="esports-api")
    return match["id"] if match else None


async def riot_request(
    url: str,
    region: str = "kr",
    params: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> Any:
    headers = {
        "X-Riot-Token": RIOT_API_KEY,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        try:
            full_url = f"https://{region}.api.riotgames.com{url}"
            res = await client.get(full_url, headers=headers, params=params, timeout=30.0)
            res.raise_for_status()
            if ctx:
                await ctx.debug(f"GET {url} [{region}] -> {res.status_code}", logger_name="riot-api")
            return res.json()
        except httpx.HTTPStatusError as e:
            if ctx:
                await ctx.warning(f"HTTP {e.response.status_code} on {url} [{region}]", logger_name="riot-api")
            return None
        except Exception as e:
            if ctx:
                await ctx.error(f"Unexpected error on {url} [{region}]: {type(e).__name__}: {e}", logger_name="riot-api")
            return None


async def get_champion_map(language: str = "en_US", ctx: Context | None = None) -> dict[int, str]:
    if language in CHAMPION_MAP:
        if ctx:
            await ctx.debug(f"Champion map cache hit for '{language}'", logger_name="riot-api")
        return CHAMPION_MAP[language]

    if ctx:
        await ctx.debug(f"Fetching champion map for '{language}' from Data Dragon", logger_name="riot-api")
    async with httpx.AsyncClient() as client:
        version_res = await client.get("https://ddragon.leagueoflegends.com/api/versions.json")
        version = version_res.json()[0]
        champ_res = await client.get(
            f"https://ddragon.leagueoflegends.com/cdn/{version}/data/{language}/champion.json"
        )
        data = champ_res.json()["data"]
        CHAMPION_MAP[language] = {int(c["key"]): c["name"] for c in data.values()}
        return CHAMPION_MAP[language]


async def get_puuid(game_name: str, tag_line: str, account_routing: str = "asia", ctx: Context | None = None) -> str | None:
    url = f"https://{account_routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    headers = {
        "X-Riot-Token": RIOT_API_KEY,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers, timeout=30.0)
            res.raise_for_status()
            if ctx:
                await ctx.debug(f"PUUID resolved for {game_name}#{tag_line} [{account_routing}]", logger_name="riot-api")
            return res.json()["puuid"]
    except httpx.HTTPStatusError as e:
        if ctx:
            await ctx.warning(
                f"PUUID lookup failed for {game_name}#{tag_line} [{account_routing}]: HTTP {e.response.status_code}",
                logger_name="riot-api",
            )
        return None
    except Exception as e:
        if ctx:
            await ctx.error(
                f"PUUID lookup error for {game_name}#{tag_line}: {type(e).__name__}: {e}",
                logger_name="riot-api",
            )
        return None


async def get_summoner_by_puuid(puuid: str, server: str = "kr", ctx: Context | None = None) -> dict[str, Any] | None:
    return await riot_request(f"/lol/summoner/v4/summoners/by-puuid/{puuid}", region=server, ctx=ctx)


async def get_rank_by_summoner_id(puuid: str, server: str = "kr", ctx: Context | None = None) -> RankInfo | None:
    rank_data = await riot_request(f"/lol/league/v4/entries/by-puuid/{puuid}", region=server, ctx=ctx)
    if not rank_data:
        return None

    solo = next((q for q in rank_data if q["queueType"] == "RANKED_SOLO_5x5"), None)
    if not solo:
        return None

    wins, losses = solo["wins"], solo["losses"]
    return RankInfo(
        tier=solo["tier"],
        rank=solo["rank"],
        lp=solo["leaguePoints"],
        wins=wins,
        losses=losses,
        winrate=round(wins / (wins + losses) * 100) if (wins + losses) > 0 else 0,
    )


async def get_top_champions(puuid: str, champ_map: dict[int, str], count: int = 3, server: str = "kr", ctx: Context | None = None) -> list[ChampionMastery]:
    mastery_data = await riot_request(
        f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top",
        region=server,
        params={"count": count},
        ctx=ctx,
    )
    if not mastery_data:
        return []

    return [
        ChampionMastery(
            champion=champ_map.get(c["championId"], f"ID({c['championId']})"),
            champion_id=c["championId"],
            level=c["championLevel"],
            points=c["championPoints"],
        )
        for c in mastery_data
    ]


async def get_recent_matches(puuid: str, count: int = 3, match_routing: str = "asia", ctx: Context | None = None) -> list[RecentMatch]:
    match_ids = await riot_request(
        f"/lol/match/v5/matches/by-puuid/{puuid}/ids",
        region=match_routing,
        params={"count": count},
        ctx=ctx,
    )
    if not match_ids:
        return []

    match_details = await asyncio.gather(*[
        riot_request(f"/lol/match/v5/matches/{mid}", region=match_routing, ctx=ctx)
        for mid in match_ids
    ])

    matches = []
    for match_id, match in zip(match_ids, match_details):
        if match:
            participant = next((p for p in match["info"]["participants"] if p["puuid"] == puuid), None)
            if participant:
                matches.append(RecentMatch(
                    match_id=match_id,
                    champion=participant["championName"],
                    kills=participant["kills"],
                    deaths=participant["deaths"],
                    assists=participant["assists"],
                    win=participant["win"],
                ))
    return matches


def resolve_region(region: str, ctx_label: str = "") -> tuple[str, str, str] | str:
    """Returns (account_routing, server, match_routing) or an error string."""
    mapping = REGION_MAP.get(region.lower())
    if not mapping:
        return f"Unknown region '{region}'. Available: {REGION_LIST}"
    return mapping


@mcp.tool()
async def get_top_champions_tool(
    game_name: str,
    tag_line: str,
    region: str = "kr",
    language: str = "en_US",
    count: int = 3,
    ctx: Context = None,
) -> list[ChampionMastery]:
    """
    🔝 Get the champions a player has the most mastery points on.

    Returns champion name, mastery level (1–10), and total points earned.
    Use this to identify which champions a player plays best.

    Args:
        game_name: Riot in-game name — the part before the # in the Riot ID (e.g. "Faker").
        tag_line: Riot tag — the part after the # (e.g. "T1" or "KR1").
        region: Server region. Options: kr, jp, euw, eune, na, br, lan, las, tr, ru, oce. Default: kr.
        language: Language for champion names (e.g. en_US, fr_FR, ko_KR). Default: en_US.
        count: Number of top champions to return. Default: 3.
    """
    routing = resolve_region(region)
    if isinstance(routing, str):
        raise ValueError(routing)
    account_routing, server, _ = routing

    await ctx.info(f"Fetching top {count} champions for {game_name}#{tag_line} [{region}]", logger_name="riot-api")
    puuid, champ_map = await asyncio.gather(
        get_puuid(game_name, tag_line, account_routing=account_routing, ctx=ctx),
        get_champion_map(language, ctx=ctx),
    )
    if not puuid:
        raise ValueError("Player not found.")

    return await get_top_champions(puuid, champ_map, count, server=server, ctx=ctx)


@mcp.tool()
async def get_recent_matches_tool(
    game_name: str,
    tag_line: str,
    region: str = "kr",
    count: int = 3,
    ctx: Context = None,
) -> list[RecentMatch]:
    """
    🕹️ Get a player's most recent matches.

    Returns champion played, kills/deaths/assists, and win or loss for each match.
    Match IDs returned here can be passed to get_match_summary for detailed stats.

    Args:
        game_name: Riot in-game name — the part before the # in the Riot ID (e.g. "Faker").
        tag_line: Riot tag — the part after the # (e.g. "T1" or "KR1").
        region: Server region. Options: kr, jp, euw, eune, na, br, lan, las, tr, ru, oce. Default: kr.
        count: Number of recent matches to return. Default: 3.
    """
    routing = resolve_region(region)
    if isinstance(routing, str):
        raise ValueError(routing)
    account_routing, _, match_routing = routing

    await ctx.info(f"Fetching {count} recent matches for {game_name}#{tag_line} [{region}]", logger_name="riot-api")
    puuid = await get_puuid(game_name, tag_line, account_routing=account_routing, ctx=ctx)
    if not puuid:
        raise ValueError("Player not found.")
    return await get_recent_matches(puuid, count, match_routing=match_routing, ctx=ctx)


@mcp.tool()
async def get_champion_mastery_tool(
    game_name: str,
    tag_line: str,
    champion_name: str,
    region: str = "kr",
    language: str = "en_US",
    ctx: Context = None,
) -> ChampionMasteryDetail:
    """
    🎯 Get a player's mastery details for a specific champion.

    Returns mastery level, total points, last time the champion was played,
    and tokens earned. Useful for checking how experienced a player is on a given champion.

    Args:
        game_name: Riot in-game name — the part before the # in the Riot ID (e.g. "Faker").
        tag_line: Riot tag — the part after the # (e.g. "T1" or "KR1").
        champion_name: Exact champion name (e.g. "Zed", "Lee Sin", "Aurelion Sol").
        region: Server region. Options: kr, jp, euw, eune, na, br, lan, las, tr, ru, oce. Default: kr.
        language: Language used to look up the champion name. Default: en_US.
    """
    routing = resolve_region(region)
    if isinstance(routing, str):
        raise ValueError(routing)
    account_routing, server, _ = routing

    await ctx.info(f"Fetching mastery for {game_name}#{tag_line} on {champion_name} [{region}]", logger_name="riot-api")
    puuid, champion_map = await asyncio.gather(
        get_puuid(game_name, tag_line, account_routing=account_routing, ctx=ctx),
        get_champion_map(language, ctx=ctx),
    )
    if not puuid:
        raise ValueError("Player not found.")

    champion_id = next((cid for cid, name in champion_map.items() if name.lower() == champion_name.lower()), None)
    if not champion_id:
        await ctx.warning(f"Champion '{champion_name}' not found in champion map", logger_name="riot-api")
        raise ValueError(f"Champion '{champion_name}' not found.")

    mastery = await riot_request(
        f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{champion_id}",
        region=server,
        ctx=ctx,
    )
    if not mastery:
        raise ValueError(f"No mastery data found for {champion_name}.")

    return ChampionMasteryDetail(
        game_name=game_name,
        tag_line=tag_line,
        champion_name=champion_name,
        champion_id=champion_id,
        level=mastery["championLevel"],
        points=mastery["championPoints"],
        last_play_time=mastery.get("lastPlayTime"),
        tokens_earned=mastery.get("tokensEarned"),
    )


@mcp.tool()
async def get_player_summary(
    game_name: str,
    tag_line: str,
    region: str = "kr",
    language: str = "en_US",
    ctx: Context = None,
) -> PlayerSummary:
    """
    🧾 Get a complete profile overview for a League of Legends player.

    Returns account level, solo ranked tier and LP, top 3 champion masteries,
    and 3 recent matches — all in a single call. Use this as a starting point
    before diving into more specific tools.

    Args:
        game_name: Riot in-game name — the part before the # in the Riot ID (e.g. "Faker").
        tag_line: Riot tag — the part after the # (e.g. "T1" or "KR1").
        region: Server region. Options: kr, jp, euw, eune, na, br, lan, las, tr, ru, oce. Default: kr.
        language: Language for champion names (e.g. en_US, fr_FR, ko_KR). Default: en_US.
    """
    routing = resolve_region(region)
    if isinstance(routing, str):
        raise ValueError(routing)
    account_routing, server, match_routing = routing

    await ctx.info(f"Fetching full profile for {game_name}#{tag_line} [{region}]", logger_name="riot-api")
    puuid, champ_map = await asyncio.gather(
        get_puuid(game_name, tag_line, account_routing=account_routing, ctx=ctx),
        get_champion_map(language, ctx=ctx),
    )
    if not puuid:
        raise ValueError("Player not found.")

    summoner, rank, top_champs, matches = await asyncio.gather(
        get_summoner_by_puuid(puuid, server=server, ctx=ctx),
        get_rank_by_summoner_id(puuid, server=server, ctx=ctx),
        get_top_champions(puuid, champ_map, count=3, server=server, ctx=ctx),
        get_recent_matches(puuid, match_routing=match_routing, ctx=ctx),
    )
    if not summoner:
        raise ValueError("Failed to get summoner profile.")

    return PlayerSummary(
        game_name=game_name,
        tag_line=tag_line,
        level=summoner["summonerLevel"],
        rank=rank,
        top_champions=top_champs,
        recent_matches=matches,
    )


@mcp.tool()
async def get_match_summary(
    match_id: str,
    puuid: str,
    region: str = "kr",
    ctx: Context = None,
) -> MatchSummary:
    """
    📊 Get detailed stats for a specific match for one player.

    Returns KDA, kill participation, damage dealt to champions, vision score,
    wards placed/killed, position, time played, and win or loss.
    Requires the match ID (from get_recent_matches) and the player's PUUID.

    Args:
        match_id: Match ID to look up (e.g. "KR_7654321012"). Obtain this from get_recent_matches.
        puuid: The player's unique Riot account identifier (PUUID). Returned by other tools or the Riot API.
        region: Server region. Options: kr, jp, euw, eune, na, br, lan, las, tr, ru, oce. Default: kr.
    """
    routing = resolve_region(region)
    if isinstance(routing, str):
        raise ValueError(routing)
    _, _, match_routing = routing

    await ctx.info(f"Fetching match summary for {match_id} [{region}]", logger_name="riot-api")
    match = await riot_request(f"/lol/match/v5/matches/{match_id}", region=match_routing, ctx=ctx)
    if not match:
        raise ValueError("Failed to load match data.")

    participant = next((p for p in match["info"]["participants"] if p["puuid"] == puuid), None)
    if not participant:
        await ctx.warning(f"No participant found with puuid in match {match_id}", logger_name="riot-api")
        raise ValueError(f"No participant found with puuid: {puuid}")

    return MatchSummary(
        champion=participant["championName"],
        lane=participant["lane"],
        role=participant["role"],
        kills=participant["kills"],
        deaths=participant["deaths"],
        assists=participant["assists"],
        kda=participant["challenges"].get("kda"),
        kill_participation=participant["challenges"].get("killParticipation"),
        damage_dealt=participant["totalDamageDealtToChampions"],
        vision_score=participant["visionScore"],
        wards_placed=participant["wardsPlaced"],
        wards_killed=participant["wardsKilled"],
        win=participant["win"],
        position=participant.get("teamPosition"),
        time_played=participant["timePlayed"],
        game_duration=match["info"]["gameDuration"],
        queue_id=match["info"]["queueId"],
    )


@mcp.tool()
async def get_upcoming_esport_matches(
    league: str,
    count: int = 5,
    language: str = "en-US",
    ctx: Context = None,
) -> list[EsportMatch]:
    """
    🗓️ Get upcoming and live professional LoL esport matches.

    Returns match start time, current state (unstarted or inProgress), competing teams,
    league name, and match ID. Optionally filter by a specific league.

    Args:
        league: League to filter by. Options: lck, lec, lcs, lpl, worlds, msi, cblol, ljl, vcs, pcs.
                Leave empty to get matches across all leagues.
        count: Maximum number of matches to return. Default: 5.
        language: Language for the response. Default: en-US.
    """
    await ctx.info(
        f"Fetching upcoming matches (league={league or 'all'}, count={count})",
        logger_name="esports-api",
    )
    params: dict[str, Any] = {"hl": language}
    if league:
        league_id = await resolve_league_id(league, language, ctx=ctx)
        if not league_id:
            raise ValueError(f"League '{league}' not found. Available: {', '.join(ESPORTS_LEAGUE_IDS)}")
        params["leagueId"] = league_id

    data = await esports_request("getSchedule", params, ctx=ctx)
    if isinstance(data, str):
        raise ValueError(data)

    events = data.get("data", {}).get("schedule", {}).get("events", [])
    upcoming = [e for e in events if e.get("state") in ("unstarted", "inProgress")]
    if league:
        upcoming = [e for e in upcoming if e.get("league", {}).get("name", "").lower() == league.lower()]
    upcoming = upcoming[:count]

    return [
        EsportMatch(
            start_time=event.get("startTime"),
            state=event.get("state"),
            league=event.get("league", {}).get("name"),
            league_slug=event.get("league", {}).get("slug"),
            block=event.get("blockName"),
            team1=event.get("match", {}).get("teams", [{}])[0].get("name") if len(event.get("match", {}).get("teams", [])) > 0 else None,
            team2=event.get("match", {}).get("teams", [{}])[1].get("name") if len(event.get("match", {}).get("teams", [])) > 1 else None,
            match_id=event.get("match", {}).get("id"),
        )
        for event in upcoming
    ]


@mcp.tool()
async def get_esport_teams(
    league: str,
    language: str = "en-US",
    ctx: Context = None,
) -> list[EsportTeam]:
    """
    🛡️ Get the list of professional LoL esport teams.

    Returns team name, short code (e.g. T1, FNC, G2), unique identifier, and home league.
    The identifier in the slug field can be passed to get_esport_players to retrieve the full roster.
    Optionally filter by a specific league.

    Args:
        league: League to filter by. Options: lck, lec, lcs, lpl, worlds, msi, cblol, ljl, vcs, pcs.
                Leave empty to get teams from all leagues.
        language: Language for the response. Default: en-US.
    """
    await ctx.info(f"Fetching esport teams (league={league or 'all'})", logger_name="esports-api")
    data = await esports_request("getTeams", {"hl": language}, ctx=ctx)
    if isinstance(data, str):
        raise ValueError(data)

    teams = data.get("data", {}).get("teams", [])
    valid = [
        t for t in teams
        if t.get("slug")
        and t.get("slug") != "tbd"
        and (t.get("homeLeague") or {}).get("name")
        and t.get("players")
    ]

    if league:
        valid = [
            t for t in valid
            if (t.get("homeLeague") or {}).get("name", "").lower() == league.lower()
        ]

    return [
        EsportTeam(
            name=t.get("name"),
            code=t.get("code"),
            slug=t.get("slug"),
            league=(t.get("homeLeague") or {}).get("name"),
        )
        for t in valid
    ]


@mcp.tool()
async def get_esport_players(team: str, language: str = "en-US", ctx: Context = None) -> EsportTeamRoster:
    """
    👥 Get the current player roster for a professional LoL team.

    Returns the team name, short code, and a list of players with their summoner name,
    role (top, jungle, mid, bot, support), and full name.
    Use get_esport_teams to find the team identifier (slug field).

    Args:
        team: Team identifier (slug). Examples: t1, cloud9, fnatic, g2-esports, gen-g.
              Use get_esport_teams to discover available identifiers.
        language: Language for the response. Default: en-US.
    """
    await ctx.info(f"Fetching roster for team '{team}'", logger_name="esports-api")
    data = await esports_request("getTeams", {"hl": language}, ctx=ctx)
    if isinstance(data, str):
        raise ValueError(data)

    all_teams = data.get("data", {}).get("teams", [])
    matched = [t for t in all_teams if t.get("slug", "").lower() == team.lower()]
    if not matched:
        await ctx.warning(f"Team '{team}' not found", logger_name="esports-api")
        raise ValueError(f"Team '{team}' not found. Use get_esport_teams to browse available teams.")

    team_data = matched[0]
    return EsportTeamRoster(
        name=team_data.get("name"),
        code=team_data.get("code"),
        slug=team_data.get("slug"),
        league=(team_data.get("homeLeague") or {}).get("name"),
        players=[
            EsportPlayer(
                summoner_name=p.get("summonerName"),
                role=p.get("role"),
                first_name=p.get("firstName"),
                last_name=p.get("lastName"),
            )
            for p in team_data.get("players", [])
        ],
    )


@mcp.tool()
async def get_esport_tournaments(
    league: str,
    language: str = "en-US",
    ctx: Context = None,
) -> list[EsportTournament]:
    """
    🏆 Get LoL esport tournaments, optionally filtered by league.

    Returns tournament name, unique identifier, and start/end dates.
    Useful for knowing which splits or international events are scheduled.

    Args:
        league: League to filter by. Options: lck, lec, lcs, lpl, worlds, msi, cblol, ljl, vcs, pcs.
                Leave empty to get tournaments across all leagues.
        language: Language for the response. Default: en-US.
    """
    await ctx.info(f"Fetching tournaments (league={league or 'all'})", logger_name="esports-api")
    params: dict[str, Any] = {"hl": language}
    if league:
        league_id = await resolve_league_id(league, language, ctx=ctx)
        if not league_id:
            raise ValueError(f"League '{league}' not found. Available: {', '.join(ESPORTS_LEAGUE_IDS)}")
        params["leagueId"] = league_id

    data = await esports_request("getTournaments", params, ctx=ctx)
    if isinstance(data, str):
        raise ValueError(data)

    tournaments = data.get("data", {}).get("tournaments", [])
    if league:
        tournaments = [t for t in tournaments if league.lower() in (t.get("slug") or "").lower()]
    return [
        EsportTournament(
            name=t.get("name", t.get("slug")),
            slug=t.get("slug"),
            id=t.get("id"),
            start_date=t.get("startDate"),
            end_date=t.get("endDate"),
        )
        for t in tournaments
    ]


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    if transport == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
