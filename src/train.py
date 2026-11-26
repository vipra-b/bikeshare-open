"""Stage 3: temporal split, fit, evaluate, write metrics.

Two baselines and two models, on purpose.

  baseline_mean         predict the 2011 average for every day
  baseline_persistence  predict yesterday's count (cnt_lag_1)
  ridge                 standardised linear model on the audited features
  hgb                   gradient-boosted trees on the same features

The mean baseline shows what "the distribution moved" costs. Persistence
is the baseline that actually matters: ridge's features are dominated by
lagged demand, so if it cannot beat "yesterday again" it has learned
nothing worth reporting. The booster is there because it fails, and the
reason it fails is the headline result.

Run: python -m src.train

Exercise 4 (not part of `make all`): refit ridge and hgb on a transformed
target and print VALIDATION scores only. Test is reported only with
--touch-test, which is meant to be run once, at the end.
    python -m src.train --target-transform ratio
"""
import argparse
import json

import numpy as np

import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import METRICS, PROCESSED, TARGET, TRAIN_END, VALID_END
from src.features import feature_columns


class PersistenceBaseline(BaseEstimator, RegressorMixin):
    """Predict a single lagged column unchanged. Nothing is fit."""

    def __init__(self, column: str = "cnt_lag_1"):
        self.column = column

    def fit(self, X, y=None):
        if self.column not in X.columns:
            raise ValueError(f"persistence baseline needs column {self.column!r}")
        return self

    def predict(self, X):
        return X[self.column].to_numpy(dtype=float)


MODELS = {
    "baseline_mean": DummyRegressor(strategy="mean"),
    "baseline_persistence": PersistenceBaseline("cnt_lag_1"),
    "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "hgb": HistGradientBoostingRegressor(random_state=0, max_iter=300),
}


def temporal_split(df: pd.DataFrame):
    """Split by date, never at random. A random split on a time series
    puts tomorrow in train and today in test."""
    train = df[df.dteday <= TRAIN_END]
    valid = df[(df.dteday > TRAIN_END) & (df.dteday <= VALID_END)]
    test = df[df.dteday > VALID_END]
    return train, valid, test


# Exercise 4: target transforms. Each maps (y, X) -> z for fitting and
# (zhat, X) -> yhat for scoring. Every input is a lag column, so each is
# computable at prediction time.
TRANSFORMS = {
    # predict the ratio to the trailing 7-day mean: a level-free target
    "ratio": (lambda y, X: y / X["cnt_roll_7"], lambda z, X: z * X["cnt_roll_7"]),
    # predict the change from yesterday
    "diff": (lambda y, X: y - X["cnt_lag_1"], lambda z, X: z + X["cnt_lag_1"]),
    # log scale: compresses the range but does not remove the level
    "log": (lambda y, X: np.log1p(y), lambda z, X: np.expm1(z)),
}


def score_transformed(name: str, touch_test: bool = False) -> dict:
    fwd, inv = TRANSFORMS[name]
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)
    parts = [("valid", valid)] + ([("test", test)] if touch_test else [])
    out = {}
    for model_name, template in MODELS.items():
        model = clone(template)
        is_baseline = model_name.startswith("baseline_")
        model.fit(train[cols], train[TARGET] if is_baseline else fwd(train[TARGET], train[cols]))
        out[model_name] = {}
        for split, part in parts:
            pred = model.predict(part[cols])
            if not is_baseline:
                pred = inv(pred, part[cols])
            out[model_name][split] = {
                "r2": round(float(r2_score(part[TARGET], pred)), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], pred)), 1),
            }
    return out


def fit_and_score(exclude_features: tuple[str, ...] = ()) -> dict:
    df = pd.read_parquet(PROCESSED)
    cols = [c for c in feature_columns(df) if c not in exclude_features]
    train, valid, test = temporal_split(df)

    results = {
        "n_features": len(cols),
        "features": cols,
        "n_train": len(train),
        "n_valid": len(valid),
        "n_test": len(test),
    }
    for name, template in MODELS.items():
        model = clone(template)
        model.fit(train[cols], train[TARGET])
        results[name] = {
            split: {
                "r2": round(float(r2_score(part[TARGET], model.predict(part[cols]))), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], model.predict(part[cols]))), 1),
            }
            for split, part in [("valid", valid), ("test", test)]
        }
    return results


def comparison_metrics() -> dict:
    """Freeze the chosen feature and reproduce both rows of its comparison.

    Both versions use the same calendar rows, split, estimators and seeds.
    The before version omits only the added seven-day volatility feature.
    This is reporting a fixed comparison, not choosing features on test.
    """
    results = fit_and_score()
    results["before_feature"] = fit_and_score(("cnt_roll_std_7",))
    results["comparison"] = {
        "added_feature": "cnt_roll_std_7",
        "before_feature_source_commit": "f38a6d2",
        "after_feature_source_commit": "c94572b",
        "method": "Same retained rows and fixed models; before excludes only cnt_roll_std_7.",
    }
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-transform", choices=["none", *TRANSFORMS], default="none")
    ap.add_argument("--touch-test", action="store_true")
    args = ap.parse_args()
    if args.target_transform != "none":
        # Never writes reports/metrics.json: the committed file is untransformed.
        print(json.dumps({args.target_transform: score_transformed(
            args.target_transform, args.touch_test)}, indent=2))
        raise SystemExit
    res = comparison_metrics()
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    METRICS.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "features"}, indent=2))
