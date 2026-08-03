"""
=============================================================================
run_revision  --  the whole revision, in the prescribed execution order.
=============================================================================
    1  reproduce the existing pipeline                     r01
    2  audit terminology and units                         r01 (inventories)
    3  temperature sanity checks                           r02
    4  correct the period aggregation                      r03
    5  trend sensitivity                                   r04
    6  external benchmarking                               r05
    7  construct families and eligibility denominators     r06
    8  agreement, gates, rates, geography                   r07
    9  long-event audit and data-quality sensitivity        r08
   10  regenerate E2-E4 and the new Part 1 figures          r09
   11  regenerate E5-E9 and the new Part 2 figures          r10
   12  the consolidated QA suite                            r11
   13  dictionary, registry, manifests, final report        r12

The run STOPS at the first step that fails, including a blocking QA failure.
It does not continue by dropping failed records or changing assumptions.
=============================================================================
"""
import os
import sys
import time
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K

STEPS = [
    ("r01_reproduce_audit", "Stage 1: reproduce and audit the existing pipeline"),
    ("r02_temperature_panel", "Stage 2: county temperature panel and sanity checks"),
    ("r03_period_aggregation", "Stages 3-4: equal-county period aggregation"),
    ("r04_trends", "Stage 5: descriptive trend sensitivity"),
    ("r05_benchmark", "Stage 6: external benchmarking"),
    ("r06_events", "Stages 7-8: construct families and denominators"),
    ("r07_agreement_and_gates", "agreement, absolute gates, rates, geography"),
    ("r08_audits", "Stages 15-16: long-event audit and data-quality sensitivity"),
    ("r09_figures_part1", "revised figures E2-E4 and R1-R4"),
    ("r10_figures_part2", "revised figures E5-E9 and R5-R10"),
    ("r11_qa_tests", "the consolidated QA suite (blocking)"),
    ("r12_report", "dictionary, registry, manifests, final report"),
]


def main(argv=None):
    only = set(argv or [])
    t0 = time.time()
    K.log("#" * 78)
    K.log("# EXTREME-TEMPERATURE REVISION v2")
    K.log("# %s" % K.PANEL_SENTENCE)
    K.log("#" * 78)
    done = []
    for i, (mod, what) in enumerate(STEPS, 1):
        if only and mod not in only:
            continue
        K.log("")
        K.log(">" * 78)
        K.log("> STEP %d/%d  %s  --  %s" % (i, len(STEPS), mod, what))
        K.log(">" * 78)
        t = time.time()
        m = importlib.import_module(mod)
        rc = m.main()
        if rc not in (0, None):
            K.log("!! %s returned %r - stopping" % (mod, rc))
            return 1
        done.append((mod, round((time.time() - t) / 60.0, 2)))
    K.log("")
    K.log("#" * 78)
    K.log("# COMPLETE in %.1f minutes" % ((time.time() - t0) / 60))
    for mod, mins in done:
        K.log("#   %-28s %5.2f min" % (mod, mins))
    K.log("#" * 78)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except K.BlockingQAFailure as e:
        K.log("")
        K.log("!" * 78)
        K.log("! BLOCKING QA FAILURE - the revision stops here rather than continuing")
        K.log("! %s" % e)
        K.log("!" * 78)
        sys.exit(2)
