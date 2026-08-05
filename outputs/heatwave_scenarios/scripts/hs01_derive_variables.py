"""
=============================================================================
hs01_derive_variables.py  --  read county_daily_heat.csv (READ-ONLY) and derive
                              every new column this package needs.
=============================================================================
Implements plan revision 6, section 1 (EHF) and section 3-5 (hix envelope, QC).

New columns added to a copy of the county-day table:
  synthetic_tmax_rhmax_hi_f    Tmax+RHmax synthetic heat-index ENVELOPE (nonconcurrent;
                               not an observed maximum heat index -- see add_hix_envelope)
  qc_category                  confirmed_artifact | rule_flagged_probable_artifact | valid
  dmt_f, dmt_c                 daily mean temperature, Fahrenheit and Celsius
  dmt_3day_mean_c              trailing 3-day mean DMT (this day + 2 prior), Celsius
  dmt_prior30_mean_c           prior 30-day mean DMT, DISJOINT from the 3-day window (i-32..i-3)
  ehiaccl_c                    baseline-independent (does not involve T95)
  ehisig_c_fixed / _wf         baseline-DEPENDENT (T95 differs)
  ehf_c2_fixed / _wf
  ehf_n_imputed_3d/30d, ehf_imputation_fraction_3d/30d, ehf_any/high_imputed_support_flag

T95 (both baselines) and ehf85_c2 (severity reference) are computed separately in
compute_t95_all() / compute_ehf85() below, one row per (county[, analysis_year]),
NOT as a per-row column on the daily table (they are properties of a REFERENCE
PERIOD, not of an individual day).

Nothing here modifies outputs/TX/county_daily_heat.csv or any file under pipeline/.
=============================================================================
"""
import os, sys, time
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hs00_config as H
sys.path.insert(0, H.PIPELINE_DIR)
from heat_index import heat_index_f     # bundled NWS Rothfusz formula, imported unmodified

DAILY_KEEP = ["county_fips", "county_name", "date", "year", "month", "day",
              "tmax_f", "tmin_f", "tmean_f", "rmax_pct", "rmin_pct",
              "derived_tmean_meanrh_hi_f", "derived_tmax_rhmin_hi_proxy_f",
              "temp_imputed", "rh_imputed", "qc_rh_pin_likely_artifact", "prcp_in"]


def log(*a):
    print(*a, flush=True)


# =============================================================================
# 1. load
# =============================================================================
def load_county_days(state="TX"):
    path = H.county_day_path(state)
    cd = pd.read_csv(path, usecols=DAILY_KEEP, dtype={"county_fips": str})
    cd["date"] = pd.to_datetime(cd["date"])
    for c in ("temp_imputed", "rh_imputed", "qc_rh_pin_likely_artifact"):
        cd[c] = cd[c].astype(str).str.lower().isin(("true", "1", "yes"))
    cd = cd.sort_values(["county_fips", "date"]).reset_index(drop=True)
    log("[load] %s: %d county-days, %d counties, %s..%s"
        % (state, len(cd), cd["county_fips"].nunique(), cd["date"].min().date(), cd["date"].max().date()))
    return cd


# =============================================================================
# 2. synthetic Tmax+RHmax envelope
# =============================================================================
def add_hix_envelope(cd):
    # Named explicitly to signal what it is: Tmax and RHmax do NOT co-occur (Tmax is an
    # afternoon extreme, RHmax typically overnight/early-morning), so this is a SYNTHETIC
    # envelope, not an observed maximum heat index. The name must never shorten to
    # something that reads like a real observation.
    cd["synthetic_tmax_rhmax_hi_f"] = heat_index_f(cd["tmax_f"], cd["rmax_pct"])
    return cd


