"""
Plan Sec.6/7: fails if anything labeled a "metric comparison" pairs constructs
that differ in percentile or duration, and enforces the structural separations:
EHF never inside the 21x21 matrix, year-round never mixed with warm-season,
and every EHF comparison row carrying ehf_date_representation.
"""
import os, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hs00_config as H

FAILS = []


def check_true(label, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", label))
    if not cond:
        FAILS.append(label)


print("=" * 78)
print("test_matched_comparison_labeling")
print("=" * 78)

meta = {c["construct_id"]: c for c in H.CONSTRUCTS}

# ---- 1. every pair in MATCHED_METRIC_PAIRS really is matched ----
for a, b in H.MATCHED_METRIC_PAIRS:
    ca, cb = meta[a], meta[b]
    check_true("%s vs %s: percentile matched (%s == %s)" % (a, b, ca["percentile"], cb["percentile"]),
              ca["percentile"] == cb["percentile"])
    check_true("%s vs %s: min_duration matched (%s == %s)" % (a, b, ca["min_duration"], cb["min_duration"]),
              ca["min_duration"] == cb["min_duration"])
    check_true("%s vs %s: window matched (%s == %s)" % (a, b, ca["window"], cb["window"]),
              ca["window"] == cb["window"])
    check_true("%s vs %s: season matched" % (a, b), ca["season_rule"] == cb["season_rule"])
    check_true("%s vs %s: METRIC genuinely differs (that is the axis under test)" % (a, b),
              ca["metric"] != cb["metric"])

# ---- 2. the prespecified asymmetric pair must NOT be presentable as metric-isolating ----
a, b = H.PRESPECIFIED_ASYMMETRIC_PAIR
ca, cb = meta[a], meta[b]
differs = sum([ca["metric"] != cb["metric"], ca["percentile"] != cb["percentile"],
               ca["min_duration"] != cb["min_duration"]])
check_true("PRESPECIFIED_ASYMMETRIC_PAIR differs on >1 axis (so it is correctly NOT a metric test)",
          differs > 1)

# ---- 3. the real matched_metric_comparison.csv carries the non-overreach disclaimer ----
p = os.path.join(H.TABLES_DIR, "matched_metric_comparison.csv")
if os.path.exists(p):
    df = pd.read_csv(p)
    check_true("matched_metric_comparison.csv records matched_on", "matched_on" in df.columns)
    check_true("matched_metric_comparison.csv limits the metric-isolating claim to daily classification",
              "metric_isolating_claim" in df.columns and
              df["metric_isolating_claim"].astype(str).str.contains("daily classification").all())
    # every row's two constructs must be matched on the non-metric axes
    for _, r in df.iterrows():
        ca, cb = meta[r["definition_A"]], meta[r["definition_B"]]
        check_true("row %s vs %s is matched on percentile+duration+window"
                  % (r["definition_A"], r["definition_B"]),
                  ca["percentile"] == cb["percentile"] and ca["min_duration"] == cb["min_duration"]
                  and ca["window"] == cb["window"])

# ---- 4. EHF is absent from the 21x21 matrix, and warm-season is too ----
p = os.path.join(H.TABLES_DIR, "agreement_jaccard_yearround_pairs.csv")
if os.path.exists(p):
    df = pd.read_csv(p)
    ehf_ids = {c["construct_id"] for c in H.CONSTRUCTS if c["family"] == "ehf"}
    junsep_ids = {c["construct_id"] for c in H.CONSTRUCTS if c["season_rule"] == "june_september"}
    probexcl_ids = {c["construct_id"] for c in H.CONSTRUCTS if c.get("qc_tier") == "PROBEXCL"}
    involved = set(df["definition_A"]) | set(df["definition_B"])
    check_true("21x21 matrix contains NO EHF construct", not (involved & ehf_ids))
    check_true("21x21 matrix contains NO warm-season construct (eligibility periods differ)",
              not (involved & junsep_ids))
    check_true("21x21 matrix contains NO PROBEXCL sensitivity construct", not (involved & probexcl_ids))
    check_true("21x21 matrix involves exactly the 21 year-round ordinary constructs",
              involved == set(H.yearround_ordinary_construct_ids()))

# ---- 5. every EHF comparison row carries ehf_date_representation ----
p = os.path.join(H.TABLES_DIR, "ehf_cross_family_overlap.csv")
if os.path.exists(p):
    df = pd.read_csv(p)
    check_true("ehf_cross_family_overlap.csv has an ehf_date_representation column",
              "ehf_date_representation" in df.columns)
    if "ehf_date_representation" in df.columns:
        check_true("every EHF overlap row has ehf_date_representation populated (%d rows)" % len(df),
                  bool(df["ehf_date_representation"].notna().all()))
        check_true("every EHF overlap row carries the 3-day-period interpretation note",
                  bool(df["interpretation_note"].astype(str).str.contains("3-day").all()))

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- matched comparisons genuinely matched; EHF and warm-season correctly separated")
