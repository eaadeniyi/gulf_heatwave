"""
Head-to-head comparison of Definition 01 (85th pctl) vs Definition 02 (95th pctl),
statewide Texas, both computed by the SAME generalized pipeline. Produces:
  * a ground-truth stats file (comparison_stats.json + .md) used downstream, and
  * meaningful comparison figures.
"""
import os, sys, json
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUTBASE = os.path.join(ROOT, "texas_heatwave_pilot", "outputs", "TX")
FIG = os.path.join(HERE, "comparison_figures"); os.makedirs(FIG, exist_ok=True)
SHP = os.path.join(ROOT, "data", "raw", "census", "county_shapefile", "tl_2020_us_county.shp")
DEFS = {"Def 01 (85th)": "def_p85_2d", "Def 02 (95th)": "def_p95_2d"}
CDEF = {"Def 01 (85th)": "#4C72B0", "Def 02 (95th)": "#C44E52"}
YEARS = list(range(2015, 2026))
plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 150, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 12, "axes.titleweight": "bold"})


def L(*a): print(*a, flush=True)


def load(defdir, name):
    d = os.path.join(OUTBASE, defdir, "tables")
    return {
        "cy": pd.read_csv(os.path.join(d, "county_year_summary_%s.csv" % ("w15")), dtype={"county_fips": str}),
        "cy_m": pd.read_csv(os.path.join(d, "county_year_summary_month.csv"), dtype={"county_fips": str}),
        "ev": pd.read_csv(os.path.join(d, "heatwave_events_w15.csv"), dtype={"county_fips": str}),
        "cm": pd.read_csv(os.path.join(d, "county_month_summary_w15.csv"), dtype={"county_fips": str}),
        "hd": pd.read_csv(os.path.join(d, "daily_heatwave_days_w15.csv"), dtype={"county_fips": str}),
    }

data = {k: load(v, k) for k, v in DEFS.items()}
stats = {}

# ---------- headline numbers ----------
for name, dd in data.items():
    cy = dd["cy"]; ev = dd["ev"]
    pool = cy.groupby("county_fips").agg(d=("heatwave_days", "sum"), e=("heatwave_events_started", "sum"))
    stats[name] = {
        "pooled_heatwave_days_w15": int(cy["heatwave_days"].sum()),
        "pooled_events_w15": int(cy["heatwave_events_started"].sum()),
        "per_county_days_median": float(pool["d"].median()),
        "per_county_days_min": int(pool["d"].min()),
        "per_county_days_max": int(pool["d"].max()),
        "event_duration_median": float(dd["ev"]["event_duration_days"].median()),
        "event_duration_mean": round(float(dd["ev"]["event_duration_days"].mean()), 2),
        "event_duration_max": int(dd["ev"]["event_duration_days"].max()),
        "pct_events_ge5d": round(100 * (dd["ev"]["event_duration_days"] >= 5).mean(), 1),
        "pct_events_2d": round(100 * (dd["ev"]["event_duration_days"] == 2).mean(), 1),
    }
    L(name, stats[name])

# ratio 95/85
r_days = stats["Def 02 (95th)"]["pooled_heatwave_days_w15"] / stats["Def 01 (85th)"]["pooled_heatwave_days_w15"]
r_ev = stats["Def 02 (95th)"]["pooled_events_w15"] / stats["Def 01 (85th)"]["pooled_events_w15"]
stats["ratio_def02_over_def01"] = {"heatwave_days": round(r_days, 3), "events": round(r_ev, 3)}

# ---------- FIG 1: annual statewide heatwave-days, both defs ----------
fig, ax = plt.subplots(figsize=(10, 5.5))
x = np.arange(len(YEARS)); w = 0.4
for i, (name, dd) in enumerate(data.items()):
    by = dd["cy"].groupby("year")["heatwave_days"].sum().reindex(YEARS, fill_value=0)
    ax.bar(x + (i - 0.5) * w, by.values, width=w, label=name, color=CDEF[name])
