"""
=============================================================================
STEP p02  --  classify heatwave days/events and build the reporting tables.
=============================================================================
For each configured state and each configured PERCENTILE (each percentile is a
separate heatwave definition -- 85 = Def 01, 95 = Def 02), and for each
threshold WINDOW (centered 15-day, calendar-month):

  1. Build the county-specific, calendar-aware, WALK-FORWARD percentile threshold
     of the daily-MEAN heat index (baseline = all years from BASELINE_START up to
     the year BEFORE the analysis year, re-estimated each analysis year).
  2. Flag candidate days (daily-mean HI strictly ABOVE its own threshold), set the
     confirmed RH-clip artifacts to missing, and apply the >= MIN_DURATION
     consecutive-day persistence rule to get heatwave days and events.
  3. Write the substantive, county-level reporting tables (event / county-month /
     county-year) with temperatures + thresholds included; pooled statewide totals
     are written separately and labelled QA-only.

Reporting terminology is fixed: heatwave day / heatwave event / integer event
duration. Nothing is state- or percentile-specific in the code -- both come from
config.
=============================================================================
"""
import os, sys, time
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
from heatwave_run_logic import build_runs_and_events

HI = "derived_tmean_meanrh_hi_f"          # the daily-MEAN heat-index proxy (the metric)
# fixed 366-day (month,day) -> day-of-year template (leap-safe: "Mar 1" always maps
# to the same slot whether or not the historical year had a Feb 29).
_TPL = pd.date_range("2000-01-01", "2000-12-31")
MD_TO_TDOY = {(d.month, d.day): i + 1 for i, d in enumerate(_TPL)}
N_TDOY = 366


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- thresholds
def thresholds_centered(cdv, half, pctl):
    """Walk-forward centered-window percentile threshold, per county x day-of-year x year.
    Uses a tripled (prev/this/next year) day-of-year axis so the +/-half window wraps
    cleanly across Jan 1 / Dec 31."""
    out = []
    for fips, g in cdv.groupby("county_fips"):
        yrs = g["year"].values.astype(int)
        td = g["template_doy"].values.astype(int)
        val = g[HI].values.astype(float)
        for y in range(C.ANALYSIS_YEARS[0], C.ANALYSIS_YEARS[1] + 1):
            m = yrs <= y - 1                              # walk-forward: strictly prior years
            bt = np.concatenate([td[m] - N_TDOY, td[m], td[m] + N_TDOY])
            bv = np.concatenate([val[m], val[m], val[m]])
            order = np.argsort(bt); bt = bt[order]; bv = bv[order]
            for target in range(1, N_TDOY + 1):
                i0 = np.searchsorted(bt, target - half, "left")
                i1 = np.searchsorted(bt, target + half, "right")
                w = bv[i0:i1]
                out.append((fips, target, y, np.percentile(w, pctl) if w.size else np.nan, w.size))
    return pd.DataFrame(out, columns=["county_fips", "template_doy", "analysis_year",
                                      "threshold_value_f", "n_reference_values"])


def thresholds_month(cdv, pctl):
    """Walk-forward calendar-month percentile threshold, per county x month x year."""
    out = []
    for fips, g in cdv.groupby("county_fips"):
        yrs = g["year"].values.astype(int)
        mo = g["month"].values.astype(int)
        val = g[HI].values.astype(float)
        for y in range(C.ANALYSIS_YEARS[0], C.ANALYSIS_YEARS[1] + 1):
            m = yrs <= y - 1
            for cm in range(1, 13):
                w = val[m & (mo == cm)]
                out.append((fips, cm, y, np.percentile(w, pctl) if w.size else np.nan, w.size))
    return pd.DataFrame(out, columns=["county_fips", "calendar_month", "analysis_year",
                                      "threshold_value_f", "n_reference_values"])


# ---------------------------------------------------------------- classify / report helpers
def classify(an, definition_id, state_fips):
    """Reindex each county to a gap-free daily calendar and run the shared run/event logic."""
    parts = []
    for fips, g in an.groupby("county_fips"):
        g = g.sort_values("date").set_index("date")
        gf = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))
        gf["county_fips"] = fips
        gf = gf.reset_index().rename(columns={"index": "date"})
        parts.append(build_runs_and_events(gf, min_duration=C.MIN_DURATION,
                                           year_boundary_breaks_run=False,
                                           definition_id=definition_id, state_fips=state_fips))
    out = pd.concat(parts, ignore_index=True)
    out["year"] = out["date"].dt.year
    out["month"] = out["date"].dt.month
    return out


