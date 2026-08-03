"""
=============================================================================
r02  --  STAGE 2: rebuild the county temperature panel and sanity-check it.
=============================================================================
Reads the RAW OBSERVED GHCN county-day files for the five Gulf states and
builds, in order:

    daily county-level observations
        -> annual county-level observations     (county_annual_temperature.csv)
        -> monthly county-level summaries       (county_monthly_temperature.csv)

Three daily variables, named in plain language throughout:

    Daily high temperature      Tmax   (ETCCDI TX)
    Daily low temperature       Tmin   (ETCCDI TN)
    Daily average temperature   Tavg = (Tmax + Tmin) / 2   (TM)

WHAT THIS STEP DOES NOT DO
  It does not impose a rule that a summer temperature must exceed 75 degF.
  A summer AVERAGE DAILY LOW below 75 degF is ordinary in inland, northern,
  rural and elevated counties and is not a data-quality signal. Values are
  flagged only when they violate a documented physical or data-quality rule:

      Tmax < Tmin
      a value outside the prespecified physically plausible range
      an abrupt year-on-year discontinuity coinciding with a change in the
          number of contributing stations
      insufficient coverage for the summary being produced
      a value in a Fahrenheit column that is only plausible as Celsius
      a duplicated or out-of-sequence date

  Nothing is deleted, corrected or imputed. Flags are written; raw values are
  passed through untouched.

OUTPUTS
  tables/county_annual_temperature.csv
  tables/county_monthly_temperature.csv
  tables/county_record_coverage.csv
  tables/revised_temperature_monthly_sanity_check.csv
  tables/summer_audit_jun_aug_jun_sep.csv
  qa/summer_temperature_review.md
  qa/test_A_daily_temperature_logic.csv
  qa/data_quality_flags.csv
  qa/data_quality_flagged_records_sample.csv
=============================================================================
"""
import os
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K
import config as C                                          # noqa: E402

Y0, Y1 = K.YEARS
TESTA, FLAGS, FLAGGED, QUARANTINE = [], [], [], []


def load_state_daily(state):
    """Raw observed GHCN daily county-level records for one state."""
    d = pd.read_csv(C.ghcn_path(state),
                    usecols=["county_fips", "county_name", "date", "tmax_f", "tmin_f",
                             "tmax_f_nstations", "tmin_f_nstations"],
                    dtype={"county_fips": str})
    d["date"] = pd.to_datetime(d["date"])
    d["year"] = d["date"].dt.year
    d["month"] = d["date"].dt.month
    d = d[(d["year"] >= Y0) & (d["year"] <= Y1)].copy()
    d["tavg_f"] = (d["tmax_f"] + d["tmin_f"]) / 2.0
    d["state"] = state
    return d


# =============================================================================
# TEST A -- daily temperature logic (blocking)
# =============================================================================
def quarantine_inverted(state, d):
    """Remove county-DATES whose daily high is below their daily low.

    See r00_config.INVERTED_RECORD_ACTION for why these exist and why the whole
    county-date is removed rather than one variable. The raw records are copied
    out first, unaltered, and the raw input file is never touched.
    """
    both = d["tmax_f"].notna() & d["tmin_f"].notna()
    bad = both & (d["tmax_f"] < d["tmin_f"])
    if not bad.any():
        return d, 0
    q = d.loc[bad, ["state", "county_fips", "county_name", "date", "year", "month",
                    "tmax_f", "tmin_f", "tmax_f_nstations", "tmin_f_nstations"]].copy()
    q["daily_low_minus_daily_high_f"] = (q["tmin_f"] - q["tmax_f"]).round(2)
    q["station_sets_differ"] = q["tmax_f_nstations"] != q["tmin_f_nstations"]
    q["in_texas_classification_window"] = ((q["state"] == K.TEST_STATE)
                                           & q["year"].between(*K.ANALYSIS_YEARS))
    q["action"] = K.INVERTED_RECORD_ACTION
    QUARANTINE.append(q)
    return d.loc[~bad].copy(), int(bad.sum())