# =============================================================================
# 3. QC category -- confirmed_artifact / rule_flagged_probable_artifact / valid
#    (confirmed list is a fixed lookup, NEVER derived from the rule below)
# =============================================================================
def add_qc_category(cd):
    date_str = cd["date"].dt.strftime("%Y-%m-%d")
    key = cd["county_fips"].astype(str) + "|" + date_str

    confirmed_keys = {"%s|%s" % (k["county_fips"], k["date"]) for k in H.CONFIRMED_ARTIFACT_KEYS}
    is_confirmed = key.isin(confirmed_keys)

    rh_pin = (cd["rmax_pct"].round(6) == 100.0) & (cd["rmin_pct"].round(6) == 100.0)
    no_rain = cd["prcp_in"].fillna(0) < H.NO_RAIN_PRCP_IN_THRESHOLD
    warm = cd["tmax_f"] >= H.WARM_TMAX_F_THRESHOLD
    rule_flagged = (rh_pin & no_rain & warm).fillna(False)

    cd["qc_rh_saturation_flag"] = rh_pin.fillna(False)
    cd["qc_no_rain_flag"] = no_rain.fillna(False)
    cd["qc_warm_temperature_flag"] = warm.fillna(False)
    cd["qc_category"] = np.where(is_confirmed, "confirmed_artifact",
                                 np.where(rule_flagged, "rule_flagged_probable_artifact", "valid"))

    n_conf = int(is_confirmed.sum())
    n_rule = int((rule_flagged & ~is_confirmed).sum())
    if n_conf != len(H.CONFIRMED_ARTIFACT_KEYS):
        raise AssertionError("expected exactly %d confirmed_artifact rows, found %d -- check "
                             "CONFIRMED_ARTIFACT_KEYS against the source table" %
                             (len(H.CONFIRMED_ARTIFACT_KEYS), n_conf))
    log("[qc] confirmed_artifact=%d  rule_flagged_probable_artifact=%d  valid=%d"
        % (n_conf, n_rule, len(cd) - n_conf - n_rule))
    return cd


# =============================================================================
# 4. EHF components -- per-county, calendar-aware (reindexed), date-ordered rolling
# =============================================================================
def add_ehf_components(cd):
    cd = cd.sort_values(["county_fips", "date"]).reset_index(drop=True)
    cd["dmt_f"] = cd["tmean_f"]
    cd["dmt_c"] = (cd["dmt_f"] - 32.0) * 5.0 / 9.0

    parts = []
    t0 = time.time()
    counties = sorted(cd["county_fips"].unique())
    for i, fips in enumerate(counties):
        g = cd[cd["county_fips"] == fips]
        full_index = pd.date_range(g["date"].min(), g["date"].max(), freq="D")
        gi = g.set_index("date").reindex(full_index)
        gi["county_fips"] = fips
        # a reindexed row absent from the source table has no observation at all --
        # NOT the same as temp_imputed=True (IDW-filled but present); dmt_c stays NaN
        # (correctly breaking any rolling window that spans it) and temp_imputed is
        # set True defensively so it still counts against imputation-exposure fractions.
        gi["temp_imputed"] = gi["temp_imputed"].fillna(True)

        dmt_c = gi["dmt_c"]
        imputed = gi["temp_imputed"].astype(float)
        gi["dmt_3day_mean_c"] = dmt_c.rolling(window=3, min_periods=3).mean()
        gi["dmt_prior30_mean_c"] = dmt_c.shift(3).rolling(window=30, min_periods=30).mean()
        # imputation exposure counts over each window (counts, not booleans)
        gi["ehf_n_imputed_3d"] = imputed.rolling(window=3, min_periods=3).sum()
        gi["ehf_n_imputed_30d"] = imputed.shift(3).rolling(window=30, min_periods=30).sum()

        gi = gi.reset_index().rename(columns={"index": "date"})
        parts.append(gi)
        if (i + 1) % 50 == 0:
            log("   [ehf components] %d/%d counties (%.0fs)" % (i + 1, len(counties), time.time() - t0))

    out = pd.concat(parts, ignore_index=True)

    out["ehf_imputation_fraction_3d"] = out["ehf_n_imputed_3d"] / 3.0
    out["ehf_imputation_fraction_30d"] = out["ehf_n_imputed_30d"] / 30.0
    out["ehf_any_imputed_support_flag"] = out["ehf_n_imputed_3d"].fillna(3) > 0
    out["ehf_high_imputation_support_flag"] = (
        out["ehf_imputation_fraction_30d"].fillna(1.0) > H.EHF_HIGH_IMPUTATION_SUPPORT_THRESHOLD)

    # baseline-independent: EHIaccl never involves T95
    out["ehiaccl_c"] = out["dmt_3day_mean_c"] - out["dmt_prior30_mean_c"]

    log("[ehf components] done: %d rows (%.0fs)" % (len(out), time.time() - t0))
    return out


