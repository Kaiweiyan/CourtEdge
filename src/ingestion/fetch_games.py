"""Ingestion: pull NBA team game logs (multi-season) via nba_api.

Flow:  nba_api  ->  raw Parquet (raw zone)  ->  curated tables in SQLite/Postgres.

Output tables:
  team_games : one row per team per game (long form)
  games      : one row per game (home/away paired, with target home_win)
"""
from __future__ import annotations

import sys
import time

import pandas as pd
from nba_api.stats.endpoints import leaguegamelog

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from config import RAW_DIR, SEASONS  # noqa: E402
from src.db import write_df  # noqa: E402

HEADERS_TIMEOUT = 60


def fetch_season(season: str, max_retries: int = 3) -> pd.DataFrame:
    """One row per team per regular-season game for a season."""
    for attempt in range(1, max_retries + 1):
        try:
            log = leaguegamelog.LeagueGameLog(
                season=season,
                season_type_all_star="Regular Season",
                timeout=HEADERS_TIMEOUT,
            )
            df = log.get_data_frames()[0]
            df["SEASON"] = season
            print(f"  {season}: {len(df)} team-game rows")
            return df
        except Exception as e:  # noqa: BLE001
            print(f"  {season}: attempt {attempt} failed ({e}); retrying...")
            time.sleep(2 * attempt)
    raise RuntimeError(f"Failed to fetch season {season}")


def build_team_games(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(
        columns={
            "TEAM_ID": "team_id",
            "TEAM_ABBREVIATION": "team",
            "GAME_ID": "game_id",
            "GAME_DATE": "game_date",
            "MATCHUP": "matchup",
            "WL": "wl",
            "PTS": "pts",
            "SEASON": "season",
        }
    )
    df["game_date"] = pd.to_datetime(df["game_date"])
    df["is_home"] = df["matchup"].str.contains("vs.").astype(int)
    df["win"] = (df["wl"] == "W").astype(int)
    cols = ["game_id", "game_date", "season", "team_id", "team", "is_home", "pts", "win"]
    return df[cols].sort_values(["game_date", "game_id"]).reset_index(drop=True)


def build_games(team_games: pd.DataFrame) -> pd.DataFrame:
    """Pair the two team rows per game into one home/away row."""
    home = team_games[team_games.is_home == 1].rename(
        columns={"team_id": "home_team_id", "team": "home_team", "pts": "home_pts"}
    )
    away = team_games[team_games.is_home == 0].rename(
        columns={"team_id": "away_team_id", "team": "away_team", "pts": "away_pts"}
    )
    g = home.merge(
        away[["game_id", "away_team_id", "away_team", "away_pts"]],
        on="game_id",
        how="inner",
    )
    g["home_win"] = (g["home_pts"] > g["away_pts"]).astype(int)
    cols = [
        "game_id", "game_date", "season",
        "home_team_id", "home_team", "home_pts",
        "away_team_id", "away_team", "away_pts", "home_win",
    ]
    return g[cols].sort_values("game_date").reset_index(drop=True)


def main():
    print(f"Ingesting seasons: {SEASONS}")
    frames = []
    for season in SEASONS:
        frames.append(fetch_season(season))
        time.sleep(1)  # be polite to stats.nba.com
    raw = pd.concat(frames, ignore_index=True)

    # raw zone (Parquet)
    raw_path = RAW_DIR / "league_game_log.parquet"
    raw.to_parquet(raw_path, index=False)
    print(f"Raw -> {raw_path} ({len(raw)} rows)")

    team_games = build_team_games(raw)
    games = build_games(team_games)

    write_df(team_games, "team_games")
    write_df(games, "games")
    print(f"Wrote team_games ({len(team_games)}) and games ({len(games)}) to DB.")
    print(f"Date range: {games.game_date.min().date()} -> {games.game_date.max().date()}")


if __name__ == "__main__":
    main()
