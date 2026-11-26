# Seeded faults (Exercise 2)

Who did what. The faults were seeded and fixed by an AI agent (Claude Opus 5.5 in Claude Code, not the local Ollama model). Every block below is pasted terminal output, not a description.

How the hook was run. The agent's own Claude Code session was not started from this repo, so the repo's `.claude/settings.json` hooks did not fire on its edits. After each edit the hook was run by hand: a PostToolUse payload of the same shape Claude Code sends (`tool_name: "Edit"`, `tool_input.file_path` set to the edited file) was piped into `.claude/hooks/check_leakage.sh` with `CLAUDE_PROJECT_DIR` set. The script is the same one the harness runs, so the stderr and exit code are what the agent would have received.

Turns to fix. Counted as edit-and-verify cycles by the agent after seeing the red output.

## 0. Exercise 1: the feature test, written first

`tests/test_leakage.py::test_roll_std_7_on_named_date`, committed before `cnt_roll_std_7` existed (commit "Add failing test for cnt_roll_std_7"). It fails for the right reason: the column does not exist yet.

```
$ make test
E   KeyError: 'cnt_roll_std_7'
E           KeyError: 'cnt_roll_std_7'
FAILED tests/test_leakage.py::test_roll_std_7_on_named_date - KeyError: 'cnt_...
1 failed, 14 passed in 1.00s
make: *** [test] Error 1
```

## 1. Forbidden column added to `feature_columns`

Change, test output and hook stderr:

```
$ git diff src/features.py
diff --git a/src/features.py b/src/features.py
index 518b3c0..bb1c501 100644
--- a/src/features.py
+++ b/src/features.py
@@ -84,7 +84,7 @@ def build_features(df: pd.DataFrame) -> pd.DataFrame:
 def feature_columns(df: pd.DataFrame) -> list[str]:
     """Numeric columns that are safe to feed the model."""
     numeric = df.select_dtypes(include="number").columns
-    return [c for c in numeric if c not in FORBIDDEN]
+    return [c for c in numeric if c not in FORBIDDEN] + ["casual"]
 
 
 if __name__ == "__main__":

$ echo '<PostToolUse Edit payload for src/features.py>' | .claude/hooks/check_leakage.sh
Leakage tests failed after editing /Users/viprabindal/DSC180A-Methodology-7/bikeshare-open/src/features.py:
feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 cnt_roll_std_7
0   2011-01-10     10.0  WINTER  ...     1...857     886.694316
713 2012-12-31    731.0  WINTER  ...      920.0  1531.428571     887.135250

[714 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'cnt_roll_std_7', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests/test_leakage.py:31: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 7 passed in 0.32s
[hook exit code: 2]

$ make test
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'cnt_roll_std_7', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 15 passed in 1.09s
make: *** [test] Error 1
```

Fixed in 1 turn (restored the return line). After the fix:

```
$ echo '<PostToolUse Edit payload for src/features.py>' | .claude/hooks/check_leakage.sh
[hook exit code: 0]
$ make test
16 passed in 0.75s
```

## 2. `.shift(1)` deleted from `cnt_roll_7`