# =============================================================================
# 5. T95 -- both baselines, with the full reference-adequacy rule (plan Sec.1 fix)
# =============================================================================
def _reference_quality(n_valid, expected_days, n_distinct_years, n_imputed):
    completeness = n_valid / expected_days if expected_days else 0.0
    imputation_frac = (n_imputed / n_valid) if n_valid else 1.0
    if n_valid == 0:
        flag = "missing"
    elif completeness < H.MIN_REFERENCE_COMPLETENESS_FRACTION:
        flag = "insufficient_day_coverage"
    elif n_distinct_years < H.MIN_DISTINCT_REFERENCE_YEARS:
        flag = "insufficient_year_coverage"
    elif imputation_frac > H.EXCESSIVE_REFERENCE_IMPUTATION_THRESHOLD:
        flag = "excessive_reference_imputation"
    else:
        flag = "ok"
    return completeness, imputation_frac, flag


def compute_t95_all(ehf_df):
    """One row per county (fixed) + one row per county x analysis-year (walk-forward)."""
    rows = []
    for fips, g in ehf_df.groupby("county_fips", sort=True):
        yrs = g["year"].to_numpy()
        dmt = g["dmt_c"].to_numpy()
        imputed = g["temp_imputed"].to_numpy().astype(bool)
        valid = ~pd.isna(dmt)

        # ---- fixed 1979-2014 ----
        fy0, fy1 = H.FIXED_BASELINE
        m = (yrs >= fy0) & (yrs <= fy1) & valid
        expected_days = (pd.Timestamp(fy1, 12, 31) - pd.Timestamp(fy0, 1, 1)).days + 1
        n_valid = int(m.sum())
        by_year = pd.Series(yrs[m]).value_counts()
        n_distinct_years = int((by_year >= H.MIN_VALID_DAYS_PER_QUALIFYING_YEAR).sum())
        n_imp = int(imputed[m].sum())
        completeness, imp_frac, flag = _reference_quality(n_valid, expected_days, n_distinct_years, n_imp)
        t95 = float(np.percentile(dmt[m], 95)) if n_valid else np.nan
        rows.append({"county_fips": fips, "baseline": "fixed_1979_2014", "analysis_year": None,
                     "t95_c": t95, "expected_reference_days": expected_days,
                     "n_reference_days": n_valid, "reference_day_completeness_fraction": completeness,
                     "n_distinct_reference_years": n_distinct_years,
                     "reference_imputed_day_count": n_imp, "reference_imputation_fraction": imp_frac,
                     "threshold_quality_flag": flag})

        # ---- walk-forward: year Y <- 1979..Y-1 ----
        for Y in range(H.ANALYSIS_YEARS[0], H.ANALYSIS_YEARS[1] + 1):
            mw = (yrs <= Y - 1) & valid
            expected_days_w = (pd.Timestamp(Y - 1, 12, 31) - pd.Timestamp(H.BASELINE_START, 1, 1)).days + 1
            n_valid_w = int(mw.sum())
            by_year_w = pd.Series(yrs[mw]).value_counts()
            n_distinct_years_w = int((by_year_w >= H.MIN_VALID_DAYS_PER_QUALIFYING_YEAR).sum())
            n_imp_w = int(imputed[mw].sum())
            completeness_w, imp_frac_w, flag_w = _reference_quality(
                n_valid_w, expected_days_w, n_distinct_years_w, n_imp_w)
            t95_w = float(np.percentile(dmt[mw], 95)) if n_valid_w else np.nan
            rows.append({"county_fips": fips, "baseline": "walk_forward", "analysis_year": Y,
                        "t95_c": t95_w, "expected_reference_days": expected_days_w,
                        "n_reference_days": n_valid_w,
                        "reference_day_completeness_fraction": completeness_w,
                        "n_distinct_reference_years": n_distinct_years_w,
                        "reference_imputed_day_count": n_imp_w,
                        "reference_imputation_fraction": imp_frac_w,
                        "threshold_quality_flag": flag_w})
    return pd.DataFrame(rows)


