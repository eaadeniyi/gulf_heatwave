"""
Plan Sec.1 blocking fix: the T95 reference-adequacy rule (day-completeness AND
year-coverage AND imputation-fraction), replacing the indefensible bare n>=20
count. Verifies threshold_quality_flag correctly reaches each failure state on
engineered low-coverage counties, and 'ok' on a county meeting every floor.
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hs00_config as H
import hs01_derive_variables as hs01

FAILS = []


def check(label, got, want):
    print("   [%s] %-60s got=%s want=%s" % ("PASS" if got == want else "FAIL", label, got, want))
    if got != want:
        FAILS.append(label)


print("=" * 78)
print("test_t95_reference_adequacy")
print("=" * 78)

fy0, fy1 = H.FIXED_BASELINE
full_dates = pd.date_range("%d-01-01" % fy0, "%d-12-31" % fy1, freq="D")
n_full = len(full_dates)
print("fixed baseline %d-%d: %d expected reference days" % (fy0, fy1, n_full))


def make_ehf_frame(fips, present_mask, dmt_val=20.0, imputed_frac_within_present=0.0):
    """present_mask: boolean array over full_dates -- True where a valid (non-missing)
    reference day exists. imputed_frac_within_present: fraction of the PRESENT days
    that are flagged temp_imputed=True (drawn deterministically, evenly spaced)."""
    dmt = np.where(present_mask, dmt_val, np.nan)
    imputed = np.zeros(n_full, dtype=bool)
    present_idx = np.flatnonzero(present_mask)
    n_imp = int(round(len(present_idx) * imputed_frac_within_present))
    if n_imp:
        imputed[present_idx[:: max(1, len(present_idx) // n_imp)][:n_imp]] = True
    return pd.DataFrame({"county_fips": fips, "year": full_dates.year, "dmt_c": dmt,
                         "temp_imputed": imputed})


# ---- case OK: full coverage, low imputation ----
mask_ok = np.ones(n_full, dtype=bool)
df_ok = make_ehf_frame("11111", mask_ok, imputed_frac_within_present=0.10)

# ---- case insufficient_day_coverage: only 70% of days present (< 0.90 floor), but the
#      distinct-year and imputation floors would otherwise pass ----
rng = np.random.default_rng(1)
mask_daycov = rng.random(n_full) < 0.70
df_daycov = make_ehf_frame("22222", mask_daycov, imputed_frac_within_present=0.05)

# ---- case insufficient_year_coverage: overall day-completeness is kept ABOVE the 0.90
#      floor (so this isolates the year-coverage failure specifically, not a mix of both),
#      but the days are concentrated in only 29 fully-present years (< the 30 required) --
#      the other 7 years each get 250 days (below the 300-day per-year qualifying floor,
#      so they don't count toward n_distinct_reference_years, but their days still count
#      toward overall completeness).
years = np.arange(fy0, fy1 + 1)
full_years = set(years[:29].tolist())
mask_yearcov = np.zeros(n_full, dtype=bool)
for yr in years:
    yr_idx = np.flatnonzero(full_dates.year == yr)
    if yr in full_years:
        mask_yearcov[yr_idx] = True
    else:
        mask_yearcov[yr_idx[:250]] = True
df_yearcov = make_ehf_frame("33333", mask_yearcov, imputed_frac_within_present=0.05)
_completeness_yearcov = mask_yearcov.mean()
print("   (engineered year-coverage case: 29 full years + 7 partial(250d) years -> "
      "completeness=%.3f, should be >= %.2f)" % (_completeness_yearcov, H.MIN_REFERENCE_COMPLETENESS_FRACTION))
assert _completeness_yearcov >= H.MIN_REFERENCE_COMPLETENESS_FRACTION, (
    "test engineering error: completeness must clear the day-coverage floor so this case "
    "isolates the year-coverage failure specifically")

# ---- case excessive_reference_imputation: full day/year coverage, but 70% of the
#      present days are IDW-imputed (> 0.50 floor) ----
df_imputed = make_ehf_frame("44444", mask_ok, imputed_frac_within_present=0.70)

combined = pd.concat([df_ok, df_daycov, df_yearcov, df_imputed], ignore_index=True)
t95_df = hs01.compute_t95_all(combined)
fixed = t95_df[t95_df["baseline"] == "fixed_1979_2014"].set_index("county_fips")

check("OK case -> threshold_quality_flag == ok", fixed.loc["11111", "threshold_quality_flag"], "ok")
check("day-coverage case -> insufficient_day_coverage",
      fixed.loc["22222", "threshold_quality_flag"], "insufficient_day_coverage")
check("year-coverage case -> insufficient_year_coverage",
      fixed.loc["33333", "threshold_quality_flag"], "insufficient_year_coverage")
check("excessive-imputation case -> excessive_reference_imputation",
      fixed.loc["44444", "threshold_quality_flag"], "excessive_reference_imputation")

print()
print("   completeness fractions:")
for fips in ("11111", "22222", "33333", "44444"):
    r = fixed.loc[fips]
    print("     %s: completeness=%.3f  distinct_years=%d  imputation_frac=%.3f  flag=%s"
          % (fips, r["reference_day_completeness_fraction"], r["n_distinct_reference_years"],
             r["reference_imputation_fraction"], r["threshold_quality_flag"]))

# ---- sanity: the OK case's completeness/imputation numbers are exactly what was engineered ----
r_ok = fixed.loc["11111"]
check("OK case completeness == 1.0", round(float(r_ok["reference_day_completeness_fraction"]), 6), 1.0)
check("OK case n_distinct_reference_years == 36", int(r_ok["n_distinct_reference_years"]), fy1 - fy0 + 1)

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- T95 reference-adequacy rule replaces the old bare n>=20 count correctly")