ax.set_xticks(x); ax.set_xticklabels(YEARS); ax.set_xlabel("Year")
ax.set_ylabel("Statewide heatwave county-days (QA pooled)")
ax.set_title("Statewide heatwave days per year: Definition 01 vs 02 (Texas, 254 counties)")
ax.legend()
fig.text(0.005, -0.02, "Heatwave day = one county on one date inside a >=2-day run (centered 15-day window). Pooled statewide totals shown for scale (QA).",
         fontsize=7.5, color="#555")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "cmp01_annual_statewide_days.png"), bbox_inches="tight", facecolor="white")
plt.close(fig); L("[fig] cmp01_annual_statewide_days.png")

# ---------- FIG 2: distribution of per-county heatwave-days (overlaid) ----------
fig, ax = plt.subplots(figsize=(10, 5.5))
for name, dd in data.items():
    pool = dd["cy"].groupby("county_fips")["heatwave_days"].sum()
    ax.hist(pool.values, bins=30, alpha=0.55, label="%s (median %.0f)" % (name, pool.median()), color=CDEF[name])
ax.set_xlabel("Heatwave days per county (2015-2025 total)"); ax.set_ylabel("Number of counties")
ax.set_title("How many heatwave days each county gets: Def 01 vs 02")
ax.legend()
fig.tight_layout(); fig.savefig(os.path.join(FIG, "cmp02_percounty_day_distribution.png"), bbox_inches="tight", facecolor="white")
plt.close(fig); L("[fig] cmp02_percounty_day_distribution.png")

# ---------- FIG 3: event-duration distribution ----------
fig, ax = plt.subplots(figsize=(10, 5.5))
maxd = 15
bins = np.arange(2, maxd + 2) - 0.5
for name, dd in data.items():
    h, _ = np.histogram(dd["ev"]["event_duration_days"].clip(upper=maxd), bins=bins)
    ax.plot(np.arange(2, maxd + 1), 100 * h / h.sum(), marker="o", label=name, color=CDEF[name])
ax.set_xlabel("Event duration (consecutive days; 15 = 15+)"); ax.set_ylabel("% of events")
ax.set_title("Event-duration distribution: Def 01 vs 02 (stricter percentile -> shorter events)")
ax.legend()
fig.tight_layout(); fig.savefig(os.path.join(FIG, "cmp03_event_duration_distribution.png"), bbox_inches="tight", facecolor="white")
plt.close(fig); L("[fig] cmp03_event_duration_distribution.png")

# ---------- FIG 4: seasonal distribution (heatwave days by month) ----------
fig, ax = plt.subplots(figsize=(10, 5.5))
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
for name, dd in data.items():
    bymon = dd["hd"].groupby("month").size().reindex(range(1, 13), fill_value=0)
    ax.plot(range(1, 13), 100 * bymon.values / bymon.sum(), marker="s", label=name, color=CDEF[name])
ax.set_xticks(range(1, 13)); ax.set_xticklabels(MONTHS); ax.set_ylabel("% of heatwave days")
ax.set_title("When heatwave days fall (seasonal share): Def 01 vs 02")
ax.legend()
# annotate the summer share
for name, dd in data.items():
    js = dd["hd"]["month"].isin([6,7,8,9]).mean()
    stats[name]["pct_days_junsep"] = round(100 * js, 1)
fig.text(0.005, -0.02, "Both are year-round RELATIVE definitions; a substantial share of days fall outside Jun-Sep (cool-season anomalies).",
         fontsize=7.5, color="#555")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "cmp04_seasonal_distribution.png"), bbox_inches="tight", facecolor="white")
plt.close(fig); L("[fig] cmp04_seasonal_distribution.png")

