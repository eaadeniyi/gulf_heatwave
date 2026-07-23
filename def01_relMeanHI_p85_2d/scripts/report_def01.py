"""
DEFINITION 01 reporting, following the reviewer's naming convention:
  heatwave day   = one county on one date inside a qualifying >=2-day run
  heatwave event = one uninterrupted run within one county (its own record)
  event duration = integer count of consecutive calendar dates

Individual records are the substantive output; cross-county/-year pooled totals
are QA-only (in sensitivity_scenarios_qc_totals.csv), never the headline.

Builds from the PRIMARY daily classification:
  heatwave_events.csv        one row per event (county, id, start, end, duration, intensity)
  county_month_summary.csv   events started / active / heatwave days / longest, per county-month
  county_year_summary.csv    events (onset-year) / heatwave days / first-last span / longest
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(__file__)
OUT = os.path.abspath(os.path.join(HERE, "..", "tables"))
HI = "hi_mean_f"


def log(*a):
    print(*a, flush=True)


d = pd.read_csv(os.path.join(OUT, "daily_heatwave_classification.csv"), dtype={"county_fips": str})
d["date"] = pd.to_datetime(d["date"])
hw = d[d["heatwave_day_flag"] == 1].copy()

log("=" * 72)
log("DEFINITION 01 reporting (heatwave day / heatwave event / event duration)")
log("=" * 72)

# ----------------------------------------------------------------------
# 1. EVENT table -- one row per heatwave event (never averaged together)
# ----------------------------------------------------------------------
ev = hw.groupby("event_id").agg(
    county_fips=("county_fips", "first"),
    county_name=("county_name", "first"),
    start_date=("date", "min"),
    end_date=("date", "max"),
    event_duration_days=("event_duration_days", "first"),
    peak_mean_hi_f=(HI, "max"),
    mean_mean_hi_f=(HI, "mean"),
    peak_exceedance_f=("exceedance_f", "max"),
    cumulative_exceedance_f=("exceedance_f", lambda s: float(np.maximum(0, s).sum())),
).reset_index()
ev["onset_year"] = ev["start_date"].dt.year
# human-readable per-county sequential event id, e.g. HARRIS_2021_001
ev = ev.sort_values(["county_fips", "start_date"]).reset_index(drop=True)
ev["seq"] = ev.groupby(["county_fips", "onset_year"]).cumcount() + 1
ev["event_label"] = ev.apply(
    lambda r: "%s_%d_%03d" % (r["county_name"].split()[0].upper(), r["onset_year"], r["seq"]), axis=1)
ev["peak_mean_hi_f"] = ev["peak_mean_hi_f"].round(1)
ev["mean_mean_hi_f"] = ev["mean_mean_hi_f"].round(1)
ev["peak_exceedance_f"] = ev["peak_exceedance_f"].round(2)
ev["cumulative_exceedance_f"] = ev["cumulative_exceedance_f"].round(2)
ev_cols = ["event_label", "county_fips", "county_name", "start_date", "end_date", "event_duration_days",
           "peak_mean_hi_f", "mean_mean_hi_f", "peak_exceedance_f", "cumulative_exceedance_f", "onset_year"]
ev[ev_cols].to_csv(os.path.join(OUT, "heatwave_events.csv"), index=False)
log("[1] heatwave_events.csv -- %d individual events (one row each)" % len(ev))

# ----------------------------------------------------------------------
# 2. COUNTY-MONTH summary (events started / active / heatwave days / longest)
#    Month-crossing rules: an event is counted under events_started once, in its
#    ONSET month; it is "active" in every month it touches; heatwave DAYS are
#    allocated to their actual calendar month (no double counting).
# ----------------------------------------------------------------------
# active (county, month-period) pairs per event, from the event's date span
active_rows = []
for _, e in ev.iterrows():
    months = pd.period_range(e["start_date"], e["end_date"], freq="M")
    for i, p in enumerate(months):
        active_rows.append({"county_fips": e["county_fips"], "year": p.year, "month": p.month,
                            "event_label": e["event_label"], "duration": e["event_duration_days"],
                            "is_onset_month": (i == 0)})
active = pd.DataFrame(active_rows)

# heatwave DAYS per county-year-month (actual calendar allocation)
hw_days = (hw.groupby(["county_fips", "county_name", "year", "month"])
             .size().rename("heatwave_days").reset_index())

cm = []
grp = active.groupby(["county_fips", "year", "month"])
for (fips, yr, mo), g in grp:
    started = g[g["is_onset_month"]]["event_label"].tolist()
    cm.append({"county_fips": fips, "year": yr, "month": mo,
               "heatwave_events_started": len(started),
               "heatwave_events_active": g["event_label"].nunique(),
               "longest_active_event_duration_days": int(g["duration"].max()),
               "event_ids_started": ";".join(started),
               "event_ids_active": ";".join(sorted(g["event_label"].unique()))})
cm = pd.DataFrame(cm)
cm = cm.merge(hw_days, on=["county_fips", "year", "month"], how="outer")
cm["heatwave_days"] = cm["heatwave_days"].fillna(0).astype(int)
for c in ["heatwave_events_started", "heatwave_events_active", "longest_active_event_duration_days"]:
    cm[c] = cm[c].fillna(0).astype(int)
cm["county_name"] = cm["county_name"].fillna(cm["county_fips"].map(
    d.drop_duplicates("county_fips").set_index("county_fips")["county_name"]))
cm = cm.sort_values(["county_fips", "year", "month"])
cm[["county_fips", "county_name", "year", "month", "heatwave_events_started", "heatwave_events_active",
    "heatwave_days", "longest_active_event_duration_days", "event_ids_started", "event_ids_active"]].to_csv(
    os.path.join(OUT, "county_month_summary.csv"), index=False)
log("[2] county_month_summary.csv -- %d county-months" % len(cm))

# ----------------------------------------------------------------------
# 3. COUNTY-YEAR summary (events counted by ONSET year)
# ----------------------------------------------------------------------
cy = []
for (fips, yr), g in ev.groupby(["county_fips", "onset_year"]):
    hwy = hw[(hw["county_fips"] == fips) & (hw["year"] == yr)]
    cy.append({"county_fips": fips, "county_name": g["county_name"].iloc[0], "year": yr,
               "heatwave_events": len(g),
               "heatwave_days": int(len(hwy)),
               "first_event_start_date": g["start_date"].min().date(),
               "last_event_end_date": g["end_date"].max().date(),
               "longest_event_duration_days": int(g["event_duration_days"].max()),
               "event_durations": ",".join(str(int(x)) for x in sorted(g["event_duration_days"])),
               "event_ids": ";".join(g.sort_values("start_date")["event_label"])})
cy = pd.DataFrame(cy).sort_values(["county_fips", "year"])
cy.to_csv(os.path.join(OUT, "county_year_summary.csv"), index=False)
log("[3] county_year_summary.csv -- %d county-years" % len(cy))

# ----------------------------------------------------------------------
# Interpretable examples (individual records, NOT pooled averages)
# ----------------------------------------------------------------------
log("\n[interpretable examples -- individual records, no pooling]")
for fips, name in [("48201", "Harris (Houston)"), ("48061", "Cameron (Brownsville)")]:
    for yr in [2021, 2023]:
        r = cy[(cy["county_fips"] == fips) & (cy["year"] == yr)]
        if len(r):
            r = r.iloc[0]
            log("  %s, %d: %d heatwave events; %d heatwave days; durations = %s; longest = %d days"
                % (name, yr, r["heatwave_events"], r["heatwave_days"], r["event_durations"],
                   r["longest_event_duration_days"]))

log("\n[longest single events in the dataset -- individual events]")
top = ev.nlargest(5, "event_duration_days")
for _, e in top.iterrows():
    log("  %-18s %s to %s = %d consecutive days (peak mean-HI %.1fF)"
        % (e["event_label"], e["start_date"].date(), e["end_date"].date(),
           e["event_duration_days"], e["peak_mean_hi_f"]))
