"""
=============================================================================
run_package.py  --  build the whole definition-comparison package, in order.
=============================================================================
    s01_rerun_legacy.py     re-run Def 01/02 on the current code path and PROVE
                            they reproduce the published results        (~2 min)
    s02_canonical_long.py   the canonical long table + every aggregation (~3 min)
    s03_validate.py         the ten pre-comparison validation items      (~1 min)
    s04_tables.py           the eight required tables + support tables   (~1 min)
    s05_core_figures.py     Figures 1-7, 11, 12                          (~1 min)
    s06_county_profiles.py  Figure 8: 254 county report cards            (~7 min)
    s07_event_audits.py     Figures 9-10: timelines and the long-event audit
    s08_report.py           captions, methods notes, decision table, manifest

Each step is independently runnable and each writes its own log to stdout.
s01-s04 must run in order (each consumes the previous step's output); s05-s08
only need s04.

A step that exits non-zero STOPS the build: s01 and s03 are gates, and the
comparison must not be assembled on definitions that failed verification.

USAGE
    python run_package.py                 # everything
    python run_package.py --from s05      # from one step onward
    python run_package.py --only s03 s04
    python run_package.py --dry-run
=============================================================================
"""
import os
import sys
import time
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    ("s01", "s01_rerun_legacy.py", "re-run and verify the published definitions", True),
    ("s02", "s02_canonical_long.py", "canonical long table + aggregations", True),
    ("s03", "s03_validate.py", "pre-comparison validation (gate)", True),
    ("s04", "s04_tables.py", "the eight required tables", True),
    ("s05", "s05_core_figures.py", "core figures 1-7, 11, 12", False),
    ("s06", "s06_county_profiles.py", "figure 8: county report cards", False),
    ("s07", "s07_event_audits.py", "figures 9-10: event audits", False),
    ("s08", "s08_report.py", "captions, methods, decision table, manifest", False),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default=None, help="first step, e.g. s05")
    ap.add_argument("--only", nargs="+", default=None, help="run just these steps")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    steps = STEPS
    if args.only:
        steps = [s for s in STEPS if s[0] in set(args.only)]
    elif args.start:
        keys = [s[0] for s in STEPS]
        if args.start not in keys:
            sys.exit("unknown step %r (choose from %s)" % (args.start, ", ".join(keys)))
        steps = STEPS[keys.index(args.start):]

    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        env.setdefault(v, "1")

    print("=" * 74, flush=True)
    print("DEFINITION-COMPARISON PACKAGE  --  %d step(s)" % len(steps), flush=True)
    print("=" * 74, flush=True)
    t0 = time.time()
    for key, script, label, is_gate in steps:
        print("\n" + "#" * 74, flush=True)
        print("# %s  %s%s" % (key, label, "   [GATE]" if is_gate else ""), flush=True)
        print("#" * 74, flush=True)
        if args.dry_run:
            continue
        t1 = time.time()
        rc = subprocess.call([sys.executable, os.path.join(HERE, script)], env=env)
        print("--> %s finished rc=%d in %.1f min" % (key, rc, (time.time() - t1) / 60),
              flush=True)
        if rc != 0 and is_gate:
            print("\nSTOPPING: %s is a gate and it failed. The comparison must not be "
                  "built on unverified definitions." % key, flush=True)
            return rc
        if rc != 0:
            print("WARNING: %s failed (rc=%d) but is not a gate; continuing." % (key, rc),
                  flush=True)
    print("\n" + "=" * 74, flush=True)
    print("PACKAGE BUILD COMPLETE in %.1f min" % ((time.time() - t0) / 60), flush=True)
    print("read: DECISION_TABLE.md, then figure_captions.md, then methods_notes.md",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