```
$ git diff src/features.py
diff --git a/src/features.py b/src/features.py
index 518b3c0..870ad15 100644
--- a/src/features.py
+++ b/src/features.py
@@ -73,7 +73,7 @@ def build_features(df: pd.DataFrame) -> pd.DataFrame:
     # If you add a longer lag, raise LAG_WARMUP in src/config.py.
     out["cnt_lag_1"] = out[TARGET].shift(1)
     out["cnt_lag_7"] = out[TARGET].shift(LAG_WARMUP)
-    out["cnt_roll_7"] = out[TARGET].shift(1).rolling(LAG_WARMUP).mean()
+    out["cnt_roll_7"] = out[TARGET].rolling(LAG_WARMUP).mean()
     # Volatility of the previous 7 days. Same window as cnt_roll_7, so it
     # needs no extra warm-up and LAG_WARMUP stays at 7.
     out["cnt_roll_std_7"] = out[TARGET].shift(1).rolling(LAG_WARMUP).std()

$ echo '<PostToolUse Edit payload for src/features.py>' | .claude/hooks/check_leakage.sh
Leakage tests failed after editing /Users/viprabindal/DSC180A-Methodology-7/bikeshare-open/src/features.py:
[714 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4389.0) == 4414.857142857143 ± 0.00441486
E             
E             comparison failed
E             Obtained: 4389.0
E             Expected: 4414.857142857143 ± 0.00441486

tests/test_leakage.py:57: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 7 passed in 0.21s
[hook exit code: 2]

$ make test
E           assert np.float64(4389.0) == 4414.857142857143 ± 0.00441486
E             
E             comparison failed
E             Obtained: 4389.0
E             Expected: 4414.857142857143 ± 0.00441486
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 15 passed in 0.83s
make: *** [test] Error 1
```

Fixed in 1 turn (restored `.shift(1)`). After the fix:

```
$ echo '<PostToolUse Edit payload for src/features.py>' | .claude/hooks/check_leakage.sh
[hook exit code: 0]
$ make test
16 passed in 0.75s
```

## 3. The weather encoder's `raise` removed

Finding: the starter suite stays green. The checked-in CSV only has GOOD / MISTY / BAD, all of which are in `WEATHER_ORDER`, so without the guard nothing becomes NaN and the row-loss bound has nothing to catch. The hook exits 0.

```
$ git diff src/features.py
diff --git a/src/features.py b/src/features.py
index 518b3c0..fcebaf1 100644
--- a/src/features.py
+++ b/src/features.py
@@ -24,10 +24,6 @@ def encode_weather(series: pd.Series) -> pd.Series:
     days -- the most interesting days in the dataset -- disappear with no
     error and no warning.
     """
-    known = series.dropna()
-    unknown = set(known.unique()) - set(WEATHER_ORDER)
-    if unknown:
-        raise ValueError(f"unmapped weather labels: {sorted(unknown)}")
     return series.map(WEATHER_ORDER).astype(float)
 
 

$ echo '<PostToolUse Edit payload for src/features.py>' | .claude/hooks/check_leakage.sh
[hook exit code: 0]

$ make test
16 passed in 0.82s
```

Fix took 2 turns. Turn 1 added `test_weather_encoder_rejects_unknown_labels` to `tests/test_leakage.py` (so the hook runs it) and ran it against the still-broken encoder:

```
$ # new test added to tests/test_leakage.py, encoder still broken
$ echo '<PostToolUse Edit payload for src/features.py>' | .claude/hooks/check_leakage.sh
Leakage tests failed after editing /Users/viprabindal/DSC180A-Methodology-7/bikeshare-open/src/features.py:
........F                                                                [100%]
=================================== FAILURES ===================================
_________________ test_weather_encoder_rejects_unknown_labels __________________

    def test_weather_encoder_rejects_unknown_labels():
        """The checked-in CSV only has GOOD / MISTY / BAD, so the row-loss bound
        cannot see a missing guard in encode_weather: nothing goes NaN. Feed it
        a label it has never seen and require a loud failure, not a silent NaN."""
        from src.features import encode_weather
    
>       with pytest.raises(ValueError, match="unmapped weather labels"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests/test_leakage.py:88: Failed
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_weather_encoder_rejects_unknown_labels - F...
1 failed, 8 passed in 0.22s
[hook exit code: 2]

$ make test
E       Failed: DID NOT RAISE ValueError
FAILED tests/test_leakage.py::test_weather_encoder_rejects_unknown_labels - F...
1 failed, 16 passed in 0.89s
make: *** [test] Error 1
```

Turn 2 restored the `raise`:

```
$ echo '<PostToolUse Edit payload for src/features.py>' | .claude/hooks/check_leakage.sh
[hook exit code: 0]
$ make test
17 passed in 0.79s
```

