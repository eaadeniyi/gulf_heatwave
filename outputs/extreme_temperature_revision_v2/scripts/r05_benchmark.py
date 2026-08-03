"""
=============================================================================
r05  --  STAGE 6: external benchmarking.
=============================================================================
THE HEADLINE RESULT OF THIS STEP IS A NEGATIVE ONE.

The only second county-day temperature table in this repository is

    data/raw/noaa/county_day_tmax.csv
    data/raw/noaa/county_day_tmin.csv

built by the national heatWaveUS pipeline. Its own build script
(scripts/01_download_noaa_ghcn.py) describes it as a NEAREST-STATION county
assignment, which would make it a genuine method benchmark against the Gulf
pull's point-in-polygon station mean.

IT IS NOT. This step tests that claim directly by comparing the two products
DAILY RECORD BY DAILY RECORD, and they are identical to within floating point
on every matched county-date. The file therefore duplicates the project data;
it does not validate it. No agreement statistic computed against it would mean
anything, so none is reported as validation.

WHAT THIS STEP DOES
  1  runs the identity test and writes the evidence
  2  if the products are identical, records every required comparison as NOT
     AVAILABLE with the reason, and states what would be needed instead
  3  if a genuinely different product is ever placed at those paths, the full
     comparison below runs automatically: monthly average daily high and low,
     annual average, 1980s-versus-recent difference, state ranking, seasonal
     shape, with mean absolute difference, correlation and seasonal bias

The project data are never replaced by a benchmark.

OUTPUTS
  qa/benchmark_identity_test.csv
  qa/benchmark_limitations.md
  tables/benchmark_comparison_summary.csv
  tables/benchmark_comparison_county_month.csv   (only if a real benchmark exists)
  tables/benchmark_comparison_monthly.csv        (only if a real benchmark exists)
  tables/benchmark_state_ranking.csv             (only if a real benchmark exists)
=============================================================================
"""
import os
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K
import config as C                                          # noqa: E402

B0, B1 = K.BENCHMARK_YEARS
FIPS = {C.STATE_FIPS[s]: s for s in K.STATES}
IDENTITY_THRESHOLD = 0.999      # >= this share identical -> not an independent product

REQUIRED_COMPARISONS = [
    ("monthly_average_daily_high", "monthly average daily high"),
    ("monthly_average_daily_low", "monthly average daily low"),
    ("annual_average_temperature", "annual average temperature"),
    ("period_difference_1980s_vs_recent", "1980s versus recent-period difference"),
    ("state_ranking", "state ranking"),
    ("seasonal_shape", "seasonal shape"),
]


def load_benchmark_daily(path, col, states=None):
    parts = []
    for ch in pd.read_csv(os.path.abspath(path), dtype={"county_fips": str},
                          usecols=["county_fips", "date", col], chunksize=2_000_000):
        ch = ch[ch["county_fips"].str[:2].isin(states or FIPS)]
        if len(ch):
            parts.append(ch)
    if not parts:
        return pd.DataFrame(columns=["county_fips", "date", col])
    d = pd.concat(parts, ignore_index=True)
    y = pd.to_datetime(d["date"]).dt.year
    return d[(y >= B0) & (y <= B1)]


