"""
=============================================================================
hs05_comparison.py  --  the cross-construct comparison layer.
=============================================================================
Implements plan revision 6, sections 6, 7 and 8.

THE JACCARD DEFINITION USED THROUGHOUT (this was mis-stated in an earlier draft
and is the single most consequential formula in this file):

    U = Eligible_A  INTERSECT  Eligible_B          <- the comparison UNIVERSE
    A = {d in U : classified_A(d)}
    B = {d in U : classified_B(d)}
    jaccard = |A INTERSECT B| / |A UNION B|         <- denominator is the UNION OF
                                                      POSITIVE CLASSIFICATIONS,
                                                      *not* |U|
    when |A UNION B| == 0  ->  NA  (never silently 0 or 1)

Pair-specific common eligibility is applied to EVERY cell of every matrix, not
only the matched Tmax-vs-HIPROXY comparison: the run set mixes QC tiers, so a
date excluded on one side must not be read as "classified 0" on the other.

Outputs:
  agreement_jaccard_yearround_21x21.csv / _pairs.csv   21 year-round ordinary runs
  warmseason_candidate_pair_comparison.csv             the 2 JUNSEP runs
  ehf_cross_family_overlap.csv                         EHF, reported SEPARATELY, with
                                                       both date representations
  matched_metric_comparison.csv                        Tmax vs HIPROXY at matched
                                                       percentile+duration+window
  threshold_loyo_sensitivity.csv                       leave-one-baseline-year-out
=============================================================================
"""
import os, sys, time, itertools
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hs00_config as H
import hs02_classify as hs02
sys.path.insert(0, H.PIPELINE_DIR)
from p02_classify_and_report import compute_thresholds, MD_TO_TDOY
from heatwave_run_logic import build_runs_and_events_panel
import config as PC

W15 = PC.GRID_WINDOWS["w15"]


def log(*a):
    print(*a, flush=True)


# =============================================================================
# eligibility + classification sets, per construct
# =============================================================================
def _encode(county_fips, dates):
    """int64 key for (county, date) -- fast, exact, no string overhead."""
    cty = pd.Series(county_fips).astype(str)
    codes, _ = pd.factorize(cty)
    do = pd.to_datetime(pd.Series(dates)).to_numpy(dtype="datetime64[D]").astype(np.int64)
    return codes.astype(np.int64) * 100000 + do


def build_sets(state="TX"):
    """For each construct: the ELIGIBLE date set and the CLASSIFIED date set,
    both as sorted int64 arrays over a shared county/date encoding."""
    dv = pd.read_csv(os.path.join(H.TABLES_DIR, "_derived_variables_%s.csv.gz" % state),
                     usecols=["county_fips", "date", "year", "month", "qc_category",
                              "ehf_c2_fixed", "ehf_c2_wf"],
                     dtype={"county_fips": str})
    dv["date"] = pd.to_datetime(dv["date"])
    an = dv[(dv["year"] >= H.ANALYSIS_YEARS[0]) & (dv["year"] <= H.ANALYSIS_YEARS[1])].copy()

    # one global county code map so keys are comparable across constructs
    counties = sorted(an["county_fips"].unique())
    cmap = {c: i for i, c in enumerate(counties)}
    an["_c"] = an["county_fips"].map(cmap).astype(np.int64)
    an["_d"] = an["date"].to_numpy(dtype="datetime64[D]").astype(np.int64)
    an["_key"] = an["_c"] * 100000 + an["_d"]

    eligible, classified = {}, {}
    for construct in H.CONSTRUCTS:
        cid = construct["construct_id"]
        excl = hs02.QC_EXCLUDE_SETS.get(construct.get("qc_tier"), set())
        m = ~an["qc_category"].isin(excl) if excl else pd.Series(True, index=an.index)
        if construct["season_rule"] == "june_september":
            m = m & an["month"].between(6, 9)
        if construct["family"] == "ehf":
            col = "ehf_c2_fixed" if construct["baseline"] == "fixed_1979_2014" else "ehf_c2_wf"
            m = m & an[col].notna()
        eligible[cid] = np.sort(an.loc[m, "_key"].to_numpy())

        tdir = os.path.join(H.construct_dir(cid, make=False), "tables")
        for fname in ("daily_classified.csv.gz", "ehf_positive_assessment_dates.csv.gz"):
            p = os.path.join(tdir, fname)
            if os.path.exists(p):
                d = pd.read_csv(p, usecols=["county_fips", "date"], dtype={"county_fips": str})
                d["date"] = pd.to_datetime(d["date"])
                k = d["county_fips"].map(cmap).astype(np.int64) * 100000 + \
                    d["date"].to_numpy(dtype="datetime64[D]").astype(np.int64)
                classified[cid] = np.sort(k.dropna().to_numpy().astype(np.int64))
                break
        else:
            # reused grid cells: rebuild the classified set from their county-year table is
            # not possible at date level, so read the grid's own daily file
            src_tdir, wkey = hs02.source_grid_dir(construct["source_run_id"])
            p = os.path.join(src_tdir, "daily_heatwave_days_%s.csv.gz" % wkey)
            d = pd.read_csv(p, usecols=["county_fips", "date"], dtype={"county_fips": str})
            d["date"] = pd.to_datetime(d["date"])
            k = d["county_fips"].map(cmap).astype(np.int64) * 100000 + \
                d["date"].to_numpy(dtype="datetime64[D]").astype(np.int64)
            classified[cid] = np.sort(k.dropna().to_numpy().astype(np.int64))
        log("   [sets] %-38s eligible=%9s classified=%8s"
            % (cid, "{:,}".format(len(eligible[cid])), "{:,}".format(len(classified[cid]))))
    return eligible, classified


