"""
STEP 1-2 (adapted from spec Part C): validate inputs, standardize, build the
county-daily heat table for the 5 Texas pilot counties.

This project has no hourly or dewpoint data (see 01_configuration.yaml), so
spec Steps 5-8 (hourly HI, grid-daily aggregation, spatial weights, land-area-
weighted county aggregation) are SKIPPED. We start from the existing daily
GHCN (temperature) + gridMET (humidity) county-day extracts.

REVISION 2026-07-16 (external review corrections):
  - Issue 1: primary metric renamed derived_max_hi_f -> derived_tmax_rhmin_hi_proxy_f
    (a Tmax+RHmin PROXY, not a validated county daily maximum HI).
  - Issue 3: completeness numerator bug (bitwise &) fixed; denominators reported
    per period (full raw source / fixed 1979-2014 / analysis 2015-2025).
  - Issue 5: TWO separate 80F flags now computed -- one on the derived HI proxy
    (absolute apparent-heat floor, PRIMARY) and one on Tmax (heat-index formula
    domain, SENSITIVITY). Neither is called "minimum_valid_temperature".
  - Issue 2/R2-6: four-level qc_status (valid / suspicious_retain / missing_input / invalid_physical)
    -- suspicious soft-QC flags now DO propagate into county_daily_quality_flag.

Output: tables/05_county_daily_heat.csv
        tables/quality_control/01_input_validation_report.md
        tables/quality_control/completeness_by_county.csv
"""
import os, sys
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

ROOT = r"C:\Users\eadeni1\OneDrive - Louisiana State University\Documents\doc\heatWaveUS"
sys.path.insert(0, os.path.join(ROOT, "gulf_eda", "scripts"))
from eda_util import heat_index_f  # corrected 2026-07-16 version

PILOT = os.path.join(ROOT, "texas_heatwave_pilot")
TAB = os.path.join(PILOT, "tables")
QC = os.path.join(TAB, "quality_control")
os.makedirs(QC, exist_ok=True)

PILOT_COUNTIES = {
    "48201": {"name": "Harris (Houston)", "division": "Upper Coast (4108)", "role": "humid coastal"},
    "48141": {"name": "El Paso", "division": "Trans-Pecos (4105)", "role": "hot/arid desert"},
    "48303": {"name": "Lubbock", "division": "High Plains (4101)", "role": "semi-arid panhandle"},
    "48453": {"name": "Travis (Austin)", "division": "South Central (4107)", "role": "central/transitional"},
    "48061": {"name": "Cameron (Brownsville)", "division": "Lower Valley (4110)", "role": "subtropical humid south"},
}
FIPS = list(PILOT_COUNTIES.keys())
HI_FLOOR_F = 80          # absolute apparent-heat floor, applied to the HI proxy (PRIMARY)
TMAX_DOMAIN_F = 80       # NWS heat-index formula domain, applied to Tmax (SENSITIVITY)

log_lines = []
def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    log_lines.append(s)

log("=" * 70)
log("STEP 1-2: input validation + county-daily heat table (5 TX pilot counties)")
log("  (revised 2026-07-16 per external methodological review)")
log("=" * 70)

# ----------------------------------------------------------------------
# Load raw sources (already county-day aggregated upstream -- see config;
# this aggregation ORDER/METHOD is a documented deviation, review Issue 1)
# ----------------------------------------------------------------------
t = pd.read_csv(os.path.join(ROOT, "data", "raw", "gulf_states", "TX", "weather", "ghcn_county_day_weather_TX.csv"),
                 usecols=["county_fips", "county_name", "date", "tmax_f", "tmin_f", "prcp_in"], dtype={"county_fips": str})
h = pd.read_csv(os.path.join(ROOT, "data", "raw", "gulf_states", "TX", "weather", "gridmet_county_day_humidity_TX.csv"),
                 usecols=["county_fips", "date", "rmax_pct", "rmin_pct"], dtype={"county_fips": str})
t["county_fips"] = t["county_fips"].str.zfill(5)
h["county_fips"] = h["county_fips"].str.zfill(5)
t = t[t["county_fips"].isin(FIPS)].copy()
h = h[h["county_fips"].isin(FIPS)].copy()
t["date"] = pd.to_datetime(t["date"], errors="coerce")
h["date"] = pd.to_datetime(h["date"], errors="coerce")

log("\n[1] raw load: temp rows=%d  humidity rows=%d" % (len(t), len(h)))

