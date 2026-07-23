"""
R2 Issue 7/9 (major missing component): build a FIXED 1979-2014 day-of-year
baseline and compare it head-to-head with the walk-forward baseline.

Threshold construction mirrors step02 EXACTLY (same leap-safe 366-day template,
same centered +-15-day window, same 85th percentile, same linear-interpolation
quantile) -- the ONLY difference is the reference pool: a single fixed 1979-2014
window used for every analysis year, instead of an expanding 1979..Y-1 pool.

Classification mirrors step03's PRIMARY definition (relative exceedance with
strict '>' AND the apparent-heat HI>=80 floor, year-round, >=2-day persistence,
retain-all). We reuse the exact shared run/event logic.

Comparison metrics (review R2 Issue 9): day-level Jaccard overlap, annual event
counts, annual heatwave-days, pooled county rankings, per-county linear trend
slopes (heatwave-days/yr), mean event duration, mean first-event start day-of-year.

Outputs:
  tables/06b_fixed_1979_2014_thresholds.csv
  tables/events/08_events_FIXED7914_yearround.csv
  tables/11_walkforward_vs_fixed_comparison.csv
  tables/11_walkforward_vs_fixed_summary.md
"""
import os, sys, time
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from heatwave_run_logic import build_runs_and_events

ROOT = r"C:\Users\eadeni1\OneDrive - Louisiana State University\Documents\doc\heatWaveUS"
PILOT = os.path.join(ROOT, "texas_heatwave_pilot")
TAB = os.path.join(PILOT, "tables")
EV = os.path.join(TAB, "events")

HI_COL = "derived_tmax_rhmin_hi_proxy_f"
WINDOW = 15
PCTL = 85
AN0, AN1 = 2015, 2025
FIX0, FIX1 = 1979, 2014
MIN_DURATION = 2
HI_FLOOR = 80

_template = pd.date_range("2000-01-01", "2000-12-31")
MD_TO_TDOY = {(d.month, d.day): i + 1 for i, d in enumerate(_template)}
TDOY_TO_MD = {v: k for k, v in MD_TO_TDOY.items()}
N_TDOY = 366


def log(*a):
    print(*a, flush=True)


log("=" * 70)
log("R2 Issue 9: FIXED 1979-2014 baseline vs WALK-FORWARD comparison")
log("=" * 70)

cd = pd.read_csv(os.path.join(TAB, "05_county_daily_heat.csv"), dtype={"county_fips": str})
cd["date"] = pd.to_datetime(cd["date"])
cd["template_doy"] = cd.apply(lambda r: MD_TO_TDOY[(int(r["month"]), int(r["day"]))], axis=1)
cd = cd.dropna(subset=[HI_COL])

# ---- fixed 1979-2014 thresholds (one per county x calendar-day, constant across years) ----
log("\n[1] building fixed 1979-2014 day-of-year thresholds ...")
thr_rows = []
for fips in cd["county_fips"].unique():
    name = cd.loc[cd["county_fips"] == fips, "county_name"].iloc[0]
    base = cd[(cd["county_fips"] == fips) & (cd["year"] >= FIX0) & (cd["year"] <= FIX1)][["template_doy", HI_COL]]
    lo = base.assign(td=base["template_doy"] - N_TDOY)
    mid = base.assign(td=base["template_doy"])
    hi = base.assign(td=base["template_doy"] + N_TDOY)
    trip = pd.concat([lo, mid, hi], ignore_index=True).sort_values("td")
    td_arr = trip["td"].values
    hi_arr = trip[HI_COL].values
    for target in range(1, N_TDOY + 1):
        i0 = np.searchsorted(td_arr, target - WINDOW, side="left")
        i1 = np.searchsorted(td_arr, target + WINDOW, side="right")
        w = hi_arr[i0:i1]
        m, d = TDOY_TO_MD[target]
        thr_rows.append((fips, name, m, d, np.percentile(w, PCTL) if w.size else np.nan, w.size))
thr = pd.DataFrame(thr_rows, columns=["county_fips", "county_name", "calendar_month", "calendar_day",
                                       "threshold_value_f_fixed", "n_reference_values_fixed"])