# =============================================================================
# the pairwise metric (the corrected Jaccard)
# =============================================================================
def pair_metrics(a_id, b_id, eligible, classified):
    EA, EB = eligible[a_id], eligible[b_id]
    U = np.intersect1d(EA, EB, assume_unique=True)
    A = np.intersect1d(classified[a_id], U, assume_unique=True)
    B = np.intersect1d(classified[b_id], U, assume_unique=True)
    both = np.intersect1d(A, B, assume_unique=True)
    n_a, n_b, n_both = len(A), len(B), len(both)
    n_either = n_a + n_b - n_both
    jac = (n_both / n_either) if n_either > 0 else np.nan
    e_union = len(np.union1d(EA, EB))
    return {
        "definition_A": a_id, "definition_B": b_id,
        "n_A_eligible_dates": len(EA), "n_B_eligible_dates": len(EB),
        "n_common_eligible_dates": len(U),
        "eligibility_jaccard": round(len(U) / e_union, 6) if e_union else np.nan,
        "fraction_A_eligible_also_eligible_B": round(len(U) / len(EA), 6) if len(EA) else np.nan,
        "fraction_B_eligible_also_eligible_A": round(len(U) / len(EB), 6) if len(EB) else np.nan,
        "n_classified_by_A": n_a, "n_classified_by_B": n_b,
        "n_classified_by_both": n_both, "n_classified_by_either": n_either,
        "n_A_only_positive": n_a - n_both, "n_B_only_positive": n_b - n_both,
        "jaccard_common_eligibility": round(jac, 6) if not pd.isna(jac) else np.nan,
    }


