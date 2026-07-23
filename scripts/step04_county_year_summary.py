"""
STEP 20 (spec Part H): county-year annual summary metrics.

REVISION 2 (2026-07-16, second external review):
  - R2 Issue 1 (BLOCKING): warm-season prevalence now uses the IN-SEASON valid
    denominator (Jun-Sep valid days), not the full-year count. Both denominators
    and two explicitly-labeled percentages are reported.
  - R2 Issue 3: a county-year summary is produced for EVERY scenario (primary +
    3 sensitivities), each reading its own scenario daily-classification file,
    so annual counts / rankings / trends are comparable across definitions.
  - R2 Issue 2A: definition metadata carried onto every summary row.

For each scenario the "season" metadata field decides the prevalence
denominator: year-round scenarios use valid days across the whole year;
the warm-season scenario uses valid Jun-Sep days only.

Output: tables/09_county_year_summary_<scenario>.csv  (one per scenario)
"""
import os
import numpy as np
import pandas as pd

ROOT = r"C:\Users\eadeni1\OneDrive - Louisiana State University\Documents\doc\heatWaveUS"
PILOT = os.path.join(ROOT, "texas_heatwave_pilot")
TAB = os.path.join(PILOT, "tables")
EV = os.path.join(TAB, "events")
HI_COL = "derived_tmax_rhmin_hi_proxy_f"
WARM_MONTHS = [6, 7, 8, 9]
META_COLS = ["definition_id", "construct_label", "metric", "reference_method",
             "season", "floor_variable", "floor_value", "minimum_duration", "comparison_operator"]


def log(*a):
    print(*a, flush=True)


def summarize(daily, events, scenario_tag):
    """One row per county-year. Denominator rule keyed off the scenario's
    'season' metadata: 'jun_sep' -> in-season valid days; else full-year."""
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    season = daily["season"].iloc[0] if "season" in daily.columns and len(daily) else "year_round"
    events = events.copy()
    if len(events):
        events["event_start_year"] = pd.to_datetime(events["event_start_date"]).dt.year

    rows = []
    for (fips, year), g in daily.groupby(["county_fips", "year"]):
        g_inseason = g[g["month"].isin(WARM_MONTHS)]
        valid_full = g[g["candidate_day_flag"].notna()]
        valid_inseason = g_inseason[g_inseason["candidate_day_flag"].notna()]
        n_valid_full = len(valid_full)
        n_valid_inseason = len(valid_inseason)
        n_candidate = int(g["candidate_day_flag"].fillna(0).sum())
        n_heatwave = int(g["heatwave_day_flag"].fillna(0).sum())
        # heatwave-days that actually FALL in Jun-Sep (review R3 Issue 2: the in-season
        # percentage must use an in-season NUMERATOR, not the full-year count -- the old
        # code divided full-year hw-days by 122 and produced >100% values).
        n_heatwave_junsep = int(g_inseason["heatwave_day_flag"].fillna(0).sum())
        n_susp_hw = int(((g["heatwave_day_flag"] == 1) & (g["qc_status"] == "suspicious_retain")).sum())
        ev_y = events[(events["county_fips"] == fips) & (events["event_start_year"] == year)] if len(events) else events
        n_events = len(ev_y)
        hw_rows = g[g["heatwave_day_flag"] == 1]
        first_start = hw_rows["date"].min() if len(hw_rows) else pd.NaT
        last_end = hw_rows["date"].max() if len(hw_rows) else pd.NaT
        span = (last_end - first_start).days + 1 if pd.notna(first_start) else 0

        # denominator for the PRIMARY prevalence stat depends on the scenario's season
        if season == "jun_sep":
            primary_denom = n_valid_inseason
        else:
            primary_denom = n_valid_full

        rows.append({
            "county_fips": fips, "county_name": g["county_name"].iloc[0],
            "climate_division": g["climate_division"].iloc[0], "year": year,
            "valid_days_full_year": n_valid_full,
            "valid_days_in_junsep": n_valid_inseason,
            "candidate_exceedance_days": n_candidate,
            "heatwave_days_full_year": n_heatwave,
            "heatwave_days_in_junsep": n_heatwave_junsep,
            "heatwave_days_flagged_suspicious": n_susp_hw,
            "number_of_events": n_events,
            # correctly-matched numerator/denominator percentages (review R3 Issue 2):
            # full-year numerator over full-year denominator; Jun-Sep numerator over
            # Jun-Sep denominator. Neither can exceed 100%.
            "pct_full_year_days_classified": round(100 * n_heatwave / n_valid_full, 2) if n_valid_full else np.nan,
            "pct_junsep_days_classified": round(100 * n_heatwave_junsep / n_valid_inseason, 2) if n_valid_inseason else np.nan,
            "pct_valid_days_heatwave_PRIMARY": round(100 * (n_heatwave_junsep if season == "jun_sep" else n_heatwave) / primary_denom, 2) if primary_denom else np.nan,
            "primary_denominator_basis": "in_season_junsep" if season == "jun_sep" else "full_year",
            "pct_candidate_removed_by_persistence": round(100 * (1 - n_heatwave / n_candidate), 2) if n_candidate else np.nan,
            "mean_event_duration": round(ev_y["event_duration_days"].mean(), 2) if n_events else np.nan,
            "max_event_duration": int(ev_y["event_duration_days"].max()) if n_events else 0,
            "mean_event_peak_hi_proxy": round(ev_y["peak_hi_proxy_f"].mean(), 2) if n_events else np.nan,
            "annual_peak_hi_proxy": round(hw_rows[HI_COL].max(), 2) if len(hw_rows) else np.nan,
            "annual_cumulative_exceedance": round(np.maximum(0, hw_rows["exceedance_f"]).sum(), 2) if len(hw_rows) else 0.0,
            "first_event_start": first_start, "last_event_end": last_end,
            "first_to_last_event_span_days": span,
            "n_events_reaching_hi100": int(ev_y["any_day_hi_ge_100f"].sum()) if n_events else 0,
            "n_events_reaching_hi103": int(ev_y["any_day_hi_ge_103f"].sum()) if n_events else 0,
        })
    out = pd.DataFrame(rows).sort_values(["county_fips", "year"])
    # carry definition metadata onto every row
    for c in META_COLS:
        if c in daily.columns:
            out[c] = daily[c].iloc[0]
    return out


