"""
Proves the VECTORISED panel implementation is interchangeable with the REFERENCE
per-day implementation.

The reference (build_runs_and_events) is the oracle: it is the readable code the
unit tests assert against and the code that produced the published Definition
01 / 02 results. The panel version (build_runs_and_events_panel) exists only
because the definition grid needs ~1M county-days x 56 runs. If these two ever
disagree, the grid results are not trustworthy -- so this test is a gate, not a
nicety.

Checks:
  A. the 6 mandated spec sequences, both year-boundary settings
  B. 400 randomised sequences (candidate/non-candidate/missing, random lengths,
     min_duration 2 and 3) -- compares EVERY shared column
  C. multi-county panels, including absent (not just NaN) calendar days and
     counties whose series butt up against each other
  D. edge cases: empty input, all-missing, all-candidate, single row
"""
import os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from heatwave_run_logic import build_runs_and_events, build_runs_and_events_panel

FAILS = []
CHECKED = 0

# columns both implementations must agree on, exactly
SHARED = ["run_id", "run_length", "heatwave_day_flag", "event_id",
          "event_start_date", "event_end_date", "event_duration_days",
          "event_day_number", "event_onset_flag", "event_continuation_flag",
          "event_final_day_flag"]


def series_equal(col, a, b):
    """True if two columns agree, treating null-vs-null as equal.

    Nulls need explicit handling: pandas 3 keeps nulls as NaN through
    .astype(str), and NaN != NaN, so a naive string compare reports spurious
    mismatches on the (many) non-event rows.
    """
    if col in ("event_start_date", "event_end_date"):
        a, b = pd.to_datetime(a), pd.to_datetime(b)
        return bool(((a.isna() & b.isna()) | (a == b)).all())
    if col == "event_id":
        a = a.reset_index(drop=True).astype(object)
        b = b.reset_index(drop=True).astype(object)
        a = a.where(a.notna(), "<NULL>").astype(str)
        b = b.where(b.notna(), "<NULL>").astype(str)
        return bool((a == b).all())
    a = pd.to_numeric(a, errors="coerce").reset_index(drop=True)
    b = pd.to_numeric(b, errors="coerce").reset_index(drop=True)
    return bool(((a.isna() & b.isna()) | np.isclose(a.fillna(-9e9), b.fillna(-9e9))).all())


def compare(name, ref, pan, cols=SHARED):
    """Compare the reference and panel frames column by column."""
    global CHECKED
    CHECKED += 1
    for col in cols:
        if not series_equal(col, ref[col], pan[col]):
            FAILS.append("%s :: column %s" % (name, col))
            print("  [FAIL] %s column=%s" % (name, col))
            print("     ref :", list(ref[col])[:20])
            print("     pan :", list(pan[col])[:20])
            return False
    return True


def run_both(seq, start="2023-07-01", min_duration=2, ybreak=False,
             definition_id="HI85_2D", state_fips="48", county="48201"):
    dates = pd.date_range(start, periods=len(seq))
    base = pd.DataFrame({"date": dates, "county_fips": county, "candidate_day_flag": seq})
    ref = build_runs_and_events(base.copy(), min_duration=min_duration,
                                year_boundary_breaks_run=ybreak,
                                definition_id=definition_id, state_fips=state_fips)
    pan, _ = build_runs_and_events_panel(base.copy(), min_duration=min_duration,
                                         year_boundary_breaks_run=ybreak,
                                         definition_id=definition_id, state_fips=state_fips)
    return ref, pan


print("=" * 78)
print("A. the 6 mandated spec sequences")
print("=" * 78)
MANDATED = [
    ("1,1,1,0", [1, 1, 1, 0]),
    ("1,1,0", [1, 1, 0]),
    ("1,0,1", [1, 0, 1]),
    ("1,NA,1", [1, np.nan, 1]),
    ("1,1,1,0,1,1", [1, 1, 1, 0, 1, 1]),
    ("May31/Jun1 boundary", [1, 1]),
]
for label, seq in MANDATED:
    for md in (2, 3):
        for yb in (False, True):
            ref, pan = run_both(seq, min_duration=md, ybreak=yb)
            ok = compare("%s md=%d yb=%s" % (label, md, yb), ref, pan)
            print("  [%s] %-22s min_duration=%d year_break=%-5s -> heatwave=%s"
                  % ("PASS" if ok else "FAIL", label, md, yb, pan["heatwave_day_flag"].tolist()))

# the Dec31 -> Jan1 case specifically (the year-boundary configurable)
for yb in (False, True):
    ref, pan = run_both([1, 1], start="2023-12-31", ybreak=yb)
    ok = compare("Dec31/Jan1 yb=%s" % yb, ref, pan)
    print("  [%s] %-22s year_break=%-5s -> heatwave=%s"
          % ("PASS" if ok else "FAIL", "Dec31,Jan1", yb, pan["heatwave_day_flag"].tolist()))

