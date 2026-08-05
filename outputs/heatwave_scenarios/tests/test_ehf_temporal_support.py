"""
Plan Sec.1: for a synthetic series with positive trailing EHF values, verify
the assessment/support-start/support-end date fields, and that the two event
tables (positive-period vs. thermal-support) produce DIFFERENT, individually
correct results on a constructed case designed to make them differ: two
assessment dates 2 days apart with a NEGATIVE day between them. This breaks
the positive_periods run (not consecutive) but the two 3-day support windows
still touch at the middle day, so thermal_support_events must merge them into
one event.
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hs02_classify as hs02

FAILS = []


def check_true(label, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", label))
    if not cond:
        FAILS.append(label)


def check_eq(label, got, want):
    print("   [%s] %-60s got=%s want=%s" % ("PASS" if got == want else "FAIL", label, got, want))
    if got != want:
        FAILS.append(label)


print("=" * 78)
print("test_ehf_temporal_support")
print("=" * 78)

# 20 days, county "12345". Day index 9 (date +9) and day index 11 (date +11) are
# positive EHF (ehf_c2_fixed>0); day index 10 (between them) is NEGATIVE. Every
# other day is negative too. Both positive days are otherwise isolated.
n = 20
dates = pd.date_range("2020-07-01", periods=n)
ehf = np.full(n, -1.0)
ehf[9] = 2.0
ehf[11] = 3.0
df = pd.DataFrame({"county_fips": "12345", "county_name": "Synthetic", "date": dates,
                   "year": dates.year, "ehf_c2_fixed": ehf})

daily, hw, positive_periods, support_df = hs02.build_ehf_events(df, "fixed", "48", "TEST_EHF")

check_eq("exactly 2 positive assessment dates flagged", len(hw), 2)
check_eq("positive_periods: 2 SEPARATE 1-day periods (not consecutive, day 10 is negative)",
        len(positive_periods), 2)
if len(positive_periods):
    durs = sorted(positive_periods["event_duration_days"].tolist())
    check_eq("both positive-periods have duration 1", durs, [1, 1])

check_eq("thermal_support_events: exactly 1 MERGED event (supports touch at the middle day)",
        len(support_df), 1)
if len(support_df):
    row = support_df.iloc[0]
    expected_start = dates[9] - pd.Timedelta(days=2)   # support(day9) = [day9-2, day9]
    expected_end = dates[11]                            # support(day11) = [day11-2, day11] = [day9, day11]
    check_true("merged support event starts at day9-2 (%s)" % expected_start.date(),
              row["ehf_support_start_date"] == expected_start)
    check_true("merged support event ends at day11 (%s)" % expected_end.date(),
              row["ehf_support_end_date"] == expected_end)
    check_eq("merged support event duration (days, inclusive)",
            int(row["support_duration_days"]), int((expected_end - expected_start).days) + 1)

# ---- the two event tables must disagree in exactly this case (that's the point) ----
check_true("positive_periods count (2) != thermal_support_events count (1) -- the two "
          "constructions genuinely differ on this constructed case",
          len(positive_periods) != len(support_df))

# ---- event_definition_type is present and distinct on both tables ----
if len(positive_periods):
    check_true("positive_periods carries event_definition_type=positive_ehf_assessment_period",
              (positive_periods["event_definition_type"] == "positive_ehf_assessment_period").all())
if len(support_df):
    check_true("thermal_support_events carries event_definition_type=merged_thermal_support_interval",
              (support_df["event_definition_type"] == "merged_thermal_support_interval").all())

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- the two EHF event constructions are distinct and individually correct")
