"""
DEFINITION 01 -- the first heatwave threshold definition under examination:

  "A county relative 85th-percentile daily-MEAN heat index, >= 2 consecutive
   days, using the walk-forward baseline method; study period 2015-2025."

Concretely, for the 5 Texas pilot counties:
  metric      : daily-MEAN heat index proxy = heat_index(Tmean, mean RH)
                (Tmean = (Tmax+Tmin)/2 ; mean RH = (RHmax+RHmin)/2)
                -- note this is the daily-MEAN, NOT the daily-max (Tmax+RHmin)
                proxy used in the earlier pilot primary.
  threshold   : county-specific, calendar-day-of-year +/-15-day centered window,
                85th percentile, WALK-FORWARD (year Y drawn from 1979..Y-1)
  candidate   : mean_HI > threshold   (strict '>', per pilot convention)
  PRIMARY     : NO absolute floor (faithful to the definition as written)
  persistence : a HEATWAVE DAY is a candidate day inside a run of >= 2
                consecutive calendar days; a HEATWAVE EVENT is one such
                uninterrupted run within one county.
  artifacts   : the 3 confirmed RH-clip artifacts (qc_rh_pin_likely_artifact,
                2023-03-01) are set to MISSING in the primary (established
                data-quality practice); a retain-all sensitivity is also produced.
  sensitivity : (a) retain-all artifacts; (b) mean_HI>=80F absolute floor.

Reuses the already-built, review-corrected county-day table
(../../tables/05_county_daily_heat.csv) and the shared run/event logic.

TERMINOLOGY (per the reviewer's naming convention):
  heatwave day   = one county on one date inside a qualifying run (county-date)
  heatwave event = one uninterrupted run within one county
  event duration = integer count of consecutive calendar dates in the event
Pooled cross-county/-year totals are QA-only, never the headline.

Outputs (tables/):
  thresholds_walkforward_meanHI_doy.csv
  daily_heatwave_classification.csv        (one row per county-date)
  heatwave_events.csv                      (one row per event)
  county_month_summary.csv
  county_year_summary.csv
  sensitivity_scenarios_qc_totals.csv      (QA-only pooled totals)
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
OUT = os.path.join(HERE, "..", "tables")
os.makedirs(OUT, exist_ok=True)

HI = "hi_mean_f"                     # working name for the daily-mean HI proxy
SRC_HI = "derived_tmean_meanrh_hi_f" # its name in the source county-day table
WINDOW, PCTL, AN0, AN1, BASE_START, MIN_DUR = 15, 85, 2015, 2025, 1979, 2
DEFINITION_ID = "relMeanHI_p85_2d_walkforward"

_tpl = pd.date_range("2000-01-01", "2000-12-31")
MD_TO_TDOY = {(d.month, d.day): i + 1 for i, d in enumerate(_tpl)}
TDOY_TO_MD = {v: k for k, v in MD_TO_TDOY.items()}
N_TDOY = 366


def log(*a):
    print(*a, flush=True)


log("=" * 72)
log("DEFINITION 01: relative 85th-pctl daily-MEAN heat index, >=2 days, walk-forward")
log("  metric=%s  window=+/-%d d  pctl=%d  years=%d-%d  baseline_start=%d" %
    (SRC_HI, WINDOW, PCTL, AN0, AN1, BASE_START))
log("=" * 72)

cd = pd.read_csv(SRC_DAILY, dtype={"county_fips": str})
cd["date"] = pd.to_datetime(cd["date"])
cd = cd.rename(columns={SRC_HI: HI})
cd["template_doy"] = cd.apply(lambda r: MD_TO_TDOY[(int(r["month"]), int(r["day"]))], axis=1)
cd_valid = cd.dropna(subset=[HI])
log("[load] %d county-days, %d counties; mean-HI non-null=%d"
    % (len(cd), cd["county_fips"].nunique(), len(cd_valid)))

# ----------------------------------------------------------------------
# 1. WALK-FORWARD day-of-year thresholds on the daily-MEAN heat index
# ----------------------------------------------------------------------
log("[1] walk-forward day-of-year +/-15 thresholds on daily-mean HI ...")
thr_rows = []
t0 = time.time()
for fips in cd_valid["county_fips"].unique():
    name = cd_valid.loc[cd_valid["county_fips"] == fips, "county_name"].iloc[0]
    full = cd_valid[cd_valid["county_fips"] == fips][["year", "template_doy", HI]]
    for y in range(AN0, AN1 + 1):
        base = full[full["year"] <= y - 1]
        lo = base.assign(td=base["template_doy"] - N_TDOY)
        mid = base.assign(td=base["template_doy"])
        hi = base.assign(td=base["template_doy"] + N_TDOY)
        trip = pd.concat([lo, mid, hi], ignore_index=True).sort_values("td")
        tarr, harr = trip["td"].values, trip[HI].values
        for target in range(1, N_TDOY + 1):
            i0 = np.searchsorted(tarr, target - WINDOW, "left")
            i1 = np.searchsorted(tarr, target + WINDOW, "right")
            w = harr[i0:i1]
            m, d = TDOY_TO_MD[target]
            thr_rows.append((fips, name, m, d, y, np.percentile(w, PCTL) if w.size else np.nan, w.size))
thr = pd.DataFrame(thr_rows, columns=["county_fips", "county_name", "calendar_month", "calendar_day",
                                      "analysis_year", "threshold_value_f", "n_reference_values"])
thr["definition_id"] = DEFINITION_ID
thr["metric"] = "daily_mean_heat_index_proxy"
thr["percentile"] = PCTL
thr["window_days"] = 2 * WINDOW + 1
thr["reference_method"] = "walk_forward_1979_to_Yminus1"
thr["baseline_start_year"] = BASE_START
thr["baseline_end_year"] = thr["analysis_year"] - 1
thr.to_csv(os.path.join(OUT, "thresholds_walkforward_meanHI_doy.csv"), index=False)
log("    wrote thresholds (%d rows, %.1fs); n_ref %d-%d"
    % (len(thr), time.time() - t0, int(thr["n_reference_values"].min()), int(thr["n_reference_values"].max())))

# ----------------------------------------------------------------------
# 2. Classify the analysis period + build heatwave days / events
# ----------------------------------------------------------------------
an = cd[(cd["year"] >= AN0) & (cd["year"] <= AN1)].merge(
    thr[["county_fips", "calendar_month", "calendar_day", "analysis_year", "threshold_value_f", "n_reference_values"]],
    left_on=["county_fips", "month", "day", "year"],
    right_on=["county_fips", "calendar_month", "calendar_day", "analysis_year"], how="left")
an["exceedance_f"] = an[HI] - an["threshold_value_f"]
an["relative_exceedance"] = (an[HI] > an["threshold_value_f"]).astype("Int64")
artifact = an.get("qc_rh_pin_likely_artifact", pd.Series(False, index=an.index)).fillna(False)

# candidate builders for the three scenarios
def candidate(base_relexc, floor=None, drop_artifacts=True):
    cand = np.where(an[HI].isna() | an["threshold_value_f"].isna(), np.nan, base_relexc.astype(float))
    if floor is not None:
        cand = np.where(np.isnan(cand), np.nan, ((cand == 1) & (an[HI] >= floor)).astype(float))
    cand = pd.Series(cand, index=an.index)
    if drop_artifacts:
        cand = cand.where(~artifact.values, np.nan)
    return cand

relexc = (an["relative_exceedance"] == 1)
scenarios = {
    "PRIMARY_no_floor_artifactmissing": candidate(relexc, floor=None, drop_artifacts=True),
    "sens_no_floor_retainall":          candidate(relexc, floor=None, drop_artifacts=False),
    "sens_floor80_artifactmissing":     candidate(relexc, floor=80.0, drop_artifacts=True),
}


def classify(cand_series, definition_id):
    a = an.copy()
    a["candidate_day_flag"] = cand_series.values
    parts = []
    for fips, g in a.groupby("county_fips"):
        g = g.sort_values("date").set_index("date")
        gf = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))
        gf["county_fips"] = fips
        gf = gf.reset_index().rename(columns={"index": "date"})
        parts.append(build_runs_and_events(gf, min_duration=MIN_DUR, year_boundary_breaks_run=False,
                                           definition_id=definition_id, state_fips="48"))
    out = pd.concat(parts, ignore_index=True)
    out["year"] = out["date"].dt.year
    out["month"] = out["date"].dt.month
    return out


log("[2] classifying scenarios (heatwave day = candidate inside a >=2-day run) ...")
daily = {}
qc_rows = []
for tag, cand in scenarios.items():
    d = classify(cand, DEFINITION_ID + "__" + tag)
    daily[tag] = d
    n_hd = int(d["heatwave_day_flag"].fillna(0).sum())
    n_ev = d.loc[d["heatwave_day_flag"] == 1, "event_id"].nunique()
    n_cand = int((d["candidate_day_flag"] == 1).sum())
    qc_rows.append({"scenario": tag, "heatwave_days_QA_pooled": n_hd, "heatwave_events_QA_pooled": n_ev,
                    "candidate_days": n_cand,
                    "pct_candidates_removed_by_persistence": round(100 * (1 - n_hd / n_cand), 2) if n_cand else np.nan})
    log("    %-38s heatwave-days=%5d  heatwave-events=%4d  (candidates=%d)" % (tag, n_hd, n_ev, n_cand))

pd.DataFrame(qc_rows).to_csv(os.path.join(OUT, "sensitivity_scenarios_qc_totals.csv"), index=False)
log("    [note] the pooled totals above are QA-ONLY -- NOT the headline; see county-level tables.")

# ----------------------------------------------------------------------
# 3. PRIMARY daily classification table (one row per county-date)
# ----------------------------------------------------------------------
prim = daily["PRIMARY_no_floor_artifactmissing"]
daily_cols = ["county_fips", "county_name", "date", "year", "month", "day",
              HI, "threshold_value_f", "n_reference_values", "exceedance_f",
              "relative_exceedance", "candidate_day_flag", "run_length", "heatwave_day_flag",
              "event_id", "event_duration_days", "event_day_number",
              "event_onset_flag", "event_final_day_flag", "qc_status"]
for c in ["relative_exceedance", "candidate_day_flag", "run_length", "heatwave_day_flag",
          "event_duration_days", "event_day_number", "event_onset_flag", "event_final_day_flag"]:
    if c in prim.columns:
        prim[c] = prim[c].astype("Int64")
prim["definition_id"] = DEFINITION_ID
prim[[c for c in daily_cols if c in prim.columns] + ["definition_id"]].to_csv(
    os.path.join(OUT, "daily_heatwave_classification.csv"), index=False)
log("[3] wrote daily_heatwave_classification.csv (PRIMARY) rows=%d" % len(prim))
log("[done] build_def01 classification complete -- reporting tables built by report_def01.py")