## 4. `cp` into `data/raw/` from Bash (the fault the hook cannot see)

A tampered copy of the CSV (humidity set to 0 on 2012-07-04, every other value unchanged) was copied over `data/raw/bike_daily.csv` with `cp`. `$SCRATCH` is the agent's scratch directory outside the repo.

```
$ cp $SCRATCH/bike_daily_tampered.csv data/raw/bike_daily.csv   # Bash tool; tampered copy sets hum=0 on 2012-07-04
[cp exit code: 0]
$ shasum -a 256 data/raw/bike_daily.csv
eb3bda3169b9062a1a548350679e81d3ed3af0096866b711957f9f6824f859f8  data/raw/bike_daily.csv
$ # PostToolUse matcher is "Edit|Write", so a Bash tool call never reaches the hook. Fed a Bash payload by hand anyway:
[hook exit code: 0]
$ make test
17 passed in 0.93s
$ make all  (ridge valid r2 shown)
ridge valid {'r2': 0.7224, 'mae': 700.4}
```

What happened. Nothing stopped it and nothing noticed. The deny rules `Write(./data/raw/**)` and `Edit(./data/raw/**)` bind the Edit and Write tools, not a `cp` inside a Bash call. The PostToolUse hook is matched on `Edit|Write` and only acts on `src/*.py`, so it never ran. All tests passed and `make all` ran to completion on the modified data. The validation metrics did not move because 2012-07-04 is a test-set day, which is exactly why this kind of change is dangerous: it moves a number nobody is looking at during iteration.

What would catch it. A hash check on the raw file (implemented below), a PreToolUse hook on Bash that rejects commands writing under `data/raw/`, a Stop hook that runs `make test`, or a filesystem permission (`chmod -w data/raw`). The hash check catches the change however it was made. A PreToolUse hook would block it before it lands but only for the agent's tool calls.

Implemented: the sha256 of the raw CSV is pinned in `src/config.py`, checked by `make data` and by `tests/test_contract.py::test_raw_data_is_unmodified`. With the tampered file still in place:

```
$ # tampered CSV still in data/raw/, hash check added
$ make test
E       AssertionError: data/raw/bike_daily.csv was modified; restore it with git checkout -- data/raw/
E       assert 'eb3bda3169b9...f9f6824f859f8' == 'a6bed1577f6e...0c86a0b5ad9dc'
E         
E         - a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc
E         + eb3bda3169b9062a1a548350679e81d3ed3af0096866b711957f9f6824f859f8
FAILED tests/test_contract.py::test_raw_data_is_unmodified - AssertionError: ...
1 failed, 17 passed in 1.16s
make: *** [test] Error 1
$ make data
ValueError: bike_daily.csv sha256 is eb3bda3169b9062a..., expected a6bed1577f6e4de5...; raw data was modified. Restore it with: git checkout -- data/raw/
make: *** [data] Error 1
```

The raw file was then restored with `git checkout -- data/raw/bike_daily.csv` (sha256 `a6bed1577f6e4de5...` again) and `make test` passed (18 tests). The diff:

