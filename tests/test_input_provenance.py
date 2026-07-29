"""
PROVENANCE GATE — the classification input really is derived from the raw sources.

The classification steps (p02 onward) read outputs/<ST>/county_daily_heat.csv rather
than the raw GHCN / gridMET files, and the definition grid reuses that table instead
of re-running p01 for each of its 56 runs. That shortcut is only legitimate if
re-deriving the table from the original sources reproduces it exactly.

This test re-runs p01 from
    data/raw/gulf_states/<ST>/weather/ghcn_county_day_weather_<ST>.csv     (Tmax/Tmin/precip)
    data/raw/gulf_states/<ST>/weather/gridmet_county_day_humidity_<ST>.csv (RHmax/RHmin)
into a temporary directory and compares byte-for-byte against the table the pipeline
actually consumes. It also checks that the table spans the full baseline period, so the
walk-forward thresholds are estimated from the source record rather than a truncated copy.

Run it when the raw inputs may have changed, or to re-establish provenance for a set of
published results:   python tests/test_input_provenance.py

Takes ~1 minute per state (p01 rebuild + hashing a ~700 MB file).
"""
import os, sys, time, hashlib, shutil, tempfile
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))
import config as C

FAILS = []


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def check(label, got, want):
    ok = (got == want)
    print("   [%s] %-52s %s" % ("PASS" if ok else "FAIL", label, got))
    if not ok:
        print("          expected: %s" % (want,))
        FAILS.append(label)
    return ok


def verify_state(state):
    print("=" * 78)
    print("INPUT PROVENANCE — %s" % state)
    print("=" * 78)
    consumed = C.county_day_path(state)
    for label, p in (("GHCN (temperature)", C.ghcn_path(state)),
                     ("gridMET (humidity)", C.gridmet_path(state))):
        if not os.path.exists(p):
            print("   [SKIP] %s missing: %s" % (label, p))
            return
        print("   source  %-20s %7.0f MB  %s" % (label, os.path.getsize(p) / 1e6, p))
    if not os.path.exists(consumed):
        print("   [SKIP] no county-day table to verify (run p01 first)")
        return
    print("   consumed by the pipeline: %s (%.0f MB)"
          % (consumed, os.path.getsize(consumed) / 1e6))
    print()

    # ---- the table must cover the whole baseline period ---------------------
    span = pd.read_csv(consumed, usecols=["date"])
    yr_min, yr_max = int(span["date"].str[:4].min()), int(span["date"].str[:4].max())
    print("   table spans %d..%d (%d county-days)" % (yr_min, yr_max, len(span)))
    check("baseline start present (%d)" % C.BASELINE_START, yr_min, C.BASELINE_START)
    check("analysis end present (%d)" % C.ANALYSIS_YEARS[1], yr_max, C.ANALYSIS_YEARS[1])
    del span
    print()

    # ---- rebuild from the raw sources and compare --------------------------
    scratch = tempfile.mkdtemp(prefix="p01_provenance_")
    try:
        real_root = C.OUTPUT_ROOT
        C.OUTPUT_ROOT = scratch                      # redirect p01's output
        import p01_build_countyday_idw as p01
        print("   rebuilding from the raw sources ...")
        t0 = time.time()
        p01.build_state(state)
        print("   rebuild took %.1f min" % ((time.time() - t0) / 60))
        rebuilt = os.path.join(scratch, state, "county_daily_heat.csv")
        C.OUTPUT_ROOT = real_root

        print()
        a, b = md5(consumed), md5(rebuilt)
        print("   md5 consumed : %s" % a)
        print("   md5 rebuilt  : %s" % b)
        check("rebuild from GHCN + gridMET is byte-identical", a == b, True)
    finally:
        C.OUTPUT_ROOT = real_root
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", action="append", default=None)
    a = ap.parse_args()
    for st in (a.state or C.STATES):
        verify_state(st)
        print()

    print("=" * 78)
    if FAILS:
        print("RESULT: %d FAILURE(S) — the consumed input is NOT what the raw sources produce" % len(FAILS))
        for f in FAILS:
            print("   -", f)
        sys.exit(1)
    else:
        print("RESULT: PASS — the classification input is exactly what re-deriving from")
        print("        GHCN + gridMET produces, over the full baseline period")
