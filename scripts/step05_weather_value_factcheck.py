"""
Weather-value fact-check audit (spec Part C Step 1 + Part J Step 24).

REVISION 2026-07-16 (review Issue 2): the QC flags + three-level qc_status are
now computed once in step01 and stored in 05_county_daily_heat.csv. This script
consumes them, writes the flagged-records file (renamed from "invalid" to
"suspicious", since these are implausible-but-not-impossible, per the review),
and produces the audit summary. It does NOT recompute the flags, so there is a
single source of truth.

Output: tables/quality_control/02_suspicious_meteorological_values.csv
        tables/quality_control/02_suspicious_summary.md
"""
import os
import numpy as np
import pandas as pd

ROOT = r"C:\Users\eadeni1\OneDrive - Louisiana State University\Documents\doc\heatWaveUS"
PILOT = os.path.join(ROOT, "texas_heatwave_pilot")
TAB = os.path.join(PILOT, "tables")
QC = os.path.join(TAB, "quality_control")
HI_COL = "derived_tmax_rhmin_hi_proxy_f"

SOFT_FLAGS = ["qc_zero_diurnal_rh_range", "qc_rh_pinned_at_100",
              "qc_tiny_diurnal_temp_range", "qc_hi_jump_unexplained_by_tmax"]
HARD_FLAGS = ["qc_tmax_lt_tmin", "qc_rh_oob", "qc_rmin_gt_rmax"]
PIN_SUBFLAGS = ["qc_rh_pin_likely_artifact", "qc_rh_pin_likely_real_wet"]

lines = []
def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    lines.append(s)


log("=" * 70)
log("Weather-value fact-check audit (consumes step01 qc_status; review Issue 2)")
log("=" * 70)

d = pd.read_csv(os.path.join(TAB, "05_county_daily_heat.csv"), dtype={"county_fips": str})
d["date"] = pd.to_datetime(d["date"])

log("\n[qc_status distribution across all %d county-days]" % len(d))
for k, v in d["qc_status"].value_counts().items():
    log("  %-18s %d (%.4f%%)" % (k, v, 100 * v / len(d)))

log("\n[soft-QC flag frequencies -- implausible but not physically impossible]")
for f in SOFT_FLAGS:
    log("  %-32s %d" % (f, int(d[f].sum())))

# PRCP-aware pin sub-classification (R2 workflow investigation)
if "qc_rh_pin_likely_artifact" in d.columns:
    log("\n[RH=100 pin sub-classification via independent GHCN precipitation cross-check]")
    log("  likely_artifact (warm+dry, PRCP~=0, Tmax>=80F): %d -- these SPURIOUSLY inflate the HI proxy"
        % int(d["qc_rh_pin_likely_artifact"].sum()))
    log("  likely_real_wet (PRCP>=0.01in):                 %d -- genuine saturation, physically defensible"
        % int(d["qc_rh_pin_likely_real_wet"].sum()))
    art = d[d["qc_rh_pin_likely_artifact"]]
    if len(art):
        log("  confirmed-artifact days (all pinned RH=100 on rain-free warm days):")
        for _, r in art.iterrows():
            log("    %-22s %s  Tmax=%.1f  proxy_HI=%.1f (inflated)" %
                (r["county_name"], str(r["date"])[:10], r["tmax_f"], r["derived_tmax_rhmin_hi_proxy_f"]))
log("[hard-QC flag frequencies -- physically impossible, field set to NaN]")
for f in HARD_FLAGS:
    log("  %-32s %d" % (f, int(d[f].sum())))

# concentration check: do the RH-pinned dates hit multiple counties at once
# (points to a real shared regional weather event, not a per-file glitch)?
pinned = d[d["qc_rh_pinned_at_100"]]
by_date = pinned.groupby("date")["county_fips"].nunique().sort_values(ascending=False)
log("\n[rh_pinned_at_100 dates affecting >1 county simultaneously]")
log(by_date[by_date > 1].to_string())

