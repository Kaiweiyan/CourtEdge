"""Build the "Today's Board": model prob vs. market, edge, EV, Kelly stake.

Live path: The Odds API upcoming games -> score with the trained model -> best
price across books -> edge/EV/Kelly. Offseason/no-key fallback: a labelled
sample board built from real held-out predictions so the UI always renders.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from nba_api.stats.static import teams as nba_teams
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import ARTIFACT_DIR, KELLY_FRACTION, MAX_STAKE_FRAC  # noqa: E402
from src.db import read_sql  # noqa: E402
from src.model import quant  # noqa: E402
from src.model.dataset import FEATURES  # noqa: E402
from src.processing.elo import BASE, HOME_ADV, expected  # noqa: E402

_ABBR_TO_NAME = {t["abbreviation"]: t["full_name"] for t in nba_teams.get_teams()}
_NAME_TO_ABBR = {v: k for k, v in _ABBR_TO_NAME.items()}


def _load_model():
    model = XGBClassifier()
    model.load_model(ARTIFACT_DIR / "xgb_model.json")
    with open(ARTIFACT_DIR / "isotonic.pkl", "rb") as f:
        iso = pickle.load(f)
    return model, iso


def build_team_latest() -> dict:
    """Latest pre-game rolling form + Elo per team abbreviation."""
    tg = read_sql("SELECT game_id, team_id, team, game_date FROM team_games")
    form = read_sql("SELECT * FROM team_form")
    f = tg.merge(form, on=["game_id", "team_id"], how="inner")
    f["game_date"] = pd.to_datetime(f["game_date"])
    latest = f.sort_values("game_date").groupby("team").tail(1).set_index("team")

    # Latest Elo per team (from pre-game Elo stored per game).
    games = read_sql("SELECT * FROM games")
    elo = read_sql("SELECT * FROM game_elo")
    g = games.merge(elo, on="game_id")
    g["game_date"] = pd.to_datetime(g["game_date"])
    long = pd.concat([
        g[["home_team", "game_date", "home_elo"]].rename(
            columns={"home_team": "team", "home_elo": "elo"}),
        g[["away_team", "game_date", "away_elo"]].rename(
            columns={"away_team": "team", "away_elo": "elo"}),
    ])
    elo_latest = long.sort_values("game_date").groupby("team").tail(1).set_index("team")["elo"]

    out = {}
    for team in latest.index:
        out[team] = {
            "roll_pts_for": latest.loc[team, "roll_pts_for"],
            "roll_pts_against": latest.loc[team, "roll_pts_against"],
            "roll_net_rating": latest.loc[team, "roll_net_rating"],
            "roll_win_rate": latest.loc[team, "roll_win_rate"],
            "elo": float(elo_latest.get(team, BASE)),
        }
    return out


def score_matchup(home, away, team_latest, model, iso,
                  home_rest=2, away_rest=2) -> float:
    """Calibrated model P(home win) for an abbr-vs-abbr matchup."""
    h, a = team_latest[home], team_latest[away]
    row = {
        "diff_pts_for": h["roll_pts_for"] - a["roll_pts_for"],
        "diff_pts_against": h["roll_pts_against"] - a["roll_pts_against"],
        "diff_net": h["roll_net_rating"] - a["roll_net_rating"],
        "diff_win_rate": h["roll_win_rate"] - a["roll_win_rate"],
        "home_rest": home_rest, "away_rest": away_rest,
        "home_b2b": int(home_rest == 1), "away_b2b": int(away_rest == 1),
        "elo_diff": (h["elo"] + HOME_ADV) - a["elo"],
        "elo_exp_home": expected(h["elo"] + HOME_ADV, a["elo"]),
    }
    X = pd.DataFrame([row])[FEATURES]
    raw = model.predict_proba(X)[:, 1][0]
    return float(iso.transform([raw])[0])


def _best_side(p_home, books):
    """Pick the side/price with the best EV across books."""
    rows = []
    for b in books:
        for side, p, odds in [("HOME", p_home, b["home_odds"]),
                              ("AWAY", 1 - p_home, b["away_odds"])]:
            rows.append((quant.expected_value(p, odds), side, b["book"], odds, p))
    rows.sort(reverse=True)
    ev, side, book, odds, p = rows[0]
    return {
        "pick": side, "book": book, "odds": odds, "p_model": round(p, 3),
        "implied": round(quant.american_to_implied(odds), 3),
        "edge": round(quant.edge(p, odds), 3),
        "ev": round(ev, 3),
        "kelly_stake": round(quant.recommended_stake(
            p, odds, KELLY_FRACTION, MAX_STAKE_FRAC), 4),
    }


def build_board() -> pd.DataFrame:
    from src.odds.odds_api import get_upcoming_odds

    model, iso = _load_model()
    team_latest = build_team_latest()
    games = get_upcoming_odds()

    rows = []
    if games:
        for g in games:
            home = _NAME_TO_ABBR.get(g["home"]); away = _NAME_TO_ABBR.get(g["away"])
            if home not in team_latest or away not in team_latest:
                continue
            p_home = score_matchup(home, away, team_latest, model, iso)
            best = _best_side(p_home, g["books"])
            rows.append({"matchup": f"{away} @ {home}", "p_home": round(p_home, 3),
                         "source": "live", **best})
        if rows:
            return pd.DataFrame(rows).sort_values("ev", ascending=False)

    # Fallback: sample board from real held-out predictions + plausible book odds.
    return _sample_board()


def _sample_board(n: int = 8) -> pd.DataFrame:
    preds = read_sql("SELECT * FROM predictions_test")
    sample = preds.sample(min(n, len(preds)), random_state=7).reset_index(drop=True)
    rng = np.random.default_rng(7)
    rows = []
    for r in sample.itertuples(index=False):
        p = float(r.model_prob)
        # Build a market line that disagrees with the model by a small noise,
        # add ~4.5% vig, so some games show an edge (demonstrates the product).
        mkt_p = float(np.clip(p + rng.normal(0, 0.03), 0.05, 0.95))
        home_odds = _fair_american(mkt_p, vig=0.045)
        away_odds = _fair_american(1 - mkt_p, vig=0.045)
        books = [{"book": "SampleBook", "home_odds": home_odds, "away_odds": away_odds}]
        best = _best_side(p, books)
        rows.append({"matchup": f"{r.away_team} @ {r.home_team}",
                     "p_home": round(p, 3), "source": "sample",
                     "result": "HOME win" if r.home_win == 1 else "AWAY win", **best})
    return pd.DataFrame(rows).sort_values("ev", ascending=False)


def _fair_american(p: float, vig: float = 0.0) -> int:
    """Probability -> American odds, optionally shading in a vig."""
    p_v = min(0.98, p * (1 + vig))
    dec = 1.0 / p_v
    if dec >= 2.0:
        return int(round((dec - 1) * 100))
    return int(round(-100 / (dec - 1)))


if __name__ == "__main__":
    board = build_board()
    print(f"Board ({board['source'].iloc[0]} data), {len(board)} games:")
    print(board.to_string(index=False))
