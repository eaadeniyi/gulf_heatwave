"""
NWS advisory-threshold PROXY -- a SEPARATE sensitivity (spec sections 7-8),
answering a different question than the relative 85th-pctl definition:
  relative:  "was this unusually hot for this county and time of year?"
  NWS proxy: "did estimated apparent heat reach a level comparable to the LOCAL
              NWS office's operational advisory / extreme-warning criteria?"

IMPORTANT LABELLING (spec section 8): because we only have a daily Tmax-RHmin
heat-index PROXY (not hourly concurrent HI, and not the office's exact
duration / overnight-minimum / spatial-coverage rules), the outputs are the
"NWS advisory-threshold PROXY", NOT official NWS Heat Advisories.

Metric: daily-MAX HI proxy (derived_tmax_rhmin_hi_proxy_f) -- NWS advisory
thresholds are daytime-max heat-index values, so the MAX proxy (not the mean)
is the right comparison here.

Per-county local office thresholds come from nws_office_thresholds.csv (each row
carries its source + verification_status; EWX & LUB are flagged approximate).
Current NWS terminology (since 2025-03-04): "Extreme Heat Warning" (formerly
"Excessive Heat Warning").

Outputs:
  tables/nws_proxy_daily.csv           one row per county-date (2015-2025) with met-flags
  tables/nws_proxy_county_year.csv     annual count of advisory- and warning-threshold days
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PILOT = os.path.join(ROOT, "texas_heatwave_pilot")
SRC = os.path.join(PILOT, "tables", "05_county_daily_heat.csv")
OUT = os.path.abspath(os.path.join(HERE, "..", "tables"))
MAXHI = "derived_tmax_rhmin_hi_proxy_f"
AN0, AN1 = 2015, 2025


def log(*a):
    print(*a, flush=True)


log("=" * 72)
log("NWS advisory-threshold PROXY (separate sensitivity; NOT official advisories)")
log("=" * 72)

d = pd.read_csv(SRC, dtype={"county_fips": str})
d["date"] = pd.to_datetime(d["date"])
d = d[(d["date"].dt.year >= AN0) & (d["date"].dt.year <= AN1)].copy()
off = pd.read_csv(os.path.join(OUT, "nws_office_thresholds.csv"), dtype={"county_fips": str})

d = d.merge(off, on="county_fips", how="left", suffixes=("", "_off"))
# exclude the 3 confirmed RH-clip artifacts (consistent with the relative primary)
artifact = d.get("qc_rh_pin_likely_artifact", pd.Series(False, index=d.index)).fillna(False)
d["max_hi_proxy_f"] = d[MAXHI].where(~artifact)

d["nws_advisory_threshold_met"] = (d["max_hi_proxy_f"] >= d["advisory_hi_f"]).astype("Int64")
d["nws_extreme_warning_threshold_met"] = (d["max_hi_proxy_f"] >= d["extreme_warning_hi_f"]).astype("Int64")

daily_cols = ["county_fips", "county_name", "date", "nws_office", "nws_office_name",
              "tmax_f", "rmin_pct", "max_hi_proxy_f", "advisory_hi_f", "extreme_warning_hi_f",
              "nws_advisory_threshold_met", "nws_extreme_warning_threshold_met",
              "threshold_source", "verification_status"]
d["year"] = d["date"].dt.year
d[daily_cols].to_csv(os.path.join(OUT, "nws_proxy_daily.csv"), index=False)
log("[daily] wrote nws_proxy_daily.csv rows=%d" % len(d))

cy = d.groupby(["county_fips", "county_name", "nws_office", "year"]).agg(
    advisory_threshold_days=("nws_advisory_threshold_met", "sum"),
    extreme_warning_threshold_days=("nws_extreme_warning_threshold_met", "sum"),
    advisory_hi_f=("advisory_hi_f", "first"),
    extreme_warning_hi_f=("extreme_warning_hi_f", "first"),
    verification_status=("verification_status", "first"),
).reset_index()
cy.to_csv(os.path.join(OUT, "nws_proxy_county_year.csv"), index=False)
log("[county-year] wrote nws_proxy_county_year.csv rows=%d" % len(cy))

log("\n[interpretable, per county -- NWS advisory-threshold PROXY days, pooled 2015-2025]")
pool = cy.groupby(["county_name", "nws_office", "advisory_hi_f", "extreme_warning_hi_f", "verification_status"]).agg(
    adv_days=("advisory_threshold_days", "sum"), warn_days=("extreme_warning_threshold_days", "sum")).reset_index()
for _, r in pool.iterrows():
    log("  %-22s [%s adv>=%dF warn>=%dF %s]: advisory-threshold days=%d  warning-threshold days=%d"
        % (r["county_name"], r["nws_office"], r["advisory_hi_f"], r["extreme_warning_hi_f"],
           r["verification_status"], r["adv_days"], r["warn_days"]))
log("\n[caveat] PROXY only: daily Tmax-RHmin HI, not hourly concurrent; no duration /")
log("         overnight-minimum / spatial-coverage rules; EWX & LUB thresholds approximate.")
