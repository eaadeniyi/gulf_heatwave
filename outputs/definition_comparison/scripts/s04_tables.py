"""
=============================================================================
s04  --  THE EIGHT REQUIRED TABLES (and the support tables the figures read).
=============================================================================
Every number in this package is computed here and written to tables/. The
figure scripts read these files and do no analysis of their own, so a figure
and its table can never disagree.

THE EIGHT
  1  table1_definition_registry.csv          one row per definition, incl. the
                                             two UNTESTED cells, with status
  2  table2_run_qa_summary.csv               one row per run (16 x 4), QA level
  3  master_county_year_summary.csv          (written by s02) county x year x run
  4  master_county_month_summary.csv         (written by s02) county x month x run
  5  master_event_table.csv.gz               (written by s02) one row per event
  6  table6_definition_pair_agreement.csv    every run pair: shared / A-only /
                                             B-only county-dates, Jaccard, and
                                             county-rank Spearman
  7  table7_matched_pair_marginal_effects.csv   single-axis pairs only,
     table7b_marginal_effects_summary.csv       + the axis-level summary with
                                                the matched-pair count
  8  table8a_long_event_audit.csv            every event >= the prespecified
                                             review length, never deleted
     table8b_county_data_quality.csv         per-county imputation and flags

SUPPORT TABLES (read by the figures)
  support_jaccard_matrix_primary.csv        16 x 16 at the primary window
  support_county_rank_spearman_all.csv      16 x 16 Spearman, all counties
  support_county_rank_spearman_complete.csv 16 x 16 Spearman, complete-data only
  support_monthly_rate_by_definition.csv    heatwave days per 1,000 eligible
                                            county-days, by definition x month
  support_window_sensitivity.csv            each definition vs the primary window
  support_pair_disagreement_*.csv           per-county disagreement for the
                                            prespecified pairs
  support_pair_days_*_only.csv.gz           the A-only / B-only county-date lists

UNIT DISCIPLINE
  Column names carry the unit. Anything pooled across counties is suffixed
  _QA_pooled and is never used as a substantive result. Cumulative 2015-2025
  counts are named _2015_2025, never "annual". Event durations are integers.
=============================================================================
"""
import os
import sys
import json
import time
import itertools
import datetime

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defcmp_config as K
import defcmp_common as U
import config as C

STATE = K.STATE
N_YEARS = C.ANALYSIS_YEARS[1] - C.ANALYSIS_YEARS[0] + 1


# =============================================================================
# TABLE 1 -- the definition registry
# =============================================================================
def table1_registry(avail_ids):
    rows = []
    for d in K.definitions_expanded():
        windows_have = [w for w in K.WINDOW_ORDER
                        if "%s__%s" % (d["definition_id"], w) in avail_ids]
        rows.append({
            "def_number": d["def_number"], "definition_id": d["definition_id"],
            "definition_sentence": C.definition_sentence(d["metric"], d["percentile"],
                                                         d["min_duration"]),
            "metric": d["metric_code"], "metric_label": d["metric_label"],
            "percentile": d["percentile"], "minimum_duration_days": d["min_duration"],
            "round": "previous (published)" if d["source"] == "published_round1" else "current grid",
            "windows_available": ",".join(windows_have),
            "n_windows_available": len(windows_have),
            "reference_method": C.BASELINE_SCHEME, "comparison_op": C.COMPARISON_OP,
            "season_rule": C.SEASON, "absolute_floor": "none",
            "artifact_handling": d["artifact_handling"],
            "analysis_years": "%d-%d" % C.ANALYSIS_YEARS,
            "input_comparability": ("same input file and hash, same county boundaries, same "
                                    "IDW gap-filling, same walk-forward baseline, same strict "
                                    "'>' operator, same year-round season, no floor"),
            "provenance_note": ("re-run on the current code path; reproduces the published "
                                "outputs exactly (qa/s01_legacy_rerun_verification.csv)"
                                if d["rerun_required"] else
                                "produced by the current code path in the definition grid"),
            "status": "tested" if len(windows_have) == 4 else
                      ("partially tested (%d/4 windows)" % len(windows_have)
                       if windows_have else "NOT RUN"),
        })
    for u in K.UNTESTED_CELLS:
        rows.append({
            "def_number": "", "definition_id": u["definition_id"],
            "definition_sentence": C.definition_sentence(u["metric"], u["percentile"],
                                                         u["min_duration"]),
            "metric": C.METRICS[u["metric"]]["code"],
            "metric_label": C.METRICS[u["metric"]]["label"],
            "percentile": u["percentile"], "minimum_duration_days": u["min_duration"],
            "round": "never run", "windows_available": "", "n_windows_available": 0,
            "reference_method": "", "comparison_op": "", "season_rule": "",
            "absolute_floor": "", "artifact_handling": "",
            "analysis_years": "", "input_comparability": "n/a - never run",
            "provenance_note": u["note"],
            "status": "NOT TESTED",
        })
    df = pd.DataFrame(rows)
    df.insert(0, "state", STATE)
    df.to_csv(os.path.join(K.DIR_TABLES, "table1_definition_registry.csv"), index=False)
    K.log("[table 1] definition registry: %d definitions + %d untested cells"
          % (len(K.DEFINITIONS), len(K.UNTESTED_CELLS)))
    return df


