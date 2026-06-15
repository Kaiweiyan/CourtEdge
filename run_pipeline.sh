#!/usr/bin/env bash
# CourtEdge — end-to-end pipeline. Run from the repo root inside the nba-bet env.
#   conda activate nba-bet && bash run_pipeline.sh
set -euo pipefail

echo "[1/4] Ingestion: nba_api -> Parquet -> DB"
python -m src.ingestion.fetch_games

echo "[2/4] Processing: Spark rolling features"
python -m src.processing.features_spark

echo "[2b]  Processing: Elo ratings"
python -m src.processing.elo

echo "[3/4] Model: train + calibrate + evaluate"
python -m src.model.train

# [4] Big-data Spark demo over real play-by-play (~550k+ event rows).
# The pull is rate-limited (~25-30 min); set SKIP_PBP=1 to skip it.
if [ "${SKIP_PBP:-0}" = "1" ]; then
  echo "[4/4] Skipping play-by-play step (SKIP_PBP=1)."
else
  echo "[4/4] Play-by-play: fetch one season (resumable) -> Spark aggregation"
  python -m src.ingestion.fetch_pbp
  python -m src.processing.pbp_spark
fi

echo "Done. Launch the dashboard with:  streamlit run app/dashboard.py"
