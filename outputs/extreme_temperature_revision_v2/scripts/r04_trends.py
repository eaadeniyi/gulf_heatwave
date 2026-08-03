"""
=============================================================================
r04  --  STAGE 5: trend sensitivity.
=============================================================================
A difference between two period summaries is not a trend. This step estimates
descriptive time-trend models so that the period differences in r03 and the
slopes reported here are never confused with one another.

For every state and temperature variable:

  1  a descriptive ANNUAL series: the median across counties of the annual
     county-level observation, one point per year
  2  the Sen (Theil-Sen) slope, the primary descriptive slope
  3  an ordinary least-squares slope, as a sensitivity case
  4  a bootstrap interval that resamples COUNTIES, so the interval reflects
     uncertainty in which counties are in the series
  5  a sensitivity excluding the 2020-2025 recent period
  6  a sensitivity on the observed-only consistent-county sample (Sample A),
     where the county set does not change from year to year
  7  a sensitivity on a stable-station subset: Sample A counties whose number
     of contributing stations never changes by more than a factor of 1.5
     between consecutive qualifying years and is at least two throughout

REQUIRED WORDING, applied to every slope reported here:

  "The annual state summary increased by X degF per decade under this
   descriptive model."
  "This result may reflect climate change, station-network composition, data
   coverage, or remaining inhomogeneity and does not isolate causation."

No causal language is used anywhere in this step or in anything built from it.

OUTPUTS
  tables/state_annual_series.csv
  tables/trend_sensitivity.csv
=============================================================================
"""
import os
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K

CAVEAT = ("This result may reflect climate change, station-network composition, "
          "data coverage, or remaining inhomogeneity and does not isolate causation.")


def stable_station_counties(annual, members):
    """Sample A counties whose station composition is stable over the record."""
    a = annual[annual["meets_annual_coverage_requirement"]].sort_values(
        ["state", "county_fips", "variable", "year"]).copy()
    mem = members[members["sample"] == K.SAMPLE_A_NAME][["state", "variable",
                                                         "county_fips"]]
    a = a.merge(mem, on=["state", "variable", "county_fips"], how="inner")
    g = a.groupby(["state", "variable", "county_fips"], observed=True)
    a["prev"] = g["mean_contributing_stations"].shift()
    a["ratio"] = a["mean_contributing_stations"] / a["prev"]
    ok = (a.groupby(["state", "variable", "county_fips"], observed=True)
          .agg(min_stations=("mean_contributing_stations", "min"),
               max_ratio=("ratio", "max"), min_ratio=("ratio", "min")).reset_index())
    keep = ok[(ok["min_stations"] >= 2.0) & (ok["max_ratio"] <= 1.5)
              & (ok["min_ratio"] >= 1 / 1.5)][["state", "variable", "county_fips"]]
    return keep.assign(sample="stable_station")


def annual_series(annual, county_filter=None, label="all_reporting_counties"):
    """Median across counties of the annual county-level observation, by year."""
    a = annual[annual["meets_annual_coverage_requirement"]]
    if county_filter is not None:
        a = a.merge(county_filter[["state", "variable", "county_fips"]],
                    on=["state", "variable", "county_fips"], how="inner")
    s = (a.groupby(["state", "variable", "year"], observed=True)
         .agg(contributing_counties=("county_fips", "nunique"),
              median_across_counties_f=("period_mean_f", "median"),
              p25_across_counties_f=("period_mean_f", lambda x: x.quantile(0.25)),
              p75_across_counties_f=("period_mean_f", lambda x: x.quantile(0.75)))
         .reset_index())
    s["series"] = label
    return s, a


def fit(years, values):
    """Sen slope with its distribution-free interval, and an OLS slope."""
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if x.size < 5:
        return {}
    sen, icept, lo, hi = stats.theilslopes(y, x, alpha=0.95)
    ols = stats.linregress(x, y)
    tau, p_tau = stats.kendalltau(x, y)
    return dict(n_years=int(x.size), first_year=int(x.min()), last_year=int(x.max()),
                sen_slope_f_per_decade=round(10 * sen, 4),
                sen_ci_low_f_per_decade=round(10 * lo, 4),
                sen_ci_high_f_per_decade=round(10 * hi, 4),
                ols_slope_f_per_decade=round(10 * ols.slope, 4),
                ols_stderr_f_per_decade=round(10 * ols.stderr, 4),
                ols_p_value=float(ols.pvalue), ols_r_squared=round(ols.rvalue ** 2, 4),
                kendall_tau=round(float(tau), 4), kendall_p_value=float(p_tau))


def county_bootstrap_slope(a, state, var, years_keep=None):
    """Resample counties, rebuild the annual median series, refit the Sen slope."""
    s = a[(a["state"] == state) & (a["variable"] == var)]
    if years_keep is not None:
        s = s[s["year"].isin(years_keep)]
    if not len(s):
        return np.nan, np.nan
    wide = s.pivot_table(index="county_fips", columns="year", values="period_mean_f")
    M = wide.to_numpy(dtype=float)
    yrs = np.asarray(wide.columns, dtype=float)
    n = M.shape[0]
    if n < 5:
        return np.nan, np.nan
    rng = np.random.default_rng(K.BOOTSTRAP_SEED)
    out = np.full(K.BOOTSTRAP_N, np.nan)
    for b in range(K.BOOTSTRAP_N):
        idx = rng.integers(0, n, size=n)
        med = np.nanmedian(M[idx, :], axis=0)
        ok = np.isfinite(med)
        if ok.sum() >= 5:
            out[b] = stats.theilslopes(med[ok], yrs[ok])[0]
    lo, hi = np.nanpercentile(out, K.BOOTSTRAP_CI)
    return round(10 * float(lo), 4), round(10 * float(hi), 4)


