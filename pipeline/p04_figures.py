"""
=============================================================================
STEP p04  --  figures, per state and per definition (percentile).
=============================================================================
At statewide scale a state can have hundreds of counties, so per-county line
charts are unreadable -- the primary figures are CHOROPLETH MAPS plus
distributions. All figures are state-agnostic: the state's counties are pulled
from the shapefile by FIPS, titles use the state name from config.

Produced per (state, percentile), for the centered-window definition:
  map01  heatwave DAYS per county (pooled analysis period)
  map02  heatwave EVENTS per county (pooled)
  map03  data-quality: % of county-days IDW-imputed
  map04  NWS advisory-threshold PROXY days per county   (if the NWS step ran)
  dist01 distribution of per-county heatwave-day totals
  map05  heatwave days per county BY YEAR (small multiples, shared color scale)
=============================================================================
"""
import os, sys
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

PRIMARY_WINDOW = "w15"          # the centered window is the primary for maps


def log(*a):
    print(*a, flush=True)


def run_state_percentile(state, pctl):
    fips = C.STATE_FIPS[state]
    sname = C.STATE_NAME.get(state, state)
    ddir = C.definition_output_dir(state, pctl)
    tdir = os.path.join(ddir, "tables")
    fdir = os.path.join(ddir, "figures")
    sdir = C.state_output_dir(state)
    subtitle = "%s | rel %dth-pctl daily-mean HI, >=%d days, walk-forward, IDW gap-filled" % (sname, pctl, C.MIN_DURATION)
    log("p04  figures  --  state=%s percentile=%d" % (state, pctl))

    # state county polygons (equal-area for mapping)
    tx = gpd.read_file(C.COUNTY_SHAPEFILE)
    tx = tx[tx["STATEFP"] == fips].to_crs(C.EQUAL_AREA_CRS)[["GEOID", "geometry"]].rename(columns={"GEOID": "county_fips"})

    def choropleth(series, title, fname, cmap="YlOrRd", label="value", note="", vmax=None):
        g = tx.merge(series.rename("val").reset_index(), on="county_fips", how="left")
        fig, ax = plt.subplots(figsize=(9, 8))
        g.plot(column="val", cmap=cmap, linewidth=0.2, edgecolor="#888", ax=ax, legend=True, vmax=vmax,
               missing_kwds={"color": "#dddddd", "label": "no data"},
               legend_kwds={"label": label, "shrink": 0.6})
        ax.set_title(title, fontsize=12, fontweight="bold"); ax.axis("off")
        if note:
            fig.text(0.005, 0.02, note, fontsize=7.5, color="#555")
        fig.savefig(os.path.join(fdir, fname + ".png"), bbox_inches="tight", facecolor="white")
        plt.close(fig); log("  [fig]", fname + ".png")

    cy = pd.read_csv(os.path.join(tdir, "county_year_summary_%s.csv" % PRIMARY_WINDOW), dtype={"county_fips": str})
    pool = cy.groupby("county_fips").agg(days=("heatwave_days", "sum"),
                                         events=("heatwave_events_started", "sum")).reset_index().set_index("county_fips")
    choropleth(pool["days"], "Heatwave DAYS per county, %d-%d" % C.ANALYSIS_YEARS,
               "map01_heatwave_days_per_county", label="heatwave days (period total)",
               note=subtitle + " | grey = no data")
    choropleth(pool["events"], "Heatwave EVENTS per county, %d-%d" % C.ANALYSIS_YEARS,
               "map02_heatwave_events_per_county", label="heatwave events (period total)", note=subtitle)

    cov = pd.read_csv(os.path.join(sdir, "coverage_and_imputation_report.csv"),
                      dtype={"county_fips": str}).set_index("county_fips")
    choropleth(cov["pct_analysis_days_imputed"], "Data quality: percent of county-days IDW-imputed",
               "map03_pct_days_imputed_per_county", cmap="Purples", label="% analysis days imputed",
               note="Darker = more reliance on inverse-distance interpolation from neighbours")

    nws_path = os.path.join(sdir, "nws_proxy_county_year.csv")
    if os.path.exists(nws_path):
        ny = pd.read_csv(nws_path, dtype={"county_fips": str})
        choropleth(ny.groupby("county_fips")["advisory_threshold_days"].sum(),
                   "NWS advisory-threshold PROXY days per county, %d-%d" % C.ANALYSIS_YEARS,
                   "map04_nws_advisory_threshold_days", cmap="OrRd", label="advisory-threshold days (period total)",
                   note="PROXY (daily max-HI vs local office threshold); NOT official advisories; approximate crosswalk")

    # distribution of per-county heatwave days
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(pool["days"], bins=30, color="#C44E52", edgecolor="white")
    ax.axvline(pool["days"].median(), color="k", ls="--", lw=1, label="median=%.0f" % pool["days"].median())
    ax.set_xlabel("Heatwave days per county (%d-%d total)" % C.ANALYSIS_YEARS)
    ax.set_ylabel("Number of counties"); ax.set_title("Per-county heatwave-day totals (%d counties)" % len(pool))
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(fdir, "dist01_heatwave_days_hist.png"), bbox_inches="tight", facecolor="white")
    plt.close(fig); log("  [fig] dist01_heatwave_days_hist.png")

    # per-year small-multiple maps (shared scale)
    peryr = cy.set_index(["county_fips", "year"])["heatwave_days"]
    yrs = list(range(C.ANALYSIS_YEARS[0], C.ANALYSIS_YEARS[1] + 1))
    vmax = int(cy["heatwave_days"].max())
    ncol = 4; nrow = int(np.ceil(len(yrs) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 3.6 * nrow)); axes = np.array(axes).ravel()
    for k, yr in enumerate(yrs):
        ax = axes[k]
        vals = peryr.xs(yr, level="year") if yr in cy["year"].values else pd.Series(dtype=float)
        g = tx.merge(vals.rename("val").reset_index(), on="county_fips", how="left")
        g.plot(column="val", cmap="YlOrRd", vmin=0, vmax=vmax, linewidth=0.1, edgecolor="#999", ax=ax,
               missing_kwds={"color": "#dddddd"})
        ax.set_title(str(yr), fontsize=11); ax.axis("off")
    for k in range(len(yrs), len(axes)):
        axes[k].axis("off")
    sm = plt.cm.ScalarMappable(cmap="YlOrRd", norm=plt.Normalize(vmin=0, vmax=vmax))
    fig.colorbar(sm, ax=axes[len(yrs) - 1] if len(yrs) == len(axes) else axes[-1], shrink=0.7,
                 label="heatwave days/yr (shared scale 0-%d)" % vmax)
    fig.suptitle("Heatwave days per county BY YEAR (shared scale) -- %s" % subtitle, fontsize=12, fontweight="bold")
    fig.savefig(os.path.join(fdir, "map05_heatwave_days_by_year.png"), bbox_inches="tight", facecolor="white")
    plt.close(fig); log("  [fig] map05_heatwave_days_by_year.png")


if __name__ == "__main__":
    for st in C.STATES:
        for p in C.PERCENTILES:
            run_state_percentile(st, p)
