"""
=============================================================================
r07  --  agreement, absolute gates, monthly rates and geography.
=============================================================================
Everything here is built from the r06 outputs, so every number in a figure has
a saved table behind it.

WHAT CHANGES RELATIVE TO THE CURRENT PACKAGE

  monthly rates      each construct family uses ITS OWN valid-record
                     denominator. The equality of the three denominators is a
                     tested result (qa/eligibility_denominator_comparison.csv),
                     not an assumption carried over from another package.
  seasonality        June-September, May and October, and November-April are
                     reported separately. The shoulder months are no longer
                     merged into a single "outside summer" category.
  "flat"             a quantitative flatness criterion is defined and evaluated.
                     The word is used only where the criterion is met.
  event counts       the median ANNUAL county-level event count replaces the
                     statewide pooled event total as the reported quantity.
                     Pooled totals survive only in columns ending _QA.
  gates              80 degF and 90 degF are ABSOLUTE DAILY-HIGH GATES. They are
                     not National Weather Service advisory thresholds, and a
                     gate is not a correction: it changes the construct from a
                     purely relative one to a hybrid relative-and-absolute one.
  Jaccard            agreement between two constructs on the set of classified
                     county-dates. Never accuracy. Nested percentiles and
                     durations make some agreements structural.

OUTPUTS
  tables/definition_agreement_jaccard.csv            (long form)
  tables/definition_agreement_jaccard_matrix.csv     (square form)
  tables/construct_summary.csv
  tables/monthly_classification_rates.csv
  tables/seasonal_classification_shares.csv
  tables/absolute_gate_effect.csv
  tables/absolute_vs_relative.csv
  tables/county_gate_effect.csv
  tables/annual_event_count_distribution.csv
  tables/event_duration_distribution.csv
  qa/flatness_criterion.csv
=============================================================================
"""
import os
import sys
import time
import itertools

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K
import config as C                                          # noqa: E402

# A monthly rate profile is called FLAT only if BOTH hold. Prespecified here so
# the word is a measurement rather than an impression.
FLATNESS_MAX_MIN_RATIO = 1.5
FLATNESS_MAX_CV = 0.15


def load_daysets():
    z = np.load(os.path.join(K.DIR_QA, "_classified_day_sets.npz"), allow_pickle=True)
    return {k: z[k] for k in z.files if k != "counties"}


def jaccard(a, b):
    inter = np.intersect1d(a, b, assume_unique=True).size
    union = a.size + b.size - inter
    return inter / union if union else np.nan


def short_label(con):
    """Reader-facing short label carrying metric, percentile and duration."""
    if con["family"] == "absolute":
        return "TX->%d-D%d" % (int(con["absolute_gate_f"]), con["duration_days"])
    base = "TX-P%d-D%d" % (con["percentile"], con["duration_days"])
    if con["family"] == "hybrid":
        base += "+A%d" % int(con["absolute_gate_f"])
    return base