# =============================================================================
# TABLE 2 -- run-level QA summary
# =============================================================================
def table2_run_qa(runs, avail_ids, cy, cm, ev, el, ref):
    all_counties = sorted(ref["county_fips"].unique())
    rows = []
    for r in runs:
        if r["run_id"] not in avail_ids:
            continue
        c = cy[cy["run_id"] == r["run_id"]]
        e = ev[ev["run_id"] == r["run_id"]]
        m = cm[cm["run_id"] == r["run_id"]]
        per_county = (c.groupby("county_fips")["heatwave_days"].sum()
                      .reindex(all_counties, fill_value=0))
        elig = el[(el["metric"] == r["metric_code"]) & (el["window"] == r["window_key"])]
        elig_total = int(elig["eligible_days"].sum())
        dur = e["event_duration_days"]
        month_days = m.groupby("month")["heatwave_days"].sum().reindex(range(1, 13), fill_value=0)
        month_elig = elig.groupby("month")["eligible_days"].sum().reindex(range(1, 13))
        jun_sep_rate = (1000.0 * month_days.loc[K.JUN_SEP].sum() / month_elig.loc[K.JUN_SEP].sum())
        other = [x for x in range(1, 13) if x not in K.JUN_SEP]
        other_rate = 1000.0 * month_days.loc[other].sum() / month_elig.loc[other].sum()
        # provenance for this run, from the pipeline's own log
        rows.append({
            "state": STATE, "run_id": r["run_id"], "definition_id": r["definition_id"],
            "def_number": r["def_number"], "metric": r["metric_code"],
            "percentile": r["percentile"], "minimum_duration_days": r["min_duration"],
            "window": r["window_key"], "window_label": r["window_label"],
            "counties_total": len(all_counties),
            "counties_with_any_heatwave_day": int((per_county > 0).sum()),
            "counties_with_zero_heatwave_days": int((per_county == 0).sum()),
            "eligible_county_days_QA_pooled": elig_total,
            "heatwave_days_QA_pooled_2015_2025": int(c["heatwave_days"].sum()),
            "heatwave_events_QA_pooled_2015_2025": int(len(e)),
            "heatwave_days_per_1000_eligible_QA_pooled": round(
                1000.0 * c["heatwave_days"].sum() / elig_total, 2) if elig_total else np.nan,
            "per_county_heatwave_days_2015_2025_median": float(per_county.median()),
            "per_county_heatwave_days_2015_2025_q25": float(per_county.quantile(0.25)),
            "per_county_heatwave_days_2015_2025_q75": float(per_county.quantile(0.75)),
            "per_county_heatwave_days_2015_2025_min": int(per_county.min()),
            "per_county_heatwave_days_2015_2025_max": int(per_county.max()),
            "event_duration_days_median": float(dur.median()) if len(dur) else np.nan,
            "event_duration_days_q75": float(dur.quantile(0.75)) if len(dur) else np.nan,
            "event_duration_days_max": int(dur.max()) if len(dur) else 0,
            "events_of_2_days": int((dur == 2).sum()), "events_of_3_days": int((dur == 3).sum()),
            "events_7_days_or_more": int((dur >= 7).sum()),
            "events_at_or_over_review_length": int((dur >= K.LONG_EVENT_REVIEW_DAYS).sum()),
            "events_crossing_a_month_boundary": int(e["event_crosses_month"].sum()) if len(e) else 0,
            "events_crossing_a_year_boundary": int(e["event_crosses_year"].sum()) if len(e) else 0,
            "rate_jun_sep_per_1000_eligible": round(jun_sep_rate, 2),
            "rate_oct_may_per_1000_eligible": round(other_rate, 2),
            "pct_heatwave_days_in_jun_sep": round(
                100.0 * month_days.loc[K.JUN_SEP].sum() / month_days.sum(), 2)
            if month_days.sum() else np.nan,
            "peak_month_by_rate": K.MONTH_ABBR[int((1000 * month_days / month_elig).idxmax()) - 1],
            "heatwave_days_imputed_QA_pooled": int(c["heatwave_days_imputed"].sum()),
            "pct_heatwave_days_imputed": round(
                100.0 * c["heatwave_days_imputed"].sum() / c["heatwave_days"].sum(), 2)
            if c["heatwave_days"].sum() else np.nan,
            "artifact_county_days_excluded": int(elig["artifact_excluded_days"].sum()),
            "reference_method": C.BASELINE_SCHEME, "season_rule": C.SEASON,
            "absolute_floor": "none", "comparison_op": C.COMPARISON_OP,
        })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(K.DIR_TABLES, "table2_run_qa_summary.csv"), index=False)
    K.log("[table 2] run-level QA summary: %d runs" % len(df))
    return df