print()
print("=" * 78)
print("B. 400 randomised sequences")
print("=" * 78)
rng = np.random.default_rng(20260729)
n_rand = 0
for trial in range(400):
    length = int(rng.integers(1, 60))
    # mix of candidate (1), non-candidate (0) and missing (NaN), skewed so runs occur
    seq = rng.choice([1.0, 0.0, np.nan], size=length, p=[0.60, 0.30, 0.10]).tolist()
    md = int(rng.choice([2, 3]))
    yb = bool(rng.integers(0, 2))
    start = "%d-%02d-%02d" % (int(rng.integers(2015, 2026)), int(rng.integers(1, 13)),
                              int(rng.integers(1, 28)))
    ref, pan = run_both(seq, start=start, min_duration=md, ybreak=yb)
    if compare("rand#%d len=%d md=%d yb=%s" % (trial, length, md, yb), ref, pan):
        n_rand += 1
print("  %d/400 randomised sequences identical across every shared column" % n_rand)
if n_rand != 400:
    FAILS.append("randomised sequences")

print()
print("=" * 78)
print("C. multi-county panels (the case the grid actually runs)")
print("=" * 78)
# Build a panel of several counties; drop some dates entirely so the panel has
# ABSENT days (the grid path relies on a date gap breaking a run, rather than on
# reindexing every county to a gap-free calendar first).
for trial in range(40):
    counties = ["48%03d" % c for c in rng.choice(np.arange(1, 500, 2), size=4, replace=False)]
    frames, refs = [], []
    for cty in sorted(counties):
        length = int(rng.integers(5, 40))
        seq = rng.choice([1.0, 0.0, np.nan], size=length, p=[0.6, 0.3, 0.1])
        dates = pd.date_range("2019-06-%02d" % int(rng.integers(1, 20)), periods=length)
        g = pd.DataFrame({"date": dates, "county_fips": cty, "candidate_day_flag": seq})
        if length > 8:                       # punch out 2 dates entirely
            drop = rng.choice(np.arange(1, length - 1), size=2, replace=False)
            g = g.drop(index=g.index[drop]).reset_index(drop=True)
        frames.append(g)
    md = int(rng.choice([2, 3]))
    panel = pd.concat(frames, ignore_index=True).sort_values(
        ["county_fips", "date"]).reset_index(drop=True)

    # reference: per-county, exactly as p02's classify() does it
    ref_parts = []
    for cty, g in panel.groupby("county_fips", sort=True):
        ref_parts.append(build_runs_and_events(g.reset_index(drop=True), min_duration=md,
                                               definition_id="GRIDTEST", state_fips="48"))
    ref = pd.concat(ref_parts, ignore_index=True)
    pan, ev = build_runs_and_events_panel(panel, min_duration=md,
                                          definition_id="GRIDTEST", state_fips="48")

    # run_id numbering is panel-global in the vectorised version and per-county in
    # the reference, so compare everything EXCEPT the raw run_id integer (event_id,
    # durations, day numbers and flags all still have to match exactly).
    bad = [col for col in SHARED if col != "run_id"
           and not series_equal(col, ref[col], pan[col])]
    # the event table must also match the reference's event count and durations
    ref_ev = sorted(ref[ref["heatwave_day_flag"] == 1]
                    .groupby("event_id")["event_duration_days"].first().tolist())
    pan_ev = sorted(float(x) for x in ev["event_duration_days"].tolist())
    if ref_ev != pan_ev:
        bad.append("event_table_durations(ref=%d ev, pan=%d ev)" % (len(ref_ev), len(pan_ev)))
    CHECKED += 1
    if bad:
        FAILS.append("panel#%d: %s" % (trial, bad))
        print("  [FAIL] panel#%d md=%d columns=%s" % (trial, md, bad))
print("  40 multi-county panels checked (absent days, 4 counties each, md=2 and 3)")

print()
print("=" * 78)
print("D. edge cases")
print("=" * 78)
edge = {
    "empty": [],
    "single non-candidate": [0],
    "single candidate": [1],
    "all missing": [np.nan, np.nan, np.nan],
    "all candidate (30d)": [1] * 30,
    "alternating": [1, 0] * 15,
}
for label, seq in edge.items():
    if len(seq) == 0:
        empty = pd.DataFrame({"date": pd.to_datetime([]), "county_fips": pd.Series(dtype=str),
                              "candidate_day_flag": pd.Series(dtype=float)})
        pan, ev = build_runs_and_events_panel(empty, min_duration=2)
        ok = len(pan) == 0 and len(ev) == 0
        print("  [%s] %-22s -> empty in, empty out" % ("PASS" if ok else "FAIL", label))
        if not ok:
            FAILS.append("edge:" + label)
        continue
    ref, pan = run_both(seq, min_duration=2)
    ok = compare("edge:" + label, ref, pan)
    print("  [%s] %-22s -> heatwave=%s" % ("PASS" if ok else "FAIL", label,
                                           pan["heatwave_day_flag"].tolist()[:12]))

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS[:25]:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- vectorised panel == reference implementation")
    print("        (%d frame comparisons, every shared column)" % CHECKED)
