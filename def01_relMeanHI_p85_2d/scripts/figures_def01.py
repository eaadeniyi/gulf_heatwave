"""
DEFINITION 01 figures (revised). Produced for BOTH threshold windows
(w15 = centered 15-day-total +/-7 ; month = calendar-month bucket), reported
alongside each other. Event durations shown as DISTRIBUTIONS / individual events
(never a pooled average). fig04 is separated BY YEAR with a shared color scale.

Per window <W>:
  fig01_<W>_annual_heatwave_days_by_county
  fig02_<W>_annual_events_by_county
  fig03_<W>_event_duration_distribution
  fig04_<W>_county_month_heatmap_by_year   (11 per-year panels, shared color scale)
  fig05_<W>_threshold_by_dayofyear
Cross-cutting:
  fig06_event_timeline_cameron_w15
  fig07_window_comparison_annual_days
  fig08_nws_proxy_threshold_days
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
plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 150, "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 11, "axes.titleweight": "bold"})
SCOLOR = {"Harris (Houston)": "#4C72B0", "El Paso": "#DD8452", "Lubbock": "#55A868",
          "Travis (Austin)": "#C44E52", "Cameron (Brownsville)": "#8172B3"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MID = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]
WIN_LABEL = {"w15": "centered 15-day-total (+/-7) window", "month": "calendar-month bucket"}
YEARS = list(range(2015, 2026))


def save(fig, name, note=""):
    try:
        if fig.get_layout_engine() is None:
            fig.tight_layout()
    except Exception:
        pass
    if note:
        fig.text(0.005, -0.008, note, fontsize=7, color="#555", ha="left", va="top")
    fig.savefig(os.path.join(FIG, name + ".png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  [fig]", name + ".png", flush=True)


def counties_in(df):
    return [c for c in SCOLOR if c in set(df["county_name"])]


for W in ["w15", "month"]:
    lbl = WIN_LABEL[W]
    cy = pd.read_csv(os.path.join(TAB, "county_year_summary_%s.csv" % W), dtype={"county_fips": str})
    cm = pd.read_csv(os.path.join(TAB, "county_month_summary_%s.csv" % W), dtype={"county_fips": str})
    ev = pd.read_csv(os.path.join(TAB, "heatwave_events_%s.csv" % W), dtype={"county_fips": str})
    thr = pd.read_csv(os.path.join(TAB, "thresholds_%s.csv" % W), dtype={"county_fips": str})
    cs = counties_in(cy)

    # fig01 annual heatwave days
    fig, ax = plt.subplots(figsize=(9, 5))
    for name in cs:
        g = cy[cy["county_name"] == name].sort_values("year")
        ax.plot(g["year"], g["heatwave_days"], marker="o", label=name, color=SCOLOR[name])
    ax.set_xlabel("Year"); ax.set_ylabel("Heatwave days"); ax.set_xticks(YEARS)
    ax.set_title("Heatwave days per year, by county [%s]" % lbl); ax.legend(fontsize=8)
    save(fig, "fig01_%s_annual_heatwave_days_by_county" % W,
         "Def 01 daily-mean HI, 85th pctl, >=2 days, walk-forward | %s | heatwave day = county-date in a >=2-day run" % lbl)

    # fig02 annual events
    fig, ax = plt.subplots(figsize=(9, 5))
    for name in cs:
        g = cy[cy["county_name"] == name].sort_values("year")
        ax.plot(g["year"], g["heatwave_events_started"], marker="s", label=name, color=SCOLOR[name])
    ax.set_xlabel("Year"); ax.set_ylabel("Heatwave events started (onset-year)"); ax.set_xticks(YEARS)
    ax.set_title("Heatwave events per year, by county [%s]" % lbl); ax.legend(fontsize=8)
    save(fig, "fig02_%s_annual_events_by_county" % W, "Def 01 | %s | events counted in onset year" % lbl)

    # fig03 event-duration distribution (counts of REAL events by exact duration)
    fig, ax = plt.subplots(figsize=(9, 5))
    maxd = int(ev["event_duration_days"].max())
    bottom = np.zeros(maxd - 1)
    xs = np.arange(2, maxd + 1)
    for name in cs:
        h, _ = np.histogram(ev[ev["county_name"] == name]["event_duration_days"], bins=np.arange(2, maxd + 2) - 0.5)
        ax.bar(xs, h, bottom=bottom, color=SCOLOR[name], label=name, width=0.85)
        bottom += h
    ax.set_xlabel("Event duration (consecutive days)"); ax.set_ylabel("Number of heatwave events")
    ax.set_title("Distribution of individual event durations [%s]" % lbl); ax.legend(fontsize=8)
    save(fig, "fig03_%s_event_duration_distribution" % W,
         "Def 01 | %s | each bar = count of REAL events of that exact duration (not a pooled average)" % lbl)

    # fig04 county x month heatmap SEPARATED BY YEAR, shared color scale
    vmax = int(cm["heatwave_days"].max())
    fig, axes = plt.subplots(3, 4, figsize=(15, 9), constrained_layout=True)
    axes = axes.ravel()
    im = None
    for k, yr in enumerate(YEARS):
        ax = axes[k]
        sub = cm[cm["year"] == yr]
        piv = sub.pivot_table(index="county_name", columns="month", values="heatwave_days", aggfunc="sum")
        piv = piv.reindex(index=cs, columns=range(1, 13), fill_value=0).fillna(0)
        im = ax.imshow(piv.values, aspect="auto", cmap="YlOrRd", vmin=0, vmax=vmax)
        ax.set_title(str(yr), fontsize=10)
        ax.set_xticks(range(12)); ax.set_xticklabels(MONTHS, fontsize=6, rotation=90)
        ax.set_yticks(range(len(cs)))
        ax.set_yticklabels([c.split()[0] for c in cs], fontsize=6)
    axes[11].axis("off")  # 12th slot unused (11 years)
    fig.colorbar(im, ax=axes[11], shrink=0.8, label="heatwave days (shared scale)")
    fig.suptitle("Heatwave days by county x month, SEPARATED BY YEAR (shared color scale 0-%d) [%s]" % (vmax, lbl),
                 fontsize=12, fontweight="bold")
    save(fig, "fig04_%s_county_month_heatmap_by_year" % W,
         "Def 01 | %s | one panel per year (NOT merged); identical color scale across all panels" % lbl)

    # fig05 threshold by day-of-year (analysis year 2025)
    fig, ax = plt.subplots(figsize=(9, 5))
    t25 = thr[thr["analysis_year"] == 2025].copy()
    if W == "w15":
        t25["doy"] = pd.to_datetime(dict(year=2000, month=t25["calendar_month"], day=t25["calendar_day"])).dt.dayofyear
        for name in cs:
            g = t25[t25["county_name"] == name].sort_values("doy")
            ax.plot(g["doy"], g["threshold_value_f"], label=name, color=SCOLOR[name], lw=1.2)
    else:
        for name in cs:
            g = t25[t25["county_name"] == name].sort_values("calendar_month")
            ax.step([MID[m - 1] for m in g["calendar_month"]], g["threshold_value_f"],
                    where="mid", label=name, color=SCOLOR[name], lw=1.4)
    ax.set_xlabel("Day of year"); ax.set_ylabel("85th-pctl mean-HI threshold (F)")
    ax.set_xticks(MID); ax.set_xticklabels(MONTHS)
    ax.set_title("Walk-forward threshold by time of year (analysis year 2025) [%s]" % lbl); ax.legend(fontsize=8)
    save(fig, "fig05_%s_threshold_by_timeofyear" % W, "Def 01 | %s | county- and season-specific relative threshold" % lbl)

# fig06 event timeline (Cameron, w15)
ev = pd.read_csv(os.path.join(TAB, "heatwave_events_w15.csv"), dtype={"county_fips": str})
ev["start_date"] = pd.to_datetime(ev["start_date"])
sub = ev[ev["county_name"] == "Cameron (Brownsville)"]
fig, ax = plt.subplots(figsize=(11, 5))
for _, e in sub.iterrows():
    ax.barh(e["start_date"].year, e["event_duration_days"], left=e["start_date"].dayofyear,
            height=0.6, color=SCOLOR["Cameron (Brownsville)"], edgecolor="white", lw=0.4)
ax.set_xlabel("Day of year"); ax.set_ylabel("Year"); ax.set_yticks(YEARS)
ax.set_xticks(MID); ax.set_xticklabels(MONTHS); ax.invert_yaxis()
ax.set_title("Individual heatwave events: Cameron (Brownsville) [w15]")
save(fig, "fig06_event_timeline_cameron_w15", "Def 01 | each bar = one REAL event (start -> start+duration); no averaging")

# fig07 window comparison (annual heatwave days per county: w15 vs month)
cyw = pd.read_csv(os.path.join(TAB, "county_year_summary_w15.csv"), dtype={"county_fips": str})
cym = pd.read_csv(os.path.join(TAB, "county_year_summary_month.csv"), dtype={"county_fips": str})
cs = counties_in(cyw)
fig, ax = plt.subplots(figsize=(9, 5))
for name in cs:
    a = cyw[cyw["county_name"] == name].sort_values("year")
    b = cym[cym["county_name"] == name].sort_values("year")
    ax.plot(a["year"], a["heatwave_days"], marker="o", color=SCOLOR[name], lw=1.6, label="%s (15-day)" % name.split()[0])
    ax.plot(b["year"], b["heatwave_days"], marker="x", ls="--", color=SCOLOR[name], lw=1.2, label="%s (month)" % name.split()[0])
ax.set_xlabel("Year"); ax.set_ylabel("Heatwave days"); ax.set_xticks(YEARS)
ax.set_title("Threshold-window comparison: heatwave days per year (solid=15-day, dashed=month)")
ax.legend(fontsize=6, ncol=2)
save(fig, "fig07_window_comparison_annual_days", "Def 01 | same definition, two threshold windows reported alongside")

# fig08 NWS proxy threshold days per county
ny = pd.read_csv(os.path.join(TAB, "nws_proxy_county_year.csv"), dtype={"county_fips": str})
pool = ny.groupby(["county_name", "nws_office", "advisory_hi_f", "extreme_warning_hi_f"]).agg(
    adv=("advisory_threshold_days", "sum"), warn=("extreme_warning_threshold_days", "sum")).reset_index()
pool = pool.set_index("county_name").reindex([c for c in SCOLOR if c in set(pool["county_name"])]).reset_index()
fig, ax = plt.subplots(figsize=(9, 5))
x = np.arange(len(pool))
ax.bar(x - 0.2, pool["adv"], width=0.4, label="advisory-threshold days", color="#DD8452")
ax.bar(x + 0.2, pool["warn"], width=0.4, label="extreme-warning-threshold days", color="#C44E52")
ax.set_xticks(x)
ax.set_xticklabels(["%s\n[%s adv>=%d/warn>=%d]" % (n.split()[0], o, a, w)
                    for n, o, a, w in zip(pool["county_name"], pool["nws_office"],
                                          pool["advisory_hi_f"], pool["extreme_warning_hi_f"])], fontsize=7)
ax.set_ylabel("Days (2015-2025 total)")
ax.set_title("NWS advisory-threshold PROXY days by county (daily max-HI proxy)")
ax.legend(fontsize=8)
save(fig, "fig08_nws_proxy_threshold_days",
     "PROXY only (not official advisories); local office HI thresholds; EWX & LUB approximate | arid El Paso/Lubbock rarely reach absolute thresholds")

print("[done] figures complete", flush=True)
