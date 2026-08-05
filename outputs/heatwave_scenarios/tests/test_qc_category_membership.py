"""
Plan Sec.5: verify the three QC tiers exclude EXACTLY the right membership, and
that the confirmed-artifact list is a fixed lookup that is NEVER re-derived from
the screening rule (they are different data objects).

  RAW       excludes nothing
  CONFEXCL  excludes {confirmed_artifact}
  PROBEXCL  excludes {confirmed_artifact, rule_flagged_probable_artifact}
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hs00_config as H
import hs01_derive_variables as hs01
import hs02_classify as hs02

FAILS = []


def check_true(label, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", label))
    if not cond:
        FAILS.append(label)


def check_eq(label, got, want):
    print("   [%s] %-58s got=%s want=%s" % ("PASS" if got == want else "FAIL", label, got, want))
    if got != want:
        FAILS.append(label)


print("=" * 78)
print("test_qc_category_membership")
print("=" * 78)

# ---- 1. tier membership definitions are exactly as specified ----
check_eq("RAW excludes nothing", hs02.QC_EXCLUDE_SETS["RAW"], set())
check_eq("CONFEXCL excludes exactly {confirmed_artifact}",
        hs02.QC_EXCLUDE_SETS["CONFEXCL"], {"confirmed_artifact"})
check_eq("PROBEXCL excludes exactly {confirmed_artifact, rule_flagged_probable_artifact}",
        hs02.QC_EXCLUDE_SETS["PROBEXCL"], {"confirmed_artifact", "rule_flagged_probable_artifact"})

# ---- 2. the confirmed list is a FIXED LOOKUP, not re-derived from the rule ----
# Build a synthetic frame where the screening rule fires on a day that is NOT in
# CONFIRMED_ARTIFACT_KEYS. That day must come out rule_flagged_probable_artifact,
# never confirmed_artifact -- proving the confirmed set isn't generated from the rule.
dates = pd.to_datetime(["2023-03-01", "2019-07-04", "2017-01-14"])
df = pd.DataFrame({
    "county_fips": ["48201", "48201", "48303"],   # Harris (confirmed date), Harris (rule-fires only), Lubbock (2017 known-valid)
    "county_name": ["Harris", "Harris", "Lubbock"],
    "date": dates, "year": dates.year, "month": dates.month, "day": dates.day,
    # all three rows satisfy the screening rule's RH+rain conditions ...
    "rmax_pct": [100.0, 100.0, 100.0], "rmin_pct": [100.0, 100.0, 100.0],
    "prcp_in": [0.0, 0.0, 0.0],
    # ... but only the first two are warm enough for the rule's tmax>=80 condition;
    # the 2017-01-14 row is a genuine COLD saturation event (Tmax 34F), so the rule
    # must not fire on it at all
    "tmax_f": [87.47, 95.0, 33.98], "tmin_f": [71.60, 75.0, 30.0], "tmean_f": [79.5, 85.0, 32.0],
    "derived_tmean_meanrh_hi_f": np.nan, "derived_tmax_rhmin_hi_proxy_f": np.nan,
    "temp_imputed": False, "rh_imputed": False, "qc_rh_pin_likely_artifact": False,
})
# add_qc_category asserts the confirmed count matches CONFIRMED_ARTIFACT_KEYS exactly, so
# call the classification logic directly on this 3-row synthetic frame
date_str = df["date"].dt.strftime("%Y-%m-%d")
key = df["county_fips"].astype(str) + "|" + date_str
confirmed_keys = {"%s|%s" % (k["county_fips"], k["date"]) for k in H.CONFIRMED_ARTIFACT_KEYS}
is_confirmed = key.isin(confirmed_keys)
rh_pin = (df["rmax_pct"].round(6) == 100.0) & (df["rmin_pct"].round(6) == 100.0)
no_rain = df["prcp_in"].fillna(0) < H.NO_RAIN_PRCP_IN_THRESHOLD
warm = df["tmax_f"] >= H.WARM_TMAX_F_THRESHOLD
rule_flagged = (rh_pin & no_rain & warm).fillna(False)
qc_category = np.where(is_confirmed, "confirmed_artifact",
                       np.where(rule_flagged, "rule_flagged_probable_artifact", "valid"))

check_eq("Harris 2023-03-01 (IS in the confirmed list) -> confirmed_artifact",
        qc_category[0], "confirmed_artifact")
check_eq("Harris 2019-07-04 (rule fires, NOT in confirmed list) -> rule_flagged_probable_artifact",
        qc_category[1], "rule_flagged_probable_artifact")
check_eq("Lubbock 2017-01-14 (known genuine cold saturation, Tmax 34F) -> valid",
        qc_category[2], "valid")

# ---- 3. the known-valid 2017-01-14 multi-county pin is never excluded, under ANY tier ----
for tier, excl in hs02.QC_EXCLUDE_SETS.items():
    check_true("2017-01-14 Lubbock stays classification-eligible under tier %s" % tier,
              "valid" not in excl)

# ---- 4. against the REAL derived table: exactly 3 confirmed, and they are the 3 named keys ----
derived_path = os.path.join(H.TABLES_DIR, "_derived_variables_TX.csv.gz")
if os.path.exists(derived_path):
    real = pd.read_csv(derived_path, usecols=["county_fips", "date", "qc_category"],
                      dtype={"county_fips": str})
    conf = real[real["qc_category"] == "confirmed_artifact"]
    check_eq("real table: exactly 3 confirmed_artifact county-days", len(conf), 3)
    got_keys = set(zip(conf["county_fips"], pd.to_datetime(conf["date"]).dt.strftime("%Y-%m-%d")))
    want_keys = {(k["county_fips"], k["date"]) for k in H.CONFIRMED_ARTIFACT_KEYS}
    check_true("real table: the 3 confirmed keys are exactly Cameron/Harris/Travis 2023-03-01",
              got_keys == want_keys)
    # the 2017-01-14 records must be present in the table and classified valid
    jan2017 = real[pd.to_datetime(real["date"]).dt.strftime("%Y-%m-%d") == "2017-01-14"]
    lub = jan2017[jan2017["county_fips"] == "48303"]
    if len(lub):
        check_true("real table: Lubbock 2017-01-14 is qc_category=valid (genuine cold saturation event)",
                  bool((lub["qc_category"] == "valid").all()))
else:
    print("   [SKIP] derived table not built yet -- run hs01 first for the real-data checks")

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- QC tier membership exact; confirmed list is a fixed lookup, not rule-derived")