# ----------------------------------------------------------------------
# Required checks (spec Step 1) -- flag, do not silently delete
# ----------------------------------------------------------------------
log("\n[2] required checks (flag only, no silent deletion)")
log("  duplicate (county,date) rows: temp=%d  humidity=%d"
    % (t.duplicated(subset=["county_fips", "date"]).sum(), h.duplicated(subset=["county_fips", "date"]).sum()))
log("  unparseable timestamps: temp=%d  humidity=%d" % (t["date"].isna().sum(), h["date"].isna().sum()))
log("  impossible Tmax<Tmin rows: %d" % (t["tmax_f"] < t["tmin_f"]).sum())
log("  RH out-of-bounds (0-100%%) rows: %d"
    % (((h["rmax_pct"] < 0) | (h["rmax_pct"] > 100)) | ((h["rmin_pct"] < 0) | (h["rmin_pct"] > 100))).sum())
log("  RHmin>RHmax (impossible) rows: %d" % (h["rmin_pct"] > h["rmax_pct"]).sum())

# ----------------------------------------------------------------------
# Merge + standardize
# ----------------------------------------------------------------------
log("\n[3] merge temp + humidity, standardize (units already degF/pct, no conversion needed)")
cd = t.merge(h, on=["county_fips", "date"], how="outer")
cd["county_name"] = cd["county_fips"].map(lambda f: PILOT_COUNTIES[f]["name"])
cd["climate_division"] = cd["county_fips"].map(lambda f: PILOT_COUNTIES[f]["division"])
cd = cd.dropna(subset=["date"]).sort_values(["county_fips", "date"]).reset_index(drop=True)
cd["year"] = cd["date"].dt.year
cd["month"] = cd["date"].dt.month
cd["day"] = cd["date"].dt.day
cd["doy"] = cd["date"].dt.dayofyear

# ---- HARD-invalid (physically impossible): set offending field to NaN + flag ----
cd["qc_tmax_lt_tmin"] = (cd["tmax_f"] < cd["tmin_f"]).fillna(False)
cd.loc[cd["qc_tmax_lt_tmin"], ["tmax_f", "tmin_f"]] = np.nan
cd["qc_rh_oob"] = (((cd["rmax_pct"] < 0) | (cd["rmax_pct"] > 100)) |
                    ((cd["rmin_pct"] < 0) | (cd["rmin_pct"] > 100))).fillna(False)
cd.loc[cd["qc_rh_oob"], ["rmax_pct", "rmin_pct"]] = np.nan
cd["qc_rmin_gt_rmax"] = (cd["rmin_pct"] > cd["rmax_pct"]).fillna(False)

# ---- SOFT-suspicious (implausible but not strictly impossible) -- review Issue 2 ----
cd["qc_zero_diurnal_rh_range"] = ((cd["rmax_pct"] - cd["rmin_pct"]).abs() < 1e-6).fillna(False)
cd["qc_rh_pinned_at_100"] = ((cd["rmax_pct"].round(6) == 100.0) & (cd["rmin_pct"].round(6) == 100.0)).fillna(False)
cd["qc_tiny_diurnal_temp_range"] = ((cd["tmax_f"] - cd["tmin_f"]).abs() < 2.0).fillna(False)
# PRCP-aware refinement of the RH=100 pin (R2 workflow investigation, 2026-07-16):
# gridMET pins RH at exactly 100.000000 on two physically-distinct kinds of day.
# A WARM + DRY (precip~=0) pin is a confirmed product-level clipping artifact that
# spuriously inflates the HI proxy (verified: 2023-03-01 was pinned in 118/254 TX
# counties simultaneously with zero precip and station RH only ~80%). A COLD/WET
# pin (e.g. 2017-01-14) is a genuine saturation event and affects no heat metric.
# prcp_in is an INDEPENDENT source (GHCN) from the pinned RH (gridMET), so this is
# a real cross-check, not circular.
_prcp = cd["prcp_in"].fillna(0)
cd["qc_rh_pin_likely_artifact"] = (cd["qc_rh_pinned_at_100"] & (_prcp < 0.01) & (cd["tmax_f"] >= 80)).fillna(False)
cd["qc_rh_pin_likely_real_wet"] = (cd["qc_rh_pinned_at_100"] & (_prcp >= 0.01)).fillna(False)

cd["tmean_f"] = (cd["tmax_f"] + cd["tmin_f"]) / 2.0
cd["rh_mean_pct"] = (cd["rmax_pct"] + cd["rmin_pct"]) / 2.0

