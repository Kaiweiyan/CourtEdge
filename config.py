"""Central configuration for CourtEdge."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"          # Parquet raw zone (partitioned)
ARTIFACT_DIR = DATA_DIR / "artifacts"  # model, plots, predictions
for d in (DATA_DIR, RAW_DIR, ARTIFACT_DIR):
    d.mkdir(parents=True, exist_ok=True)

# SQLite by default (zero-friction). Swap to Postgres via env, e.g.
#   DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/courtedge
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'courtedge.db'}")

# Seasons to ingest, e.g. "2018-19".  Recent seasons keep the demo fast.
SEASONS = os.getenv(
    "SEASONS",
    "2020-21,2021-22,2022-23,2023-24,2024-25",
).split(",")

# Rolling window (games) for team form features.
ROLL_WINDOW = int(os.getenv("ROLL_WINDOW", "10"))

# The Odds API (https://the-odds-api.com) — optional; board falls back to sample.
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
ODDS_SPORT = "basketball_nba"
ODDS_REGION = "us"

# Fractional Kelly multiplier (safety) and per-bet stake cap (fraction of bankroll).
KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.25"))
MAX_STAKE_FRAC = float(os.getenv("MAX_STAKE_FRAC", "0.05"))
