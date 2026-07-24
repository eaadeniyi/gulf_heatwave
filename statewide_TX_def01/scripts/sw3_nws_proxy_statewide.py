"""
STATEWIDE NWS advisory-threshold PROXY (all 254 TX counties) -- separate sensitivity.

county -> NWS forecast office (WFO): assigned by NEAREST OFFICE (county centroid
to office location, EPSG:5070). This is an APPROXIMATE crosswalk (real County
Warning Areas do not follow exact Voronoi boundaries and no authoritative CWA
shapefile was available locally); every county row carries crosswalk_method=
'nearest_office_approx' and is editable in nws_office_crosswalk.csv.

Per-office advisory / extreme-warning HEAT-INDEX thresholds (deg F), with source
+ verification_status. Only HGX & BRO are office-documented; FWD & EPZ are
close to documented Southern-Region values; the rest default to SR-standard
(105/110) or, for humid coastal/eastern offices, an approximate coastal value,
all flagged 'approximate'. Current NWS term: Extreme Heat Warning (since 2025-03).

Metric: daily MAX-HI proxy (derived_tmax_rhmin_hi_proxy_f); confirmed RH-clip
artifacts excluded. PROXY only -- NOT official advisories (no hourly HI, no
duration / overnight-min / spatial-coverage rules).

Outputs:
  tables/nws_office_crosswalk.csv       (county -> office + thresholds + status; EDITABLE)
  tables/nws_proxy_county_year.csv
  tables/nws_proxy_daily.csv            (git-ignored; large)
"""
import os, sys
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import geopandas as gpd

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.abspath(os.path.join(HERE, "..", "tables"))
SHP = os.path.join(ROOT, "data", "raw", "census", "county_shapefile", "tl_2020_us_county.shp")
SRC = os.path.join(OUT, "statewide_county_daily_heat.csv")
MAXHI = "derived_tmax_rhmin_hi_proxy_f"
AN0, AN1 = 2015, 2025


def log(*a):
    print(*a, flush=True)


# office: (lat, lon, advisory_hi, extreme_warning_hi, source, status)
OFFICES = {
    "HGX": (29.47, -95.08, 108, 113, "weather.gov/hgx/WWA_criteria", "documented"),
    "BRO": (25.92, -97.42, 111, 115, "weather.gov/bro/mapcolors", "documented"),
    "FWD": (32.83, -97.30, 105, 110, "weather.gov/fwd/heat3 (HI>=105F 2 days)", "documented_advisory"),
    "EPZ": (31.87, -106.70, 105, 110, "NWS Southern Region standard", "sr_standard"),
    "EWX": (29.70, -98.03, 105, 110, "SR standard / EWX AFD rule-of-thumb", "approximate"),
    "LUB": (33.65, -101.82, 105, 110, "NWS LUB (approx)", "approximate"),
    "AMA": (35.22, -101.72, 103, 108, "NWS AMA high-plains (approx)", "approximate"),
    "MAF": (31.94, -102.19, 105, 110, "SR standard arid-west (approx)", "approximate"),
    "SJT": (31.37, -100.49, 105, 110, "SR standard (approx)", "approximate"),
    "CRP": (27.78, -97.51, 108, 113, "coastal humid, HGX-like (approx)", "approximate"),
    "SHV": (32.45, -93.84, 108, 113, "humid E-TX, coastal-like (approx)", "approximate"),
    "LCH": (30.12, -93.22, 108, 113, "humid SE-TX edge (approx)", "approximate"),
}
OFFICE_NAME = {"HGX": "Houston/Galveston", "BRO": "Brownsville/RGV", "FWD": "Fort Worth/Dallas",
               "EPZ": "El Paso/Santa Teresa", "EWX": "Austin/San Antonio", "LUB": "Lubbock",
               "AMA": "Amarillo", "MAF": "Midland/Odessa", "SJT": "San Angelo",
               "CRP": "Corpus Christi", "SHV": "Shreveport", "LCH": "Lake Charles"}

# ---- county centroids + nearest-office assignment (EPSG:5070) ----
log("[crosswalk] assigning 254 counties to nearest NWS office (approx) ...")
gdf = gpd.read_file(SHP)
gdf = gdf[gdf["STATEFP"] == "48"].to_crs(5070)
cc = pd.DataFrame({"county_fips": gdf["GEOID"].values, "county_name": gdf["NAME"].values,
                   "cx": gdf.geometry.centroid.x.values, "cy": gdf.geometry.centroid.y.values})