# =============================================================================
# TABLE 6 -- pairwise agreement, every run pair
# =============================================================================
def table6_pair_agreement(runs, sets, cy, ref):
    meta = {r["run_id"]: r for r in runs}
    ids = [r["run_id"] for r in runs if r["run_id"] in sets]
    # per-county totals per run, for the rank correlation column
    piv = (cy.pivot_table(index="county_fips", columns="run_id", values="heatwave_days",
                          aggfunc="sum")
           .reindex(sorted(ref["county_fips"].unique())).fillna(0))
    rows = []
    for a, b in itertools.combinations(ids, 2):
        sa, sb = sets[a], sets[b]
        inter = np.intersect1d(sa, sb, assume_unique=True).size
        union = sa.size + sb.size - inter
        ra, rb = meta[a], meta[b]
        diffs = U.axes_differing(ra, rb)
        rho = (piv[a].corr(piv[b], method="spearman")
               if a in piv.columns and b in piv.columns else np.nan)
        rows.append({
            "run_a": a, "run_b": b,
            "definition_a": ra["definition_id"], "definition_b": rb["definition_id"],
            "window_a": ra["window_key"], "window_b": rb["window_key"],
            "n_axes_differing": len(diffs),
            "axes_differing": "+".join(sorted(diffs)) if diffs else "none",
            "single_axis": diffs[0] if len(diffs) == 1 else "",
            "heatwave_days_a_QA_pooled": int(sa.size),
            "heatwave_days_b_QA_pooled": int(sb.size),
            "county_dates_shared": int(inter),
            "county_dates_a_only": int(sa.size - inter),
            "county_dates_b_only": int(sb.size - inter),
            "jaccard_day_level": round(inter / union, 4) if union else np.nan,
            "dice_day_level": round(2 * inter / (sa.size + sb.size), 4) if (sa.size + sb.size) else np.nan,
            "pct_of_a_also_in_b": round(100 * inter / sa.size, 2) if sa.size else np.nan,
            "pct_of_b_also_in_a": round(100 * inter / sb.size, 2) if sb.size else np.nan,
            "count_ratio_b_over_a": round(sb.size / sa.size, 4) if sa.size else np.nan,
            "county_rank_spearman": round(float(rho), 4) if pd.notna(rho) else np.nan,
        })
    df = pd.DataFrame(rows).sort_values(["n_axes_differing", "jaccard_day_level"])
    df.insert(0, "state", STATE)
    df.to_csv(os.path.join(K.DIR_TABLES, "table6_definition_pair_agreement.csv"), index=False)
    K.log("[table 6] pair agreement: %d pairs (%d single-axis)"
          % (len(df), int((df["n_axes_differing"] == 1).sum())))
    return df


