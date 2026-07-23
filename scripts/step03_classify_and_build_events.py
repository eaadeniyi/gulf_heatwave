"""
STEP 12-19 (spec Parts E+F): join thresholds, classify candidate days, build
runs/events, compute event-level statistics, evaluate absolute thresholds.

REVISION 2026-07-16 (external review corrections):
  - Issue 1: uses renamed derived_tmax_rhmin_hi_proxy_f throughout.
  - Issue 2: qc_status propagated to the daily table; per-event columns
    event_contains_suspicious_day / n_suspicious_days / peak_day_qc_status;
    THREE event scenarios produced (retain-all PRIMARY, suspicious-set-missing,
    and warm-season) so severity impact is visible.
  - Issue 4: each day tagged with season membership; a warm-season (Jun-Sep)
    event table produced alongside the year-round one. Year-round events carry
    construct_label = 'persistent_apparent_heat_anomaly' (NOT 'heatwave'),
    warm-season events carry 'warm_season_heatwave'.
  - Issue 5: PRIMARY candidate uses the apparent-heat floor (proxy HI>=80);
    a SENSITIVITY candidate using the formula-domain floor (Tmax>=80) is also
    computed and its events written to a separate sensitivity table.

Outputs:
  tables/07_county_daily_classification.csv               (one row per county-day)
  tables/events/08_heatwave_events_PRIMARY_yearround_retainall.csv
  tables/events/08_sensitivity_yearround_suspicious_set_missing.csv
  tables/events/08_sensitivity_warmseason_junsep.csv
  tables/events/08_sensitivity_yearround_tmaxfloor.csv
"""
import os, sys
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
os.makedirs(EV, exist_ok=True)

HI_COL = "derived_tmax_rhmin_hi_proxy_f"
AN0, AN1 = 2015, 2025
MIN_DURATION = 2
YEAR_BOUNDARY_BREAKS_RUN = False
STATE_FIPS = "48"
WARM_MONTHS = [6, 7, 8, 9]


def log(*a):
    print(*a, flush=True)


INT_DAILY = ["relative_exceedance_flag", "floor_hi_ge_80", "domain_tmax_ge_80",
             "candidate_day_flag", "run_length", "heatwave_day_flag",
             "event_duration_days", "event_day_number",
             "event_onset_flag", "event_continuation_flag", "event_final_day_flag",
             "max_hi_ge_95f", "max_hi_ge_100f", "max_hi_ge_103f", "tmax_ge_95f", "tmax_ge_100f"]


def stamp_metadata(df, meta):
    """Attach the full definition metadata block (review R2 Issue 12A) so every
    output self-describes its definition and is safe to concatenate."""
    for k, v in meta.items():
        df[k] = v
    return df