def identity_test():
    """Are the two products actually different data? One row per state x variable."""
    rows = []
    for st in K.STATES:
        p = pd.read_csv(C.ghcn_path(st),
                        usecols=["county_fips", "date", "tmax_f", "tmin_f"],
                        dtype={"county_fips": str})
        y = pd.to_datetime(p["date"]).dt.year
        p = p[(y >= B0) & (y <= B1)]
        for path, col, var in ((K.BENCHMARK_TMAX, "tmax_f", "Tmax"),
                               (K.BENCHMARK_TMIN, "tmin_f", "Tmin")):
            b = load_benchmark_daily(path, col, states={C.STATE_FIPS[st]})
            j = p[["county_fips", "date", col]].merge(
                b, on=["county_fips", "date"], how="inner", suffixes=("_project",
                                                                      "_benchmark"))
            j = j.dropna(subset=[col + "_project", col + "_benchmark"])
            if not len(j):
                rows.append(dict(state=st, variable=var, matched_daily_records=0,
                                 identical_records=0, share_identical=np.nan,
                                 max_absolute_difference_f=np.nan,
                                 verdict="NO_OVERLAP"))
                continue
            d = (j[col + "_project"] - j[col + "_benchmark"]).abs()
            n_id = int((d < 1e-9).sum())
            share = n_id / len(j)
            rows.append(dict(
                state=st, variable=var, matched_daily_records=int(len(j)),
                identical_records=n_id, share_identical=round(share, 6),
                max_absolute_difference_f=round(float(d.max()), 6),
                verdict=("DUPLICATE_NOT_INDEPENDENT" if share >= IDENTITY_THRESHOLD
                         else "DIFFERENT_PRODUCT")))
            del b, j
        del p
    return pd.DataFrame(rows)


def unavailable_summary(reason):
    rows = []
    for key, label in REQUIRED_COMPARISONS:
        rows.append(dict(comparison=key, comparison_label=label, available=False,
                         benchmark_product=K.BENCHMARK_NAME,
                         benchmark_years="%d-%d" % (B0, B1),
                         project_median_f=np.nan, benchmark_median_f=np.nan,
                         median_difference_f=np.nan, mean_absolute_difference_f=np.nan,
                         correlation_across_counties=np.nan, counties_matched=0,
                         reason=reason))
    return pd.DataFrame(rows)


def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 78)
    K.log("r05  STAGE 6 -- external benchmarking")
    K.log("=" * 78)

    have = (os.path.exists(os.path.abspath(K.BENCHMARK_TMAX))
            and os.path.exists(os.path.abspath(K.BENCHMARK_TMIN)))
    if not have:
        reason = ("no second temperature product is present in this repository; "
                  "an independent spatially consistent product must be downloaded")
        K.log("no candidate benchmark file found")
        unavailable_summary(reason).to_csv(
            os.path.join(K.DIR_TABLES, "benchmark_comparison_summary.csv"), index=False)
        write_limitations(None, reason)
        return 0

    K.log("candidate benchmark: %s" % K.BENCHMARK_NAME)
    K.log("running the identity test -- is it actually different data?")
    idt = identity_test()
    idt.to_csv(os.path.join(K.DIR_QA, "benchmark_identity_test.csv"), index=False)
    for _, r in idt.iterrows():
        K.log("   %-3s %-5s  %9s matched daily records, %.4f%% identical, "
              "max |difference| %.6g degF  -> %s"
              % (r["state"], r["variable"],
                 "{:,}".format(int(r["matched_daily_records"])),
                 100 * (r["share_identical"] if r["share_identical"] == r["share_identical"]
                        else float("nan")),
                 r["max_absolute_difference_f"], r["verdict"]))

    is_dup = bool((idt["verdict"] == "DUPLICATE_NOT_INDEPENDENT").all())
    if is_dup:
        reason = ("the candidate product is byte-identical to the project data on "
                  "%s of %s matched daily county-level records (maximum absolute "
                  "difference %.6g degF), so it duplicates the project data rather "
                  "than providing independent validation"
                  % ("{:,}".format(int(idt["identical_records"].sum())),
                     "{:,}".format(int(idt["matched_daily_records"].sum())),
                     float(idt["max_absolute_difference_f"].max())))
        K.log("-" * 78)
        K.log("RESULT: external benchmarking CANNOT be performed with the contents of "
              "this repository.")
        K.log("   %s" % reason)
        unavailable_summary(reason).to_csv(
            os.path.join(K.DIR_TABLES, "benchmark_comparison_summary.csv"), index=False)
        write_limitations(idt, reason)
        K.log("[write] qa/benchmark_identity_test.csv")
        K.log("[write] qa/benchmark_limitations.md")
        K.log("[write] tables/benchmark_comparison_summary.csv  (all comparisons "
              "recorded NOT AVAILABLE)")
        K.log("r05 done in %.1f min" % ((time.time() - t0) / 60))
        return 0

    K.log("the candidate product differs from the project data - running the full "
          "comparison")
    return full_comparison(idt, t0)