def apply_t95(ehf_df, t95_df):
    """Attach ehisig_c/ehf_c2 for both baselines onto the daily EHF-component table."""
    fixed = t95_df[t95_df["baseline"] == "fixed_1979_2014"].set_index("county_fips")["t95_c"]
    ehf_df["t95_c_fixed"] = ehf_df["county_fips"].map(fixed)
    ehf_df["ehisig_c_fixed"] = ehf_df["dmt_3day_mean_c"] - ehf_df["t95_c_fixed"]
    ehf_df["ehf_c2_fixed"] = ehf_df["ehisig_c_fixed"] * np.maximum(1.0, ehf_df["ehiaccl_c"])

    wf = t95_df[t95_df["baseline"] == "walk_forward"].set_index(["county_fips", "analysis_year"])["t95_c"]
    an = ehf_df[(ehf_df["year"] >= H.ANALYSIS_YEARS[0]) & (ehf_df["year"] <= H.ANALYSIS_YEARS[1])].copy()
    an["t95_c_wf"] = an.set_index(["county_fips", "year"]).index.map(wf).to_numpy()
    an["ehisig_c_wf"] = an["dmt_3day_mean_c"] - an["t95_c_wf"]
    an["ehf_c2_wf"] = an["ehisig_c_wf"] * np.maximum(1.0, an["ehiaccl_c"])

    ehf_df = ehf_df.merge(an[["county_fips", "date", "t95_c_wf", "ehisig_c_wf", "ehf_c2_wf"]],
                          on=["county_fips", "date"], how="left")
    return ehf_df


# =============================================================================
# 6. EHF85 severity reference (fixed baseline only; plan Sec.1)
# =============================================================================
def compute_ehf85(ehf_df, ehf_col="ehf_c2_fixed"):
    fy0, fy1 = H.FIXED_BASELINE
    rows = []
    ref = ehf_df[(ehf_df["year"] >= fy0) & (ehf_df["year"] <= fy1)]
    for fips, g in ref.groupby("county_fips", sort=True):
        pos = g.loc[g[ehf_col] > 0, ehf_col].dropna()
        n_pos = len(pos)
        n_years = g.loc[g[ehf_col] > 0, "year"].nunique()
        if n_pos < H.EHF_SEVERITY_MIN_POSITIVE_REFERENCE_VALUES or n_years < H.EHF_SEVERITY_MIN_DISTINCT_YEARS:
            flag = ("insufficient_positive_reference" if n_pos < H.EHF_SEVERITY_MIN_POSITIVE_REFERENCE_VALUES
                    else "insufficient_reference_years")
            ehf85 = np.nan
        else:
            ehf85 = float(np.percentile(pos, 85))
            flag = "degenerate_reference" if abs(ehf85) < H.EHF_SEVERITY_DEGENERATE_TOLERANCE_C2 else "ok"
            if flag == "degenerate_reference":
                ehf85 = np.nan
        rows.append({"county_fips": fips, "ehf85_c2": ehf85, "n_positive_reference_ehf_values": n_pos,
                    "n_distinct_reference_years_with_positive_ehf": n_years,
                    "severity_quality_flag": flag})
    return pd.DataFrame(rows)


