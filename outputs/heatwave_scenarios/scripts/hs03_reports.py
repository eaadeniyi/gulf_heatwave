"""
=============================================================================
hs03_reports.py  --  registry, per-construct summaries, and the QA summary.
=============================================================================
Implements plan revision 6, sections 10 and 13.

REPORTING HIERARCHY (this project's standing convention):
  PRIMARY   per-construct county-date / event / county-month / county-year tables.
            These are the substantive results.
  SECONDARY scenario_summary_QA.csv -- pooled cross-county medians and shares,
            every field explicitly _QA-suffixed, never a headline number.

Every QA aggregation formula is stated exactly (a field name like
"median_annual_classified_date_count" is open to at least three readings, so the
one used is written down here and in the data dictionary):
  median_annual_classified_date_count_QA
      = median across ALL eligible county x year records
        (NOT a median-of-per-county-medians, NOT a median of statewide annual sums)
  median_annual_event_count_QA
      = same basis; ALWAYS NA for EHF rows, whose event units are not
        cross-family comparable (they live in ehf_summary.csv instead)
  jun_sep_classified_date_share_QA
      = classified county-date records in Jun-Sep / all classified county-date
        records -- a POOLED share, not averaged per county first
  classified_days_per_1000_valid_eligible_QA
      = 1000 * classified daily records / valid eligible daily records, per month
        -- a RATE, reported alongside the share because they answer different questions
=============================================================================
"""
import os, sys, time, json, subprocess, hashlib, datetime
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hs00_config as H

ANALYSIS_N_YEARS = H.ANALYSIS_YEARS[1] - H.ANALYSIS_YEARS[0] + 1


def log(*a):
    print(*a, flush=True)


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=H.PROJECT_ROOT,
                              capture_output=True, text=True, timeout=20).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return "md5:" + h.hexdigest()[:16]


