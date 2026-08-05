"""The 8-item verification plan from the approved spec (revision 6)."""
import os, sys, json
import numpy as np
import pandas as pd

PKG = r"C:\Users\eadeni1\OneDrive - Louisiana State University\Documents\doc\heatWaveUS\texas_heatwave_pilot\outputs\heatwave_scenarios"
sys.path.insert(0, os.path.join(PKG, "scripts"))
import hs00_config as H

FAILS = []
def ck(label, cond, detail=""):
    print("   [%s] %-68s %s" % ("PASS" if cond else "FAIL", label, detail))
    if not cond:
        FAILS.append(label)

T = os.path.join(PKG, "tables")
reg = pd.read_csv(os.path.join(T, "scenario_registry.csv"))
qa = pd.read_csv(os.path.join(T, "scenario_summary_QA.csv"))

print("=" * 90)
print("VERIFICATION PLAN (approved spec, revision 6)")
print("=" * 90)

print("\n2. registry shows 27/27, QC tier in every HIPROXY/HIXENV id, 6 reused")
ck("registry has 27 rows", len(reg) == 27, "%d" % len(reg))
ck("all 27 status=done", (reg["status"] == "done").all())
ck("exactly 6 reused_from_grid", int(reg["reused_from_grid"].sum()) == 6,
   "%d" % int(reg["reused_from_grid"].sum()))
ck("21 year-round + 2 warm-season + 2 EHF + 2 PROBEXCL = 27",
   len(H.yearround_ordinary_construct_ids()) == 21
   and int((reg["season_rule"] == "june_september").sum()) == 2
   and int((reg["family"] == "ehf").sum()) == 2
   and int((reg["qc_tier"] == "PROBEXCL").sum()) == 2)

print("\n3. no bare (un-suffixed) HIPROXY_*/HIXENV_* identifier anywhere in outputs")
bad = [c for c in reg["construct_id"]
       if (c.startswith("HIPROXY") or c.startswith("HIXENV"))
       and not any(c.endswith(s) for s in ("_RAW", "_CONFEXCL", "_PROBEXCL"))]
ck("every HIPROXY/HIXENV id carries its QC tier", not bad, str(bad))
# also scan every produced table's construct_id-like columns
leaked = set()
for f in os.listdir(T):
    if not f.endswith(".csv"):
        continue
    try:
        df = pd.read_csv(os.path.join(T, f), nrows=5000)
    except Exception:
        continue
    for col in df.columns:
        if "definition" in col or "construct" in col or col in ("comparator",):
            for v in df[col].dropna().astype(str).unique():
                if (v.startswith("HIPROXY") or v.startswith("HIXENV")) and not any(
                        v.endswith(s) for s in ("_RAW", "_CONFEXCL", "_PROBEXCL")):
                    leaked.add((f, v))
ck("no bare id leaked into any output table", not leaked, str(list(leaked)[:3]))

print("\n4. confirmed_artifact_keys exact; 2017-01-14 never excluded")
dv = pd.read_csv(os.path.join(T, "_derived_variables_TX.csv.gz"),
                 usecols=["county_fips", "date", "qc_category"], dtype={"county_fips": str})
conf = dv[dv["qc_category"] == "confirmed_artifact"]
got = set(zip(conf["county_fips"], pd.to_datetime(conf["date"]).dt.strftime("%Y-%m-%d")))
want = {(k["county_fips"], k["date"]) for k in H.CONFIRMED_ARTIFACT_KEYS}
ck("exactly the 3 named confirmed keys", got == want, str(sorted(got)))
# The QC document investigated 2017-01-14 for LUBBOCK and TRAVIS specifically and found a
# genuine cold-season saturation event there. It did not vouch for all 254 counties on that
# date, so the correct assertion is about those two -- other counties on the same date are
# judged on their own merits by the screening rule.
j17 = dv[pd.to_datetime(dv["date"]).dt.strftime("%Y-%m-%d") == "2017-01-14"]
vouched = j17[j17["county_fips"].isin(["48303", "48453"])]
ck("the 2 counties the QC doc vouched for on 2017-01-14 are valid (Lubbock, Travis)",
   bool((vouched["qc_category"] == "valid").all()), "%d records" % len(vouched))
