"""Train + calibrate the home-win model with an honest time-based split.

Train (oldest) -> validate (calibrate) -> test (most recent). Reports log loss,
Brier, accuracy, AUC vs. an Elo-only baseline, saves a calibration plot, the
model artifacts, and the test predictions for the dashboard.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import ARTIFACT_DIR  # noqa: E402
from src.db import write_df  # noqa: E402
from src.model.dataset import FEATURES, TARGET, build_dataset  # noqa: E402


def time_split(df, train_frac=0.70, valid_frac=0.15):
    n = len(df)
    i_tr, i_va = int(n * train_frac), int(n * (train_frac + valid_frac))
    return df.iloc[:i_tr], df.iloc[i_tr:i_va], df.iloc[i_va:]


def metrics(y, p) -> dict:
    return {
        "n": int(len(y)),
        "log_loss": round(float(log_loss(y, p)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "accuracy": round(float(accuracy_score(y, (p > 0.5).astype(int))), 4),
        "auc": round(float(roc_auc_score(y, p)), 4),
    }


def main():
    df = build_dataset()
    train, valid, test = time_split(df)
    print(f"Rows: total={len(df)} train={len(train)} valid={len(valid)} test={len(test)}")
    print(f"Test season span: {test.game_date.min().date()} -> {test.game_date.max().date()}")

    Xtr, ytr = train[FEATURES], train[TARGET]
    Xva, yva = valid[FEATURES], valid[TARGET]
    Xte, yte = test[FEATURES], test[TARGET].to_numpy()

    model = XGBClassifier(
        n_estimators=300, max_depth=3, learning_rate=0.04,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
        eval_metric="logloss", early_stopping_rounds=30, n_jobs=4,
    )
    model.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)

    # Calibrate raw model probabilities on the validation slice (isotonic).
    raw_va = model.predict_proba(Xva)[:, 1]
    iso = IsotonicRegression(out_of_bounds="clip").fit(raw_va, yva)

    raw_te = model.predict_proba(Xte)[:, 1]
    cal_te = iso.transform(raw_te)
    elo_te = test["elo_exp_home"].to_numpy()  # baseline: Elo's own probability

    results = {
        "elo_baseline": metrics(yte, elo_te),
        "xgb_raw": metrics(yte, raw_te),
        "xgb_calibrated": metrics(yte, cal_te),
        "features": FEATURES,
        "feature_importance": {
            f: round(float(v), 4)
            for f, v in sorted(zip(FEATURES, model.feature_importances_),
                               key=lambda x: -x[1])
        },
    }
    (ARTIFACT_DIR / "metrics.json").write_text(json.dumps(results, indent=2))
    print(json.dumps({k: results[k] for k in ("elo_baseline", "xgb_raw", "xgb_calibrated")}, indent=2))

    # Calibration (reliability) plot.
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.plot([0, 1], [0, 1], "k--", label="perfect")
    for name, p in [("Elo baseline", elo_te), ("XGB raw", raw_te), ("XGB calibrated", cal_te)]:
        frac, mean = calibration_curve(yte, p, n_bins=10, strategy="quantile")
        ax.plot(mean, frac, marker="o", label=name)
    ax.set_xlabel("Predicted P(home win)")
    ax.set_ylabel("Observed frequency")
    ax.set_title("Calibration on held-out test season")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ARTIFACT_DIR / "calibration.png", dpi=120)
    print(f"Saved calibration plot -> {ARTIFACT_DIR / 'calibration.png'}")

    # Persist artifacts + test predictions for the dashboard.
    model.save_model(ARTIFACT_DIR / "xgb_model.json")
    with open(ARTIFACT_DIR / "isotonic.pkl", "wb") as f:
        pickle.dump(iso, f)

    preds = test[["game_id", "game_date", "home_team", "away_team", TARGET]].copy()
    preds["model_prob"] = cal_te
    preds["elo_prob"] = elo_te
    preds["game_date"] = preds["game_date"].astype(str)
    write_df(preds, "predictions_test")
    print(f"Wrote predictions_test ({len(preds)} rows).")


if __name__ == "__main__":
    main()
