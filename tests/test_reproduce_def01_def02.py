"""
REGRESSION GATE for the generalised p02.

p02 was generalised from "the daily-mean heat index at one percentile" to
"any metric x percentile x duration x window" so it could run the definition
grid. That refactor is only safe if the generalised code still produces the
PUBLISHED Definition 01 / Definition 02 results bit for bit.

This test re-runs Def 01 (85th) and Def 02 (95th) through the new code into a
scratch directory (the published outputs are never touched) and compares against
outputs/TX/def_p85_2d and def_p95_2d:

  * per-county-year heatwave DAYS      -- exact, every county x year
  * per-county-year events started     -- exact
  * the EVENT set (county, start, end, duration) -- exact
  * the documented headline totals     -- exact

Published headline numbers being defended (w15 window, statewide QA pooled):
      Def 01 : 170,894 heatwave days / 48,323 events / per-county median 677
      Def 02 :  52,786 heatwave days / 17,428 events / per-county median 196

Run:  python tests/test_reproduce_def01_def02.py
"""
import os, sys, shutil, tempfile
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))
import config as C
import p02_classify_and_report as p02

STATE = "TX"
# documented headline values from FINDINGS_STATEWIDE.md / HANDOFF.md (w15 window)
PUBLISHED = {
    85: {"days": 170894, "events": 48323, "median": 677, "min": 154, "max": 1230},
    95: {"days": 52786, "events": 17428, "median": 196, "min": 18, "max": 516},
}
FAILS = []


def check(label, got, want):
    ok = (got == want)
    print("   [%s] %-46s got=%-9s expected=%-9s" % ("PASS" if ok else "FAIL", label, got, want))
    if not ok:
        FAILS.append(label)
    return ok


def read_events(tables_dir, wkey):
    """Event table for one window, whether it was written plain or gzipped."""
    for name in ("heatwave_events_%s.csv" % wkey, "heatwave_events_%s.csv.gz" % wkey):
        p = os.path.join(tables_dir, name)
        if os.path.exists(p):
            return pd.read_csv(p, dtype={"county_fips": str})
    raise FileNotFoundError("no event table for window %s in %s" % (wkey, tables_dir))


def compare_frames(label, new, old, keys, value_cols):
    """Exact comparison of two summary tables on the given value columns."""
    m = old.merge(new, on=keys, how="outer", suffixes=("_old", "_new"), indicator=True)
    only = m["_merge"] != "both"
    if only.any():
        print("   [FAIL] %s: %d key(s) present in only one table" % (label, int(only.sum())))
        print(m[only].head(10).to_string())
        FAILS.append(label + " [keys]")
        return
    for c in value_cols:
        a = pd.to_numeric(m[c + "_old"], errors="coerce").fillna(0)
        b = pd.to_numeric(m[c + "_new"], errors="coerce").fillna(0)
        n_diff = int((a != b).sum())
        ok = n_diff == 0
        print("   [%s] %s :: %-28s %d/%d rows differ" %
              ("PASS" if ok else "FAIL", label, c, n_diff, len(m)))
        if not ok:
            FAILS.append("%s [%s]" % (label, c))
            d = m.loc[a != b, keys + [c + "_old", c + "_new"]]
            print(d.head(10).to_string())


print("=" * 78)
print("REGRESSION: generalised p02 must reproduce published Def 01 / Def 02")
print("=" * 78)

scratch = tempfile.mkdtemp(prefix="def_repro_")
print("scratch output dir: %s" % scratch)
cd = p02.load_county_days(STATE)
cache = {}

try:
    for pctl in (85, 95):
        print("\n" + "-" * 78)
        print("Definition %02d  --  %dth percentile daily-mean heat index, >=2 days"
              % (1 if pctl == 85 else 2, pctl))
        print("-" * 78)
        outdir = os.path.join(scratch, "def_p%d_2d" % pctl)
        os.makedirs(os.path.join(outdir, "tables"), exist_ok=True)
        p02.run_state_percentile(STATE, pctl, cd=cd, cache=cache, outdir=outdir, write_daily=False)

        pub_dir = os.path.join(C.OUTPUT_ROOT, STATE, "def_p%d_2d" % pctl, "tables")
        new_dir = os.path.join(outdir, "tables")

        for wkey in C.LEGACY_WINDOWS:
            print("\n  window = %s" % wkey)
            # ---- county-year summary: exact per-county-year comparison ----------
            pub_cy = pd.read_csv(os.path.join(pub_dir, "county_year_summary_%s.csv" % wkey),
                                 dtype={"county_fips": str})
            new_cy = pd.read_csv(os.path.join(new_dir, "county_year_summary_%s.csv" % wkey),
                                 dtype={"county_fips": str})
            compare_frames("county_year[%s]" % wkey, new_cy, pub_cy,
                           keys=["county_fips", "year"],
                           value_cols=["heatwave_days", "heatwave_events_started",
                                       "longest_event_duration_days", "heatwave_days_imputed"])

            # ---- the event set itself -------------------------------------------
            # The PUBLISHED event tables are plain .csv; p02 now gzips them (the
            # grid's 56 runs would otherwise dominate the repo). Accept either, so
            # this gate keeps comparing the event sets across that format change.
            pub_ev = read_events(pub_dir, wkey)
            new_ev = read_events(new_dir, wkey)
            pk = lambda d: set(zip(d["county_fips"], d["start_date"].astype(str),
                                   d["end_date"].astype(str), d["event_duration_days"]))
            sp, sn = pk(pub_ev), pk(new_ev)
            check("event set identical [%s]" % wkey, (len(sp - sn), len(sn - sp)), (0, 0))
            check("event count [%s]" % wkey, len(new_ev), len(pub_ev))

            # ---- headline totals -------------------------------------------------
            if wkey == "w15":
                exp = PUBLISHED[pctl]
                check("pooled heatwave days [w15]", int(new_cy["heatwave_days"].sum()), exp["days"])
                check("pooled events [w15]", len(new_ev), exp["events"])
                # reindex over ALL counties so counties with zero heatwave days
                # (absent from the county-year table) still count toward the median
                all_counties = sorted(cd["county_fips"].unique())
                per_county = (new_cy.groupby("county_fips")["heatwave_days"].sum()
                              .reindex(all_counties, fill_value=0))
                med = float(per_county.median())
                # the published medians were reported with "%.0f" formatting; with an
                # even county count the median can land on .5, so match that rounding
                # rather than truncating (Def 02 is exactly 195.5 -> "196")
                check("per-county median heatwave days [w15] (raw=%.1f)" % med,
                      int("%.0f" % med), exp["median"])
                check("per-county min heatwave days [w15]", int(per_county.min()), exp["min"])
                check("per-county max heatwave days [w15]", int(per_county.max()), exp["max"])
finally:
    shutil.rmtree(scratch, ignore_errors=True)

print("\n" + "=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S) -- the refactor changed published results" % len(FAILS))
    for f in FAILS[:25]:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: PASS -- generalised p02 reproduces Def 01 and Def 02 exactly")
