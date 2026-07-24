"""
STATEWIDE Definition 01: relative 85th-pctl daily-MEAN heat index, >=2 consecutive
days, walk-forward baseline, 2015-2025, ALL 254 Texas counties.

Same methodology as the 5-county def01 (build_def01.py), applied statewide on the
IDW-gap-filled county-day table:
  * TWO windows: w15 = centered 15-day-total (+/-7); month = calendar-month bucket.
  * candidate = daily-mean HI > walk-forward 85th-pctl threshold (strict '>').
  * PRIMARY: no absolute floor; confirmed RH-clip artifacts set to missing.
  * heatwave day / heatwave event / integer event duration; county-level records.
  * imputed county-days participate but keep their temp_imputed flag downstream.

Outputs per window <W>:
  tables/heatwave_events_<W>.csv        (one row per event; temps+threshold)
  tables/county_year_summary_<W>.csv
  tables/county_month_summary_<W>.csv   (large; git-ignored)
  tables/state_year_qc_<W>.csv          (statewide QA totals per year -- QA only)
  tables/daily_heatwave_days_<W>.csv    (heatwave days only, temps+threshold; git-ignored)
"""
import os, sys, time
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "texas_heatwave_pilot", "scripts"))
from heatwave_run_logic import build_runs_and_events

OUT = os.path.abspath(os.path.join(HERE, "..", "tables"))
SRC = os.path.join(OUT, "statewide_county_daily_heat.csv")
HI = "hi_mean_f"
SRC_HI = "derived_tmean_meanrh_hi_f"
PCTL, AN0, AN1, BASE_START, MIN_DUR, HALF = 85, 2015, 2025, 1979, 2, 7
DEFINITION_ID = "relMeanHI_p85_2d_walkforward_statewide"
_tpl = pd.date_range("2000-01-01", "2000-12-31")
MD_TO_TDOY = {(d.month, d.day): i + 1 for i, d in enumerate(_tpl)}
N_TDOY = 366


def log(*a):
    print(*a, flush=True)


t0 = time.time()
log("=" * 72)
log("STATEWIDE Def 01: relative 85th-pctl daily-mean HI, >=2 days, walk-forward (254 counties)")
log("=" * 72)
cd = pd.read_csv(SRC, dtype={"county_fips": str})
cd["date"] = pd.to_datetime(cd["date"])
cd = cd.rename(columns={SRC_HI: HI})
cd["template_doy"] = cd["date"].dt.strftime("%m-%d").map(
    lambda md: MD_TO_TDOY[(int(md[:2]), int(md[3:]))])
cdv = cd.dropna(subset=[HI])
log("[load] %d county-days, %d counties (%.0fs)" % (len(cd), cd["county_fips"].nunique(), time.time() - t0))


def thresholds_centered(df, half):
    out = []
    for fips, g in df.groupby("county_fips"):
        arr = g[["year", "template_doy", HI]].values
        yrs = arr[:, 0].astype(int); td = arr[:, 1].astype(int); val = arr[:, 2].astype(float)
        for y in range(AN0, AN1 + 1):
            mask = yrs <= y - 1
            bt = np.concatenate([td[mask] - N_TDOY, td[mask], td[mask] + N_TDOY])
            bv = np.concatenate([val[mask], val[mask], val[mask]])
            order = np.argsort(bt); bt = bt[order]; bv = bv[order]
            for target in range(1, N_TDOY + 1):
                i0 = np.searchsorted(bt, target - half, "left")
                i1 = np.searchsorted(bt, target + half, "right")
                w = bv[i0:i1]
                out.append((fips, target, y, np.percentile(w, PCTL) if w.size else np.nan, w.size))
    t = pd.DataFrame(out, columns=["county_fips", "template_doy", "analysis_year", "threshold_value_f", "n_reference_values"])
    return t


def thresholds_month(df):
    out = []
    for fips, g in df.groupby("county_fips"):
        arr = g[["year", "month", HI]].values
        yrs = arr[:, 0].astype(int); mo = arr[:, 1].astype(int); val = arr[:, 2].astype(float)
        for y in range(AN0, AN1 + 1):
            mask = yrs <= y - 1
            for m in range(1, 13):
                w = val[mask & (mo == m)]
                out.append((fips, m, y, np.percentile(w, PCTL) if w.size else np.nan, w.size))
    return pd.DataFrame(out, columns=["county_fips", "calendar_month", "analysis_year", "threshold_value_f", "n_reference_values"])


