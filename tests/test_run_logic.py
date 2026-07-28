"""Part J, Step 23: the 6 mandated test sequences, plus 2 extra tests for the
year-boundary configurable this pilot added. Run against the exact same
build_runs_and_events() function used on real data (heatwave_run_logic.py).
"""
import os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from heatwave_run_logic import build_runs_and_events

FAILS = []


def make_df(candidate_seq, start="2023-07-01"):
    dates = pd.date_range(start, periods=len(candidate_seq))
    return pd.DataFrame({"date": dates, "county_fips": "48201", "candidate_day_flag": candidate_seq})


def check(name, candidate_seq, expected_heatwave, expected_n_events=None, expected_durations=None, **kwargs):
    df = build_runs_and_events(make_df(candidate_seq), **kwargs)
    got_hw = df["heatwave_day_flag"].tolist()
    ok = got_hw == expected_heatwave
    msg = "PASS" if ok else "FAIL"
    if not ok:
        FAILS.append(name)
    print("[%s] %-45s seq=%s -> heatwave=%s (expected %s)" % (msg, name, candidate_seq, got_hw, expected_heatwave))
    if expected_n_events is not None:
        n_events = df.loc[df["heatwave_day_flag"] == 1, "run_id"].nunique()
        ok2 = n_events == expected_n_events
        if not ok2:
            FAILS.append(name + " [n_events]")
        print("       %s n_events=%d (expected %d)" % ("PASS" if ok2 else "FAIL", n_events, expected_n_events))
    if expected_durations is not None:
        durations = (df.loc[df["heatwave_day_flag"] == 1]
                       .groupby("run_id")["event_duration_days"].first().tolist())
        ok3 = sorted(durations) == sorted(expected_durations)
        if not ok3:
            FAILS.append(name + " [durations]")
        print("       %s durations=%s (expected %s)" % ("PASS" if ok3 else "FAIL", durations, expected_durations))
    return df


print("=" * 75)
print("Part J unit tests (spec Step 23)")
print("=" * 75)

# Test 1: 1,1,1,0 -> one event, duration 3, heatwave flags 1,1,1,0
check("Test1: 1,1,1,0 -> one 3-day event", [1, 1, 1, 0],
      [1, 1, 1, 0], expected_n_events=1, expected_durations=[3])

# Test 2: 1,1,0 -> one event, duration 2
check("Test2: 1,1,0 -> one 2-day event", [1, 1, 0],
      [1, 1, 0], expected_n_events=1, expected_durations=[2])

# Test 3: 1,0,1 -> zero events, two isolated candidates
check("Test3: 1,0,1 -> zero events (isolated candidates)", [1, 0, 1],
      [0, 0, 0], expected_n_events=0)

# Test 4: 1,NA,1 -> missing day breaks run, zero events
check("Test4: 1,NA,1 -> missing day breaks run", [1, np.nan, 1],
      [0, 0, 0], expected_n_events=0)

# Test 5: 1,1,1,0,1,1 -> two events, durations 3 and 2, five heatwave days
df5 = check("Test5: 1,1,1,0,1,1 -> two events (3,2)", [1, 1, 1, 0, 1, 1],
            [1, 1, 1, 0, 1, 1], expected_n_events=2, expected_durations=[3, 2])
n_hw_days = df5["heatwave_day_flag"].sum()
ok = n_hw_days == 5
print("       %s five heatwave days total: got %d" % ("PASS" if ok else "FAIL", n_hw_days))
if not ok:
    FAILS.append("Test5 [total heatwave days]")

# Test 6: season-boundary candidate days (May31=1, Jun1=1) -- current config has
# restrict_to_season=False (no season boundary configured), so the documented
# "configured boundary rule" for THIS pilot is simply: no break. If season
# restriction is turned on later (open config item), this test must be rerun
# with that rule wired in.
df6 = make_df([1, 1], start="2023-05-31")
df6 = build_runs_and_events(df6)
print("[INFO ] Test6: May31=1,Jun1=1 under current config (no season restriction configured)"
      " -> heatwave=%s (expected [1,1], i.e. continues -- season restriction is OFF per config)"
      % df6["heatwave_day_flag"].tolist())
if df6["heatwave_day_flag"].tolist() != [1, 1]:
    FAILS.append("Test6")

# Extra test (not in the mandated 6, but this pilot's year_boundary_breaks_run
# configurable needs its own check): Dec31=1, Jan1=1
dfyb_off = build_runs_and_events(make_df([1, 1], start="2023-12-31"), year_boundary_breaks_run=False)
dfyb_on = build_runs_and_events(make_df([1, 1], start="2023-12-31"), year_boundary_breaks_run=True)
print("[EXTRA] Dec31=1,Jan1=1  year_boundary_breaks_run=False -> heatwave=%s (expect [1,1], one event)"
      % dfyb_off["heatwave_day_flag"].tolist())
print("[EXTRA] Dec31=1,Jan1=1  year_boundary_breaks_run=True  -> heatwave=%s (expect [0,0], two isolated candidates)"
      % dfyb_on["heatwave_day_flag"].tolist())
if dfyb_off["heatwave_day_flag"].tolist() != [1, 1]:
    FAILS.append("Extra-year-boundary-off")
if dfyb_on["heatwave_day_flag"].tolist() != [0, 0]:
    FAILS.append("Extra-year-boundary-on")

# Extra: verify event_id format + onset/continuation/final flags match spec's
# worked Monday/Tuesday/Wednesday example exactly
dfw = build_runs_and_events(make_df([1, 1, 1], start="2023-07-10"), definition_id="HI85_2D", state_fips="48")
onset = dfw["event_onset_flag"].tolist()
cont = dfw["event_continuation_flag"].tolist()
final = dfw["event_final_day_flag"].tolist()
daynum = dfw["event_day_number"].tolist()
print("[EXTRA] 3-day event onset=%s cont=%s final=%s day_number=%s" % (onset, cont, final, daynum))
print("        (spec's worked example: onset=[1,0,0] cont=[0,1,1] final=[0,0,1] day_number=[1,2,3])")
if onset != [1, 0, 0] or cont != [0, 1, 1] or final != [0, 0, 1] or daynum != [1.0, 2.0, 3.0]:
    FAILS.append("Extra-onset-continuation-final")
eid = dfw["event_id"].iloc[0]
print("        event_id example: %s" % eid)

print("\n" + "=" * 75)
if FAILS:
    print("RESULT: %d FAILURE(S): %s" % (len(FAILS), FAILS))
    sys.exit(1)
else:
    print("RESULT: ALL TESTS PASSED")