# ---- row-level RH=100-pin classification (review R3 Issue 4) ----
# every pinned record gets an explicit disposition, using GHCN precipitation (an
# INDEPENDENT source from the pinned gridMET RH) plus temperature as the basis.
pin = d["qc_rh_pinned_at_100"]
d["rh_pin_class"] = np.select(
    [d.get("qc_rh_pin_likely_artifact", False) & pin,
     d.get("qc_rh_pin_likely_real_wet", False) & pin,
     pin],
    ["confirmed_artifact", "likely_real_wet", "indeterminate"],
    default="not_applicable")
d["verification_basis"] = np.select(
    [d["rh_pin_class"] == "confirmed_artifact",
     d["rh_pin_class"] == "likely_real_wet",
     d["rh_pin_class"] == "indeterminate"],
    ["precipitation~=0 + Tmax>=80F (warm dry -> saturation impossible)",
     "precipitation>=0.01in (genuine wet-day saturation)",
     "pinned but neither warm-dry nor wet (cold-dry or precip missing)"],
    default="n/a")
d["recommended_action"] = np.select(
    [d["rh_pin_class"] == "confirmed_artifact",
     d["rh_pin_class"] == "likely_real_wet",
     d["rh_pin_class"] == "indeterminate"],
    ["set_missing_or_correct", "retain", "manual_review"], default="n/a")

n_art = int((d["rh_pin_class"] == "confirmed_artifact").sum())
n_wet = int((d["rh_pin_class"] == "likely_real_wet").sum())
n_ind = int((d["rh_pin_class"] == "indeterminate").sum())
log("\n[RH=100 pin row-level disposition] confirmed_artifact=%d  likely_real_wet=%d  indeterminate=%d  (total pins=%d)"
    % (n_art, n_wet, n_ind, int(pin.sum())))

flagged = d[d["qc_status"].isin(["suspicious_retain", "missing_input", "invalid_physical"])][
    ["county_fips", "county_name", "date", "tmax_f", "tmin_f", "prcp_in", "rmax_pct", "rmin_pct",
     HI_COL, "qc_status", "rh_pin_class", "verification_basis", "recommended_action"]
    + HARD_FLAGS + SOFT_FLAGS + [c for c in PIN_SUBFLAGS if c in d.columns]]
out_path = os.path.join(QC, "02_suspicious_meteorological_values.csv")
flagged.to_csv(out_path, index=False)
log("[done] wrote %s rows=%d" % (out_path, len(flagged)))

# remove the old misnamed file if present
old = os.path.join(QC, "02_invalid_meteorological_values.csv")
if os.path.exists(old):
    os.remove(old)
    log("[cleanup] removed old-misnamed 02_invalid_meteorological_values.csv")

with open(os.path.join(QC, "02_suspicious_summary.md"), "w", encoding="utf-8") as f:
    f.write("# Suspicious meteorological values -- audit summary (revised 2026-07-16)\n\n")
    f.write("Renamed from '02_invalid...' because these records are IMPLAUSIBLE, not\n")
    f.write("strictly impossible. They are retained (`suspicious_retain`) and flagged,\n")
    f.write("never silently dropped. Downstream, step03 also produces a sensitivity\n")
    f.write("event table with these set to missing, so their influence is quantified.\n\n")
    f.write("## RH=100 pin row-level disposition (review R3 Issue 4)\n\n")
    f.write("Each pinned record now carries rh_pin_class / verification_basis / "
            "recommended_action columns in the CSV. Of %d total pins in the 5 pilot counties:\n\n" % int(pin.sum()))
    f.write("- **%d confirmed_artifact** (warm + rain-free): recommended set_missing/correct. "
            "These are the 2023-03-01 records that inflate the proxy 15-24F.\n" % n_art)
    f.write("- **%d likely_real_wet** (measurable precip): genuine saturation, recommended retain.\n" % n_wet)
    f.write("- **%d indeterminate**: pinned but neither warm-dry nor wet -- i.e. cold/cool dry days "
            "or days with precip missing. These do NOT sit in warm-season events and are flagged "
            "for manual_review rather than auto-dropped, since fog/moisture can pin RH without "
            "measurable precipitation.\n\n" % n_ind)
    f.write("Note: only the %d confirmed_artifact records are removed from the PRIMARY analysis "
            "(step03); the retain-all sensitivity keeps them.\n\n" % n_art)
    f.write("\n".join("    " + l for l in lines) + "\n")
log("[done] wrote 02_suspicious_summary.md")
