"""
STATEWIDE (all 254 Texas counties) -- county-day table with IDW gap-filling.

Extends the 5-county pilot's county-day build (step01) to every Texas county,
adding inverse-distance-weighted (IDW) spatial imputation of MISSING temperature
(and the handful of missing RH cells) from surrounding counties, per user
instruction ("Inverse Distance Weighting ... surrounding county ... center of
the county").

IDW method (Shepard, power=2): for a county-date whose value is missing, the
imputed value is  sum_i w_i v_i / sum_i w_i  over all counties i that HAVE a
valid value that date, with w_i = 1 / d_i^2 and d_i = planar distance between
county CENTROIDS (EPSG:5070 CONUS Albers, metres). Distant counties get ~0
weight, so this is effectively local. EVERY imputed county-day is flagged
(temp_imputed / rh_imputed) so interpolated values never pass as observed.

Confirmed RH-clip artifacts (RH pinned at 100 on warm dry days) are FLAGGED
here (qc_rh_pin_likely_artifact) and handled at classification time (set to
missing), NOT imputed -- consistent with the pilot.

Output:
  tables/statewide_county_daily_heat.csv   (LARGE; git-ignored)
  tables/coverage_and_imputation_report.csv (per-county coverage + imputed counts)
"""
import os, sys, time
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import geopandas as gpd

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "gulf_eda", "scripts"))
from eda_util import heat_index_f

W_DIR = os.path.join(ROOT, "data", "raw", "gulf_states", "TX", "weather")
SHP = os.path.join(ROOT, "data", "raw", "census", "county_shapefile", "tl_2020_us_county.shp")
OUT = os.path.abspath(os.path.join(HERE, "..", "tables"))
os.makedirs(OUT, exist_ok=True)
BASE_START, AN0, AN1 = 1979, 2015, 2025


def log(*a):
    print(*a, flush=True)


t0 = time.time()
log("=" * 72)
log("STATEWIDE build: 254 TX counties, county-day table with IDW gap-fill")
log("=" * 72)

# ---------------------------------------------------------------- load
t = pd.read_csv(os.path.join(W_DIR, "ghcn_county_day_weather_TX.csv"),
                usecols=["county_fips", "county_name", "date", "tmax_f", "tmin_f", "prcp_in"],
                dtype={"county_fips": str})
h = pd.read_csv(os.path.join(W_DIR, "gridmet_county_day_humidity_TX.csv"),
                usecols=["county_fips", "date", "rmax_pct", "rmin_pct"], dtype={"county_fips": str})
t["county_fips"] = t["county_fips"].str.zfill(5)
h["county_fips"] = h["county_fips"].str.zfill(5)
cd = t.merge(h, on=["county_fips", "date"], how="outer")
cd["date"] = pd.to_datetime(cd["date"], errors="coerce")
cd = cd.dropna(subset=["date"])
cd = cd[(cd["date"].dt.year >= BASE_START) & (cd["date"].dt.year <= AN1)].copy()
cd["year"] = cd["date"].dt.year
cd["month"] = cd["date"].dt.month
cd["day"] = cd["date"].dt.day
log("[load] %d county-days, %d counties, %s..%s" %
    (len(cd), cd["county_fips"].nunique(), cd["date"].min().date(), cd["date"].max().date()))

# ---------------------------------------------------------------- hard QC (null impossible values) + flags
cd["qc_tmax_lt_tmin"] = (cd["tmax_f"] < cd["tmin_f"]).fillna(False)
cd.loc[cd["qc_tmax_lt_tmin"], ["tmax_f", "tmin_f"]] = np.nan
cd["qc_rh_oob"] = (((cd["rmax_pct"] < 0) | (cd["rmax_pct"] > 100)) |
                   ((cd["rmin_pct"] < 0) | (cd["rmin_pct"] > 100))).fillna(False)
cd.loc[cd["qc_rh_oob"], ["rmax_pct", "rmin_pct"]] = np.nan
_prcp = cd["prcp_in"].fillna(0)
cd["qc_rh_pin_likely_artifact"] = (((cd["rmax_pct"].round(6) == 100.0) & (cd["rmin_pct"].round(6) == 100.0))
                                   & (_prcp < 0.01) & (cd["tmax_f"] >= 80)).fillna(False)

# ---------------------------------------------------------------- centroids + IDW weight matrix
log("[centroids] building EPSG:5070 centroid IDW weights ...")
gdf = gpd.read_file(SHP)
gdf = gdf[gdf["STATEFP"] == "48"].to_crs(5070)
cent = pd.DataFrame({"county_fips": gdf["GEOID"].values,
                     "cx": gdf.geometry.centroid.x.values,
                     "cy": gdf.geometry.centroid.y.values})
NAME_MAP = dict(zip(gdf["GEOID"].values, gdf["NAME"].values))
# backfill county names for counties that had no rows in the source temp file
cd["county_name"] = cd["county_fips"].map(NAME_MAP).fillna(cd["county_name"])
counties = sorted(cd["county_fips"].unique())
cent = cent.set_index("county_fips").reindex(counties)
XY = cent[["cx", "cy"]].values                                   # (n,2) metres
n = len(counties)
dx = XY[:, 0][:, None] - XY[:, 0][None, :]
dy = XY[:, 1][:, None] - XY[:, 1][None, :]
dist = np.sqrt(dx * dx + dy * dy)
with np.errstate(divide="ignore"):
    W = 1.0 / (dist ** 2)