def classify(an):
    parts = []
    for fips, g in an.groupby("county_fips"):
        g = g.sort_values("date").set_index("date")
        gf = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))
        gf["county_fips"] = fips
        gf = gf.reset_index().rename(columns={"index": "date"})
        parts.append(build_runs_and_events(gf, min_duration=MIN_DUR, year_boundary_breaks_run=False,
                                           definition_id=DEFINITION_ID, state_fips="48"))
    out = pd.concat(parts, ignore_index=True)
    out["year"] = out["date"].dt.year
    out["month"] = out["date"].dt.month
    return out


def event_table(hw):
    if not len(hw):
        return pd.DataFrame()
    pidx = hw.groupby("event_id")[HI].idxmax()
    peak = hw.loc[pidx, ["event_id", "date", "tmax_f", "tmin_f", "tmean_f", "rmin_pct", "threshold_value_f"]].set_index("event_id")
    ev = hw.groupby("event_id").agg(
        county_fips=("county_fips", "first"), county_name=("county_name", "first"),
        start_date=("date", "min"), end_date=("date", "max"),
        event_duration_days=("event_duration_days", "first"),
        peak_mean_hi_f=(HI, "max"), tmax_max_f=("tmax_f", "max"), tmean_mean_f=("tmean_f", "mean"),
        peak_exceedance_f=("exceedance_f", "max"),
        cumulative_exceedance_f=("exceedance_f", lambda s: float(np.maximum(0, s).sum())),
        n_imputed_days=("temp_imputed", "sum"),
    ).reset_index()
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
    return ev[["event_label", "county_fips", "county_name", "start_date", "end_date", "event_duration_days",
               "peak_mean_hi_f", "peak_day_date", "peak_day_tmax_f", "peak_day_tmean_f", "peak_day_rmin_pct",
               "peak_day_threshold_f", "tmax_max_f", "tmean_mean_f", "peak_exceedance_f",
               "cumulative_exceedance_f", "n_imputed_days", "event_contains_imputed_day", "onset_year"]]


def county_year(ev, hw):
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

WINDOWS = {}
log("[thresholds] w15 (centered +/-7) ...")
tw = thresholds_centered(cdv, HALF)
tw = tw.merge(cd[["template_doy", "month", "day"]].drop_duplicates(), on="template_doy", how="left")
WINDOWS["w15"] = ("w15", tw, ["county_fips", "month", "day", "analysis_year"], ["county_fips", "month", "day", "year"])
log("[thresholds] month bucket ...")
tm = thresholds_month(cdv)
WINDOWS["month"] = ("month", tm, ["county_fips", "calendar_month", "analysis_year"], ["county_fips", "month", "year"])
log("   thresholds built (%.0fs)" % (time.time() - t0))

for W, (_, thr, keys, left) in WINDOWS.items():
    log("\n[window=%s] classify + report ..." % W)
    thr.to_csv(os.path.join(OUT, "thresholds_%s.csv" % W), index=False)
    an = cd[(cd["year"] >= AN0) & (cd["year"] <= AN1)].merge(
        thr[keys + ["threshold_value_f", "n_reference_values"]], left_on=left, right_on=keys, how="left")
    an["exceedance_f"] = an[HI] - an["threshold_value_f"]
    rel = (an[HI] > an["threshold_value_f"])
    art = an["qc_rh_pin_likely_artifact"].fillna(False).values
    cand = np.where(an[HI].isna() | an["threshold_value_f"].isna(), np.nan, rel.astype(float))
    cand = pd.Series(cand, index=an.index).where(~art, np.nan)      # artifacts -> missing (PRIMARY)
    an["candidate_day_flag"] = cand.values
    d = classify(an)
    hw = d[d["heatwave_day_flag"] == 1].copy()
    ev = event_table(hw)
    ev.to_csv(os.path.join(OUT, "heatwave_events_%s.csv" % W), index=False)
    county_year(ev, hw).to_csv(os.path.join(OUT, "county_year_summary_%s.csv" % W), index=False)
    county_month(ev, hw).to_csv(os.path.join(OUT, "county_month_summary_%s.csv" % W), index=False)
    hw[[c for c in DAILY_KEEP if c in hw.columns]].to_csv(os.path.join(OUT, "daily_heatwave_days_%s.csv" % W), index=False)
    # statewide per-year QA (QA-ONLY pooled)
    sy = hw.groupby("year").agg(heatwave_days_QA=("heatwave_day_flag", "sum"),
                                counties_with_any=("county_fips", "nunique")).reset_index()
    sy["heatwave_events_QA"] = hw.groupby("year")["event_id"].nunique().values
    sy.to_csv(os.path.join(OUT, "state_year_qc_%s.csv" % W), index=False)
    log("   [%s] events=%d  heatwave-days(QA pooled)=%d  counties-with-any=%d"
        % (W, len(ev), int(hw["heatwave_day_flag"].sum()), hw["county_fips"].nunique()))

log("\n[done] statewide Def 01 complete for both windows (%.0fs)" % (time.time() - t0))