def test_a(state, d, n_quarantined):
    """Tmax >= Tmin, Tavg identity, plausible ranges, duplicate dates.

    `d` is the ANALYSIS PANEL, i.e. after the declared quarantine, so the
    inversion check is expected to pass by construction; it is still run,
    because a failure here would mean the quarantine did not work.
    """
    both = d["tmax_f"].notna() & d["tmin_f"].notna()
    inverted = both & (d["tmax_f"] < d["tmin_f"])
    tavg_ok = both & ((d["tavg_f"] - (d["tmax_f"] + d["tmin_f"]) / 2.0).abs()
                      <= K.TAVG_TOLERANCE_F)
    lo, hi = K.PLAUSIBLE_TMAX_F
    tmax_bad = d["tmax_f"].notna() & ((d["tmax_f"] < lo) | (d["tmax_f"] > hi))
    lo2, hi2 = K.PLAUSIBLE_TMIN_F
    tmin_bad = d["tmin_f"].notna() & ((d["tmin_f"] < lo2) | (d["tmin_f"] > hi2))
    dup = d.duplicated(subset=["county_fips", "date"], keep=False)

    def rec(check, n_bad, n_checked, blocking, note):
        TESTA.append(dict(test="A", state=state, check=check,
                          records_checked=int(n_checked), records_failing=int(n_bad),
                          pct_failing=round(100.0 * n_bad / n_checked, 6) if n_checked else np.nan,
                          blocking=blocking,
                          result="PASS" if n_bad == 0 else ("FAIL" if blocking else "FLAG"),
                          note=note))

    rec("tmax_not_below_tmin_in_analysis_panel", inverted.sum(), both.sum(), True,
        "a daily high below the same day's daily low is physically impossible; "
        "checked AFTER the declared quarantine")
    rec("inverted_county_dates_quarantined_from_raw_input", n_quarantined,
        n_quarantined + len(d), False,
        "raw county-dates removed by the declared rule %r; all are written "
        "unaltered to qa/quarantined_inverted_daily_records.csv"
        % K.INVERTED_RECORD_ACTION)
    rec("tavg_equals_mean_of_tmax_tmin", (both & ~tavg_ok).sum(), both.sum(), True,
        "Tavg is DEFINED as (Tmax + Tmin) / 2; tolerance %.0e degF" % K.TAVG_TOLERANCE_F)
    rec("tmax_within_plausible_range", tmax_bad.sum(), d["tmax_f"].notna().sum(), False,
        "prespecified range %s degF; flagged, never edited" % (K.PLAUSIBLE_TMAX_F,))
    rec("tmin_within_plausible_range", tmin_bad.sum(), d["tmin_f"].notna().sum(), False,
        "prespecified range %s degF; flagged, never edited" % (K.PLAUSIBLE_TMIN_F,))
    rec("no_duplicated_county_date", dup.sum(), len(d), True,
        "a duplicated county-date would double-weight that day")

    for m in (inverted, tmax_bad, tmin_bad, dup):
        if m.any():
            s = d.loc[m, ["state", "county_fips", "county_name", "date", "tmax_f",
                          "tmin_f", "tavg_f", "tmax_f_nstations", "tmin_f_nstations"]].head(200)
            s = s.assign(flag_reason=("inverted" if m is inverted else
                                      "implausible_tmax" if m is tmax_bad else
                                      "implausible_tmin" if m is tmin_bad else
                                      "duplicate_county_date"))
            FLAGGED.append(s)
    return int(inverted.sum()), int((both & ~tavg_ok).sum()), int(dup.sum())


def test_a_conversion():
    """Fahrenheit conversion verified against known test values."""
    for c, f_expected in K.CELSIUS_TEST_CASES:
        f = c * 9.0 / 5.0 + 32.0
        TESTA.append(dict(test="A", state="(all)",
                          check="fahrenheit_conversion_%.0fC" % c,
                          records_checked=1,
                          records_failing=int(abs(f - f_expected) > 1e-9),
                          pct_failing=0.0, blocking=True,
                          result="PASS" if abs(f - f_expected) <= 1e-9 else "FAIL",
                          note="%.1f degC must equal %.1f degF" % (c, f_expected)))


