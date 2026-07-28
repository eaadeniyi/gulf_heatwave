"""
Generate CALENDAR-MONTH threshold-window figures for both definitions (mirrors the
centered-15-day figure set, which was already produced). Saved with a '_month'
suffix in each definition's figures/ folder so the two windows sit side by side.
Reads the *_month.csv outputs (which the pipeline already produced).
"""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "texas_heatwave_pilot", "outputs", "TX")
SHP = os.path.join(ROOT, "data", "raw", "census", "county_shapefile", "tl_2020_us_county.shp")
DEFS = {"Definition 01 (85th pctl)": ("def_p85_2d", "#4C72B0"),
        "Definition 02 (95th pctl)": ("def_p95_2d", "#C44E52")}
YEARS = list(range(2015, 2026))
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 150, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 12, "axes.titleweight": "bold"})


def L(*a): print(*a, flush=True)


tx = gpd.read_file(SHP)
tx = tx[tx["STATEFP"] == "48"].to_crs(5070)[["GEOID", "geometry"]].rename(columns={"GEOID": "county_fips"})

for name, (ddir, color) in DEFS.items():
    tdir = os.path.join(OUT, ddir, "tables")
    fdir = os.path.join(OUT, ddir, "figures")
    cy = pd.read_csv(os.path.join(tdir, "county_year_summary_month.csv"), dtype={"county_fips": str})
    ev = pd.read_csv(os.path.join(tdir, "heatwave_events_month.csv"), dtype={"county_fips": str})
    hd = pd.read_csv(os.path.join(tdir, "daily_heatwave_days_month.csv"), dtype={"county_fips": str})
    percty = cy.groupby(["county_fips", "county_name"])["heatwave_days"].sum().reset_index()
    L("\n===", name, "(calendar-month window) ===")

    # choropleth heatwave days per county
    ser = percty.set_index("county_fips")["heatwave_days"]
    g = tx.merge(ser.rename("val").reset_index(), on="county_fips", how="left")
    fig, ax = plt.subplots(figsize=(9, 8))
    g.plot(column="val", cmap="YlOrRd", linewidth=0.2, edgecolor="#888", ax=ax, legend=True,
           missing_kwds={"color": "#ddd"}, legend_kwds={"label": "heatwave days (2015-2025 total)", "shrink": 0.6})
    ax.set_title("%s — heatwave days per county [CALENDAR-MONTH window]" % name, fontsize=12, fontweight="bold"); ax.axis("off")
    fig.text(0.005, 0.02, "Calendar-month threshold window (robustness). Near-identical to the centered-15-day map (r~=0.99). Regional gradient is the reliable signal.", fontsize=7.5, color="#555")
    fig.savefig(os.path.join(fdir, "map01_heatwave_days_per_county_month.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)

    # annual statewide
    fig, ax = plt.subplots(figsize=(9, 5))
    by = cy.groupby("year")["heatwave_days"].sum().reindex(YEARS, fill_value=0)
    ax.bar(YEARS, by.values, color=color)
    ax.set_xticks(YEARS); ax.set_xlabel("Year"); ax.set_ylabel("Heatwave county-days (statewide)")
    ax.set_title("%s — statewide heatwave days per year [CALENDAR-MONTH window]" % name)
    fig.tight_layout(); fig.savefig(os.path.join(fdir, "res_annual_days_month.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)

    # event duration
    dur = ev["event_duration_days"]
    fig, ax = plt.subplots(figsize=(9, 5))
    md = 15; h, _ = np.histogram(dur.clip(upper=md), bins=np.arange(2, md + 2) - 0.5)
    ax.bar(np.arange(2, md + 1), 100 * h / h.sum(), color=color)
    ax.set_xlabel("Event duration (consecutive days; 15 = 15+)"); ax.set_ylabel("% of events")
    ax.set_title("%s — event durations [CALENDAR-MONTH window] (median %.0f d, max %d d)" % (name, dur.median(), dur.max()))
    fig.tight_layout(); fig.savefig(os.path.join(fdir, "res_event_duration_month.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)

    # seasonal
    fig, ax = plt.subplots(figsize=(9, 5))
    bymon = hd.groupby("month").size().reindex(range(1, 13), fill_value=0)
    js = round(100 * hd["month"].isin([6, 7, 8, 9]).mean(), 0)
    bars = ax.bar(range(1, 13), 100 * bymon.values / bymon.sum(), color=color)
    for m in [6, 7, 8, 9]:
        bars[m - 1].set_edgecolor("black"); bars[m - 1].set_linewidth(1.5)
    ax.set_xticks(range(1, 13)); ax.set_xticklabels(MONTHS); ax.set_ylabel("% of heatwave days")
    ax.set_title("%s — when heatwave days fall [CALENDAR-MONTH window] (%.0f%% in Jun-Sep)" % (name, js))
    fig.tight_layout(); fig.savefig(os.path.join(fdir, "res_seasonal_month.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)

    # top-15 counties
    fig, ax = plt.subplots(figsize=(9, 6))
    top = percty.nlargest(15, "heatwave_days").sort_values("heatwave_days")
    ax.barh(top["county_name"], top["heatwave_days"], color=color)
    ax.set_xlabel("Heatwave days (2015-2025 total)"); ax.set_title("%s — top 15 counties by heatwave days [CALENDAR-MONTH window]" % name)
    fig.tight_layout(); fig.savefig(os.path.join(fdir, "res_top_counties_month.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)
    L("  wrote 5 month-window figures ->", fdir)

L("\n[done] calendar-month window figures generated for both definitions")