# =============================================================================
# TABLE 7 -- marginal effects, matched pairs only
# =============================================================================
def table7_marginal_effects(pairs, agree, qa):
    """One row per matched pair, plus an axis-level summary.

    Only pairs differing on EXACTLY ONE axis are used, so the effect attributed
    to an axis cannot be contaminated by another axis moving at the same time.
    Direction is reported from the lower-count run to the higher-count run, but
    the CONTRAST LABEL is canonical (sorted), so one contrast never splits into
    two rows depending on which side happened to count more days.
    """
    a = agree[agree["n_axes_differing"] == 1].copy()
    q = qa.set_index("run_id")
    rows = []
    for _, p in a.iterrows():
        ra, rb = p["run_a"], p["run_b"]
        if ra not in q.index or rb not in q.index:
            continue
        axis = p["single_axis"]
        da = int(q.loc[ra, "heatwave_days_QA_pooled_2015_2025"])
        db = int(q.loc[rb, "heatwave_days_QA_pooled_2015_2025"])
        field = {"metric": "metric", "percentile": "percentile",
                 "duration": "minimum_duration_days", "window": "window"}[axis]
        va, vb = q.loc[ra, field], q.loc[rb, field]
        (lo_run, lo_days, lo_val), (hi_run, hi_days, hi_val) = sorted(
            [(ra, da, va), (rb, db, vb)], key=lambda t: t[1])
        rows.append({
            "axis": axis,
            "contrast": " vs ".join(sorted([str(va), str(vb)])),
            "from_run": lo_run, "to_run": hi_run,
            "from_value": lo_val, "to_value": hi_val,
            "metric_held": p["definition_a"].split("_")[0] if axis != "metric" else "",
            "window_held": p["window_a"] if axis != "window" else "",
            "heatwave_days_from_QA_pooled": lo_days, "heatwave_days_to_QA_pooled": hi_days,
            "count_ratio_hi_over_lo": round(hi_days / lo_days, 4) if lo_days else np.nan,
            "pct_count_difference": round(100.0 * (hi_days - lo_days) / lo_days, 2)
            if lo_days else np.nan,
            "jaccard_day_level": p["jaccard_day_level"],
            "county_dates_shared": p["county_dates_shared"],
            "county_dates_disagreeing": int(p["county_dates_a_only"] + p["county_dates_b_only"]),
            "county_rank_spearman": p["county_rank_spearman"],
        })
    df = pd.DataFrame(rows)
    df.insert(0, "state", STATE)
    df.to_csv(os.path.join(K.DIR_TABLES, "table7_matched_pair_marginal_effects.csv"), index=False)

    s = df.groupby("axis").agg(
        n_matched_pairs=("jaccard_day_level", "size"),
        jaccard_median=("jaccard_day_level", "median"),
        jaccard_min=("jaccard_day_level", "min"),
        jaccard_max=("jaccard_day_level", "max"),
        count_ratio_median=("count_ratio_hi_over_lo", "median"),
        count_ratio_min=("count_ratio_hi_over_lo", "min"),
        count_ratio_max=("count_ratio_hi_over_lo", "max"),
        rank_spearman_median=("county_rank_spearman", "median"),
    ).reset_index().sort_values("jaccard_median")
    for c in s.columns:
        if s[c].dtype.kind == "f":
            s[c] = s[c].round(4)
    s["interpretation"] = [
        "lower Jaccard = this axis changes WHICH county-dates are classified more; "
        "count ratio far from 1 = it changes HOW MANY"] * len(s)
    s.to_csv(os.path.join(K.DIR_TABLES, "table7b_marginal_effects_summary.csv"), index=False)
    K.log("[table 7] marginal effects: %d matched pairs across %d axes"
          % (len(df), s["axis"].nunique()))
    K.log(s[["axis", "n_matched_pairs", "jaccard_median", "count_ratio_median"]]
          .to_string(index=False))
    return df, s


