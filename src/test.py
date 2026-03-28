import asyncio
import httpx
import os
from typing import Any
from dotenv import load_dotenv

from server import get_player_summary

load_dotenv()

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
if not RIOT_API_KEY:
    raise EnvironmentError("RIOT_API_KEY is not set in the environment variables.")

async def get_top_champions_tool(game_name: str, tag_line: str, language: str = "en_US", count: int = 3) -> str:
    """
    🔝 Get the player's top champion masteries.

    Returns a list of the player's most-played champions based on mastery points.
    """
    puuid = await get_puuid(game_name, tag_line)
    if not puuid:
      return "Failed to find player."
    print(f"PUUID for {game_name}#{tag_line}: {puuid}")




async def get_puuid(game_name: str, tag_line: str) -> str | None:
    url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Safari/605.1.15",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Charset": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://developer.riotgames.com",
        "X-Riot-Token": RIOT_API_KEY,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers)
            res.raise_for_status()
            json = res.json()
            puuid = json.get("puuid")
            return puuid
    except Exception:
        return None
    

if __name__ == "__main__":

    game_name = "TOPKING"
    tag_line = "asd"
    language = "en_US"
    count = 3

    result = asyncio.run(get_player_summary(game_name, tag_line, language))