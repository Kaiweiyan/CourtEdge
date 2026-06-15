"""The Odds API client (https://the-odds-api.com).

Returns upcoming NBA games with moneyline odds per bookmaker. Without an API
key (or out of season) it returns None, and the board falls back to sample data.
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import ODDS_API_BASE, ODDS_API_KEY, ODDS_REGION, ODDS_SPORT  # noqa: E402


def get_upcoming_odds(timeout: int = 15) -> list[dict] | None:
    """List of {home, away, commence, books:[{book, home_odds, away_odds}]}."""
    if not ODDS_API_KEY:
        return None
    url = f"{ODDS_API_BASE}/sports/{ODDS_SPORT}/odds"
    params = {
        "apiKey": ODDS_API_KEY, "regions": ODDS_REGION,
        "markets": "h2h", "oddsFormat": "american",
    }
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"Odds API error: {e}")
        return None

    games = []
    for g in data:
        home, away = g.get("home_team"), g.get("away_team")
        books = []
        for bk in g.get("bookmakers", []):
            price = {o["name"]: o["price"]
                     for m in bk.get("markets", []) if m["key"] == "h2h"
                     for o in m["outcomes"]}
            if home in price and away in price:
                books.append({"book": bk["title"],
                              "home_odds": price[home], "away_odds": price[away]})
        if books:
            games.append({"home": home, "away": away,
                          "commence": g.get("commence_time"), "books": books})
    return games or None
