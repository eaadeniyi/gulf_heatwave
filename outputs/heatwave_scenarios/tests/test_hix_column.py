"""
Plan Sec.4 / revision-5 fix: spot-check synthetic_tmax_rhmax_hi_f against
heat_index_f applied by hand; check finiteness and RH bounds; and REPORT (as an
empirical count over the observed domain, NOT assert as a universal mathematical
property) how often the envelope exceeds the afternoon-aligned Tmax+RHmin proxy.

The NWS heat-index procedure has conditional branches (a simple Steadman-style
form, the Rothfusz regression, and low/high-humidity adjustments), so monotonicity
in RH is not guaranteed across every possible input by construction -- it is
measured here, and exceptions do not fail the suite.
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hs00_config as H
sys.path.insert(0, H.PIPELINE_DIR)
from heat_index import heat_index_f

FAILS = []


def check_true(label, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", label))
    if not cond:
        FAILS.append(label)


print("=" * 78)
print("test_hix_column")
print("=" * 78)

# ---- 1. hand spot-checks: the stored column equals heat_index_f(tmax_f, rmax_pct) ----
derived_path = os.path.join(H.TABLES_DIR, "_derived_variables_TX.csv.gz")
if not os.path.exists(derived_path):
    print("   [SKIP] derived table not built -- run hs01 first")
    sys.exit(0)

d = pd.read_csv(derived_path,
                usecols=["county_fips", "date", "tmax_f", "rmax_pct", "rmin_pct",
                         "synthetic_tmax_rhmax_hi_f", "derived_tmax_rhmin_hi_proxy_f"],
                dtype={"county_fips": str})
sample = d.dropna(subset=["tmax_f", "rmax_pct", "synthetic_tmax_rhmax_hi_f"]).sample(2000, random_state=7)
recomputed = heat_index_f(sample["tmax_f"], sample["rmax_pct"])
maxdiff = float((recomputed - sample["synthetic_tmax_rhmax_hi_f"]).abs().max())
check_true("stored column == heat_index_f(tmax_f, rmax_pct) on 2000 sampled rows (max diff %.2e)" % maxdiff,
          maxdiff < 1e-9)

# ---- 2. finiteness and RH bounds ----
valid_inputs = d["tmax_f"].notna() & d["rmax_pct"].notna()
check_true("envelope is finite wherever both inputs are valid",
          bool(np.isfinite(d.loc[valid_inputs, "synthetic_tmax_rhmax_hi_f"]).all()))
rh = d["rmax_pct"].dropna()
check_true("rmax_pct within [0,100] everywhere it is present",
          bool(((rh >= 0) & (rh <= 100)).all()))
rh_min = d["rmin_pct"].dropna()
check_true("rmin_pct within [0,100] everywhere it is present",
          bool(((rh_min >= 0) & (rh_min <= 100)).all()))
both = d[["rmax_pct", "rmin_pct"]].dropna()
check_true("rmax_pct >= rmin_pct on every row where both are present (input sanity)",
          bool((both["rmax_pct"] >= both["rmin_pct"]).all()))

# ---- 3. envelope vs afternoon-aligned proxy: REPORTED empirically, not asserted ----
print()
print("-" * 78)
print("Envelope vs. Tmax+RHmin proxy -- EMPIRICAL, not asserted as a universal property")
print("-" * 78)
cmp_rows = d.dropna(subset=["synthetic_tmax_rhmax_hi_f", "derived_tmax_rhmin_hi_proxy_f"])
ge = (cmp_rows["synthetic_tmax_rhmax_hi_f"] >= cmp_rows["derived_tmax_rhmin_hi_proxy_f"])
n_total, n_ge = len(cmp_rows), int(ge.sum())
n_exceptions = n_total - n_ge
print("   rows compared:                       %s" % "{:,}".format(n_total))
print("   envelope >= afternoon proxy:         %s (%.4f%%)" % ("{:,}".format(n_ge), 100 * n_ge / n_total))
print("   exceptions (envelope < proxy):       %s (%.4f%%)" % ("{:,}".format(n_exceptions),
                                                               100 * n_exceptions / n_total))
if n_exceptions:
    ex = cmp_rows[~ge]
    print("   exception Tmax range: %.1f to %.1f F" % (ex["tmax_f"].min(), ex["tmax_f"].max()))
    print("   exception RHmax range: %.1f to %.1f %%" % (ex["rmax_pct"].min(), ex["rmax_pct"].max()))
    print("   -> reported as an empirical observation over this domain; NOT a suite failure")
else:
    print("   -> zero exceptions in this domain; still reported as empirical, not asserted universal")
check_true("this relationship is REPORTED, and the suite does not fail on exceptions", True)

# ---- 4. NWS branch behaviour recorded for representative inputs (not asserted) ----
print()
print("   heat_index_f on representative inputs (branch behaviour recorded):")
for label, t, rh_v in [("hot+humid", 95.0, 85.0), ("hot+dry", 100.0, 10.0),
                       ("warm+humid", 82.0, 95.0), ("cool", 60.0, 90.0)]:
    val = float(np.asarray(heat_index_f(pd.Series([t]), pd.Series([rh_v]))).ravel()[0])
    print("     %-12s Tmax=%5.1fF RH=%5.1f%%  ->  HI=%7.2fF" % (label, t, rh_v, val))

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- envelope column verified; monotonicity reported empirically, not assumed")