# =============================================================================
# driver
# =============================================================================
def run(state="TX"):
    t0 = time.time()
    log("[sets] building eligibility + classification sets ...")
    eligible, classified = build_sets(state)

    meta = {c["construct_id"]: c for c in H.CONSTRUCTS}

    # ---- 1. the 21x21 year-round ordinary matrix -------------------------
    yr_ids = H.yearround_ordinary_construct_ids()
    assert len(yr_ids) == 21, "expected 21 year-round ordinary constructs, got %d" % len(yr_ids)
    rows = []
    for a, b in itertools.combinations(yr_ids, 2):
        rows.append(pair_metrics(a, b, eligible, classified))
    pairs = pd.DataFrame(rows)
    pairs.to_csv(os.path.join(H.TABLES_DIR, "agreement_jaccard_yearround_pairs.csv"), index=False)

    M = pd.DataFrame(np.eye(len(yr_ids)), index=yr_ids, columns=yr_ids)
    for r in rows:
        M.loc[r["definition_A"], r["definition_B"]] = r["jaccard_common_eligibility"]
        M.loc[r["definition_B"], r["definition_A"]] = r["jaccard_common_eligibility"]
    M.to_csv(os.path.join(H.TABLES_DIR, "agreement_jaccard_yearround_21x21.csv"))
    log("[1/5] year-round matrix: %dx%d, %d pairs" % (len(yr_ids), len(yr_ids), len(rows)))

    # ---- 2. warm-season candidate pair (2 runs -- a pair, not a matrix) ----
    a, b = H.WARMSEASON_PAIR
    ws = pd.DataFrame([pair_metrics(a, b, eligible, classified)])
    ws["comparison_note"] = ("non-metric-isolating: percentile and duration differ between these two "
                             "definitions, so disagreement cannot be attributed to metric choice")
    ws.to_csv(os.path.join(H.TABLES_DIR, "warmseason_candidate_pair_comparison.csv"), index=False)
    log("[2/5] warm-season candidate pair written")

    # ---- 3. EHF cross-family overlap -- SEPARATE, both date representations ----
    ehf_rows = []
    for ehf_c in H.constructs_by_family("ehf"):
        eid = ehf_c["construct_id"]
        for other in yr_ids:
            m = pair_metrics(eid, other, eligible, classified)
            m["ehf_construct"] = eid
            m["comparator"] = other
            m["ehf_date_representation"] = "positive_ehf_assessment_date"
            m["assessment_date_jaccard"] = m["jaccard_common_eligibility"]
            m["interpretation_note"] = ("EHF assessment dates summarise a trailing 3-day thermal "
                                        "period; this is NOT equivalent to ordinary single-day "
                                        "classification agreement")
            ehf_rows.append(m)
    pd.DataFrame(ehf_rows).to_csv(os.path.join(H.TABLES_DIR, "ehf_cross_family_overlap.csv"), index=False)
    log("[3/5] EHF cross-family overlap: %d comparisons (kept OUT of the 21x21 matrix)" % len(ehf_rows))

    # ---- 4. matched metric comparison (Tmax vs HIPROXY, matched pctl+duration+window) ----
    mm = [dict(pair_metrics(a, b, eligible, classified),
               matched_on="percentile+min_duration+window",
               metric_isolating_claim="daily classification only; event-level differences are NOT "
                                      "claimed to isolate metric choice")
          for a, b in H.MATCHED_METRIC_PAIRS]
    pd.DataFrame(mm).to_csv(os.path.join(H.TABLES_DIR, "matched_metric_comparison.csv"), index=False)
    log("[4/5] matched metric comparison: %d matched pairs" % len(mm))

    # ---- 5. leave-one-baseline-year-out threshold sensitivity ----
    loyo = leave_one_year_out(state)
    loyo.to_csv(os.path.join(H.TABLES_DIR, "threshold_loyo_sensitivity.csv"), index=False)
    log("[5/5] LOYO sensitivity: %d rows" % len(loyo))

    log("[done] hs05 in %.1f min" % ((time.time() - t0) / 60))
    return pairs, M


