"""
Plan Sec.1/7: EHF must never be combined with ordinary daily classifications
(Tmax/HIPROXY/HIXENV) in an agreement output without an explicit
ehf_date_representation field, and EHF event counts/durations must never be
presented as directly comparable to ordinary consecutive-day event counts
without cross_family_comparable_events=False being visible.

This test operates on the CONSTRUCTS registry + a stand-in "agreement output
builder" pattern: it defines the rule as a reusable checker function and
verifies it correctly PASSES well-formed outputs and FAILS malformed ones
(the actual hs05 comparison outputs are checked with this same function once
built).
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


def assert_no_unqualified_ehf_in_agreement(df, construct_id_cols=("definition_A", "definition_B")):
    """The rule under test: any row referencing an EHF construct_id in an agreement
    table must carry a populated ehf_date_representation field. Raises AssertionError
    (mirroring how a real test-suite gate would fail the build) if violated."""
    ehf_ids = {c["construct_id"] for c in H.CONSTRUCTS if c["family"] == "ehf"}
    for col in construct_id_cols:
        if col not in df.columns:
            continue
        involves_ehf = df[col].isin(ehf_ids)
        if involves_ehf.any():
            if "ehf_date_representation" not in df.columns:
                raise AssertionError("EHF construct present in %s but no ehf_date_representation column exists" % col)
            missing = involves_ehf & df["ehf_date_representation"].isna()
            if missing.any():
                raise AssertionError("%d row(s) reference an EHF construct in %s without "
                                     "ehf_date_representation populated" % (int(missing.sum()), col))
    return True


print("=" * 78)
print("test_ehf_comparison_semantics")
print("=" * 78)

ehf_id = "EHF_TX_FIXED7914"
tmax_id = "TMAX_P85_D3_W15"

# ---- 1. a WELL-FORMED table (EHF row carries ehf_date_representation) passes ----
good = pd.DataFrame({
    "definition_A": [tmax_id, ehf_id],
    "definition_B": ["HIPROXY_P95_D2_W15_CONFEXCL", tmax_id],
    "ehf_date_representation": [pd.NA, "assessment_date_jaccard"],
})
try:
    assert_no_unqualified_ehf_in_agreement(good)
    check_true("well-formed table (EHF row has ehf_date_representation) passes", True)
except AssertionError as e:
    check_true("well-formed table (EHF row has ehf_date_representation) passes -- %s" % e, False)

# ---- 2. a MALFORMED table (EHF present, no ehf_date_representation column at all) fails ----
bad_no_col = pd.DataFrame({
    "definition_A": [tmax_id, ehf_id],
    "definition_B": ["HIPROXY_P95_D2_W15_CONFEXCL", tmax_id],
})
raised = False
try:
    assert_no_unqualified_ehf_in_agreement(bad_no_col)
except AssertionError:
    raised = True
check_true("malformed table (no ehf_date_representation column at all) is correctly REJECTED", raised)

# ---- 3. a MALFORMED table (column exists but is null on the EHF row) fails ----
bad_null = pd.DataFrame({
    "definition_A": [tmax_id, ehf_id],
    "definition_B": ["HIPROXY_P95_D2_W15_CONFEXCL", tmax_id],
    "ehf_date_representation": [pd.NA, pd.NA],   # present but empty exactly where EHF appears
})
raised = False
try:
    assert_no_unqualified_ehf_in_agreement(bad_null)
except AssertionError:
    raised = True
check_true("malformed table (ehf_date_representation null on the EHF row) is correctly REJECTED", raised)

# ---- 4. a table with NO EHF rows at all passes trivially, column or not ----
no_ehf = pd.DataFrame({
    "definition_A": [tmax_id], "definition_B": ["HIPROXY_P95_D2_W15_CONFEXCL"],
})
try:
    assert_no_unqualified_ehf_in_agreement(no_ehf)
    check_true("table with no EHF rows at all passes even without the column", True)
except AssertionError:
    check_true("table with no EHF rows at all passes even without the column", False)

# ---- 5. cross_family_comparable_events is False for every EHF construct in the registry ----
ehf_constructs = [c for c in H.CONSTRUCTS if c["family"] == "ehf"]
check_true("every EHF construct in the registry has cross_family_comparable_events=False",
          all(c["cross_family_comparable_events"] is False for c in ehf_constructs))
check_true("every NON-EHF construct also has cross_family_comparable_events=False "
          "(no family claims cross-family-comparable events in this package)",
          all(c["cross_family_comparable_events"] is False for c in H.CONSTRUCTS))

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- the EHF/ordinary comparison-semantics gate works correctly")