def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 78)
    K.log("r04  STAGE 5 -- trend sensitivity (descriptive; no causal claim)")
    K.log("=" * 78)

    annual = pd.read_csv(os.path.join(K.DIR_TABLES, "county_annual_temperature.csv"),
                         dtype={"county_fips": str})
    members = pd.read_csv(os.path.join(K.DIR_TABLES, "sample_membership_counties.csv"),
                          dtype={"county_fips": str})
    stable = stable_station_counties(annual, members)
    K.log("stable-station subset: %s"
          % ", ".join("%s %d" % (st, int(((stable["state"] == st)
                                          & (stable["variable"] == "Tmax")).sum()))
                      for st in K.STATES))

    specs = [
        ("all_reporting_counties", None, None,
         "every county passing the coverage requirement that year; the county set "
         "changes between years"),
        ("consistent_county_sample_A",
         members[members["sample"] == K.SAMPLE_A_NAME], None,
         "Sample A; the county set is fixed across the whole record"),
        ("consistent_county_excluding_recent_period",
         members[members["sample"] == K.SAMPLE_A_NAME],
         list(range(K.YEARS[0], K.PERIODS[-1][0])),
         "Sample A, 2020-2025 dropped, to test whether the recent period drives the "
         "slope"),
        ("stable_station_subset", stable, None,
         "Sample A counties whose contributing-station count is at least two "
         "throughout and never changes by more than a factor of 1.5 between "
         "consecutive qualifying years"),
    ]

    series_rows, trend_rows = [], []
    for label, filt, years_keep, note in specs:
        s, a = annual_series(annual, filt, label)
        if years_keep is not None:
            s = s[s["year"].isin(years_keep)]
        series_rows.append(s)
        for st in K.STATES:
            for var in K.VAR_KEYS:
                ss = s[(s["state"] == st) & (s["variable"] == var)].sort_values("year")
                f = fit(ss["year"], ss["median_across_counties_f"])
                if not f:
                    continue
                blo, bhi = county_bootstrap_slope(a, st, var, years_keep)
                trend_rows.append(dict(
                    series=label, series_note=note, state=st,
                    state_name=K.STATE_LABEL[st], variable=var,
                    variable_label=K.VAR_PERIOD_LABEL[var],
                    counties_median=int(ss["contributing_counties"].median()),
                    counties_min=int(ss["contributing_counties"].min()),
                    counties_max=int(ss["contributing_counties"].max()),
                    county_bootstrap_ci_low_f_per_decade=blo,
                    county_bootstrap_ci_high_f_per_decade=bhi,
                    statement=("The annual state summary increased by %.2f degF per "
                               "decade under this descriptive model."
                               % f["sen_slope_f_per_decade"])
                    if f["sen_slope_f_per_decade"] >= 0 else
                    ("The annual state summary decreased by %.2f degF per decade "
                     "under this descriptive model."
                     % abs(f["sen_slope_f_per_decade"])),
                    caveat=CAVEAT, model="Theil-Sen (primary), OLS (sensitivity)",
                    unit_of_analysis="annual median across counties",
                    **f))

    ser = pd.concat(series_rows, ignore_index=True)
    for c in ser.columns:
        if c.endswith("_f"):
            ser[c] = ser[c].round(3)
    ser.to_csv(os.path.join(K.DIR_TABLES, "state_annual_series.csv"), index=False)
    tr = pd.DataFrame(trend_rows)
    tr.to_csv(os.path.join(K.DIR_TABLES, "trend_sensitivity.csv"), index=False)
    K.log("[write] state_annual_series.csv   %d rows" % len(ser))
    K.log("[write] trend_sensitivity.csv     %d rows" % len(tr))

    # -- external benchmark availability for a trend --------------------------
    K.log("-" * 78)
    K.log("sensitivity 7 (benchmark product): NOT AVAILABLE. The only second "
          "temperature product in this repository covers %d-%d, which does not reach "
          "the 1979-2014 part of the record, and r05 shows it to be byte-identical to "
          "the project data in any case. No slope here has been checked against an "
          "independent product." % K.BENCHMARK_YEARS)

    K.log("-" * 78)
    K.log("SEN SLOPE, degF per decade, daily high temperature (95%% Sen interval)")
    K.log("   %-3s %-30s %-30s" % ("st", "all reporting counties",
                                   "consistent-county (Sample A)"))
    for st in K.STATES:
        cells = []
        for lab in ("all_reporting_counties", "consistent_county_sample_A"):
            r = tr[(tr["series"] == lab) & (tr["state"] == st)
                   & (tr["variable"] == "Tmax")]
            cells.append("%+.2f [%+.2f, %+.2f]"
                         % (r["sen_slope_f_per_decade"].iloc[0],
                            r["sen_ci_low_f_per_decade"].iloc[0],
                            r["sen_ci_high_f_per_decade"].iloc[0]) if len(r) else "n/a")
        K.log("   %-3s %-30s %-30s" % (st, cells[0], cells[1]))
    K.log("")
    K.log("   " + CAVEAT)
    K.log("r04 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