# =============================================================================
# TABLE 8 -- long events and data quality
# =============================================================================
def table8_audit(ev, ref, el):
    long_ev = ev[ev["event_duration_days"] >= K.LONG_EVENT_REVIEW_DAYS].copy()
    long_ev = long_ev.merge(
        ref[["county_fips", "county_name", "climate_division", "climdiv_id",
             "temperature_imputation_pct", "fully_imputed_county", "data_complete"]]
        .rename(columns={"county_name": "county_name_ref"}), on="county_fips", how="left")
    long_ev["pct_event_days_imputed"] = (
        100.0 * long_ev["imputed_days_in_event"] / long_ev["days_in_event"]).round(1)
    long_ev["months_touched"] = (
        pd.to_datetime(long_ev["end_date"]).dt.to_period("M").astype("int64")
        - pd.to_datetime(long_ev["start_date"]).dt.to_period("M").astype("int64") + 1)
    long_ev["review_reason"] = np.where(
        long_ev["pct_event_days_imputed"] >= 50, "long event AND >=50% imputed days",
        np.where(long_ev["fully_imputed_county"], "long event in a fully imputed county",
                 "long event"))
    long_ev["disposition"] = "RETAINED - flagged for review, not deleted"
    cols = ["state", "run_id", "definition_id", "metric", "percentile", "minimum_duration",
            "window", "event_id", "county_fips", "county_name", "climate_division",
            "start_date", "end_date", "event_duration_days", "months_touched",
            "event_crosses_month", "event_crosses_year", "peak_day_date",
            "peak_metric_value", "peak_day_threshold_value", "days_in_event",
            "imputed_days_in_event", "pct_event_days_imputed",
            "temperature_imputation_pct", "fully_imputed_county", "data_complete",
            "review_reason", "disposition"]
    long_ev = long_ev[cols].sort_values(["event_duration_days", "run_id"], ascending=[False, True])
    long_ev.to_csv(os.path.join(K.DIR_TABLES, "table8a_long_event_audit.csv"), index=False)
    K.log("[table 8a] long-event audit: %d events >= %d days (across %d runs); NONE deleted"
          % (len(long_ev), K.LONG_EVENT_REVIEW_DAYS, long_ev["run_id"].nunique()))

    dq = ref.copy()
    dq["imputation_band"] = pd.cut(dq["temperature_imputation_pct"],
                                   [-0.01, 0, 5, 10, 25, 50, 99.99, 100.01],
                                   labels=["0% (fully native)", ">0-5%", ">5-10%", ">10-25%",
                                           ">25-50%", ">50-<100%", "100% (fully imputed)"])
    art = el.groupby("county_fips")["artifact_excluded_days"].max().rename(
        "artifact_excluded_days_max_per_metric_window")
    dq = dq.merge(art, left_on="county_fips", right_index=True, how="left")
    dq["flag_exclude_from_county_ranking"] = ~dq["data_complete"]
    dq["flag_reason"] = np.where(
        dq["fully_imputed_county"], "temperature 100% IDW-imputed - no native station data",
        np.where(~dq["data_complete"],
                 "temperature imputation above the prespecified %.0f%% cut" % K.IMPUTATION_MAX_PCT,
                 ""))
    keep = ["county_fips", "county_name", "climate_division", "climdiv_id", "analysis_days",
            "temp_imputed_days", "temperature_imputation_pct", "imputation_band",
            "native_analysis_days", "fully_imputed_county", "data_complete",
            "artifact_excluded_days_max_per_metric_window",
            "flag_exclude_from_county_ranking", "flag_reason"]
    dq = dq[[c for c in keep if c in dq.columns]]
    dq.insert(0, "state", STATE)
    dq.to_csv(os.path.join(K.DIR_TABLES, "table8b_county_data_quality.csv"), index=False)
    K.log("[table 8b] county data quality: %d counties, %d flagged, %d fully imputed"
          % (len(dq), int(dq["flag_exclude_from_county_ranking"].sum()),
             int(dq["fully_imputed_county"].sum())))
    return long_ev, dq


# =============================================================================
# SUPPORT TABLES for the figures
# =============================================================================
def support_matrices(runs, sets, cy, ref):
    """16 x 16 day-level agreement and county-rank correlation at the primary window."""
    prim = [r for r in runs if r["window_key"] == K.PRIMARY_WINDOW]
    order = K.def_order()
    ids = ["%s__%s" % (d, K.PRIMARY_WINDOW) for d in order]
    ids = [i for i in ids if i in sets]
    J = U.jaccard_matrix(sets, ids)
    J.index = J.columns = [i.split("__")[0] for i in ids]
    J.to_csv(os.path.join(K.DIR_TABLES, "support_jaccard_matrix_primary.csv"))

    piv = cy[cy["window"] == K.PRIMARY_WINDOW].pivot_table(
        index="county_fips", columns="definition_id", values="heatwave_days", aggfunc="sum")
    piv = piv.reindex(sorted(ref["county_fips"].unique())).fillna(0)
    piv = piv[[c for c in order if c in piv.columns]]
    S_all = piv.corr(method="spearman")
    S_all.to_csv(os.path.join(K.DIR_TABLES, "support_county_rank_spearman_all.csv"))
    complete = ref.loc[ref["data_complete"], "county_fips"]
    S_cmp = piv.loc[piv.index.isin(complete)].corr(method="spearman")
    S_cmp.to_csv(os.path.join(K.DIR_TABLES, "support_county_rank_spearman_complete.csv"))
    K.log("[support] %dx%d Jaccard; Spearman on %d counties (all) and %d (complete data)"
          % (J.shape[0], J.shape[1], len(piv), int(piv.index.isin(complete).sum())))
    return J, S_all, S_cmp


