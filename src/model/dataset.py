"""Assemble the model-ready table by joining games + team_form + Elo."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.db import read_sql  # noqa: E402

FEATURES = [
    "diff_pts_for", "diff_pts_against", "diff_net", "diff_win_rate",
    "home_rest", "away_rest", "home_b2b", "away_b2b",
    "elo_diff", "elo_exp_home",
]
TARGET = "home_win"


def build_dataset() -> pd.DataFrame:
    games = read_sql("SELECT * FROM games")
    form = read_sql("SELECT * FROM team_form")
    elo = read_sql("SELECT * FROM game_elo")

    home = form.add_prefix("h_").rename(columns={"h_game_id": "game_id", "h_team_id": "home_team_id"})
    away = form.add_prefix("a_").rename(columns={"a_game_id": "game_id", "a_team_id": "away_team_id"})

    df = (
        games
        .merge(home, on=["game_id", "home_team_id"], how="inner")
        .merge(away, on=["game_id", "away_team_id"], how="inner")
        .merge(elo, on="game_id", how="inner")
    )

    df["diff_pts_for"] = df.h_roll_pts_for - df.a_roll_pts_for
    df["diff_pts_against"] = df.h_roll_pts_against - df.a_roll_pts_against
    df["diff_net"] = df.h_roll_net_rating - df.a_roll_net_rating
    df["diff_win_rate"] = df.h_roll_win_rate - df.a_roll_win_rate
    df["home_rest"] = df.h_rest_days
    df["away_rest"] = df.a_rest_days
    df["home_b2b"] = df.h_b2b
    df["away_b2b"] = df.a_b2b

    df["game_date"] = pd.to_datetime(df["game_date"])
    df = df.dropna(subset=FEATURES + [TARGET]).sort_values("game_date").reset_index(drop=True)
    return df
