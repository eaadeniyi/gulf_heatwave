"""
DEFINITION 01 (revised) -- relative 85th-pctl daily-MEAN heat index, >=2 consecutive
days, walk-forward baseline, 2015-2025, 5 Texas counties.

REVISION (this pass), per user instruction:
  * TWO threshold windows, reported alongside each other:
      - "w15"   : centered 15-day-TOTAL window (target day +/- 7 days)   [replaces the old +/-15/31-day]
      - "month" : calendar-MONTH bucket (85th pctl of all days in that calendar month)
    Both walk-forward (analysis year Y drawn from 1979..Y-1).
  * Temperatures (Tmax, Tmin, Tmean, RHmax, RHmin, mean RH) AND the county-day
    threshold + exceedance are carried into BOTH the daily heatwave records and
    the event table.
  * Reporting follows the naming convention exactly:
      heatwave day   = one county on one date inside a qualifying >=2-day run (county-date)
      heatwave event = one uninterrupted run within one county (its own record)
      event duration = integer count of consecutive calendar dates
    Pooled cross-county/-year totals are QA-only (never the headline). Pooled
    AVERAGE duration is NOT reported as a primary statistic.
  * Construct label = persistent_apparent_heat_anomaly (year-round relative).

PRIMARY = no absolute floor (faithful to the definition as written); confirmed
RH-clip artifacts (2023-03-01) set to missing. A mean-HI>=80F floor variant is
retained as a QA sensitivity in sensitivity_scenarios_qc_totals.csv.

Outputs, per window <W> in {w15, month}:
  tables/thresholds_<W>.csv
  tables/daily_heatwave_days_<W>.csv        (one row per county-DATE that is a heatwave day; carries temps+threshold)
  tables/daily_classification_<W>.csv       (one row per analysis county-date; QA/full)
  tables/heatwave_events_<W>.csv            (one row per event; carries temps+threshold)
  tables/county_month_summary_<W>.csv
  tables/county_year_summary_<W>.csv
  tables/sensitivity_scenarios_qc_totals.csv (QA-only pooled totals, both windows + floor)
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

PILOT = os.path.join(ROOT, "texas_heatwave_pilot")
SRC_DAILY = os.path.join(PILOT, "tables", "05_county_daily_heat.csv")
OUT = os.path.abspath(os.path.join(HERE, "..", "tables"))
os.makedirs(OUT, exist_ok=True)

HI = "hi_mean_f"                        # daily-mean HI proxy (working name)
SRC_HI = "derived_tmean_meanrh_hi_f"
PCTL, AN0, AN1, BASE_START, MIN_DUR = 85, 2015, 2025, 1979, 2
HALF = 7                                # centered 15-day-TOTAL window = target +/- 7
DEFINITION_ID = "relMeanHI_p85_2d_walkforward"
CONSTRUCT = "persistent_apparent_heat_anomaly"

_tpl = pd.date_range("2000-01-01", "2000-12-31")
MD_TO_TDOY = {(d.month, d.day): i + 1 for i, d in enumerate(_tpl)}
TDOY_TO_MD = {v: k for k, v in MD_TO_TDOY.items()}
N_TDOY = 366


def log(*a):
    print(*a, flush=True)


log("=" * 74)
log("DEFINITION 01 (revised): relative 85th-pctl daily-MEAN HI, >=2 days, walk-forward")
log("  windows: w15 = centered 15-day-total (+/-7)  |  month = calendar-month bucket")
log("=" * 74)

cd = pd.read_csv(SRC_DAILY, dtype={"county_fips": str})
cd["date"] = pd.to_datetime(cd["date"])
cd = cd.rename(columns={SRC_HI: HI})
cd["template_doy"] = cd.apply(lambda r: MD_TO_TDOY[(int(r["month"]), int(r["day"]))], axis=1)
cdv = cd.dropna(subset=[HI])
log("[load] %d county-days, %d counties; mean-HI non-null=%d" % (len(cd), cd["county_fips"].nunique(), len(cdv)))


# ---------------------------------------------------------------- thresholds
def thresholds_centered(df, half):
    rows = []
    for fips in df["county_fips"].unique():
        name = df.loc[df["county_fips"] == fips, "county_name"].iloc[0]
        full = df[df["county_fips"] == fips][["year", "template_doy", HI]]
        for y in range(AN0, AN1 + 1):
            base = full[full["year"] <= y - 1]
            trip = pd.concat([base.assign(td=base["template_doy"] + off * N_TDOY) for off in (-1, 0, 1)],
                             ignore_index=True).sort_values("td")
            tarr, harr = trip["td"].values, trip[HI].values
            for target in range(1, N_TDOY + 1):
                i0 = np.searchsorted(tarr, target - half, "left")
                i1 = np.searchsorted(tarr, target + half, "right")
                w = harr[i0:i1]
                m, d = TDOY_TO_MD[target]
                rows.append((fips, name, m, d, y, np.percentile(w, PCTL) if w.size else np.nan, w.size))
    t = pd.DataFrame(rows, columns=["county_fips", "county_name", "calendar_month", "calendar_day",
                                    "analysis_year", "threshold_value_f", "n_reference_values"])
    t["window_method"] = "centered_15day_total_pm%d" % half
    return t


def thresholds_month(df):
    rows = []
    for fips in df["county_fips"].unique():
        name = df.loc[df["county_fips"] == fips, "county_name"].iloc[0]
        full = df[df["county_fips"] == fips][["year", "month", HI]]
        for y in range(AN0, AN1 + 1):
            base = full[full["year"] <= y - 1]
            for mo in range(1, 13):
                w = base[base["month"] == mo][HI].values
                rows.append((fips, name, mo, y, np.percentile(w, PCTL) if w.size else np.nan, w.size))
    t = pd.DataFrame(rows, columns=["county_fips", "county_name", "calendar_month",
                                    "analysis_year", "threshold_value_f", "n_reference_values"])
    t["window_method"] = "calendar_month_bucket"
    return t


# ---------------------------------------------------------------- classify + events
DAILY_KEEP = ["county_fips", "county_name", "date", "year", "month", "day",
              "tmax_f", "tmin_f", "tmean_f", "rmax_pct", "rmin_pct", "rh_mean_pct", HI,
              "threshold_value_f", "exceedance_f", "relative_exceedance",
              "candidate_day_flag", "run_length", "heatwave_day_flag",
              "event_id", "event_duration_days", "event_day_number",
              "event_onset_flag", "event_final_day_flag", "qc_status"]


def classify(an, definition_tag):
    parts = []
    for fips, g in an.groupby("county_fips"):
        g = g.sort_values("date").set_index("date")
        gf = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))
        gf["county_fips"] = fips
        gf = gf.reset_index().rename(columns={"index": "date"})
        parts.append(build_runs_and_events(gf, min_duration=MIN_DUR, year_boundary_breaks_run=False,
                                           definition_id=definition_tag, state_fips="48"))
    out = pd.concat(parts, ignore_index=True)
    out["year"] = out["date"].dt.year
    out["month"] = out["date"].dt.month
    return out


def build_event_table(hw):
    """one row per heatwave event, carrying temperatures + thresholds."""
    if not len(hw):
        return pd.DataFrame()
    peak_idx = hw.groupby("event_id")[HI].idxmax()
    peak = hw.loc[peak_idx, ["event_id", "date", "tmax_f", "tmin_f", "tmean_f",
                             "rmax_pct", "rmin_pct", HI, "threshold_value_f"]].set_index("event_id")
    ev = hw.groupby("event_id").agg(
        county_fips=("county_fips", "first"), county_name=("county_name", "first"),
        start_date=("date", "min"), end_date=("date", "max"),
        event_duration_days=("event_duration_days", "first"),
        peak_mean_hi_f=(HI, "max"),
        tmax_max_f=("tmax_f", "max"), tmean_mean_f=("tmean_f", "mean"),
        peak_exceedance_f=("exceedance_f", "max"),
        cumulative_exceedance_f=("exceedance_f", lambda s: float(np.maximum(0, s).sum())),
    ).reset_index()
    # temperatures + threshold ON the peak-HI day (the event's hottest day)
    ev["peak_day_date"] = ev["event_id"].map(peak["date"])
    ev["peak_day_tmax_f"] = ev["event_id"].map(peak["tmax_f"]).round(1)
    ev["peak_day_tmin_f"] = ev["event_id"].map(peak["tmin_f"]).round(1)
    ev["peak_day_tmean_f"] = ev["event_id"].map(peak["tmean_f"]).round(1)
    ev["peak_day_rmax_pct"] = ev["event_id"].map(peak["rmax_pct"]).round(1)
    ev["peak_day_rmin_pct"] = ev["event_id"].map(peak["rmin_pct"]).round(1)
    ev["peak_day_threshold_f"] = ev["event_id"].map(peak["threshold_value_f"]).round(1)
    for c in ["peak_mean_hi_f", "tmax_max_f", "tmean_mean_f", "peak_exceedance_f", "cumulative_exceedance_f"]:
        ev[c] = ev[c].round(2)
    ev = ev.sort_values(["county_fips", "start_date"]).reset_index(drop=True)
    ev["onset_year"] = ev["start_date"].dt.year
    ev["seq"] = ev.groupby(["county_fips", "onset_year"]).cumcount() + 1
    ev["event_label"] = ev.apply(
        lambda r: "%s_%d_%03d" % (r["county_name"].split()[0].upper(), r["onset_year"], r["seq"]), axis=1)
    ev["definition_id"] = DEFINITION_ID
    ev["construct_label"] = CONSTRUCT
    cols = ["event_label", "county_fips", "county_name", "start_date", "end_date", "event_duration_days",
            "peak_mean_hi_f", "peak_day_date", "peak_day_tmax_f", "peak_day_tmin_f", "peak_day_tmean_f",
            "peak_day_rmax_pct", "peak_day_rmin_pct", "peak_day_threshold_f",
            "tmax_max_f", "tmean_mean_f", "peak_exceedance_f", "cumulative_exceedance_f",
            "onset_year", "definition_id", "construct_label"]
    return ev[cols]


def county_month(ev, hw, county_names):
    """events started / active / heatwave days / longest, per county-month (month-crossing rules)."""
    act = []
    for _, e in ev.iterrows():
        for i, p in enumerate(pd.period_range(e["start_date"], e["end_date"], freq="M")):
            act.append({"county_fips": e["county_fips"], "year": p.year, "month": p.month,
                        "event_label": e["event_label"], "duration": e["event_duration_days"],
                        "onset": i == 0})
    act = pd.DataFrame(act)
    hwd = hw.groupby(["county_fips", "year", "month"]).size().rename("heatwave_days").reset_index()
    rows = []
    for (fips, yr, mo), g in act.groupby(["county_fips", "year", "month"]):
        started = g[g["onset"]]["event_label"].tolist()
        rows.append({"county_fips": fips, "year": yr, "month": mo,
                     "heatwave_events_started": len(started),
                     "heatwave_events_active": g["event_label"].nunique(),
                     "longest_event_duration_days": int(g["duration"].max()),
                     "event_ids_started": ";".join(started),
                     "event_ids_active": ";".join(sorted(g["event_label"].unique()))})
    cm = pd.DataFrame(rows).merge(hwd, on=["county_fips", "year", "month"], how="outer")
    cm["heatwave_days"] = cm["heatwave_days"].fillna(0).astype(int)
    for c in ["heatwave_events_started", "heatwave_events_active", "longest_event_duration_days"]:
        cm[c] = cm[c].fillna(0).astype(int)
    cm["county_name"] = cm["county_fips"].map(county_names)
    return cm.sort_values(["county_fips", "year", "month"])[
        ["county_fips", "county_name", "year", "month", "heatwave_events_started", "heatwave_events_active",
         "heatwave_days", "longest_event_duration_days", "event_ids_started", "event_ids_active"]]


def county_year(ev, hw):
    rows = []
    for (fips, yr), g in ev.groupby(["county_fips", "onset_year"]):
        hwy = hw[(hw["county_fips"] == fips) & (hw["year"] == yr)]
        rows.append({"county_fips": fips, "county_name": g["county_name"].iloc[0], "year": yr,
                     "heatwave_events_started": len(g),
                     "heatwave_days": int(len(hwy)),
                     "first_event_start_date": g["start_date"].min().date(),
                     "last_event_end_date": g["end_date"].max().date(),
                     "longest_event_duration_days": int(g["event_duration_days"].max()),
                     "event_durations": ",".join(str(int(x)) for x in sorted(g["event_duration_days"])),
                     "event_ids": ";".join(g.sort_values("start_date")["event_label"])})
    return pd.DataFrame(rows).sort_values(["county_fips", "year"])


# ---------------------------------------------------------------- run both windows
county_names = cd.drop_duplicates("county_fips").set_index("county_fips")["county_name"].to_dict()
qc_rows = []
WINDOWS = {"w15": thresholds_centered(cdv, HALF), "month": thresholds_month(cdv)}

for W, thr in WINDOWS.items():
    log("\n[window=%s] %s" % (W, thr["window_method"].iloc[0]))
    thr["definition_id"] = DEFINITION_ID
    thr["percentile"] = PCTL
    thr["reference_method"] = "walk_forward_1979_to_Yminus1"
    thr.to_csv(os.path.join(OUT, "thresholds_%s.csv" % W), index=False)
    log("   thresholds rows=%d  n_ref %d-%d" % (len(thr), int(thr["n_reference_values"].min()),
                                                int(thr["n_reference_values"].max())))
    # join thresholds to analysis-period days
    keys = ["county_fips", "calendar_month", "calendar_day", "analysis_year"] if W == "w15" \
        else ["county_fips", "calendar_month", "analysis_year"]
    left = ["county_fips", "month", "day", "year"] if W == "w15" else ["county_fips", "month", "year"]
    an = cd[(cd["year"] >= AN0) & (cd["year"] <= AN1)].merge(
        thr[keys + ["threshold_value_f", "n_reference_values"]], left_on=left, right_on=keys, how="left")
    an["exceedance_f"] = an[HI] - an["threshold_value_f"]
    an["relative_exceedance"] = (an[HI] > an["threshold_value_f"]).astype("Int64")
    artifact = an.get("qc_rh_pin_likely_artifact", pd.Series(False, index=an.index)).fillna(False)

    def cand(floor=None, drop_art=True):
        c = np.where(an[HI].isna() | an["threshold_value_f"].isna(), np.nan, (an["relative_exceedance"] == 1).astype(float))
        if floor is not None:
            c = np.where(np.isnan(c), np.nan, ((c == 1) & (an[HI] >= floor)).astype(float))
        c = pd.Series(c, index=an.index)
        return c.where(~artifact.values, np.nan) if drop_art else c

    # QA sensitivities (pooled QA only)
    for tag, floor, drop in [("PRIMARY_nofloor_artifactmissing", None, True),
                             ("sens_nofloor_retainall", None, False),
                             ("sens_floor80_artifactmissing", 80.0, True)]:
        aa = an.copy(); aa["candidate_day_flag"] = cand(floor, drop).values
        dd = classify(aa, "%s__%s__%s" % (DEFINITION_ID, W, tag))
        n_hd = int(dd["heatwave_day_flag"].fillna(0).sum())
        n_ev = dd.loc[dd["heatwave_day_flag"] == 1, "event_id"].nunique()
        qc_rows.append({"window": W, "scenario": tag, "heatwave_days_QA_pooled": n_hd,
                        "heatwave_events_QA_pooled": n_ev})
        if tag == "PRIMARY_nofloor_artifactmissing":
            prim = dd

    # PRIMARY outputs for this window
    for c in ["relative_exceedance", "candidate_day_flag", "run_length", "heatwave_day_flag",
              "event_duration_days", "event_day_number", "event_onset_flag", "event_final_day_flag"]:
        if c in prim.columns:
            prim[c] = prim[c].astype("Int64")
    prim["definition_id"] = DEFINITION_ID
    prim["window_method"] = thr["window_method"].iloc[0]
    prim[[c for c in DAILY_KEEP if c in prim.columns] + ["definition_id", "window_method"]].to_csv(
        os.path.join(OUT, "daily_classification_%s.csv" % W), index=False)

    hw = prim[prim["heatwave_day_flag"] == 1].copy()
    # heatwave-DAY table (only county-dates that ARE heatwave days), carries temps + threshold
    hw[[c for c in DAILY_KEEP if c in hw.columns] + ["definition_id", "window_method"]].to_csv(
        os.path.join(OUT, "daily_heatwave_days_%s.csv" % W), index=False)

    ev = build_event_table(hw)
    ev.to_csv(os.path.join(OUT, "heatwave_events_%s.csv" % W), index=False)
    county_month(ev, hw, county_names).to_csv(os.path.join(OUT, "county_month_summary_%s.csv" % W), index=False)
    county_year(ev, hw).to_csv(os.path.join(OUT, "county_year_summary_%s.csv" % W), index=False)
    log("   PRIMARY: heatwave days=%d  heatwave events=%d  (QA-pooled; see county tables for substance)"
        % (int(hw["heatwave_day_flag"].sum()), len(ev)))

pd.DataFrame(qc_rows).to_csv(os.path.join(OUT, "sensitivity_scenarios_qc_totals.csv"), index=False)
log("\n[QA-only pooled totals] (NOT headline):")
log(pd.DataFrame(qc_rows).to_string(index=False))
log("\n[done] build_def01 complete for both windows.")