def support_monthly_rates(cm, el):
    """Heatwave days per 1,000 ELIGIBLE county-days, by definition x window x month.

    A rate, not a share of all heatwave days: a share cannot distinguish "December
    has many heatwave days" from "December has many days".
    """
    d = cm.groupby(["definition_id", "metric", "percentile", "minimum_duration",
                    "window", "month"], as_index=False)["heatwave_days"].sum()
    e = el.groupby(["metric", "window", "month"], as_index=False)["eligible_days"].sum()
    out = d.merge(e, on=["metric", "window", "month"], how="left")
    out["heatwave_days_per_1000_eligible_county_days"] = (
        1000.0 * out["heatwave_days"] / out["eligible_days"]).round(3)
    out["month_share_pct_of_all_heatwave_days"] = out.groupby(
        ["definition_id", "window"])["heatwave_days"].transform(lambda s: (100 * s / s.sum()).round(2))
    out["is_jun_sep"] = out["month"].isin(K.JUN_SEP)
    out.to_csv(os.path.join(K.DIR_TABLES, "support_monthly_rate_by_definition.csv"), index=False)
    K.log("[support] monthly rates: %d definition x window x month rows" % len(out))
    return out


def support_window_sensitivity(runs, sets, cy):
    """Every definition against its own PRIMARY-window run: day-level agreement,
    and the paired county-year count difference (paired on county x year)."""
    rows = []
    cyi = cy.set_index(["run_id", "county_fips", "year"])["heatwave_days"]
    for d in K.def_order():
        base_id = "%s__%s" % (d, K.PRIMARY_WINDOW)
        if base_id not in sets:
            continue
        base_cy = cy[cy["run_id"] == base_id][["county_fips", "year", "heatwave_days"]]
        for w in K.WINDOW_ORDER:
            rid = "%s__%s" % (d, w)
            if rid not in sets:
                continue
            j = U.jaccard(sets[base_id], sets[rid])
            other = cy[cy["run_id"] == rid][["county_fips", "year", "heatwave_days"]]
            mg = base_cy.merge(other, on=["county_fips", "year"], how="outer",
                               suffixes=("_primary", "_this")).fillna(0)
            diff = mg["heatwave_days_this"] - mg["heatwave_days_primary"]
            rows.append({
                "definition_id": d, "window": w, "primary_window": K.PRIMARY_WINDOW,
                "is_primary": w == K.PRIMARY_WINDOW,
                "jaccard_vs_primary": round(j, 4),
                "heatwave_days_QA_pooled": int(sets[rid].size),
                "count_ratio_vs_primary": round(sets[rid].size / sets[base_id].size, 4),
                "n_paired_county_years": int(len(mg)),
                "paired_diff_median": float(diff.median()),
                "paired_diff_q25": float(diff.quantile(0.25)),
                "paired_diff_q75": float(diff.quantile(0.75)),
                "paired_diff_min": float(diff.min()), "paired_diff_max": float(diff.max()),
                "pct_county_years_higher": round(100.0 * (diff > 0).mean(), 1),
                "pct_county_years_lower": round(100.0 * (diff < 0).mean(), 1),
            })
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(K.DIR_TABLES, "support_window_sensitivity.csv"), index=False)
    K.log("[support] window sensitivity: %d definition x window rows" % len(out))
    return out