# ----------------------------------------------------------------------
# Derived (approximated) HI proxy -- Issue 1 rename
# ----------------------------------------------------------------------
log("\n[4] derived Tmax+RHmin HI PROXY (renamed per review Issue 1; not a validated daily max)")
cd["derived_tmax_rhmin_hi_proxy_f"] = heat_index_f(cd["tmax_f"], cd["rmin_pct"])
cd["derived_tmean_meanrh_hi_f"] = heat_index_f(cd["tmean_f"], cd["rh_mean_pct"])  # documentation only
cd["heat_index_method"] = np.where(cd["tmax_f"] >= 80, "full_rothfusz_plus_adjustments", "simple_fallback_below_80F")
cd["heat_index_validity_flag"] = "derived_from_daily_nonconcurrent_inputs_not_observed_hourly_max"

# ---- soft-QC: HI day-to-day jump not explained by Tmax (RH-driven spike detector) ----
cd["_hi_diff"] = cd.groupby("county_fips")["derived_tmax_rhmin_hi_proxy_f"].diff()
cd["_tmax_diff"] = cd.groupby("county_fips")["tmax_f"].diff()
cd["qc_hi_jump_unexplained_by_tmax"] = ((cd["_hi_diff"].abs() > 15) & (cd["_tmax_diff"].abs() < 5)).fillna(False)

SOFT_FLAGS = ["qc_zero_diurnal_rh_range", "qc_rh_pinned_at_100",
              "qc_tiny_diurnal_temp_range", "qc_hi_jump_unexplained_by_tmax"]
# informative sub-classifications of the pin (NOT extra soft flags -- they partition
# qc_rh_pinned_at_100, which already drives suspicious_retain; kept for reporting)
PIN_SUBFLAGS = ["qc_rh_pin_likely_artifact", "qc_rh_pin_likely_real_wet"]
HARD_FLAGS = ["qc_tmax_lt_tmin", "qc_rh_oob", "qc_rmin_gt_rmax"]
cd["any_soft_flag"] = cd[SOFT_FLAGS].any(axis=1)
cd["any_hard_flag"] = cd[HARD_FLAGS].any(axis=1)

# ----------------------------------------------------------------------
# FOUR-level qc_status (review R2 Issue 6: split missing from physically invalid)
#   invalid_physical  -> a hard flag fired (Tmax<Tmin, RH out of 0-100, RHmin>RHmax)
#                        = a DATA-QUALITY problem
#   missing_input     -> proxy uncomputable because a required input is absent
#                        = a COMPLETENESS problem (distinct handling/reporting)
#   suspicious_retain -> implausible but not impossible; kept and flagged
#   valid             -> clean
# (order matters: physical-invalidity checked before missing, since a hard flag
#  also nulls the field -- we still want it labeled by its root cause.)
# ----------------------------------------------------------------------
cd["qc_status"] = np.select(
    [cd["any_hard_flag"],
     cd["derived_tmax_rhmin_hi_proxy_f"].isna(),
     cd["any_soft_flag"]],
    ["invalid_physical", "missing_input", "suspicious_retain"],
    default="valid")
# keep the legacy column name too, now reflecting the 4-level status (review Issue 2)
cd["county_daily_quality_flag"] = cd["qc_status"]

for lvl in ["valid", "suspicious_retain", "missing_input", "invalid_physical"]:
    log("  qc_status %-18s %d" % (lvl, int((cd["qc_status"] == lvl).sum())))
log("  (total=%d)" % len(cd))
log("  RH=100 pin sub-classification (PRCP-aware, R2 investigation): "
    "likely_artifact(warm+dry)=%d  likely_real_wet=%d  of %d total pins"
    % (int(cd["qc_rh_pin_likely_artifact"].sum()), int(cd["qc_rh_pin_likely_real_wet"].sum()),
       int(cd["qc_rh_pinned_at_100"].sum())))

# ----------------------------------------------------------------------
# Issue 5: TWO 80F flags, clearly distinguished
# ----------------------------------------------------------------------
cd["floor_hi_ge_80"] = (cd["derived_tmax_rhmin_hi_proxy_f"] >= HI_FLOOR_F).astype("Int64")   # PRIMARY
cd["domain_tmax_ge_80"] = (cd["tmax_f"] >= TMAX_DOMAIN_F).astype("Int64")                     # SENSITIVITY
log("\n[5] dual 80F flags (review Issue 5):")
log("  floor_hi_ge_80    (apparent-heat floor, PRIMARY):     %d days" % int(cd["floor_hi_ge_80"].sum()))
log("  domain_tmax_ge_80 (formula-domain, SENSITIVITY):      %d days" % int(cd["domain_tmax_ge_80"].sum()))

