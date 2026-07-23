"""
DEFINITION 01 figures. Individual county records emphasized (no pooled headline).
  fig01  annual heatwave-days per county
  fig02  annual heatwave-events per county
  fig03  event-duration distribution (count of events by duration)
  fig04  county x month heatwave-days heatmap (2015-2025 total)
  fig05  85th-pctl mean-HI threshold by day-of-year, per county (2025 walk-forward)
  fig06  event timeline (Gantt) for one representative county
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(__file__)
TAB = os.path.abspath(os.path.join(HERE, "..", "tables"))
FIG = os.path.abspath(os.path.join(HERE, "..", "figures"))
os.makedirs(FIG, exist_ok=True)

plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 150, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 12, "axes.titleweight": "bold"})
SCOLOR = {"Harris (Houston)": "#4C72B0", "El Paso": "#DD8452", "Lubbock": "#55A868",
          "Travis (Austin)": "#C44E52", "Cameron (Brownsville)": "#8172B3"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DEF_TITLE = "Def 01: relative 85th-pctl daily-mean heat index, >=2 days, walk-forward (TX pilot)"

cy = pd.read_csv(os.path.join(TAB, "county_year_summary.csv"), dtype={"county_fips": str})
cm = pd.read_csv(os.path.join(TAB, "county_month_summary.csv"), dtype={"county_fips": str})
ev = pd.read_csv(os.path.join(TAB, "heatwave_events.csv"), dtype={"county_fips": str})
thr = pd.read_csv(os.path.join(TAB, "thresholds_walkforward_meanHI_doy.csv"), dtype={"county_fips": str})
ev["start_date"] = pd.to_datetime(ev["start_date"]); ev["end_date"] = pd.to_datetime(ev["end_date"])
counties = [c for c in SCOLOR if c in set(cy["county_name"])]


def save(fig, name, note=""):
    fig.tight_layout()
    if note:
        fig.text(0.005, -0.01, note, fontsize=7.5, color="#555", ha="left", va="top")
    p = os.path.join(FIG, name + ".png")
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  [fig]", name + ".png", flush=True)


# fig01 annual heatwave-days per county
fig, ax = plt.subplots(figsize=(9, 5))
for name in counties:
    g = cy[cy["county_name"] == name].sort_values("year")
    ax.plot(g["year"], g["heatwave_days"], marker="o", label=name, color=SCOLOR[name])
ax.set_xlabel("Year"); ax.set_ylabel("Heatwave days"); ax.set_title("Heatwave days per year, by county")
ax.legend(fontsize=8); ax.set_xticks(range(2015, 2026))
save(fig, "fig01_annual_heatwave_days_by_county", DEF_TITLE + " | heatwave day = county-date in a >=2-day run")

# fig02 annual events per county
fig, ax = plt.subplots(figsize=(9, 5))
for name in counties:
    g = cy[cy["county_name"] == name].sort_values("year")
    ax.plot(g["year"], g["heatwave_events"], marker="s", label=name, color=SCOLOR[name])
ax.set_xlabel("Year"); ax.set_ylabel("Heatwave events (onset-year)"); ax.set_title("Heatwave events per year, by county")
ax.legend(fontsize=8); ax.set_xticks(range(2015, 2026))
save(fig, "fig02_annual_events_by_county", DEF_TITLE + " | event counted in its onset year")

# fig03 event-duration distribution
fig, ax = plt.subplots(figsize=(9, 5))
maxd = int(ev["event_duration_days"].max())
bins = np.arange(2, maxd + 2) - 0.5
bottom = np.zeros(len(bins) - 1)
for name in counties:
    h, _ = np.histogram(ev[ev["county_name"] == name]["event_duration_days"], bins=bins)
    ax.bar(np.arange(2, maxd + 1), h, bottom=bottom, color=SCOLOR[name], label=name, width=0.85)
    bottom += h
ax.set_xlabel("Event duration (consecutive days)"); ax.set_ylabel("Number of heatwave events")
ax.set_title("Distribution of individual event durations")
ax.legend(fontsize=8)
save(fig, "fig03_event_duration_distribution",
     DEF_TITLE + " | each bar = count of real events of that exact duration (NOT a pooled average)")

# fig04 county x month heatwave-days heatmap (total 2015-2025)
piv = cm.groupby(["county_name", "month"])["heatwave_days"].sum().unstack(fill_value=0).reindex(counties)
piv = piv.reindex(columns=range(1, 13), fill_value=0)
fig, ax = plt.subplots(figsize=(10, 4.5))
im = ax.imshow(piv.values, aspect="auto", cmap="YlOrRd")
ax.set_xticks(range(12)); ax.set_xticklabels(MONTHS)
ax.set_yticks(range(len(counties))); ax.set_yticklabels(counties)
for i in range(len(counties)):
    for j in range(12):
        v = int(piv.values[i, j])
        if v:
            ax.text(j, i, v, ha="center", va="center", fontsize=7,
                    color="white" if v > piv.values.max() * 0.55 else "black")
ax.set_title("Total heatwave days by county and month (2015-2025)")
fig.colorbar(im, ax=ax, label="heatwave days", shrink=0.8)
save(fig, "fig04_county_month_heatmap", DEF_TITLE + " | heatwave days allocated to their actual calendar month")

# fig05 threshold by day-of-year (walk-forward for analysis year 2025)
fig, ax = plt.subplots(figsize=(9, 5))
t25 = thr[thr["analysis_year"] == 2025].copy()
t25["doy"] = pd.to_datetime(dict(year=2000, month=t25["calendar_month"], day=t25["calendar_day"])).dt.dayofyear
for name in counties:
    g = t25[t25["county_name"] == name].sort_values("doy")
    ax.plot(g["doy"], g["threshold_value_f"], label=name, color=SCOLOR[name], lw=1.3)
ax.set_xlabel("Day of year"); ax.set_ylabel("85th-pctl mean-HI threshold (F)")
ax.set_title("Walk-forward day-of-year threshold (analysis year 2025 = baseline 1979-2024)")
ax.legend(fontsize=8)
mid = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]
ax.set_xticks(mid); ax.set_xticklabels(MONTHS)
save(fig, "fig05_threshold_by_dayofyear", DEF_TITLE + " | county- and season-specific relative threshold")

# fig06 event timeline (Gantt) for Cameron (most events / longest)
target = "Cameron (Brownsville)"
sub = ev[ev["county_name"] == target].sort_values("start_date")
fig, ax = plt.subplots(figsize=(11, 5))
for _, e in sub.iterrows():
    y = e["start_date"].year
    doy0 = e["start_date"].dayofyear
    ax.barh(y, e["event_duration_days"], left=doy0, height=0.6, color=SCOLOR[target],
            edgecolor="white", lw=0.4)
ax.set_xlabel("Day of year"); ax.set_ylabel("Year")
ax.set_title("Individual heatwave events: %s" % target)
ax.set_yticks(range(2015, 2026)); ax.set_xticks(mid); ax.set_xticklabels(MONTHS)
ax.invert_yaxis()
save(fig, "fig06_event_timeline_cameron",
     DEF_TITLE + " | each bar = one real event (start -> start+duration); no averaging")

print("[done] 6 figures written to", FIG, flush=True)