def support_pair_disagreement(sets, ref, cm):
    """For each prespecified pair: per-county and per-month disagreement, plus the
    explicit A-only / B-only county-date lists."""
    out_rows = []
    for spec in K.DISAGREEMENT_PAIRS:
        wa = spec.get("window_a") or spec["window"]
        wb = spec.get("window_b") or spec["window"]
        ida = "%s__%s" % (spec["a"], wa)
        idb = "%s__%s" % (spec["b"], wb)
        if ida not in sets or idb not in sets:
            continue
        A = pd.read_csv(K.canonical_path(spec["a"], wa),
                        usecols=["county_fips", "date", "heatwave_day_flag"],
                        dtype={"county_fips": str})
        B = pd.read_csv(K.canonical_path(spec["b"], wb),
                        usecols=["county_fips", "date", "heatwave_day_flag"],
                        dtype={"county_fips": str})
        A = A[A["heatwave_day_flag"] == 1][["county_fips", "date"]]
        B = B[B["heatwave_day_flag"] == 1][["county_fips", "date"]]
        m = A.merge(B, on=["county_fips", "date"], how="outer", indicator=True)
        m["month"] = pd.to_datetime(m["date"]).dt.month
        m["status"] = m["_merge"].map({"left_only": "a_only", "right_only": "b_only",
                                       "both": "shared"})
        tag = "%s_%s_vs_%s_%s" % (spec["a"], wa, spec["b"], wb)

        per_county = (m.pivot_table(index="county_fips", columns="status", values="date",
                                    aggfunc="size").fillna(0).astype(int)
                      .reindex(sorted(ref["county_fips"].unique()), fill_value=0))
        for c in ("a_only", "b_only", "shared"):
            if c not in per_county.columns:
                per_county[c] = 0
        per_county["total_classified_by_either"] = per_county[["a_only", "b_only", "shared"]].sum(axis=1)
        per_county["disagreement_rate_pct"] = (
            100.0 * (per_county["a_only"] + per_county["b_only"])
            / per_county["total_classified_by_either"].replace(0, np.nan)).round(2)
        per_county = per_county.reset_index().merge(
            ref[["county_fips", "county_name", "climate_division",
                 "temperature_imputation_pct", "fully_imputed_county", "data_complete"]],
            on="county_fips", how="left")
        per_county.insert(0, "pair", tag)
        per_county.to_csv(os.path.join(K.DIR_TABLES,
                                       "support_pair_disagreement_%s.csv" % tag), index=False)

        per_month = (m.groupby(["month", "status"]).size().unstack(fill_value=0)
                     .reindex(range(1, 13), fill_value=0))
        for c in ("a_only", "b_only", "shared"):
            if c not in per_month.columns:
                per_month[c] = 0
        per_month["disagreement_rate_pct"] = (
            100.0 * (per_month["a_only"] + per_month["b_only"])
            / per_month[["a_only", "b_only", "shared"]].sum(axis=1).replace(0, np.nan)).round(2)
        per_month = per_month.reset_index().rename(columns={"index": "month"})
        per_month.insert(0, "pair", tag)
        per_month.to_csv(os.path.join(K.DIR_TABLES,
                                      "support_pair_disagreement_by_month_%s.csv" % tag),
                         index=False)

        # the explicit county-date lists, one file per side
        for side, status in (("a_only", "a_only"), ("b_only", "b_only")):
            sub = m.loc[m["status"] == status, ["county_fips", "date"]].copy()
            sub = sub.merge(ref[["county_fips", "county_name", "climate_division"]],
                            on="county_fips", how="left")
            sub.insert(0, "pair", tag)
            sub.insert(1, "classified_only_by",
                       spec["a"] + "__" + wa if side == "a_only" else spec["b"] + "__" + wb)
            sub.sort_values(["county_fips", "date"]).to_csv(
                os.path.join(K.DIR_TABLES, "support_pair_days_%s_%s.csv.gz" % (tag, side)),
                index=False, compression="gzip")

        n_a = int((m["status"] == "a_only").sum())
        n_b = int((m["status"] == "b_only").sum())
        n_s = int((m["status"] == "shared").sum())
        out_rows.append({"pair": tag, "axis": spec["axis"], "rationale": spec["rationale"],
                         "run_a": ida, "run_b": idb,
                         "county_dates_a_only": n_a, "county_dates_b_only": n_b,
                         "county_dates_shared": n_s,
                         "jaccard_day_level": round(n_s / (n_s + n_a + n_b), 4),
                         "disagreement_rate_pct": round(100.0 * (n_a + n_b) / (n_s + n_a + n_b), 2),
                         "counties_with_any_disagreement":
                             int((per_county["a_only"] + per_county["b_only"] > 0).sum())})
        K.log("[support] pair %-46s jaccard=%.3f  a-only=%s b-only=%s"
              % (tag, n_s / (n_s + n_a + n_b), "{:,}".format(n_a), "{:,}".format(n_b)))
    idx = pd.DataFrame(out_rows)
    idx.to_csv(os.path.join(K.DIR_TABLES, "support_pair_disagreement_index.csv"), index=False)
    return idx


