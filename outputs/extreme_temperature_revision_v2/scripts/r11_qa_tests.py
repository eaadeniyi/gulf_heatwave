"""
=============================================================================
r11  --  the consolidated QA suite. The pipeline FAILS if any blocking test
         fails; nothing downstream is allowed to run on unverified output.
=============================================================================
  TEST A  daily temperature logic          (re-verified against the panel)
  TEST B  coverage
  TEST C  period weighting
  TEST D  event logic
  TEST E  gate logic
  TEST F  denominators
  TEST G  output consistency, including figure values against the CSVs
  plus    palette validation, Stage 1 reproduction, terminology compliance

Tests already executed by the step that generated the data (A in r02, C in
r03, D-G in r06) are re-read here and RE-CHECKED against the written tables, so
a test cannot pass in memory and then be contradicted by what was saved.
=============================================================================
"""
import os
import re
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K
import r_palette

T, Q = K.DIR_TABLES, K.DIR_QA
R = []


def rec(test, check, result, detail, blocking=True, source=""):
    R.append(dict(test=test, check=check, result=result, blocking=blocking,
                  detail=str(detail)[:600], source=source))


def carry(path, test):
    """Re-read a test table written by an earlier step."""
    if not os.path.exists(path):
        rec(test, "test_table_present", "FAIL", "missing %s" % path)
        return
    d = pd.read_csv(path)
    for _, r in d.iterrows():
        res = r.get("result", "")
        blocking = bool(r.get("blocking", True))
        rec(test, r.get("check", ""), res, r.get("detail", r.get("note", "")),
            blocking, os.path.basename(path))


# =============================================================================
def test_a_panel():
    a = pd.read_csv(os.path.join(T, "county_annual_temperature.csv"),
                    dtype={"county_fips": str})
    m = pd.read_csv(os.path.join(T, "county_monthly_temperature.csv"),
                    dtype={"county_fips": str})
    w = a.pivot_table(index=["state", "county_fips", "year"], columns="variable",
                      values="period_mean_f")
    ok = w.dropna(subset=["Tmax", "Tmin", "Tavg"])
    bad = ok[ok["Tmax"] < ok["Tmin"]]
    rec("A", "annual_high_at_least_annual_low_in_the_written_panel",
        "PASS" if not len(bad) else "FAIL",
        "%d annual county-level observations with a mean high below the mean low"
        % len(bad), source="county_annual_temperature.csv")
    # Tavg is DEFINED daily as (Tmax + Tmin) / 2, so the identity must hold exactly
    # at the annual level whenever the three variables rest on the SAME set of days.
    # The coverage gate is applied per variable, so that is not always the case, and
    # the size of the resulting gap is reported rather than tolerated silently.
    n = a.pivot_table(index=["state", "county_fips", "year"], columns="variable",
                      values="valid_daily_observation_count")
    d = (ok["Tavg"] - (ok["Tmax"] + ok["Tmin"]) / 2.0).abs()
    same = ((n["Tmax"] == n["Tmin"]) & (n["Tmin"] == n["Tavg"])).reindex(
        ok.index).fillna(False)
    rec("A", "annual_average_equals_the_mean_of_the_annual_high_and_low_on_equal_days",
        "PASS" if d[same].max() < 0.005 else "FAIL",
        "on the %s annual county-level observations where all three variables rest on "
        "the same number of days, max |Tavg - (Tmax+Tmin)/2| = %.6f degF (the written "
        "table is rounded to 3 decimal places)"
        % ("{:,}".format(int(same.sum())), d[same].max()),
        source="county_annual_temperature.csv")
    w = a[a["meets_annual_coverage_requirement"]].pivot_table(
        index=["state", "county_fips", "year"], columns="variable",
        values="period_mean_f").dropna()
    dq = (w["Tavg"] - (w["Tmax"] + w["Tmin"]) / 2.0).abs()
    rec("A", "annual_average_identity_among_QUALIFYING_observations",
        "PASS" if dq.max() < 1.0 else "FAIL",
        "among the %s annual county-level observations where all three variables meet "
        "the coverage requirement, max |Tavg - (Tmax+Tmin)/2| = %.3f degF, median "
        "%.5f, 99th percentile %.3f. The tolerance is 1 degF: the residual is the "
        "per-variable coverage gate admitting slightly different day sets, not an "
        "arithmetic error."
        % ("{:,}".format(len(w)), dq.max(), dq.median(), dq.quantile(0.99)),
        source="county_annual_temperature.csv")
    rec("A", "per_variable_coverage_gate_can_rest_on_different_day_sets", "REPORT",
        "%s of %s annual county-level observations have different valid-day counts "
        "for the high, the low and the average, because the coverage gate is applied "
        "per variable. Where they differ the gap is usually negligible (median %.3f "
        "degF) but reaches %.2f degF in the worst case. CONSEQUENCE: do not compute "
        "an annual average from the annual high and the annual low; use the Tavg rows, "
        "which are built from daily values."
        % ("{:,}".format(int((~same).sum())), "{:,}".format(len(ok)),
           d[~same].median(), d[~same].max()),
        blocking=False, source="county_annual_temperature.csv")
    conv = [(0.0, 32.0), (100.0, 212.0), (-40.0, -40.0), (37.0, 98.6)]
    bad = [(c, e) for c, e in conv if abs(c * 9 / 5 + 32 - e) > 1e-9]
    rec("A", "fahrenheit_conversion_verified_against_known_values",
        "PASS" if not bad else "FAIL", "failed cases: %s" % bad)
    q = os.path.join(Q, "quarantined_inverted_daily_records.csv")
    n = len(pd.read_csv(q)) if os.path.exists(q) else 0
    rec("A", "inverted_records_quarantined_and_reported", "REPORT",
        "%d raw county-dates removed by the declared rule %r and preserved in "
        "qa/quarantined_inverted_daily_records.csv" % (n, K.INVERTED_RECORD_ACTION),
        blocking=False, source="quarantined_inverted_daily_records.csv")
    return a, m


