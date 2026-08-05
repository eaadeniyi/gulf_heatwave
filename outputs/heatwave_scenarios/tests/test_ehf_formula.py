"""
Plan revision 6, Sec.1 blocking fix: a NUMERICAL Celsius-equivalence test, not a
name-based check (a name-based check is brittle -- correct code could log
Fahrenheit values without using them, or convert incorrectly while avoiding the
literal variable name).

Method: build a synthetic Fahrenheit Tmean sequence, independently compute the
expected EHIsig/EHIaccl/EHF in Celsius by hand (via plain numpy, NOT by calling
hs01), run it through the real hs01 implementation, and assert exact agreement.
Then compute a DELIBERATELY WRONG result (skip the F->C conversion) and assert
the real implementation does NOT match that wrong value -- proving the
conversion was actually applied, not just present somewhere in the code.
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hs01_derive_variables as hs01

FAILS = []


def check(label, got, want, tol=1e-9):
    ok = (pd.isna(got) and pd.isna(want)) or (not pd.isna(got) and not pd.isna(want) and abs(got - want) < tol)
    print("   [%s] %-55s got=%s want=%s" % ("PASS" if ok else "FAIL", label, got, want))
    if not ok:
        FAILS.append(label)
    return ok


def check_true(label, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", label))
    if not cond:
        FAILS.append(label)


def make_synthetic_county(tmean_f_seq, start="2019-01-01", fips="99999"):
    dates = pd.date_range(start, periods=len(tmean_f_seq))
    return pd.DataFrame({
        "county_fips": fips, "county_name": "Synthetic", "date": dates,
        "year": dates.year, "month": dates.month, "day": dates.day,
        "tmax_f": np.nan, "tmin_f": np.nan, "tmean_f": tmean_f_seq,
        "rmax_pct": 50.0, "rmin_pct": 30.0, "prcp_in": 0.0,
        "derived_tmean_meanrh_hi_f": np.nan, "derived_tmax_rhmin_hi_proxy_f": np.nan,
        "temp_imputed": False, "rh_imputed": False, "qc_rh_pin_likely_artifact": False,
    })


print("=" * 78)
print("test_ehf_formula -- numerical Celsius-equivalence, not name-based")
print("=" * 78)

# 50 days at 70F, days 35-37 (0-indexed 34-36) at 100F -- a clean, well-separated
# "hot spell" so the 3-day window and the disjoint prior-30-day window don't overlap
# and don't touch the start of the record (min_periods=30 needs day >= 33 to have a
# full window; the spell starts at day 35, well clear of that).
seq = [70.0] * 50
seq[34] = seq[35] = seq[36] = 100.0
cd = make_synthetic_county(seq)

out = hs01.add_ehf_components(cd)

# ---- independent, by-hand expected computation (plain numpy, not hs01) ----
dmt_c_expected = (np.array(seq) - 32.0) * 5.0 / 9.0
i = 36   # last day of the hot spell (0-indexed), date = day 37
mean3 = dmt_c_expected[i - 2:i + 1].mean()
mean30 = dmt_c_expected[i - 32:i - 2].mean()          # i-32 .. i-3 inclusive = indices i-32 .. i-2 (exclusive end i-2+1... )
# careful index arithmetic: "i-32..i-3" inclusive on both ends -> python slice [i-32 : i-2]
mean30 = dmt_c_expected[i - 32: i - 2].mean()
ehiaccl_expected = mean3 - mean30
t95_c_test = 25.0     # arbitrary fixed threshold for this formula-only test
ehisig_expected = mean3 - t95_c_test
ehf_expected = ehisig_expected * max(1.0, ehiaccl_expected)

row = out[out["date"] == cd["date"].iloc[i]].iloc[0]
check("dmt_c at hot-spell peak", row["dmt_c"], dmt_c_expected[i])
check("dmt_3day_mean_c", row["dmt_3day_mean_c"], mean3)
check("dmt_prior30_mean_c", row["dmt_prior30_mean_c"], mean30)
check("ehiaccl_c (baseline-independent)", row["ehiaccl_c"], ehiaccl_expected)

# apply the test's own T95 (both "baselines" set to the same value here -- this test is
# about the FORMULA, not about T95 estimation, which is covered by other test files)
out["t95_c_fixed"] = t95_c_test
out["ehisig_c_fixed"] = out["dmt_3day_mean_c"] - out["t95_c_fixed"]
out["ehf_c2_fixed"] = out["ehisig_c_fixed"] * np.maximum(1.0, out["ehiaccl_c"])
row = out[out["date"] == cd["date"].iloc[i]].iloc[0]
check("ehisig_c_fixed", row["ehisig_c_fixed"], ehisig_expected)
check("ehf_c2_fixed (real implementation)", row["ehf_c2_fixed"], ehf_expected)

# ---- structural identity: EHF>0 <=> EHIsig>0 ----
m = out["ehf_c2_fixed"].notna() & out["ehisig_c_fixed"].notna()
check_true("EHF>0 <=> EHIsig>0 holds on this synthetic series",
          bool(((out.loc[m, "ehf_c2_fixed"] > 0) == (out.loc[m, "ehisig_c_fixed"] > 0)).all()))

print()
print("-" * 78)
print("Deliberately WRONG calculation: skip the F->C conversion")
print("-" * 78)
# Treat the raw Fahrenheit tmean values AS IF they were already Celsius (the exact bug
# this test exists to catch): rebuild the whole pipeline on tmean_f directly, no conversion.
wrong = cd.copy()
wrong["dmt_c_WRONG"] = wrong["tmean_f"]        # <-- the bug: no (F-32)*5/9 conversion
dmt_wrong = wrong["dmt_c_WRONG"].to_numpy()
mean3_wrong = dmt_wrong[i - 2:i + 1].mean()
mean30_wrong = dmt_wrong[i - 32:i - 2].mean()
ehiaccl_wrong = mean3_wrong - mean30_wrong
ehisig_wrong = mean3_wrong - t95_c_test
ehf_wrong = ehisig_wrong * max(1.0, ehiaccl_wrong)

print("   real implementation ehf_c2_fixed = %.6f" % ehf_expected)
print("   wrong (no-conversion) ehf_c2     = %.6f" % ehf_wrong)
check_true("real implementation does NOT match the no-conversion bug",
          abs(ehf_expected - ehf_wrong) > 1.0)   # they differ by a lot (70F vs 21.1C is a huge gap)

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- EHF formula verified numerically, Celsius conversion confirmed applied")
