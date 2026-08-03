"""
=============================================================================
r03  --  STAGES 3 and 4: correct the period-comparison aggregation.
=============================================================================
THE DEFECT BEING CORRECTED

The current package computes a state's value for a period as the MEDIAN OVER
ALL POOLED ANNUAL COUNTY-LEVEL OBSERVATIONS in that period. A county with ten
qualifying years therefore contributes ten values and a county with two
contributes two, so the state estimate is weighted by reporting frequency. Its
own docstring describes the quantity as a median across counties, which it is
not.

It also calls its county set a BALANCED PANEL. The rule it enforces is "the
county has at least ONE qualifying year in each of the five periods", which
does not balance anything: the number of annual observations a county
contributes still varies by county and by period.

THE CORRECTION

    daily county-level observations
      -> annual county-level observation        (r02)
      -> ONE value per county per period        (mean of its annual values)
      -> state summary                          (median ACROSS counties)

with an interquartile range across counties and a bootstrap interval that
resamples COUNTIES, never county-years.

TWO PRESPECIFIED SAMPLES, both reported, neither preferred by default:

  SAMPLE A  consistent-county   at least the configured minimum number of
                                qualifying years in EVERY period
                                (8 of 10 in the full decades, 5 of 6 in
                                2020-2025; see config/resolved_configuration.csv)
  SAMPLE B  strict balanced     EXACTLY the same number of annual observations
                                in every period (6, the length of the shortest
                                period), selected by a documented deterministic
                                rule with no randomness

OUTPUTS
  tables/county_period_temperature.csv
  tables/state_period_temperature_equal_county.csv
  tables/state_month_period_temperature_equal_county.csv
  tables/sample_membership_counties.csv
  tables/period_comparison_current_vs_revised.csv
  tables/state_period_temperature_current_vs_revised.csv   (required-name alias)
  qa/test_C_period_weighting.csv
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

TESTC = []


# =============================================================================
# 1. sample construction
# =============================================================================
def qualifying_annual(annual):
    """Annual county-level observations that meet the coverage requirement and
    fall inside one of the comparison periods."""
    a = annual[annual["meets_annual_coverage_requirement"] & annual["period"].notna()]
    return a[["state", "county_fips", "county_name", "variable", "year", "period",
              "period_mean_f", "valid_daily_observation_count",
              "mean_contributing_stations"]].copy()


def sample_a(q):
    """Counties with at least the configured minimum qualifying years in EVERY
    period. Returns (membership, selected_rows)."""
    need = {K.PERIOD_LABEL[k]: v for k, v in K.SAMPLE_A_MIN_YEARS.items()}
    n = (q.groupby(["state", "variable", "county_fips", "period"], observed=True)
         .size().rename("n_years").reset_index())
    n["required"] = n["period"].map(need)
    n["meets"] = n["n_years"] >= n["required"]
    ok = (n.groupby(["state", "variable", "county_fips"], observed=True)["meets"]
          .agg(["sum", "size"]).reset_index())
    keep = ok[(ok["sum"] == len(K.PERIODS)) & (ok["size"] == len(K.PERIODS))][
        ["state", "variable", "county_fips"]]
    keep = keep.assign(sample=K.SAMPLE_A_NAME)
    sel = q.merge(keep[["state", "variable", "county_fips"]],
                  on=["state", "variable", "county_fips"], how="inner")
    sel = sel.assign(sample=K.SAMPLE_A_NAME)
    return keep, sel, n


def sample_b(q):
    """Counties contributing EXACTLY K annual observations to every period.

    K = SAMPLE_B_YEARS_PER_PERIOD. Within each period the K qualifying years
    closest to the period midpoint are taken; ties break toward the earlier
    year. The rule is deterministic and uses no randomness.
    """
    kk = K.SAMPLE_B_YEARS_PER_PERIOD
    mid = {K.PERIOD_LABEL[p]: (p[0] + p[1]) / 2.0 for p in K.PERIODS}
    n = (q.groupby(["state", "variable", "county_fips", "period"], observed=True)
         .size().rename("n_years").reset_index())
    ok = n[n["n_years"] >= kk]
    cnt = (ok.groupby(["state", "variable", "county_fips"], observed=True)
           .size().rename("periods_ok").reset_index())
    keep = cnt[cnt["periods_ok"] == len(K.PERIODS)][["state", "variable", "county_fips"]]
    keep = keep.assign(sample=K.SAMPLE_B_NAME)
    sub = q.merge(keep[["state", "variable", "county_fips"]],
                  on=["state", "variable", "county_fips"], how="inner").copy()
    sub["distance_to_period_midpoint"] = (
        sub["year"] - sub["period"].map(mid)).abs()
    sub = sub.sort_values(["state", "variable", "county_fips", "period",
                           "distance_to_period_midpoint", "year"])
    sel = sub.groupby(["state", "variable", "county_fips", "period"],
                      observed=True).head(kk).copy()
    sel = sel.assign(sample=K.SAMPLE_B_NAME)
    return keep, sel


def county_period_values(sel):
    """One value per county per period: the mean of its selected annual values."""
    agg = "mean" if K.COUNTY_PERIOD_STAT == "mean" else "median"
    g = (sel.groupby(["sample", "state", "variable", "county_fips", "county_name",
                      "period"], observed=True)
         .agg(county_period_value_f=("period_mean_f", agg),
              annual_observations_used=("period_mean_f", "size"),
              first_year_used=("year", "min"), last_year_used=("year", "max"),
              mean_contributing_stations=("mean_contributing_stations", "mean"))
         .reset_index())
    g["county_period_statistic"] = K.COUNTY_PERIOD_STAT
    return g


# =============================================================================
# 2. equal-county state summaries with a county bootstrap
# =============================================================================
def bootstrap_state(cp):
    """State x variable x period medians, IQR and bootstrap intervals.

    Counties are resampled with replacement; the SAME resampled county set is
    used for every period inside one replicate, so the interval on a period
    DIFFERENCE is a paired interval.
    """
    rows = []
    rng = np.random.default_rng(K.BOOTSTRAP_SEED)
    lo_q, hi_q = K.BOOTSTRAP_CI
    for (sample, state, var), g in cp.groupby(["sample", "state", "variable"],
                                              observed=True):
        wide = g.pivot_table(index="county_fips", columns="period",
                             values="county_period_value_f")
        wide = wide.reindex(columns=K.PERIOD_ORDER)
        wide = wide.dropna(how="any")            # complete by construction
        M = wide.to_numpy(dtype=float)
        n_cty = M.shape[0]
        if n_cty == 0:
            continue
        idx = rng.integers(0, n_cty, size=(K.BOOTSTRAP_N, n_cty))
        boot = np.median(M[idx, :], axis=1)      # (BOOTSTRAP_N, n_periods)
        med = np.median(M, axis=0)
        base_i = K.PERIOD_ORDER.index(K.BASE_PERIOD)
        diff = med - med[base_i]
        boot_diff = boot - boot[:, [base_i]]
        paired = M - M[:, [base_i]]
        med_paired = np.median(paired, axis=0)
        boot_paired = np.median(paired[idx, :], axis=1)
        for j, per in enumerate(K.PERIOD_ORDER):
            rows.append(dict(
                sample=sample, state=state, state_name=K.STATE_LABEL[state],
                variable=var, variable_label=K.VAR_PERIOD_LABEL[var],
                period=per, period_note=K.PERIOD_NOTE.get(
                    [p for p in K.PERIODS if K.PERIOD_LABEL[p] == per][0], ""),
                contributing_counties=int(n_cty),
                annual_observations_per_county_per_period=int(
                    g.loc[g["period"] == per, "annual_observations_used"].median()),
                median_across_counties_f=round(float(med[j]), 3),
                p25_across_counties_f=round(float(np.percentile(M[:, j], 25)), 3),
                p75_across_counties_f=round(float(np.percentile(M[:, j], 75)), 3),
                iqr_across_counties_f=round(float(np.percentile(M[:, j], 75)
                                                  - np.percentile(M[:, j], 25)), 3),
                min_across_counties_f=round(float(M[:, j].min()), 3),
                max_across_counties_f=round(float(M[:, j].max()), 3),
                median_ci_low_f=round(float(np.percentile(boot[:, j], lo_q)), 3),
                median_ci_high_f=round(float(np.percentile(boot[:, j], hi_q)), 3),
                difference_of_medians_vs_base_f=round(float(diff[j]), 3),
                difference_ci_low_f=round(float(np.percentile(boot_diff[:, j], lo_q)), 3),
                difference_ci_high_f=round(float(np.percentile(boot_diff[:, j], hi_q)), 3),
                median_paired_county_difference_f=round(float(med_paired[j]), 3),
                paired_difference_ci_low_f=round(float(np.percentile(boot_paired[:, j], lo_q)), 3),
                paired_difference_ci_high_f=round(float(np.percentile(boot_paired[:, j], hi_q)), 3),
                base_period=K.BASE_PERIOD,
                bootstrap_resamples=K.BOOTSTRAP_N,
                bootstrap_unit=K.BOOTSTRAP_UNIT,
                aggregation=("daily -> annual county value -> county period %s -> "
                             "state median across counties" % K.COUNTY_PERIOD_STAT),
                interpretation=("a difference between two period summaries; NOT a "
                                "trend estimate and NOT a causal statement")))
    return pd.DataFrame(rows)


def monthly_equal_county(monthly, members):
    """The same equal-county aggregation, by calendar month.

    A county enters a (state, variable, month, period) cell only if it is in the
    sample AND has at least one qualifying monthly county-level summary for that
    month in that period; the count of contributing counties is reported for
    every cell so a thin cell is visible rather than hidden.
    """
    q = monthly[monthly["meets_monthly_coverage_requirement"]
                & monthly["period"].notna()]
    out = []
    for sample in K.SAMPLES:
        mem = members[members["sample"] == sample][["state", "variable", "county_fips"]]
        s = q.merge(mem, on=["state", "variable", "county_fips"], how="inner")
        cp = (s.groupby(["state", "variable", "month", "period", "county_fips"],
                        observed=True)
              .agg(county_period_value_f=("period_mean_f", "mean"),
                   monthly_summaries_used=("period_mean_f", "size")).reset_index())
        st = (cp.groupby(["state", "variable", "month", "period"], observed=True)
              .agg(contributing_counties=("county_fips", "nunique"),
                   median_across_counties_f=("county_period_value_f", "median"),
                   p25_across_counties_f=("county_period_value_f",
                                          lambda x: x.quantile(0.25)),
                   p75_across_counties_f=("county_period_value_f",
                                          lambda x: x.quantile(0.75)),
                   monthly_summaries_used=("monthly_summaries_used", "sum")).reset_index())
        st["sample"] = sample
        out.append(st)
    m = pd.concat(out, ignore_index=True)
    # difference from the base period, on counties present in BOTH periods
    diffs = []
    for sample in K.SAMPLES:
        mem = members[members["sample"] == sample][["state", "variable", "county_fips"]]
        s = q.merge(mem, on=["state", "variable", "county_fips"], how="inner")
        cp = (s.groupby(["state", "variable", "month", "period", "county_fips"],
                        observed=True)["period_mean_f"].mean().reset_index())
        w = cp.pivot_table(index=["state", "variable", "month", "county_fips"],
                           columns="period", values="period_mean_f")
        for per in K.PERIOD_ORDER:
            if per not in w.columns or K.BASE_PERIOD not in w.columns:
                continue
            sub = w[[K.BASE_PERIOD, per]].dropna()
            # per == BASE_PERIOD gives duplicate column labels, so index by position
            d = (sub.iloc[:, 1] - sub.iloc[:, 0]).rename("d").reset_index()
            g = (d.groupby(["state", "variable", "month"], observed=True)
                 .agg(counties_in_both_periods=("county_fips", "nunique"),
                      median_paired_county_difference_f=("d", "median"),
                      p25_paired_difference_f=("d", lambda x: x.quantile(0.25)),
                      p75_paired_difference_f=("d", lambda x: x.quantile(0.75))).reset_index())
            g["period"] = per
            g["sample"] = sample
            diffs.append(g)
    dd = pd.concat(diffs, ignore_index=True)
    m = m.merge(dd, on=["sample", "state", "variable", "month", "period"], how="left")
    m["month_name"] = m["month"].map(lambda x: K.MONTH_ABBR[x - 1])
    m["season"] = m["month"].map(K.SEASON_OF)
    m["variable_label"] = m["variable"].map(K.VAR_PERIOD_LABEL)
    m["base_period"] = K.BASE_PERIOD
    for c in m.columns:
        if c.endswith("_f"):
            m[c] = m[c].round(3)
    return m.sort_values(["sample", "state", "variable", "month", "period"]).reset_index(
        drop=True)


# =============================================================================
# 3. the current method, reproduced on the same panel
# =============================================================================
def current_method(q):
    """The current package's rule, applied to the revised panel.

    'balanced panel' = at least ONE qualifying year in every period; the state
    value = median over ALL POOLED annual county-level observations.
    """
    dec = (q.groupby(["state", "variable", "county_fips"], observed=True)["period"]
           .nunique().rename("n_periods").reset_index())
    keep = dec[dec["n_periods"] == len(K.PERIODS)][["state", "variable", "county_fips"]]
    g = q.merge(keep, on=["state", "variable", "county_fips"], how="inner")
    out = (g.groupby(["state", "variable", "period"], observed=True)
           .agg(counties=("county_fips", "nunique"),
                pooled_annual_observations=("period_mean_f", "size"),
                pooled_median_f=("period_mean_f", "median")).reset_index())
    out["sample"] = "current_balanced_panel_pooled"
    return out, keep


def load_current_published():
    """The numbers the current package actually published."""
    p = os.path.join(K.CURRENT_PKG, "tables", "e01_state_decade_temperature.csv")
    d = pd.read_csv(p)
    d = d[d["panel"] == "balanced_panel"]
    lab = {"1980s": "1980-1989", "1990s": "1990-1999", "2000s": "2000-2009",
           "2010s": "2010-2019", "2020-2025*": "2020-2025"}
    d["period"] = d["decade"].map(lab)
    # the current package calls the daily average "Tmean"; this revision calls it
    # "Tavg" and defines it explicitly. Without this remap the third variable would
    # silently drop out of every current-versus-revised comparison.
    d["variable"] = d["variable"].replace({"Tmean": "Tavg"})
    return d[["state", "variable", "period", "counties", "county_years", "median_f",
              "change_vs_1980s_f"]].rename(
        columns={"counties": "current_published_counties",
                 "county_years": "current_published_pooled_annual_observations",
                 "median_f": "current_published_median_f",
                 "change_vs_1980s_f": "current_published_change_vs_base_f"})


# =============================================================================
# 4. TEST C -- period weighting
# =============================================================================
def test_c(cp, sel, q, sa_counts):
    def rec(check, result, detail, blocking=True):
        TESTC.append(dict(test="C", check=check, result=result, blocking=blocking,
                          detail=detail))

    dup = cp.duplicated(subset=["sample", "state", "variable", "county_fips", "period"])
    rec("one_value_per_county_per_state_period",
        "PASS" if not dup.any() else "FAIL",
        "%d duplicated (sample, state, variable, county, period) rows" % int(dup.sum()))

    for sample in K.SAMPLES:
        s = cp[cp["sample"] == sample]
        n = s.groupby(["state", "variable", "period"], observed=True)["county_fips"].nunique()
        w = n.unstack("period")
        same = bool((w.nunique(axis=1) == 1).all())
        rec("same_county_count_in_every_period__%s" % sample,
            "PASS" if same else "FAIL",
            "county counts per period: %s" % w.to_dict("index"))

    b = cp[cp["sample"] == K.SAMPLE_B_NAME]
    exact = bool((b["annual_observations_used"] == K.SAMPLE_B_YEARS_PER_PERIOD).all())
    rec("strict_balanced_contributes_identical_annual_counts",
        "PASS" if exact else "FAIL",
        "every county-period must use exactly %d annual observations; observed range "
        "%d-%d" % (K.SAMPLE_B_YEARS_PER_PERIOD,
                   int(b["annual_observations_used"].min()),
                   int(b["annual_observations_used"].max())))

    # counties excluded, and why
    allc = q.groupby(["state", "variable"], observed=True)["county_fips"].nunique()
    for sample in K.SAMPLES:
        inc = (cp[cp["sample"] == sample].groupby(["state", "variable"], observed=True)
               ["county_fips"].nunique())
        exc = (allc - inc.reindex(allc.index).fillna(0)).astype(int)
        rec("counties_excluded_for_insufficient_coverage__%s" % sample, "REPORT",
            "; ".join("%s/%s %d of %d excluded" % (k[0], k[1], v, allc.loc[k])
                      for k, v in exc.items()), blocking=False)

    # duplicating one annual county-level record must not change the result
    demo = duplication_demonstration(sel)
    rec("duplicating_one_annual_record_does_not_change_the_state_estimate",
        "PASS" if demo["max_abs_change_f"] == 0 else "FAIL",
        "duplicated %s in %s; max change in any state-period median = %.10g degF "
        "(the current pooled rule changes by %.4g degF on the same perturbation)"
        % (demo["county"], demo["year"], demo["max_abs_change_f"],
           demo["current_rule_change_f"]))
    return demo


def duplication_demonstration(sel):
    """Duplicate one annual county-level observation and re-run both rules."""
    s = sel[(sel["sample"] == K.SAMPLE_A_NAME) & (sel["state"] == "TX")
            & (sel["variable"] == "Tmax")].copy()
    victim = s.sort_values(["county_fips", "year"]).iloc[0]
    extra = pd.DataFrame([victim])
    s2 = pd.concat([s, extra], ignore_index=True)

    def revised(frame):
        cp = (frame.groupby(["state", "variable", "county_fips", "period"], observed=True)
              ["period_mean_f"].mean().reset_index())
        return (cp.groupby(["state", "variable", "period"], observed=True)
                ["period_mean_f"].median())

    def pooled(frame):
        return (frame.groupby(["state", "variable", "period"], observed=True)
                ["period_mean_f"].median())

    a, b = revised(s), revised(s2)
    ca, cb = pooled(s), pooled(s2)
    return dict(county=str(victim["county_fips"]), year=int(victim["year"]),
                max_abs_change_f=float((b - a).abs().max()),
                current_rule_change_f=float((cb - ca).abs().max()))


# =============================================================================
# driver
# =============================================================================
def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 78)
    K.log("r03  STAGES 3-4 -- equal-county period aggregation")
    K.log("=" * 78)

    annual = pd.read_csv(os.path.join(K.DIR_TABLES, "county_annual_temperature.csv"),
                         dtype={"county_fips": str})
    monthly = pd.read_csv(os.path.join(K.DIR_TABLES, "county_monthly_temperature.csv"),
                          dtype={"county_fips": str})
    q = qualifying_annual(annual)
    K.log("qualifying annual county-level observations inside the periods: %s"
          % "{:,}".format(len(q)))

    ka, sela, sa_counts = sample_a(q)
    kb, selb = sample_b(q)
    members = pd.concat([ka, kb], ignore_index=True)
    sel = pd.concat([sela, selb], ignore_index=True)
    cp = county_period_values(sel)

    K.log("-" * 78)
    K.log("SAMPLE SIZES (counties retained, per state and variable)")
    K.log("   Sample A rule: %s"
          % "; ".join("%s >= %d qualifying years" % (K.PERIOD_LABEL[k], v)
                      for k, v in K.SAMPLE_A_MIN_YEARS.items()))
    K.log("   Sample B rule: exactly %d annual observations per period (%s)"
          % (K.SAMPLE_B_YEARS_PER_PERIOD, K.SAMPLE_B_SELECTION_RULE))
    allc = q.groupby(["state", "variable"], observed=True)["county_fips"].nunique()
    hdr = "   %-3s %-6s %10s %12s %12s   %s" % ("st", "var", "any-data", "Sample A",
                                                "Sample B", "current 'balanced panel'")
    K.log(hdr)
    _, cur_keep = current_method(q)
    curn = cur_keep.groupby(["state", "variable"], observed=True).size()
    for st in K.STATES:
        for var in K.VAR_KEYS:
            na = int(((ka["state"] == st) & (ka["variable"] == var)).sum())
            nb = int(((kb["state"] == st) & (kb["variable"] == var)).sum())
            K.log("   %-3s %-6s %10d %12d %12d   %d"
                  % (st, var, int(allc.get((st, var), 0)), na, nb,
                     int(curn.get((st, var), 0))))

    st_period = bootstrap_state(cp)
    st_month = monthly_equal_county(monthly, members)

    cur, _ = current_method(q)
    pub = load_current_published()

    rev = st_period[["sample", "state", "variable", "period", "contributing_counties",
                     "median_across_counties_f", "median_ci_low_f", "median_ci_high_f",
                     "iqr_across_counties_f", "difference_of_medians_vs_base_f",
                     "difference_ci_low_f", "difference_ci_high_f",
                     "annual_observations_per_county_per_period"]]
    comp = pub.merge(cur[["state", "variable", "period", "counties",
                          "pooled_annual_observations", "pooled_median_f"]]
                     .rename(columns={"counties": "current_rule_counties",
                                      "pooled_annual_observations":
                                          "current_rule_pooled_annual_observations",
                                      "pooled_median_f": "current_rule_median_f"}),
                     on=["state", "variable", "period"], how="outer")
    out = []
    for sample in K.SAMPLES:
        r = rev[rev["sample"] == sample].rename(columns={
            "contributing_counties": "revised_counties",
            "median_across_counties_f": "revised_median_f",
            "median_ci_low_f": "revised_median_ci_low_f",
            "median_ci_high_f": "revised_median_ci_high_f",
            "iqr_across_counties_f": "revised_iqr_f",
            "difference_of_medians_vs_base_f": "revised_change_vs_base_f",
            "difference_ci_low_f": "revised_change_ci_low_f",
            "difference_ci_high_f": "revised_change_ci_high_f",
            "annual_observations_per_county_per_period":
                "revised_annual_observations_per_county"})
        m = comp.merge(r, on=["state", "variable", "period"], how="left")
        m["sample"] = sample
        out.append(m)
    comp = pd.concat(out, ignore_index=True)
    comp["absolute_difference_f"] = (comp["revised_median_f"]
                                     - comp["current_published_median_f"]).round(3)
    comp["percent_difference"] = (100.0 * comp["absolute_difference_f"]
                                  / comp["current_published_median_f"]).round(3)
    comp["change_absolute_difference_f"] = (comp["revised_change_vs_base_f"]
                                            - comp["current_published_change_vs_base_f"]
                                            ).round(3)
    comp["coverage_criterion"] = comp["sample"].map({
        K.SAMPLE_A_NAME: "; ".join("%s >= %d qualifying years" % (K.PERIOD_LABEL[k], v)
                                   for k, v in K.SAMPLE_A_MIN_YEARS.items()),
        K.SAMPLE_B_NAME: "exactly %d annual observations per period (%s)"
                         % (K.SAMPLE_B_YEARS_PER_PERIOD, K.SAMPLE_B_SELECTION_RULE)})
    comp["current_aggregation"] = ("median over ALL POOLED annual county-level "
                                   "observations; county sample = at least one "
                                   "qualifying year per period")
    comp["revised_aggregation"] = ("median ACROSS COUNTIES of each county's period "
                                   "%s; one value per county per period"
                                   % K.COUNTY_PERIOD_STAT)
    comp["variable_label"] = comp["variable"].map(K.VAR_PERIOD_LABEL)
    comp["period_note"] = comp["period"].map(
        {K.PERIOD_LABEL[p]: K.PERIOD_NOTE.get(p, "") for p in K.PERIODS})
    order = ["sample", "state", "variable", "variable_label", "period", "period_note",
             "current_published_counties", "current_published_pooled_annual_observations",
             "current_published_median_f", "current_published_change_vs_base_f",
             "current_rule_counties", "current_rule_pooled_annual_observations",
             "current_rule_median_f",
             "revised_counties", "revised_annual_observations_per_county",
             "revised_median_f", "revised_median_ci_low_f", "revised_median_ci_high_f",
             "revised_iqr_f", "revised_change_vs_base_f", "revised_change_ci_low_f",
             "revised_change_ci_high_f", "absolute_difference_f", "percent_difference",
             "change_absolute_difference_f", "coverage_criterion",
             "current_aggregation", "revised_aggregation"]
    comp = comp[order].sort_values(["sample", "state", "variable", "period"])

    demo = test_c(cp, sel, q, sa_counts)
    tc = pd.DataFrame(TESTC)
    tc.to_csv(os.path.join(K.DIR_QA, "test_C_period_weighting.csv"), index=False)
    K.log("-" * 78)
    K.log("TEST C -- period weighting")
    for _, r in tc.iterrows():
        K.log("   %-6s %-58s %s" % (r["result"], r["check"], r["detail"][:70]))
    bad = tc[(tc["result"] == "FAIL") & tc["blocking"]]
    if len(bad):
        raise K.BlockingQAFailure("TEST C failed: %s" % list(bad["check"]))

    # ---- write --------------------------------------------------------------
    for c in cp.columns:
        if c.endswith("_f") or c.endswith("stations"):
            cp[c] = cp[c].round(3)
    cp.to_csv(os.path.join(K.DIR_TABLES, "county_period_temperature.csv"), index=False)
    st_period.to_csv(os.path.join(K.DIR_TABLES,
                                  "state_period_temperature_equal_county.csv"),
                     index=False)
    st_month.to_csv(os.path.join(K.DIR_TABLES,
                                 "state_month_period_temperature_equal_county.csv"),
                    index=False)
    members.to_csv(os.path.join(K.DIR_TABLES, "sample_membership_counties.csv"),
                   index=False)
    comp.to_csv(os.path.join(K.DIR_TABLES, "period_comparison_current_vs_revised.csv"),
                index=False)
    comp.to_csv(os.path.join(K.DIR_TABLES,
                             "state_period_temperature_current_vs_revised.csv"),
                index=False)
    comp.to_csv(os.path.join(K.DIR_CVR, "period_comparison_current_vs_revised.csv"),
                index=False)
    K.log("[write] county_period_temperature.csv                   %s rows"
          % "{:,}".format(len(cp)))
    K.log("[write] state_period_temperature_equal_county.csv       %d rows" % len(st_period))
    K.log("[write] state_month_period_temperature_equal_county.csv %d rows" % len(st_month))
    K.log("[write] period_comparison_current_vs_revised.csv        %d rows" % len(comp))

    # ---- the headline the FINDINGS table has to be rewritten from ----------
    K.log("-" * 78)
    K.log("DIFFERENCE from %s to %s (degF), daily high temperature"
          % (K.BASE_PERIOD, K.RECENT_PERIOD))
    K.log("   %-3s %10s   %-26s %-26s" % ("st", "current", "Sample A revised [95% CI]",
                                          "Sample B revised [95% CI]"))
    for st in K.STATES:
        cells = []
        cur_v = comp[(comp["state"] == st) & (comp["variable"] == "Tmax")
                     & (comp["period"] == K.RECENT_PERIOD)
                     & (comp["sample"] == K.SAMPLE_A_NAME)]
        cv = float(cur_v["current_published_change_vs_base_f"].iloc[0]) if len(cur_v) else np.nan
        for sample in K.SAMPLES:
            s = st_period[(st_period["sample"] == sample) & (st_period["state"] == st)
                          & (st_period["variable"] == "Tmax")
                          & (st_period["period"] == K.RECENT_PERIOD)]
            if len(s):
                r = s.iloc[0]
                cells.append("%+.2f [%+.2f, %+.2f] n=%d"
                             % (r["difference_of_medians_vs_base_f"],
                                r["difference_ci_low_f"], r["difference_ci_high_f"],
                                r["contributing_counties"]))
            else:
                cells.append("n/a")
        K.log("   %-3s %+9.2f   %-26s %-26s" % (st, cv, cells[0], cells[1]))
    K.log("")
    K.log("   duplicating one annual county-level record changes the revised estimate "
          "by %.10g degF and the current pooled estimate by %.4g degF"
          % (demo["max_abs_change_f"], demo["current_rule_change_f"]))
    K.log("r03 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