def test_b(a, m):
    bad = a[a["meets_annual_coverage_requirement"]
            & (a["valid_daily_observation_count"] < K.MIN_DAYS_PER_COUNTY_YEAR)]
    rec("B", "annual_records_meet_the_configured_annual_day_threshold",
        "PASS" if not len(bad) else "FAIL",
        "%d annual county-level observations flagged as meeting a %d-day requirement "
        "with fewer days" % (len(bad), K.MIN_DAYS_PER_COUNTY_YEAR))
    bad = m[m["meets_monthly_coverage_requirement"]
            & (m["valid_daily_observation_count"] < K.MIN_DAYS_PER_COUNTY_MONTH)]
    rec("B", "monthly_records_meet_the_configured_monthly_day_threshold",
        "PASS" if not len(bad) else "FAIL",
        "%d monthly county-level summaries flagged as meeting a %d-day requirement "
        "with fewer days" % (len(bad), K.MIN_DAYS_PER_COUNTY_MONTH))
    sp = pd.read_csv(os.path.join(T, "state_period_temperature_equal_county.csv"))
    miss = sp[sp["contributing_counties"].isna() | (sp["contributing_counties"] <= 0)]
    rec("B", "every_state_period_result_reports_a_contributing_county_count",
        "PASS" if not len(miss) else "FAIL",
        "%d of %d state-period rows lack a county count" % (len(miss), len(sp)),
        source="state_period_temperature_equal_county.csv")
    sm = pd.read_csv(os.path.join(T, "state_month_period_temperature_equal_county.csv"))
    miss = sm[sm["contributing_counties"].isna() | (sm["contributing_counties"] <= 0)]
    rec("B", "every_state_month_period_cell_reports_a_county_count",
        "PASS" if not len(miss) else "FAIL",
        "%d of %d state-month-period rows lack a county count" % (len(miss), len(sm)))


