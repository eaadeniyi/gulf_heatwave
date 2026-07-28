"""
PER-DEFINITION results: for EACH definition on its own (not a comparison),
pull detailed statistics from its CSV outputs and build result figures.
Writes per-def stats (JSON) + 4 result figures per def into the def's figures/ dir.
Also re-verifies the headline numbers inline (the workflow verifiers hit the limit).
"""
import os, sys, json
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUTBASE = os.path.join(ROOT, "texas_heatwave_pilot", "outputs", "TX")
DEFS = {"Definition 01 (85th pctl)": ("def_p85_2d", "#4C72B0"),
        "Definition 02 (95th pctl)": ("def_p95_2d", "#C44E52")}
YEARS = list(range(2015, 2026))
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 150, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 12, "axes.titleweight": "bold"})


def L(*a): print(*a, flush=True)


allstats = {}
for name, (ddir, color) in DEFS.items():
    tdir = os.path.join(OUTBASE, ddir, "tables")
    fdir = os.path.join(OUTBASE, ddir, "figures"); os.makedirs(fdir, exist_ok=True)
    cy = pd.read_csv(os.path.join(tdir, "county_year_summary_w15.csv"), dtype={"county_fips": str})
    ev = pd.read_csv(os.path.join(tdir, "heatwave_events_w15.csv"), dtype={"county_fips": str})
    hd = pd.read_csv(os.path.join(tdir, "daily_heatwave_days_w15.csv"), dtype={"county_fips": str})

    percty = cy.groupby(["county_fips", "county_name"]).agg(
        days=("heatwave_days", "sum"), events=("heatwave_events_started", "sum")).reset_index()
    dur = ev["event_duration_days"]
    st = {
        "pooled_heatwave_days": int(cy["heatwave_days"].sum()),
        "pooled_events": int(cy["heatwave_events_started"].sum()),
        "n_counties": int(percty.shape[0]),
        "per_county_days": {
            "median": float(percty["days"].median()), "mean": round(float(percty["days"].mean()), 1),
            "p25": float(percty["days"].quantile(.25)), "p75": float(percty["days"].quantile(.75)),
            "min": int(percty["days"].min()), "max": int(percty["days"].max())},
        "per_county_events": {"median": float(percty["events"].median()),
                              "min": int(percty["events"].min()), "max": int(percty["events"].max())},
        "event_duration": {"median": float(dur.median()), "mean": round(float(dur.mean()), 2),
                           "max": int(dur.max()), "pct_2day": round(100 * (dur == 2).mean(), 1),
                           "pct_ge5day": round(100 * (dur >= 5).mean(), 1)},
        "pct_days_junsep": round(100 * hd["month"].isin([6, 7, 8, 9]).mean(), 1),
        "pct_days_imputed": round(100 * hd["temp_imputed"].mean(), 1) if "temp_imputed" in hd else None,
        "top5_counties_by_days": percty.nlargest(5, "days")[["county_name", "days", "events"]].to_dict("records"),
        "longest3_events": ev.nlargest(3, "event_duration_days")[
            ["county_name", "start_date", "end_date", "event_duration_days", "peak_mean_hi_f"]].to_dict("records"),
        "annual_days": cy.groupby("year")["heatwave_days"].sum().reindex(YEARS, fill_value=0).astype(int).to_dict(),
    }
    allstats[name] = st
    L("\n===", name, "==="); L(json.dumps(st, indent=1, default=str)[:900])

    tag = ddir  # for filenames
    # FIG A: annual statewide heatwave days
    fig, ax = plt.subplots(figsize=(9, 5))
    by = cy.groupby("year")["heatwave_days"].sum().reindex(YEARS, fill_value=0)
    ax.bar(YEARS, by.values, color=color)
    ax.set_xticks(YEARS); ax.set_xlabel("Year"); ax.set_ylabel("Heatwave county-days (statewide)")
    ax.set_title("%s — statewide heatwave days per year" % name)
    fig.text(0.005, -0.02, "Heatwave day = one county on one date inside a >=2-day run (centered 15-day window). Statewide pooled totals.", fontsize=7.5, color="#555")
    fig.tight_layout(); fig.savefig(os.path.join(fdir, "res_annual_days.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)
    # FIG B: event-duration distribution
    fig, ax = plt.subplots(figsize=(9, 5))
    md = 15; h, _ = np.histogram(dur.clip(upper=md), bins=np.arange(2, md + 2) - 0.5)
    ax.bar(np.arange(2, md + 1), 100 * h / h.sum(), color=color)
    ax.set_xlabel("Event duration (consecutive days; 15 = 15+)"); ax.set_ylabel("% of events")
    ax.set_title("%s — how long events last (median %.0f d, max %d d)" % (name, dur.median(), dur.max()))
    fig.tight_layout(); fig.savefig(os.path.join(fdir, "res_event_duration.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)
    # FIG C: seasonal (monthly share)
    fig, ax = plt.subplots(figsize=(9, 5))
    bymon = hd.groupby("month").size().reindex(range(1, 13), fill_value=0)
    bars = ax.bar(range(1, 13), 100 * bymon.values / bymon.sum(), color=color)
    for m in [6, 7, 8, 9]:
        bars[m - 1].set_edgecolor("black"); bars[m - 1].set_linewidth(1.5)
    ax.set_xticks(range(1, 13)); ax.set_xticklabels(MONTHS); ax.set_ylabel("% of heatwave days")
    ax.set_title("%s — when heatwave days fall (%.0f%% in Jun-Sep, outlined)" % (name, st["pct_days_junsep"]))
    fig.text(0.005, -0.02, "Year-round RELATIVE definition: most days are 'unusual for the date', not necessarily absolutely hot.", fontsize=7.5, color="#555")
    fig.tight_layout(); fig.savefig(os.path.join(fdir, "res_seasonal.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)
    # FIG D: top-15 counties by heatwave days
    fig, ax = plt.subplots(figsize=(9, 6))
    top = percty.nlargest(15, "days").sort_values("days")
    ax.barh(top["county_name"], top["days"], color=color)
    ax.set_xlabel("Heatwave days (2015-2025 total)"); ax.set_title("%s — top 15 counties by heatwave days" % name)
    fig.text(0.005, -0.02, "Single-county values are noisy (multi-station composite + IDW imputation); read the regional pattern, not exact ranks.", fontsize=7.5, color="#555")
    fig.tight_layout(); fig.savefig(os.path.join(fdir, "res_top_counties.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)
    L("[figs] wrote res_annual_days / res_event_duration / res_seasonal / res_top_counties ->", fdir)

# ---- inline re-verification of headline numbers (workflow verifiers hit the limit) ----
L("\n=== inline verification ===")
for name, (ddir, _) in DEFS.items():
    cy = pd.read_csv(os.path.join(OUTBASE, ddir, "tables", "county_year_summary_w15.csv"), dtype={"county_fips": str})
    L("  %-26s pooled days=%d events=%d  (independent re-sum from county_year_summary_w15.csv)"
      % (name, int(cy["heatwave_days"].sum()), int(cy["heatwave_events_started"].sum())))

json.dump(allstats, open(os.path.join(HERE, "per_definition_stats.json"), "w"), indent=2, default=str)
L("\n[done] wrote per_definition_stats.json")
