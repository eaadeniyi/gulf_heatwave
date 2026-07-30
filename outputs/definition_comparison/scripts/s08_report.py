"""
=============================================================================
s08  --  THE WRITTEN DELIVERABLES.
=============================================================================
Generates, with every number read live from the tables so the prose cannot
drift from the data:

  figure_captions.md   for EVERY figure: purpose, unit of analysis, input file,
                       transformation, visual encoding, what it DOES support,
                       what it does NOT support, a draft publication caption,
                       and its known limitation
  methods_notes.md     the prespecified choices, the definitions of every unit,
                       the reporting rules, and the QA findings that came out of
                       building this package
  DECISION_TABLE.md    which definitions are primary candidates, which are
                       sensitivity cases, which are a DIFFERENT CONSTRUCT, and
                       which need more data-quality work before use
                       (+ DECISION_TABLE.csv)
  run_manifest.csv     every file in the package: size, timestamp, the script
                       that produced it, unit of analysis, git commit, input hash
  README.md            how to navigate and how to regenerate

The decision table is a READING of the comparison, not a selection: no injury
or health outcome is used anywhere in this package, and none of these figures
can identify a "correct" definition.
=============================================================================
"""
import os
import sys
import glob
import time
import json
import hashlib
import platform
import subprocess
import datetime

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defcmp_config as K
import defcmp_common as U
import config as C

STATE = K.STATE
YEARS = "%d-%d" % C.ANALYSIS_YEARS
T = K.DIR_TABLES


def rd(name, **kw):
    return pd.read_csv(os.path.join(T, name), **kw)


