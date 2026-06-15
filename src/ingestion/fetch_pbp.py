"""Ingestion: full-season play-by-play via nba_api -> Parquet (raw zone).

This is the genuine "big data" source: ~550k+ event rows for one season. The pull
is rate-limited, retried, and **resumable** (re-run to continue where it stopped).

Usage:
    python -m src.ingestion.fetch_pbp                 # season from PBP_SEASON env or default
    PBP_SEASON=2023-24 python -m src.ingestion.fetch_pbp
    PBP_MAX_GAMES=5 python -m src.ingestion.fetch_pbp # quick test
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import playbyplayv3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import RAW_DIR  # noqa: E402
from src.db import read_sql  # noqa: E402

SEASON = os.getenv("PBP_SEASON", "2023-24")
MAX_GAMES = int(os.getenv("PBP_MAX_GAMES", "0"))  # 0 = all
SLEEP = float(os.getenv("PBP_SLEEP", "0.7"))
PBP_DIR = RAW_DIR / "pbp"
PBP_DIR.mkdir(parents=True, exist_ok=True)
OUT = PBP_DIR / f"season={SEASON}.parquet"

# PlayByPlayV2 is deprecated (returns empty); V3 is the current endpoint.
KEEP = [
    "gameId", "actionNumber", "period", "clock", "teamId", "teamTricode",
    "scoreHome", "scoreAway", "isFieldGoal", "shotResult", "shotValue", "actionType",
]
GID_COL = "gameId"


def game_ids_for_season(season: str) -> list[str]:
    df = read_sql("SELECT game_id FROM games WHERE season = :s ORDER BY game_date", s=season)
    return [str(g).zfill(10) for g in df.game_id.tolist()]


def fetch_one(game_id: str, retries: int = 3) -> pd.DataFrame | None:
    for attempt in range(1, retries + 1):
        try:
            df = playbyplayv3.PlayByPlayV3(game_id=game_id, timeout=30).get_data_frames()[0]
            cols = [c for c in KEEP if c in df.columns]
            return df[cols]
        except Exception as e:  # noqa: BLE001
            if attempt == retries:
                print(f"  !! {game_id} failed after {retries} tries ({e})")
                return None
            time.sleep(1.5 * attempt)
    return None


def main():
    ids = game_ids_for_season(SEASON)
    if MAX_GAMES:
        ids = ids[:MAX_GAMES]
    print(f"Season {SEASON}: {len(ids)} games to fetch.")

    done: set[str] = set()
    existing = None
    if OUT.exists():
        existing = pd.read_parquet(OUT)
        done = set(existing[GID_COL].astype(str).str.zfill(10).unique())
        print(f"Resuming: {len(done)} games already saved.")

    frames = [existing] if existing is not None else []
    pending = [g for g in ids if g not in done]
    t0 = time.time()
    for i, gid in enumerate(pending, 1):
        df = fetch_one(gid)
        if df is not None:
            frames.append(df)
        time.sleep(SLEEP)
        if i % 50 == 0 or i == len(pending):
            pd.concat(frames, ignore_index=True).to_parquet(OUT, index=False)  # checkpoint
            rows = sum(len(f) for f in frames)
            rate = i / (time.time() - t0)
            eta = (len(pending) - i) / rate if rate else 0
            print(f"  {i}/{len(pending)} games | {rows:,} rows | "
                  f"{rate:.2f} g/s | ETA {eta/60:.1f} min")

    final = pd.concat(frames, ignore_index=True)
    final.to_parquet(OUT, index=False)
    print(f"Done. {final[GID_COL].nunique()} games, {len(final):,} event rows -> {OUT}")


if __name__ == "__main__":
    main()