out_cols = ["county_fips", "county_name", "climate_division", "date", "year", "month", "day", "doy",
            "tmax_f", "tmin_f", "tmean_f", "prcp_in", "rmax_pct", "rmin_pct", "rh_mean_pct",
            "derived_tmax_rhmin_hi_proxy_f", "derived_tmean_meanrh_hi_f",
            "heat_index_method", "heat_index_validity_flag",
            "floor_hi_ge_80", "domain_tmax_ge_80",
            "qc_status", "county_daily_quality_flag"] + HARD_FLAGS + SOFT_FLAGS + PIN_SUBFLAGS
cd[out_cols].to_csv(os.path.join(TAB, "05_county_daily_heat.csv"), index=False)
log("\n[done] wrote 05_county_daily_heat.csv rows=%d" % len(cd))

# ----------------------------------------------------------------------
# Issue 3: completeness reported PER PERIOD, numerator computed correctly
# ----------------------------------------------------------------------
def joint_valid(g):
    return int((g["tmax_f"].notna() & g["tmin_f"].notna() & g["rmax_pct"].notna() & g["rmin_pct"].notna()).sum())

periods = {
    "full_raw_source": (cd["date"].min(), cd["date"].max()),
    "fixed_1979_2014": (pd.Timestamp("1979-01-01"), pd.Timestamp("2014-12-31")),
    "analysis_2015_2025": (pd.Timestamp("2015-01-01"), pd.Timestamp("2025-12-31")),
}
comp_rows = []
for fips, g in cd.groupby("county_fips"):
    row = {"county_fips": fips, "name": PILOT_COUNTIES[fips]["name"]}
    for pname, (lo, hi) in periods.items():
        sub = g[(g["date"] >= lo) & (g["date"] <= hi)]
        n_possible = (hi.normalize() - lo.normalize()).days + 1
        row["%s_n_possible" % pname] = n_possible
        row["%s_n_joint_valid" % pname] = joint_valid(sub)
        row["%s_pct_complete" % pname] = round(100 * joint_valid(sub) / n_possible, 2)
    comp_rows.append(row)
completeness = pd.DataFrame(comp_rows)
completeness.to_csv(os.path.join(QC, "completeness_by_county.csv"), index=False)
log("\n[6] completeness by county, per period (review Issue 3 -- numerator/denominator fixed):")
for _, r in completeness.iterrows():
    log("  %-22s full=%d/%d (%.2f%%)  1979-2014=%d/%d (%.2f%%)  2015-2025=%d/%d (%.2f%%)" % (
        r["name"],
        r["full_raw_source_n_joint_valid"], r["full_raw_source_n_possible"], r["full_raw_source_pct_complete"],
        r["fixed_1979_2014_n_joint_valid"], r["fixed_1979_2014_n_possible"], r["fixed_1979_2014_pct_complete"],
        r["analysis_2015_2025_n_joint_valid"], r["analysis_2015_2025_n_possible"], r["analysis_2015_2025_pct_complete"]))

report_path = os.path.join(QC, "01_input_validation_report.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write("# Step 1-2: Input Validation Report (revised 2026-07-16)\n\n")
    f.write("Generated by `step01_validate_and_build_county_day.py`.\n\n")
    f.write("\n".join("    " + l for l in log_lines))
    f.write("\n\n## Notes\n\n")
    f.write("- No rows silently dropped for suspicious values. Four-level qc_status: "
            "physically-impossible observations -> `invalid_physical`; source absences "
            "(proxy uncomputable) -> `missing_input`; implausible-but-usable values kept "
            "and flagged -> `suspicious_retain`; else `valid`.\n")
    f.write("- Units already degF / percent as delivered by upstream extraction.\n")
    f.write("- Primary metric is a Tmax+RHmin PROXY (`derived_tmax_rhmin_hi_proxy_f`); "
            "components are NOT observed concurrently and have different spatial supports "
            "(GHCN station-based temperature vs. gridMET grid-mean humidity).\n")
    f.write("- Time-convention of the two sources documented separately "
            "(see `04_source_time_conventions.md`).\n")
log("\n[done] wrote %s" % report_path)
