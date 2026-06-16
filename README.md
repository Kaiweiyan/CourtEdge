# CourtEdge — NBA +EV Betting Analytics

> BDA Final Project — *Designing a System That Monetizes Data* (NTU, Spring 2026)

CourtEdge is an end-to-end data system for **serious recreational NBA bettors**. It
does **not** sell "guaranteed picks." It ingests NBA stats + sportsbook odds, runs a
calibrated win-probability model, and helps the user bet smarter via **edge detection**
(model prob vs. market-implied prob), **line shopping**, **Kelly bankroll sizing**, and
**CLV** (Closing Line Value) — the real long-term skill metric.

- **GitHub:** <https://github.com/Kaiweiyan/CourtEdge>
- **Live demo:** <http://140.112.30.184:9999>

See [`spec.md`](spec.md) for the full business + system write-up and
[`research/demand_evidence.md`](research/demand_evidence.md) for the demand analysis.

---

## Architecture (ingestion → storage → processing → delivery)

```
┌──────────────────────────────────────────────────┐
│ INGESTION                                        │
│ nba_api game logs + Play-by-Play V3,             │
│ The Odds API live moneyline                      │
└──────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────┐
│ STORAGE                                          │
│ Raw zone: Parquet (data/raw/, by season)         │
│ Warehouse: SQLite (default) / Postgres           │
└──────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────┐
│ PROCESSING                                       │
│ PySpark rolling form features (no leakage)       │
│ + PBP aggregation (~599k events) + Elo           │
│ + XGBoost (isotonic calib.) + quant layer        │
└──────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────┐
│ DELIVERY                                         │
│ Streamlit dashboard: Today's Board /             │
│ Model Performance / How It Works                 │
└──────────────────────────────────────────────────┘
```

| Layer | Tech | Why |
|---|---|---|
| Ingestion | `nba_api`, `requests` | free, official-ish NBA stats + multi-book odds |
| Raw storage | Parquet (partitioned) | columnar, Spark-friendly data lake |
| Warehouse | SQLite (default) / Postgres | curated query-served tables (`DATABASE_URL` swappable) |
| Processing | **PySpark** (local[*]) | rolling features (window fns) + **aggregating ~550k+ play-by-play event rows**; scales to all-time PBP (~10M+) |
| Model | XGBoost + isotonic calibration | calibrated probs are required for honest edge detection |
| Delivery | Streamlit | deployable web dashboard |

## Results (held-out most-recent season, out-of-sample)

| Model | Accuracy | Log loss | Brier | AUC |
|---|---|---|---|---|
| Elo baseline | 0.654 | 0.616 | 0.214 | 0.723 |
| XGBoost (calibrated) | **0.669** | **0.608** | **0.210** | **0.728** |

**Honest read:** the NBA market is highly efficient, so a calibrated model lands around
65–68% accuracy and only modestly beats Elo. We make **no** profit guarantee — the value
is surfacing occasional mispriced lines, line-shopping, and correct bet sizing. CLV is the
north-star metric.

---

## Quickstart

```bash
# 1. Environment (conda env: nba-bet, python 3.10; needs Java 8/11 for Spark)
conda activate nba-bet
pip install -r requirements.txt

# 2. (optional) live odds — copy .env.example to .env and add an Odds API key.
#    Without a key the dashboard board uses labelled sample data.
cp .env.example .env

# 3. Build everything (ingest -> Spark features -> Elo -> train), ~3-5 min
bash run_pipeline.sh

# 4. Launch the dashboard
streamlit run app/dashboard.py
```

### Reproduce individual steps

```bash
python -m src.ingestion.fetch_games      # nba_api -> Parquet -> DB (team_games, games)
python -m src.processing.features_spark  # Spark window features -> team_form
python -m src.processing.elo             # Elo ratings -> game_elo
python -m src.model.train                # train + calibrate -> metrics, predictions_test
python -m src.model.quant                # unit tests for the odds math
python -m src.model.predict              # print today's board (sample if offseason)

# Big-data Spark demo over real play-by-play (~550k+ event rows for one season):
python -m src.ingestion.fetch_pbp        # nba_api PlayByPlayV3 -> Parquet (resumable, ~25-30 min)
python -m src.processing.pbp_spark       # Spark aggregation -> pbp_game_features, pbp_team_game
```

## Deploy on a remote workstation (fast path — no Spark/Java/rebuild)

The prebuilt `data/courtedge.db` + `data/artifacts/` are committed, and serving the
dashboard does **not** import PySpark. So a fresh clone serves in ~1 minute:

```bash
git clone <your repo>           # on the workstation
cd CourtEdge
python -m venv .venv && source .venv/bin/activate   # or: conda create -n courtedge python=3.10
pip install -r requirements-serve.txt               # lightweight; no pyspark
bash serve.sh 8501                                  # binds 0.0.0.0:8501
```

Open `http://<workstation-ip>:8501`. If that port isn't publicly reachable, tunnel from
your laptop instead: `ssh -L 8501:localhost:8501 user@workstation`, then open
`http://localhost:8501`.

> To **rebuild** the data on the workstation instead (needs Java 8/11 + the full
> `requirements.txt`), run `bash run_pipeline.sh` before serving.

## Repo layout

```
config.py                 # paths, DATABASE_URL, seasons, Kelly params
run_pipeline.sh           # one-command end-to-end build
src/ingestion/            # nba_api -> Parquet -> warehouse
src/processing/           # features_spark.py (Spark), elo.py
src/model/                # dataset.py, train.py, quant.py, predict.py
src/odds/                 # The Odds API client
app/dashboard.py          # Streamlit web app
research/                 # demand evidence write-up
docs/                     # architecture notes
data/                     # raw Parquet (gitignored); courtedge.db + artifacts/ committed for fast serve
```

## Notes & ethics

- Analytics only — **we never accept wagers** (not a gambling operator). 21+; responsible-gambling messaging in-app.
- Respects `nba_api` rate limits and The Odds API ToS. No scraping in the shipped pipeline.
- `torch` is in the env but unused (the model is gradient boosting).
