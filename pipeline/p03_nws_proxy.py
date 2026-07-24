"""
=============================================================================
STEP p03  --  NWS advisory-threshold PROXY (a separate, absolute-threshold
              sensitivity), per state.
=============================================================================
This answers a DIFFERENT question than the relative definitions: "did estimated
apparent heat reach a level comparable to the LOCAL NWS forecast office's
advisory / extreme-heat-warning criteria?" It is a PROXY -- it uses a daily
Tmax+RHmin heat-index approximation, not hourly concurrent heat index, and it
cannot reproduce each office's duration / overnight-minimum / spatial-coverage
rules. It is NOT an official NWS advisory.

State-agnostic mechanics:
  * Reads a per-state office table  nws_offices_<ST>.csv  (office lat/lon +
    advisory/extreme-warning heat-index thresholds + source + verification_status).
    If that file is absent, this step is skipped for the state.
  * Assigns each county to its NEAREST office by centroid distance (an APPROXIMATE
    crosswalk -- real County Warning Areas are not exact Voronoi cells; flagged as
    such and written to an editable crosswalk file).
  * Flags each county-day where the daily-MAX heat-index proxy meets each threshold.

Current NWS terminology: "Extreme Heat Warning" (renamed from "Excessive Heat
Warning" on 2025-03-04).
=============================================================================
"""
import os, sys
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import geopandas as gpd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

MAXHI = "derived_tmax_rhmin_hi_proxy_f"   # daily-MAX proxy: NWS thresholds are daytime-max HI values


def log(*a):
    print(*a, flush=True)


def run_state(state):
    office_path = C.nws_office_table(state)
    if not os.path.exists(office_path):
        log("[p03] no office table (%s) -- skipping NWS proxy for %s" % (os.path.basename(office_path), state))
        return
    fips = C.STATE_FIPS[state]
    outdir = C.state_output_dir(state)
    log("=" * 72)
    log("p03  NWS advisory-threshold PROXY  --  state=%s  (PROXY, not official advisories)" % state)
    log("=" * 72)
    off = pd.read_csv(office_path)

    # ---- county centroids -> nearest office (approximate crosswalk) --------
    gdf = gpd.read_file(C.COUNTY_SHAPEFILE)
    gdf = gdf[gdf["STATEFP"] == fips].to_crs(C.EQUAL_AREA_CRS)
    cc = pd.DataFrame({"county_fips": gdf["GEOID"].values, "county_name": gdf["NAME"].values,
                       "cx": gdf.geometry.centroid.x.values, "cy": gdf.geometry.centroid.y.values})
    offpts = gpd.GeoDataFrame(off.copy(),
                              geometry=gpd.points_from_xy(off["office_lon"], off["office_lat"]),
                              crs="EPSG:4326").to_crs(C.EQUAL_AREA_CRS)
    ox = offpts.geometry.x.values; oy = offpts.geometry.y.values
    dx = cc["cx"].values[:, None] - ox[None, :]
    dy = cc["cy"].values[:, None] - oy[None, :]
    nearest = np.argmin(np.sqrt(dx * dx + dy * dy), axis=1)
    xwalk = cc[["county_fips", "county_name"]].copy()
    for col in ["nws_office", "nws_office_name", "advisory_hi_f", "extreme_warning_hi_f",
                "threshold_source", "verification_status"]:
        xwalk[col] = off[col].values[nearest]
    xwalk["crosswalk_method"] = "nearest_office_approx"
    xwalk.to_csv(os.path.join(outdir, "nws_office_crosswalk.csv"), index=False)
    log("   counties per office:\n" + xwalk["nws_office"].value_counts().to_string())

    # ---- daily proxy: does the daily-MAX HI proxy meet each threshold? -----
    d = pd.read_csv(os.path.join(outdir, "county_daily_heat.csv"), dtype={"county_fips": str},
                    usecols=["county_fips", "date", MAXHI, "qc_rh_pin_likely_artifact", "temp_imputed"])
    d["date"] = pd.to_datetime(d["date"]); d["year"] = d["date"].dt.year
    d = d[(d["year"] >= C.ANALYSIS_YEARS[0]) & (d["year"] <= C.ANALYSIS_YEARS[1])].merge(xwalk, on="county_fips", how="left")
    art = d["qc_rh_pin_likely_artifact"].fillna(False)
    d["max_hi_proxy_f"] = d[MAXHI].where(~art)              # exclude confirmed artifacts
    d["nws_advisory_threshold_met"] = (d["max_hi_proxy_f"] >= d["advisory_hi_f"]).astype("Int64")
    d["nws_extreme_warning_threshold_met"] = (d["max_hi_proxy_f"] >= d["extreme_warning_hi_f"]).astype("Int64")
    d[["county_fips", "county_name", "date", "year", "nws_office", "max_hi_proxy_f", "advisory_hi_f",
       "extreme_warning_hi_f", "nws_advisory_threshold_met", "nws_extreme_warning_threshold_met",
       "temp_imputed", "verification_status"]].to_csv(os.path.join(outdir, "nws_proxy_daily.csv"), index=False)

    cy = d.groupby(["county_fips", "county_name", "nws_office", "year"]).agg(
        advisory_threshold_days=("nws_advisory_threshold_met", "sum"),
        extreme_warning_threshold_days=("nws_extreme_warning_threshold_met", "sum"),
        advisory_hi_f=("advisory_hi_f", "first"), extreme_warning_hi_f=("extreme_warning_hi_f", "first"),
        verification_status=("verification_status", "first")).reset_index()
    cy.to_csv(os.path.join(outdir, "nws_proxy_county_year.csv"), index=False)
    log("[done] nws_proxy_county_year.csv rows=%d (PROXY; crosswalk approximate; edit nws_offices_%s.csv to correct thresholds)"
        % (len(cy), state))


if __name__ == "__main__":
    for st in C.STATES:
        run_state(st)