log("=" * 70)
log("STEP 20: county-year summaries -- one per scenario (revised R2 2026-07-16)")
log("=" * 70)

SCENARIOS = ["PRIMARY_yearround_artifactmissing",
             "sensitivity_yearround_retainall",
             "sensitivity_yearround_suspicious_set_missing",
             "sensitivity_warmseason_junsep",
             "sensitivity_yearround_tmaxfloor"]

summaries = {}
for tag in SCENARIOS:
    daily = pd.read_csv(os.path.join(EV, "07_daily_%s.csv" % tag), dtype={"county_fips": str})
    events = pd.read_csv(os.path.join(EV, "08_events_%s.csv" % tag), dtype={"county_fips": str})
    s = summarize(daily, events, tag)
    s.to_csv(os.path.join(TAB, "09_county_year_summary_%s.csv" % tag), index=False)
    summaries[tag] = s
    log("[done] wrote 09_county_year_summary_%s.csv rows=%d" % (tag, len(s)))

# ---- worked-example verification of the R3 in-season-% fix (must be <=100%) ----
sp = summaries["PRIMARY_yearround_artifactmissing"]
for yr in [2017, 2023]:
    r = sp[(sp["county_name"] == "Cameron (Brownsville)") & (sp["year"] == yr)].iloc[0]
    log("[R3 in-season-%% check] Cameron %d PRIMARY (year-round): hw_full=%d hw_junsep=%d valid_junsep=%d"
        % (yr, r["heatwave_days_full_year"], r["heatwave_days_in_junsep"], r["valid_days_in_junsep"]))
    log("    pct_full_year=%.2f%%  pct_junsep=%.2f%%  (must be <=100%%)"
        % (r["pct_full_year_days_classified"], r["pct_junsep_days_classified"]))
# global assertion: no percentage anywhere exceeds 100
for tag, s in summaries.items():
    for col in ["pct_full_year_days_classified", "pct_junsep_days_classified", "pct_valid_days_heatwave_PRIMARY"]:
        mx = s[col].max()
        assert mx <= 100.0001, "%s %s exceeds 100%%: %.2f" % (tag, col, mx)
log("[assert] no pct_* field exceeds 100%% in any scenario summary -- OK")

# ---- side-by-side pooled comparison ----
log("\n[compare] pooled 2015-2025 by county (full-year heatwave-days):")
def pool(s):
    return s.groupby("county_name").agg(hw=("heatwave_days_full_year", "sum"), ev=("number_of_events", "sum")).reset_index()
p1 = pool(summaries["PRIMARY_yearround_artifactmissing"]).rename(columns={"hw": "PRIM_hw", "ev": "PRIM_ev"})
p1b = pool(summaries["sensitivity_yearround_retainall"]).rename(columns={"hw": "RET_hw", "ev": "RET_ev"})
p2 = pool(summaries["sensitivity_yearround_suspicious_set_missing"]).rename(columns={"hw": "SM_hw", "ev": "SM_ev"})
p3 = pool(summaries["sensitivity_warmseason_junsep"]).rename(columns={"hw": "WM_hw", "ev": "WM_ev"})
p4 = pool(summaries["sensitivity_yearround_tmaxfloor"]).rename(columns={"hw": "TM_hw", "ev": "TM_ev"})
comp = p1.merge(p1b, on="county_name").merge(p2, on="county_name").merge(p3, on="county_name").merge(p4, on="county_name")
log(comp.to_string(index=False))