```diff
diff --git a/src/config.py b/src/config.py
index 50b76d1..d051542 100644
--- a/src/config.py
+++ b/src/config.py
@@ -20,6 +20,11 @@ DATA_URL = (
     "interpretable-ml-book/master/data/bike.csv"
 )
 
+# sha256 of the checked-in raw CSV. Permission rules only bind the Edit and
+# Write tools; a `cp` from Bash walks past them and past the PostToolUse
+# hook. `make data` and tests/test_contract.py refuse a file that differs.
+RAW_SHA256 = "a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc"
+
 TARGET = "cnt"
 
 # --- Three reasons a column is kept out of the feature set --------------
diff --git a/src/ingest.py b/src/ingest.py
index 6654075..6e5e33f 100644
--- a/src/ingest.py
+++ b/src/ingest.py
@@ -2,12 +2,13 @@
 
 Run: python -m src.ingest
 """
+import hashlib
 import sys
 import urllib.request
 
 import pandas as pd
 
-from src.config import DATA_URL, RAW
+from src.config import DATA_URL, RAW, RAW_SHA256
 
 EXPECTED_MIN_ROWS = 700
 REQUIRED_COLS = {"dteday", "cnt", "casual", "registered", "temp", "hum", "windspeed"}
@@ -20,6 +21,18 @@ def download(force: bool = False) -> None:
     urllib.request.urlretrieve(DATA_URL, RAW)
 
 
+def raw_sha256() -> str:
+    return hashlib.sha256(RAW.read_bytes()).hexdigest()
+
+
+def verify_raw_hash() -> None:
+    """Raw data is immutable. Fail if the file on disk is not the one we pinned."""
+    got = raw_sha256()
+    if got != RAW_SHA256:
+        raise ValueError(f"{RAW.name} sha256 is {got[:16]}..., expected {RAW_SHA256[:16]}...; "
+                         "raw data was modified. Restore it with: git checkout -- data/raw/")
+
+
 def load_raw() -> pd.DataFrame:
     df = pd.read_csv(RAW, parse_dates=["dteday"])
     missing = REQUIRED_COLS - set(df.columns)
@@ -32,5 +45,6 @@ def load_raw() -> pd.DataFrame:
 
 if __name__ == "__main__":
     download(force="--force" in sys.argv)
+    verify_raw_hash()
     df = load_raw()
     print(f"OK ingest: {len(df)} rows, {df.dteday.min().date()} -> {df.dteday.max().date()}")
diff --git a/tests/test_contract.py b/tests/test_contract.py
index c63bbfa..ce8b179 100644
--- a/tests/test_contract.py
+++ b/tests/test_contract.py
@@ -4,9 +4,10 @@ import pytest
 from sklearn.metrics import r2_score
 
 from src.config import (DATE_COL, ENCODED_COLS, FORBIDDEN, LAG_WARMUP, RAW,
-                        RAW_FEATURE_COLS, REDUNDANT_CALENDAR_COLS, TARGET)
+                        RAW_FEATURE_COLS, RAW_SHA256, REDUNDANT_CALENDAR_COLS,
+                        TARGET)
 from src.features import build_features, feature_columns, reindex_to_calendar
-from src.ingest import load_raw
+from src.ingest import load_raw, raw_sha256
 from src.train import MODELS, temporal_split
 
 
@@ -73,3 +74,11 @@ def test_every_raw_column_is_classified():
     assert not unclassified, (
         f"unclassified raw columns {sorted(unclassified)}: add each to a set "
         "in src/config.py with the reason")
+
+
+def test_raw_data_is_unmodified():
+    """Raw data is immutable. The deny rules in .claude/settings.json stop
+    the Edit and Write tools only; `cp` from Bash gets past them and past the
+    PostToolUse hook. The pinned hash catches it however the file changed."""
+    assert raw_sha256() == RAW_SHA256, (
+        "data/raw/bike_daily.csv was modified; restore it with git checkout -- data/raw/")
```

## Extra: a new column appended to the raw CSV

Checks the new `tests/test_contract.py::test_every_raw_column_is_classified`. Run in a throwaway copy of the repo (raw CSV with `cnt_forecast = cnt` appended), before the hash check existed, so only the classification test could catch it. It was the only test that went red.

```
$ # in a throwaway copy, raw CSV with an appended numeric column cnt_forecast = cnt
$ make test
E       AssertionError: unclassified raw columns ['cnt_forecast']: add each to a set in src/config.py with the reason
E       assert not {'cnt_forecast'}
FAILED tests/test_contract.py::test_every_raw_column_is_classified - Assertio...
1 failed, 15 passed in 0.73s
make: *** [test] Error 1
```