def leave_one_year_out(state="TX"):
    """Plan Sec.8: for each named construct x named county x frozen date window, drop one
    baseline year at a time, recompute the threshold, RECLASSIFY THE ENTIRE ANNUAL SEQUENCE
    (event qualification depends on adjacent dates), rebuild events, then extract the
    differences that fall inside the frozen window. Zero change is an acceptable result."""
    dv = pd.read_csv(os.path.join(H.TABLES_DIR, "_derived_variables_%s.csv.gz" % state),
                     dtype={"county_fips": str})
    dv["date"] = pd.to_datetime(dv["date"])
    md = list(zip(dv["month"].to_numpy(), dv["day"].to_numpy()))
    dv["template_doy"] = np.array([MD_TO_TDOY[k] for k in md], dtype=np.int16)

    fips_list = [c["county_fips"] for c in H.EXAMPLE_COUNTIES]
    rows = []
    for cid in H.UNCERTAINTY_CONSTRUCT_IDS:
        c = H.get_construct(cid)
        metric, pctl = c["metric"], c["percentile"]
        excl = hs02.QC_EXCLUDE_SETS.get(c.get("qc_tier"), set())
        sub = dv[dv["county_fips"].isin(fips_list)].copy()
        if excl:
            sub = sub[~sub["qc_category"].isin(excl)]

        thr_full, _ = compute_thresholds(sub, metric, [pctl], W15, verbose=False)
        an_full, _ = hs02.build_candidates_local(sub, metric, pctl, thr_full,
                                                 qc_tier=c.get("qc_tier") if c["qc_tier"] != "n/a" else None)
        daily_full, ev_full = build_runs_and_events_panel(
            an_full, min_duration=c["min_duration"], definition_id=cid, state_fips="48",
            with_event_columns=False)
        full_cls = set(zip(daily_full.loc[daily_full["heatwave_day_flag"] == 1, "county_fips"],
                           daily_full.loc[daily_full["heatwave_day_flag"] == 1, "date"]))
        full_cand = set(zip(an_full.loc[an_full["candidate_day_flag"] == 1, "county_fips"],
                            an_full.loc[an_full["candidate_day_flag"] == 1, "date"]))
        full_ev = set(zip(ev_full["county_fips"], ev_full["start_date"], ev_full["end_date"]))

        baseline_years = sorted(set(sub.loc[sub["year"] < H.ANALYSIS_YEARS[0], "year"]))
        for b in baseline_years:
            sub_b = sub[sub["year"] != b]
            thr_b, _ = compute_thresholds(sub_b, metric, [pctl], W15, verbose=False)
            an_b, _ = hs02.build_candidates_local(sub_b, metric, pctl, thr_b,
                                                 qc_tier=c.get("qc_tier") if c["qc_tier"] != "n/a" else None)
            daily_b, ev_b = build_runs_and_events_panel(
                an_b, min_duration=c["min_duration"], definition_id=cid, state_fips="48",
                with_event_columns=False)
            b_cls = set(zip(daily_b.loc[daily_b["heatwave_day_flag"] == 1, "county_fips"],
                            daily_b.loc[daily_b["heatwave_day_flag"] == 1, "date"]))
            b_cand = set(zip(an_b.loc[an_b["candidate_day_flag"] == 1, "county_fips"],
                             an_b.loc[an_b["candidate_day_flag"] == 1, "date"]))
            b_ev = set(zip(ev_b["county_fips"], ev_b["start_date"], ev_b["end_date"]))

            def in_window(d):
                s = pd.Timestamp(d).strftime("%m-%d")
                return any(w0 <= s <= w1 for w0, w1 in H.UNCERTAINTY_DATE_WINDOWS)

            cand_changed = {x for x in (full_cand ^ b_cand) if in_window(x[1])}
            cls_changed = {x for x in (full_cls ^ b_cls) if in_window(x[1])}
            ev_start_changed = {e for e in (full_ev ^ b_ev) if in_window(e[1])}
            ev_end_changed = {e for e in (full_ev ^ b_ev) if in_window(e[2])}

            m = thr_full.merge(thr_b, on=["county_fips", "template_doy", "analysis_year"],
                               suffixes=("_full", "_b"))
            tcol = "threshold_p%s_f" % (str(pctl).replace(".0", ""))
            tcol_full = [x for x in m.columns if x.endswith("_full") and x.startswith("threshold")][0]
            tcol_b = [x for x in m.columns if x.endswith("_b") and x.startswith("threshold")][0]
            tdiff = (m[tcol_full] - m[tcol_b]).abs()

            rows.append({
                "construct_id": cid, "dropped_baseline_year": b,
                "n_counties": len(fips_list),
                "threshold_full_sample_mean_f": round(float(m[tcol_full].mean()), 4),
                "threshold_leave_one_year_out_mean_f": round(float(m[tcol_b].mean()), 4),
                "threshold_max_abs_diff_f": round(float(tdiff.max()), 4),
                "threshold_leave_one_year_out_sd_f": round(float(tdiff.std()), 6),
                "candidate_day_change_count": len(cand_changed),
                "final_classified_day_change_count": len(cls_changed),
                "event_start_change_count": len(ev_start_changed),
                "event_end_change_count": len(ev_end_changed),
                "event_count_change": len(b_ev) - len(full_ev),
                "note": "zero change is an acceptable, reportable empirical result",
            })
        log("   [loyo] %s: %d dropped-year scenarios" % (cid, len(baseline_years)))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    run()