def definition_fingerprint(construct):
    """Hash of every methodological setting -- so a construct's identity captures
    HOW it was produced, not just its name."""
    payload = {k: construct.get(k) for k in
               ("family", "metric", "percentile", "min_duration", "window", "baseline",
                "season_rule", "qc_tier", "date_representation", "event_definition_type")}
    payload.update({
        "analysis_years": list(H.ANALYSIS_YEARS), "baseline_start": H.BASELINE_START,
        "fixed_baseline": list(H.FIXED_BASELINE), "comparison_op": H.COMPARISON_OP,
        "window_type": "centered_calendar_day", "window_width_days": 15,
        "days_before": 7, "days_after": 7, "quantile_method": "numpy_linear",
        "leap_day_rule": "template_doy_366_leap_safe",
        "min_reference_completeness_fraction": H.MIN_REFERENCE_COMPLETENESS_FRACTION,
        "min_distinct_reference_years": H.MIN_DISTINCT_REFERENCE_YEARS,
        "excessive_reference_imputation_threshold": H.EXCESSIVE_REFERENCE_IMPUTATION_THRESHOLD,
    })
    return "fp:" + hashlib.md5(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


# =============================================================================
# per-construct county-level tables (PRIMARY outputs)
# =============================================================================
def build_county_tables(cid, construct):
    """From the per-construct daily/event detail, build county-year and county-month.
    Reused constructs already have these copied from outputs/TX/grid/."""
    tdir = os.path.join(H.construct_dir(cid, make=False), "tables")
    if construct["reused_from_grid"]:
        cy = pd.read_csv(os.path.join(tdir, "county_year_summary.csv"), dtype={"county_fips": str})
        return cy, None

    if construct["family"] == "ehf":
        p = os.path.join(tdir, "ehf_positive_assessment_dates.csv.gz")
        if not os.path.exists(p):
            return None, None
        d = pd.read_csv(p, usecols=["county_fips", "date", "year", "month"], dtype={"county_fips": str})
        date_col = "classified_assessment_dates"
    else:
        p = os.path.join(tdir, "daily_classified.csv.gz")
        if not os.path.exists(p):
            return None, None
        d = pd.read_csv(p, usecols=["county_fips", "date", "year", "month"], dtype={"county_fips": str})
        date_col = "classified_dates"

    cy = d.groupby(["county_fips", "year"]).size().rename(date_col).reset_index()
    cm = d.groupby(["county_fips", "year", "month"]).size().rename(date_col).reset_index()

    # event counts per county-year, by ONSET year (an event spanning a year boundary is
    # counted once, in the year it started). EHF's two event tables are deliberately NOT
    # merged into this column -- its event units are not cross-family comparable, so the
    # QA summary leaves median_annual_event_count_QA as NA for EHF and reports the real
    # EHF counts only in ehf_summary.csv.
    ev_path = os.path.join(tdir, "events.csv.gz")
    if construct["family"] != "ehf" and os.path.exists(ev_path):
        ev = pd.read_csv(ev_path, usecols=["county_fips", "start_date"], dtype={"county_fips": str})
        ev["onset_year"] = pd.to_datetime(ev["start_date"]).dt.year
        ec = (ev.groupby(["county_fips", "onset_year"]).size()
              .rename("events_started").reset_index()
              .rename(columns={"onset_year": "year"}))
        cy = cy.merge(ec, on=["county_fips", "year"], how="left")
        cy["events_started"] = cy["events_started"].fillna(0).astype(int)

    cy.to_csv(os.path.join(tdir, "county_year_summary.csv"), index=False)
    cm.to_csv(os.path.join(tdir, "county_month_summary.csv"), index=False)
    return cy, cm


# =============================================================================
# QA summary (SECONDARY -- pooled, never headline)
# =============================================================================
def qa_row(cid, construct, cy, cm, daily_month_counts, n_counties, eligible_daily_records):
    fam = construct["family"]
    is_ehf = (fam == "ehf")

    # per county x year classified-date counts, reindexed over ALL counties x ALL analysis
    # years so counties/years with zero classified dates count toward the median (they are
    # genuine zeros, not missing data)
    if cy is not None and len(cy):
        valcol = [c for c in cy.columns if c not in ("county_fips", "year", "county_name")]
        cnt_col = ("heatwave_days" if "heatwave_days" in cy.columns else valcol[0])
        full_idx = pd.MultiIndex.from_product(
            [sorted(set(cy["county_fips"])), range(H.ANALYSIS_YEARS[0], H.ANALYSIS_YEARS[1] + 1)],
            names=["county_fips", "year"])
        s = cy.set_index(["county_fips", "year"])[cnt_col].reindex(full_idx, fill_value=0)
        median_annual_dates = float(s.median())
        total_classified = int(s.sum())
    else:
        median_annual_dates, total_classified = np.nan, 0

    # median annual EVENT count -- NA for EHF by construction (its event units are not
    # cross-family comparable; the real EHF event counts live in ehf_summary.csv)
    median_annual_events = np.nan
    if not is_ehf and cy is not None:
        # reused grid cells carry 'heatwave_events_started'; newly-computed cells carry
        # 'events_started' (built in build_county_tables) -- accept either
        evcol = next((c for c in ("heatwave_events_started", "events_started") if c in cy.columns), None)
        if evcol:
            full_idx = pd.MultiIndex.from_product(
                [sorted(set(cy["county_fips"])), range(H.ANALYSIS_YEARS[0], H.ANALYSIS_YEARS[1] + 1)],
                names=["county_fips", "year"])
            se = cy.set_index(["county_fips", "year"])[evcol].reindex(full_idx, fill_value=0)
            median_annual_events = float(se.median())

    # pooled seasonal SHARES of classified dates (not per-county averages)
    shares = {"jun_sep": np.nan, "may_oct": np.nan, "nov_apr": np.nan}
    if daily_month_counts is not None and daily_month_counts.sum() > 0:
        tot = daily_month_counts.sum()
        shares["jun_sep"] = round(100 * daily_month_counts.reindex([6, 7, 8, 9]).fillna(0).sum() / tot, 2)
        shares["may_oct"] = round(100 * daily_month_counts.reindex([5, 10]).fillna(0).sum() / tot, 2)
        shares["nov_apr"] = round(100 * daily_month_counts.reindex([11, 12, 1, 2, 3, 4]).fillna(0).sum() / tot, 2)

    rate = np.nan
    if eligible_daily_records:
        rate = round(1000.0 * total_classified / eligible_daily_records, 3)

    return {
        "construct_id": cid, "family": fam, "role": construct["role"],
        "date_representation": construct["date_representation"],
        "event_definition_type": construct["event_definition_type"],
        "cross_family_comparable_events": construct["cross_family_comparable_events"],
        "classified_date_count_QA": total_classified,
        "median_annual_classified_date_count_QA": median_annual_dates,
        "median_annual_event_count_QA": median_annual_events,
        "season_rule": construct["season_rule"], "qc_tier": construct["qc_tier"],
        "jun_sep_classified_date_share_QA": shares["jun_sep"],
        "may_oct_classified_date_share_QA": shares["may_oct"],
        "nov_apr_classified_date_share_QA": shares["nov_apr"],
        "classified_days_per_1000_valid_eligible_QA": rate,
        "definition_fingerprint": definition_fingerprint(construct),
        "status": "done",
    }


# =============================================================================
# driver
# =============================================================================
def build(state="TX"):
    t0 = time.time()
    commit = git_commit()
    derived_path = os.path.join(H.TABLES_DIR, "_derived_variables_%s.csv.gz" % state)
    input_fp = file_md5(H.county_day_path(state))

    # eligible daily-record denominator (per construct family/season), for the rate field
    dv = pd.read_csv(derived_path, usecols=["county_fips", "year", "month", "qc_category"],
                     dtype={"county_fips": str})
    an = dv[(dv["year"] >= H.ANALYSIS_YEARS[0]) & (dv["year"] <= H.ANALYSIS_YEARS[1])]
    n_counties = an["county_fips"].nunique()

    rows, registry_rows = [], []
    for construct in H.CONSTRUCTS:
        cid = construct["construct_id"]
        cy, cm = build_county_tables(cid, construct)

        # month-of-year distribution of classified dates, for the seasonal shares
        tdir = os.path.join(H.construct_dir(cid, make=False), "tables")
        month_counts = None
        for fname in ("daily_classified.csv.gz", "ehf_positive_assessment_dates.csv.gz"):
            p = os.path.join(tdir, fname)
            if os.path.exists(p):
                dd = pd.read_csv(p, usecols=["month"])
                month_counts = dd["month"].value_counts().sort_index()
                break
        if month_counts is None and construct["reused_from_grid"] and cm is None:
            cm_path = os.path.join(tdir, "county_month_summary.csv")
            if os.path.exists(cm_path):
                cmx = pd.read_csv(cm_path)
                if "heatwave_days" in cmx.columns:
                    month_counts = cmx.groupby("month")["heatwave_days"].sum()

        # eligible denominator: excluded QC categories are not eligible; out-of-season is not eligible
        excl = {"CONFEXCL": {"confirmed_artifact"},
                "PROBEXCL": {"confirmed_artifact", "rule_flagged_probable_artifact"}}.get(
                    construct.get("qc_tier"), set())
        elig = an[~an["qc_category"].isin(excl)] if excl else an
        if construct["season_rule"] == "june_september":
            elig = elig[elig["month"].between(6, 9)]
        eligible_daily_records = len(elig)

        rows.append(qa_row(cid, construct, cy, cm, month_counts, n_counties, eligible_daily_records))

        registry_rows.append(dict(
            construct, definition_fingerprint=definition_fingerprint(construct),
            window_type="centered_calendar_day", window_width_days=15, days_before=7, days_after=7,
            quantile_method="numpy_linear", leap_day_rule="template_doy_366_leap_safe",
            comparison_op=H.COMPARISON_OP, analysis_years="%d-%d" % H.ANALYSIS_YEARS,
            threshold_reference_season="year_round_calendar_window",
            analysis_eligibility_season=construct["season_rule"],
            season_applied_before_run_construction=(construct["season_rule"] != "year_round"),
            season_boundary_breaks_run=(construct["season_rule"] != "year_round"),
            eligible_daily_records=eligible_daily_records,
            git_commit=commit, input_fingerprint=input_fp,
            generated_utc=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            status="done"))

    reg = pd.DataFrame(registry_rows)
    reg.to_csv(H.REGISTRY_FILE, index=False)
    log("[registry] %s (%d rows)" % (H.REGISTRY_FILE, len(reg)))

    qa = pd.DataFrame(rows)
    qa_path = os.path.join(H.TABLES_DIR, "scenario_summary_QA.csv")
    qa.to_csv(qa_path, index=False)
    log("[summary] %s (%d rows)" % (qa_path, len(qa)))

    # family-specific summaries
    for fam, fname in (("ehf", "ehf_summary.csv"), ("tmax", "temperature_percentile_summary.csv"),
                       ("hiproxy", "heat_index_proxy_summary.csv"),
                       ("hixenv", "synthetic_envelope_summary.csv")):
        sub = qa[qa["family"] == fam]
        if fam == "ehf":
            ehf_rows = []
            for construct in H.constructs_by_family("ehf"):
                cid = construct["construct_id"]
                tdir = os.path.join(H.construct_dir(cid, make=False), "tables")
                pp = pd.read_csv(os.path.join(tdir, "ehf_positive_periods.csv"))
                ts = pd.read_csv(os.path.join(tdir, "ehf_thermal_support_events.csv"))
                ehf_rows.append({
                    "construct_id": cid, "baseline": construct["baseline"], "role": construct["role"],
                    "literature_replication_status": construct.get("literature_replication_status"),
                    "positive_ehf_period_count": len(pp),
                    "positive_period_longest_duration_days": int(pp["event_duration_days"].max()) if len(pp) else 0,
                    "thermal_support_event_count": len(ts),
                    "thermal_support_longest_duration_days": int(ts["support_duration_days"].max()) if len(ts) else 0,
                    "benchmark_event_table": "ehf_positive_periods.csv",
                    "sensitivity_event_table": "ehf_thermal_support_events.csv",
                    "cross_family_comparable_events": False,
                })
            pd.DataFrame(ehf_rows).to_csv(os.path.join(H.TABLES_DIR, fname), index=False)
        else:
            sub.to_csv(os.path.join(H.TABLES_DIR, fname), index=False)
        log("[family] %s" % fname)

    log("[done] hs03 in %.0fs" % (time.time() - t0))
    return reg, qa


if __name__ == "__main__":
    build()