def build_events_from_candidate(daily, cand_col, meta):
    """Reindex to full daily calendar per county, run the shared run/event logic,
    compute event-level stats + QC/absolute indicators. Returns (daily_out, events)."""
    parts = []
    for fips, g in daily.groupby("county_fips"):
        g = g.sort_values("date").set_index("date")
        full = pd.date_range(g.index.min(), g.index.max(), freq="D")
        gf = g.reindex(full)
        gf["county_fips"] = fips
        gf = gf.reset_index().rename(columns={"index": "date"})
        gf["candidate_day_flag"] = gf[cand_col]
        ge = build_runs_and_events(gf, min_duration=MIN_DURATION,
                                   year_boundary_breaks_run=YEAR_BOUNDARY_BREAKS_RUN,
                                   definition_id=meta["definition_id"], state_fips=STATE_FIPS)
        parts.append(ge)
    out = pd.concat(parts, ignore_index=True)
    out["exceedance_f"] = out[HI_COL] - out["threshold_value_f"]
    out["_is_suspicious"] = (out["qc_status"] == "suspicious_retain")
    out = stamp_metadata(out, meta)
    # nullable-integer dtypes for flags/counts/durations (review R2 Issue 12E)
    for c in INT_DAILY:
        if c in out.columns:
            out[c] = out[c].astype("Int64")

    hw = out[out["heatwave_day_flag"] == 1].copy()
    if not len(hw):
        return out, pd.DataFrame()
    # peak-day qc status + DATE of peak HI and DATE of peak exceedance (review R2 Issue 4C/12C)
    peak_hi_idx = hw.groupby("event_id")[HI_COL].idxmax()
    peak_exc_idx = hw.groupby("event_id")["exceedance_f"].idxmax()
    peak_qc = hw.loc[peak_hi_idx, ["event_id", "qc_status"]].set_index("event_id")["qc_status"]
    peak_hi_date = hw.loc[peak_hi_idx, ["event_id", "date"]].set_index("event_id")["date"]
    peak_exc_date = hw.loc[peak_exc_idx, ["event_id", "date"]].set_index("event_id")["date"]

    ev = hw.groupby("event_id").agg(
        county_fips=("county_fips", "first"),
        county_name=("county_name", "first"),
        climate_division=("climate_division", "first"),
        event_start_date=("event_start_date", "first"),
        event_end_date=("event_end_date", "first"),
        event_duration_days=("event_duration_days", "first"),
        peak_hi_proxy_f=(HI_COL, "max"),
        mean_hi_proxy_f=(HI_COL, "mean"),
        peak_exceedance_f=("exceedance_f", "max"),
        mean_exceedance_f=("exceedance_f", "mean"),
        cumulative_exceedance_f=("exceedance_f", lambda s: np.maximum(0, s).sum()),
        n_suspicious_days=("_is_suspicious", "sum"),
        n_days_hi_ge_95f=("max_hi_ge_95f", "sum"),
        n_days_hi_ge_100f=("max_hi_ge_100f", "sum"),
        n_days_hi_ge_103f=("max_hi_ge_103f", "sum"),
        n_days_tmax_ge_95f=("tmax_ge_95f", "sum"),
        n_days_tmax_ge_100f=("tmax_ge_100f", "sum"),
    ).reset_index()
    ev["event_contains_suspicious_day"] = ev["n_suspicious_days"] > 0
    ev["peak_day_qc_status"] = ev["event_id"].map(peak_qc)
    ev["peak_hi_date"] = ev["event_id"].map(peak_hi_date)
    ev["peak_exceedance_date"] = ev["event_id"].map(peak_exc_date)
    ev["any_day_hi_ge_95f"] = ev["n_days_hi_ge_95f"] > 0
    ev["any_day_hi_ge_100f"] = ev["n_days_hi_ge_100f"] > 0
    ev["any_day_hi_ge_103f"] = ev["n_days_hi_ge_103f"] > 0
    ev = stamp_metadata(ev, meta)
    for c in ["event_duration_days", "n_suspicious_days", "n_days_hi_ge_95f", "n_days_hi_ge_100f",
              "n_days_hi_ge_103f", "n_days_tmax_ge_95f", "n_days_tmax_ge_100f"]:
        ev[c] = ev[c].astype("Int64")
    ev = ev.sort_values(["county_fips", "event_start_date"])
    return out, ev


log("=" * 70)
log("STEP 12-19: classification + run/event construction (revised 2026-07-16)")
log("=" * 70)

cd = pd.read_csv(os.path.join(TAB, "05_county_daily_heat.csv"), dtype={"county_fips": str})
cd["date"] = pd.to_datetime(cd["date"])
thr = pd.read_csv(os.path.join(TAB, "06_county_calendar_thresholds.csv"), dtype={"county_fips": str})

an = cd[(cd["year"] >= AN0) & (cd["year"] <= AN1)].copy()
an = an.merge(
    thr[["county_fips", "calendar_month", "calendar_day", "analysis_year", "threshold_value_f", "n_reference_values"]],
    left_on=["county_fips", "month", "day", "year"],
    right_on=["county_fips", "calendar_month", "calendar_day", "analysis_year"], how="left")
log("[1] analysis-period county-days %d-%d: %d rows (%d matched to thresholds)"
    % (AN0, AN1, len(an), an["threshold_value_f"].notna().sum()))

# ---- Step 13: relative exceedance + the two floor variants (Issue 5) ----
an["relative_exceedance_flag"] = (an[HI_COL] > an["threshold_value_f"]).astype("Int64")

def make_candidate(floor_col):
    return np.where(an[HI_COL].isna() | an["threshold_value_f"].isna(), np.nan,
                    ((an["relative_exceedance_flag"] == 1) & (an[floor_col] == 1)).astype(float))

# base candidates (retain-all)
an["candidate_retainall_hifloor"] = make_candidate("floor_hi_ge_80")
an["candidate_sens_tmaxfloor_retainall"] = make_candidate("domain_tmax_ge_80")