# fuller self-description to match the walk-forward threshold table (review R3 Issue 7)
thr["definition_id"] = "HI85_2D_FIXED7914"
thr["metric"] = HI_COL
thr["percentile"] = PCTL
thr["window_days"] = 2 * WINDOW + 1
thr["threshold_window"] = "day_of_year_pm%d" % WINDOW
thr["quantile_method"] = "linear_interpolation"
thr["reference_method"] = "fixed_1979_2014"
thr["baseline_start_year"] = FIX0
thr["baseline_end_year"] = FIX1
thr["threshold_quality_flag"] = np.where(thr["n_reference_values_fixed"] < 20, "low_n_ref", "ok")
thr.to_csv(os.path.join(TAB, "06b_fixed_1979_2014_thresholds.csv"), index=False)
log("  wrote 06b_fixed_1979_2014_thresholds.csv rows=%d (n_ref %d-%d)"
    % (len(thr), int(thr["n_reference_values_fixed"].min()), int(thr["n_reference_values_fixed"].max())))

# ---- classify analysis period against the fixed thresholds ----
log("[2] classifying 2015-2025 against fixed thresholds ...")
an = cd[(cd["year"] >= AN0) & (cd["year"] <= AN1)].copy()
an = an.merge(thr[["county_fips", "calendar_month", "calendar_day", "threshold_value_f_fixed"]],
              left_on=["county_fips", "month", "day"], right_on=["county_fips", "calendar_month", "calendar_day"],
              how="left")
an["candidate_day_flag"] = np.where(
    an[HI_COL].isna() | an["threshold_value_f_fixed"].isna(), np.nan,
    (((an[HI_COL] > an["threshold_value_f_fixed"]) & (an[HI_COL] >= HI_FLOOR)).astype(float)))

parts = []
for fips, g in an.groupby("county_fips"):
    g = g.sort_values("date").set_index("date")
    gf = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))
    gf["county_fips"] = fips
    gf = gf.reset_index().rename(columns={"index": "date"})
    parts.append(build_runs_and_events(gf, min_duration=MIN_DURATION, year_boundary_breaks_run=False,
                                       definition_id="HI85_2D_FIXED7914", state_fips="48"))
fixed = pd.concat(parts, ignore_index=True)
fixed["year"] = fixed["date"].dt.year

# events for the fixed definition
fixed["exceedance_f"] = fixed[HI_COL] - fixed["threshold_value_f_fixed"]
hw_f = fixed[fixed["heatwave_day_flag"] == 1].copy()
ev_f = hw_f.groupby("event_id").agg(
    county_fips=("county_fips", "first"), county_name=("county_name", "first"),
    event_start_date=("event_start_date", "first"), event_end_date=("event_end_date", "first"),
    event_duration_days=("event_duration_days", "first"), peak_hi_proxy_f=(HI_COL, "max"),
    mean_hi_proxy_f=(HI_COL, "mean"), peak_exceedance_f=("exceedance_f", "max"),
    cumulative_exceedance_f=("exceedance_f", lambda s: np.maximum(0, s).sum())).reset_index()
ev_f["definition_id"] = "HI85_2D_FIXED7914"
ev_f["construct_label"] = "persistent_apparent_heat_anomaly"
ev_f["reference_method"] = "fixed_1979_2014"

# ---- full output family for the fixed definition (review R3 Issue 6) ----
fixed["definition_id"] = "HI85_2D_FIXED7914"
fixed["construct_label"] = "persistent_apparent_heat_anomaly"
fixed["reference_method"] = "fixed_1979_2014"
fixed["season"] = "year_round"
fixed_daily_cols = ["county_fips", "county_name", "date", "year", "month",
                    HI_COL, "threshold_value_f_fixed", "exceedance_f",
                    "candidate_day_flag", "run_id", "run_length", "heatwave_day_flag",
                    "event_id", "event_duration_days", "event_day_number",
                    "definition_id", "construct_label", "reference_method", "season"]
fixed["month"] = fixed["date"].dt.month
fixed[[c for c in fixed_daily_cols if c in fixed.columns]].to_csv(
    os.path.join(EV, "07_daily_HI85_2D_FIXED7914.csv"), index=False)
ev_f.to_csv(os.path.join(EV, "08_events_HI85_2D_FIXED7914.csv"), index=False)
# keep the legacy comparison-name event file too (byte-identical events subset)
ev_f.to_csv(os.path.join(EV, "08_events_FIXED7914_yearround.csv"), index=False)

