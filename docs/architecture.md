# Architecture

End-to-end flow: **ingestion → storage → processing → delivery**.

```
┌──────────── INGESTION ────────────┐
│ nba_api  (multi-season game logs)  │   src/ingestion/fetch_games.py
│ The Odds API (live moneyline)      │   src/odds/odds_api.py
└───────────────┬────────────────────┘
                ▼
┌──────────── STORAGE ──────────────┐
│ RAW: Parquet (data/raw/, by season)│
│ WAREHOUSE: SQLite (default)/Postgres│  src/db.py  (DATABASE_URL swappable)
│   tables: team_games, games,        │
│   team_form, game_elo, predictions  │
└───────────────┬────────────────────┘
                ▼
┌──────────── PROCESSING ───────────┐
│ PySpark window functions:          │   src/processing/features_spark.py
│   rolling pre-game form (no leak)  │
│ PySpark over ~550k+ PBP events:    │   src/processing/pbp_spark.py
│   per-game / per-team aggregation  │
│ Elo ratings (sequential, pandas)   │   src/processing/elo.py
│ XGBoost + isotonic calibration,    │   src/model/train.py
│   honest time-based split          │
│ Quant layer: edge / EV / Kelly/CLV │   src/model/quant.py
└───────────────┬────────────────────┘
                ▼
┌──────────── DELIVERY ─────────────┐
│ Streamlit dashboard                │   app/dashboard.py
│  • Today's Board (edge, price, Kelly)
│  • Model Performance (calibration) │
│  • How It Works                    │
└────────────────────────────────────┘
```

## Design decisions

- **SQLite by default** for zero-friction reproducibility; `DATABASE_URL` switches to
  Postgres unchanged (SQLAlchemy). Postgres + MinIO is the documented production path.
- **Spark in `local[*]`** demonstrates the distributed paradigm (DataFrame API, window
  functions, partitioned Parquet I/O). The same code scales to a cluster; the documented
  big-data target is full play-by-play (~10M+ rows) vs. game-level here for the overnight build.
- **Isotonic calibration** is deliberate: edge = `model_prob − market_implied_prob` is only
  meaningful if `model_prob` is well-calibrated.
- **No data leakage:** all rolling features use the *previous* N games (Spark
  `rowsBetween(-N, -1)`); the model is split strictly by time (train → validate/calibrate →
  most-recent test season).

## Scaling path (10× / 100×)

- Swap SQLite → Postgres; raw Parquet → MinIO/S3; Spark local → cluster (YARN/K8s).
- Add full play-by-play ingestion + streaming odds (Kafka) for live line-movement & CLV capture.
- Orchestrate with Airflow (daily batch DAG + odds poller) — see `spec.md` §4.
