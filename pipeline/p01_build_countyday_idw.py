"""
=============================================================================
STEP p01  --  build the per-county daily table (one state), with IDW gap-fill.
=============================================================================
For each configured state this step:
  1. Loads the state's daily GHCN temperature and gridMET humidity county-day files.
  2. Applies hard quality control (nulls physically-impossible values) and flags
     the RH=100 "clip" artifact (RH pinned at 100 on warm, rain-free days).
  3. Fills MISSING daily temperature by inverse-distance weighting (IDW) from
     surrounding counties, using county CENTROID distances -- and flags every
     imputed county-day so interpolated values never pass as observed.
  4. Computes the daily-mean and daily-max heat-index proxies.
  5. Writes <OUTPUT_ROOT>/<ST>/county_daily_heat.csv (+ a coverage report).

Nothing here is Texas-specific: the state is taken from config.STATES and its
FIPS/paths/centroids are derived generically.
=============================================================================
"""
import os, sys, time
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import geopandas as gpd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
sys.path.insert(0, C.HEAT_INDEX_MODULE_DIR)
from eda_util import heat_index_f   # NWS Rothfusz heat index (deg F), shared with the rest of the project


def log(*a):
    print(*a, flush=True)


def build_state(state):
    """Build the county-day table (with IDW gap-fill) for one state."""
    t0 = time.time()
    fips = C.STATE_FIPS[state]
    outdir = C.state_output_dir(state)
    log("=" * 72)
    log("p01  build county-day table + IDW gap-fill  --  state=%s (FIPS %s)" % (state, fips))
    log("=" * 72)

    # ---- 1. load temperature + humidity, merge on county+date --------------
    t = pd.read_csv(C.ghcn_path(state),
                    usecols=["county_fips", "county_name", "date", "tmax_f", "tmin_f", "prcp_in"],
                    dtype={"county_fips": str})
    h = pd.read_csv(C.gridmet_path(state),
                    usecols=["county_fips", "date", "rmax_pct", "rmin_pct"], dtype={"county_fips": str})
    t["county_fips"] = t["county_fips"].str.zfill(5)
    h["county_fips"] = h["county_fips"].str.zfill(5)
    cd = t.merge(h, on=["county_fips", "date"], how="outer")
    cd["date"] = pd.to_datetime(cd["date"], errors="coerce")
    cd = cd.dropna(subset=["date"])
    cd = cd[(cd["date"].dt.year >= C.BASELINE_START) & (cd["date"].dt.year <= C.ANALYSIS_YEARS[1])].copy()
    cd["year"] = cd["date"].dt.year
    cd["month"] = cd["date"].dt.month
    cd["day"] = cd["date"].dt.day
    log("[load] %d county-days, %d counties, %s..%s"
        % (len(cd), cd["county_fips"].nunique(), cd["date"].min().date(), cd["date"].max().date()))

    # ---- 2. hard QC (null impossible values) + artifact flag ---------------
    cd["qc_tmax_lt_tmin"] = (cd["tmax_f"] < cd["tmin_f"]).fillna(False)
    cd.loc[cd["qc_tmax_lt_tmin"], ["tmax_f", "tmin_f"]] = np.nan
    cd["qc_rh_oob"] = (((cd["rmax_pct"] < 0) | (cd["rmax_pct"] > 100)) |
                       ((cd["rmin_pct"] < 0) | (cd["rmin_pct"] > 100))).fillna(False)
    cd.loc[cd["qc_rh_oob"], ["rmax_pct", "rmin_pct"]] = np.nan
    # RH clipped to exactly 100 (both bounds) on a warm, rain-free day is a known
    # gridMET artifact that spuriously inflates the heat index -> flag it (handled
    # by setting to missing at classification time, not imputed).
    _prcp = cd["prcp_in"].fillna(0)
    cd["qc_rh_pin_likely_artifact"] = (((cd["rmax_pct"].round(6) == 100.0) & (cd["rmin_pct"].round(6) == 100.0))
                                       & (_prcp < 0.01) & (cd["tmax_f"] >= 80)).fillna(False)

    # ---- 3. county centroids -> inverse-distance weight matrix -------------
    log("[centroids] building %s centroid IDW weights (power=%d) ..." % (state, C.IDW_POWER))
    gdf = gpd.read_file(C.COUNTY_SHAPEFILE)
    gdf = gdf[gdf["STATEFP"] == fips].to_crs(C.EQUAL_AREA_CRS)
    name_map = dict(zip(gdf["GEOID"].values, gdf["NAME"].values))
    cd["county_name"] = cd["county_fips"].map(name_map).fillna(cd["county_name"])  # backfill names
    cent = pd.DataFrame({"county_fips": gdf["GEOID"].values,
                         "cx": gdf.geometry.centroid.x.values,
                         "cy": gdf.geometry.centroid.y.values}).set_index("county_fips")
    counties = sorted(cd["county_fips"].unique())
    cent = cent.reindex(counties)
    XY = cent[["cx", "cy"]].values
    dx = XY[:, 0][:, None] - XY[:, 0][None, :]
    dy = XY[:, 1][:, None] - XY[:, 1][None, :]
    dist = np.sqrt(dx * dx + dy * dy)
    with np.errstate(divide="ignore"):
        W = 1.0 / (dist ** C.IDW_POWER)
    np.fill_diagonal(W, 0.0)                       # a county never imputes from itself

    # ---- 4. IDW-impute missing daily values (vectorised over all dates) ----
    dates = pd.date_range(cd["date"].min(), cd["date"].max(), freq="D")
    didx = {d: i for i, d in enumerate(dates)}
    cidx = {c: j for j, c in enumerate(counties)}

    def idw_fill(varname):
        """Return (filled_long, imputed_mask_long) aligned to cd's row order.
        For each date, imputed_j = sum_i(w_ij v_i) / sum_i(w_ij) over counties i
        that have data that day. Two matmuls give the whole grid at once."""
        piv = cd.pivot_table(index="date", columns="county_fips", values=varname, aggfunc="first")
        piv = piv.reindex(index=dates, columns=counties)
        V = piv.values.astype(float)                 # (ndates x ncounties)
        M = (~np.isnan(V)).astype(float)             # 1 where present
        V0 = np.where(np.isnan(V), 0.0, V)
        num = (V0 * M) @ W                           # weighted sum of available values
        den = M @ W                                  # sum of weights of available values
        with np.errstate(invalid="ignore", divide="ignore"):
            imp = num / den
        missing = np.isnan(V)
        filled = np.where(missing, imp, V)
        imputed = missing & np.isfinite(imp)
        ri = cd["date"].map(didx).values
        cj = cd["county_fips"].map(cidx).values
        return filled[ri, cj], imputed[ri, cj]

    log("[idw] imputing missing tmax_f/tmin_f/rmax_pct/rmin_pct ...")
    for var in ["tmax_f", "tmin_f", "rmax_pct", "rmin_pct"]:
        filled, imp = idw_fill(var)
        cd[var] = filled
        cd[var + "_imputed"] = imp
    cd["temp_imputed"] = cd["tmax_f_imputed"] | cd["tmin_f_imputed"]
    cd["rh_imputed"] = cd["rmax_pct_imputed"] | cd["rmin_pct_imputed"]
    log("   imputed temperature county-days: %d (%.2f%%) | imputed RH: %d"
        % (int(cd["temp_imputed"].sum()), 100 * cd["temp_imputed"].mean(), int(cd["rh_imputed"].sum())))

    # ---- 5. derived heat-index proxies (AFTER filling) ---------------------
    cd["tmean_f"] = (cd["tmax_f"] + cd["tmin_f"]) / 2.0
    cd["rh_mean_pct"] = (cd["rmax_pct"] + cd["rmin_pct"]) / 2.0
    cd["derived_tmean_meanrh_hi_f"] = heat_index_f(cd["tmean_f"], cd["rh_mean_pct"])   # daily-MEAN proxy (definitions use this)
    cd["derived_tmax_rhmin_hi_proxy_f"] = heat_index_f(cd["tmax_f"], cd["rmin_pct"])   # daily-MAX proxy (NWS-proxy step uses this)
    cd["qc_status"] = np.select(
        [cd["qc_tmax_lt_tmin"] | cd["qc_rh_oob"],
         cd["derived_tmean_meanrh_hi_f"].isna(),
         cd["qc_rh_pin_likely_artifact"]],
        ["invalid_physical", "missing_input", "suspicious_retain"], default="valid")

    keep = ["county_fips", "county_name", "date", "year", "month", "day",
            "tmax_f", "tmin_f", "tmean_f", "prcp_in", "rmax_pct", "rmin_pct", "rh_mean_pct",
            "derived_tmean_meanrh_hi_f", "derived_tmax_rhmin_hi_proxy_f",
            "temp_imputed", "rh_imputed", "qc_rh_pin_likely_artifact", "qc_status"]
    out = os.path.join(outdir, "county_daily_heat.csv")
    cd[keep].to_csv(out, index=False)
    log("[done] wrote %s (rows=%d, %.0fs)" % (out, len(cd), time.time() - t0))

    # ---- 6. coverage / imputation report -----------------------------------
    an = cd[(cd["year"] >= C.ANALYSIS_YEARS[0]) & (cd["year"] <= C.ANALYSIS_YEARS[1])]
    rep = an.groupby("county_fips").agg(county_name=("county_name", "first"),
                                        analysis_days=("date", "count"),
                                        temp_imputed_days=("temp_imputed", "sum")).reset_index()
    rep["pct_analysis_days_imputed"] = round(100 * rep["temp_imputed_days"] / rep["analysis_days"], 1)
    native = an.assign(nat=~an["temp_imputed"]).groupby("county_fips")["nat"].sum()
    rep["native_analysis_days"] = rep["county_fips"].map(native)
    rep["fully_imputed_county"] = rep["native_analysis_days"] == 0
    rep.sort_values("pct_analysis_days_imputed", ascending=False).to_csv(
        os.path.join(outdir, "coverage_and_imputation_report.csv"), index=False)
    log("[coverage] fully-imputed counties: %d | fully-native (0%%): %d"
        % (int(rep["fully_imputed_county"].sum()), int((rep["pct_analysis_days_imputed"] == 0).sum())))


if __name__ == "__main__":
    for st in C.STATES:
        build_state(st)