def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 78)
    K.log("r07  agreement, absolute gates, monthly rates, geography")
    K.log("=" * 78)

    cons = {c["construct_id"]: c for c in K.constructs_primary()}
    sets = load_daysets()
    K.log("classified county-date sets loaded for %d constructs (%s county-dates)"
          % (len(sets), "{:,}".format(sum(len(v) for v in sets.values()))))

    ann = pd.read_csv(os.path.join(K.DIR_TABLES, "county_annual_all_constructs.csv"),
                      dtype={"county_fips": str})
    mon = pd.read_csv(os.path.join(K.DIR_TABLES, "county_monthly_all_constructs.csv"),
                      dtype={"county_fips": str})
    cat = pd.concat([pd.read_csv(os.path.join(K.DIR_TABLES, f),
                                 dtype={"county_fips": str})
                     for f in ("individual_relative_warm_spell_events.csv",
                               "individual_hybrid_heat_events.csv",
                               "individual_absolute_hot_spells.csv")],
                    ignore_index=True)
    ref = pd.read_csv(os.path.join(C.state_output_dir(K.TEST_STATE),
                                   "coverage_and_imputation_report.csv"),
                      dtype={"county_fips": str})
    ref["fully_imputed_county"] = (ref["fully_imputed_county"].astype(str).str.lower()
                                   .isin(("true", "1", "yes")))

    # =========================================================================
    # 1. per-construct summary -- annual county-level distributions are primary
    # =========================================================================
    rows = []
    for cid, con in cons.items():
        a = ann[ann["construct_id"] == cid]
        m = mon[mon["construct_id"] == cid]
        c = cat[cat["construct_id"] == cid]
        if not len(a):
            continue
        cum = a.groupby("county_fips")["annual_classified_day_count"].sum()
        season = (m.groupby("season")["heat_event_day_count"].sum()
                  .reindex(["warm", "shoulder", "cool"], fill_value=0))
        tot = float(season.sum())
        by_month = (m.groupby("month")["heat_event_day_count"].sum()
                    .reindex(range(1, 13), fill_value=0))
        rows.append(dict(
            construct_id=cid, construct_family=con["family"],
            short_label=short_label(con), reader_name=con["reader_name"],
            legacy_definition_id=con["legacy_definition_id"],
            percentile=con["percentile"], duration_days=con["duration_days"],
            absolute_gate_f=con["absolute_gate_f"],
            threshold_window=con["window"] or "none",
            day_label=con["day_label"],
            # ---- primary, county-level quantities ---------------------------
            median_annual_classified_days=float(
                a["annual_classified_day_count"].median()),
            p25_annual_classified_days=float(
                a["annual_classified_day_count"].quantile(0.25)),
            p75_annual_classified_days=float(
                a["annual_classified_day_count"].quantile(0.75)),
            median_annual_event_count=float(a["annual_event_count"].median()),
            p25_annual_event_count=float(a["annual_event_count"].quantile(0.25)),
            p75_annual_event_count=float(a["annual_event_count"].quantile(0.75)),
            max_annual_event_count=int(a["annual_event_count"].max()),
            median_cumulative_classified_days_per_county=float(cum.median()),
            counties_with_any_classified_day=int((cum > 0).sum()),
            median_event_duration_days=float(c["event_duration_days"].median())
            if len(c) else np.nan,
            p75_event_duration_days=float(c["event_duration_days"].quantile(0.75))
            if len(c) else np.nan,
            max_event_duration_days=int(c["event_duration_days"].max()) if len(c) else 0,
            # ---- seasonality, three categories ------------------------------
            pct_days_june_september=round(100.0 * season["warm"] / tot, 2) if tot else np.nan,
            pct_days_may_and_october=round(100.0 * season["shoulder"] / tot, 2)
            if tot else np.nan,
            pct_days_november_april=round(100.0 * season["cool"] / tot, 2)
            if tot else np.nan,
            peak_month=K.MONTH_ABBR[int(by_month.idxmax()) - 1] if tot else "",
            # ---- rate --------------------------------------------------------
            classified_days_per_1000_valid=round(
                1000.0 * m["heat_event_day_count"].sum()
                / m["valid_daily_observation_count"].sum(), 3)
            if m["valid_daily_observation_count"].sum() else np.nan,
            valid_daily_observations=int(m["valid_daily_observation_count"].sum()),
            pct_classified_days_imputed=round(
                100.0 * m["imputed_classified_day_count"].sum()
                / m["heat_event_day_count"].sum(), 2)
            if m["heat_event_day_count"].sum() else np.nan,
            # ---- pooled totals, QA only --------------------------------------
            classified_county_dates_QA=int(m["heat_event_day_count"].sum()),
            events_QA=int(len(c)),
        ))
    summ = pd.DataFrame(rows)
    summ.to_csv(os.path.join(K.DIR_TABLES, "construct_summary.csv"), index=False)
    K.log("[table] construct_summary.csv  (%d constructs)" % len(summ))

    # =========================================================================
    # 2. monthly classification rates, construct-specific denominators
    # =========================================================================
    r = (mon.groupby(["construct_id", "construct_family", "month", "season"],
                     observed=True)
         .agg(classified_days=("heat_event_day_count", "sum"),
              valid_daily_observations=("valid_daily_observation_count", "sum"),
              counties=("county_fips", "nunique")).reset_index())
    r["classified_days_per_1000_valid"] = (
        1000.0 * r["classified_days"] / r["valid_daily_observations"]).round(3)
    r["month_name"] = r["month"].map(lambda m: K.MONTH_ABBR[m - 1])
    r = r.merge(summ[["construct_id", "short_label", "percentile", "duration_days",
                      "absolute_gate_f", "threshold_window", "day_label"]],
                on="construct_id", how="left")
    r["denominator_definition"] = r["construct_family"].map({
        "relative": "the daily high is present AND a historical threshold exists",
        "hybrid": "relative eligibility AND the absolute gate is evaluable",
        "absolute": "the daily high is present"})
    r.to_csv(os.path.join(K.DIR_TABLES, "monthly_classification_rates.csv"), index=False)
    K.log("[table] monthly_classification_rates.csv  (%d rows)" % len(r))

    # ---- the flatness criterion, evaluated ---------------------------------
    frows = []
    for cid, g in r.groupby("construct_id", observed=True):
        v = g.sort_values("month")["classified_days_per_1000_valid"].to_numpy()
        v = v[np.isfinite(v)]
        if v.size < 12 or v.min() <= 0:
            ratio, cv = np.inf, np.inf
        else:
            ratio, cv = float(v.max() / v.min()), float(v.std(ddof=0) / v.mean())
        flat = bool(ratio <= FLATNESS_MAX_MIN_RATIO and cv <= FLATNESS_MAX_CV)
        frows.append(dict(construct_id=cid,
                          construct_family=cons[cid]["family"],
                          short_label=short_label(cons[cid]),
                          max_month_rate=round(float(v.max()), 3) if v.size else np.nan,
                          min_month_rate=round(float(v.min()), 3) if v.size else np.nan,
                          max_over_min_ratio=round(ratio, 3) if np.isfinite(ratio) else np.inf,
                          coefficient_of_variation=round(cv, 4)
                          if np.isfinite(cv) else np.inf,
                          criterion_max_over_min=FLATNESS_MAX_MIN_RATIO,
                          criterion_coefficient_of_variation=FLATNESS_MAX_CV,
                          meets_flatness_criterion=flat,
                          verdict="flat" if flat else "not flat"))
    fl = pd.DataFrame(frows)
    fl.to_csv(os.path.join(K.DIR_QA, "flatness_criterion.csv"), index=False)
    n_flat = int(fl["meets_flatness_criterion"].sum())
    K.log("[qa]    flatness_criterion.csv: %d of %d constructs meet the prespecified "
          "flatness criterion (max/min <= %.1f AND coefficient of variation <= %.2f)"
          % (n_flat, len(fl), FLATNESS_MAX_MIN_RATIO, FLATNESS_MAX_CV))

    # ---- season shares ------------------------------------------------------
    s = (mon.groupby(["construct_id", "construct_family", "season"], observed=True)
         .agg(classified_days=("heat_event_day_count", "sum"),
              valid_daily_observations=("valid_daily_observation_count", "sum"))
         .reset_index())
    tot = s.groupby("construct_id")["classified_days"].transform("sum")
    s["pct_of_classified_days"] = (100.0 * s["classified_days"] / tot).round(2)
    s["classified_days_per_1000_valid"] = (
        1000.0 * s["classified_days"] / s["valid_daily_observations"]).round(3)
    s["season_label"] = s["season"].map(K.SEASON_LABEL)
    s = s.merge(summ[["construct_id", "short_label"]], on="construct_id", how="left")
    s.to_csv(os.path.join(K.DIR_TABLES, "seasonal_classification_shares.csv"),
             index=False)
    K.log("[table] seasonal_classification_shares.csv  (%d rows)" % len(s))

    # =========================================================================
    # 3. pairwise agreement
    # =========================================================================
    ids = [c for c in sets if c in cons]
    ids.sort(key=lambda c: ({"relative": 0, "hybrid": 1, "absolute": 2}[cons[c]["family"]],
                            cons[c]["percentile"] or 0, cons[c]["duration_days"],
                            cons[c]["absolute_gate_f"] or 0))
    long_rows = []
    M = pd.DataFrame(np.nan, index=[short_label(cons[i]) for i in ids],
                     columns=[short_label(cons[i]) for i in ids])
    for a in ids:
        M.loc[short_label(cons[a]), short_label(cons[a])] = 1.0
    for a, b in itertools.combinations(ids, 2):
        j = jaccard(sets[a], sets[b])
        la, lb = short_label(cons[a]), short_label(cons[b])
        M.loc[la, lb] = M.loc[lb, la] = round(j, 4)
        ca, cb = cons[a], cons[b]
        nested = (ca["family"] == cb["family"] == "relative"
                  and ca["window"] == cb["window"]
                  and ((ca["percentile"] == cb["percentile"])
                       or (ca["duration_days"] == cb["duration_days"])))
        long_rows.append(dict(
            construct_a=a, construct_b=b, label_a=la, label_b=lb,
            family_a=ca["family"], family_b=cb["family"],
            classified_county_dates_a=int(sets[a].size),
            classified_county_dates_b=int(sets[b].size),
            shared_county_dates=int(np.intersect1d(sets[a], sets[b],
                                                   assume_unique=True).size),
            jaccard=round(j, 4),
            structurally_nested=nested,
            interpretation=("agreement on the set of classified county-dates; NOT "
                            "accuracy. Nested percentiles and durations create "
                            "subset relationships, so a high value between two "
                            "nested rules is structural.")))
    lj = pd.DataFrame(long_rows)
    lj.to_csv(os.path.join(K.DIR_TABLES, "definition_agreement_jaccard.csv"),
              index=False)
    M.to_csv(os.path.join(K.DIR_TABLES, "definition_agreement_jaccard_matrix.csv"))
    K.log("[table] definition_agreement_jaccard.csv  (%d pairs)" % len(lj))

    # =========================================================================
    # 4. the absolute gate as a modifier of the relative rule
    # =========================================================================
    grows = []
    for p in K.PERCENTILES:
        for d in K.DURATIONS:
            bid = K.rel_id(p, d)
            if bid not in sets:
                continue
            ba = ann[ann["construct_id"] == bid]
            bm = mon[mon["construct_id"] == bid]
            bs = summ[summ["construct_id"] == bid].iloc[0]
            for g in K.ABSOLUTE_GATES_F:
                hid = K.hyb_id(p, d, g)
                if hid not in sets:
                    continue
                ha = ann[ann["construct_id"] == hid]
                hs = summ[summ["construct_id"] == hid].iloc[0]
                hm = mon[mon["construct_id"] == hid]
                b_cty = ba.groupby("county_fips")["annual_classified_day_count"].sum()
                h_cty = ha.groupby("county_fips")["annual_classified_day_count"].sum()
                ret = (100.0 * h_cty / b_cty.replace(0, np.nan))
                grows.append(dict(
                    relative_construct=bid, hybrid_construct=hid,
                    label=short_label(cons[bid]), percentile=p, duration_days=d,
                    absolute_gate_f=g, threshold_window=K.PRIMARY_WINDOW,
                    pct_classified_days_retained=round(
                        100.0 * hs["classified_county_dates_QA"]
                        / bs["classified_county_dates_QA"], 2),
                    day_level_jaccard_with_no_gate=round(jaccard(sets[bid], sets[hid]), 4),
                    median_annual_event_count_no_gate=bs["median_annual_event_count"],
                    median_annual_event_count_with_gate=hs["median_annual_event_count"],
                    annual_event_count_change=round(hs["median_annual_event_count"]
                                                    - bs["median_annual_event_count"], 3),
                    median_annual_classified_days_no_gate=bs["median_annual_classified_days"],
                    median_annual_classified_days_with_gate=hs["median_annual_classified_days"],
                    annual_classified_day_change=round(
                        hs["median_annual_classified_days"]
                        - bs["median_annual_classified_days"], 3),
                    counties_with_any_day_no_gate=int((b_cty > 0).sum()),
                    counties_with_any_day_with_gate=int((h_cty > 0).sum()),
                    counties_losing_all_days=int(((b_cty > 0) & (h_cty == 0)).sum()),
                    median_county_retention_pct=round(float(ret.median()), 2),
                    p10_county_retention_pct=round(float(ret.quantile(0.10)), 2),
                    p90_county_retention_pct=round(float(ret.quantile(0.90)), 2),
                    geographic_spread_of_retention_pct=round(
                        float(ret.quantile(0.90) - ret.quantile(0.10)), 2),
                    pct_days_june_september_no_gate=bs["pct_days_june_september"],
                    pct_days_june_september_with_gate=hs["pct_days_june_september"],
                    pct_days_may_and_october_no_gate=bs["pct_days_may_and_october"],
                    pct_days_may_and_october_with_gate=hs["pct_days_may_and_october"],
                    pct_days_november_april_no_gate=bs["pct_days_november_april"],
                    pct_days_november_april_with_gate=hs["pct_days_november_april"],
                    warm_season_rate_no_gate=round(
                        1000.0 * bm.loc[bm["season"] == "warm", "heat_event_day_count"].sum()
                        / bm.loc[bm["season"] == "warm",
                                 "valid_daily_observation_count"].sum(), 3),
                    warm_season_rate_with_gate=round(
                        1000.0 * hm.loc[hm["season"] == "warm", "heat_event_day_count"].sum()
                        / hm.loc[hm["season"] == "warm",
                                 "valid_daily_observation_count"].sum(), 3),
                    cool_season_rate_no_gate=round(
                        1000.0 * bm.loc[bm["season"] == "cool", "heat_event_day_count"].sum()
                        / bm.loc[bm["season"] == "cool",
                                 "valid_daily_observation_count"].sum(), 3),
                    cool_season_rate_with_gate=round(
                        1000.0 * hm.loc[hm["season"] == "cool", "heat_event_day_count"].sum()
                        / hm.loc[hm["season"] == "cool",
                                 "valid_daily_observation_count"].sum(), 3),
                    construct_change=("the gate changes the construct from a purely "
                                      "relative warm spell to a hybrid "
                                      "relative-and-absolute heat event; it is not a "
                                      "correction to the relative rule"),
                    gate_note=("an absolute daily-high gate chosen for this "
                               "sensitivity test; NOT a National Weather Service "
                               "advisory threshold")))
    ge = pd.DataFrame(grows)
    ge.to_csv(os.path.join(K.DIR_TABLES, "absolute_gate_effect.csv"), index=False)
    K.log("[table] absolute_gate_effect.csv  (%d relative x gate rows)" % len(ge))

    # =========================================================================
    # 5. absolute-only against the matched relative constructs
    # =========================================================================
    arows = []
    for g in K.ABSOLUTE_GATES_F:
        for d in K.DURATIONS:
            aid = K.abs_id(g, d)
            if aid not in sets:
                continue
            asu = summ[summ["construct_id"] == aid].iloc[0]
            for p in K.PERCENTILES:
                rid = K.rel_id(p, d)
                if rid not in sets:
                    continue
                rsu = summ[summ["construct_id"] == rid].iloc[0]
                inter = int(np.intersect1d(sets[aid], sets[rid],
                                           assume_unique=True).size)
                arows.append(dict(
                    absolute_construct=aid, absolute_label=short_label(cons[aid]),
                    absolute_gate_f=g, duration_days=d,
                    relative_construct=rid, relative_label=short_label(cons[rid]),
                    percentile=p, threshold_window=K.PRIMARY_WINDOW,
                    median_annual_classified_days_absolute=asu["median_annual_classified_days"],
                    median_annual_classified_days_relative=rsu["median_annual_classified_days"],
                    median_annual_event_count_absolute=asu["median_annual_event_count"],
                    median_annual_event_count_relative=rsu["median_annual_event_count"],
                    rate_per_1000_absolute=asu["classified_days_per_1000_valid"],
                    rate_per_1000_relative=rsu["classified_days_per_1000_valid"],
                    pct_days_june_september_absolute=asu["pct_days_june_september"],
                    pct_days_june_september_relative=rsu["pct_days_june_september"],
                    county_dates_shared=inter,
                    county_dates_absolute_only=int(sets[aid].size - inter),
                    county_dates_relative_only=int(sets[rid].size - inter),
                    jaccard=round(jaccard(sets[aid], sets[rid]), 4),
                    interpretation=("agreement, not accuracy; the two constructs "
                                    "answer different questions")))
    av = pd.DataFrame(arows)
    av.to_csv(os.path.join(K.DIR_TABLES, "absolute_vs_relative.csv"), index=False)
    K.log("[table] absolute_vs_relative.csv  (%d rows)" % len(av))

    # =========================================================================
    # 6. county-level geography of the gate
    # =========================================================================
    crows = []
    counties = sorted(ref["county_fips"].unique())
    for p in K.PERCENTILES:
        for d in K.DURATIONS:
            bid = K.rel_id(p, d)
            b = (ann[ann["construct_id"] == bid].groupby("county_fips")
                 ["annual_classified_day_count"].sum().reindex(counties, fill_value=0))
            ba = (ann[ann["construct_id"] == bid].groupby("county_fips")
                  ["annual_event_count"].sum().reindex(counties, fill_value=0))
            for g in K.ABSOLUTE_GATES_F:
                hid = K.hyb_id(p, d, g)
                h = (ann[ann["construct_id"] == hid].groupby("county_fips")
                     ["annual_classified_day_count"].sum().reindex(counties, fill_value=0))
                t = pd.DataFrame({
                    "county_fips": counties,
                    "relative_construct": bid, "hybrid_construct": hid,
                    "label": short_label(cons[bid]), "percentile": p,
                    "duration_days": d, "absolute_gate_f": g,
                    "cumulative_classified_days_no_gate": b.to_numpy(),
                    "cumulative_classified_days_with_gate": h.to_numpy(),
                    "cumulative_events_no_gate": ba.to_numpy()})
                t["classified_days_lost"] = (t["cumulative_classified_days_no_gate"]
                                             - t["cumulative_classified_days_with_gate"])
                t["pct_retained"] = (
                    100.0 * t["cumulative_classified_days_with_gate"]
                    / t["cumulative_classified_days_no_gate"].replace(0, np.nan)).round(2)
                crows.append(t)
    cg = pd.concat(crows, ignore_index=True).merge(
        ref[["county_fips", "county_name", "pct_analysis_days_imputed",
             "fully_imputed_county", "analysis_days", "native_analysis_days"]],
        on="county_fips", how="left")
    cg.to_csv(os.path.join(K.DIR_TABLES, "county_gate_effect.csv"), index=False)
    K.log("[table] county_gate_effect.csv  (%d rows)" % len(cg))

    # =========================================================================
    # 7. distributions used directly by figures
    # =========================================================================
    ad = (ann[ann["construct_id"].isin(cons)]
          .groupby(["construct_id", "construct_family"], observed=True)
          ["annual_event_count"]
          .describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).reset_index())
    ad = ad.merge(summ[["construct_id", "short_label"]], on="construct_id", how="left")
    ad.to_csv(os.path.join(K.DIR_TABLES, "annual_event_count_distribution.csv"),
              index=False)
    ed = (cat.groupby(["construct_id", "construct_family"], observed=True)
          ["event_duration_days"]
          .describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9, 0.99]).reset_index())
    ed = ed.merge(summ[["construct_id", "short_label"]], on="construct_id", how="left")
    ed["note"] = ("a median may fall between two integers because it is a median "
                  "ACROSS events; no individual event has a fractional duration")
    ed.to_csv(os.path.join(K.DIR_TABLES, "event_duration_distribution.csv"), index=False)
    K.log("[table] annual_event_count_distribution.csv, event_duration_distribution.csv")

    # =========================================================================
    K.log("-" * 78)
    K.log("SEASONALITY, three categories, relative warm spells at the primary window")
    K.log("   %-14s %10s %10s %10s   %s" % ("construct", "Jun-Sep", "May+Oct",
                                            "Nov-Apr", "peak month"))
    for _, x in summ[summ["construct_family"] == "relative"].iterrows():
        K.log("   %-14s %9.1f%% %9.1f%% %9.1f%%   %s"
              % (x["short_label"], x["pct_days_june_september"],
                 x["pct_days_may_and_october"], x["pct_days_november_april"],
                 x["peak_month"]))
    K.log("-" * 78)
    K.log("ABSOLUTE GATE EFFECT on the %s construct" % short_label(cons[K.rel_id(90, 3)]))
    for _, x in ge[(ge["percentile"] == 90) & (ge["duration_days"] == 3)].iterrows():
        K.log("   %d degF gate: %.1f%% of classified days retained, Jaccard %.3f, "
              "Jun-Sep share %.1f%% -> %.1f%%, county retention p10-p90 %.0f-%.0f%%"
              % (x["absolute_gate_f"], x["pct_classified_days_retained"],
                 x["day_level_jaccard_with_no_gate"],
                 x["pct_days_june_september_no_gate"],
                 x["pct_days_june_september_with_gate"],
                 x["p10_county_retention_pct"], x["p90_county_retention_pct"]))
    K.log("r07 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
