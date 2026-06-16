# CourtEdge — NBA +EV Betting Analytics Platform

> **BDA Final Project — Work Plan / Spec**
> Course: Big Data Systems (NTU, Spring 2026) — *"Designing a System That Monetizes Data"*
> Working product name: **CourtEdge** (placeholder, rename freely)

---

## 0. One-paragraph pitch

CourtEdge is an analytics platform for **serious recreational NBA bettors** in the
US legal-sports-betting market. It does **not** sell "guaranteed picks." Instead it
ingests NBA stats + multi-sportsbook odds, runs a calibrated win-probability model,
and helps the user bet smarter through four concrete, defensible features:
**edge detection** (model probability vs. market-implied probability), **line
shopping** (best price across books), **CLV tracking** (Closing Line Value — the
real long-term skill metric), and **Kelly bankroll sizing**. The monetized asset is
the *refined data product* — odds + model probabilities + edge surfaced in real time.

**Why this framing wins the rubric:** the NBA market is highly efficient, so a claim
of "we beat the market" is hard to defend. But "we help you get the best price, track
your CLV, and size bets correctly" provably saves/makes money and sidesteps that trap —
while the model stays the technical centerpiece.

---

## 1. Target Customer (Rubric Component 1 — 20%)

**Primary segment:** US-based *serious recreational* NBA bettors — people who already
bet regularly (have accounts at 2+ sportsbooks), bet for profit not just entertainment,
but are not professional syndicates. Post-2018 (PASPA repeal) sports betting is legal in
38+ states, creating a large, growing, English-speaking market.

