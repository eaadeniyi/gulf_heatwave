"""
=============================================================================
s01  --  RE-RUN the two published definitions on the current code path.
=============================================================================
WHY THIS STEP EXISTS

Def 01 (MHI_P85_2D) and Def 02 (MHI_P95_2D) were published in an earlier round
(outputs/TX/def_p85_2d, def_p95_2d) by an EARLIER version of p02. Comparing
them against the 14 grid definitions as they stand would break three of the
pre-comparison conditions:

  1. only two of the four threshold windows were ever run for them
     (w15 and month; no w05, no month_pm7), so the window axis would be
     unbalanced and Figure 7 could not be drawn for them;
  2. the output SCHEMA differs -- the old event table has no event_id and no
     metric column, the old daily table has no metric_value_f -- so a common
     canonical long table cannot be built from it;
  3. the old outputs carry no recorded input fingerprint, so "same input file
     and hash" could not be demonstrated for them, only assumed.

The pre-comparison rule is: if the conditions differ, RE-RUN. So this step
re-runs both definitions at ALL FOUR windows through the current p02 into
outputs/TX/grid/MHI_P85_2D and MHI_P95_2D -- the same layout, schema and
threshold cache as the other 14 -- and then PROVES the re-run reproduces the
published results exactly on the two windows where they overlap:

    per-county-year heatwave days      exact, every county x year
    per-county-year events started     exact
    the complete event set             exact (county, start, end, duration)
    the published headline totals       exact
        Def 01 (w15): 170,894 heatwave days / 48,323 events / median 677
        Def 02 (w15):  52,786 heatwave days / 17,428 events / median 196

The original published directories are opened read-only and never modified.
If any comparison fails, this script exits non-zero and the rest of the
package must not be built on it.

Written to qa/:
    s01_legacy_rerun_verification.csv    one row per check
    s01_legacy_rerun_verification.md     the same, readable

USAGE
    python s01_rerun_legacy.py            # run what is missing, then verify
    python s01_rerun_legacy.py --force    # re-run even if outputs exist
    python s01_rerun_legacy.py --verify-only
=============================================================================
"""
import os
import sys
import json
import time
import hashlib
import argparse
import subprocess
import datetime

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defcmp_config as K
import config as C
import p02_classify_and_report as p02

STATE = K.STATE
# The published headline numbers this step defends (w15 window, statewide QA pooled).
PUBLISHED_HEADLINE = {
    "MHI_P85_2D": {"days": 170894, "events": 48323, "median": 677, "min": 154, "max": 1230},
    "MHI_P95_2D": {"days": 52786, "events": 17428, "median": 196, "min": 18, "max": 516},
}
CHECKS = []


def record(check, scope, got, want, note=""):
    ok = (str(got) == str(want))
    CHECKS.append({"check": check, "scope": scope, "result": "PASS" if ok else "FAIL",
                   "observed": got, "expected": want, "note": note})
    K.log("   [%s] %-42s %-22s got=%s expected=%s"
          % ("PASS" if ok else "FAIL", check, scope, got, want))
    return ok


def read_events(tables_dir, wkey):
    """Event table for one window, written plain (published) or gzipped (current)."""
    for name in ("heatwave_events_%s.csv" % wkey, "heatwave_events_%s.csv.gz" % wkey):
        p = os.path.join(tables_dir, name)
        if os.path.exists(p):
            return pd.read_csv(p, dtype={"county_fips": str})
    raise FileNotFoundError("no event table for window %s in %s" % (wkey, tables_dir))