# ---------- FIG 5: per-county scatter Def01 vs Def02 ----------
p1 = data["Def 01 (85th)"]["cy"].groupby("county_fips")["heatwave_days"].sum().rename("d85")
p2 = data["Def 02 (95th)"]["cy"].groupby("county_fips")["heatwave_days"].sum().rename("d95")
m = pd.concat([p1, p2], axis=1).dropna()
corr = m["d85"].corr(m["d95"])
stats["percounty_corr_def01_def02"] = round(float(corr), 3)
fig, ax = plt.subplots(figsize=(6.6, 6.6))
ax.scatter(m["d85"], m["d95"], s=12, alpha=0.5, color="#555")
ax.set_xlabel("Def 01 (85th) heatwave days per county"); ax.set_ylabel("Def 02 (95th) heatwave days per county")
ax.set_title("Per-county: Def 01 vs Def 02 (r=%.2f)" % corr)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "cmp05_percounty_scatter.png"), bbox_inches="tight", facecolor="white")
plt.close(fig); L("[fig] cmp05_percounty_scatter.png")

# ---------- FIG 6: choropleth pair (Def01, Def02) heatwave-days per county ----------
tx = gpd.read_file(SHP); tx = tx[tx["STATEFP"] == "48"].to_crs(5070)[["GEOID","geometry"]].rename(columns={"GEOID":"county_fips"})
fig, axes = plt.subplots(1, 2, figsize=(15, 7))
vmax = int(m["d85"].max())
for ax, (name, series) in zip(axes, [("Def 01 (85th)", p1), ("Def 02 (95th)", p2)]):
    g = tx.merge(series.rename("val").reset_index(), on="county_fips", how="left")
    g.plot(column="val", cmap="YlOrRd", vmin=0, vmax=vmax, linewidth=0.15, edgecolor="#999", ax=ax,
           missing_kwds={"color":"#ddd"})
    ax.set_title("%s  heatwave days/county, 2015-2025" % name, fontsize=12, fontweight="bold"); ax.axis("off")
sm = plt.cm.ScalarMappable(cmap="YlOrRd", norm=plt.Normalize(0, vmax))
fig.colorbar(sm, ax=axes, shrink=0.5, label="heatwave days (11-yr total, shared scale)")
fig.suptitle("Where heatwave days occur -- same shared scale (Def 02 is sparser by construction)", fontsize=13, fontweight="bold")
fig.savefig(os.path.join(FIG, "cmp06_choropleth_pair.png"), bbox_inches="tight", facecolor="white")
plt.close(fig); L("[fig] cmp06_choropleth_pair.png")

# ---------- example events (top by duration & peak) from each def ----------
for name, dd in data.items():
    ev = dd["ev"].copy()
    top = ev.nlargest(3, "event_duration_days")[["event_label","county_name","start_date","end_date","event_duration_days","peak_mean_hi_f"]]
    stats[name]["longest_events_example"] = top.to_dict("records")

# window agreement (w15 vs month) per def
for name, defdir in DEFS.items():
    d = os.path.join(OUTBASE, defdir, "tables")
    a = pd.read_csv(os.path.join(d, "county_year_summary_w15.csv"), dtype={"county_fips": str}).groupby("county_fips")["heatwave_days"].sum()
    b = pd.read_csv(os.path.join(d, "county_year_summary_month.csv"), dtype={"county_fips": str}).groupby("county_fips")["heatwave_days"].sum()
    mm = pd.concat([a.rename("w"), b.rename("m")], axis=1).dropna()
    stats[name]["window_w15_vs_month_corr"] = round(float(mm["w"].corr(mm["m"])), 3)
    stats[name]["pooled_days_month"] = int(b.sum())

json.dump(stats, open(os.path.join(HERE, "comparison_stats.json"), "w"), indent=2, default=str)
L("\n[done] wrote comparison_stats.json + 6 figures")
L(json.dumps({k: v for k, v in stats.items() if k.startswith("Def") or k.startswith("ratio") or "corr" in k}, indent=2, default=str)[:1500])
