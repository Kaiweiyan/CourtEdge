"""Processing (Spark): rolling pre-game team-form features via window functions.

Reads the curated `games` table, explodes to team long-form, and uses Spark
window functions (partitioned by team, ordered by date) to compute rolling
averages over the *previous* N games — strictly pre-game, no leakage.

Single-node local[*] here; the same DataFrame code scales to a cluster, and the
documented scaling target is full play-by-play (~10M+ rows).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure Spark can find a JVM even if JAVA_HOME isn't exported in the shell.
if not os.environ.get("JAVA_HOME"):
    for _cand in ("/usr/lib/jvm/java-11-openjdk-amd64", "/usr/lib/jvm/default-java"):
        if Path(_cand, "bin", "java").exists():
            os.environ["JAVA_HOME"] = _cand
            break

import pandas as pd
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import ROLL_WINDOW  # noqa: E402
from src.db import read_sql, write_df  # noqa: E402


def to_long(games: pd.DataFrame) -> pd.DataFrame:
    """One row per team per game with pts_for / pts_against."""
    home = pd.DataFrame({
        "game_id": games.game_id, "game_date": games.game_date, "season": games.season,
        "team_id": games.home_team_id, "is_home": 1,
        "pts_for": games.home_pts, "pts_against": games.away_pts,
        "win": games.home_win,
    })
    away = pd.DataFrame({
        "game_id": games.game_id, "game_date": games.game_date, "season": games.season,
        "team_id": games.away_team_id, "is_home": 0,
        "pts_for": games.away_pts, "pts_against": games.home_pts,
        "win": 1 - games.home_win,
    })
    return pd.concat([home, away], ignore_index=True)


def main():
    games = read_sql("SELECT * FROM games")
    games["game_date"] = pd.to_datetime(games["game_date"])
    long = to_long(games)

    spark = (
        SparkSession.builder.appName("courtedge-features")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    sdf = spark.createDataFrame(long)

    # Previous N games for this team (exclude current row -> no leakage).
    w_prev = (
        Window.partitionBy("team_id").orderBy("game_date")
        .rowsBetween(-ROLL_WINDOW, -1)
    )
    w_order = Window.partitionBy("team_id").orderBy("game_date")

    feat = (
        sdf
        .withColumn("roll_pts_for", F.avg("pts_for").over(w_prev))
        .withColumn("roll_pts_against", F.avg("pts_against").over(w_prev))
        .withColumn("roll_win_rate", F.avg("win").over(w_prev))
        .withColumn("games_played", F.count("pts_for").over(w_prev))
        .withColumn("prev_date", F.lag("game_date").over(w_order))
        .withColumn("rest_days", F.datediff(F.col("game_date"), F.col("prev_date")))
    )
    feat = feat.withColumn(
        "rest_days", F.when(F.col("rest_days").isNull(), 3).otherwise(F.col("rest_days"))
    ).withColumn(
        "b2b", (F.col("rest_days") == 1).cast("int")
    ).withColumn(  # cap season-gap rest at 7 days (off-season isn't meaningful)
        "rest_days", F.least(F.col("rest_days"), F.lit(7))
    ).withColumn(
        "roll_net_rating", F.col("roll_pts_for") - F.col("roll_pts_against")
    )

    out = feat.select(
        "game_id", "team_id", "is_home", "games_played",
        "roll_pts_for", "roll_pts_against", "roll_net_rating", "roll_win_rate",
        "rest_days", "b2b",
    ).toPandas()
    spark.stop()

    write_df(out, "team_form")
    print(f"Wrote team_form ({len(out)} rows) via Spark window functions.")
    print(out.describe().round(2).to_string())


if __name__ == "__main__":
    main()