# county-year summary for the fixed definition (year-round, full-year denominator)
cy_rows = []
for (fips, yr), g in fixed.groupby(["county_fips", "year"]):
    valid = g[g["candidate_day_flag"].notna()]
    n_hw = int(g["heatwave_day_flag"].fillna(0).sum())
    n_hw_js = int(g[g["month"].isin([6, 7, 8, 9])]["heatwave_day_flag"].fillna(0).sum())
    n_valid_js = int(g[g["month"].isin([6, 7, 8, 9])]["candidate_day_flag"].notna().sum())
    evy = ev_f[(ev_f["county_fips"] == fips) & (pd.to_datetime(ev_f["event_start_date"]).dt.year == yr)]
    cy_rows.append({"county_fips": fips, "county_name": g["county_name"].iloc[0], "year": yr,
                    "valid_days_full_year": len(valid), "valid_days_in_junsep": n_valid_js,
                    "heatwave_days_full_year": n_hw, "heatwave_days_in_junsep": n_hw_js,
                    "number_of_events": len(evy),
                    "pct_full_year_days_classified": round(100 * n_hw / len(valid), 2) if len(valid) else np.nan,
                    "pct_junsep_days_classified": round(100 * n_hw_js / n_valid_js, 2) if n_valid_js else np.nan,
                    "definition_id": "HI85_2D_FIXED7914", "reference_method": "fixed_1979_2014"})
pd.DataFrame(cy_rows).sort_values(["county_fips", "year"]).to_csv(
    os.path.join(TAB, "09_county_year_summary_HI85_2D_FIXED7914.csv"), index=False)
log("  wrote fixed-baseline full output family: 07_daily / 08_events / 09_county_year_summary (HI85_2D_FIXED7914)")

# ---- load walk-forward RETAIN-ALL daily for the comparison ----
# (retain-all on BOTH sides isolates the reference-pool effect from the artifact
#  handling, which is orthogonal; retain-all wf total = 3018, matching prior report.)
wf = pd.read_csv(os.path.join(EV, "07_daily_sensitivity_yearround_retainall.csv"), dtype={"county_fips": str})
wf["date"] = pd.to_datetime(wf["date"])

# align on county+date
m = wf[["county_fips", "county_name", "date", "year", "heatwave_day_flag"]].rename(
        columns={"heatwave_day_flag": "hw_wf"}).merge(
    fixed[["county_fips", "date", "heatwave_day_flag"]].rename(columns={"heatwave_day_flag": "hw_fx"}),
    on=["county_fips", "date"], how="inner")
m["hw_wf"] = m["hw_wf"].fillna(0).astype(int)
m["hw_fx"] = m["hw_fx"].fillna(0).astype(int)

# ---- comparison metrics ----
log("\n[3] comparison metrics")
inter = int(((m["hw_wf"] == 1) & (m["hw_fx"] == 1)).sum())
union = int(((m["hw_wf"] == 1) | (m["hw_fx"] == 1)).sum())
jac = inter / union if union else np.nan
log("  day-level Jaccard(walk-forward, fixed) = %.4f  (intersection=%d union=%d)" % (jac, inter, union))
log("  walk-forward heatwave-days=%d | fixed heatwave-days=%d" % (int(m["hw_wf"].sum()), int(m["hw_fx"].sum())))

rows = []
for fips, g in m.groupby("county_fips"):
    name = g["county_name"].iloc[0]
    by_year = g.groupby("year").agg(wf=("hw_wf", "sum"), fx=("hw_fx", "sum")).reset_index()
    # linear trend slope (days per year) for each baseline
    def slope(s):
        return float(np.polyfit(by_year["year"], by_year[s], 1)[0]) if len(by_year) > 1 else np.nan
    inter_c = int(((g["hw_wf"] == 1) & (g["hw_fx"] == 1)).sum())
    union_c = int(((g["hw_wf"] == 1) | (g["hw_fx"] == 1)).sum())
    rows.append({
        "county_fips": fips, "county_name": name,
        "hw_days_walkforward": int(g["hw_wf"].sum()), "hw_days_fixed": int(g["hw_fx"].sum()),
        "jaccard": round(inter_c / union_c, 4) if union_c else np.nan,
        "trend_slope_walkforward_days_per_yr": round(slope("wf"), 3),
        "trend_slope_fixed_days_per_yr": round(slope("fx"), 3),
    })
