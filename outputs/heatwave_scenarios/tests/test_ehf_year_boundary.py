"""
Plan Sec.1 boundary handling: the 3-day and 30-day rolling windows must continue
across Dec31->Jan1 without resetting "by county-year", and a January analysis
date must correctly use the prior November-December DMT.
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hs01_derive_variables as hs01

FAILS = []


def check_true(label, cond):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", label))
    if not cond:
        FAILS.append(label)


def make_synthetic_county(tmean_f_seq, start, fips="99999"):
    dates = pd.date_range(start, periods=len(tmean_f_seq))
    return pd.DataFrame({
        "county_fips": fips, "county_name": "Synthetic", "date": dates,
        "year": dates.year, "month": dates.month, "day": dates.day,
        "tmax_f": np.nan, "tmin_f": np.nan, "tmean_f": tmean_f_seq,
        "rmax_pct": 50.0, "rmin_pct": 30.0, "prcp_in": 0.0,
        "derived_tmean_meanrh_hi_f": np.nan, "derived_tmax_rhmin_hi_proxy_f": np.nan,
        "temp_imputed": False, "rh_imputed": False, "qc_rh_pin_likely_artifact": False,
    })


print("=" * 78)
print("test_ehf_year_boundary")
print("=" * 78)

# 80 days spanning Nov 15 -> Feb 2 (crosses two year boundaries: 2020->2021).
# A distinctive value in December lets us confirm it's actually pulled into a
# January 3-day/30-day window rather than the window resetting at Jan 1.
start = "2020-11-15"
n = 80
seq = [60.0] * n
dates = pd.date_range(start, periods=n)
# mark Dec 20-22 with a distinctive temperature
dec_mask = (dates.month == 12) & (dates.day.isin([20, 21, 22]))
seq = np.array(seq, dtype=float)
seq[dec_mask] = 95.0
cd = make_synthetic_county(seq.tolist(), start)

out = hs01.add_ehf_components(cd)
out = out.sort_values("date").reset_index(drop=True)

# a January date whose disjoint 30-day window (i-32..i-3) should reach back into
# the marked December days
jan_target = pd.Timestamp("2021-01-14")   # 30-day window i-32..i-3 -> spans back to ~Dec 13-Dec 12
row = out[out["date"] == jan_target].iloc[0]
check_true("Jan 14 2021's dmt_3day_mean_c is not NaN (window continues across the year boundary)",
          pd.notna(row["dmt_3day_mean_c"]))
check_true("Jan 14 2021's dmt_prior30_mean_c is not NaN (30-day window crosses Dec31->Jan1 cleanly)",
          pd.notna(row["dmt_prior30_mean_c"]))

# does the prior-30-day window for a date that reaches back to the Dec 20-22 spike
# actually reflect it? Compare a date whose window [i-32,i-3] includes the spike
# index against one whose window is entirely before it -- computed programmatically
# from the actual index positions, not guessed calendar dates, to get the arithmetic right.
spike_idx = int(np.flatnonzero(dec_mask)[0])   # first spike day's position in the sequence
# window [i-32, i-3] includes spike_idx  <=>  i-32 <= spike_idx <= i-3  <=>  spike_idx+3 <= i <= spike_idx+32
i_includes = spike_idx + 10                      # comfortably inside that range
i_excludes = spike_idx - 3                       # window [i-35, i-6], strictly before the spike
assert i_excludes >= 32, "test setup needs i_excludes >= 32 for a full 30-day window"
date_includes = dates[i_includes]
date_excludes = dates[i_excludes]
r_in = out[out["date"] == date_includes].iloc[0]
r_out = out[out["date"] == date_excludes].iloc[0]
print("   (spike at index %d; includes-window date=%s window=[%d,%d]; excludes-window date=%s window=[%d,%d])"
      % (spike_idx, date_includes.date(), i_includes - 32, i_includes - 3,
         date_excludes.date(), i_excludes - 32, i_excludes - 3))
check_true("a date whose 30-day window spans the Dec spike reads HIGHER than one whose window doesn't",
          pd.notna(r_in["dmt_prior30_mean_c"]) and pd.notna(r_out["dmt_prior30_mean_c"])
          and r_in["dmt_prior30_mean_c"] > r_out["dmt_prior30_mean_c"])

# independent recomputation for a couple of cross-boundary dates: does the pandas
# rolling result match a by-hand slice of the Celsius series?
dmt_c_all = (np.array(seq, dtype=float) - 32.0) * 5.0 / 9.0
for target in [pd.Timestamp("2021-01-01"), pd.Timestamp("2021-01-14"), pd.Timestamp("2021-02-01")]:
    idx = (dates == target).argmax()
    if idx < 32:
        continue
    expected_3 = dmt_c_all[idx - 2:idx + 1].mean()
    expected_30 = dmt_c_all[idx - 32:idx - 2].mean()
    r = out[out["date"] == target].iloc[0]
    ok3 = abs(r["dmt_3day_mean_c"] - expected_3) < 1e-9
    ok30 = abs(r["dmt_prior30_mean_c"] - expected_30) < 1e-9
    check_true("date=%s: 3-day window matches by-hand slice across the year boundary" % target.date(), ok3)
    check_true("date=%s: 30-day window matches by-hand slice across the year boundary" % target.date(), ok30)

print()
print("=" * 78)
if FAILS:
    print("RESULT: %d FAILURE(S)" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
else:
    print("RESULT: ALL PASSED -- rolling windows correctly cross the Dec31->Jan1 boundary")