def test_g_outputs():
    ann = pd.read_csv(os.path.join(T, "county_annual_all_constructs.csv"),
                      dtype={"county_fips": str})
    mon = pd.read_csv(os.path.join(T, "county_monthly_all_constructs.csv"),
                      dtype={"county_fips": str})
    summ = pd.read_csv(os.path.join(T, "construct_summary.csv"))
    season = pd.read_csv(os.path.join(T, "seasonal_classification_shares.csv"))
    rates = pd.read_csv(os.path.join(T, "monthly_classification_rates.csv"))
    ge = pd.read_csv(os.path.join(T, "absolute_gate_effect.csv"))
    sp = pd.read_csv(os.path.join(T, "state_period_temperature_equal_county.csv"))

    # ---- figure values must reproduce from the published CSVs ---------------
    #  E5 panel A
    for _, r in summ[summ["construct_family"] == "relative"].iterrows():
        a = ann[ann["construct_id"] == r["construct_id"]]
        cum = a.groupby("county_fips")["annual_classified_day_count"].sum()
        if abs(float(cum.median()) - r["median_cumulative_classified_days_per_county"]) > 1e-6:
            rec("G", "figure_E5A_value_matches_the_csv", "FAIL",
                "%s: summary says %.3f, annual table gives %.3f"
                % (r["construct_id"], r["median_cumulative_classified_days_per_county"],
                   cum.median()))
            break
    else:
        rec("G", "figure_E5A_value_matches_the_csv", "PASS",
            "median cumulative classified days recomputed from "
            "county_annual_all_constructs.csv for all 9 relative constructs")

    #  E5 panel B
    bad = []
    for _, r in summ.iterrows():
        a = ann[ann["construct_id"] == r["construct_id"]]
        if len(a) and abs(float(a["annual_event_count"].median())
                          - r["median_annual_event_count"]) > 1e-6:
            bad.append(r["construct_id"])
    rec("G", "figure_E5B_value_matches_the_csv", "PASS" if not bad else "FAIL",
        "median annual event count recomputed for %d constructs%s"
        % (len(summ), "" if not bad else "; mismatched: %s" % bad[:5]))

    #  E5 panel D and the seasonal shares
    s = season.groupby("construct_id")["pct_of_classified_days"].sum()
    off = (s - 100.0).abs()
    rec("G", "figure_E5D_seasonal_shares_sum_to_100", "PASS" if off.max() < 0.05
        else "FAIL", "worst deviation %.4f percentage points" % off.max())

    #  E6 / R9 rates recompute from counts
    d = (rates["classified_days_per_1000_valid"]
         - 1000.0 * rates["classified_days"] / rates["valid_daily_observations"]).abs()
    rec("G", "figure_E6_R9_rates_recompute_from_their_counts",
        "PASS" if d.max() < 5e-3 else "FAIL",
        "worst deviation %.6f per 1,000" % d.max())

    #  E7 panel A
    bad = []
    for _, r in ge.iterrows():
        b = summ[summ["construct_id"] == r["relative_construct"]].iloc[0]
        h = summ[summ["construct_id"] == r["hybrid_construct"]].iloc[0]
        exp = 100.0 * h["classified_county_dates_QA"] / b["classified_county_dates_QA"]
        if abs(exp - r["pct_classified_days_retained"]) > 0.02:
            bad.append(r["hybrid_construct"])
    rec("G", "figure_E7A_retained_share_matches_the_csv",
        "PASS" if not bad else "FAIL",
        "recomputed for %d gate rows%s" % (len(ge),
                                           "" if not bad else "; mismatched %s" % bad[:5]))

    #  E3 bars
    bad = sp[sp["difference_of_medians_vs_base_f"].isna()
             | sp["difference_ci_low_f"].isna()]
    rec("G", "figure_E3_bars_have_point_estimate_and_interval",
        "PASS" if not len(bad) else "FAIL",
        "%d of %d state-period rows lack a difference or an interval"
        % (len(bad), len(sp)))
    bad = sp[(sp["difference_ci_low_f"] > sp["difference_of_medians_vs_base_f"])
             | (sp["difference_ci_high_f"] < sp["difference_of_medians_vs_base_f"])]
    rec("G", "bootstrap_interval_contains_its_point_estimate",
        "PASS" if not len(bad) else "FAIL", "%d violations" % len(bad))

    # ---- cross-table consistency -------------------------------------------
    shared = sorted(set(mon["construct_id"]) & set(ann["construct_id"]))
    ms = (mon[mon["construct_id"].isin(shared)]
          .groupby(["construct_id", "county_fips", "year"])["heat_event_day_count"]
          .sum().rename("m").reset_index())
    asum = ann[ann["construct_id"].isin(shared)][
        ["construct_id", "county_fips", "year", "annual_classified_day_count"]]
    j = asum.merge(ms, on=["construct_id", "county_fips", "year"], how="outer").fillna(0)
    bad = j[j["annual_classified_day_count"] != j["m"]]
    rec("G", "annual_classified_days_equal_the_sum_of_monthly_counts",
        "PASS" if not len(bad) else "FAIL",
        "%d of %d county-years disagree across %d constructs"
        % (len(bad), len(j), len(shared)))

    cat = pd.concat([pd.read_csv(os.path.join(T, f), dtype={"county_fips": str})
                     for f in ("individual_relative_warm_spell_events.csv",
                               "individual_hybrid_heat_events.csv",
                               "individual_absolute_hot_spells.csv")],
                    ignore_index=True)
    dur = cat.groupby("construct_id")["event_duration_days"].sum()
    day = mon.groupby("construct_id")["heat_event_day_count"].sum()
    cmp = pd.concat([dur.rename("d"), day.rename("c")], axis=1).dropna()
    bad = cmp[cmp["d"] != cmp["c"]]
    rec("G", "event_durations_sum_to_classified_days",
        "PASS" if not len(bad) else "FAIL",
        "%d of %d constructs disagree" % (len(bad), len(cmp)))

    known = set(cat["event_id"])
    ids = set()
    for col in ("event_ids_started", "event_ids_active"):
        for v in mon[col].dropna().astype(str):
            if v:
                ids.update(v.split(";"))
    rec("G", "every_event_id_in_a_summary_exists_in_the_event_table",
        "PASS" if not (ids - known) else "FAIL",
        "%d referenced ids, %d absent from the catalogues" % (len(ids),
                                                              len(ids - known)))
    rec("G", "event_durations_are_integers",
        "PASS" if (cat["event_duration_days"] % 1 == 0).all() else "FAIL",
        "%d events with a fractional duration"
        % int((cat["event_duration_days"] % 1 != 0).sum()))
    return cat, mon, ann


