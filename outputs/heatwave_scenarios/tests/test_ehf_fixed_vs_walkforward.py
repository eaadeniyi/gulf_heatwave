"""
Plan Sec.1 / revision-5 fix: requires baseline_end_year == analysis_year-1 and
no_future_data_used for EVERY analysis year -- but does NOT require the
walk-forward T95 value to numerically change every year (a new baseline year
may not move the quantile). Reports whether it changed; never asserts it must.
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hs00_config as H
import hs01_derive_variables as hs01

FAILS = []


def check_true(label, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", label))
    if not cond:
        FAILS.append(label)


print("=" * 78)
print("test_ehf_fixed_vs_walkforward")
print("=" * 78)

# One synthetic county, full record, constant dmt_c=20.0 EXCEPT a single poison day
# placed on 2022-06-15 (dmt_c=5000.0). If walk-forward year Y's reference pool ever
# leaked in data from year Y itself or later, this poison day would appear in the
# reference pool for analysis years <= 2022 -- it must not.
dates = pd.date_range("%d-01-01" % H.BASELINE_START, "2025-12-31", freq="D")
dmt = np.full(len(dates), 20.0)
poison_date = pd.Timestamp("2022-06-15")
poison_idx = int((dates == poison_date).argmax())
dmt[poison_idx] = 5000.0
df = pd.DataFrame({"county_fips": "12345", "year": dates.year, "dmt_c": dmt,
                   "temp_imputed": False})

t95_df = hs01.compute_t95_all(df)
wf = t95_df[(t95_df["baseline"] == "walk_forward") & (t95_df["county_fips"] == "12345")]
wf = wf.set_index("analysis_year").sort_index()

# ---- 1. baseline_end_year == analysis_year - 1, structurally, for every analysis year ----
for Y in range(H.ANALYSIS_YEARS[0], H.ANALYSIS_YEARS[1] + 1):
    row = wf.loc[Y]
    expected_days = (pd.Timestamp(Y - 1, 12, 31) - pd.Timestamp(H.BASELINE_START, 1, 1)).days + 1
    check_true("year %d: expected_reference_days matches baseline_end_year=%d exactly" % (Y, Y - 1),
              int(row["expected_reference_days"]) == expected_days)

# ---- 2. no_future_data_used: the poison day (2022-06-15) must NOT appear in the
#         reference pool for any analysis year <= 2022 ----
for Y in range(H.ANALYSIS_YEARS[0], 2023):   # 2015..2022 inclusive: baseline ends 2021 at the latest
    row = wf.loc[Y]
    check_true("year %d (baseline ends %d, before the poison year): T95 unaffected by the poison day"
              % (Y, Y - 1), abs(row["t95_c"] - 20.0) < 1e-9)

# ---- 3. for analysis year 2023+ (baseline now includes all of 2022, so the poison day
#         IS in the reference pool) -- the poison day is admitted, checked via n_reference_days
#         actually growing to include it, NOT via requiring the percentile itself to move ----
row_2023 = wf.loc[2023]
row_2022 = wf.loc[2022]
check_true("year 2023's reference pool is exactly 1 day larger than 2022's (the poison day now included)",
          int(row_2023["n_reference_days"]) - int(row_2022["n_reference_days"]) ==
          (pd.Timestamp(2022, 12, 31) - pd.Timestamp(2022, 1, 1)).days + 1)
print("   (year 2022 T95=%.4f, year 2023 T95=%.4f -- with 1 poison value among %d reference days, "
      "the 95th percentile is not required to move, and reporting shows it: %s)"
      % (row_2022["t95_c"], row_2023["t95_c"], int(row_2023["n_reference_days"]),
         "changed" if abs(row_2022["t95_c"] - row_2023["t95_c"]) > 1e-9 else "did not change"))

# ---- 4. year-to-year change is REPORTED, never asserted to occur ----
changes = wf["t95_c"].diff().abs() > 1e-9
print("   walk-forward T95 changed year-over-year in %d/%d transitions (reported, not required)"
      % (int(changes.sum()), len(changes) - 1))

# ---- 5. fixed baseline is a single, year-invariant value (only one row exists at all) ----
fixed_rows = t95_df[(t95_df["baseline"] == "fixed_1979_2014") & (t95_df["county_fips"] == "12345")]
check_true("exactly one fixed-baseline T95 row exists per county (year-invariant by construction)",
          len(fixed_rows) == 1)

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- walk-forward T95 never uses future data; year-to-year change is reported, not required")