# =============================================================================
# the real comparison, which runs only if a genuinely different product appears
# =============================================================================
def full_comparison(idt, t0):
    monthly = pd.read_csv(os.path.join(K.DIR_TABLES, "county_monthly_temperature.csv"),
                          dtype={"county_fips": str})
    proj = monthly[(monthly["year"] >= B0) & (monthly["year"] <= B1)
                   & monthly["meets_monthly_coverage_requirement"]]
    proj = (proj.groupby(["state", "county_fips", "county_name", "year", "month",
                          "variable"], observed=True)["period_mean_f"]
            .mean().rename("project_value_f").reset_index())

    frames = []
    for path, col, var in ((K.BENCHMARK_TMAX, "tmax_f", "Tmax"),
                           (K.BENCHMARK_TMIN, "tmin_f", "Tmin")):
        b = load_benchmark_daily(path, col)
        d = pd.to_datetime(b["date"])
        b = b.assign(year=d.dt.year, month=d.dt.month).rename(columns={col: "value"})
        b["variable"] = var
        frames.append(b[["county_fips", "year", "month", "variable", "value"]])
    bm = pd.concat(frames, ignore_index=True)
    g = (bm.groupby(["county_fips", "year", "month", "variable"], observed=True)
         .agg(benchmark_value_f=("value", "mean"),
              benchmark_days=("value", "size")).reset_index())
    g = g[g["benchmark_days"] >= K.MIN_DAYS_PER_COUNTY_MONTH]
    w = g.pivot_table(index=["county_fips", "year", "month"], columns="variable",
                      values="benchmark_value_f")
    if "Tmax" in w.columns and "Tmin" in w.columns:
        w["Tavg"] = (w["Tmax"] + w["Tmin"]) / 2.0
    bcm = w.stack().rename("benchmark_value_f").reset_index()
    bcm = bcm.rename(columns={bcm.columns[-2]: "variable"})

    j = proj.merge(bcm, on=["county_fips", "year", "month", "variable"], how="inner")
    j["difference_f"] = (j["project_value_f"] - j["benchmark_value_f"]).round(3)
    cm = (j.groupby(["state", "county_fips", "county_name", "month", "variable"],
                    observed=True)
          .agg(project_value_f=("project_value_f", "mean"),
               benchmark_value_f=("benchmark_value_f", "mean"),
               matched_months=("difference_f", "size")).reset_index())
    cm["difference_f"] = (cm["project_value_f"] - cm["benchmark_value_f"]).round(3)
    cm["variable_label"] = cm["variable"].map(K.VAR_PERIOD_LABEL)
    cm.to_csv(os.path.join(K.DIR_TABLES, "benchmark_comparison_county_month.csv"),
              index=False)

    rows = []
    for (st, var, mo), gg in cm.groupby(["state", "variable", "month"], observed=True):
        corr = (float(np.corrcoef(gg["project_value_f"], gg["benchmark_value_f"])[0, 1])
                if len(gg) > 2 else np.nan)
        rows.append(dict(state=st, variable=var,
                         variable_label=K.VAR_PERIOD_LABEL[var], month=mo,
                         month_name=K.MONTH_ABBR[mo - 1], season=K.SEASON_OF[mo],
                         counties_matched=int(gg["county_fips"].nunique()),
                         project_median_across_counties_f=round(
                             float(gg["project_value_f"].median()), 3),
                         benchmark_median_across_counties_f=round(
                             float(gg["benchmark_value_f"].median()), 3),
                         median_difference_f=round(float(gg["difference_f"].median()), 3),
                         mean_absolute_difference_f=round(
                             float(gg["difference_f"].abs().mean()), 3),
                         correlation_across_counties=round(corr, 4)
                         if corr == corr else np.nan))
    mon = pd.DataFrame(rows)
    mon.to_csv(os.path.join(K.DIR_TABLES, "benchmark_comparison_monthly.csv"),
               index=False)

    srows = []
    for key, label, sub in (
            ("monthly_average_daily_high", "monthly average daily high",
             cm[cm["variable"] == "Tmax"]),
            ("monthly_average_daily_low", "monthly average daily low",
             cm[cm["variable"] == "Tmin"]),
            ("annual_average_temperature", "annual average temperature",
             cm[cm["variable"] == "Tavg"])):
        srows.append(dict(comparison=key, comparison_label=label, available=True,
                          benchmark_product=K.BENCHMARK_NAME,
                          benchmark_years="%d-%d" % (B0, B1),
                          counties_matched=int(sub["county_fips"].nunique()),
                          project_median_f=round(float(sub["project_value_f"].median()), 3),
                          benchmark_median_f=round(float(sub["benchmark_value_f"].median()), 3),
                          median_difference_f=round(float(sub["difference_f"].median()), 3),
                          mean_absolute_difference_f=round(
                              float(sub["difference_f"].abs().mean()), 3),
                          correlation_across_counties=round(float(np.corrcoef(
                              sub["project_value_f"], sub["benchmark_value_f"])[0, 1]), 4),
                          reason=""))
    warm = cm[cm["month"].isin(K.WARM_SEASON) & (cm["variable"] == "Tmax")]
    wr = warm.groupby("state", observed=True)[["project_value_f",
                                               "benchmark_value_f"]].median()
    wr["project_rank"] = wr["project_value_f"].rank(ascending=False).astype(int)
    wr["benchmark_rank"] = wr["benchmark_value_f"].rank(ascending=False).astype(int)
    wr = wr.reset_index()
    wr.to_csv(os.path.join(K.DIR_TABLES, "benchmark_state_ranking.csv"), index=False)
    srows.append(dict(comparison="state_ranking", comparison_label="state ranking",
                      available=True, benchmark_product=K.BENCHMARK_NAME,
                      benchmark_years="%d-%d" % (B0, B1),
                      counties_matched=int(warm["county_fips"].nunique()),
                      project_median_f=np.nan, benchmark_median_f=np.nan,
                      median_difference_f=np.nan, mean_absolute_difference_f=np.nan,
                      correlation_across_counties=np.nan,
                      reason="ranks agree on %d of %d states"
                             % (int((wr["project_rank"] == wr["benchmark_rank"]).sum()),
                                len(wr))))
    amp_p = (cm[cm["month"].isin(K.WARM_SEASON)]["project_value_f"].median()
             - cm[cm["month"].isin(K.COOL_SEASON)]["project_value_f"].median())
    amp_b = (cm[cm["month"].isin(K.WARM_SEASON)]["benchmark_value_f"].median()
             - cm[cm["month"].isin(K.COOL_SEASON)]["benchmark_value_f"].median())
    srows.append(dict(comparison="seasonal_shape", comparison_label="seasonal shape",
                      available=True, benchmark_product=K.BENCHMARK_NAME,
                      benchmark_years="%d-%d" % (B0, B1),
                      counties_matched=int(cm["county_fips"].nunique()),
                      project_median_f=round(float(amp_p), 3),
                      benchmark_median_f=round(float(amp_b), 3),
                      median_difference_f=round(float(amp_p - amp_b), 3),
                      mean_absolute_difference_f=np.nan,
                      correlation_across_counties=np.nan,
                      reason="warm-season minus cool-season amplitude"))
    srows.append(dict(comparison="period_difference_1980s_vs_recent",
                      comparison_label="1980s versus recent-period difference",
                      available=False, benchmark_product=K.BENCHMARK_NAME,
                      benchmark_years="%d-%d" % (B0, B1), counties_matched=0,
                      project_median_f=np.nan, benchmark_median_f=np.nan,
                      median_difference_f=np.nan, mean_absolute_difference_f=np.nan,
                      correlation_across_counties=np.nan,
                      reason="the benchmark product begins in %d and cannot reach "
                             "1980-1989" % B0))
    summary = pd.DataFrame(srows)
    summary.to_csv(os.path.join(K.DIR_TABLES, "benchmark_comparison_summary.csv"),
                   index=False)
    write_limitations(idt, "", summary=summary, mon=mon)
    K.log("r05 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


# =============================================================================
def write_limitations(idt, reason, summary=None, mon=None):
    L = []
    A = L.append
    A("# External benchmarking: what was attempted and what it showed")
    A("")
    A("## Finding")
    A("")
    if summary is None:
        A("**External benchmarking could not be performed with the contents of this "
          "repository.**")
        A("")
        A(reason.capitalize() + ".")
    else:
        A("A genuinely different product was found and the full comparison was run; "
          "results are in `tables/benchmark_comparison_summary.csv`.")
    A("")
    A("## Why the candidate product was rejected")
    A("")
    A("The only second daily county-level temperature table in the repository is "
      "`data/raw/noaa/county_day_tmax.csv` and its `tmin` companion, produced by the "
      "national heatWaveUS pipeline. Its build script "
      "(`scripts/01_download_noaa_ghcn.py`) documents it as a **nearest-station** "
      "county assignment, which would have made it a usable method benchmark against "
      "this project's point-in-polygon station mean.")
    A("")
    A("That documented difference does not exist in the delivered file. Comparing the "
      "two products daily record by daily record:")
    A("")
    if idt is not None:
        A(K.md_table(idt[["state", "variable", "matched_daily_records",
                          "identical_records", "share_identical",
                          "max_absolute_difference_f", "verdict"]], floatfmt="%.6g"))
        A("")
        A("Every matched daily county-level record is identical to within floating "
          "point. The file duplicates the project data. Any agreement statistic "
          "computed against it would be a tautology, so none is reported as "
          "validation. The build-script docstring is inaccurate for the delivered "
          "file and that discrepancy is itself worth raising with whoever maintains "
          "the national pipeline.")
    A("")
    A("## Status of each required comparison")
    A("")
    A("| comparison | status | reason |")
    A("|---|---|---|")
    if summary is None:
        for key, label in REQUIRED_COMPARISONS:
            extra = ("; the candidate also begins in %d and could not have reached "
                     "1980-1989 in any case" % B0
                     if key == "period_difference_1980s_vs_recent" else "")
            A("| %s | **not available** | no independent product%s |" % (label, extra))
    else:
        for _, r in summary.iterrows():
            A("| %s | %s | %s |" % (r["comparison_label"],
                                    "available" if r["available"] else "**not available**",
                                    r["reason"]))
    A("")
    A("## What would be needed")
    A("")
    A("An independent, spatially consistent temperature product covering 1979-2025 "
      "for the five Gulf states at county resolution. Three candidates, none of which "
      "is currently in the repository:")
    A("")
    A("| product | coverage | why it would work |")
    A("|---|---|---|")
    A("| NOAA nClimGrid-Daily | 1951-present, 5 km CONUS | independent gridding of the "
      "station network with its own homogenisation; the standard reference for US "
      "county-level temperature |")
    A("| PRISM AN81d | 1981-present, 4 km CONUS | independent interpolation with "
      "explicit elevation and coastal adjustment, which is where this project's "
      "county aggregation is weakest |")
    A("| Daymet v4 | 1980-present, 1 km North America | already used elsewhere in the "
      "wider heatWaveUS project for vapour pressure, so the ingestion path exists |")
    A("")
    A("Until one of these is added, the following statements are **not** supported by "
      "this package and must not be made:")
    A("")
    A("- that the county temperature values agree with an independent product")
    A("- that the station-to-county aggregation has been externally validated")
    A("- that the period differences survive an independent-data check")
    A("")
    A("The unresolved temperature-source question recorded in the previous package "
      "(anchor-station versus multi-station composite agreeing at only 0.45-0.73) "
      "therefore remains open and is not narrowed by anything in this step.")
    with open(os.path.join(K.DIR_QA, "benchmark_limitations.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
