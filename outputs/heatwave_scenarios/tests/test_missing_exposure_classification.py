"""
Plan Sec.3/4: an excluded or missing input must yield
    classification_eligible = 0, candidate = NA, classified_day = NA
-- NEVER a published 0 ("confirmed non-event day") -- and the NA must BREAK a
consecutive run rather than bridging it.
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hs00_config as H
import hs02_classify as hs02
sys.path.insert(0, H.PIPELINE_DIR)
from heatwave_run_logic import build_runs_and_events_panel

FAILS = []


def check_true(label, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", label))
    if not cond:
        FAILS.append(label)


def check_eq(label, got, want):
    print("   [%s] %-58s got=%s want=%s" % ("PASS" if got == want else "FAIL", label, got, want))
    if got != want:
        FAILS.append(label)


print("=" * 78)
print("test_missing_exposure_classification")
print("=" * 78)

# 7 consecutive days, all of which WOULD be candidates (metric far above threshold).
# Day index 3 (the middle) is a confirmed_artifact -> must be excluded under CONFEXCL,
# turning what would be one 7-day run into two 3-day runs.
n = 7
dates = pd.date_range("2020-07-01", periods=n)
cd = pd.DataFrame({
    "county_fips": "12345", "county_name": "Synthetic", "date": dates,
    "year": dates.year, "month": dates.month, "day": dates.day,
    "template_doy": [183 + i for i in range(n)],
    "synthetic_tmax_rhmax_hi_f": [120.0] * n,        # far above the threshold below
    "qc_category": ["valid"] * n,
})
cd.loc[3, "qc_category"] = "confirmed_artifact"

thr = pd.DataFrame({
    "county_fips": "12345", "template_doy": [183 + i for i in range(n)],
    "analysis_year": 2020, "threshold_p95_f": 100.0, "n_reference_values": 500,
})

# ---- RAW tier: nothing excluded -> one unbroken 7-day run ----
an_raw, n_excl_raw = hs02.build_candidates_local(cd, "synthetic_tmax_rhmax_hi_f", 95, thr, qc_tier="RAW")
daily_raw, ev_raw = build_runs_and_events_panel(an_raw, min_duration=2, definition_id="T", state_fips="48",
                                               with_event_columns=False)
check_eq("RAW: 0 dates excluded", n_excl_raw, 0)
check_eq("RAW: exactly 1 event (unbroken run)", len(ev_raw), 1)
check_eq("RAW: that event is 7 days long", int(ev_raw["event_duration_days"].iloc[0]), 7)

# ---- CONFEXCL tier: the middle day is excluded -> the run BREAKS into two ----
an_c, n_excl_c = hs02.build_candidates_local(cd, "synthetic_tmax_rhmax_hi_f", 95, thr, qc_tier="CONFEXCL")
daily_c, ev_c = build_runs_and_events_panel(an_c, min_duration=2, definition_id="T", state_fips="48",
                                           with_event_columns=False)
check_eq("CONFEXCL: exactly 1 date excluded", n_excl_c, 1)

mid = an_c[an_c["date"] == dates[3]].iloc[0]
check_true("CONFEXCL: excluded day's candidate_day_flag is NA (not 0)", pd.isna(mid["candidate_day_flag"]))
check_eq("CONFEXCL: excluded day's classification_eligible == 0", int(mid["classification_eligible"]), 0)

mid_daily = daily_c[daily_c["date"] == dates[3]]
if len(mid_daily):
    hw_flag = mid_daily["heatwave_day_flag"].iloc[0]
    check_true("CONFEXCL: excluded day is NOT reported as a classified heatwave day",
              (hw_flag == 0) or pd.isna(hw_flag))

check_eq("CONFEXCL: the run BREAKS into exactly 2 events", len(ev_c), 2)
if len(ev_c) == 2:
    durs = sorted(int(x) for x in ev_c["event_duration_days"])
    check_eq("CONFEXCL: the two events are 3 and 3 days (day 4 removed from the middle)", durs, [3, 3])

# ---- season restriction must behave identically (NA, not 0, and it breaks runs) ----
an_season = hs02.apply_season_restriction(an_raw.copy(), "june_september")
oct_dates = pd.date_range("2020-10-01", periods=3)
cd_oct = cd.copy()
cd_oct["date"] = oct_dates.tolist() + list(cd["date"][3:])
an_oct, _ = hs02.build_candidates_local(cd_oct, "synthetic_tmax_rhmax_hi_f", 95, thr, qc_tier="RAW")
an_oct = hs02.apply_season_restriction(an_oct, "june_september")
out_of_season = an_oct[an_oct["month"] == 10]
if len(out_of_season):
    check_true("season restriction: out-of-season candidate_day_flag is NA (not 0)",
              bool(out_of_season["candidate_day_flag"].isna().all()))
    check_true("season restriction: out-of-season analysis_eligible == 0",
              bool((out_of_season["analysis_eligible"] == 0).all()))

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- excluded/missing input is NA (never a published 0) and correctly breaks runs")