# PRIMARY (review R3 Issue 3): the 3 confirmed RH-clipping artifacts
# (qc_rh_pin_likely_artifact, 2023-03-01) are set to MISSING so the prespecified
# missing-day run rule handles them, rather than letting a +15-24F inflated proxy
# stand inside the declared primary analysis. Applied to every HI-floor variant so
# the scenarios stay comparable; retain-all is preserved as an explicit sensitivity.
_artifact = an["qc_rh_pin_likely_artifact"].fillna(False).values if "qc_rh_pin_likely_artifact" in an.columns else np.zeros(len(an), bool)
an["candidate_primary_hifloor"] = an["candidate_retainall_hifloor"].where(~_artifact, np.nan)
an["candidate_sens_tmaxfloor"] = an["candidate_sens_tmaxfloor_retainall"].where(~_artifact, np.nan)
log("    confirmed-artifact county-days set MISSING in primary/floor/warm scenarios: %d" % int(_artifact.sum()))

# season tag (Issue 4)
an["season_junsep"] = an["month"].isin(WARM_MONTHS)

# absolute indicators (Step 19)
an["max_hi_ge_95f"] = (an[HI_COL] >= 95).astype("Int64")
an["max_hi_ge_100f"] = (an[HI_COL] >= 100).astype("Int64")
an["max_hi_ge_103f"] = (an[HI_COL] >= 103).astype("Int64")
an["tmax_ge_95f"] = (an["tmax_f"] >= 95).astype("Int64")
an["tmax_ge_100f"] = (an["tmax_f"] >= 100).astype("Int64")

n_cand_primary = int(np.nansum(an["candidate_primary_hifloor"].values))
n_cand_tmax = int(np.nansum(an["candidate_sens_tmaxfloor"].values))
log("[2] candidate days -- primary HI-floor: %d | sensitivity Tmax-floor: %d (diff %+d)"
    % (n_cand_primary, n_cand_tmax, n_cand_tmax - n_cand_primary))

# shared metadata block skeleton (review R2 Issue 12A)
def meta_for(definition_id, construct_label, season, floor_variable, floor_value):
    return {
        "definition_id": definition_id, "construct_label": construct_label,
        "metric": HI_COL, "reference_method": "walk_forward_1979_to_Yminus1",
        "season": season, "floor_variable": floor_variable, "floor_value": floor_value,
        "minimum_duration": MIN_DURATION, "comparison_operator": ">",
    }

# ===== SCENARIO 1 (PRIMARY): year-round, HI floor, confirmed artifacts set MISSING =====
d1, ev1 = build_events_from_candidate(
    an, "candidate_primary_hifloor",
    meta_for("HI85_2D", "persistent_apparent_heat_anomaly", "year_round", "floor_hi_ge_80", 80))

# ===== SCENARIO 1b (sensitivity): year-round, HI floor, RETAIN all artifacts (old primary) =====
d1b, ev1b = build_events_from_candidate(
    an, "candidate_retainall_hifloor",
    meta_for("HI85_2D_RETAINALL", "persistent_apparent_heat_anomaly", "year_round", "floor_hi_ge_80", 80))

# ===== SCENARIO 2 (sensitivity): year-round, suspicious set to missing =====
an_susp = an.copy()
susp_mask = (an_susp["qc_status"] == "suspicious_retain")
an_susp["candidate_susp_missing"] = an_susp["candidate_primary_hifloor"].where(~susp_mask, np.nan)
d2, ev2 = build_events_from_candidate(
    an_susp, "candidate_susp_missing",
    meta_for("HI85_2D_SUSPMISSING", "persistent_apparent_heat_anomaly", "year_round", "floor_hi_ge_80", 80))

# ===== SCENARIO 3 (sensitivity): warm-season Jun-Sep only, HI floor =====
# season applied BEFORE run construction (review R2 Issue 4): out-of-season days
# become non-candidate (0), which prevents runs bridging the season gap.
an_warm = an.copy()
an_warm["candidate_warm"] = an_warm["candidate_primary_hifloor"].where(an_warm["season_junsep"], 0.0)
d3, ev3 = build_events_from_candidate(
    an_warm, "candidate_warm",
    meta_for("HI85_2D_JUNSEP", "warm_season_heatwave", "jun_sep", "floor_hi_ge_80", 80))

# ===== SCENARIO 4 (sensitivity): year-round, Tmax formula-domain floor =====
d4, ev4 = build_events_from_candidate(
    an, "candidate_sens_tmaxfloor",
    meta_for("HI85_2D_TMAXFLOOR", "persistent_apparent_heat_anomaly", "year_round", "domain_tmax_ge_80", 80))

