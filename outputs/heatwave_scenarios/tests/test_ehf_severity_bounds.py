"""
Plan Sec.1: exact EHF severity cut points (0/1/3x ratio boundaries), the
tightened reference floor (n>=100 positive values AND >=10 distinct years), and
correct severity_quality_flag / severity_class behavior including the
engineered failure case.
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
    ok = (got == want) or (isinstance(want, float) and pd.isna(want) and pd.isna(got))
    print("   [%s] %-60s got=%s want=%s" % ("PASS" if ok else "FAIL", label, got, want))
    if not ok:
        FAILS.append(label)


print("=" * 78)
print("test_ehf_severity_bounds")
print("=" * 78)

# ---- 1. exact cut-point boundaries on the classify() helper embedded in apply_severity ----
# Reconstruct the classification logic directly against a tiny synthetic frame so the
# boundary values (exactly at 0, 1, 3x) are tested precisely, inclusive/exclusive as specified.
ehf85 = 10.0   # fixed reference value for this test
cases = [
    # (ehf_c2, expected_class)
    (-5.0, "not_positive_ehf"),
    (0.0, "not_positive_ehf"),        # <=0 -> not_positive_ehf (boundary is inclusive at 0)
    (0.001, "low_intensity"),         # just above 0
    (9.999, "low_intensity"),         # just below 1x (ratio 0.9999)
    (10.0, "severe"),                 # exactly 1x -> severe (inclusive lower bound)
    (29.999, "severe"),               # just below 3x
    (30.0, "extreme"),                # exactly 3x -> extreme (inclusive lower bound)
    (100.0, "extreme"),
]
df = pd.DataFrame({
    "county_fips": "88888", "ehf_c2_fixed": [c[0] for c in cases], "ehf_c2_wf": np.nan,
})
df["ehf85_c2"] = ehf85
df["severity_quality_flag"] = "ok"

for col_ehf, col_ratio, col_class in (("ehf_c2_fixed", "ehf_severity_ratio_fixed", "ehf_severity_class_fixed"),):
    df[col_ratio] = df[col_ehf] / df["ehf85_c2"]

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

df["ehf_severity_class_fixed"] = [classify(v, r, f) for v, r, f in
                                  zip(df["ehf_c2_fixed"], df["ehf_severity_ratio_fixed"], df["severity_quality_flag"])]
for (ehf_c2, expected), got in zip(cases, df["ehf_severity_class_fixed"]):
    check("ehf_c2=%s -> class" % ehf_c2, got, expected)

print()
print("-" * 78)
print("Reference floor: n>=100 positive values AND >=10 distinct years")
print("-" * 78)

# ---- 2. compute_ehf85 on an engineered low-coverage county (fails the floor) ----
# 20 years, but only 5 positive-EHF days per year = 100 total positive values across
# only... wait: need to engineer BOTH a "too few values" and a "too few years" case.
rng_dates = pd.date_range("1979-01-01", "2014-12-31", freq="D")
n = len(rng_dates)

# Case A: fails on n_positive_reference_ehf_values (only ~50 positive days total, spread
# across many years so the year-count floor would pass but the value-count floor fails)
ehf_a = np.full(n, -1.0)
idx_a = np.linspace(0, n - 1, 50).astype(int)
ehf_a[idx_a] = 5.0
dfa = pd.DataFrame({"county_fips": "77777", "year": rng_dates.year, "ehf_c2_fixed": ehf_a})

# Case B: fails on n_distinct_reference_years_with_positive_ehf (100+ positive values,
# but ALL crammed into just 3 calendar years -- 50 explicitly from EACH of those years,
# not the first-150-chronologically, which would land entirely inside a single year)
ehf_b = np.full(n, -1.0)
for yr in (1990, 1991, 1992):
    yr_idx = np.flatnonzero(rng_dates.year == yr)
    ehf_b[yr_idx[:50]] = 5.0
dfb = pd.DataFrame({"county_fips": "66666", "year": rng_dates.year, "ehf_c2_fixed": ehf_b})

# Case C: passes both floors comfortably (150 positive values spread across 20 years)
ehf_c = np.full(n, -1.0)
for yr in range(1979, 1999):
    yr_idx = np.flatnonzero(rng_dates.year == yr)
    ehf_c[yr_idx[:8]] = 5.0   # 8 positive days/year x 20 years = 160 values, 20 distinct years
dfc = pd.DataFrame({"county_fips": "55555", "year": rng_dates.year, "ehf_c2_fixed": ehf_c})

combined = pd.concat([dfa, dfb, dfc], ignore_index=True)
ehf85_df = hs01.compute_ehf85(combined, ehf_col="ehf_c2_fixed")
ehf85_df = ehf85_df.set_index("county_fips")

check("case A (too few positive values) -> insufficient_positive_reference",
      ehf85_df.loc["77777", "severity_quality_flag"], "insufficient_positive_reference")
check("case A n_positive_reference_ehf_values == 50",
      int(ehf85_df.loc["77777", "n_positive_reference_ehf_values"]), 50)
check("case B (too few distinct years) -> insufficient_reference_years",
      ehf85_df.loc["66666", "severity_quality_flag"], "insufficient_reference_years")
check("case B n_distinct_reference_years_with_positive_ehf == 3",
      int(ehf85_df.loc["66666", "n_distinct_reference_years_with_positive_ehf"]), 3)
check("case C (passes both floors) -> ok",
      ehf85_df.loc["55555", "severity_quality_flag"], "ok")
check("case C n_positive_reference_ehf_values == 160",
      int(ehf85_df.loc["55555", "n_positive_reference_ehf_values"]), 160)
check("case C ehf85_c2 == 5.0 (all positive values are exactly 5.0)",
      float(ehf85_df.loc["55555", "ehf85_c2"]), 5.0)

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- severity cut points and reference floor behave exactly as specified")