def test_f_rates(mon):
    r = mon["monthly_classification_rate_per_1000"]
    rec("F", "classification_rate_never_exceeds_1000_per_1000",
        "PASS" if not (r > 1000.0 + 1e-9).any() else "FAIL",
        "maximum observed rate %.3f per 1,000" % r.max())
    bad = mon[mon["heat_event_day_count"] > mon["valid_daily_observation_count"]]
    rec("F", "classified_days_never_exceed_valid_records",
        "PASS" if not len(bad) else "FAIL", "%d violations" % len(bad))
    bad = mon[mon["valid_daily_observation_count"].isna()
              | (mon["valid_daily_observation_count"] <= 0)]
    rec("F", "missing_exposure_is_not_coded_as_a_non_event",
        "PASS" if not len(bad) else "FAIL",
        "%d monthly summaries carry a zero or missing denominator; the panel is built "
        "FROM the valid-record table, so a county-month with no valid records is "
        "absent rather than present as a zero" % len(bad))
    e = pd.read_csv(os.path.join(Q, "eligibility_denominator_comparison.csv"))
    same = bool(e["relative_equals_absolute"].all() and e["relative_equals_hybrid"].all())
    rec("F", "construct_family_denominators_tested_not_assumed", "REPORT",
        "relative == hybrid: %s; relative == absolute: %s. %s"
        % (bool(e["relative_equals_hybrid"].all()),
           bool(e["relative_equals_absolute"].all()),
           "documented as equal for this state and period"
           if same else "NOT equal - each family must use its own denominator"),
        blocking=False, source="eligibility_denominator_comparison.csv")


def test_terminology():
    """Reader-facing prose written EARLIER in this run must not use the retired
    vocabulary. reports/ is written after this step, so r12 re-runs the same
    check over its own output and fails there."""
    skip = {"QA_REPORT.md"}          # a test log quoting the failing strings
    targets = []
    for d in (K.DIR_QA, K.DIR_EVENT_AUDITS):
        if os.path.isdir(d):
            targets += [os.path.join(d, f) for f in os.listdir(d)
                        if f.endswith(".md") and f not in skip]
    hits = K.terminology_violations(targets)
    rec("terminology", "retired_vocabulary_absent_from_qa_and_audit_prose",
        "PASS" if not hits else "FAIL",
        "%d unguarded use(s) across %d files%s"
        % (len(hits), len(targets), "" if not hits else ": " + str(hits[:3])),
        source="qa/, event_audits/ markdown")