# ---------------------------------------------------------------
# Write daily classification + event table for EVERY scenario
# (review R2 Issue 3/12B: full output family per scenario)
# ---------------------------------------------------------------
META_COLS = ["definition_id", "construct_label", "metric", "reference_method",
             "season", "floor_variable", "floor_value", "minimum_duration", "comparison_operator"]
daily_cols = (["county_fips", "county_name", "climate_division", "date", "year", "month", "day",
               "season_junsep", "tmax_f", "tmin_f", HI_COL, "threshold_value_f", "n_reference_values",
               "exceedance_f", "relative_exceedance_flag", "floor_hi_ge_80", "domain_tmax_ge_80",
               "candidate_day_flag", "run_id", "run_length", "heatwave_day_flag",
               "event_id", "event_duration_days", "event_day_number",
               "event_onset_flag", "event_continuation_flag", "event_final_day_flag",
               "max_hi_ge_95f", "max_hi_ge_100f", "max_hi_ge_103f", "tmax_ge_95f", "tmax_ge_100f",
               "qc_status"] + META_COLS)

SCENARIOS = [
    ("PRIMARY_yearround_artifactmissing", d1, ev1),
    ("sensitivity_yearround_retainall", d1b, ev1b),
    ("sensitivity_yearround_suspicious_set_missing", d2, ev2),
    ("sensitivity_warmseason_junsep", d3, ev3),
    ("sensitivity_yearround_tmaxfloor", d4, ev4),
]
for tag, d, ev in SCENARIOS:
    d[[c for c in daily_cols if c in d.columns]].to_csv(
        os.path.join(EV, "07_daily_%s.csv" % tag), index=False)
    ev.to_csv(os.path.join(EV, "08_events_%s.csv" % tag), index=False)

# canonical primary daily classification at the top-level path (review R3: this is
# the SINGLE canonical primary table; events/07_daily_PRIMARY_* is byte-identical).
d1[daily_cols].to_csv(os.path.join(TAB, "07_county_daily_classification.csv"), index=False)
log("[done] wrote 07_county_daily_classification.csv (canonical primary) rows=%d" % len(d1))
log("[done] wrote daily+event tables for all %d scenarios under events/" % len(SCENARIOS))

# ---------------------------------------------------------------
# Scenario comparison summary
# ---------------------------------------------------------------
def hw_days(d):
    return int(d["heatwave_day_flag"].sum())

log("\n" + "=" * 70)
log("SCENARIO COMPARISON")
log("=" * 70)
log("  %-56s events=%4d  heatwave-days=%5d" % ("1. PRIMARY year-round, HI-floor, ARTIFACTS MISSING", len(ev1), hw_days(d1)))
log("  %-56s events=%4d  heatwave-days=%5d" % ("1b. year-round, HI-floor, RETAIN-ALL (sensitivity)", len(ev1b), hw_days(d1b)))
log("  %-56s events=%4d  heatwave-days=%5d" % ("2. year-round, ALL-suspicious->missing (sensitivity)", len(ev2), hw_days(d2)))
log("  %-56s events=%4d  heatwave-days=%5d" % ("3. warm-season Jun-Sep only (sensitivity)", len(ev3), hw_days(d3)))
log("  %-56s events=%4d  heatwave-days=%5d" % ("4. year-round, Tmax-floor (sensitivity)", len(ev4), hw_days(d4)))

if len(ev1):
    n_susp_ev = int(ev1["event_contains_suspicious_day"].sum())
    log("\n  PRIMARY: %d/%d events contain >=1 suspicious day; %d events have a suspicious PEAK day"
        % (n_susp_ev, len(ev1), int((ev1["peak_day_qc_status"] == "suspicious_retain").sum())))
    # seasonal split of primary heatwave days
    hw1 = d1[d1["heatwave_day_flag"] == 1]
    log("  PRIMARY seasonal split of heatwave-days: Jun-Sep %.1f%% | May-Oct %.1f%% | Nov-Apr %.1f%%"
        % (100 * hw1["month"].isin([6, 7, 8, 9]).mean(),
           100 * hw1["month"].isin([5, 6, 7, 8, 9, 10]).mean(),
           100 * hw1["month"].isin([11, 12, 1, 2, 3, 4]).mean()))