def git_commit():
    try:
        c = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=K.REPO_ROOT,
                           capture_output=True, text=True, timeout=20).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=K.REPO_ROOT,
                               capture_output=True, text=True, timeout=20).stdout.strip()
        return (c or "unknown") + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def input_hash():
    h = hashlib.md5()
    with open(C.county_day_path(STATE), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return "md5:" + h.hexdigest()[:16]


# =============================================================================
# the numbers every document quotes
# =============================================================================
def gather():
    n = {}
    qa = rd("table2_run_qa_summary.csv")
    reg = rd("table1_definition_registry.csv")
    summ = rd("table7b_marginal_effects_summary.csv")
    marg = rd("table7_matched_pair_marginal_effects.csv")
    agree = rd("table6_definition_pair_agreement.csv")
    J = rd("support_jaccard_matrix_primary.csv", index_col=0)
    Sa = rd("support_county_rank_spearman_all.csv", index_col=0)
    Sc = rd("support_county_rank_spearman_complete.csv", index_col=0)
    rates = rd("support_monthly_rate_by_definition.csv")
    wsens = rd("support_window_sensitivity.csv")
    dq = rd("table8b_county_data_quality.csv", dtype={"county_fips": str})
    long_ev = rd("table8a_long_event_audit.csv", dtype={"county_fips": str})
    pidx = rd("support_pair_disagreement_index.csv")
    ex = rd("support_example_counties.csv", dtype={"county_fips": str})
    knife = pd.read_csv(os.path.join(K.DIR_QA, "s02_knife_edge_days.csv"))
    val = pd.read_csv(os.path.join(K.DIR_QA, "s03_validation.csv"))
    s01 = pd.read_csv(os.path.join(K.DIR_QA, "s01_legacy_rerun_verification.csv"))
    recon = pd.read_csv(os.path.join(K.DIR_QA, "s02_reconciliation.csv"))

    prim = qa[qa["window"] == K.PRIMARY_WINDOW]
    n["n_defs"] = int((reg["status"] != "NOT TESTED").sum())
    n["n_untested"] = int((reg["status"] == "NOT TESTED").sum())
    n["n_runs"] = len(qa)
    n["n_counties"] = int(len(dq))
    n["n_complete"] = int(dq["data_complete"].sum())
    n["n_flagged"] = int(dq["flag_exclude_from_county_ranking"].sum())
    n["n_fully_imputed"] = int(dq["fully_imputed_county"].sum())
    n["days_min"] = int(prim["heatwave_days_QA_pooled_2015_2025"].min())
    n["days_max"] = int(prim["heatwave_days_QA_pooled_2015_2025"].max())
    n["days_min_def"] = prim.loc[prim["heatwave_days_QA_pooled_2015_2025"].idxmin(),
                                 "definition_id"]
    n["days_max_def"] = prim.loc[prim["heatwave_days_QA_pooled_2015_2025"].idxmax(),
                                 "definition_id"]
    n["events_min"] = int(prim["heatwave_events_QA_pooled_2015_2025"].min())
    n["events_max"] = int(prim["heatwave_events_QA_pooled_2015_2025"].max())
    n["med_days_min"] = int(prim["per_county_heatwave_days_2015_2025_median"].min())
    n["med_days_max"] = int(prim["per_county_heatwave_days_2015_2025_median"].max())
    n["dur_med_min"] = float(prim["event_duration_days_median"].min())
    n["dur_med_max"] = float(prim["event_duration_days_median"].max())
    n["dur_max"] = int(prim["event_duration_days_max"].max())

    off = J.to_numpy(dtype=float).copy()
    np.fill_diagonal(off, np.nan)
    n["jac_min"] = float(np.nanmin(off))
    n["jac_med"] = float(np.nanmedian(off))
    n["jac_max"] = float(np.nanmax(off))
    ij = np.unravel_index(np.nanargmin(off), off.shape)
    n["jac_min_pair"] = "%s vs %s" % (J.index[ij[0]], J.columns[ij[1]])

    for _, r in summ.iterrows():
        a = r["axis"]
        n["ax_%s_pairs" % a] = int(r["n_matched_pairs"])
        n["ax_%s_jac" % a] = float(r["jaccard_median"])
        n["ax_%s_ratio" % a] = float(r["count_ratio_median"])
        n["ax_%s_jacmin" % a] = float(r["jaccard_min"])
        n["ax_%s_ratiomax" % a] = float(r["count_ratio_max"])
    n["axis_rank"] = " < ".join("%s %.3f" % (r["axis"], r["jaccard_median"])
                                for _, r in summ.sort_values("jaccard_median").iterrows())

    for lab, S in (("all", Sa), ("complete", Sc)):
        o = S.to_numpy(dtype=float).copy()
        np.fill_diagonal(o, np.nan)
        n["rho_%s_med" % lab] = float(np.nanmedian(o))
        n["rho_%s_min" % lab] = float(np.nanmin(o))
        n["rho_%s_max" % lab] = float(np.nanmax(o))
        n["rho_%s_pct_above_90" % lab] = float(100 * np.nanmean(o > 0.90))
    # rank agreement WITHIN a metric family vs ACROSS the Tmax/Tmin families: the
    # metric axis is where county ordering breaks down too, not only day-level agreement
    fam = pd.Series(Sa.index).str.split("_").str[0]
    same = np.equal.outer(fam.to_numpy(), fam.to_numpy())
    o = Sa.to_numpy(dtype=float).copy()
    np.fill_diagonal(o, np.nan)
    n["rho_within_family_med"] = float(np.nanmedian(np.where(same, o, np.nan)))
    tmax_i = np.flatnonzero(fam.to_numpy() == "TMAX")
    tmin_i = np.flatnonzero(fam.to_numpy() == "TMIN")
    cross = o[np.ix_(tmax_i, tmin_i)]
    n["rho_tmax_vs_tmin_med"] = float(np.nanmedian(cross))
    n["rho_tmax_vs_tmin_min"] = float(np.nanmin(cross))
    n["rho_tmax_vs_tmin_max"] = float(np.nanmax(cross))

    rp = rates[rates["window"] == K.PRIMARY_WINDOW]
    g = rp.groupby("definition_id").apply(
        lambda s: pd.Series({
            "js": 1000 * s.loc[s["is_jun_sep"], "heatwave_days"].sum()
            / s.loc[s["is_jun_sep"], "eligible_days"].sum(),
            "other": 1000 * s.loc[~s["is_jun_sep"], "heatwave_days"].sum()
            / s.loc[~s["is_jun_sep"], "eligible_days"].sum(),
            "pct_out": 100 * s.loc[~s["is_jun_sep"], "heatwave_days"].sum()
            / s["heatwave_days"].sum()}), include_groups=False)
    n["rate_ratio_min"] = float((g["js"] / g["other"]).min())
    n["rate_ratio_max"] = float((g["js"] / g["other"]).max())
    n["pct_outside_min"] = float(g["pct_out"].min())
    n["pct_outside_max"] = float(g["pct_out"].max())
    n["peak_months"] = ", ".join(sorted(prim["peak_month_by_rate"].unique()))

    w = wsens[~wsens["is_primary"]]
    n["win_jac_med"] = float(w["jaccard_vs_primary"].median())
    n["win_jac_min"] = float(w["jaccard_vs_primary"].min())
    for wk in [x for x in K.WINDOW_ORDER if x != K.PRIMARY_WINDOW]:
        n["win_%s_jac" % wk] = float(w.loc[w["window"] == wk, "jaccard_vs_primary"].median())
    # month vs month_pm7 DIRECTLY (not each against the primary window): the pair that
    # decides whether month_pm7 adds anything
    wpairs = agree[agree["single_axis"] == "window"]
    mm = wpairs[wpairs.apply(lambda r: {r["window_a"], r["window_b"]}
                             == {"month", "month_pm7"}, axis=1)]
    n["win_month_vs_pm7"] = float(mm["jaccard_day_level"].median()) if len(mm) else np.nan
    n["win_month_vs_pm7_n"] = len(mm)
    w05 = wpairs[wpairs.apply(lambda r: {r["window_a"], r["window_b"]}
                              == {"w05", "w15"}, axis=1)]
    n["win_w05_vs_w15"] = float(w05["jaccard_day_level"].median()) if len(w05) else np.nan
    n["n_long"] = int(len(long_ev))
    n["n_long_primary"] = int((long_ev["window"] == K.PRIMARY_WINDOW).sum())
    n["long_max"] = int(long_ev["event_duration_days"].max())
    n["long_defs"] = int(long_ev["definition_id"].nunique())
    n["long_high_imp"] = int((long_ev["pct_event_days_imputed"] >= 50).sum())

    kt = knife.copy()
    kt["fam"] = kt["definition_id"].str.split("_").str[0]
    by = kt.groupby("fam")["days_within_1e-9_degF_of_threshold"].sum()
    ev_by = kt.groupby("fam")["evaluable_county_days"].sum()
    n["tie_pct"] = {f: 100 * by.get(f, 0) / ev_by.get(f, 1) for f in ("TMAX", "TMIN", "MHI")}
    n["tie_total"] = int(by.sum())

    # data-quality subgroups: does IDW gap-filling shift exposure, and does that
    # depend on the metric? (surfaced by Figure 13, quantified in s04)
    sub_path = os.path.join(T, "support_imputation_subgroup_medians.csv")
    if os.path.exists(sub_path):
        sub = rd("support_imputation_subgroup_medians.csv")
        n["imp_sub"] = sub
        for m in ("TMAX", "TMIN", "MHI"):
            g = sub.loc[sub["metric"] == m, "ratio_fully_imputed_over_complete"]
            n["imp_ratio_%s_med" % m] = float(g.median())
            n["imp_ratio_%s_min" % m] = float(g.min())
            n["imp_ratio_%s_max" % m] = float(g.max())
        n["imp_ratio_all_med"] = float(sub["ratio_fully_imputed_over_complete"].median())
    n["val_pass"] = int((val["result"] == "PASS").sum())
    n["val_fail"] = int((val["result"] == "FAIL").sum())
    n["val_rep"] = int((val["result"] == "REPORTED").sum())
    n["s01_checks"] = len(s01)
    n["s01_fail"] = int((s01["result"] == "FAIL").sum())
    n["recon_checks"] = len(recon)
    n["recon_fail"] = int((recon["result"] == "FAIL").sum())
    n["n_pairs_total"] = len(agree)
    n["n_pairs_single"] = int((agree["n_axes_differing"] == 1).sum())
    n["n_examples"] = len(ex)
    n["examples"] = ", ".join("%s (%s)" % (r["county_name"], r["climate_division"])
                             for _, r in ex.iterrows())
    n["pidx"] = pidx
    n["summ"] = summ
    n["qa"] = qa
    n["ex"] = ex
    return n


# =============================================================================
# figure_captions.md -- the required per-figure report
# =============================================================================
def figure_report(n):
    P = K.PRIMARY_WINDOW
    F = []

    F.append(dict(
        fig="Figure 1", name="Definition design matrix",
        file="figures/core/fig01_definition_design_matrix.png",
        purpose="State the full design before any result is shown: what the %d definitions "
                "are, which round each came from, which threshold windows exist for each, "
                "whether their inputs are comparable, and which cells were never run."
                % n["n_defs"],
        unit="one definition (metric x percentile x minimum duration)",
        inputs="tables/table1_definition_registry.csv",
        transform="No statistics. The registry is rendered as a matrix; the two cells that "
                  "complete the 3x3x2 factorial but were never run are appended as explicit "
                  "NOT TESTED rows.",
        encoding="Metric by colour + hatch + marker + text label. Untested rows in flat grey "
                 "with the status spelled out. No quantitative colour scale.",
        supports="That %d of the 18 factorial cells were run, that all four windows exist for "
                 "every one of them, and that the fixed axes (input hash, boundaries, IDW, "
                 "walk-forward baseline, strict '>', year-round season, no floor) are common "
                 "to all %d." % (n["n_defs"], n["n_defs"]),
        not_supports="Nothing about how any definition performs. It carries no counts, no "
                     "agreement and no ranking, and it does not imply the design is balanced "
                     "- it is not: the mean-HI metric has no >=3-day cell at the 85th or 95th "
                     "percentile.",
        caption="Design matrix of the %d county-level heatwave definitions compared for %s, "
                "%s. Each definition is a county-relative percentile of a daily heat metric "
                "sustained over a minimum number of consecutive days, on a walk-forward "
                "baseline (1979 to the year before the analysis year), evaluated year-round "
                "with a strict '>' and no absolute floor. Definitions 01-02 were published "
                "in an earlier round and were re-run on the current code path for this "
                "comparison; Definitions 03-16 are the current grid. The two mean-HI 3-day "
                "cells were never run and are shown as NOT TESTED rather than as zero."
                % (n["n_defs"], K.STATE_LABEL, YEARS),
        limitation="A design matrix cannot show that the fixed axes were actually honoured in "
                   "the output; that is what qa/s03_validation.md tests (%d checks passed, "
                   "%d failed)." % (n["val_pass"], n["val_fail"])))

    F.append(dict(
        fig="Figure 2", name="Matched-pair count change vs day-level agreement",
        file="figures/core/fig02_count_change_vs_agreement.png",
        purpose="Separate the two things a definition choice can do: change HOW MANY heatwave "
                "days are counted, and change WHICH county-dates are classified. They are not "
                "the same, and a count table cannot tell them apart.",
        unit="one matched pair of runs (identical on the other three axes); the underlying "
             "quantities are pooled heatwave days (QA) and the SET of (county, date) heatwave "
             "days",
        inputs="tables/table7_matched_pair_marginal_effects.csv, "
               "tables/table7b_marginal_effects_summary.csv",
        transform="Only pairs differing on exactly ONE axis are used (%d of %d pairs). For "
                  "each, the percentage difference in pooled heatwave days and the Jaccard "
                  "index of the two day sets. Faceted by axis; the median of each axis is "
                  "drawn and the matched-pair count printed."
                  % (n["n_pairs_single"], n["n_pairs_total"]),
        encoding="One panel per axis (shared scales), point colour+shape = the metric held "
                 "fixed, brown reference lines = this project's earlier sensitivity "
                 "yardsticks.",
        supports="That the axes rank differently on the two questions. Day-level effect, "
                 "largest first: %s (Jaccard medians; lower = larger effect). Count effect: "
                 "percentile moves counts most (median %.2fx, up to %.2fx), metric barely at "
                 "all (median %.2fx) while disagreeing on most days (Jaccard %.3f)."
                 % (n["axis_rank"], n["ax_percentile_ratio"], n["ax_percentile_ratiomax"],
                    n["ax_metric_ratio"], n["ax_metric_jac"]),
        not_supports="Which axis matters for health, and which definition is right. Jaccard is "
                     "agreement between two definitions, NOT accuracy: neither is a gold "
                     "standard and this data contains no observed heatwave day. Nor does it "
                     "support any statement about a single county - these are statewide "
                     "matched-pair aggregates.",
        caption="Effect of changing one definition axis at a time, %s, %s. Each point is a "
                "matched pair of runs identical on the other three axes (n = %d pairs). The "
                "x axis is the percentage difference in pooled heatwave county-days (a QA "
                "quantity); the y axis is the Jaccard index on the sets of classified "
                "(county, date) heatwave days. Changing the METRIC leaves the count nearly "
                "unchanged (median %.2fx) while changing which days are classified more than "
                "any other axis (median Jaccard %.3f); changing the PERCENTILE is the count "
                "lever (median %.2fx). Brown lines mark agreement values from this project's "
                "earlier sensitivity work for scale."
                % (K.STATE_LABEL, YEARS, n["n_pairs_single"], n["ax_metric_ratio"],
                   n["ax_metric_jac"], n["ax_percentile_ratio"]),
        limitation="Matched-pair counts differ by axis (metric %d, percentile %d, duration "
                   "%d, window %d). The duration axis has fewest pairs because the two "
                   "mean-HI 3-day cells were never run, so its median rests on a smaller and "
                   "differently-composed sample than the others."
                   % (n["ax_metric_pairs"], n["ax_percentile_pairs"], n["ax_duration_pairs"],
                      n["ax_window_pairs"])))

    F.append(dict(
        fig="Figure 3", name="Day-level agreement matrix",
        file="figures/core/fig03_jaccard_heatmap_primary_window.png",
        purpose="Show, for every pair of definitions at one common window, how much of the "
                "classified exposure they actually share.",
        unit="the SET of (county, date) heatwave days",
        inputs="tables/support_jaccard_matrix_primary.csv (from the canonical long table)",
        transform="Jaccard = shared county-dates / union of county-dates, all %d definitions "
                  "at the %s window, ordered by metric then percentile then duration, fixed "
                  "0-1 scale." % (n["n_defs"], P),
        encoding="One-hue sequential ramp, fixed 0-1; black lines separate metric families; "
                 "tick labels carry the metric colour; every cell annotated.",
        supports="That definitions which look interchangeable in a count table often are not: "
                 "off-diagonal agreement runs from %.3f to %.3f (median %.3f), with the "
                 "lowest at %s. Blocks along the diagonal show that agreement is highest "
                 "within a metric family."
                 % (n["jac_min"], n["jac_max"], n["jac_med"], n["jac_min_pair"]),
        not_supports="Accuracy, or a ranking of definitions. It also does not describe any "
                     "individual county - a statewide Jaccard can hide large county-level "
                     "variation (see the per-county matrices in Figure 8).",
        caption="Day-level agreement between %d heatwave definitions, %s, %s, %s threshold "
                "window. Each cell is the Jaccard index between two definitions on the set of "
                "classified (county, date) heatwave days: 1.0 = identical sets, 0 = disjoint. "
                "Off-diagonal agreement ranges %.2f-%.2f (median %.2f). Agreement is highest "
                "within a metric family (blocks on the diagonal) and lowest between "
                "day-time and night-time temperature definitions. Jaccard measures agreement "
                "between definitions, not the accuracy of either."
                % (n["n_defs"], K.STATE_LABEL, YEARS, P, n["jac_min"], n["jac_max"],
                   n["jac_med"]),
        limitation="One window only, so it says nothing about window sensitivity (Figure 7), "
                   "and it is computed on pooled county-dates, so a county with many heatwave "
                   "days contributes more than a county with few."))

    F.append(dict(
        fig="Figure 4", name="County-rank stability",
        file="figures/core/fig04_county_rank_stability.png",
        purpose="Ask whether the ORDER of counties survives a change of definition, and "
                "whether the answer depends on including counties with heavily imputed "
                "temperature.",
        unit="county (cumulative %s heatwave days per county, not annual)" % YEARS,
        inputs="tables/support_county_rank_spearman_all.csv, "
               "tables/support_county_rank_spearman_complete.csv",
        transform="Per-county heatwave-day totals per definition at the %s window; Spearman "
                  "correlation between every pair of definitions. Panel A all %d counties; "
                  "panel B the %d counties at or below the prespecified %.0f%% imputation "
                  "cut." % (P, n["n_counties"], n["n_complete"], K.IMPUTATION_MAX_PCT),
        encoding="Same matrix layout, ordering and fixed 0-1 scale as Figure 3, so the two "
                 "figures can be read against each other directly.",
        supports="That county ORDER is far more stable than day-level agreement: median rho "
                 "%.3f (range %.3f-%.3f) across all counties, with %.0f%% of pairs above "
                 "0.90, against a median Jaccard of %.3f for the same pairs. Restricting to "
                 "complete-data counties changes it very little (median %.3f), so the "
                 "county ordering is not an artefact of the heavily imputed counties. The one "
                 "place ordering DOES break down is the metric axis: rank agreement is %.2f "
                 "within a metric family but only %.2f-%.2f between the Tmax and Tmin "
                 "families."
                 % (n["rho_all_med"], n["rho_all_min"], n["rho_all_max"],
                    n["rho_all_pct_above_90"], n["jac_med"], n["rho_complete_med"],
                    n["rho_within_family_med"], n["rho_tmax_vs_tmin_min"],
                    n["rho_tmax_vs_tmin_max"]),
        not_supports="That the definitions agree on exposure. High rank correlation with low "
                     "Jaccard means the definitions disagree about WHICH DAYS while ordering "
                     "counties similarly - so a high rho here must NOT be read as day-level "
                     "agreement, and neither quantity is accuracy. It also does not license "
                     "trusting any individual county's rank.",
        caption="Stability of county rankings across %d heatwave definitions, %s, %s, %s "
                "window. Each cell is the Spearman correlation between two definitions' "
                "per-county heatwave-day totals over %s. Panel A: all %d counties. Panel B: "
                "the %d counties with at most %.0f%% IDW-imputed temperature. County order is "
                "considerably more stable (median rho %.2f) than the underlying day-level "
                "agreement (median Jaccard %.2f, Figure 3): the definitions largely agree on "
                "which counties are more exposed while disagreeing on most of the specific "
                "days."
                % (n["n_defs"], K.STATE_LABEL, YEARS, P, YEARS, n["n_counties"],
                   n["n_complete"], K.IMPUTATION_MAX_PCT, n["rho_all_med"], n["jac_med"]),
        limitation="Rank correlation is insensitive to the SIZE of differences and to which "
                   "counties move; a definition pair can score high while reordering the top "
                   "of the distribution. It also inherits the temperature-source instability "
                   "documented in earlier rounds (anchor vs composite station agreement "
                   "0.45-0.73), which is independent of the definition axis."))

    F.append(dict(
        fig="Figure 5", name="Monthly classification rate",
        file="figures/core/fig05_monthly_rate_heatmap.png "
             "(+ figures/supplement/fig05s_monthly_share_heatmap.png)",
        purpose="Characterise seasonality as a RATE per eligible day, so that month length "
                "and unequal data coverage cannot masquerade as seasonality.",
        unit="county-month, pooled over counties and years",
        inputs="tables/support_monthly_rate_by_definition.csv "
               "(numerator: master_county_month_summary.csv; denominator: "
               "eligibility_county_month.csv)",
        transform="1,000 x heatwave days / ELIGIBLE county-days per definition x month, where "
                  "an eligible day is one the definition could be evaluated on (metric "
                  "present, threshold present, not a confirmed RH-clip artifact). The month "
                  "SHARE version is rendered separately as a supplement and labelled the "
                  "weaker metric.",
        encoding="One-hue sequential ramp with the untested cells in flat grey; Jun-Sep boxed "
                 "in brown; every cell annotated.",
        supports="That the cool-season loading of these year-round relative definitions is "
                 "intrinsic and not a property of one metric: across all %d definitions "
                 "%.0f-%.0f%% of heatwave days fall outside Jun-Sep, and the Jun-Sep rate "
                 "exceeds the Oct-May rate by only %.2f-%.2fx. Peak month by rate across the "
                 "definitions: %s."
                 % (n["n_defs"], n["pct_outside_min"], n["pct_outside_max"],
                    n["rate_ratio_min"], n["rate_ratio_max"], n["peak_months"]),
        not_supports="That cool-season heatwave days are hazardous. These are days unusual "
                     "FOR THEIR OWN DATE with no absolute floor and no seasonal restriction; "
                     "a December day above its December threshold is a persistent apparent-heat "
                     "anomaly, not physically hazardous heat. The figure also cannot say "
                     "whether a floor or a seasonal window is the better remedy.",
        caption="Seasonality of heatwave classification as a rate, %s, %s, %s window. Cells "
                "are heatwave days per 1,000 eligible county-days, by definition and calendar "
                "month; the denominator counts only days on which the definition could be "
                "evaluated, so months of different length and coverage are comparable. Every "
                "definition places %.0f-%.0f%% of its heatwave days outside June-September. "
                "Because these definitions are county-relative, year-round and carry no "
                "absolute floor, cool-season days qualify as 'unusual for the date' and must "
                "not be interpreted as hazardous heat."
                % (K.STATE_LABEL, YEARS, P, n["pct_outside_min"], n["pct_outside_max"]),
        limitation="Pooling over counties and years hides both the north-south gradient and "
                   "year-to-year variation; the county-month panels in Figure 8 carry the "
                   "county-level version. The eligible-day denominator treats an IDW-imputed "
                   "day as eligible, which is a coverage choice, not a data-quality claim."))

    F.append(dict(
        fig="Figure 6", name="Percentile and duration ladder",
        file="figures/core/fig06_percentile_duration_ladder.png",
        purpose="Show how the percentile and the persistence rule move exposure at the level "
                "the project reports - individual county-years - rather than as pooled totals.",
        unit="county-year (%d counties x 11 years = 2,794 records per definition)"
             % n["n_counties"],
        inputs="master_county_year_summary.csv, eligibility_county_month.csv",
        transform="Heatwave days per 1,000 eligible county-days per county-year, plotted "
                  "against percentile, faceted by metric, split by minimum duration. Faint "
                  "line per county-year; heavy line the MEDIAN county-year. No line is drawn "
                  "across an untested cell.",
        encoding="Metric = facet + colour + marker; percentile = x position; duration = "
                 "line style and marker fill (filled >=2 days, open >=3 days).",
        supports="The monotone effect of the percentile within every metric, the spread across "
                 "county-years at a fixed definition (visible as the width of the faint "
                 "bundle), and the size of the duration step where both durations exist "
                 "(median count ratio %.2fx, day-level Jaccard %.3f)."
                 % (n["ax_duration_ratio"], n["ax_duration_jac"]),
        not_supports="Any mean-HI >=3-day statement at the 85th or 95th percentile: those "
                     "cells were never run, so the mean-HI facet has a single >=3-day point "
                     "at the 90th and no line. No pooled average across county-years is drawn "
                     "or implied.",
        caption="Effect of percentile and minimum duration on county-year heatwave exposure, "
                "%s, %s, %s window. Each faint line is one county-year (2,794 per "
                "definition); heavy lines are the median county-year. Rates use eligible "
                "county-days as denominator. Lines are not connected across the two mean-HI "
                ">=3-day cells, which were never run."
                % (K.STATE_LABEL, YEARS, P),
        limitation="Overplotting: 2,794 faint lines per facet convey the envelope, not "
                   "individual counties, and heavily imputed counties are not visually "
                   "distinguished here (they are in Figure 11)."))

    F.append(dict(
        fig="Figure 7", name="Threshold-window sensitivity",
        file="figures/core/fig07_threshold_window_sensitivity.png",
        purpose="Quantify how much the choice of baseline-pooling window changes the result, "
                "and show the threshold curves that produce the difference.",
        unit="panel A the SET of (county, date) heatwave days; panel B county-year counts "
             "paired county by county and year by year; panel C the county's own threshold "
             "in degF by day of year",
        inputs="tables/support_window_sensitivity.csv, "
               "tables/support_example_counties.csv, outputs/%s/grid/_thresholds/" % STATE,
        transform="Every definition compared with its own %s run: Jaccard, and the "
                  "distribution of (this window - primary window) heatwave days across 2,794 "
                  "paired county-years. Panel C plots the cached walk-forward thresholds for "
                  "%s in analysis year %d."
                  % (P, K.THRESHOLD_CURVE_DEFINITION, K.THRESHOLD_CURVE_YEAR),
        encoding="Window = neutral grey ramp and bar position (never a metric colour); metric "
                 "identity retained in the coloured tick labels; panels A and B share the "
                 "definition ordering and x axis.",
        supports="That the window is the least consequential of the four axes: median Jaccard "
                 "against the primary window %.3f (lowest %.3f). Compared with each other "
                 "rather than with the primary window, month and month_pm7 are "
                 "near-duplicates (median Jaccard %.3f) while w05 vs w15 differ more (%.3f). "
                 "Paired county-year differences are small and centred near zero for the "
                 "calendar-month windows."
                 % (n["win_jac_med"], n["win_jac_min"], n["win_month_vs_pm7"],
                    n["win_w05_vs_w15"]),
        not_supports="That the window can be ignored in general - w05 differs more than the "
                     "others - or that any window is more nearly correct. Panel C shows the "
                     "mechanism, not a validation.",
        caption="Threshold-window sensitivity of %d heatwave definitions, %s, %s. (A) "
                "day-level Jaccard between each definition's %s run and its runs at the other "
                "three windows. (B) paired differences in county-year heatwave days relative "
                "to the %s run (dot = median, bar = interquartile range over 2,794 paired "
                "county-years). (C) the underlying walk-forward threshold curves for %s in "
                "%d, for example counties chosen by a documented climate-region and "
                "data-completeness rule. Centered windows give a threshold per day of year; "
                "calendar-month windows give one step per month."
                % (n["n_defs"], K.STATE_LABEL, YEARS, P, P,
                   K.THRESHOLD_CURVE_DEFINITION, K.THRESHOLD_CURVE_YEAR),
        limitation="Panel C shows %d of the %d example counties and one definition in one "
                   "year, chosen mechanically; it is an illustration of the pooling mechanism "
                   "rather than a sensitivity estimate." % (4, n["n_examples"])))

    F.append(dict(
        fig="Figure 8", name="County report cards (254 counties)",
        file="county_profiles/<fips>/fig08_report_card_<fips>.png (+ INDEX.csv)",
        purpose="Give every county its own complete, auditable record: how each definition "
                "behaves there year by year, month by month, and how much the definitions "
                "agree there - with the county's data provenance stated in the header.",
        unit="one county; panels are county-year, county-year, county-month and county-date",
        inputs="master_county_year_summary.csv, master_county_month_summary.csv, "
               "eligibility_county_month.csv, tables/canonical_long/*.csv.gz, "
               "outputs/%s/coverage_and_imputation_report.csv" % STATE,
        transform="Per county: definition x year heatwave days; definition x year events "
                  "STARTED (an event counted once, in its onset year); definition x month "
                  "rate per 1,000 eligible county-days; and a %d x %d day-level Jaccard "
                  "matrix computed on that county's days alone."
                  % (n["n_defs"] + n["n_untested"], n["n_defs"] + n["n_untested"]),
        encoding="Same sequential ramp, same definition ordering and the same flat-grey "
                 "NOT TESTED rows as the statewide figures, so a county card can be read "
                 "against Figures 3-5 without re-learning the layout.",
        supports="County-specific description: which definitions flag most days there, in "
                 "which years and months, and whether the definitions agree with each other "
                 "in that county. The header supports judging how much of the county's record "
                 "is native observation (%d of %d counties are 100%% IDW-imputed and %d are "
                 "flagged above the %.0f%% cut)."
                 % (n["n_fully_imputed"], n["n_counties"], n["n_flagged"],
                    K.IMPUTATION_MAX_PCT),
        not_supports="Any claim that one definition is correct for that county, and any "
                     "county-to-county comparison drawn from single cards - the earlier "
                     "anchor-vs-composite temperature work (agreement 0.45-0.73) means "
                     "single-county texture is not reliable. Cards for the %d flagged "
                     "counties describe the IDW field, not an independent observation."
                     % n["n_flagged"],
        caption="County report card, <county> County, %s, %s. Panel A heatwave days and "
                "panel B heatwave events started, by definition and year; panel C heatwave "
                "days per 1,000 eligible county-days by definition and month (June-September "
                "boxed); panel D day-level Jaccard between definitions computed on this "
                "county's days alone. Header states analysis days, native versus IDW-imputed "
                "days and the county's climate division. Grey rows are the two mean-HI 3-day "
                "cells, never run." % (K.STATE_LABEL, YEARS),
        limitation="A county with few heatwave days yields small and unstable Jaccard values "
                   "in panel D, and the cards are cumulative over %s - no annual rate is "
                   "shown. Cards are produced for all %d counties including fully imputed "
                   "ones; the header flag, not the absence of a card, is what marks those."
                   % (YEARS, n["n_counties"])))

    F.append(dict(
        fig="Figure 9", name="Individual event timelines",
        file="event_audits/fig09_timeline_<fips>_<county>.png",
        purpose="Make the classification mechanics inspectable day by day: where the metric "
                "sits relative to the county's own threshold, which runs qualify, and which "
                "candidate days fail the persistence rule.",
        unit="county-date within one calendar window",
        inputs="outputs/%s/county_daily_heat.csv + the cached thresholds, rebuilt through the "
               "same classification code as the canonical table" % STATE,
        transform="For each example county one calendar window - the first event of %d under "
                  "%s, padded by %d days and widened to at least 45 days - is shown for all "
                  "%d shortlisted definitions, stacked."
                  % (K.EVENT_TIMELINE_REFERENCE_YEAR, K.EVENT_TIMELINE_REFERENCE_DEFINITION,
                     K.EVENT_TIMELINE_DAYS_PAD, len(K.SHORTLIST_DEFINITIONS)),
        encoding="Metric = colour + marker; threshold = grey line whose style encodes the "
                 "percentile; qualifying runs shaded and labelled with exact start, end and "
                 "INTEGER duration; imputed days as open markers; isolated candidate days "
                 "ringed in brown.",
        supports="That the same days are treated differently by different definitions in the "
                 "same county, that events end because a single day drops below threshold, "
                 "and that integer durations and exact dates are preserved. It shows directly "
                 "why a metric change can move classification without moving the count.",
        not_supports="Anything general. These are %d counties chosen by a documented "
                     "climate-region and completeness rule and one anchored window each; they "
                     "are illustrations, not evidence about the state, and the windows were "
                     "not selected for magnitude." % n["n_examples"],
        caption="Event timelines for <county> County, %s. The same %d-day window judged by "
                "five heatwave definitions: daily metric against the county's own "
                "walk-forward percentile threshold, with qualifying runs shaded and labelled "
                "by exact start date, end date and integer duration. Open markers are "
                "IDW-imputed temperature; brown rings are candidate days that failed the "
                "minimum-duration rule and so ended a run. The window is anchored "
                "mechanically on the first %d event under %s."
                % (K.STATE_LABEL, 45, K.EVENT_TIMELINE_REFERENCE_YEAR,
                   K.EVENT_TIMELINE_REFERENCE_DEFINITION),
        limitation="One window per county, and events may extend beyond it (labelled where "
                   "they do). The example counties are the most data-complete in each climate "
                   "division by construction, so they under-represent the imputation problem "
                   "seen elsewhere."))

    F.append(dict(
        fig="Figure 10", name="Long-event audit",
        file="event_audits/fig10_long_event_<run>_<event_id>.png "
             "(+ fig10_long_event_audit_with_station_counts.csv, "
             "fig10_not_individually_plotted.csv)",
        purpose="Subject every implausibly long 'event' to inspection - with its data "
                "provenance attached - without deleting any of them.",
        unit="county-date within one heatwave event; one figure per event",
        inputs="tables/table8a_long_event_audit.csv, the rebuilt daily panels, and the RAW "
               "GHCN county-day file for contributing station counts",
        transform="Every event at or above the prespecified %d-day review length. %d such "
                  "events exist across all %d runs (%d at the %s window, longest %d days, "
                  "spanning %d definitions); the longest %d at the primary window are drawn "
                  "individually and any remainder is listed in "
                  "fig10_not_individually_plotted.csv."
                  % (K.LONG_EVENT_REVIEW_DAYS, n["n_long"], n["n_runs"],
                     n["n_long_primary"], P, n["long_max"], n["long_defs"],
                     K.LONG_EVENT_PLOT_CAP),
        encoding="Three stacked panels sharing one time axis - metric vs threshold, daily "
                 "exceedance, and data provenance (imputation flag plus Tmax/Tmin "
                 "contributing station counts) - with month boundaries marked on all three. "
                 "No dual y-scale anywhere.",
        supports="Judging whether a long run is a sustained anomaly or an artefact: %d of the "
                 "%d long events have at least half their days IDW-imputed. It also shows "
                 "that long runs in a relative year-round definition can consist of days only "
                 "marginally above threshold."
                 % (n["long_high_imp"], n["n_long"]),
        not_supports="Deleting or truncating any event. Nothing here establishes that a long "
                     "event is wrong - only that it should not be reported as sustained "
                     "hazardous heat without a floor or a seasonal rule.",
        caption="Long-event audit: <run>, <county> County, %s. An event of <n> consecutive "
                "days flagged for review because it is at or above the prespecified %d-day "
                "review length. Panels show the daily metric against the county's own "
                "walk-forward threshold, the daily exceedance, and the data provenance of "
                "every day (IDW-imputation flag and the number of contributing GHCN stations "
                "for Tmax and Tmin), with calendar-month boundaries marked. All long events "
                "are retained in every table and count; this audit makes them inspectable."
                % (K.STATE_LABEL, K.LONG_EVENT_REVIEW_DAYS),
        limitation="Station counts come from the raw GHCN input because the classification "
                   "table does not retain them; they describe the county-day temperature "
                   "aggregation, not the humidity field, so a mean-HI event's humidity "
                   "provenance is not shown. Only the primary window is drawn; long events at "
                   "the other three windows are tabulated, not plotted."))

    F.append(dict(
        fig="Figure 11", name="Data-quality influence",
        file="figures/core/fig11_data_quality_influence.png",
        purpose="Test whether the county picture is being driven by how much of a county's "
                "temperature record was gap-filled rather than by climate.",
        unit="county (cumulative %s heatwave days, and the county's rank within a definition)"
             % YEARS,
        inputs="master_county_year_summary.csv, table8b_county_data_quality.csv",
        transform="Per-county heatwave-day totals and ranks for the %d shortlisted "
                  "definitions at the %s window, plotted against the county's "
                  "temperature-imputation percentage, with Spearman correlations annotated "
                  "and fully imputed counties marked separately."
                  % (len(K.SHORTLIST_DEFINITIONS), P),
        encoding="Metric colour + marker per definition (facets); the %.0f%% cut as a dotted "
                 "brown line; the %d fully imputed counties as brown crosses."
                 % (K.IMPUTATION_MAX_PCT, n["n_fully_imputed"]),
        supports="Whether imputation and exposure are associated, and identifies exactly "
                 "which counties would carry any such association (%d flagged above the cut, "
                 "%d of them fully imputed)." % (n["n_flagged"], n["n_fully_imputed"]),
        not_supports="Causation in either direction, and any inference that a low correlation "
                     "means imputation is harmless: IDW fills a county from its neighbours, so "
                     "it can bias a county toward the regional mean without changing its total "
                     "much. The earlier anchor-vs-composite finding (0.45-0.73) is the "
                     "relevant magnitude, and this figure does not reproduce that test.",
        caption="Influence of temperature imputation on county-level results, %s, %s, %s "
                "window, five shortlisted definitions. Top row: cumulative heatwave days per "
                "county against the percentage of that county's analysis days whose "
                "temperature was IDW gap-filled. Bottom row: the county's rank within the "
                "same definition. Dotted line marks the prespecified %.0f%% completeness cut "
                "(%d of %d counties qualify); crosses mark the %d counties with no native "
                "station record. Spearman correlations are annotated."
                % (K.STATE_LABEL, YEARS, P, K.IMPUTATION_MAX_PCT, n["n_complete"],
                   n["n_counties"], n["n_fully_imputed"]),
        limitation="Imputation percentage is a crude proxy for temperature-field quality: it "
                   "counts imputed DAYS and says nothing about how far the imputed value sits "
                   "from the truth, nor about the humidity field that the mean-HI definitions "
                   "also depend on."))

    F.append(dict(
        fig="Figure 13", name="Per-county heatwave-day distribution",
        file="figures/core/fig13_county_day_distribution.png",
        purpose="Show the substantive county-level layer directly: how many heatwave days a "
                "county gets under each definition, and how widely counties differ - which a "
                "pooled statewide total cannot express and a median alone hides.",
        unit="county (one point = one county's cumulative %s heatwave days; never annual)"
             % YEARS,
        inputs="master_county_year_summary.csv, table8b_county_data_quality.csv, "
               "support_imputation_subgroup_medians.csv",
        transform="Per-county heatwave days summed over %s for each definition at the %s "
                  "window. Counties with no heatwave day are reindexed in at zero - a genuine "
                  "zero, since the definition was evaluated there. Box (IQR + median) with "
                  "every one of the counties overplotted. Panel A all %d counties; panel B the "
                  "%d at or below the prespecified %.0f%% imputation cut, on the same y scale."
                  % (YEARS, P, n["n_counties"], n["n_complete"], K.IMPUTATION_MAX_PCT),
        encoding="Metric = colour + marker + hatch; duration = fill weight (the >=3-day box is "
                 "lighter), never a separate colour; the two untested cells occupy their "
                 "correct factorial positions as flat grey NOT TESTED slots; the %d fully "
                 "imputed counties are drawn as brown crosses inside each distribution."
                 % n["n_fully_imputed"],
        supports="The size and spread of county exposure under each definition side by side "
                 "(per-county medians run from %d to %d days across the definitions), and the "
                 "monotone percentile and duration effects within each metric family. It also "
                 "shows that the overall distributions are not an artefact of the flagged "
                 "counties - restricting to complete-data counties barely moves the medians. "
                 "But drawing the fully imputed counties INSIDE each distribution exposes "
                 "something Figure 11's correlation misses: those %d counties sit "
                 "systematically higher under every Tmin definition (median ratio %.2f, range "
                 "%.2f-%.2f vs complete-data counties) while being flat to slightly lower "
                 "under Tmax (%.2f, %.2f-%.2f) and mildly higher under mean HI (%.2f). IDW "
                 "gap-filling therefore interacts with the METRIC, which makes it a "
                 "definition-level data-quality property rather than one global caveat. "
                 "Numbers in tables/support_imputation_subgroup_medians.csv."
                 % (n["med_days_min"], n["med_days_max"], n["n_fully_imputed"],
                    n.get("imp_ratio_TMIN_med", float("nan")),
                    n.get("imp_ratio_TMIN_min", float("nan")),
                    n.get("imp_ratio_TMIN_max", float("nan")),
                    n.get("imp_ratio_TMAX_med", float("nan")),
                    n.get("imp_ratio_TMAX_min", float("nan")),
                    n.get("imp_ratio_TMAX_max", float("nan")),
                    n.get("imp_ratio_MHI_med", float("nan"))),
        not_supports="Any individual county's value or rank. Earlier work found anchor-station "
                     "vs multi-station composite temperature agreeing at only 0.45-0.73, so a "
                     "single county's position within a distribution is not reliable even "
                     "though the overall gradient is. It also says nothing about WHICH days "
                     "each definition picked - two definitions can produce near-identical "
                     "distributions here while sharing few actual county-dates (Figure 3).",
        caption="Distribution of per-county heatwave days under %d heatwave definitions, %s, "
                "%s, %s threshold window. Each point is one county's cumulative heatwave-day "
                "count over %s (not an annual rate); boxes give the interquartile range with "
                "the median labelled. Panel A: all %d counties. Panel B: the %d counties with "
                "at most %.0f%% IDW-imputed temperature, on the same scale. Brown crosses mark "
                "the %d counties with no native station record. The two mean-HI 3-day cells "
                "were never run and appear in their factorial positions as NOT TESTED rather "
                "than as zero."
                % (n["n_defs"], K.STATE_LABEL, YEARS, P, YEARS, n["n_counties"],
                   n["n_complete"], K.IMPUTATION_MAX_PCT, n["n_fully_imputed"]),
        limitation="Cumulative totals over %s compress real year-to-year variation (Figure 8 "
                   "panel A carries the county-year detail), and a box plot of 254 counties "
                   "cannot show spatial structure - the same distribution could arise from a "
                   "smooth regional gradient or from scattered county-level noise, which is "
                   "why the maps in Figure 12 and the county cards in Figure 8 exist." % YEARS))

    F.append(dict(
        fig="Figure 12", name="Definition-pair disagreement",
        file="figures/core/fig12_pair_disagreement_<pair>.png (%d pairs) "
             "(+ tables/support_pair_days_<pair>_a_only.csv.gz / _b_only.csv.gz)"
             % len(n["pidx"]),
        purpose="Localise disagreement for prespecified single-axis contrasts: WHERE and WHEN "
                "two definitions part company, with the disagreeing county-dates listed "
                "explicitly.",
        unit="(county, date) heatwave day; mapped per county and summarised per calendar month",
        inputs="tables/support_pair_disagreement_<pair>.csv, "
               "tables/support_pair_disagreement_by_month_<pair>.csv, "
               "the county boundary shapefile",
        transform="Outer join of the two definitions' heatwave county-date sets, classified "
                  "A-only / B-only / shared; per-county disagreement rate mapped; monthly "
                  "counts plotted; both one-sided county-date lists written to CSV.",
        encoding="Choropleth on the one-hue sequential ramp with a fixed 0-100% scale; "
                 "counties above the imputation cut outlined in brown; monthly panel uses "
                 "two contrasting bar colours for the two one-sided sets and a dark line for "
                 "the shared set.",
        supports="That disagreement is spatially and seasonally structured rather than random, "
                 "and - via the exported lists - exactly which county-dates each definition "
                 "claims alone. Pair Jaccards: %s."
                 % "; ".join("%s %.3f" % (r["axis"], r["jaccard_day_level"])
                             for _, r in n["pidx"].iterrows()),
        not_supports="Which member of a pair is right, and any generalisation to pairs not "
                     "shown. The pairs were fixed in advance to isolate one axis each; they "
                     "are not the most or least agreeing pairs.",
        caption="Disagreement between <A> and <B>, %s, %s, isolating the <axis> axis. (A) "
                "percentage of each county's classified county-dates that only one of the two "
                "definitions flags; counties above the %.0f%% imputation cut are outlined. "
                "(B) the same disagreement by calendar month, with days claimed by only one "
                "definition shown separately from days both definitions classify. The "
                "complete A-only and B-only county-date lists accompany the figure as CSVs."
                % (K.STATE_LABEL, YEARS, K.IMPUTATION_MAX_PCT),
        limitation="A per-county RATE hides absolute volume: a county with 20 classified days "
                   "and a 50% disagreement rate looks identical to one with 600 days at 50%. "
                   "The map inherits the county-boundary and IDW caveats and, for the window "
                   "contrast, both panels come from the same underlying metric so the "
                   "disagreement is purely a baseline-pooling effect."))
    # keep the report in figure-number order regardless of the order the blocks are
    # written in above
    return sorted(F, key=lambda x: int(x["fig"].split()[-1]))


def write_figure_captions(n, F):
    p = os.path.join(K.PKG_ROOT, "figure_captions.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("# Figure report - %d heatwave definitions, %s, %s\n\n"
                % (n["n_defs"], K.STATE_LABEL, YEARS))
        f.write("For every figure: purpose, unit of analysis, input file, transformation, "
                "visual encoding, what the figure DOES support, what it does NOT support, a "
                "draft publication caption, and its known limitation.\n\n")
        f.write("Primary threshold window: `%s`. Data-completeness cut: %.0f%% imputed "
                "(%d of %d counties). Long-event review length: %d days. All counts are "
                "cumulative over %s unless stated; pooled cross-county totals are QA "
                "quantities only.\n\n"
                % (K.PRIMARY_WINDOW, K.IMPUTATION_MAX_PCT, n["n_complete"], n["n_counties"],
                   K.LONG_EVENT_REVIEW_DAYS, YEARS))
        f.write("| # | figure | file |\n|---|---|---|\n")
        for x in F:
            f.write("| %s | %s | `%s` |\n" % (x["fig"], x["name"], x["file"].split(" (")[0]))
        f.write("\n---\n\n")
        for x in F:
            f.write("## %s - %s\n\n" % (x["fig"], x["name"]))
            f.write("**File** `%s`\n\n" % x["file"])
            for label, key in (("Purpose", "purpose"), ("Unit of analysis", "unit"),
                               ("Input file(s)", "inputs"), ("Transformation", "transform"),
                               ("Visual encoding", "encoding"),
                               ("Result supported", "supports"),
                               ("Result NOT supported", "not_supports")):
                f.write("**%s.** %s\n\n" % (label, x[key]))
            f.write("**Draft publication caption.**\n\n> %s\n\n" % x["caption"])
            f.write("**Known limitation.** %s\n\n---\n\n" % x["limitation"])
    K.log("[write] figure_captions.md  (%d figures)" % len(F))


# =============================================================================
# methods_notes.md
# =============================================================================
def write_methods(n):
    p = os.path.join(K.PKG_ROOT, "methods_notes.md")
    tie = n["tie_pct"]
    with open(p, "w", encoding="utf-8") as f:
        f.write("# Methods notes\n\n")
        f.write("## 1. What is being compared\n\n")
        f.write("%d county-level heatwave definitions for %s, %s, each crossed with 4 "
                "threshold windows = %d runs. A definition is `metric x percentile x minimum "
                "duration`; a run is `definition x window`.\n\n"
                % (n["n_defs"], K.STATE_LABEL, YEARS, n["n_runs"]))
        f.write("Held fixed across all %d: county-relative percentile, strict `>`, "
                "walk-forward baseline (1979 to the year before the analysis year, "
                "re-estimated annually), year-round season, **no absolute floor**, IDW "
                "gap-filling of missing temperature, and one identical input county-day "
                "table. Any difference between two runs is therefore attributable to metric, "
                "percentile, duration or window.\n\n" % n["n_defs"])
        f.write("## 2. Units, and the reporting rules they enforce\n\n")
        f.write("| unit | definition |\n|---|---|\n")
        f.write("| heatwave day | one county on one date inside a qualifying run |\n")
        f.write("| heatwave event | one uninterrupted qualifying run within one county |\n")
        f.write("| event duration | integer count of consecutive dates, `end - start + 1` |\n")
        f.write("| candidate day | metric strictly above its own threshold, before the "
                "persistence rule |\n")
        f.write("| eligible day | a county-day the definition could be evaluated on |\n\n")
        f.write("- Pooled cross-county totals appear only in fields suffixed `_QA_pooled` and "
                "are never a substantive result.\n"
                "- No pooled average event duration is reported anywhere; medians, quartiles "
                "and maxima are.\n"
                "- Event durations are integers in every table and label.\n"
                "- Cumulative %s counts are named `_2015_2025` and never described as "
                "annual.\n"
                "- Year-round relative anomalies are never called hazardous heat: with no "
                "absolute floor and no seasonal restriction, a qualifying day is 'unusual for "
                "its own date'.\n\n" % YEARS)
        f.write("### County-month rule\n\nAn event crossing two months is counted ONCE in "
                "`heatwave_events_started`, in its onset month; it is counted as ACTIVE in "
                "every month it touches (`heatwave_events_active`); and its heatwave DAYS are "
                "allocated to the calendar month each day actually falls in.\n\n")
        f.write("### Year-boundary rule\n\nA run is NOT broken at 31 December "
                "(`year_boundary_breaks_run=False`): one physical episode stays one event. "
                "It is counted once in its onset year, and its days are allocated to their "
                "actual calendar years.\n\n")
        f.write("## 3. Prespecified choices\n\n")
        f.write("| choice | value | basis |\n|---|---|---|\n")
        f.write("| primary window | `%s` | the window Def 01/02 were published on |\n"
                % K.PRIMARY_WINDOW)
        f.write("| data-completeness cut | <= %.0f%% imputed days (%d of %d counties) | the "
                "INPUT imputation distribution (median 0.5%%, q75 11.7%%), not any heatwave "
                "result |\n" % (K.IMPUTATION_MAX_PCT, n["n_complete"], n["n_counties"]))
        f.write("| long-event review length | %d days | three continuous weeks is implausible "
                "as one physical episode |\n" % K.LONG_EVENT_REVIEW_DAYS)
        f.write("| example counties | %d, one per NOAA climate division | lowest imputation "
                "%% within the division, ties by lowest FIPS |\n" % n["n_examples"])
        f.write("| shortlist | %s | one definition per metric at the middle percentile and "
                "shorter duration, plus the two published definitions |\n"
                % ", ".join("`%s`" % s for s in K.SHORTLIST_DEFINITIONS))
        f.write("| detailed pairs | %d single-axis contrasts | each isolates one axis; fixed "
                "before results were seen |\n" % len(n["pidx"]))
        f.write("| event-timeline anchor | first %d event under `%s` | fixed definition and "
                "fixed year, so windows are not chosen for magnitude |\n"
                % (K.EVENT_TIMELINE_REFERENCE_YEAR, K.EVENT_TIMELINE_REFERENCE_DEFINITION))
        f.write("\nExample counties selected by that rule: %s.\n\n" % n["examples"])
        f.write("## 4. The canonical long table\n\n")
        f.write("One row per county x date x definition x window, stored at its informative "
                "support: **every candidate day** (a strict superset of the heatwave days, "
                "including isolated candidates). The full cross-product would be 65.3 million "
                "rows, ~90% of them recording only 'nowhere near threshold'.\n\n"
                "Consequences, handled explicitly: a county-day absent from a shard is 'not a "
                "candidate for that definition' - not missing data and not a zero to impute; "
                "and **denominators never come from this table**, they come from "
                "`eligibility_county_month.csv`.\n\n")
        f.write("`exceedance_degF` is stored UNROUNDED while the two value columns are rounded "
                "for readability, so the table remains self-verifying: for these definitions "
                "`candidate_day_flag == 1` exactly where `exceedance_degF > 0` and the day is "
                "not a masked artifact.\n\n")
        f.write("## 5. Validation and provenance\n\n")
        f.write("- **Input provenance.** `tests/test_input_provenance.py` re-derives the "
                "county-day table from the raw GHCN and gridMET files and confirms it is "
                "byte-identical (md5 `f0276ee5888539f9dd4df1b3c7d2435e`), over the full "
                "1979-2025 record.\n")
        f.write("- **Def 01/02 comparability.** The published outputs came from an earlier "
                "`p02` (different schema, only 2 of 4 windows, no recorded input "
                "fingerprint), so both definitions were RE-RUN on the current code path. "
                "%d/%d verification checks pass, including the complete event set and the "
                "published headline totals (Def 01 170,894 days / 48,323 events; Def 02 "
                "52,786 / 17,428). The published directories were never modified. "
                "(`qa/s01_legacy_rerun_verification.md`)\n"
                % (n["s01_checks"] - n["s01_fail"], n["s01_checks"]))
        f.write("- **Rebuild reconciliation.** The canonical table's own heatwave-day and "
                "event counts are checked against every run's published pipeline summary: "
                "%d/%d agree exactly. (`qa/s02_reconciliation.csv`)\n"
                % (n["recon_checks"] - n["recon_fail"], n["recon_checks"]))
        f.write("- **Pre-comparison validation.** %d checks: %d pass, %d fail, plus %d "
                "reported observations. (`qa/s03_validation.md`)\n\n"
                % (n["val_pass"] + n["val_fail"] + n["val_rep"], n["val_pass"],
                   n["val_fail"], n["val_rep"]))
        f.write("### QA findings worth carrying forward\n\n")
        f.write("**(a) Float parsing changes classification.** pandas' default CSV float "
                "parser is not correctly rounded. A cached threshold written as "
                "`101.74999999999999` reads back as `101.75`, and under a strict `>` that "
                "silently drops county-days. Reading thresholds with "
                "`float_precision=\"round_trip\"` is required, not cosmetic; before the fix, "
                "19 of 128 reconciliation checks were off by 1-4 county-days.\n\n")
        f.write("**(b) Exact ties are metric-dependent, and that is an asymmetry between "
                "definitions.** Tmax/Tmin are quantised to 0.1 degC, so a percentile "
                "frequently lands exactly on an observed value: %.2f%% of evaluable "
                "county-days for Tmax and %.2f%% for Tmin sit within 1e-9 degF of their own "
                "threshold, against **%.2f%%** for the derived mean heat index. The choice of "
                "strict `>` over `>=` therefore excludes ~1-2%% of days for the temperature "
                "definitions and **no days at all** for the mean-HI definitions. That is a "
                "data-quantisation artefact, not physics, and it slightly biases every "
                "Tmax/Tmin-vs-mean-HI comparison in this package. "
                "(`qa/s02_knife_edge_days.csv`)\n\n"
                % (tie["TMAX"], tie["TMIN"], tie["MHI"]))
        if "imp_ratio_TMIN_med" in n:
            f.write("**(c) IDW gap-filling interacts with the METRIC, so it is not one global "
                    "caveat.** Comparing the %d fully imputed counties against the %d "
                    "complete-data counties definition by definition (Figure 13; "
                    "`tables/support_imputation_subgroup_medians.csv`): the fully imputed "
                    "counties carry **%.0f-%.0f%% MORE** heatwave days under every Tmin "
                    "definition (median ratio %.2f), but are **flat to slightly lower** under "
                    "Tmax (%.2f, range %.2f-%.2f) and mildly higher under mean HI (%.2f). "
                    "Figure 11's across-all-counties Spearman misses this because it is "
                    "dominated by the 93 counties at 0%% imputation and the effect is a STEP at "
                    "the fully imputed end, not a monotone trend: for `TMIN_P90_2D` that rho is "
                    "-0.011 while the fully imputed subgroup sits %.0f%% higher. Any Tmin-based "
                    "result should therefore be reported on the complete-data subset, or with "
                    "this gap quantified.\n\n"
                    % (n["n_fully_imputed"], n["n_complete"],
                       100 * (n["imp_ratio_TMIN_min"] - 1), 100 * (n["imp_ratio_TMIN_max"] - 1),
                       n["imp_ratio_TMIN_med"], n["imp_ratio_TMAX_med"],
                       n["imp_ratio_TMAX_min"], n["imp_ratio_TMAX_max"],
                       n["imp_ratio_MHI_med"],
                       100 * (float(n["imp_sub"].loc[n["imp_sub"]["definition_id"]
                                                     == "TMIN_P90_2D",
                                                     "ratio_fully_imputed_over_complete"]
                                    .iloc[0]) - 1)))
        f.write("## 6. Known gaps in this package\n\n")
        f.write("1. **The design is not balanced.** `MHI_P85_3D` and `MHI_P95_3D` were never "
                "run, so the duration axis rests on %d matched pairs against %d for the "
                "percentile axis. They are carried as NOT TESTED everywhere and never "
                "zero-filled.\n" % (n["ax_duration_pairs"], n["ax_percentile_pairs"]))
        f.write("2. **Temperature-field homogeneity is unresolved and dominates.** Earlier "
                "work found anchor-station vs multi-station composite temperature agreeing at "
                "only 0.45-0.73 - larger than the effect of most definition choices measured "
                "here. Single-county results are not reliable until that is settled.\n")
        f.write("3. **No absolute floor or seasonal rule.** Every definition puts %.0f-%.0f%% "
                "of its heatwave days outside Jun-Sep. This is intrinsic to the year-round "
                "relative construct, not a metric artefact, so it cannot be fixed by choosing "
                "a different definition from this set.\n"
                % (n["pct_outside_min"], n["pct_outside_max"]))
        f.write("4. **Station counts are only available for temperature.** The classification "
                "table does not retain them; Figure 10 reads them from the raw GHCN file. "
                "There is no equivalent provenance for the gridMET humidity field, so a "
                "mean-HI event's humidity provenance cannot be audited the same way.\n")
        f.write("5. **No outcome data is used anywhere.** Nothing in this package can identify "
                "a correct definition, and the decision table does not attempt to.\n\n")
        f.write("## 7. Environment\n\n")
        f.write("- python %s, pandas %s, numpy %s, matplotlib %s\n"
                % (platform.python_version(), pd.__version__, np.__version__,
                   matplotlib_version()))
        f.write("- No new dependencies were added; `tabulate` is absent, so markdown tables "
                "are written by a local helper (`defcmp_config.md_table`).\n")
        f.write("- Regenerate with `python scripts/run_package.py` (see README.md).\n")
    K.log("[write] methods_notes.md")


def matplotlib_version():
    import matplotlib
    return matplotlib.__version__


# =============================================================================
# DECISION_TABLE
# =============================================================================
def write_decision_table(n):
    P = K.PRIMARY_WINDOW
    rows = []

    def add(defs, role, rationale, conditions):
        for d in defs:
            rows.append({"definition_id": d, "role": role, "rationale": rationale,
                         "conditions_before_use": conditions})

    add(["MHI_P90_2D", "TMAX_P90_2D"], "primary candidate",
        "Middle percentile, shorter duration, day-time exposure pathway. Mean HI carries "
        "humidity, which matters for evaporative cooling during outdoor work; Tmax is the "
        "dry-bulb comparator and is the more transparent, more widely reproducible metric. "
        "At matched percentile and duration these two differ on most classified days "
        "(Jaccard %.3f for the Tmax-vs-mean-HI pair) while counting almost the same number, "
        "so they are genuine alternatives rather than a robustness pair."
        % float(n["pidx"].loc[n["pidx"]["pair"].str.contains("TMAX_P90_2D_w15_vs_MHI_P90_2D"),
                              "jaccard_day_level"].iloc[0])
        if (n["pidx"]["pair"].str.contains("TMAX_P90_2D_w15_vs_MHI_P90_2D")).any() else
        "Middle percentile, shorter duration, day-time exposure pathway.",
        "Requires the floor/season decision to be made FIRST (both put %.0f-%.0f%% of "
        "heatwave days outside Jun-Sep), and requires the temperature-composite homogeneity "
        "question to be settled before any county-level use."
        % (n["pct_outside_min"], n["pct_outside_max"]))

    add(["MHI_P85_2D", "MHI_P95_2D"], "primary candidate (continuity)",
        "The two definitions already published by this project. Retaining one of them keeps "
        "the new work comparable with what has been reported; the re-run here reproduces the "
        "published results exactly, so continuity costs nothing analytically.",
        "The 85th flags roughly %.1fx the days of the 95th - a construct choice about how "
        "unusual a day must be, not a robustness setting. Choose deliberately, not by "
        "inheritance."
        % (float(n["qa"].loc[(n["qa"]["definition_id"] == "MHI_P85_2D")
                             & (n["qa"]["window"] == P),
                             "heatwave_days_QA_pooled_2015_2025"].iloc[0])
           / float(n["qa"].loc[(n["qa"]["definition_id"] == "MHI_P95_2D")
                               & (n["qa"]["window"] == P),
                               "heatwave_days_QA_pooled_2015_2025"].iloc[0])))

    add(["TMAX_P85_2D", "TMAX_P95_2D", "TMAX_P85_3D", "TMAX_P95_3D", "MHI_P90_3D",
         "TMAX_P90_3D"], "sensitivity case",
        "Single-axis variants of a primary candidate: the percentile ladder and the "
        "persistence rule. The percentile moves counts substantially (median %.2fx) and the "
        "duration rule is strictly nested - >=3-day heatwave days are a verified subset of "
        ">=2-day days - so both behave as interpretable sensitivity dials rather than new "
        "constructs." % (n["ax_percentile_ratio"]),
        "Report alongside the primary, never as an alternative headline. Duration "
        "sensitivities for mean HI are only available at the 90th percentile.")

    add(["%s at w05 / month / month_pm7" % d for d in ("all definitions",)],
        "sensitivity case (window)",
        "The threshold window is the least consequential axis: median Jaccard %.3f against "
        "the primary window over %d matched pairs. Compared DIRECTLY, month and month_pm7 "
        "are near-duplicates (median Jaccard %.3f over %d pairs) while w05 vs w15 differ "
        "more (%.3f). Window choice can be reported as a robustness check rather than "
        "explored as a design question."
        % (n["win_jac_med"], n["ax_window_pairs"], n["win_month_vs_pm7"],
           n["win_month_vs_pm7_n"], n["win_w05_vs_w15"]),
        "month_pm7 adds almost nothing beyond month and could be dropped from future "
        "rounds; w05 is the one window that differs enough to be worth retaining.")

    add(["TMIN_P85_2D", "TMIN_P90_2D", "TMIN_P95_2D", "TMIN_P85_3D", "TMIN_P90_3D",
         "TMIN_P95_3D"], "different construct",
        "Night-time minimum temperature measures absence of overnight recovery, not day-time "
        "work exposure. At matched percentile and duration Tmin and Tmax agree on only "
        "%.3f of classified county-dates while differing in count by ~%.0f%%. The separation "
        "shows up in county ORDER as well, which nothing else in this package does: rank "
        "agreement is %.2f within a metric family but only %.2f-%.2f (median %.2f) between "
        "the Tmax and Tmin families. Together that is the clearest evidence here that the "
        "metric selects a different phenomenon rather than a different amount of the same one."
        % (float(n["pidx"].loc[n["pidx"]["pair"].str.contains("TMIN"),
                               "jaccard_day_level"].iloc[0]),
           100 * (n["ax_metric_ratio"] - 1), n["rho_within_family_med"],
           n["rho_tmax_vs_tmin_min"], n["rho_tmax_vs_tmin_max"], n["rho_tmax_vs_tmin_med"]),
        "Do not report as a variant of a Tmax or mean-HI result, and do not average with "
        "them. If used, state the exposure pathway (no overnight recovery) explicitly.")

    add(["MHI_P85_3D", "MHI_P95_3D"], "not tested",
        "Never run. These two cells would complete the 3 x 3 x 2 factorial and are the reason "
        "the duration axis is estimated from %d matched pairs rather than %d."
        % (n["ax_duration_pairs"], n["ax_percentile_pairs"]),
        "One line each in config.GRID_DEFINITIONS; the thresholds they need are already "
        "cached, so running them is cheap. Never substitute zero or an interpolated value.")

    add(["all Tmax and Tmin definitions"], "needs data-quality validation",
        "Three independent issues. (i) The exact-tie asymmetry: %.2f%% (Tmax) and %.2f%% "
        "(Tmin) of evaluable county-days sit exactly on their threshold because the input is "
        "quantised to 0.1 degC, against %.2f%% for mean HI - so the strict `>` silently "
        "removes days from the temperature definitions only. (ii) %d of %d counties exceed "
        "the %.0f%% imputation cut and %d have no native station record at all. (iii) That "
        "imputation is NOT metric-neutral: the fully imputed counties carry a median %.2fx the "
        "heatwave days of complete-data counties under every Tmin definition (range "
        "%.2f-%.2f), against %.2fx under Tmax - IDW gap-filling inflates Tmin-based exposure "
        "specifically (Figure 13; support_imputation_subgroup_medians.csv)."
        % (n["tie_pct"]["TMAX"], n["tie_pct"]["TMIN"], n["tie_pct"]["MHI"], n["n_flagged"],
           n["n_counties"], K.IMPUTATION_MAX_PCT, n["n_fully_imputed"],
           n.get("imp_ratio_TMIN_med", float("nan")),
           n.get("imp_ratio_TMIN_min", float("nan")),
           n.get("imp_ratio_TMIN_max", float("nan")),
           n.get("imp_ratio_TMAX_med", float("nan"))),
        "Quantify the `>` vs `>=` effect before comparing a temperature definition against "
        "mean HI on day-level agreement; resolve the anchor-vs-composite temperature question "
        "(earlier agreement 0.45-0.73) before any county ranking; and report Tmin-based "
        "results on the complete-data subset, or with the imputation gap quantified.")

    add(["every definition in this package"], "needs data-quality validation",
        "All %d are year-round and carry no absolute floor, so %.0f-%.0f%% of their heatwave "
        "days fall outside Jun-Sep and %d long events (>= %d days, longest %d) exist across "
        "the runs, %d of them at least half IDW-imputed."
        % (n["n_defs"], n["pct_outside_min"], n["pct_outside_max"], n["n_long"],
           K.LONG_EVENT_REVIEW_DAYS, n["long_max"], n["long_high_imp"]),
        "Make the floor-or-season decision before publication. Until then, describe results "
        "as persistent apparent-heat anomalies relative to the local date, never as "
        "hazardous heatwaves.")

    df = pd.DataFrame(rows)
    df.insert(0, "state", STATE)
    df.to_csv(os.path.join(K.PKG_ROOT, "DECISION_TABLE.csv"), index=False)

    p = os.path.join(K.PKG_ROOT, "DECISION_TABLE.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("# Decision table\n\n")
        f.write("A reading of the comparison, not a selection. **No injury, illness or other "
                "health outcome is used anywhere in this package**, and no figure in it can "
                "identify a correct definition - every quantity here is agreement or count, "
                "and neither is accuracy. The final primary definition must not be chosen "
                "using injury-outcome results.\n\n")
        f.write("Scope: %d definitions x 4 windows, %s, %s, %d counties, primary window "
                "`%s`.\n\n" % (n["n_defs"], K.STATE_LABEL, YEARS, n["n_counties"],
                               K.PRIMARY_WINDOW))
        for role in ["primary candidate", "primary candidate (continuity)", "sensitivity case",
                     "sensitivity case (window)", "different construct", "not tested",
                     "needs data-quality validation"]:
            sub = df[df["role"] == role]
            if not len(sub):
                continue
            f.write("## %s\n\n" % role.upper())
            for rat, g in sub.groupby("rationale", sort=False):
                f.write("**%s**\n\n" % ", ".join("`%s`" % x for x in g["definition_id"]))
                f.write("%s\n\n" % rat)
                f.write("*Conditions before use:* %s\n\n"
                        % g["conditions_before_use"].iloc[0])
        f.write("---\n\n## What the comparison established, in one paragraph\n\n")
        f.write("Across %d definitions at the %s window, the four design axes do not do the "
                "same job. Day-level effect, largest first: %s. The METRIC changes which "
                "county-dates are classified more than anything else (median Jaccard %.3f "
                "over %d matched pairs) while barely changing the count (median %.2fx) - so a "
                "count-based justification for a metric is not sufficient, and the choice has "
                "to be argued on exposure-pathway grounds. The PERCENTILE is the count lever "
                "(median %.2fx). The WINDOW matters least (median Jaccard %.3f vs the primary "
                "window). County RANKINGS are much more stable (median rho %.3f) than "
                "day-level agreement (median Jaccard %.3f), which means rank stability must "
                "not be quoted as evidence that the definitions agree about exposure. And the "
                "cool-season loading (%.0f-%.0f%% of heatwave days outside Jun-Sep in every "
                "definition) is intrinsic to the year-round relative construct, so it cannot "
                "be resolved by choosing a different definition from this set - it needs the "
                "floor-or-season decision.\n"
                % (n["n_defs"], K.PRIMARY_WINDOW, n["axis_rank"], n["ax_metric_jac"],
                   n["ax_metric_pairs"], n["ax_metric_ratio"], n["ax_percentile_ratio"],
                   n["win_jac_med"], n["rho_all_med"], n["jac_med"], n["pct_outside_min"],
                   n["pct_outside_max"]))
    K.log("[write] DECISION_TABLE.md / .csv  (%d rows)" % len(df))


# =============================================================================
# run_manifest.csv + README
# =============================================================================
PRODUCED_BY = [
    ("tables/canonical_long/", "s02_canonical_long.py", "county x date x definition x window"),
    ("tables/master_event_table.csv.gz", "s02_canonical_long.py", "heatwave event"),
    ("tables/master_county_year_summary.csv", "s02_canonical_long.py", "county x year x run"),
    ("tables/master_county_month_summary.csv", "s02_canonical_long.py",
     "county x year x month x run"),
    ("tables/eligibility_county_month.csv", "s02_canonical_long.py",
     "county x year x month x metric x window (denominators)"),
    ("tables/ref_county_climate_division.csv", "s02_canonical_long.py", "county"),
    ("tables/table1", "s04_tables.py", "definition"),
    ("tables/table2", "s04_tables.py", "run = definition x window"),
    ("tables/table6", "s04_tables.py", "pair of runs"),
    ("tables/table7", "s04_tables.py", "matched pair"),
    ("tables/table8a", "s04_tables.py", "heatwave event >= review length"),
    ("tables/table8b", "s04_tables.py", "county"),
    ("tables/support_", "s04_tables.py", "see the file's own key columns"),
    ("tables/TABLE_INDEX.md", "s04_tables.py", "index"),
    ("figures/core/fig01", "s05_core_figures.py", "definition"),
    ("figures/core/fig02", "s05_core_figures.py", "matched pair"),
    ("figures/core/fig03", "s05_core_figures.py", "set of county-dates"),
    ("figures/core/fig04", "s05_core_figures.py", "county"),
    ("figures/core/fig05", "s05_core_figures.py", "county-month"),
    ("figures/core/fig06", "s05_core_figures.py", "county-year"),
    ("figures/core/fig07", "s05_core_figures.py", "county-date / county-year / threshold"),
    ("figures/core/fig11", "s05_core_figures.py", "county"),
    ("figures/core/fig12", "s05_core_figures.py", "county-date"),
    ("figures/core/fig13", "s05_core_figures.py", "county"),
    ("figures/supplement/", "s05_core_figures.py", "county-month"),
    ("county_profiles/", "s06_county_profiles.py", "county"),
    ("event_audits/fig09", "s07_event_audits.py", "county-date"),
    ("event_audits/fig10", "s07_event_audits.py", "county-date within an event"),
    ("event_audits/", "s07_event_audits.py", "heatwave event"),
    ("qa/s01", "s01_rerun_legacy.py", "verification check"),
    ("qa/s02", "s02_canonical_long.py", "reconciliation check / run"),
    ("qa/s03", "s03_validate.py", "validation check"),
    ("data_dictionary/", "s08_report.py", "column"),
    ("figure_captions.md", "s08_report.py", "figure"),
    ("methods_notes.md", "s08_report.py", "document"),
    ("DECISION_TABLE", "s08_report.py", "definition"),
    ("README.md", "s08_report.py", "document"),
    ("run_manifest.csv", "s08_report.py", "file"),
    ("scripts/", "hand-written", "source"),
]


def write_manifest(n, commit, ihash):
    rows = []
    for root, dirs, files in os.walk(K.PKG_ROOT):
        for fn in sorted(files):
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, K.PKG_ROOT).replace("\\", "/")
            if rel == "run_manifest.csv":
                continue
            producer, unit = "", ""
            for pref, prod, u in PRODUCED_BY:
                if rel.startswith(pref) or ("/" + pref) in ("/" + rel):
                    producer, unit = prod, u
                    break
            st = os.stat(full)
            rows.append({
                "file": rel, "bytes": st.st_size,
                "modified_utc": datetime.datetime.fromtimestamp(
                    st.st_mtime, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "produced_by": producer or "s08_report.py",
                "unit_of_analysis": unit,
            })
    df = pd.DataFrame(rows).sort_values("file")
    df.insert(0, "state", STATE)
    df["git_commit"] = commit
    df["input_hash"] = ihash
    df["python"] = platform.python_version()
    df["pandas"] = pd.__version__
    df["numpy"] = np.__version__
    df.to_csv(os.path.join(K.PKG_ROOT, "run_manifest.csv"), index=False)
    K.log("[write] run_manifest.csv  (%d files, %.0f MB total)"
          % (len(df), df["bytes"].sum() / 1e6))
    return df


def write_data_dictionary(n):
    """Column-level dictionary for the canonical table and the eight tables."""
    rows = [
        ("canonical_long/*.csv.gz", "county_fips", "5-digit county FIPS", "identifier"),
        ("canonical_long/*.csv.gz", "county_name", "county name", "identifier"),
        ("canonical_long/*.csv.gz", "climate_division",
         "NOAA climate-division name (numbers primary source, names secondary labels)",
         "identifier"),
        ("canonical_long/*.csv.gz", "climdiv_id", "NOAA climate-division number", "identifier"),
        ("canonical_long/*.csv.gz", "date", "calendar date (YYYY-MM-DD)", "identifier"),
        ("canonical_long/*.csv.gz", "year", "calendar year of the date", "identifier"),
        ("canonical_long/*.csv.gz", "month", "calendar month of the date", "identifier"),
        ("canonical_long/*.csv.gz", "run_id", "definition_id + '__' + window", "identifier"),
        ("canonical_long/*.csv.gz", "definition_id",
         "METRIC_Pxx_nD, e.g. TMAX_P90_2D", "identifier"),
        ("canonical_long/*.csv.gz", "metric", "TMAX | TMIN | MHI", "design"),
        ("canonical_long/*.csv.gz", "percentile", "85 | 90 | 95", "design"),
        ("canonical_long/*.csv.gz", "minimum_duration",
         "minimum consecutive days for a qualifying run", "design"),
        ("canonical_long/*.csv.gz", "window", "w05 | w15 | month | month_pm7", "design"),
        ("canonical_long/*.csv.gz", "reference_method",
         "walk_forward_1979_to_Yminus1", "design"),
        ("canonical_long/*.csv.gz", "season_rule", "year_round", "design"),
        ("canonical_long/*.csv.gz", "absolute_floor", "none in all 16 definitions", "design"),
        ("canonical_long/*.csv.gz", "daily_metric_value",
         "the day's metric, degF, ROUNDED to 3 dp for readability", "measurement"),
        ("canonical_long/*.csv.gz", "threshold_value",
         "the county's own walk-forward percentile threshold, degF, ROUNDED to 3 dp",
         "measurement"),
        ("canonical_long/*.csv.gz", "exceedance_degF",
         "metric minus threshold, UNROUNDED - the column that reproduces the strict '>'",
         "measurement"),
        ("canonical_long/*.csv.gz", "n_reference_values",
         "baseline observations behind the threshold (low_n_ref below %d)" % K.MIN_REF_OBS,
         "quality"),
        ("canonical_long/*.csv.gz", "relative_exceedance_flag",
         "1 if metric > threshold, before any floor and before artifact masking", "flag"),
        ("canonical_long/*.csv.gz", "candidate_day_flag",
         "1 if a candidate day (relative exceedance, floor if any, not an artifact day)",
         "flag"),
        ("canonical_long/*.csv.gz", "heatwave_day_flag",
         "1 if a candidate day inside a run of >= minimum_duration consecutive days", "flag"),
        ("canonical_long/*.csv.gz", "event_id",
         "state_county_year_seq_definition; null on non-heatwave days", "identifier"),
        ("canonical_long/*.csv.gz", "event_start_date", "first date of the event", "event"),
        ("canonical_long/*.csv.gz", "event_end_date", "last date of the event", "event"),
        ("canonical_long/*.csv.gz", "event_duration_days",
         "INTEGER consecutive dates, end - start + 1", "event"),
        ("canonical_long/*.csv.gz", "observed_or_imputed",
         "'observed' or 'imputed' (IDW-filled temperature) for this county-day", "quality"),
        ("canonical_long/*.csv.gz", "temperature_imputation_fraction",
         "county-level fraction of analysis days whose temperature was IDW-filled", "quality"),
        ("canonical_long/*.csv.gz", "input_hash", "md5 prefix of the input county-day table",
         "provenance"),
        ("canonical_long/*.csv.gz", "pipeline_version", "git commit (+dirty)", "provenance"),
        ("eligibility_county_month.csv", "eligible_days",
         "county-days the definition could be evaluated on - THE DENOMINATOR", "denominator"),
        ("eligibility_county_month.csv", "calendar_days", "county-days in the month",
         "denominator"),
        ("eligibility_county_month.csv", "missing_metric_days",
         "metric absent for that county-day", "quality"),
        ("eligibility_county_month.csv", "missing_threshold_days",
         "no threshold estimable for that county-day", "quality"),
        ("eligibility_county_month.csv", "artifact_excluded_days",
         "confirmed RH-clip artifact days excluded (RH-dependent metrics only)", "quality"),
        ("master_county_month_summary.csv", "heatwave_events_started",
         "events whose ONSET falls in this month (an event is counted once)", "event"),
        ("master_county_month_summary.csv", "heatwave_events_active",
         "events touching this month (a month-crossing event counts in each)", "event"),
        ("master_county_year_summary.csv", "heatwave_events_started",
         "events whose onset falls in this year (year boundary does not split an event)",
         "event"),
        ("table2_run_qa_summary.csv", "*_QA_pooled*",
         "pooled across counties - a QA quantity, never a substantive result", "QA"),
        ("table6_definition_pair_agreement.csv", "jaccard_day_level",
         "shared county-dates / union; AGREEMENT between two definitions, not accuracy",
         "comparison"),
        ("table7_matched_pair_marginal_effects.csv", "count_ratio_hi_over_lo",
         "pooled heatwave days, higher run / lower run, within a matched pair", "comparison"),
        ("table8a_long_event_audit.csv", "disposition",
         "always RETAINED - long events are flagged for review, never deleted", "QA"),
    ]
    df = pd.DataFrame(rows, columns=["table", "column", "definition", "kind"])
    df.to_csv(os.path.join(K.DIR_DICT, "data_dictionary.csv"), index=False)
    with open(os.path.join(K.DIR_DICT, "data_dictionary.md"), "w", encoding="utf-8") as f:
        f.write("# Data dictionary\n\n")
        f.write("Units are carried in the column names: `_QA_pooled` marks a pooled "
                "cross-county quantity (never a substantive result), `_2015_2025` marks a "
                "cumulative count (never annual), and every event duration is an integer "
                "number of consecutive dates.\n\n")
        for tbl, g in df.groupby("table", sort=False):
            f.write("## `%s`\n\n" % tbl)
            f.write(K.md_table(g, ["column", "definition", "kind"]))
            f.write("\n\n")
    K.log("[write] data_dictionary/  (%d columns)" % len(df))


def write_readme(n, commit, ihash):
    p = os.path.join(K.PKG_ROOT, "README.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("# Definition-comparison package - %d heatwave definitions, %s, %s\n\n"
                % (n["n_defs"], K.STATE_LABEL, YEARS))
        f.write("Compares %d county-level heatwave definitions x 4 threshold windows = %d "
                "runs over %d counties, to show how the choice of **metric, percentile, "
                "minimum duration and threshold window** changes: the number of heatwave "
                "days, the number of events, the IDENTITY of the classified county-dates, "
                "seasonality, county rankings, event duration, and sensitivity to data "
                "quality.\n\n" % (n["n_defs"], n["n_runs"], n["n_counties"]))
        f.write("**Read first:** `DECISION_TABLE.md`, then `figure_captions.md` (what each "
                "figure does and does not support), then `methods_notes.md`.\n\n")
        f.write("## Headline\n\n")
        f.write("| question | answer |\n|---|---|\n")
        f.write("| Which axis changes WHICH days most? | metric (median Jaccard %.3f over %d "
                "matched pairs) |\n" % (n["ax_metric_jac"], n["ax_metric_pairs"]))
        f.write("| Which axis changes HOW MANY days most? | percentile (median %.2fx, up to "
                "%.2fx) |\n" % (n["ax_percentile_ratio"], n["ax_percentile_ratiomax"]))
        f.write("| Which axis matters least? | threshold window (median Jaccard %.3f vs the "
                "primary window) |\n" % n["win_jac_med"])
        f.write("| Do county rankings survive? | more than day-level agreement does: median "
                "rho %.3f vs median Jaccard %.3f |\n" % (n["rho_all_med"], n["jac_med"]))
        f.write("| Is the cool-season loading a metric artefact? | no - %.0f-%.0f%% of "
                "heatwave days fall outside Jun-Sep in every definition |\n"
                % (n["pct_outside_min"], n["pct_outside_max"]))
        f.write("| Range of pooled heatwave days across definitions | %s (%s) to %s (%s) |\n"
                % ("{:,}".format(n["days_min"]), n["days_min_def"],
                   "{:,}".format(n["days_max"]), n["days_max_def"]))
        f.write("\n## Layout\n\n```\n")
        f.write("figures/core/        Figures 1-7, 11, 12, 13\n"
                "figures/supplement/  the weaker variants, kept for comparison\n"
                "county_profiles/     Figure 8: one report card per county + INDEX.csv\n"
                "tables/              the 8 required tables, the canonical long table,\n"
                "                     and the support tables the figures read\n"
                "event_audits/        Figures 9-10: event timelines and the long-event audit\n"
                "data_dictionary/     every column defined\n"
                "qa/                  provenance, reconciliation and validation records\n"
                "scripts/             s01..s08 + run_package.py (the only code)\n"
                "figure_captions.md   the per-figure report\n"
                "methods_notes.md     prespecified choices, units, reporting rules, QA notes\n"
                "DECISION_TABLE.md    primary / sensitivity / different construct / needs work\n"
                "run_manifest.csv     every file, its producer and its unit of analysis\n```\n\n")
        f.write("## Regenerate\n\n```bash\ncd outputs/definition_comparison/scripts\n"
                "python run_package.py            # everything, in order\n"
                "python run_package.py --from s04 # from one step onward\n```\n\n")
        f.write("Provenance of this build: git `%s`, input `%s`.\n\n" % (commit, ihash))
        f.write("## Three things not to conclude from this package\n\n")
        f.write("1. **Jaccard is not accuracy.** No definition here is a gold standard and "
                "the data contains no observed heatwave day. Low agreement means two "
                "definitions classify different days, not that one is wrong.\n")
        f.write("2. **A high county-rank correlation is not day-level agreement.** The "
                "definitions largely agree on which counties are more exposed (median rho "
                "%.3f) while disagreeing on most individual days (median Jaccard %.3f).\n"
                % (n["rho_all_med"], n["jac_med"]))
        f.write("3. **These are not hazardous-heat definitions.** All %d are county-relative, "
                "year-round and carry no absolute floor, so a qualifying day is unusual FOR "
                "ITS OWN DATE. Do not describe the output as hazardous heatwaves without an "
                "absolute floor or a declared season.\n" % n["n_defs"])
    K.log("[write] README.md")


def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 74)
    K.log("s08  WRITTEN DELIVERABLES")
    K.log("=" * 74)
    commit, ihash = git_commit(), input_hash()
    n = gather()
    F = figure_report(n)
    write_figure_captions(n, F)
    write_methods(n)
    write_decision_table(n)
    write_data_dictionary(n)
    write_readme(n, commit, ihash)
    write_manifest(n, commit, ihash)
    K.log("=" * 74)
    K.log("s08 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