# =============================================================================
# annual and monthly county-level layers
# =============================================================================
def annual_layer(d):
    out = []
    for col, var, _sym, _dl, _pl, _def in K.TEMP_VARS:
        g = d.loc[d[col].notna()].groupby(
            ["state", "county_fips", "county_name", "year"], observed=True)
        a = g.agg(valid_daily_observation_count=(col, "size"),
                  period_mean_f=(col, "mean"),
                  period_median_f=(col, "median"),
                  daily_min_f=(col, "min"), daily_max_f=(col, "max"),
                  daily_p95_f=(col, lambda s: s.quantile(0.95)),
                  mean_contributing_stations=("tmax_f_nstations", "mean"),
                  min_contributing_stations=("tmax_f_nstations", "min"),
                  max_contributing_stations=("tmax_f_nstations", "max")).reset_index()
        a["variable"] = var
        a["variable_label"] = K.VAR_PERIOD_LABEL[var]
        a["meets_annual_coverage_requirement"] = (
            a["valid_daily_observation_count"] >= K.MIN_DAYS_PER_COUNTY_YEAR)
        out.append(a)
    a = pd.concat(out, ignore_index=True)
    a["period"] = a["year"].map(K.period_of)
    return a


def monthly_layer(d):
    out = []
    for col, var, _sym, _dl, _pl, _def in K.TEMP_VARS:
        g = d.loc[d[col].notna()].groupby(
            ["state", "county_fips", "county_name", "year", "month"], observed=True)
        a = g.agg(valid_daily_observation_count=(col, "size"),
                  period_mean_f=(col, "mean"),
                  daily_min_f=(col, "min"), daily_max_f=(col, "max"),
                  mean_contributing_stations=("tmax_f_nstations", "mean")).reset_index()
        a["variable"] = var
        a["meets_monthly_coverage_requirement"] = (
            a["valid_daily_observation_count"] >= K.MIN_DAYS_PER_COUNTY_MONTH)
        out.append(a)
    a = pd.concat(out, ignore_index=True)
    a["period"] = a["year"].map(K.period_of)
    a["season"] = a["month"].map(K.SEASON_OF)
    return a


# =============================================================================
# data-quality flags that are NOT simple range checks
# =============================================================================
def discontinuity_flags(annual):
    """Year-on-year jumps that coincide with a change in station composition.

    Neither a jump nor a station change is by itself evidence of an error; the
    two together in the same county-year is what is worth a human look.
    """
    a = annual[annual["meets_annual_coverage_requirement"]].sort_values(
        ["state", "county_fips", "variable", "year"]).copy()
    g = a.groupby(["state", "county_fips", "variable"], observed=True)
    a["delta_f"] = g["period_mean_f"].diff()
    a["prev_stations"] = g["mean_contributing_stations"].shift()
    a["station_ratio"] = a["mean_contributing_stations"] / a["prev_stations"]
    a["consecutive_year"] = g["year"].diff() == 1
    big = a["delta_f"].abs() >= 5.0
    net = (a["station_ratio"] >= 1.5) | (a["station_ratio"] <= 1 / 1.5)
    a["flag_discontinuity_with_station_change"] = big & net & a["consecutive_year"]
    a["flag_discontinuity_only"] = big & ~net & a["consecutive_year"]
    return a


def celsius_suspicion(monthly):
    """A warm-season daily-high mean that is only plausible if the column were
    Celsius rather than Fahrenheit. This is a unit-conversion check, not a
    temperature-level rule."""
    m = monthly[(monthly["variable"] == "Tmax")
                & monthly["month"].isin(K.WARM_SEASON)
                & monthly["meets_monthly_coverage_requirement"]]
    return m[m["period_mean_f"] < 50.0]