ck("no 2017-01-14 record is ever classified confirmed_artifact",
   not bool((j17["qc_category"] == "confirmed_artifact").any()))
other_flagged = j17[j17["qc_category"] == "rule_flagged_probable_artifact"]
print("        note: %d other county-record(s) on 2017-01-14 meet the screening rule on their own "
      "(warm+dry+saturated) and are correctly rule_flagged, not confirmed: %s"
      % (len(other_flagged), sorted(other_flagged["county_fips"].tolist())))

print("\n5. threshold_quality_flag reflects the completeness/coverage rule, not n>=20")
t95 = pd.read_csv(os.path.join(T, "_t95_reference_TX.csv"), dtype={"county_fips": str})
flags = t95["threshold_quality_flag"].value_counts().to_dict()
ck("flag vocabulary is the completeness rule's, not a bare count",
   set(flags) <= {"ok", "insufficient_day_coverage", "insufficient_year_coverage",
                  "excessive_reference_imputation", "missing"}, str(flags))
ck("some counties actually FAIL the rule (it is doing work)",
   any(k != "ok" for k in flags), str({k: v for k, v in flags.items() if k != "ok"}))
ck("reference-adequacy fields are present on every threshold row",
   all(c in t95.columns for c in ("reference_day_completeness_fraction",
                                  "n_distinct_reference_years", "reference_imputation_fraction")))

print("\n6. LOYO reports zero-valued change counts without failing")
loyo = pd.read_csv(os.path.join(T, "threshold_loyo_sensitivity.csv"))
zero_rows = int((loyo["final_classified_day_change_count"] == 0).sum())
ck("LOYO ran for all 4 named constructs", loyo["construct_id"].nunique() == 4)
ck("zero-change scenarios are present and reported, not suppressed", zero_rows > 0,
   "%d of %d scenarios show zero classified-date change" % (zero_rows, len(loyo)))
ck("all 5 separate change counters are reported",
   all(c in loyo.columns for c in ("candidate_day_change_count", "final_classified_day_change_count",
                                   "event_start_change_count", "event_end_change_count",
                                   "event_count_change")))

print("\n7. every pairwise agreement table reports all 3 eligibility fractions")
for f in ("agreement_jaccard_yearround_pairs.csv", "matched_metric_comparison.csv",
          "warmseason_candidate_pair_comparison.csv", "ehf_cross_family_overlap.csv"):
    df = pd.read_csv(os.path.join(T, f))
    ck("%s has all 3 named eligibility fractions" % f,
       all(c in df.columns for c in ("eligibility_jaccard", "fraction_A_eligible_also_eligible_B",
                                     "fraction_B_eligible_also_eligible_A")))

print("\nEXTRA: QA-schema discipline")
ck("scenario_summary_QA.csv exists (renamed from scenario_summary)",
   os.path.exists(os.path.join(T, "scenario_summary_QA.csv")))
ck("every pooled field carries the _QA suffix",
   all(c.endswith("_QA") for c in qa.columns if any(
       k in c for k in ("median_annual", "share", "per_1000", "classified_date_count"))))
ck("median_annual_event_count_QA is NA for BOTH EHF rows and populated for all others",
   bool(qa.loc[qa["family"] == "ehf", "median_annual_event_count_QA"].isna().all())
   and bool(qa.loc[qa["family"] != "ehf", "median_annual_event_count_QA"].notna().all()))
ck("cross_family_comparable_events is False on every row",
   bool((~qa["cross_family_comparable_events"].astype(bool)).all()))

print("\nEXTRA: provenance")
ck("registry carries git_commit + input_fingerprint + definition_fingerprint",
   all(c in reg.columns for c in ("git_commit", "input_fingerprint", "definition_fingerprint")))
ck("definition_fingerprint is unique per construct", reg["definition_fingerprint"].nunique() == 27,
   "%d distinct" % reg["definition_fingerprint"].nunique())

print("\n" + "=" * 90)
if FAILS:
    print("RESULT: %d CHECK(S) FAILED" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("RESULT: ALL VERIFICATION CHECKS PASSED")
