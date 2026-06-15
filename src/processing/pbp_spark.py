"""Processing (Spark): aggregate raw play-by-play (~550k+ event rows) at scale.

This is the real big-data Spark job: it reads partitioned PBP Parquet and reduces
hundreds of thousands of event rows into per-game and per-team-game descriptors
using groupBy + window functions.

Outputs:
  pbp_game_features : per game (events, OT, lead changes, max margin, final score)
  pbp_team_game     : per game-team (FG made/att/%, threes) — richer model features

Run:  python -m src.processing.pbp_spark
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make sure Spark can find a JVM even if JAVA_HOME isn't exported.
if not os.environ.get("JAVA_HOME"):
    for _cand in ("/usr/lib/jvm/java-11-openjdk-amd64", "/usr/lib/jvm/default-java"):
        if Path(_cand, "bin", "java").exists():
            os.environ["JAVA_HOME"] = _cand
            break

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import RAW_DIR  # noqa: E402
from src.db import write_df  # noqa: E402

PBP_GLOB = str(RAW_DIR / "pbp" / "*.parquet")


def main():
    spark = (
        SparkSession.builder.appName("courtedge-pbp")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "16")
        .config("spark.driver.memory", "2g")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    df = spark.read.parquet(PBP_GLOB)
    total = df.count()
    n_games = df.select("gameId").distinct().count()
    print(f"Loaded PBP: {total:,} event rows across {n_games} games "
          f"(~{total // max(n_games,1)} events/game).")

    # Clean numeric score columns ('' -> null), then carry the running score.
    s = (
        df.withColumn("sh", F.when(F.col("scoreHome") == "", None)
                      .otherwise(F.col("scoreHome").cast("int")))
          .withColumn("sa", F.when(F.col("scoreAway") == "", None)
                      .otherwise(F.col("scoreAway").cast("int")))
          .withColumn("fg", F.col("isFieldGoal").cast("int"))
          .withColumn("made", (F.col("shotResult") == "Made").cast("int"))
          .withColumn("three", ((F.col("shotValue").cast("int") == 3) &
                                (F.col("shotResult") == "Made")).cast("int"))
    )

    w = Window.partitionBy("gameId").orderBy("actionNumber")
    w_run = w.rowsBetween(Window.unboundedPreceding, Window.currentRow)
    s = (
        s.withColumn("run_h", F.last("sh", ignorenulls=True).over(w_run))
         .withColumn("run_a", F.last("sa", ignorenulls=True).over(w_run))
         .fillna(0, subset=["run_h", "run_a"])
         .withColumn("margin", F.col("run_h") - F.col("run_a"))
    )
    # Lead change = sign of margin flips (ignoring ties) vs. previous non-tie row.
    s = s.withColumn("sign", F.signum("margin"))
    nz = s.filter(F.col("sign") != 0)
    nz = nz.withColumn("prev_sign", F.lag("sign").over(w))
    lead_changes = (
        nz.withColumn("flip", ((F.col("prev_sign").isNotNull()) &
                               (F.col("sign") != F.col("prev_sign"))).cast("int"))
          .groupBy("gameId").agg(F.sum("flip").alias("lead_changes"))
    )

    game_feats = (
        s.groupBy("gameId").agg(
            F.count("*").alias("total_events"),
            F.max("period").alias("num_periods"),
            F.max("run_h").alias("home_final"),
            F.max("run_a").alias("away_final"),
            F.max(F.abs(F.col("margin"))).alias("max_abs_margin"),
            F.sum("made").alias("total_fg_made"),
            F.sum("three").alias("total_three_made"),
        )
        .withColumn("overtime", (F.col("num_periods") > 4).cast("int"))
        .join(lead_changes, "gameId", "left")
        .fillna(0, subset=["lead_changes"])
    )

    team_game = (
        s.filter((F.col("teamTricode").isNotNull()) & (F.col("teamTricode") != ""))
         .groupBy("gameId", "teamTricode").agg(
            F.sum("fg").alias("fg_att"),
            F.sum("made").alias("fg_made"),
            F.sum("three").alias("threes_made"),
        )
         .withColumn("fg_pct", F.round(F.col("fg_made") / F.col("fg_att"), 3))
    )

    gf = game_feats.toPandas()
    tg = team_game.toPandas()
    spark.stop()

    write_df(gf.rename(columns={"gameId": "game_id"}), "pbp_game_features")
    write_df(tg.rename(columns={"gameId": "game_id"}), "pbp_team_game")
    print(f"Wrote pbp_game_features ({len(gf)} games), pbp_team_game ({len(tg)} rows).")
    print(gf[["total_events", "num_periods", "lead_changes",
              "max_abs_margin", "total_three_made"]].describe().round(1).to_string())


if __name__ == "__main__":
    main()