def apply_severity(ehf_df, ehf85_df):
    e85 = ehf85_df.set_index("county_fips")["ehf85_c2"]
    flag = ehf85_df.set_index("county_fips")["severity_quality_flag"]
    ehf_df["ehf85_c2"] = ehf_df["county_fips"].map(e85)
    ehf_df["severity_quality_flag"] = ehf_df["county_fips"].map(flag)

    def classify(ehf_c2, ratio, flag):
        if flag != "ok":
            return "undetermined"
        if pd.isna(ehf_c2):
            return np.nan
        if ehf_c2 <= 0:
            return "not_positive_ehf"
        if ratio < H.EHF_SEVERITY_SEVERE_RATIO:
            return "low_intensity"
        if ratio < H.EHF_SEVERITY_EXTREME_RATIO:
            return "severe"
        return "extreme"

    for col_ehf, col_ratio, col_class in (
        ("ehf_c2_fixed", "ehf_severity_ratio_fixed", "ehf_severity_class_fixed"),
        ("ehf_c2_wf", "ehf_severity_ratio_wf", "ehf_severity_class_wf"),
    ):
        ehf_df[col_ratio] = ehf_df[col_ehf] / ehf_df["ehf85_c2"]
        ehf_df[col_class] = [classify(v, r, f) for v, r, f in
                             zip(ehf_df[col_ehf], ehf_df[col_ratio], ehf_df["severity_quality_flag"])]
    return ehf_df


# =============================================================================
# 7. boundary metadata (plan Sec.1)
# =============================================================================
def boundary_metadata(ehf_df):
    theoretical_first = pd.Timestamp(H.BASELINE_START, 1, 1) + pd.Timedelta(days=32)
    valid_mask = ehf_df["dmt_3day_mean_c"].notna() & ehf_df["dmt_prior30_mean_c"].notna()
    actual_first = ehf_df.loc[valid_mask, "date"].min()
    n_lost = int((ehf_df["date"] < actual_first).sum()) if pd.notna(actual_first) else None
    log("[boundary] theoretical first valid assessment date: %s" % theoretical_first.date())
    log("[boundary] actual first valid assessment date:      %s" % (actual_first.date() if pd.notna(actual_first) else "N/A"))
    return {"ehf_theoretical_first_valid_assessment_date": theoretical_first,
            "ehf_actual_first_valid_assessment_date": actual_first,
            "n_reference_dates_lost_to_rolling_support": n_lost}


# =============================================================================
# driver
# =============================================================================
def build(state="TX", write=True):
    t0 = time.time()
    cd = load_county_days(state)
    cd = add_hix_envelope(cd)
    cd = add_qc_category(cd)
    ehf_df = add_ehf_components(cd)

    t95_df = compute_t95_all(ehf_df)
    ehf_df = apply_t95(ehf_df, t95_df)
    ehf85_df = compute_ehf85(ehf_df, ehf_col="ehf_c2_fixed")
    ehf_df = apply_severity(ehf_df, ehf85_df)
    boundary = boundary_metadata(ehf_df)

    # structural QA: EHF>0 <=> EHIsig>0, for both baselines, wherever both are defined
    for suf in ("fixed", "wf"):
        e = ehf_df["ehf_c2_%s" % suf]
        s = ehf_df["ehisig_c_%s" % suf]
        m = e.notna() & s.notna()
        mismatch = int(((e[m] > 0) != (s[m] > 0)).sum())
        if mismatch:
            raise AssertionError("EHF>0 <=> EHIsig>0 structural identity violated (%s): %d mismatches"
                                 % (suf, mismatch))
        log("[qa] structural identity holds for ehf_c2_%s (%d rows checked)" % (suf, int(m.sum())))

    if write:
        # ehf_df already carries the envelope/qc_category columns through -- add_ehf_components() reindexes
        # `cd` (which already has them) per county, and the reindex preserves existing columns for
        # every row that isn't a true calendar gap (verified: 0 gaps in this table). Merging them
        # back in from `cd` here would be redundant and would silently _x/_y-suffix every
        # overlapping column instead of erroring -- write ehf_df directly.
        out_path = os.path.join(H.TABLES_DIR, "_derived_variables_%s.csv.gz" % state)
        ehf_df.to_csv(out_path, index=False, compression="gzip")
        log("[write] %s (%d rows, %.0fs total)" % (out_path, len(ehf_df), time.time() - t0))
        t95_df.to_csv(os.path.join(H.TABLES_DIR, "_t95_reference_%s.csv" % state), index=False)
        ehf85_df.to_csv(os.path.join(H.TABLES_DIR, "_ehf85_reference_%s.csv" % state), index=False)
        return ehf_df, t95_df, ehf85_df, boundary
    return ehf_df, t95_df, ehf85_df, boundary


if __name__ == "__main__":
    build()