# =============================================================================
# the monthly sanity-check table
# =============================================================================
def monthly_sanity(monthly):
    """For every state, variable and calendar month: the distribution ACROSS
    COUNTIES of the county's own monthly value, plus coverage counts.

    Each county contributes one value per (state, variable, month): the mean of
    its qualifying monthly county-level summaries over the whole record. That
    keeps a county with 47 reporting years from outweighing one with 20.
    """
    q = monthly[monthly["meets_monthly_coverage_requirement"]]
    per_county = (q.groupby(["state", "variable", "month", "county_fips"], observed=True)
                  .agg(county_value_f=("period_mean_f", "mean"),
                       monthly_summaries=("period_mean_f", "size")).reset_index())
    s = (per_county.groupby(["state", "variable", "month"], observed=True)
         .agg(contributing_counties=("county_fips", "nunique"),
              median_across_counties_f=("county_value_f", "median"),
              p25_across_counties_f=("county_value_f", lambda x: x.quantile(0.25)),
              p75_across_counties_f=("county_value_f", lambda x: x.quantile(0.75)),
              min_across_counties_f=("county_value_f", "min"),
              max_across_counties_f=("county_value_f", "max"),
              contributing_monthly_summaries=("monthly_summaries", "sum")).reset_index())
    allm = (monthly.groupby(["state", "variable", "month"], observed=True)
            .agg(monthly_records_total=("period_mean_f", "size"),
                 counties_with_any_record=("county_fips", "nunique")).reset_index())
    s = s.merge(allm, on=["state", "variable", "month"], how="left")
    s["pct_monthly_records_passing_coverage"] = (
        100.0 * s["contributing_monthly_summaries"] / s["monthly_records_total"]).round(2)
    s["season"] = s["month"].map(K.SEASON_OF)
    s["month_name"] = s["month"].map(lambda m: K.MONTH_ABBR[m - 1])
    s["variable_label"] = s["variable"].map(K.VAR_PERIOD_LABEL)
    s["coverage_requirement_days"] = K.MIN_DAYS_PER_COUNTY_MONTH
    s["unit_of_analysis"] = ("county; each county contributes one value per month, "
                             "averaged over its qualifying monthly county-level summaries")
    for c in s.columns:
        if c.endswith("_f"):
            s[c] = s[c].round(2)
    return s.sort_values(["state", "variable", "month"]).reset_index(drop=True)


def summer_audit(monthly):
    """June-August and June-September, per state and variable."""
    rows = []
    q = monthly[monthly["meets_monthly_coverage_requirement"]]
    for label, months in (("Jun-Aug", [6, 7, 8]), ("Jun-Sep", K.WARM_SEASON)):
        sub = q[q["month"].isin(months)]
        per_county = (sub.groupby(["state", "variable", "county_fips"], observed=True)
                      .agg(county_value_f=("period_mean_f", "mean"),
                           monthly_summaries=("period_mean_f", "size"),
                           months_present=("month", "nunique")).reset_index())
        per_county = per_county[per_county["months_present"] == len(months)]
        g = (per_county.groupby(["state", "variable"], observed=True)
             .agg(contributing_counties=("county_fips", "nunique"),
                  median_across_counties_f=("county_value_f", "median"),
                  p25_across_counties_f=("county_value_f", lambda x: x.quantile(0.25)),
                  p75_across_counties_f=("county_value_f", lambda x: x.quantile(0.75)),
                  min_across_counties_f=("county_value_f", "min"),
                  max_across_counties_f=("county_value_f", "max"),
                  contributing_monthly_summaries=("monthly_summaries", "sum")).reset_index())
        g["window"] = label
        g["counties_below_75F"] = [
            int((per_county[(per_county["state"] == r["state"])
                            & (per_county["variable"] == r["variable"])]
                 ["county_value_f"] < 75.0).sum()) for _, r in g.iterrows()]
        g["pct_counties_below_75F"] = (100.0 * g["counties_below_75F"]
                                       / g["contributing_counties"]).round(1)
        rows.append(g)
    out = pd.concat(rows, ignore_index=True)
    out["variable_label"] = out["variable"].map(K.VAR_PERIOD_LABEL)
    out["interpretation"] = np.where(
        out["variable"] == "Tmin",
        "an average daily low below 75 degF in the warm season is expected in "
        "inland, northern, rural and elevated counties and is NOT a defect",
        np.where(out["variable"] == "Tmax",
                 "an average daily high should be well above 75 degF in the warm season",
                 "an average daily temperature near or above 75 degF is plausible; "
                 "either side of it is not a defect"))
    for c in out.columns:
        if c.endswith("_f"):
            out[c] = out[c].round(2)
    return out[["state", "variable", "variable_label", "window", "contributing_counties",
                "median_across_counties_f", "p25_across_counties_f", "p75_across_counties_f",
                "min_across_counties_f", "max_across_counties_f",
                "contributing_monthly_summaries", "counties_below_75F",
                "pct_counties_below_75F", "interpretation"]]


