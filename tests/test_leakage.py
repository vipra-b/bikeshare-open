"""The tests that make the agent honest.

test_no_forbidden_features is the single most valuable test in this repo:
casual + registered == cnt exactly, so any model handed those columns
scores R^2 = 1.0 and looks brilliant while having learned nothing.
"""
import pandas as pd
import pytest
import numpy as np
from itertools import combinations

from src.config import FORBIDDEN, LEAKAGE_COLS, TARGET
from src.features import build_features, feature_columns
from src.ingest import load_raw


@pytest.fixture(scope="module")
def feats():
    return build_features(load_raw())


def test_leakage_identity_holds(feats):
    """Documents *why* casual and registered are forbidden."""
    assert (feats.casual + feats.registered == feats[TARGET]).all()


def test_no_forbidden_features(feats):
    """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
    construction, so this cannot discover a *new* leaky column. What it
    catches is someone editing feature_columns() or FORBIDDEN -- which is
    exactly the fault the Step 7 hook demonstrates."""
    cols = set(feature_columns(feats))
    assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"


def test_no_feature_subset_restates_target(feats):
    """Renaming a leaked count must not defeat the forbidden-name gate.

    Check fitted identities with an intercept, independently of column
    names, using all retained days. Single-column aliases or rescalings
    of cnt, casual, or registered, and combinations such as renamed
    casual + registered, must go red. A component alone is also leakage.
    This does not establish the availability of arbitrary nonlinear inputs.
    """
    protected = sorted(LEAKAGE_COLS)
    y = feats[protected].to_numpy(dtype=float)
    for size in (1, 2, 3):
        for subset in combinations(feature_columns(feats), size):
            X = np.column_stack([feats[list(subset)].to_numpy(dtype=float),
                                 np.ones(len(feats))])
            coef, *_ = np.linalg.lstsq(X, y, rcond=None)
            residuals = np.abs(X @ coef - y).max(axis=0)
            identities = {name: float(residual) for name, residual
                          in zip(protected, residuals) if residual < 1e-6}
            assert not identities, (
                f"feature subset {subset} restates target or components; "
                f"max absolute residuals {identities}")


def test_lags_are_true_calendar_lags(feats):
    """cnt_lag_1 for date d must equal cnt on d-1, in calendar days."""
    by_date = feats.set_index("dteday")[TARGET]
    checked = 0
    for date, lag in feats.set_index("dteday").cnt_lag_1.items():
        prev = date - pd.Timedelta(days=1)
        if prev in by_date.index:
            assert lag == pytest.approx(by_date[prev]), f"bad lag at {date.date()}"
            checked += 1
    assert checked > 600, "too few rows actually verified"


def test_lag_is_not_the_target(feats):
    assert not (feats.cnt_lag_1 == feats[TARGET]).all()


def test_rolling_mean_excludes_today(feats):
    """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
    by_date = feats.set_index("dteday")[TARGET]
    date = feats.dteday.iloc[200]
    window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
    if all(d in by_date.index for d in window):
        expected = sum(by_date[d] for d in window) / 7
        assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)


def test_no_missing_values(feats):
    assert feats[feature_columns(feats)].isna().sum().sum() == 0


def test_dates_are_sorted_and_unique(feats):
    assert feats.dteday.is_monotonic_increasing
    assert feats.dteday.is_unique


def test_roll_std_7_on_named_date(feats):
    """cnt_roll_std_7 on 2011-06-15 must be the sample std (ddof=1) of cnt on
    2011-06-08 .. 2011-06-14, the seven calendar days strictly before it.
    The counts are typed in by hand from data/raw/bike_daily.csv so the test
    does not trust the same pandas call the feature uses."""
    import statistics

    prior_week = [4401, 3915, 4586, 4966, 4460, 5020, 4891]  # 06-08 .. 06-14
    expected = statistics.stdev(prior_week)                  # 392.3098
    value = feats.set_index("dteday").loc[pd.Timestamp("2011-06-15"), "cnt_roll_std_7"]
    assert value == pytest.approx(expected)


def test_weather_encoder_rejects_unknown_labels():
    """The checked-in CSV only has GOOD / MISTY / BAD, so the row-loss bound
    cannot see a missing guard in encode_weather: nothing goes NaN. Feed it
    a label it has never seen and require a loud failure, not a silent NaN."""
    from src.features import encode_weather

    with pytest.raises(ValueError, match="unmapped weather labels"):
        encode_weather(pd.Series(["GOOD", "SNOW", "BAD"]))