def support_example_counties(ref, cy):
    """The example counties used by the time-series and threshold-curve figures.

    THE RULE, fixed in advance and applied mechanically: one county per NOAA
    climate division; within a division take the county with the LOWEST
    temperature-imputation percentage, breaking ties on the lowest FIPS code.
    Selection uses only climate region and data completeness -- never heatwave
    counts, rankings or event lengths -- so the examples cannot be cherry-picked.
    """
    r = ref.sort_values(["climdiv_id", "temperature_imputation_pct", "county_fips"])
    pick = r.groupby("climdiv_id", as_index=False).first()
    pick["selection_rule"] = ("lowest temperature-imputation % within the climate division, "
                             "ties broken by lowest FIPS")
    # for context only, never used to select
    tot = (cy[cy["window"] == K.PRIMARY_WINDOW]
           .groupby("county_fips")["heatwave_days"].sum().rename("heatwave_days_all_defs_context"))
    pick = pick.merge(tot, left_on="county_fips", right_index=True, how="left")
    cols = ["climdiv_id", "climate_division", "county_fips", "county_name",
            "temperature_imputation_pct", "fully_imputed_county", "data_complete",
            "selection_rule", "heatwave_days_all_defs_context"]
    pick = pick[cols].sort_values("climdiv_id")
    pick.to_csv(os.path.join(K.DIR_TABLES, "support_example_counties.csv"), index=False)
    K.log("[support] example counties: %d (one per climate division), imputation %.1f-%.1f%%"
          % (len(pick), pick["temperature_imputation_pct"].min(),
             pick["temperature_imputation_pct"].max()))
    return pick


# =============================================================================
# driver
# =============================================================================
def main():
    K.ensure_dirs()
    t0 = time.time()
    runs = K.runs_expanded()
    avail = U.available_runs(runs)
    avail_ids = {r["run_id"] for r in avail}
    K.log("=" * 74)
    K.log("s04  TABLES  --  %d of %d runs available" % (len(avail_ids), len(runs)))
    K.log("=" * 74)

    ref = U.read_reference()
    cy = U.read_master_county_year()
    cm = U.read_master_county_month()
    ev = U.read_master_events()
    el = U.read_eligibility()

    table1_registry(avail_ids)
    qa = table2_run_qa(runs, avail_ids, cy, cm, ev, el, ref)

    K.log("-" * 74)
    K.log("loading day-level sets (the identity of the classified county-dates)")
    sets = U.load_day_sets(avail, verbose=False)
    K.log("   %d run sets, %s county-dates in total"
          % (len(sets), "{:,}".format(sum(len(v) for v in sets.values()))))

    agree = table6_pair_agreement(runs, sets, cy, ref)
    pairs = U.matched_pairs(runs, only_available=avail_ids)
    table7_marginal_effects(pairs, agree, qa)
    table8_audit(ev, ref, el)

    K.log("-" * 74)
    support_matrices(runs, sets, cy, ref)
    support_monthly_rates(cm, el)
    support_window_sensitivity(runs, sets, cy)
    support_pair_disagreement(sets, ref, cm)
    support_example_counties(ref, cy)

    # a small index so the eight required tables are findable by number
    with open(os.path.join(K.DIR_TABLES, "TABLE_INDEX.md"), "w", encoding="utf-8") as f:
        f.write("# Required tables - index\n\n")
        f.write("| # | table | file | unit of analysis |\n|---|---|---|---|\n")
        for n, name, fn, unit in [
            (1, "Definition registry", "table1_definition_registry.csv",
             "one definition (16 tested + 2 untested)"),
            (2, "Run-level QA summary", "table2_run_qa_summary.csv",
             "one run = definition x window (64); pooled fields labelled _QA_pooled"),
            (3, "County-year summary", "master_county_year_summary.csv",
             "county x year x run"),
            (4, "County-month summary", "master_county_month_summary.csv",
             "county x year x month x run"),
            (5, "Individual-event table", "master_event_table.csv.gz",
             "one heatwave event (integer duration)"),
            (6, "Definition-pair agreement", "table6_definition_pair_agreement.csv",
             "one pair of runs; day-level sets of county-dates"),
            (7, "Matched-pair marginal effects", "table7_matched_pair_marginal_effects.csv "
                "+ table7b_marginal_effects_summary.csv",
             "one matched pair (single axis differing); summary reports n pairs per axis"),
            (8, "Long-event and data-quality audit", "table8a_long_event_audit.csv "
                "+ table8b_county_data_quality.csv",
             "one event >= %d days; one county" % K.LONG_EVENT_REVIEW_DAYS)]:
            f.write("| %d | %s | `%s` | %s |\n" % (n, name, fn, unit))
        f.write("\nTables 3-5 are written by `s02_canonical_long.py` (they are the "
                "aggregation levels of the canonical long table); tables 1, 2, 6, 7 and 8 "
                "by `s04_tables.py`. Support tables read by the figures are prefixed "
                "`support_`.\n")
    K.log("=" * 74)
    K.log("s04 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