def git_commit():
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=K.REPO_ROOT,
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def input_fingerprint():
    h = hashlib.md5()
    with open(C.county_day_path(STATE), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return "md5:" + h.hexdigest()[:16]


# =============================================================================
# 1. the runs to execute
# =============================================================================
def legacy_runs():
    """The 8 runs: the two re-run definitions x all four windows."""
    runs = []
    for d in K.definitions_expanded():
        if not d["rerun_required"]:
            continue
        for wkey in K.WINDOW_ORDER:
            w = C.GRID_WINDOWS[wkey]
            runs.append(dict(d,
                             run_id="%s__%s" % (d["definition_id"], wkey),
                             window_key=wkey, window_type=w["type"],
                             window_label=w["label"], window_order=w["order"],
                             user_item="published_round1_rerun",
                             baseline=C.BASELINE_SCHEME, season=C.SEASON,
                             absolute_floor="none" if C.GRID_FLOOR_F is None else str(C.GRID_FLOOR_F),
                             comparison_op=C.COMPARISON_OP,
                             analysis_years="%d-%d" % C.ANALYSIS_YEARS))
    return runs


def already_done(run):
    p = os.path.join(K.tables_dir_for(run["definition_id"]),
                     "run_summary_%s.json" % run["window_key"])
    return os.path.exists(p)


def append_run_log(summ, commit, fingerprint):
    """Append to the pipeline's own append-only provenance log.

    These 8 runs must be logged in exactly the same place and format as the 56
    grid runs, or the definition set has two provenance regimes -- which is the
    problem this whole step exists to remove. (s03's item-1 check fails if any
    definition is missing from this log.)
    """
    path = os.path.join(C.grid_root(STATE), "run_log.csv")
    row = {"logged_utc": datetime.datetime.now(datetime.timezone.utc)
           .strftime("%Y-%m-%dT%H:%M:%SZ"),
           "state": STATE, "run_id": summ["run_id"], "definition_id": summ["definition_id"],
           "def_number": summ["def_number"], "git_commit": commit,
           "input_fingerprint": fingerprint,
           "heatwave_days_QA_pooled": summ["heatwave_days_QA_pooled"],
           "heatwave_events_QA_pooled": summ["heatwave_events_QA_pooled"],
           "per_county_heatwave_days_median": summ["per_county_heatwave_days_median"],
           "runtime_seconds": summ["runtime_seconds"]}
    pd.DataFrame([row]).to_csv(path, mode="a", header=not os.path.exists(path), index=False)


def execute(runs, cd, write_daily=True, commit="unknown", fingerprint=""):
    """Run them grouped by threshold set, exactly as run_grid.py does, so each
    (metric, window) threshold pass is computed once and reused by both
    percentiles."""
    groups = {}
    for r in runs:
        groups.setdefault((r["metric"], r["window_key"]), []).append(r)
    done = []
    for (metric, wkey), grp in sorted(groups.items()):
        pctls = sorted({r["percentile"] for r in grp})
        K.log("=" * 74)
        K.log("threshold group metric=%s window=%s -> %d run(s), percentiles=%s"
              % (metric, wkey, len(grp), pctls))
        cache = {}
        p02.get_thresholds(STATE, metric, wkey, pctls, cd, cache=cache)
        for r in sorted(grp, key=lambda x: x["percentile"]):
            outdir = os.path.dirname(K.tables_dir_for(r["definition_id"]))
            os.makedirs(os.path.join(outdir, "tables"), exist_ok=True)
            os.makedirs(os.path.join(outdir, "figures"), exist_ok=True)
            summ = p02.run_one(STATE, r, cd, cache=cache, outdir=outdir,
                               write_daily=write_daily)
            append_run_log(summ, commit, fingerprint)
            done.append(summ)
        del cache
    return done


# =============================================================================
# 2. verification against the published outputs
# =============================================================================
def verify(definition_id, counties):
    """Compare the re-run against the ORIGINAL published outputs, on the two
    windows the published round actually ran."""
    pub_dir = K.published_tables_dir(definition_id)
    new_dir = K.tables_dir_for(definition_id)
    K.log("-" * 74)
    K.log("verify %s   published=%s" % (definition_id, os.path.relpath(pub_dir, K.REPO_ROOT)))

    for wkey in ("w15", "month"):
        pub_cy = pd.read_csv(os.path.join(pub_dir, "county_year_summary_%s.csv" % wkey),
                             dtype={"county_fips": str})
        new_cy = pd.read_csv(os.path.join(new_dir, "county_year_summary_%s.csv" % wkey),
                             dtype={"county_fips": str})
        m = pub_cy.merge(new_cy, on=["county_fips", "year"], how="outer",
                         suffixes=("_pub", "_new"), indicator=True)
        record("county-year keys present in both", "%s[%s]" % (definition_id, wkey),
               int((m["_merge"] != "both").sum()), 0,
               "%d county-years compared" % len(m))
        for col in ("heatwave_days", "heatwave_events_started",
                    "longest_event_duration_days", "heatwave_days_imputed"):
            a = pd.to_numeric(m[col + "_pub"], errors="coerce").fillna(0)
            b = pd.to_numeric(m[col + "_new"], errors="coerce").fillna(0)
            record("county-year exact: %s" % col, "%s[%s]" % (definition_id, wkey),
                   int((a != b).sum()), 0, "rows differing / %d" % len(m))

        pub_ev, new_ev = read_events(pub_dir, wkey), read_events(new_dir, wkey)
        key = lambda d: set(zip(d["county_fips"], d["start_date"].astype(str),
                                d["end_date"].astype(str), d["event_duration_days"]))
        sp, sn = key(pub_ev), key(new_ev)
        record("event set: published-only events", "%s[%s]" % (definition_id, wkey),
               len(sp - sn), 0, "%d published events" % len(sp))
        record("event set: rerun-only events", "%s[%s]" % (definition_id, wkey),
               len(sn - sp), 0, "%d rerun events" % len(sn))
        record("event count", "%s[%s]" % (definition_id, wkey), len(new_ev), len(pub_ev))

        if wkey == "w15":
            exp = PUBLISHED_HEADLINE[definition_id]
            per_county = (new_cy.groupby("county_fips")["heatwave_days"].sum()
                          .reindex(counties, fill_value=0))
            record("published headline: heatwave days (QA pooled)",
                   "%s[w15]" % definition_id, int(new_cy["heatwave_days"].sum()), exp["days"])
            record("published headline: heatwave events",
                   "%s[w15]" % definition_id, len(new_ev), exp["events"])
            record("published headline: per-county median days",
                   "%s[w15]" % definition_id, int("%.0f" % float(per_county.median())),
                   exp["median"], "raw median = %.1f" % float(per_county.median()))
            record("published headline: per-county min days",
                   "%s[w15]" % definition_id, int(per_county.min()), exp["min"])
            record("published headline: per-county max days",
                   "%s[w15]" % definition_id, int(per_county.max()), exp["max"])

    # the two windows that did NOT exist before must now exist
    for wkey in ("w05", "month_pm7"):
        p = os.path.join(new_dir, "run_summary_%s.json" % wkey)
        record("new window produced", "%s[%s]" % (definition_id, wkey),
               os.path.exists(p), True, "window absent from the published round")


# =============================================================================
# 3. driver
# =============================================================================
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--no-daily", action="store_true")
    args = ap.parse_args(argv)

    K.ensure_dirs()
    t0 = time.time()
    runs = legacy_runs()
    fp = input_fingerprint()
    commit = git_commit()
    K.log("=" * 74)
    K.log("s01  RE-RUN OF THE PUBLISHED DEFINITIONS ON THE CURRENT CODE PATH")
    K.log("=" * 74)
    K.log("definitions : %s" % ", ".join(sorted({r["definition_id"] for r in runs})))
    K.log("windows     : %s" % ", ".join(K.WINDOW_ORDER))
    K.log("input       : %s  (%s)" % (os.path.basename(C.county_day_path(STATE)), fp))
    K.log("git commit  : %s" % commit)

    todo = runs if args.force else [r for r in runs if not already_done(r)]
    if args.verify_only:
        todo = []
    if todo:
        K.log("executing %d of %d run(s)" % (len(todo), len(runs)))
        cd = p02.load_county_days(STATE)
        execute(todo, cd, write_daily=not args.no_daily, commit=commit, fingerprint=fp)
    else:
        K.log("all %d run(s) already on disk" % len(runs))

    counties = sorted(pd.read_csv(os.path.join(K.REPO_ROOT, "outputs", STATE,
                                               "coverage_and_imputation_report.csv"),
                                  dtype={"county_fips": str})["county_fips"].unique())
    K.log("")
    K.log("VERIFICATION against the published Def 01 / Def 02 outputs")
    for d in K.definitions_expanded():
        if d["rerun_required"]:
            verify(d["definition_id"], counties)

    df = pd.DataFrame(CHECKS)
    df.insert(0, "state", STATE)
    df["input_fingerprint"] = fp
    df["git_commit"] = commit
    df["checked_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_csv = os.path.join(K.DIR_QA, "s01_legacy_rerun_verification.csv")
    df.to_csv(out_csv, index=False)

    n_fail = int((df["result"] == "FAIL").sum())
    with open(os.path.join(K.DIR_QA, "s01_legacy_rerun_verification.md"), "w",
              encoding="utf-8") as f:
        f.write("# s01 - published-definition re-run verification\n\n")
        f.write("Def 01 (`MHI_P85_2D`) and Def 02 (`MHI_P95_2D`) were re-run through the "
                "current `p02` at all four threshold windows, then compared against the "
                "originally published outputs on the two windows the published round ran "
                "(`w15`, `month`). The published directories were read-only.\n\n")
        f.write("- input file: `outputs/%s/county_daily_heat.csv` (%s)\n" % (STATE, fp))
        f.write("- git commit: `%s`\n" % commit)
        f.write("- checks run: %d, failures: %d\n\n" % (len(df), n_fail))
        f.write("**Result: %s**\n\n" % ("PASS - the re-run reproduces the published Def 01 / "
                                        "Def 02 results exactly, so all sixteen definitions can "
                                        "be compared on one code path"
                                        if n_fail == 0 else
                                        "FAIL - the re-run does NOT reproduce the published "
                                        "results; do not build the comparison on it"))
        f.write(K.md_table(df, ["check", "scope", "result", "observed", "expected", "note"]))
        f.write("\n")
    K.log("")
    K.log("=" * 74)
    K.log("%d check(s), %d failure(s)   ->  %s" % (len(df), n_fail, out_csv))
    K.log("elapsed %.1f min" % ((time.time() - t0) / 60))
    if n_fail:
        K.log("FAIL: the re-run does not reproduce the published results.")
        return 1
    K.log("PASS: all sixteen definitions now sit on one code path, one schema, one input.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
