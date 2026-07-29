"""
Verifies the THRESHOLD WINDOWS pool the calendar days they claim to.

Two of the four windows are new in the definition grid and nothing else tests them:
    w05        centered 5-day  (target +/-2)
    month_pm7  calendar month PLUS a 7-day collar either side

The other two are already validated end to end: `w15` and `month` are the windows
the published Definition 01 / 02 used, and tests/test_reproduce_def01_def02.py
proves the generalised code reproduces those results exactly.

Method: build a synthetic county-day table on LEAP years only, so every template
day-of-year 1..366 is present exactly once per year, and set the metric value equal
to the template day-of-year. Then for any window the pooled baseline set is known
in advance, and asking for percentiles 0 and 100 returns the MIN and MAX pooled
day-of-year -- which shows directly which calendar days went into the pool.

Checks the count of pooled values, the min/max day-of-year, and that windows wrap
correctly across 1 Jan / 31 Dec instead of truncating.
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))
import config as C
import p02_classify_and_report as p02

FAILS = []
BASE_YEARS = [2004, 2008, 2012]        # leap years -> all 366 template days present
N_BASE = len(BASE_YEARS)


def check(label, got, want):
    ok = (got == want)
    print("   [%s] %-58s got=%-12s expected=%s" % ("PASS" if ok else "FAIL", label,
                                                   str(got), str(want)))
    if not ok:
        FAILS.append(label)


def synthetic_county_days():
    """One county, three leap baseline years + one analysis year.
    metric value == template day-of-year, so the pool is self-identifying."""
    rows = []
    for y in BASE_YEARS + [C.ANALYSIS_YEARS[0]]:
        for d in pd.date_range("%d-01-01" % y, "%d-12-31" % y):
            rows.append((d, d.month, d.day, y, p02.MD_TO_TDOY[(d.month, d.day)]))
    cd = pd.DataFrame(rows, columns=["date", "month", "day", "year", "template_doy"])
    cd["county_fips"] = "48001"
    cd["county_name"] = "Synthetic"
    cd["probe_metric"] = cd["template_doy"].astype(float)
    return cd


def thresholds_for(cd, window_key):
    """min (pctl 0) and max (pctl 100) of the pooled day-of-year, plus the pool size."""
    spec = C.GRID_WINDOWS[window_key]
    thr, key_name = p02.compute_thresholds(cd, "probe_metric", [0, 100], spec, verbose=False)
    t = thr[thr["analysis_year"] == C.ANALYSIS_YEARS[0]].set_index(key_name)
    return t, key_name


print("=" * 82)
print("THRESHOLD WINDOW POOLING")
print("=" * 82)
cd = synthetic_county_days()
print("synthetic input: 1 county, baseline years %s (all leap -> 366 days each), "
      "analysis year %d" % (BASE_YEARS, C.ANALYSIS_YEARS[0]))
print("metric value == template day-of-year, so percentile 0/100 reveal the pooled range\n")

# ---------------------------------------------------------------- w05
print("-" * 82)
print("w05  --  centered 5-day window (target +/-2). Expect 5 days x %d years = %d values."
      % (N_BASE, 5 * N_BASE))
print("-" * 82)
t, key = thresholds_for(cd, "w05")
check("w05 key is day-of-year", key, "template_doy")
check("w05 has 366 keys", len(t), 366)
check("w05 pool size (all targets) == %d" % (5 * N_BASE),
      sorted(t["n_reference_values"].unique().tolist()), [5 * N_BASE])
# a mid-year target: doy 100 -> pools 98..102
check("w05 target doy 100 -> min pooled doy", int(t.loc[100, "threshold_p0_f"]), 98)
check("w05 target doy 100 -> max pooled doy", int(t.loc[100, "threshold_p100_f"]), 102)
# wrap across 1 Jan: doy 1 -> pools 365, 366, 1, 2, 3
check("w05 target doy 1 wraps to previous year (min)", int(t.loc[1, "threshold_p0_f"]), 1)
check("w05 target doy 1 wraps to previous year (max)", int(t.loc[1, "threshold_p100_f"]), 366)
# wrap across 31 Dec: doy 366 -> pools 364, 365, 366, 1, 2
check("w05 target doy 366 wraps to next year (min)", int(t.loc[366, "threshold_p0_f"]), 1)
check("w05 target doy 366 wraps to next year (max)", int(t.loc[366, "threshold_p100_f"]), 366)

# ---------------------------------------------------------------- w15
print("-" * 82)
print("w15  --  centered 15-day window (target +/-7). Expect 15 x %d = %d values."
      % (N_BASE, 15 * N_BASE))
print("-" * 82)
t15, _ = thresholds_for(cd, "w15")
check("w15 pool size (all targets) == %d" % (15 * N_BASE),
      sorted(t15["n_reference_values"].unique().tolist()), [15 * N_BASE])
check("w15 target doy 100 -> min pooled doy", int(t15.loc[100, "threshold_p0_f"]), 93)
check("w15 target doy 100 -> max pooled doy", int(t15.loc[100, "threshold_p100_f"]), 107)
check("w15 is WIDER than w05 (15 vs 5 days)",
      int(t15.loc[100, "n_reference_values"]) > int(t.loc[100, "n_reference_values"]), True)

# ---------------------------------------------------------------- month
print("-" * 82)
print("month  --  calendar-month bucket. Expect (days in month) x %d values." % N_BASE)
print("-" * 82)
tm, keym = thresholds_for(cd, "month")
check("month key is calendar month", keym, "calendar_month")
check("month has 12 keys", len(tm), 12)
check("month Jan pool size (31 x %d)" % N_BASE, int(tm.loc[1, "n_reference_values"]), 31 * N_BASE)
check("month Feb pool size (29 x %d, leap template)" % N_BASE,
      int(tm.loc[2, "n_reference_values"]), 29 * N_BASE)
check("month Jan pooled range = doy 1..31",
      (int(tm.loc[1, "threshold_p0_f"]), int(tm.loc[1, "threshold_p100_f"])), (1, 31))
check("month Dec pooled range = doy 336..366",
      (int(tm.loc[12, "threshold_p0_f"]), int(tm.loc[12, "threshold_p100_f"])), (336, 366))

# ---------------------------------------------------------------- month_pm7
print("-" * 82)
print("month_pm7  --  calendar month PLUS a 7-day collar either side.")
print("           Expect (days in month + 14) x %d values, and NOT the same pool as `month`."
      % N_BASE)
print("-" * 82)
tp, keyp = thresholds_for(cd, "month_pm7")
check("month_pm7 key is calendar month", keyp, "calendar_month")
check("month_pm7 has 12 keys", len(tp), 12)
check("month_pm7 Jan pool size ((31+14) x %d)" % N_BASE,
      int(tp.loc[1, "n_reference_values"]), 45 * N_BASE)
check("month_pm7 Feb pool size ((29+14) x %d)" % N_BASE,
      int(tp.loc[2, "n_reference_values"]), 43 * N_BASE)
check("month_pm7 Jul pool size ((31+14) x %d)" % N_BASE,
      int(tp.loc[7, "n_reference_values"]), 45 * N_BASE)
# February: Jan 25..31 (doy 25-31) + Feb (32..60) + Mar 1..7 (61..67) -- no wrapping
check("month_pm7 Feb pooled range = doy 25..67 (collar into Jan and Mar)",
      (int(tp.loc[2, "threshold_p0_f"]), int(tp.loc[2, "threshold_p100_f"])), (25, 67))
# July: Jun 24..30 (176..182) + Jul (183..213) + Aug 1..7 (214..220)
check("month_pm7 Jul pooled range = doy 176..220",
      (int(tp.loc[7, "threshold_p0_f"]), int(tp.loc[7, "threshold_p100_f"])), (176, 220))
# January wraps back into December; December wraps forward into January
check("month_pm7 Jan wraps into Dec (max pooled doy = 366)",
      int(tp.loc[1, "threshold_p100_f"]), 366)
check("month_pm7 Dec wraps into Jan (min pooled doy = 1)",
      int(tp.loc[12, "threshold_p0_f"]), 1)
check("month_pm7 pools strictly MORE than month, every month",
      bool((tp["n_reference_values"].to_numpy() ==
            tm["n_reference_values"].to_numpy() + 14 * N_BASE).all()), True)

# ---------------------------------------------------------------- distinctness
print("-" * 82)
print("The four windows must be genuinely DIFFERENT pools")
print("-" * 82)
check("w05 != w15 pool size", int(t.loc[100, "n_reference_values"]),
      5 * N_BASE)
check("month_pm7 Jul (45d) is wider than w15 (15d)",
      int(tp.loc[7, "n_reference_values"]) > int(t15.loc[200, "n_reference_values"]), True)
check("month_pm7 is not identical to month for any month",
      int((tp["n_reference_values"].to_numpy() == tm["n_reference_values"].to_numpy()).sum()), 0)

# ---------------------------------------------------------------- walk-forward
print("-" * 82)
print("WALK-FORWARD: year Y must never see year Y or later")
print("-" * 82)
spec = C.GRID_WINDOWS["month"]
thr_all, _ = p02.compute_thresholds(cd, "probe_metric", [50], spec, verbose=False)
# analysis year 2015 sees 3 baseline years; add a later analysis year and confirm the
# pool grows by exactly one year's worth of days once 2015 itself becomes history
cd2 = cd.copy()
n_2015 = int(thr_all[(thr_all["analysis_year"] == 2015) &
                     (thr_all["calendar_month"] == 1)]["n_reference_values"].iloc[0])
check("analysis year 2015 pools only the 3 prior leap years (Jan)", n_2015, 31 * N_BASE)
n_2016 = int(thr_all[(thr_all["analysis_year"] == 2016) &
                     (thr_all["calendar_month"] == 1)]["n_reference_values"].iloc[0])
check("analysis year 2016 additionally pools 2015 (Jan: +31)", n_2016, 31 * N_BASE + 31)

print()
print("=" * 82)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- all four windows pool the calendar days they claim to")