**The job they're trying to do today:**
- Manually check odds across DraftKings / FanDuel / BetMGM / etc. to find the best line.
- Guess whether a line is "good value" without a probabilistic baseline.
- Track bets in a spreadsheet (most don't track CLV at all).
- Size bets by gut feel, not bankroll math.

**Current workarounds:** spreadsheets, free Reddit picks, scattered odds-comparison
sites, expensive incumbents (OddsJam, Action Network, Unabated at \$30–150/mo).

**Why CourtEdge is better than the status quo:** one place that unifies model edge +
line shopping + CLV tracking + Kelly sizing, with transparent methodology (no "trust me"
black box). Cheaper, more focused than incumbents.

**Secondary segment (future):** sell the model-probability + edge **data feed via API**
to other tool builders (B2B2X). Out of scope for v1 but mentioned for go-to-market.

---

## 2. Evidence of Demand & Willingness to Pay (Rubric Component 2 — 25%)

> The rubric wants the **full data-acquisition process**, not just a conclusion. Plan to
> document each step (reuse HW2 methodology).

**Planned evidence (do these and record the raw data in the repo):**

1. **Public-data analysis**
   - Reddit `r/sportsbook` (~600k+ members), `r/dfsports` — scrape/manually sample
     threads about model-building, line shopping, CLV; quantify how often these pains
     come up.
   - Google Trends for "NBA betting model", "+EV betting", "line shopping", "CLV".
   - App-store reviews of incumbent apps (what users praise / complain about → unmet needs).
2. **Competitor pricing benchmarks** (willingness-to-pay anchor)
   - Tabulate OddsJam, Action Network, Unabated, Outlier pricing tiers. Existing
     \$30–150/mo subscriptions prove a paying market exists.
3. **Small primary survey / interviews** (5–15 respondents from Reddit or friends who bet)
   - Questions: Do you track CLV? How many books do you check? Would you pay \$X/mo for
     auto line-shop + edge + CLV? What's missing in your current tool?
   - Include the questionnaire + response summary in the repo (`/research`).
4. **Quantified WTP estimate**
   - Monetary: target price point derived from survey + competitor anchor (e.g. \$15–25/mo
     undercut tier).
   - Non-monetary: time saved per night vs. manual line shopping (estimate minutes × games).

**Deliverable:** `/research/demand_evidence.md` documenting the journey from vague idea →
defensible demand claim, plus raw artifacts (survey responses, screenshots, trend exports).

---

## 3. Go-to-Market Difficulties (Bonus Component 3 — up to +10%)

Address honestly — this is where domain credibility shows:

- **Market efficiency / trust:** NBA closing lines are near-optimal. We must NOT promise
  profit. Build trust via a *transparent, auditable CLV track record* and open methodology,
  not hype. This honesty is the differentiator from the scam "tout" industry.
- **Legal & compliance:** We are **analytics only — we never accept bets**, which keeps us
  out of gambling-operator licensing. Still: state-by-state advertising rules, affiliate
  disclosure, responsible-gambling messaging, age-gating. Must respect each book's ToS.
- **Data acquisition costs & risk:** `nba_api` is unofficial & rate-limited; The Odds API
  free tier is tiny (≈500 req/mo) → polling for line movement gets expensive at scale;
  scraping Basketball Reference has ToS/robots.txt constraints. Discuss unit economics:
  odds-API cost scales with polling frequency × games × books.
- **Cold-start / data volume:** need historical seasons to backfill before the model is
  credible; CLV track record needs time to accumulate.
- **Competition & moats:** incumbents are well-funded. Honest moat assessment: focus +
  transparency + price, not data exclusivity (data is largely public). Weak moat — say so.
- **Unit economics:** at what MRR does odds-API + hosting break even? Sketch at 100 / 1k
  users.

---

## 4. System Design (Rubric Component 4 — 40%, the biggest single chunk)

### 4.1 Architecture overview

```
                          ┌─────────────────── INGESTION ───────────────────┐
  External sources        │  Airflow DAG (daily batch)   Odds poller (mins)  │
  ─────────────────       │  ┌──────────────┐            ┌────────────────┐  │
  nba_api (stats) ───────►│  │ stats fetcher│            │ odds snapshotter│ │
  The Odds API   ───────►│  │ schedule/inj │            │ (line movement) │  │
  Basketball-Ref ───────►│  │ scraper      │            └────────┬────────┘  │
  Kaggle (backfill) ────►│  └──────┬───────┘                     │           │
                          └─────────┼─────────────────────────────┼──────────┘
                                    ▼                             ▼
                          ┌──────────────── STORAGE ─────────────────────────┐
                          │  RAW ZONE: Parquet (partitioned by date)          │
                          │           + MinIO/S3-compatible object store      │
                          │  WAREHOUSE: PostgreSQL (curated tables)           │
                          └──────────────────────┬───────────────────────────┘
                                                 ▼
                          ┌──────────────── PROCESSING ──────────────────────┐
                          │  Spark (PySpark):                                 │
                          │   • multi-season play-by-play backfill (10M+ rows)│
                          │   • rolling-window team/player features           │
                          │   • Elo / rest / B2B / market-implied prob        │
                          │  ML: XGBoost/LightGBM + probability calibration   │
                          │  Backtester: ROI / CLV / hit-rate, walk-forward   │
                          └──────────────────────┬───────────────────────────┘
                                                 ▼
                          ┌──────────────── DELIVERY ────────────────────────┐
                          │  FastAPI  ──►  Next.js dashboard (web app)        │
                          │  Endpoints: /board /game/{id} /lines /clv /track  │
                          └───────────────────────────────────────────────────┘
```

### 4.2 Data sources

| Source | What | Access | Notes / risk |
|---|---|---|---|
| `nba_api` | box scores, game logs, **play-by-play**, schedule | free Python wrapper | unofficial, rate-limited (~0.6s/req), throttle + retry |
| The Odds API | moneyline/spread/totals across US books | REST, free tier ~500/mo | poll to capture line movement + closing line |
| Basketball Reference | advanced stats, injuries (backfill) | scrape | respect robots.txt/ToS, rate-limit, educational use |
| Kaggle NBA datasets | bulk historical games + PBP | download | for backtesting / cold-start backfill |

### 4.3 Storage (why these tools fit the scale)

- **Raw zone — Parquet, partitioned by `date`/`season`**, optionally in **MinIO** (S3-compatible)
  to tell the "object storage / data lake" story. Columnar Parquet = efficient Spark reads.
- **Warehouse — PostgreSQL** for curated, query-served tables:
  `teams, games, player_game_logs, odds_snapshots, features, predictions, clv_records, users, bets`.
- **PBP** stays in Parquet (too big/row-heavy for transactional Postgres) → processed by Spark.

### 4.4 Processing (the legitimate "big data" core)

- **Spark (PySpark)** for historical backfill: full multi-season play-by-play is **tens of
  millions of rows** — this justifies distributed processing honestly. Use window functions
  for rolling aggregates; compute Elo, pace, off/def rating, rest days, B2B, travel.
- **Feature table** materialized to Postgres/Parquet, keyed by `(game_id, team_id)`.
- **Modeling:** logistic-regression baseline → XGBoost/LightGBM. **Time-series walk-forward
  validation** (train on past, test on future — no leakage). **Probability calibration**
  (isotonic/Platt) is essential: edge = `model_prob − market_implied_prob` only makes sense
  if model_prob is well-calibrated.
- **Backtester:** simulate the +EV strategy out-of-sample; report **ROI, CLV, hit-rate vs.
  closing line, Brier score, log loss, calibration curve**. North-star metric = **CLV**.

### 4.5 Model features (engineered)

- Team rolling form: last 5/10 game off/def rating, net rating, pace, points for/against.
- Context: rest days, back-to-back, 3-in-4, travel distance / time-zone change, altitude (DEN), home/away splits.
- Roster: star player on/off, injury availability, projected minutes.
- Strength: Elo / power rating, head-to-head history.
- **Market features (strongest):** opening line, line movement, market-implied probability.

### 4.6 Delivery

- **Backend:** FastAPI. Key endpoints:
  - `GET /board?date=` — today's games: model prob, best odds per market, implied prob, edge %, Kelly stake.
  - `GET /game/{id}` — line-movement chart, feature breakdown, injuries, matchup history.
  - `GET /lines/{id}` — full odds-shopping table across books.
  - `GET /clv` & `POST /bets` — bet tracker + CLV computation.
  - `GET /performance` — backtest + calibration + historical CLV (transparency).
- **Frontend:** see §5.

---

## 5. Frontend / UI Design (web app — deploy on your school workstation)

**Stack:** Next.js (React) + Tailwind + a charts lib (Recharts/visx). Responsive (works as
website now; same components can wrap into an app later).

**Pages:**

1. **Today's Board** *(home)* — table/cards of today's games. Columns: matchup, model win
   prob, best available odds (book logo), market-implied prob, **edge %** (color-coded),
   recommended Kelly stake. Sort by edge. This is the money screen.
2. **Game Detail** — line-movement chart over time, model breakdown (top features), rest/injury
   context, H2H history, per-market edges (ML / spread / total).
3. **Line Shopping** — per game: odds across all books, best price highlighted, "you save X%".
4. **Bet Tracker** — log a bet; system records the line, later grabs the closing line, computes
   **CLV**, running ROI, bankroll chart. The retention hook.
5. **Model Performance / Transparency** — backtest ROI, calibration plot, historical CLV track
   record. This is what earns *trust* (see §3).
6. (Auth: lightweight — email or even local for demo; needed for tracker.)

**Design principles:** clarity over flash; numbers are the product; always show methodology /
confidence; responsible-gambling footer.

---

## 6. Tech Stack Summary

| Layer | Choice |
|---|---|
| Orchestration | Airflow (daily DAG) + lightweight odds poller (APScheduler/cron) |
| Ingestion | Python (`nba_api`, `requests`, `beautifulsoup4`) |
| Raw storage | Parquet (+ optional MinIO/S3) |
| Warehouse | PostgreSQL |
| Processing | **PySpark** (PBP + features), pandas (glue) |
| ML | scikit-learn, XGBoost/LightGBM, calibration |
| Backend | FastAPI + SQLAlchemy |
| Frontend | Next.js + Tailwind + Recharts |
| Deploy | School workstation (Docker Compose); FastAPI + Postgres + Next.js |

---

## 7. Repository Structure (for the GitHub deliverable)

```
courtedge/
├── README.md                  # how to run locally / access demo + architecture overview
├── docker-compose.yml         # postgres + minio + api + web
├── ingestion/
│   ├── dags/                  # Airflow daily DAG
│   ├── stats_fetcher.py       # nba_api pulls
│   ├── odds_poller.py         # Odds API snapshots
│   └── scrapers/              # basketball-ref (rate-limited)
├── processing/
│   ├── spark/                 # PySpark jobs: pbp backfill, feature build
│   ├── features.py
│   ├── model/                 # train, calibrate, walk-forward CV
│   └── backtest/              # ROI / CLV / metrics
├── api/                       # FastAPI app
├── web/                       # Next.js dashboard
├── research/
│   ├── demand_evidence.md     # Component 2 write-up + raw artifacts
│   └── survey/                # questionnaire + responses
├── data/                      # sample data + download scripts (reproducibility)
└── docs/
    └── architecture.md        # mirrors PDF diagram
```

---

## 8. Milestones (adjust to your actual deadline)

> Phase-based; compress/expand per time available. Recommend building the thin end-to-end
> slice first, then widen.

- **M1 — Data plumbing (thin slice):** ingest one season of games + current odds → Parquet →
  Postgres. Verify a single game flows end-to-end.
- **M2 — Spark backfill + features:** multi-season PBP via Spark → feature table. Elo + rolling
  + market features.
- **M3 — Model + backtest:** baseline → XGBoost, calibration, walk-forward CV, CLV/ROI backtester.
  *Be honest about results.*
- **M4 — API + frontend (Today's Board + Game Detail + Line Shopping):** the core demo.
- **M5 — Bet tracker + CLV + Performance page:** retention + transparency features.
- **M6 — Demand research:** run survey, gather public-data evidence, write `demand_evidence.md`.
- **M7 — Deploy on workstation** (Docker Compose) + write report + record architecture diagram.
- **M8 — Report polish:** map every section to the rubric; finalize PDF with repo + live URL on page 1.

---

## 9. Deliverables Checklist (maps to rubric)

- [ ] **PDF report** `<student_id>.pdf` — GitHub URL + live URL on **page 1**.
  - [ ] §1 Target customer (specific segment, job, why-better) — 20%
  - [ ] §2 Demand evidence + full acquisition process — 25%
  - [ ] §4 System design + architecture diagram + code quality — 40%
  - [ ] Clear writing + diagrams — 15%
  - [ ] §3 Go-to-market difficulties — bonus +10%
- [ ] **GitHub repo** — all ingestion/processing/delivery code, README, sample data, repro scripts.
- [ ] **Live deployment** on school workstation — bonus +10%.

---

## 10. Honesty Guardrails (keep the project defensible)

1. **Never claim guaranteed profit.** Report calibration + CLV honestly, even if ROI ≈ break-even.
2. **No data leakage:** strictly time-ordered train/test; market features must be pre-game only.
3. **Respect ToS / robots.txt / rate limits;** add responsible-gambling + age messaging.
4. **CLV is the north-star**, not win rate — frame all results around it.

---

## 11. Implementation Details (concrete specs to build from)

### 11.1 Database schema sketch (PostgreSQL)

```
teams(team_id PK, abbr, name, conference, division)
games(game_id PK, date, season, home_team_id FK, away_team_id FK,
      home_score, away_score, tipoff_utc, status)
player_game_logs(game_id FK, player_id, team_id FK, min, pts, reb, ast, ...,
                 PK(game_id, player_id))
odds_snapshots(id PK, game_id FK, book, market, side, american_odds,
               captured_at)                       -- time series, append-only
features(game_id FK, team_id FK, <elo, rest_days, b2b, roll_off_rtg,
         roll_def_rtg, pace, market_implied_prob, ...>, PK(game_id, team_id))
predictions(id PK, game_id FK, model_version, market, side, model_prob, created_at)
users(id PK, email, created_at)
bets(id PK, user_id FK, game_id FK, market, side, stake, odds_taken, placed_at)
clv_records(bet_id FK, closing_odds, clv_pct, computed_at)
```

Raw **play-by-play stays in Parquet** (partitioned by season/date), not in Postgres.

### 11.2 The quant layer (exact formulas — this is the product)

American odds → **implied probability**:

- negative (`-150`): `imp = (-o) / (-o + 100)`  → 0.60
- positive (`+130`): `imp = 100 / (o + 100)`     → 0.435

American → **decimal**: neg `d = 100/(-o)+1`; pos `d = o/100+1`.

**De-vig** a 2-way market (fair prob): `p_fair_A = imp_A / (imp_A + imp_B)`.

**Bet is +EV** when `p_model > imp(offered price)`. Expected value per unit:
`EV = p_model·(d − 1) − (1 − p_model)`.

**Displayed edge %** = `p_model − imp(offered)`.

**Kelly stake**: `f* = (b·p − q) / b`, where `b = d − 1`, `p = p_model`, `q = 1 − p`.
Use **fractional Kelly (e.g. 0.25×)** and cap per-bet stake for safety.

**CLV**: compare the price you took vs the **closing line** (last snapshot before
`tipoff_utc`). Positive CLV ⇔ `imp(your_odds) < imp(closing_odds)` (you beat the close).

### 11.3 Odds polling / closing-line capture

- Poll The Odds API on a tapering cadence: e.g. every 60 min during the day, every
  5–10 min in the final hour before tip-off. Store each pull as an `odds_snapshots` row.
- **Closing line** = the last snapshot with `captured_at < tipoff_utc` per `(game_id, book, market, side)`.
- Free tier (~500 req/mo) is tight → for the demo, restrict to a few games/books;
  use a Kaggle historical odds dataset for backtesting. (Feeds §3 unit economics.)

### 11.4 Spark deployment reality (be honest in the report)

- Runs in **`local[*]` (single-node) mode** on the workstation. This still genuinely
  demonstrates the distributed paradigm: DataFrame API, window functions for rolling
  features, partitioned Parquet I/O — and the same code scales to a cluster unchanged.
- **Data-volume justification (state concretely):** ~450 PBP events/game ×
  ~1,230 regular-season games/season ≈ **0.55M rows/season**; 15+ seasons (+playoffs)
  ⇒ **~10M+ rows** — beyond comfortable single-process pandas, the legit big-data core.
- Requires **JDK 11/17** on the workstation (check before M2).

### 11.5 Secrets & reproducibility

- API keys via `.env` (gitignored) + commit a **`.env.example`** template.
- Commit **sample data** (one season slice) + **download scripts** so graders can
  reproduce the pipeline without your keys (rubric requires this).

### 11.6 MVP scope tiers (pick the cut-line by deadline)

- **Tier 0 — must-have demo:** ingest current season + live odds → features →
  calibrated model → **Today's Board** (edge + best price + Kelly) → deployed.
  Spark backfill on ≥3 seasons. Backtest with honest CLV/ROI. Demand research write-up.
- **Tier 1 — strong:** + Game Detail (line-movement chart) + Line Shopping page +
  Model Performance/transparency page.
- **Tier 2 — stretch:** + Bet Tracker w/ live CLV + auth + odds streaming + Airflow DAG.

> Build **Tier 0 end-to-end first**, then widen. A working thin slice beats a half-built
> wide one.

### 11.7 Note on builder jurisdiction

We build from Taiwan for the US market. CourtEdge is an **analytics tool only — it never
accepts wagers**, so it is not a gambling operator in any jurisdiction; it consumes public
US stats/odds data. (Reinforces the legal stance in §3.)

---

## 12. What was actually built (one-day solo MVP — ACTIVE)

Due-tomorrow, solo → shipped **Tier 0** end-to-end. Report matches what exists.

**Built & verified:**

- **Ingestion** (`src/ingestion/fetch_games.py`): `nba_api` 5 seasons (2020–21 … 2024–25)
  → Parquet raw zone → SQLite (`games` 5,995, `team_games` 12,000).
- **Processing — Spark** (`src/processing/features_spark.py`): window-function rolling
  pre-game form features (no leakage) → `team_form`. **Elo** (`elo.py`) → `game_elo`.
- **Big-data Spark** (`src/processing/pbp_spark.py`): aggregates **~550k+ real
  play-by-play event rows** (one full season, `nba_api` PlayByPlayV3) into per-game and
  per-team descriptors (lead changes, max margin, OT, FG%/threes) → `pbp_game_features`,
  `pbp_team_game`. This is the genuine distributed-processing workload.
- **Model** (`src/model/train.py`): XGBoost + isotonic calibration, honest time split.
  Held-out test season: **acc 0.669, log loss 0.608, Brier 0.210, AUC 0.728**, beating an
  Elo baseline (0.654) — realistic, no overfit miracle.
- **Quant** (`src/model/quant.py`): implied/de-vig/edge/EV/Kelly/CLV (unit-tested).
- **Delivery** (`app/dashboard.py`): Streamlit web app — Today's Board (edge/price/Kelly),
  Model Performance (metrics + calibration plot), How It Works. Deployable on the workstation.
- Docs: `README.md`, `research/demand_evidence.md`, `docs/architecture.md`, `run_pipeline.sh`.

**Honestly descoped → write up as future work (matches §3/§4 scaling path):**

- SQLite instead of Postgres+MinIO+docker (SQLAlchemy keeps it swappable).
- Spark on **game-level** data (~12k rows), not full **play-by-play** (~10M+) — same code scales.
- Streamlit instead of FastAPI + Next.js. Single dashboard, no auth.
- Live **historical-odds CLV/ROI backtest** needs paid odds history → board uses live odds
  if a key is set, else a **labelled sample board**; model is validated statistically
  (calibration) instead. Bet Tracker / streaming odds / Airflow not built.

**Before submitting:** add GitHub + live URLs to page 1; verify the `[verify]` figures in
`research/demand_evidence.md`; run a real mini-survey if time permits.