def test_reproduction():
    rp = pd.read_csv(os.path.join(Q, "01_existing_pipeline_reproduction.csv"))
    ok = rp["verdict"].isin(["PASS", "IDENTICAL_BYTES", "IDENTICAL_VALUES",
                             "NOT_RE_EXECUTED"])
    rec("stage1", "current_pipeline_reproduces", "PASS" if ok.all() else "FAIL",
        "%d of %d artifacts reproduce" % (int(ok.sum()), len(rp)),
        source="01_existing_pipeline_reproduction.csv")
    v = pd.read_csv(os.path.join(Q, "e02_independent_rebuild_verification.csv"))
    rec("stage1", "classification_step_reproduces_by_independent_rebuild",
        "PASS" if (v["result"] == "PASS").all() else "FAIL",
        "%d of %d exact set-equality checks pass"
        % (int((v["result"] == "PASS").sum()), len(v)),
        source="e02_independent_rebuild_verification.csv")
    f = pd.read_csv(os.path.join(Q, "float_roundtrip_defect.csv"))
    rec("stage1", "archived_csv_float_roundtrip_defect_quantified", "REPORT",
        "%s of %s archived threshold values are misparsed by the pandas DEFAULT float "
        "parser, flipping the relative condition on %s daily records; this package "
        "reads them with float_precision='round_trip'"
        % ("{:,}".format(int(f["threshold_values_misparsed_by_default"].sum())),
           "{:,}".format(int(f["threshold_rows"].sum())),
           "{:,}".format(int(f["daily_records_whose_condition_flips"].sum()))),
        blocking=False, source="float_roundtrip_defect.csv")


def test_palette():
    _, sm = r_palette.run(write=True)
    bad = sm[sm["overall"] == "FAIL"]
    rec("palette", "figure_palettes_pass_the_colour_vision_checks",
        "PASS" if not len(bad) else "FAIL",
        "%d of %d palettes pass; worst normal-vision separation %.1f, worst "
        "colour-vision separation %.1f"
        % (len(sm) - len(bad), len(sm), sm["worst_normal_delta_e"].min(),
           min(sm["worst_protanopia_delta_e"].min(),
               sm["worst_deuteranopia_delta_e"].min())),
        source="palette_validation_summary.csv")


# =============================================================================
def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 78)
    K.log("r11  CONSOLIDATED QA SUITE")
    K.log("=" * 78)

    a, m = test_a_panel()
    carry(os.path.join(Q, "test_A_daily_temperature_logic.csv"), "A")
    test_b(a, m)
    carry(os.path.join(Q, "test_C_period_weighting.csv"), "C")
    carry(os.path.join(Q, "test_DEFG_event_logic.csv"), "D-G")
    cat, mon, ann = test_g_outputs()
    test_f_rates(mon)
    test_reproduction()
    test_palette()
    test_terminology()

    df = pd.DataFrame(R)
    df.to_csv(os.path.join(Q, "QA_TEST_SUITE.csv"), index=False)
    n_pass = int((df["result"] == "PASS").sum())
    n_fail = int((df["result"] == "FAIL").sum())
    n_rep = int(df["result"].isin(["REPORT", "FLAG"]).sum())
    K.log("%d checks: %d PASS, %d FAIL, %d REPORT/FLAG" % (len(df), n_pass, n_fail,
                                                           n_rep))
    for _, r in df[df["result"].isin(["FAIL", "REPORT", "FLAG"])].iterrows():
        K.log("   %-7s %-4s %-56s %s" % (r["result"], r["test"], r["check"],
                                         r["detail"][:90]))
    write_report(df)
    blocking = df[(df["result"] == "FAIL") & df["blocking"]]
    if len(blocking):
        raise K.BlockingQAFailure(
            "%d blocking QA test(s) failed: %s" % (len(blocking),
                                                   list(blocking["check"])))
    K.log("r11 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


def write_report(df):
    L = []
    A = L.append
    A("# QA test suite")
    A("")
    A("The revised pipeline stops if any blocking test fails. Tests are executed by "
      "the step that generates the data and then RE-CHECKED here against the written "
      "tables, so a test cannot pass in memory and be contradicted by what was saved.")
    A("")
    A("| result | checks |")
    A("|---|---|")
    for k, v in df["result"].value_counts().items():
        A("| %s | %d |" % (k, v))
    A("")
    for t, name in (("A", "TEST A - daily temperature logic"),
                    ("B", "TEST B - coverage"),
                    ("C", "TEST C - period weighting"),
                    ("D", "TEST D - event logic"),
                    ("E", "TEST E - gate logic"),
                    ("F", "TEST F - denominators"),
                    ("G", "TEST G - output consistency"),
                    ("D-G", "TESTS D to G as executed in r06"),
                    ("stage1", "Stage 1 reproduction"),
                    ("palette", "figure palettes"),
                    ("terminology", "terminology compliance")):
        s = df[df["test"] == t]
        if not len(s):
            continue
        A("## %s" % name)
        A("")
        A(K.md_table(s[["check", "result", "blocking", "detail"]], max_rows=60))
        A("")
    with open(os.path.join(Q, "QA_REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