np.fill_diagonal(W, 0.0)                                         # no self-weight
log("   %d counties; centroid pairwise distances %.0f..%.0f km" %
    (n, np.nanmin(dist[dist > 0]) / 1000, dist.max() / 1000))

# full date x county grid, aligned to `counties` order
dates = pd.date_range(cd["date"].min(), cd["date"].max(), freq="D")
cidx = {c: j for j, c in enumerate(counties)}
didx = {d: i for i, d in enumerate(dates)}


def idw_fill(varname):
    """Return (filled_values_long, imputed_mask_long) aligned to cd rows."""
    piv = cd.pivot_table(index="date", columns="county_fips", values=varname, aggfunc="first")
    piv = piv.reindex(index=dates, columns=counties)
    V = piv.values.astype(float)                                # (ndates, n)
    M = (~np.isnan(V)).astype(float)
    V0 = np.where(np.isnan(V), 0.0, V)
    num = (V0 * M) @ W                                          # (ndates, n)
    den = M @ W
    with np.errstate(invalid="ignore", divide="ignore"):
        imp = num / den
    missing = np.isnan(V)
    filled = np.where(missing, imp, V)
    imputed = missing & np.isfinite(imp)
    # map back to cd rows
    rows_i = cd["date"].map(didx).values
    cols_j = cd["county_fips"].map(cidx).values
    return filled[rows_i, cols_j], imputed[rows_i, cols_j]


log("[idw] imputing tmax_f, tmin_f, rmax_pct, rmin_pct ...")
tmax_f, tmax_imp = idw_fill("tmax_f")
tmin_f, tmin_imp = idw_fill("tmin_f")
rmax_pct, rmax_imp = idw_fill("rmax_pct")
rmin_pct, rmin_imp = idw_fill("rmin_pct")
cd["temp_imputed"] = tmax_imp | tmin_imp
cd["rh_imputed"] = rmax_imp | rmin_imp
cd["tmax_f"] = tmax_f
cd["tmin_f"] = tmin_f
cd["rmax_pct"] = rmax_pct
cd["rmin_pct"] = rmin_pct
log("   imputed temperature county-days: %d (%.2f%%) | imputed RH: %d"
    % (int(cd["temp_imputed"].sum()), 100 * cd["temp_imputed"].mean(), int(cd["rh_imputed"].sum())))

# ---------------------------------------------------------------- derived metrics (post-fill)
cd["tmean_f"] = (cd["tmax_f"] + cd["tmin_f"]) / 2.0
cd["rh_mean_pct"] = (cd["rmax_pct"] + cd["rmin_pct"]) / 2.0
cd["derived_tmean_meanrh_hi_f"] = heat_index_f(cd["tmean_f"], cd["rh_mean_pct"])
cd["derived_tmax_rhmin_hi_proxy_f"] = heat_index_f(cd["tmax_f"], cd["rmin_pct"])

cd["qc_status"] = np.select(
    [cd["qc_tmax_lt_tmin"] | cd["qc_rh_oob"],
     cd["derived_tmean_meanrh_hi_f"].isna(),
     cd["qc_rh_pin_likely_artifact"]],
    ["invalid_physical", "missing_input", "suspicious_retain"], default="valid")

keep = ["county_fips", "county_name", "date", "year", "month", "day",
        "tmax_f", "tmin_f", "tmean_f", "prcp_in", "rmax_pct", "rmin_pct", "rh_mean_pct",
        "derived_tmean_meanrh_hi_f", "derived_tmax_rhmin_hi_proxy_f",
        "temp_imputed", "rh_imputed", "qc_rh_pin_likely_artifact", "qc_status"]
cd[keep].to_csv(os.path.join(OUT, "statewide_county_daily_heat.csv"), index=False)
log("[done] wrote statewide_county_daily_heat.csv rows=%d (%.0fs)" % (len(cd), time.time() - t0))

# ---------------------------------------------------------------- coverage/imputation report
an = cd[(cd["year"] >= AN0) & (cd["year"] <= AN1)]
rep = an.groupby("county_fips").agg(
    county_name=("county_name", "first"),
    analysis_days=("date", "count"),
    temp_imputed_days=("temp_imputed", "sum"),
    hi_null_days=("derived_tmean_meanrh_hi_f", lambda s: int(s.isna().sum())),
).reset_index()
rep["pct_analysis_days_imputed"] = round(100 * rep["temp_imputed_days"] / rep["analysis_days"], 1)
# fully-imputed (no native station data at all in analysis window)
native = an.assign(nat=~an["temp_imputed"]).groupby("county_fips")["nat"].sum()
rep["native_analysis_days"] = rep["county_fips"].map(native)
rep["fully_imputed_county"] = rep["native_analysis_days"] == 0
rep = rep.sort_values("pct_analysis_days_imputed", ascending=False)
rep.to_csv(os.path.join(OUT, "coverage_and_imputation_report.csv"), index=False)
log("\n[coverage] counties fully IDW-imputed (no native station data 2015-2025): %d"
    % int(rep["fully_imputed_county"].sum()))
log("[coverage] counties with >50%% analysis days imputed: %d"
    % int((rep["pct_analysis_days_imputed"] > 50).sum()))
log("[coverage] counties with 0%% imputed (fully native): %d"
    % int((rep["pct_analysis_days_imputed"] == 0).sum()))
log("\nMost-imputed counties:")
log(rep.head(8)[["county_fips", "county_name", "analysis_days", "pct_analysis_days_imputed", "fully_imputed_county"]].to_string(index=False))