# project office lat/lon -> 5070
offpts = gpd.GeoDataFrame(
    {"office": list(OFFICES)},
    geometry=gpd.points_from_xy([OFFICES[o][1] for o in OFFICES], [OFFICES[o][0] for o in OFFICES]),
    crs="EPSG:4326").to_crs(5070)
ox = offpts.geometry.x.values; oy = offpts.geometry.y.values; onames = offpts["office"].values
dx = cc["cx"].values[:, None] - ox[None, :]
dy = cc["cy"].values[:, None] - oy[None, :]
nearest = onames[np.argmin(np.sqrt(dx * dx + dy * dy), axis=1)]
cc["nws_office"] = nearest
cc["nws_office_name"] = cc["nws_office"].map(OFFICE_NAME)
cc["advisory_hi_f"] = cc["nws_office"].map(lambda o: OFFICES[o][2])
cc["extreme_warning_hi_f"] = cc["nws_office"].map(lambda o: OFFICES[o][3])
cc["threshold_source"] = cc["nws_office"].map(lambda o: OFFICES[o][4])
cc["verification_status"] = cc["nws_office"].map(lambda o: OFFICES[o][5])
cc["crosswalk_method"] = "nearest_office_approx"
xwalk = cc[["county_fips", "county_name", "nws_office", "nws_office_name", "advisory_hi_f",
            "extreme_warning_hi_f", "threshold_source", "verification_status", "crosswalk_method"]]
xwalk.to_csv(os.path.join(OUT, "nws_office_crosswalk.csv"), index=False)
log("   counties per office:")
log(xwalk["nws_office"].value_counts().to_string())

# ---- daily proxy ----
log("[proxy] computing advisory / extreme-warning threshold-met (daily max-HI proxy) ...")
d = pd.read_csv(SRC, dtype={"county_fips": str}, usecols=["county_fips", "date", "tmax_f", "rmin_pct",
                                                          MAXHI, "qc_rh_pin_likely_artifact", "temp_imputed"])
d["date"] = pd.to_datetime(d["date"]); d["year"] = d["date"].dt.year
d = d[(d["year"] >= AN0) & (d["year"] <= AN1)].merge(xwalk, on="county_fips", how="left")
art = d["qc_rh_pin_likely_artifact"].fillna(False)
d["max_hi_proxy_f"] = d[MAXHI].where(~art)
d["nws_advisory_threshold_met"] = (d["max_hi_proxy_f"] >= d["advisory_hi_f"]).astype("Int64")
d["nws_extreme_warning_threshold_met"] = (d["max_hi_proxy_f"] >= d["extreme_warning_hi_f"]).astype("Int64")
d[["county_fips", "county_name", "date", "year", "nws_office", "max_hi_proxy_f", "advisory_hi_f",
   "extreme_warning_hi_f", "nws_advisory_threshold_met", "nws_extreme_warning_threshold_met",
   "temp_imputed", "verification_status"]].to_csv(os.path.join(OUT, "nws_proxy_daily.csv"), index=False)

cy = d.groupby(["county_fips", "county_name", "nws_office", "year"]).agg(
    advisory_threshold_days=("nws_advisory_threshold_met", "sum"),
    extreme_warning_threshold_days=("nws_extreme_warning_threshold_met", "sum"),
    advisory_hi_f=("advisory_hi_f", "first"), extreme_warning_hi_f=("extreme_warning_hi_f", "first"),
    verification_status=("verification_status", "first")).reset_index()
cy.to_csv(os.path.join(OUT, "nws_proxy_county_year.csv"), index=False)
log("[done] nws_proxy_county_year.csv rows=%d" % len(cy))

log("\n[by office -- advisory-threshold PROXY days, pooled 2015-2025]")
byoff = cy.groupby(["nws_office", "advisory_hi_f", "extreme_warning_hi_f", "verification_status"]).agg(
    counties=("county_fips", "nunique"), adv=("advisory_threshold_days", "sum"),
    warn=("extreme_warning_threshold_days", "sum")).reset_index().sort_values("adv", ascending=False)
log(byoff.to_string(index=False))
log("\n[caveat] PROXY only; nearest-office crosswalk is APPROXIMATE; most office thresholds")
log("         flagged 'approximate' -- editable in nws_office_crosswalk.csv.")
