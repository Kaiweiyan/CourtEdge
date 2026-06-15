"""Elo power ratings (sequential by date). Pre-game Elo for home & away per game.

Elo is inherently sequential (each game updates ratings), so it's computed in
pandas rather than Spark. Output table `game_elo` is joined into training data.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.db import read_sql, write_df  # noqa: E402

K = 20.0          # update speed
HOME_ADV = 60.0   # Elo points added to home team for win expectation
BASE = 1500.0
REGRESS = 0.75    # season-to-season regression toward the mean


def expected(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def main():
    games = read_sql("SELECT * FROM games").sort_values("game_date").reset_index(drop=True)
    ratings: dict[int, float] = {}
    rows = []
    cur_season = None

    for g in games.itertuples(index=False):
        if g.season != cur_season:  # regress toward mean at season start
            cur_season = g.season
            for t in ratings:
                ratings[t] = BASE + REGRESS * (ratings[t] - BASE)

        rh = ratings.get(g.home_team_id, BASE)
        ra = ratings.get(g.away_team_id, BASE)
        exp_home = expected(rh + HOME_ADV, ra)

        rows.append({"game_id": g.game_id, "home_elo": rh, "away_elo": ra,
                     "elo_diff": (rh + HOME_ADV) - ra, "elo_exp_home": exp_home})

        result = g.home_win
        ratings[g.home_team_id] = rh + K * (result - exp_home)
        ratings[g.away_team_id] = ra + K * ((1 - result) - (1 - exp_home))

    out = pd.DataFrame(rows)
    write_df(out, "game_elo")
    print(f"Wrote game_elo ({len(out)} rows). "
          f"Elo range: {out.home_elo.min():.0f}-{out.home_elo.max():.0f}")


if __name__ == "__main__":
    main()