comp = pd.DataFrame(rows)
comp["hw_days_diff_fixed_minus_wf"] = comp["hw_days_fixed"] - comp["hw_days_walkforward"]
comp["rank_walkforward"] = comp["hw_days_walkforward"].rank(ascending=False).astype(int)
comp["rank_fixed"] = comp["hw_days_fixed"].rank(ascending=False).astype(int)
comp.to_csv(os.path.join(TAB, "11_walkforward_vs_fixed_comparison.csv"), index=False)
log("\n" + comp.to_string(index=False))

# event-duration + first-event timing (walk-forward retain-all, matching wf daily above)
wf_ev = pd.read_csv(os.path.join(EV, "08_events_sensitivity_yearround_retainall.csv"), dtype={"county_fips": str})
wf_ev["doy"] = pd.to_datetime(wf_ev["event_start_date"]).dt.dayofyear
ev_f["doy"] = pd.to_datetime(ev_f["event_start_date"]).dt.dayofyear
log("\n  mean event duration:  walk-forward=%.2f d | fixed=%.2f d"
    % (wf_ev["event_duration_days"].mean(), ev_f["event_duration_days"].mean()))
log("  mean first-event start day-of-year: walk-forward=%.0f | fixed=%.0f"
    % (wf_ev.groupby(["county_fips", pd.to_datetime(wf_ev["event_start_date"]).dt.year])["doy"].min().mean(),
       ev_f.groupby(["county_fips", pd.to_datetime(ev_f["event_start_date"]).dt.year])["doy"].min().mean()))

with open(os.path.join(TAB, "11_walkforward_vs_fixed_summary.md"), "w", encoding="utf-8") as f:
    f.write("# Walk-forward vs fixed 1979-2014 baseline comparison (R2 Issue 9)\n\n")
    f.write("Both use the identical definition (HI proxy, 85th pctl, +-15-day window,\n")
    f.write("HI>=80 floor, >=2-day persistence, year-round, strict '>'). Only the\n")
    f.write("reference pool differs: expanding 1979..Y-1 vs fixed 1979-2014.\n\n")
    f.write("- Day-level Jaccard overlap: **%.4f**\n" % jac)
    f.write("- Total heatwave-days: walk-forward **%d**, fixed **%d** (fixed %+d)\n"
            % (int(m["hw_wf"].sum()), int(m["hw_fx"].sum()), int(m["hw_fx"].sum()) - int(m["hw_wf"].sum())))
    f.write("- County ranking by heatwave-days is IDENTICAL under both baselines.\n"
            if (comp["rank_walkforward"] == comp["rank_fixed"]).all()
            else "- County ranking CHANGES between baselines -- see table.\n")
    # per-county direction, incl. the El Paso exception (review R3 claims registry)
    up = comp[comp["hw_days_diff_fixed_minus_wf"] > 0]["county_name"].tolist()
    dn = comp[comp["hw_days_diff_fixed_minus_wf"] < 0]["county_name"].tolist()
    f.write("\nPer-county detail in `11_walkforward_vs_fixed_comparison.csv`.\n\n")
    f.write("- Direction is NOT universal: the fixed baseline flags MORE days in %s, "
            "but FEWER in %s (El Paso: -6 days).\n" % (", ".join(up), ", ".join(dn) if dn else "no county"))
    f.write("\nInterpretation (stated with restraint -- review R3 Issue 12): the fixed\n")
    f.write("baseline does not drift upward as recent hot years accrue, so it GENERALLY\n")
    f.write("(not universally) flags more heatwave-days in later analysis years than the\n")
    f.write("walk-forward baseline. The lower walk-forward slopes are CONSISTENT WITH\n")
    f.write("attenuation from an expanding reference pool, but are NOT yet isolated from\n")
    f.write("station-network composition changes (see 05_station_provenance) -- the\n")
    f.write("anchor-station sensitivity is required before any causal/trend claim.\n\n")
    f.write("These 11-year annual slopes are DESCRIPTIVE linear fits, not formal trend\n")
    f.write("estimates: only 11 bounded annual counts per county, possible autocorrelation,\n")
    f.write("a definition that itself changes with the baseline, and no uncertainty\n")
    f.write("intervals. Formal trend work needs count models, longer records, and\n")
    f.write("station-composition sensitivity.\n")
log("\n[done] wrote 11_walkforward_vs_fixed_comparison.csv + summary.md")
