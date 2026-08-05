"""
Plan Sec.2 / reuse rule: the 6 reused Tmax cells must reconcile EXACTLY against
outputs/TX/grid/, on normalized event properties (county, start, end, duration)
and the county-year table -- NOT on literal event-ID strings, which legitimately
use different prefixes across packages.
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hs00_config as H
import hs02_classify as hs02

FAILS = []


def check_true(label, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", label))
    if not cond:
        FAILS.append(label)


print("=" * 78)
print("test_reconcile_reused_tmax")
print("=" * 78)

reused = [c for c in H.CONSTRUCTS if c["reused_from_grid"]]
print("reused constructs: %d" % len(reused))
check_true("exactly 6 constructs are marked reused_from_grid", len(reused) == 6)

for c in reused:
    cid = c["construct_id"]
    tdir = os.path.join(H.construct_dir(cid, make=False), "tables")

    # package copy
    pkg_cy = pd.read_csv(os.path.join(tdir, "county_year_summary.csv"), dtype={"county_fips": str})
    pkg_ev = pd.read_csv(os.path.join(tdir, "heatwave_events.csv.gz"), dtype={"county_fips": str})

    # authoritative source, re-read directly from outputs/TX/grid/
    src_cy, src_cm, src_ev, fp = hs02.reuse_tmax_construct(c)

    # ---- county-year table: exact on every value column ----
    keys = ["county_fips", "year"]
    valcols = [col for col in ("heatwave_days", "heatwave_events_started",
                               "longest_event_duration_days", "heatwave_days_imputed")
               if col in src_cy.columns and col in pkg_cy.columns]
    m = src_cy.merge(pkg_cy, on=keys, how="outer", suffixes=("_src", "_pkg"), indicator=True)
    check_true("%s: county-year keys identical (no rows on only one side)" % cid,
              bool((m["_merge"] == "both").all()))
    for col in valcols:
        a = pd.to_numeric(m[col + "_src"], errors="coerce").fillna(-999)
        b = pd.to_numeric(m[col + "_pkg"], errors="coerce").fillna(-999)
        check_true("%s: county-year %s identical (%d rows)" % (cid, col, len(m)), bool((a == b).all()))

    # ---- event set: normalized properties, NOT literal event ids ----
    def norm_events(df):
        return set(zip(df["county_fips"].astype(str),
                       pd.to_datetime(df["start_date"]).astype(str),
                       pd.to_datetime(df["end_date"]).astype(str),
                       pd.to_numeric(df["event_duration_days"]).astype(int)))
    s_src, s_pkg = norm_events(src_ev), norm_events(pkg_ev)
    check_true("%s: event set identical on (county, start, end, duration) -- %d events, "
              "0 src-only, 0 pkg-only" % (cid, len(s_src)),
              (len(s_src - s_pkg) == 0) and (len(s_pkg - s_src) == 0))

    # ---- fingerprint provenance is recorded, not just assumed ----
    import json
    fp_path = os.path.join(tdir, "reuse_fingerprint.json")
    check_true("%s: reuse_fingerprint.json exists" % cid, os.path.exists(fp_path))
    if os.path.exists(fp_path):
        with open(fp_path) as f:
            saved = json.load(f)
        check_true("%s: fingerprint records reused_without_recalculation=True" % cid,
                  saved.get("reused_without_recalculation") is True)
        check_true("%s: fingerprint's recorded source hash still matches the live source file" % cid,
                  saved.get("source_events_hash") == fp["source_events_hash"])

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- all 6 reused Tmax cells reconcile exactly against outputs/TX/grid/")
