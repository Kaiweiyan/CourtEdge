"""CourtEdge dashboard — deployable web app (Streamlit).

Pages:
  • Today's Board     — model edge vs. market, best price, Kelly stake
  • Model Performance — honest held-out metrics + calibration (the trust layer)
  • How It Works      — pipeline + methodology

Run:  streamlit run app/dashboard.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import ARTIFACT_DIR, KELLY_FRACTION, MAX_STAKE_FRAC  # noqa: E402
from src.db import read_sql, table_exists  # noqa: E402

st.set_page_config(page_title="CourtEdge", page_icon="🏀", layout="wide")


@st.cache_data(ttl=300)
def load_board():
    from src.model.predict import build_board
    return build_board()


@st.cache_data
def load_metrics():
    p = ARTIFACT_DIR / "metrics.json"
    return json.loads(p.read_text()) if p.exists() else None


def fmt_pct(x):
    return f"{x*100:.1f}%"


# ----------------------------------------------------------------------------- #
st.sidebar.title("🏀 CourtEdge")
st.sidebar.caption("NBA +EV betting analytics — *find value, don't buy picks*")
page = st.sidebar.radio("", ["Today's Board", "Model Performance", "How It Works"])
st.sidebar.markdown("---")
st.sidebar.caption(
    "Analytics only — we never accept wagers. 21+. "
    "If gambling is a problem, call 1-800-GAMBLER."
)

# ----------------------------------------------------------------------------- #
if page == "Today's Board":
    st.title("Today's Board")
    st.caption("Model win probability vs. the market. Positive **edge / EV** = a value bet.")

    if not (ARTIFACT_DIR / "xgb_model.json").exists():
        st.warning("No trained model found. Run the pipeline first (see *How It Works*).")
        st.stop()

    board = load_board()
    source = board["source"].iloc[0]
    if source == "sample":
        st.info(
            "⚠️ **Sample data** (no live NBA games / no Odds API key right now). "
            "Model probabilities and the edge math are real; book odds are simulated "
            "around the model with ~4.5% vig to demonstrate the product. The `result` "
            "column shows the actual historical outcome."
        )

    value = board[board["ev"] > 0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Games on board", len(board))
    c2.metric("+EV opportunities", len(value))
    c3.metric("Best edge", fmt_pct(board["edge"].max()))

    show = board.copy()
    show["P(home win)"] = show["p_home"].map(fmt_pct)
    show["edge"] = show["edge"].map(fmt_pct)
    show["ev/unit"] = show["ev"].map(lambda x: f"{x:+.2f}")
    show["Kelly stake"] = show["kelly_stake"].map(lambda x: fmt_pct(x) + " of bankroll")
    cols = ["matchup", "P(home win)", "pick", "book", "odds", "implied", "edge",
            "ev/unit", "Kelly stake"]
    if "result" in show:
        cols.append("result")
    st.dataframe(show[cols], use_container_width=True, hide_index=True)

    st.caption(
        f"Stake = {KELLY_FRACTION:g}× Kelly, capped at {fmt_pct(MAX_STAKE_FRAC)} of bankroll. "
        "Edge = model prob − implied prob at the best available price."
    )

# ----------------------------------------------------------------------------- #
elif page == "Model Performance":
    st.title("Model Performance")
    st.caption("Held-out **most-recent season** — strictly out-of-sample, no leakage.")

    m = load_metrics()
    if not m:
        st.warning("No metrics yet. Run `python -m src.model.train`.")
        st.stop()

    st.subheader("Out-of-sample metrics vs. an Elo baseline")
    md = pd.DataFrame(
        {k: m[k] for k in ["elo_baseline", "xgb_raw", "xgb_calibrated"]}
    ).T[["n", "accuracy", "log_loss", "brier", "auc"]]
    st.dataframe(md, use_container_width=True)

    st.markdown(
        "**Honest read:** the NBA market is highly efficient, so a calibrated model "
        "lands around **65–68% accuracy / AUC ≈ 0.73** and only modestly beats Elo. "
        "We do **not** claim guaranteed profit — the product value is surfacing the "
        "*occasional* mispriced line, line-shopping the best price, and correct "
        "(Kelly) bet sizing. The real long-term skill metric is **CLV**."
    )

    cal = ARTIFACT_DIR / "calibration.png"
    if cal.exists():
        st.subheader("Calibration (reliability) curve")
        st.image(str(cal), width=520)
        st.caption("Closer to the diagonal = better-calibrated probabilities, "
                   "which is what makes the edge comparison trustworthy.")

    st.subheader("Feature importance")
    fi = pd.Series(m["feature_importance"]).sort_values(ascending=True)
    st.bar_chart(fi)

# ----------------------------------------------------------------------------- #
else:
    st.title("How It Works")
    st.markdown(
        """
**Pipeline (ingestion → storage → processing → delivery):**

1. **Ingestion** — `nba_api` multi-season team game logs → Parquet raw zone.
2. **Storage** — Parquet (raw) + SQLite/Postgres warehouse (curated tables).
3. **Processing** — **PySpark** window functions build rolling pre-game form
   features (no leakage); Elo ratings computed sequentially; XGBoost trained with
   an honest time-based split and **isotonic calibration**.
4. **Delivery** — this dashboard: edge detection, line shopping, Kelly sizing.

**The quant layer:** model probability vs. market-implied probability →
`edge`, `EV`, and a fractional-**Kelly** stake. CLV (Closing Line Value) is the
north-star metric for long-term skill.

**Reproduce:**
```bash
python -m src.ingestion.fetch_games      # nba_api -> Parquet -> DB
python -m src.processing.features_spark  # Spark rolling features
python -m src.processing.elo             # Elo ratings
python -m src.model.train                # train + calibrate + evaluate
streamlit run app/dashboard.py           # this app
```
        """
    )
    if table_exists("games"):
        g = read_sql("SELECT COUNT(*) c, MIN(game_date) a, MAX(game_date) b FROM games")
        st.caption(f"Warehouse: {int(g.c[0])} games, {g.a[0]} → {g.b[0]}.")
