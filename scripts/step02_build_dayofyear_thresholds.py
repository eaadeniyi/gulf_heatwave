"""
STEP 9-11 (spec Part D): county-CALENDAR-DAY (not month-bucket) walk-forward
thresholds, centered +/-15-day (31-day) window, for the 5 TX pilot counties.

Leap day rule (Step 11 -- documented, applied consistently): calendar days are
matched by (month, day) against a fixed 366-day template built from a leap
year (2000), so "Mar 1" always maps to the same template position (61)
whether or not that particular historical year was itself a leap year. This
avoids the classic day-of-year integer drift bug where dt.dayofyear silently
shifts every date after Feb by one day in non-leap years. Feb 29 is treated
as its own calendar target (template position 60), pooling only the
historical years that actually had a Feb 29 within its own +/-15-day window;
no interpolation is used (chose Step 11's first documented option, not the
Feb28/Mar1-interpolation alternative).

Walk-forward rule: for analysis year Y, the reference pool for every target
calendar day is all matching-window observations from 1979 through Y-1
(config: reference_period.primary_method = walk_forward).

Output: tables/06_county_calendar_thresholds.csv
"""
import os, sys, time
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

ROOT = r"C:\Users\eadeni1\OneDrive - Louisiana State University\Documents\doc\heatWaveUS"
PILOT = os.path.join(ROOT, "texas_heatwave_pilot")
TAB = os.path.join(PILOT, "tables")

WINDOW = 15          # +/- days -> 31-day window (config: calendar_window_days=31)
PCTL = 85            # config: relative_threshold.percentile=0.85
AN0, AN1 = 2015, 2025  # config: analysis_period
BASE_START = 1979     # config: reference_period.walk_forward_pool_start_year
MIN_REF_OBS = 20      # config: quality_control.minimum_reference_observations_per_threshold

# ---- fixed 366-day (month,day) -> template_doy lookup (leap year 2000) ----
_template_dates = pd.date_range("2000-01-01", "2000-12-31")
MD_TO_TDOY = {(d.month, d.day): i + 1 for i, d in enumerate(_template_dates)}
TDOY_TO_MD = {v: k for k, v in MD_TO_TDOY.items()}
N_TDOY = 366


def log(*a):
    print(*a, flush=True)


log("=" * 70)
log("STEP 9-11: day-of-year windowed walk-forward thresholds")
log("  window=+/-%d days  percentile=%d  analysis_years=%d-%d  baseline_start=%d"
    % (WINDOW, PCTL, AN0, AN1, BASE_START))
log("=" * 70)

HI_COL = "derived_tmax_rhmin_hi_proxy_f"   # renamed per review Issue 1

cd = pd.read_csv(os.path.join(TAB, "05_county_daily_heat.csv"), dtype={"county_fips": str})
cd["date"] = pd.to_datetime(cd["date"])
cd["template_doy"] = cd.apply(lambda r: MD_TO_TDOY[(int(r["month"]), int(r["day"]))], axis=1)
cd = cd.dropna(subset=[HI_COL])

counties = cd["county_fips"].unique()
t0 = time.time()
thr_rows = []

for fips in counties:
    county_name = cd.loc[cd["county_fips"] == fips, "county_name"].iloc[0]
    full = cd[cd["county_fips"] == fips][["year", "template_doy", HI_COL]].copy()

    for y in range(AN0, AN1 + 1):
        base = full[full["year"] <= y - 1]
        if base.empty:
            continue
        # tripled + sorted array for O(log n) circular-window lookups
        lo = base.assign(td=base["template_doy"] - N_TDOY)
        mid = base.assign(td=base["template_doy"])
        hi = base.assign(td=base["template_doy"] + N_TDOY)
        trip = pd.concat([lo, mid, hi], ignore_index=True).sort_values("td")
        td_arr = trip["td"].values
        hi_arr = trip[HI_COL].values

        for target in range(1, N_TDOY + 1):
            i0 = np.searchsorted(td_arr, target - WINDOW, side="left")
            i1 = np.searchsorted(td_arr, target + WINDOW, side="right")
            window_vals = hi_arr[i0:i1]
            n_ref = window_vals.size
            thr_val = np.percentile(window_vals, PCTL) if n_ref > 0 else np.nan
            m, d = TDOY_TO_MD[target]
            thr_rows.append((fips, county_name, m, d, target, y, thr_val, n_ref))

    log("  %-22s done (%.1fs elapsed)" % (county_name, time.time() - t0))

thr = pd.DataFrame(thr_rows, columns=["county_fips", "county_name", "calendar_month", "calendar_day",
                                       "template_doy", "analysis_year", "threshold_value_f", "n_reference_values"])
thr["percentile"] = PCTL
thr["window_days"] = 2 * WINDOW + 1
thr["quantile_method"] = "linear_interpolation"
thr["baseline_start_year"] = BASE_START
thr["baseline_end_year"] = thr["analysis_year"] - 1
thr["threshold_quality_flag"] = np.where(thr["n_reference_values"] < MIN_REF_OBS, "low_n_ref", "ok")
# definition metadata (review R2 Issue 12A -- every output self-describes its definition)
thr["definition_id"] = "HI85_2D"
thr["metric"] = HI_COL
thr["reference_method"] = "walk_forward_1979_to_Yminus1"
thr["threshold_window"] = "day_of_year_pm%d" % WINDOW

n_low = (thr["threshold_quality_flag"] == "low_n_ref").sum()
log("\n[summary] thresholds built: %d rows" % len(thr))
log("  n_reference_values: min=%d p1=%.0f median=%.0f max=%d" % (
    thr["n_reference_values"].min(), thr["n_reference_values"].quantile(0.01),
    thr["n_reference_values"].median(), thr["n_reference_values"].max()))
log("  flagged low_n_ref (<%d obs): %d rows (%.2f%%)" % (MIN_REF_OBS, n_low, 100 * n_low / len(thr)))

out_path = os.path.join(TAB, "06_county_calendar_thresholds.csv")
thr.to_csv(out_path, index=False)
log("\n[done] wrote %s rows=%d" % (out_path, len(thr)))

# quick sanity print: Harris County, Aug 1, across a few analysis years
sanity = thr[(thr["county_fips"] == "48201") & (thr["calendar_month"] == 8) & (thr["calendar_day"] == 1)]
log("\n[sanity check] Harris County, Aug 1 threshold by analysis year:")
log(sanity[["analysis_year", "threshold_value_f", "n_reference_values"]].to_string(index=False))
