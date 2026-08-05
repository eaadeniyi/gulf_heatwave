"""
Plan Sec.6 blocking fix: the Jaccard denominator is the UNION OF POSITIVE
CLASSIFICATIONS within the pairwise-common eligible universe -- NOT the size of
that universe. Also verifies the three named eligibility fractions and the
NA-on-empty-union convention.
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hs00_config as H
import hs05_comparison as hs05

FAILS = []


def check_true(label, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", label))
    if not cond:
        FAILS.append(label)


print("=" * 78)
print("test_common_eligibility_calendar")
print("=" * 78)

# ---- 1. synthetic, fully hand-checkable case ----
# universe: keys 1..10 eligible for A; 5..14 eligible for B  -> U = {5..10}, |U| = 6
# A classifies {5,6,7,20}; B classifies {6,7,8,20}
#   within U: A = {5,6,7}, B = {6,7,8}
#   both = {6,7} = 2 ; either = 3 + 3 - 2 = 4 ; jaccard = 2/4 = 0.5
#   NOTE |U| = 6, so a denominator of |U| would give 2/6 = 0.333 -- the wrong answer
#   this test exists to catch.
eligible = {"A": np.arange(1, 11), "B": np.arange(5, 15)}
classified = {"A": np.array([5, 6, 7, 20]), "B": np.array([6, 7, 8, 20])}
m = hs05.pair_metrics("A", "B", eligible, classified)

check_true("n_common_eligible_dates == 6 (the universe |U|)", m["n_common_eligible_dates"] == 6)
check_true("n_classified_by_A within U == 3", m["n_classified_by_A"] == 3)
check_true("n_classified_by_B within U == 3", m["n_classified_by_B"] == 3)
check_true("n_classified_by_both == 2", m["n_classified_by_both"] == 2)
check_true("n_classified_by_either == 4 (union identity: 3+3-2)", m["n_classified_by_either"] == 4)
check_true("jaccard == 2/4 == 0.5 (union of POSITIVES, not |U|)",
          abs(m["jaccard_common_eligibility"] - 0.5) < 1e-12)
check_true("jaccard is NOT 2/|U| == 0.3333 (the formula error this test guards against)",
          abs(m["jaccard_common_eligibility"] - (2.0 / 6.0)) > 1e-6)
check_true("classifications OUTSIDE the common universe (key 20) are excluded from both sides",
          m["n_classified_by_A"] == 3 and m["n_classified_by_B"] == 3)

# ---- 2. the union identity holds exactly ----
check_true("union identity: either == A + B - both",
          m["n_classified_by_either"] == m["n_classified_by_A"] + m["n_classified_by_B"] - m["n_classified_by_both"])

# ---- 3. the three named eligibility fractions ----
# |EA|=10, |EB|=10, |U|=6, |EA union EB| = |{1..14}| = 14
check_true("eligibility_jaccard == 6/14", abs(m["eligibility_jaccard"] - 6.0 / 14.0) < 1e-6)
check_true("fraction_A_eligible_also_eligible_B == 6/10",
          abs(m["fraction_A_eligible_also_eligible_B"] - 0.6) < 1e-9)
check_true("fraction_B_eligible_also_eligible_A == 6/10",
          abs(m["fraction_B_eligible_also_eligible_A"] - 0.6) < 1e-9)

# ---- 4. NA (not 0, not 1) when neither side classifies anything in the universe ----
eligible2 = {"A": np.arange(1, 11), "B": np.arange(5, 15)}
classified2 = {"A": np.array([100]), "B": np.array([200])}   # nothing inside U
m2 = hs05.pair_metrics("A", "B", eligible2, classified2)
check_true("empty positive union -> n_classified_by_either == 0", m2["n_classified_by_either"] == 0)
check_true("empty positive union -> jaccard is NA (never silently 0 or 1)",
          pd.isna(m2["jaccard_common_eligibility"]))

# ---- 5. against the REAL outputs: the identity holds on every produced pair ----
print()
print("-" * 78)
print("Verifying the identity on every real pairwise row produced by hs05")
print("-" * 78)
for fname in ("agreement_jaccard_yearround_pairs.csv", "matched_metric_comparison.csv",
              "warmseason_candidate_pair_comparison.csv", "ehf_cross_family_overlap.csv"):
    p = os.path.join(H.TABLES_DIR, fname)
    if not os.path.exists(p):
        print("   [SKIP] %s not built yet" % fname)
        continue
    df = pd.read_csv(p)
    ident = (df["n_classified_by_either"] ==
             df["n_classified_by_A"] + df["n_classified_by_B"] - df["n_classified_by_both"])
    check_true("%s: union identity holds on all %d rows" % (fname, len(df)), bool(ident.all()))

    nonzero = df["n_classified_by_either"] > 0
    recomputed = df.loc[nonzero, "n_classified_by_both"] / df.loc[nonzero, "n_classified_by_either"]
    match = np.isclose(recomputed, df.loc[nonzero, "jaccard_common_eligibility"], atol=1e-6)
    check_true("%s: jaccard == both/either on all %d non-empty rows" % (fname, int(nonzero.sum())),
              bool(match.all()))

    zero = df["n_classified_by_either"] == 0
    if zero.any():
        check_true("%s: jaccard is NA wherever the positive union is empty (%d rows)"
                  % (fname, int(zero.sum())),
                  bool(df.loc[zero, "jaccard_common_eligibility"].isna().all()))

    # the denominator must never equal the universe size (unless coincidentally equal)
    wrong = np.isclose(df["jaccard_common_eligibility"].fillna(-1),
                       (df["n_classified_by_both"] / df["n_common_eligible_dates"].replace(0, np.nan)).fillna(-1),
                       atol=1e-9) & (df["n_classified_by_either"] != df["n_common_eligible_dates"])
    check_true("%s: jaccard is NOT both/|U| anywhere (the formula error)" % fname, not bool(wrong.any()))

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- Jaccard denominator is the positive union; eligibility fractions correct")