def event_table(hw):
    """One row per heatwave event, carrying peak-day temperatures + threshold."""
    if not len(hw):
        return pd.DataFrame()
    pidx = hw.groupby("event_id")[HI].idxmax()
    peak = hw.loc[pidx, ["event_id", "date", "tmax_f", "tmin_f", "tmean_f", "rmin_pct",
                         "threshold_value_f"]].set_index("event_id")
    ev = hw.groupby("event_id").agg(
        county_fips=("county_fips", "first"), county_name=("county_name", "first"),
        start_date=("date", "min"), end_date=("date", "max"),
        event_duration_days=("event_duration_days", "first"),
        peak_mean_hi_f=(HI, "max"), tmax_max_f=("tmax_f", "max"), tmean_mean_f=("tmean_f", "mean"),
        peak_exceedance_f=("exceedance_f", "max"),
        cumulative_exceedance_f=("exceedance_f", lambda s: float(np.maximum(0, s).sum())),
        n_imputed_days=("temp_imputed", "sum")).reset_index()
    ev["peak_day_date"] = ev["event_id"].map(peak["date"])
    ev["peak_day_tmax_f"] = ev["event_id"].map(peak["tmax_f"]).round(1)
    ev["peak_day_tmean_f"] = ev["event_id"].map(peak["tmean_f"]).round(1)
    ev["peak_day_rmin_pct"] = ev["event_id"].map(peak["rmin_pct"]).round(1)
    ev["peak_day_threshold_f"] = ev["event_id"].map(peak["threshold_value_f"]).round(1)
    for c in ["peak_mean_hi_f", "tmax_max_f", "tmean_mean_f", "peak_exceedance_f", "cumulative_exceedance_f"]:
        ev[c] = ev[c].round(2)
    ev = ev.sort_values(["county_fips", "start_date"]).reset_index(drop=True)
    ev["onset_year"] = ev["start_date"].dt.year
    ev["seq"] = ev.groupby(["county_fips", "onset_year"]).cumcount() + 1
    ev["event_label"] = ev.apply(lambda r: "%s_%d_%03d" % (r["county_fips"], r["onset_year"], r["seq"]), axis=1)
    ev["event_contains_imputed_day"] = ev["n_imputed_days"] > 0
    return ev[["event_label", "county_fips", "county_name", "start_date", "end_date",
               "event_duration_days", "peak_mean_hi_f", "peak_day_date", "peak_day_tmax_f",
               "peak_day_tmean_f", "peak_day_rmin_pct", "peak_day_threshold_f", "tmax_max_f",
               "tmean_mean_f", "peak_exceedance_f", "cumulative_exceedance_f",
               "n_imputed_days", "event_contains_imputed_day", "onset_year"]]


def county_year(ev, hw):
    """One row per county-year: events (onset-year) + heatwave days + span + longest."""
    rows = []
    for (fips, yr), g in ev.groupby(["county_fips", "onset_year"]):
        hwy = hw[(hw["county_fips"] == fips) & (hw["year"] == yr)]
        rows.append({"county_fips": fips, "county_name": g["county_name"].iloc[0], "year": yr,
                     "heatwave_events_started": len(g), "heatwave_days": int(len(hwy)),
                     "first_event_start_date": g["start_date"].min().date(),
                     "last_event_end_date": g["end_date"].max().date(),
                     "longest_event_duration_days": int(g["event_duration_days"].max()),
                     "heatwave_days_imputed": int(hwy["temp_imputed"].sum())})
    return pd.DataFrame(rows).sort_values(["county_fips", "year"])


def county_month(ev, hw):
    """One row per county-month. Month-crossing events counted once at onset, active in
    every month they touch; heatwave DAYS allocated to their actual calendar month."""
    act = []
    for _, e in ev.iterrows():
        for i, p in enumerate(pd.period_range(e["start_date"], e["end_date"], freq="M")):
            act.append({"county_fips": e["county_fips"], "year": p.year, "month": p.month,
                        "event_label": e["event_label"], "duration": e["event_duration_days"], "onset": i == 0})
    act = pd.DataFrame(act)
    hwd = hw.groupby(["county_fips", "year", "month"]).size().rename("heatwave_days").reset_index()
    rows = []
    for (fips, yr, mo), g in act.groupby(["county_fips", "year", "month"]):
        rows.append({"county_fips": fips, "year": yr, "month": mo,
                     "heatwave_events_started": int(g["onset"].sum()),
                     "heatwave_events_active": g["event_label"].nunique(),
                     "longest_event_duration_days": int(g["duration"].max())})
    cm = pd.DataFrame(rows).merge(hwd, on=["county_fips", "year", "month"], how="outer")
    cm["heatwave_days"] = cm["heatwave_days"].fillna(0).astype(int)
    for c in ["heatwave_events_started", "heatwave_events_active", "longest_event_duration_days"]:
        cm[c] = cm[c].fillna(0).astype(int)
    return cm.sort_values(["county_fips", "year", "month"])


