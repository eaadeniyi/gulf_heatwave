"""
STATEWIDE figures (254 counties) -- choropleth maps + distributions (per-county
line charts do not scale to 254 counties).

  fig_map01_heatwave_days_per_county_w15      choropleth, pooled 2015-2025
  fig_map02_heatwave_events_per_county_w15    choropleth, pooled
  fig_map03_pct_days_imputed_per_county       data-quality map (IDW coverage)
  fig_map04_nws_advisory_threshold_days       choropleth, pooled
  fig_dist01_heatwave_days_hist               distribution across counties
  fig_cmp01_w15_vs_month_scatter              per-county window comparison
  fig_map05_heatwave_days_by_year_w15         small-multiple maps per year (shared scale)
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TAB = os.path.abspath(os.path.join(HERE, "..", "tables"))
FIG = os.path.abspath(os.path.join(HERE, "..", "figures"))
os.makedirs(FIG, exist_ok=True)
SHP = os.path.join(ROOT, "data", "raw", "census", "county_shapefile", "tl_2020_us_county.shp")
plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 150, "font.size": 9})
YEARS = list(range(2015, 2026))
DEF = "Def 01: rel 85th-pctl daily-mean HI, >=2 days, walk-forward, IDW gap-filled (statewide TX)"


def log(*a):
    print(*a, flush=True)


tx = gpd.read_file(SHP)
tx = tx[tx["STATEFP"] == "48"].to_crs(3083)[["GEOID", "NAME", "geometry"]].rename(columns={"GEOID": "county_fips"})


def choropleth(values_by_fips, title, fname, cmap="YlOrRd", note="", vmin=None, vmax=None, label="value"):
    g = tx.merge(values_by_fips.rename("val").reset_index(), on="county_fips", how="left")
    fig, ax = plt.subplots(figsize=(9, 8))
    g.plot(column="val", cmap=cmap, linewidth=0.2, edgecolor="#888", ax=ax, legend=True,
           vmin=vmin, vmax=vmax, missing_kwds={"color": "#dddddd", "label": "no data"},
           legend_kwds={"label": label, "shrink": 0.6})
    ax.set_title(title, fontsize=12, fontweight="bold"); ax.axis("off")
    if note:
        fig.text(0.005, 0.02, note, fontsize=7.5, color="#555")
    fig.savefig(os.path.join(FIG, fname + ".png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)
    log("  [fig]", fname + ".png")


cy = pd.read_csv(os.path.join(TAB, "county_year_summary_w15.csv"), dtype={"county_fips": str})
pool = cy.groupby("county_fips").agg(days=("heatwave_days", "sum"), events=("heatwave_events_started", "sum")).reset_index()
pool = pool.set_index("county_fips")

choropleth(pool["days"], "Heatwave DAYS per county, 2015-2025 (centered 15-day window)",
           "fig_map01_heatwave_days_per_county_w15",
           note=DEF + " | heatwave day = county-date in a >=2-day run | grey = no data", label="heatwave days (11-yr total)")
choropleth(pool["events"], "Heatwave EVENTS per county, 2015-2025 (centered 15-day window)",
           "fig_map02_heatwave_events_per_county_w15",
           note=DEF + " | one event = one uninterrupted run in one county", label="heatwave events (11-yr total)")

# data-quality: % of analysis days IDW-imputed
cov = pd.read_csv(os.path.join(TAB, "coverage_and_imputation_report.csv"), dtype={"county_fips": str}).set_index("county_fips")
choropleth(cov["pct_analysis_days_imputed"], "Data quality: percent of 2015-2025 county-days IDW-imputed",
           "fig_map03_pct_days_imputed_per_county", cmap="Purples",
           note="Counties in darker purple rely more on inverse-distance-weighted interpolation from neighbours (no/low native station data)",
           label="% analysis days imputed")

# NWS advisory-threshold days per county (pooled)
ny = pd.read_csv(os.path.join(TAB, "nws_proxy_county_year.csv"), dtype={"county_fips": str})
nyp = ny.groupby("county_fips")["advisory_threshold_days"].sum()
choropleth(nyp, "NWS advisory-threshold PROXY days per county, 2015-2025",
           "fig_map04_nws_advisory_threshold_days", cmap="OrRd",
           note="PROXY (daily max-HI vs local office threshold); NOT official advisories; nearest-office crosswalk + mostly-approximate thresholds",
           label="advisory-threshold days (11-yr total)")

# distribution of per-county heatwave days
fig, ax = plt.subplots(figsize=(9, 5))
ax.hist(pool["days"], bins=30, color="#C44E52", edgecolor="white")
ax.set_xlabel("Heatwave days per county (2015-2025 total)"); ax.set_ylabel("Number of counties")
ax.set_title("Distribution of per-county heatwave-day totals (254 counties)")
ax.axvline(pool["days"].median(), color="k", ls="--", lw=1, label="median=%.0f" % pool["days"].median())
ax.legend()
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_dist01_heatwave_days_hist.png"), bbox_inches="tight", facecolor="white")
plt.close(fig); log("  [fig] fig_dist01_heatwave_days_hist.png")

# window comparison scatter (w15 vs month), per county
cym = pd.read_csv(os.path.join(TAB, "county_year_summary_month.csv"), dtype={"county_fips": str})
poolm = cym.groupby("county_fips")["heatwave_days"].sum()
cmp = pd.DataFrame({"w15": pool["days"], "month": poolm}).dropna()
fig, ax = plt.subplots(figsize=(6.5, 6.5))
ax.scatter(cmp["w15"], cmp["month"], s=12, alpha=0.6, color="#4C72B0")
lim = [0, max(cmp.max()) * 1.05]
ax.plot(lim, lim, "k--", lw=1, label="1:1")
ax.set_xlabel("Heatwave days per county (15-day window)"); ax.set_ylabel("Heatwave days per county (month bucket)")
ax.set_title("Threshold-window agreement, per county (2015-2025)"); ax.legend()
ax.set_xlim(lim); ax.set_ylim(lim)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_cmp01_w15_vs_month_scatter.png"), bbox_inches="tight", facecolor="white")
plt.close(fig); log("  [fig] fig_cmp01_w15_vs_month_scatter.png")

# small-multiple maps per year (shared scale)
peryr = cy.set_index(["county_fips", "year"])["heatwave_days"]
vmax = int(cy["heatwave_days"].max())
fig, axes = plt.subplots(3, 4, figsize=(16, 11)); axes = axes.ravel()
im = None
for k, yr in enumerate(YEARS):
    ax = axes[k]
    vals = peryr.xs(yr, level="year") if yr in cy["year"].values else pd.Series(dtype=float)
    g = tx.merge(vals.rename("val").reset_index(), on="county_fips", how="left")
    g.plot(column="val", cmap="YlOrRd", vmin=0, vmax=vmax, linewidth=0.1, edgecolor="#999", ax=ax,
           missing_kwds={"color": "#dddddd"})
    ax.set_title(str(yr), fontsize=11); ax.axis("off")
axes[11].axis("off")
sm = plt.cm.ScalarMappable(cmap="YlOrRd", norm=plt.Normalize(vmin=0, vmax=vmax))
fig.colorbar(sm, ax=axes[11], shrink=0.7, label="heatwave days/yr (shared scale 0-%d)" % vmax)
fig.suptitle("Heatwave days per county, BY YEAR (shared scale) [centered 15-day window]", fontsize=13, fontweight="bold")
fig.savefig(os.path.join(FIG, "fig_map05_heatwave_days_by_year_w15.png"), bbox_inches="tight", facecolor="white")
plt.close(fig); log("  [fig] fig_map05_heatwave_days_by_year_w15.png")

log("[done] statewide figures complete")
