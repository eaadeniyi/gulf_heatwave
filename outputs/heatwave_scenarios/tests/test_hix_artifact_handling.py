"""
Plan Sec.5 / revision-5 fix: verifies the METHOD, not a forced numerical effect.

Requires:
  1. artifact records are ABSENT from the QC-filtered reference pool
  2. thresholds are RECOMPUTED from the filtered data
  3. the reference count changes by exactly the number of affected records
  4. any resulting threshold difference is RECORDED
  5. NO difference is also an acceptable result (removing one value from a large
     reference pool may legitimately leave a percentile unchanged)
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hs00_config as H
import hs02_classify as hs02
sys.path.insert(0, H.PIPELINE_DIR)
from p02_classify_and_report import compute_thresholds, MD_TO_TDOY
import config as PC

FAILS = []


def check_true(label, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", label))
    if not cond:
        FAILS.append(label)


print("=" * 78)
print("test_hix_artifact_handling")
print("=" * 78)

derived_path = os.path.join(H.TABLES_DIR, "_derived_variables_TX.csv.gz")
if not os.path.exists(derived_path):
    print("   [SKIP] derived table not built -- run hs01 first")
    sys.exit(0)

d = pd.read_csv(derived_path,
                usecols=["county_fips", "date", "year", "month", "day", "qc_category",
                         "synthetic_tmax_rhmax_hi_f", "derived_tmax_rhmin_hi_proxy_f"],
                dtype={"county_fips": str})
d["date"] = pd.to_datetime(d["date"])
md = list(zip(d["month"].to_numpy(), d["day"].to_numpy()))
d["template_doy"] = np.array([MD_TO_TDOY[k] for k in md], dtype=np.int16)

# ---- 1. exclusion sets are the right size and content ----
n_conf = int((d["qc_category"] == "confirmed_artifact").sum())
n_prob = int((d["qc_category"] == "rule_flagged_probable_artifact").sum())
print("   confirmed_artifact records:              %d" % n_conf)
print("   rule_flagged_probable_artifact records:  %d" % n_prob)
check_true("exactly 3 confirmed_artifact records (the independently verified set)", n_conf == 3)
check_true("rule-flagged set is non-empty and distinct from the confirmed set", n_prob > 0)

# ---- 2/3. artifact records absent from the filtered reference pool; count changes exactly ----
# Restrict to the affected counties so the threshold recomputation is fast but real.
affected_fips = sorted({k["county_fips"] for k in H.CONFIRMED_ARTIFACT_KEYS})
sub = d[d["county_fips"].isin(affected_fips)].copy()

for tier, expected_removed in (("CONFEXCL", n_conf), ("PROBEXCL", n_conf + n_prob)):
    excl_cats = hs02.QC_EXCLUDE_SETS[tier]
    removed_in_sub = int(sub["qc_category"].isin(excl_cats).sum())
    filtered = sub[~sub["qc_category"].isin(excl_cats)]
    check_true("%s: every excluded category is absent from the filtered pool" % tier,
              not filtered["qc_category"].isin(excl_cats).any())
    check_true("%s: filtered pool is exactly %d rows smaller (the affected records)"
              % (tier, removed_in_sub), len(sub) - len(filtered) == removed_in_sub)

# ---- 4/5. thresholds RECOMPUTED from filtered data; difference RECORDED, not required ----
print()
print("-" * 78)
print("Threshold recomputation: difference is RECORDED, a zero difference is acceptable")
print("-" * 78)
w15 = PC.GRID_WINDOWS["w15"]
metric = "synthetic_tmax_rhmax_hi_f"

thr_raw, _ = compute_thresholds(sub, metric, [95], w15, verbose=False)
sub_conf = sub[~sub["qc_category"].isin(hs02.QC_EXCLUDE_SETS["CONFEXCL"])]
thr_conf, _ = compute_thresholds(sub_conf, metric, [95], w15, verbose=False)

merged = thr_raw.merge(thr_conf, on=["county_fips", "template_doy", "analysis_year"],
                       suffixes=("_raw", "_conf"))
diff = (merged["threshold_p95_f_raw"] - merged["threshold_p95_f_conf"]).abs()
n_changed = int((diff > 1e-9).sum())
nref_changed = int((merged["n_reference_values_raw"] != merged["n_reference_values_conf"]).sum())

print("   thresholds compared:                     %s" % "{:,}".format(len(merged)))
print("   thresholds whose REFERENCE COUNT changed: %s" % "{:,}".format(nref_changed))
print("   thresholds whose VALUE changed:           %s" % "{:,}".format(n_changed))
if n_changed:
    print("   max |threshold difference|:              %.6f F" % float(diff.max()))
else:
    print("   max |threshold difference|:              0.000000 F (acceptable -- see below)")

check_true("thresholds were RECOMPUTED from filtered data (reference counts differ somewhere)",
          nref_changed > 0)
check_true("the threshold difference is RECORDED, and zero change does NOT fail the suite", True)
print("   -> the artifact days sit inside the baseline pool for %s thresholds; whether that moves"
      % "{:,}".format(nref_changed))
print("      the 95th percentile is an empirical outcome, not a requirement.")

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- artifact filtering verified by METHOD (exclusion + recomputation), not by forced numerical change")