DAILY_KEEP = ["county_fips", "county_name", "date", "year", "month",
              "tmax_f", "tmin_f", "tmean_f", "rmin_pct", HI, "threshold_value_f", "exceedance_f",
              "heatwave_day_flag", "event_id", "event_duration_days", "temp_imputed", "qc_status"]


# ---------------------------------------------------------------- driver
def run_state_percentile(state, pctl):
    t0 = time.time()
    fips = C.STATE_FIPS[state]
    defn = C.definition_id(pctl)
    ddir = C.definition_output_dir(state, pctl)
    tdir = os.path.join(ddir, "tables")
    log("=" * 72)
    log("p02  classify + report  --  state=%s  percentile=%d  (%s)" % (state, pctl, defn))
    log("=" * 72)

    cd = pd.read_csv(os.path.join(C.state_output_dir(state), "county_daily_heat.csv"),
                     dtype={"county_fips": str})
    cd["date"] = pd.to_datetime(cd["date"])
    cd["template_doy"] = cd["date"].dt.strftime("%m-%d").map(lambda md: MD_TO_TDOY[(int(md[:2]), int(md[3:]))])
    cdv = cd.dropna(subset=[HI])

    for W, spec in C.WINDOWS.items():
        log("[window=%s] %s" % (W, spec["label"]))
        if spec["type"] == "centered":
            thr = thresholds_centered(cdv, spec["half"], pctl)
            thr = thr.merge(cd[["template_doy", "month", "day"]].drop_duplicates(), on="template_doy", how="left")
            keys = ["county_fips", "month", "day", "analysis_year"]
            left = ["county_fips", "month", "day", "year"]
        else:
            thr = thresholds_month(cdv, pctl)
            keys = ["county_fips", "calendar_month", "analysis_year"]
            left = ["county_fips", "month", "year"]
        thr["definition_id"] = defn
        thr["percentile"] = pctl
        thr["window_method"] = spec["label"]
        thr["threshold_quality_flag"] = np.where(thr["n_reference_values"] < C.MIN_REF_OBS, "low_n_ref", "ok")
        thr.to_csv(os.path.join(tdir, "thresholds_%s.csv" % W), index=False)

        # join thresholds onto the analysis-period days; candidate = mean HI > threshold
        an = cd[(cd["year"] >= C.ANALYSIS_YEARS[0]) & (cd["year"] <= C.ANALYSIS_YEARS[1])].merge(
            thr[keys + ["threshold_value_f", "n_reference_values"]], left_on=left, right_on=keys, how="left")
        an["exceedance_f"] = an[HI] - an["threshold_value_f"]
        rel = (an[HI] > an["threshold_value_f"])
        art = an["qc_rh_pin_likely_artifact"].fillna(False).values
        cand = np.where(an[HI].isna() | an["threshold_value_f"].isna(), np.nan, rel.astype(float))
        # PRIMARY: optional absolute floor (config.PRIMARY_FLOOR_F), artifacts -> missing
        if C.PRIMARY_FLOOR_F is not None:
            cand = np.where(np.isnan(cand), np.nan, ((cand == 1) & (an[HI] >= C.PRIMARY_FLOOR_F)).astype(float))
        an["candidate_day_flag"] = pd.Series(cand, index=an.index).where(~art, np.nan).values

        d = classify(an, defn, fips)
        hw = d[d["heatwave_day_flag"] == 1].copy()
        ev = event_table(hw)
        ev.to_csv(os.path.join(tdir, "heatwave_events_%s.csv" % W), index=False)
        county_year(ev, hw).to_csv(os.path.join(tdir, "county_year_summary_%s.csv" % W), index=False)
        county_month(ev, hw).to_csv(os.path.join(tdir, "county_month_summary_%s.csv" % W), index=False)
        hw[[c for c in DAILY_KEEP if c in hw.columns]].to_csv(
            os.path.join(tdir, "daily_heatwave_days_%s.csv" % W), index=False)
        # QA-only statewide pooled totals per year
        sy = hw.groupby("year").agg(heatwave_days_QA=("heatwave_day_flag", "sum"),
                                    counties_with_any=("county_fips", "nunique")).reset_index()
        sy["heatwave_events_QA"] = hw.groupby("year")["event_id"].nunique().values
        sy.to_csv(os.path.join(tdir, "state_year_qc_%s.csv" % W), index=False)
        log("   [%s] events=%d  heatwave-days(QA pooled)=%d  counties-with-any=%d"
            % (W, len(ev), int(hw["heatwave_day_flag"].sum()), hw["county_fips"].nunique()))
    log("[done] %s p%d complete (%.0fs)" % (state, pctl, time.time() - t0))


if __name__ == "__main__":
    for st in C.STATES:
        for p in C.PERCENTILES:
            run_state_percentile(st, p)