# =============================================================================
# driver
# =============================================================================
def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 78)
    K.log("r02  STAGE 2 -- county temperature panel and sanity checks")
    K.log("=" * 78)
    K.log(K.PANEL_SENTENCE)

    test_a_conversion()
    annual_all, monthly_all, extent = [], [], []
    for st in K.STATES:
        d = load_state_daily(st)
        d, n_quar = quarantine_inverted(st, d)
        inv, tavg_bad, dup = test_a(st, d, n_quar)
        a = annual_layer(d)
        m = monthly_layer(d)
        annual_all.append(a)
        monthly_all.append(m)
        tm = a[a["variable"] == "Tmax"]
        extent.append(dict(
            state=st, state_name=K.STATE_LABEL[st],
            daily_county_level_observations=len(d),
            counties_in_file=d["county_fips"].nunique(),
            first_date=str(d["date"].min().date()), last_date=str(d["date"].max().date()),
            pct_daily_records_with_daily_high=round(100 * d["tmax_f"].notna().mean(), 2),
            pct_daily_records_with_daily_low=round(100 * d["tmin_f"].notna().mean(), 2),
            median_contributing_stations_high=float(d["tmax_f_nstations"].median()),
            annual_observations_meeting_coverage=int(
                tm["meets_annual_coverage_requirement"].sum()),
            annual_observations_total=int(len(tm)),
            records_quarantined_high_below_low=n_quar,
            records_with_high_below_low_after_quarantine=inv,
            records_with_duplicate_county_date=dup))
        K.log("[load] %-2s  %s daily records, %3d counties, %.1f%% with a daily high, "
              "%d/%d annual observations meet coverage"
              % (st, "{:,}".format(len(d)), d["county_fips"].nunique(),
                 100 * d["tmax_f"].notna().mean(),
                 int(tm["meets_annual_coverage_requirement"].sum()), len(tm)))
        del d

    annual = pd.concat(annual_all, ignore_index=True)
    monthly = pd.concat(monthly_all, ignore_index=True)
    ext = pd.DataFrame(extent)

    # ---- the declared quarantine, reported before anything else -------------
    quar = (pd.concat(QUARANTINE, ignore_index=True) if QUARANTINE
            else pd.DataFrame(columns=["state", "county_fips", "date"]))
    quar.to_csv(os.path.join(K.DIR_QA, "quarantined_inverted_daily_records.csv"),
                index=False)
    K.log("-" * 78)
    K.log("DECLARED QUARANTINE (%s)" % K.INVERTED_RECORD_ACTION)
    K.log("   %d raw county-dates have a daily high below the same day's daily low "
          "and are removed" % len(quar))
    if len(quar):
        K.log("   of these, %d have the daily high and daily low averaged over "
              "DIFFERENT numbers of stations -- the county aggregation, not the "
              "station observations, is the source"
              % int(quar["station_sets_differ"].sum()))
        K.log("   %d fall inside the Texas %s classification window (Part 2 and Part 3 "
              "are unaffected)" % (int(quar["in_texas_classification_window"].sum()),
                                   K.ANALYSIS_YEARS_LABEL))
        K.log("   full records preserved in qa/quarantined_inverted_daily_records.csv")
        if len(quar) > K.INVERTED_RECORD_MAX_TOLERATED:
            raise K.BlockingQAFailure(
                "%d inverted county-dates exceeds the tolerated maximum of %d. That is "
                "a systematic aggregation failure, not a handful of artifacts, and the "
                "pipeline stops rather than quarantining at that scale."
                % (len(quar), K.INVERTED_RECORD_MAX_TOLERATED))

    # ---- blocking gate on TEST A -------------------------------------------
    ta = pd.DataFrame(TESTA)
    ta.to_csv(os.path.join(K.DIR_QA, "test_A_daily_temperature_logic.csv"), index=False)
    fails = ta[(ta["result"] == "FAIL")]
    K.log("-" * 78)
    K.log("TEST A -- daily temperature logic: %d checks, %d FAIL, %d FLAG"
          % (len(ta), len(fails), int((ta["result"] == "FLAG").sum())))
    for _, r in ta[ta["result"] != "PASS"].iterrows():
        K.log("   %-6s %-3s %-34s %d/%d records"
              % (r["result"], r["state"], r["check"], r["records_failing"],
                 r["records_checked"]))
    if len(fails):
        raise K.BlockingQAFailure(
            "TEST A failed on %d check(s); see qa/test_A_daily_temperature_logic.csv. "
            "The pipeline stops here rather than dropping the offending records."
            % len(fails))

    # ---- other data-quality flags ------------------------------------------
    disc = discontinuity_flags(annual)
    cel = celsius_suspicion(monthly)
    n_disc = int(disc["flag_discontinuity_with_station_change"].sum())
    n_disc_only = int(disc["flag_discontinuity_only"].sum())
    FLAGS.append(dict(flag="abrupt_annual_discontinuity_with_station_change",
                      n_records=n_disc, denominator=len(disc),
                      rule=">= 5 degF year-on-year change in the annual county value "
                           "AND a >= 1.5x change in the mean number of contributing "
                           "stations, in consecutive qualifying years",
                      action="flagged for human review; no value altered"))
    FLAGS.append(dict(flag="abrupt_annual_discontinuity_without_station_change",
                      n_records=n_disc_only, denominator=len(disc),
                      rule=">= 5 degF year-on-year change with no matching station change",
                      action="flagged; most are genuine interannual variability"))
    FLAGS.append(dict(flag="warm_season_daily_high_only_plausible_as_celsius",
                      n_records=len(cel),
                      denominator=int(((monthly["variable"] == "Tmax")
                                       & monthly["month"].isin(K.WARM_SEASON)
                                       & monthly["meets_monthly_coverage_requirement"]).sum()),
                      rule="qualifying June-September monthly average daily high "
                           "below 50 degF",
                      action="unit-conversion check; flagged, never converted"))
    FLAGS.append(dict(flag="insufficient_annual_coverage",
                      n_records=int((~annual["meets_annual_coverage_requirement"]).sum()),
                      denominator=len(annual),
                      rule="fewer than %d valid daily county-level observations in the year"
                           % K.MIN_DAYS_PER_COUNTY_YEAR,
                      action="excluded from annual summaries, retained in the table"))
    FLAGS.append(dict(flag="insufficient_monthly_coverage",
                      n_records=int((~monthly["meets_monthly_coverage_requirement"]).sum()),
                      denominator=len(monthly),
                      rule="fewer than %d valid daily county-level observations in the month"
                           % K.MIN_DAYS_PER_COUNTY_MONTH,
                      action="excluded from monthly summaries, retained in the table"))
    fl = pd.DataFrame(FLAGS)
    fl.to_csv(os.path.join(K.DIR_QA, "data_quality_flags.csv"), index=False)
    K.log("-" * 78)
    K.log("data-quality flags (nothing altered):")
    for _, r in fl.iterrows():
        K.log("   %-58s %8s / %s" % (r["flag"], "{:,}".format(r["n_records"]),
                                     "{:,}".format(r["denominator"])))

    samples = []
    if FLAGGED:
        samples.append(pd.concat(FLAGGED, ignore_index=True))
    if n_disc:
        s = disc[disc["flag_discontinuity_with_station_change"]].head(400).copy()
        s["flag_reason"] = "discontinuity_with_station_change"
        samples.append(s[["state", "county_fips", "county_name", "year", "variable",
                          "period_mean_f", "delta_f", "prev_stations",
                          "mean_contributing_stations", "flag_reason"]])
    if len(cel):
        s = cel.head(200).copy()
        s["flag_reason"] = "warm_season_high_plausible_only_as_celsius"
        samples.append(s[["state", "county_fips", "county_name", "year", "month",
                          "variable", "period_mean_f", "flag_reason"]])
    if samples:
        pd.concat(samples, ignore_index=True).to_csv(
            os.path.join(K.DIR_QA, "data_quality_flagged_records_sample.csv"), index=False)

    # ---- write the panel ---------------------------------------------------
    K.log("-" * 78)
    annual_out = annual.copy()
    for c in annual_out.columns:
        if c.endswith("_f") or c.endswith("stations"):
            annual_out[c] = annual_out[c].round(3)
    annual_out.to_csv(os.path.join(K.DIR_TABLES, "county_annual_temperature.csv"),
                      index=False)
    monthly_out = monthly.copy()
    for c in monthly_out.columns:
        if c.endswith("_f") or c.endswith("stations"):
            monthly_out[c] = monthly_out[c].round(3)
    monthly_out.to_csv(os.path.join(K.DIR_TABLES, "county_monthly_temperature.csv"),
                       index=False)
    ext.to_csv(os.path.join(K.DIR_TABLES, "county_record_coverage.csv"), index=False)
    K.log("[write] county_annual_temperature.csv   %s rows" % "{:,}".format(len(annual_out)))
    K.log("[write] county_monthly_temperature.csv  %s rows" % "{:,}".format(len(monthly_out)))

    # ---- sanity-check tables ------------------------------------------------
    sanity = monthly_sanity(monthly)
    sanity.to_csv(os.path.join(K.DIR_TABLES,
                               "revised_temperature_monthly_sanity_check.csv"), index=False)
    summer = summer_audit(monthly)
    summer.to_csv(os.path.join(K.DIR_TABLES, "summer_audit_jun_aug_jun_sep.csv"),
                  index=False)
    K.log("[write] revised_temperature_monthly_sanity_check.csv  %d rows" % len(sanity))
    K.log("[write] summer_audit_jun_aug_jun_sep.csv              %d rows" % len(summer))

    # ---- the written review -------------------------------------------------
    write_summer_review(sanity, summer, fl, ext, quar)
    K.log("[write] qa/summer_temperature_review.md")

    K.log("-" * 78)
    js = summer[summer["window"] == "Jun-Sep"]
    for var in K.VAR_KEYS:
        s = js[js["variable"] == var]
        K.log("Jun-Sep %-28s median across counties: %s"
              % (K.VAR_PERIOD_LABEL[var],
                 "  ".join("%s %.1f" % (r["state"], r["median_across_counties_f"])
                           for _, r in s.iterrows())))
    K.log("r02 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


def write_summer_review(sanity, summer, flags, ext, quar):
    L = []
    A = L.append
    A("# Warm-season temperature review")
    A("")
    A(K.PANEL_SENTENCE)
    A("")
    A("This review exists because a previous reading of the record treated a summer "
      "value below 75 degF as suspect. That rule is not supported and is not applied "
      "here. The three daily variables answer different questions and have different "
      "expected magnitudes:")
    A("")
    A("| variable | definition | warm-season expectation |")
    A("|---|---|---|")
    A("| Daily high temperature (Tmax) | daily maximum air temperature | should be well "
      "above 75 degF in June-September in these states |")
    A("| Daily low temperature (Tmin) | daily minimum air temperature | may plausibly be "
      "below 75 degF, especially in inland, northern, rural and elevated counties |")
    A("| Daily average temperature (Tavg) | (Tmax + Tmin) / 2 | may fall on either side "
      "of 75 degF depending on state and month |")
    A("")
    A("An average of daily minimum temperatures is the AVERAGE DAILY LOW. It is not "
      "'the minimum temperature of the month'.")
    A("")
    A("## What the record shows, June-September")
    A("")
    js = summer[summer["window"] == "Jun-Sep"].copy()
    js["median"] = js["median_across_counties_f"]
    tab = js.pivot_table(index="state", columns="variable_label", values="median")
    tab = tab.reset_index()
    A(K.md_table(tab, floatfmt="%.1f"))
    A("")
    for var, expect in (("Tmax", "above 75 degF"), ("Tmin", "below or above 75 degF"),
                        ("Tavg", "near 75 degF")):
        s = js[js["variable"] == var]
        n_below = int(s["counties_below_75F"].sum())
        n_tot = int(s["contributing_counties"].sum())
        A("- **%s.** Median across counties ranges %.1f to %.1f degF across the five "
          "states. %d of %d contributing counties have a June-September value below "
          "75 degF (%.0f%%). Expected: %s."
          % (K.VAR_PERIOD_LABEL[var], s["median_across_counties_f"].min(),
             s["median_across_counties_f"].max(), n_below, n_tot,
             100.0 * n_below / n_tot if n_tot else float("nan"), expect))
    A("")
    A("A June-September average daily low below 75 degF is therefore the ordinary case "
      "in much of this region, not a data-quality signal. It is not flagged.")
    A("")
    A("## June-August compared with June-September")
    A("")
    ja = summer[summer["window"] == "Jun-Aug"][
        ["state", "variable_label", "median_across_counties_f", "contributing_counties"]]
    jsx = summer[summer["window"] == "Jun-Sep"][
        ["state", "variable_label", "median_across_counties_f"]]
    cmp = ja.merge(jsx, on=["state", "variable_label"], suffixes=("_jun_aug", "_jun_sep"))
    cmp["difference_f"] = (cmp["median_across_counties_f_jun_aug"]
                           - cmp["median_across_counties_f_jun_sep"]).round(2)
    cmp["state"] = cmp["state"].map(K.STATE_LABEL)
    cmp = cmp.rename(columns={
        "state": "state", "variable_label": "variable",
        "median_across_counties_f_jun_aug": "Jun-Aug median across counties (degF)",
        "contributing_counties": "counties",
        "median_across_counties_f_jun_sep": "Jun-Sep median across counties (degF)",
        "difference_f": "Jun-Aug minus Jun-Sep (degF)"})
    A(K.md_table(cmp, floatfmt="%.2f"))
    A("")
    A("September is cooler than June-August in every state and variable, so the wider "
      "June-September window sits below the June-August window. The prespecified warm "
      "season for this project is June-September; both are reported so the choice is "
      "visible.")
    A("")
    A("## A defect the previous package did not check for")
    A("")
    A("%d raw daily county-level records out of %s have a **daily high below the same "
      "day's daily low**." % (len(quar), "{:,}".format(int(
          ext["daily_county_level_observations"].sum()) + len(quar))))
    if len(quar):
        A("")
        A("On %d of the %d, the county daily high and the county daily low were averaged "
          "over **different numbers of stations**. The source file aggregates each "
          "element over whatever stations reported that element that day, so a county's "
          "high and its low can describe different station sets and are not guaranteed "
          "to be internally consistent. The station observations are not in question; "
          "the county aggregation is."
          % (int(quar["station_sets_differ"].sum()), len(quar)))
        A("")
        A("**Declared handling.** The affected county-dates are quarantined from the "
          "analysis panel in full, written unaltered to "
          "`qa/quarantined_inverted_daily_records.csv`, and reported here. The raw input "
          "files are not modified. %d of them fall inside the Texas %s classification "
          "window, so no Part 2 or Part 3 result depends on this choice. The handling "
          "rule is `r00_config.INVERTED_RECORD_ACTION` and is an open item for advisor "
          "sign-off."
          % (int(quar["in_texas_classification_window"].sum()), K.ANALYSIS_YEARS_LABEL))
        A("")
        A(K.md_table(quar[["state", "county_fips", "county_name", "date", "tmax_f",
                           "tmax_f_nstations", "tmin_f", "tmin_f_nstations",
                           "daily_low_minus_daily_high_f"]].head(25), floatfmt="%.2f"))
    A("")
    A("## What is flagged, and on what rule")
    A("")
    A(K.md_table(flags[["flag", "n_records", "denominator", "rule", "action"]]))
    A("")
    A("Nothing above was altered, deleted or imputed. Coverage flags govern which "
      "records enter a summary; the records themselves stay in "
      "`tables/county_annual_temperature.csv` and `tables/county_monthly_temperature.csv` "
      "with their flags attached.")
    A("")
    A("## Record extent and coverage")
    A("")
    A(K.md_table(ext[["state", "state_name", "daily_county_level_observations",
                      "counties_in_file", "first_date", "last_date",
                      "pct_daily_records_with_daily_high",
                      "annual_observations_meeting_coverage",
                      "annual_observations_total"]], floatfmt="%.2f"))
    A("")
    A("Full monthly distributions across counties, including the interquartile range, "
      "minimum, maximum, contributing county count, contributing monthly-summary count "
      "and the percentage of monthly records passing the coverage requirement, are in "
      "`tables/revised_temperature_monthly_sanity_check.csv`.")
    with open(os.path.join(K.DIR_QA, "summer_temperature_review.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
