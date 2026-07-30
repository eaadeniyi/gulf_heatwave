"""
=============================================================================
s02  --  THE CANONICAL LONG TABLE, and the county/event tables built from it.
=============================================================================
One pass over all 64 runs (16 definitions x 4 threshold windows) that rebuilds
the classification from the SAME cached walk-forward thresholds the pipeline
used, and emits every level of aggregation the comparison needs, each labelled
with its unit of analysis:

  tables/canonical_long/canonical_<DEFINITION_ID>__<window>.csv.gz
        one row per COUNTY x DATE x DEFINITION x WINDOW
  tables/master_event_table.csv.gz          one row per EVENT
  tables/master_county_year_summary.csv     one row per COUNTY x YEAR x RUN
  tables/master_county_month_summary.csv    one row per COUNTY x YEAR x MONTH x RUN
  tables/eligibility_county_month.csv       valid-day DENOMINATORS, per metric x window
  tables/ref_county_climate_division.csv    county -> NOAA climate division
  qa/s02_reconciliation.csv                 rebuild vs the pipeline's own run tables

-----------------------------------------------------------------------------
WHAT IS AND IS NOT IN THE CANONICAL TABLE  (read this before using it)
-----------------------------------------------------------------------------
The full county x date x definition x window cross-product is 254 counties x
4,018 dates x 64 runs = 65.3 MILLION rows, which is not a usable CSV and, for
~90% of those rows, records only "this day was nowhere near the threshold".
So the canonical table is stored at its INFORMATIVE support:

    every county-day that is a CANDIDATE DAY (metric strictly above its own
    walk-forward percentile threshold), for every definition and window.

That set is a strict superset of the heatwave days, so nothing that any figure
in this package classifies is missing, and it still contains the ISOLATED
candidate days (candidate, but not part of a long enough run), which the event
audits need in order to show WHY a run stopped.

Consequences, handled explicitly rather than left implicit:
  * a county-day absent from a shard is "not a candidate day for that
    definition" -- it is NOT missing data and NOT a zero to be imputed;
  * DENOMINATORS therefore never come from this table. They come from
    eligibility_county_month.csv, which counts, per county x month, the days
    on which the definition COULD have been evaluated (metric present,
    threshold present, not an RH-clip artifact for RH-dependent metrics).
    Every rate in this package uses that denominator;
  * the full daily metric series for a county (candidate or not) is read
    straight from outputs/<ST>/county_daily_heat.csv by the figure scripts
    that draw time series (s06).

-----------------------------------------------------------------------------
FLAG DEFINITIONS (all three are kept, they are not the same thing)
-----------------------------------------------------------------------------
  relative_exceedance_flag  metric > its own county/calendar threshold, strict
                            ">", before any absolute floor and before artifact
                            masking. The purely relative statement.
  candidate_day_flag        the above, AND the absolute floor if one is
                            configured (none is, in all 16 definitions), AND
                            not a confirmed RH-clip artifact day for an
                            RH-dependent metric. NaN where the day could not
                            be evaluated at all.
  heatwave_day_flag         a candidate day inside a run of >= min_duration
                            consecutive calendar days. THE unit of exposure.

USAGE
    python s02_canonical_long.py                 # all 64 runs
    python s02_canonical_long.py --window w15    # subset, for a quick check
    python s02_canonical_long.py --definition TMAX_P90_2D
=============================================================================
"""
import os
import sys
import json
import time
import shutil
import hashlib
import argparse
import subprocess
import datetime

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defcmp_config as K
import config as C
import p02_classify_and_report as p02
from heatwave_run_logic import build_runs_and_events_panel

STATE = K.STATE

CANON_COLS = [
    "state", "county_fips", "county_name", "climate_division", "climdiv_id",
    "date", "year", "month",
    "run_id", "definition_id", "metric", "percentile", "minimum_duration", "window",
    "reference_method", "season_rule", "absolute_floor",
    "daily_metric_value", "threshold_value", "exceedance_degF", "n_reference_values",
    "relative_exceedance_flag", "candidate_day_flag", "heatwave_day_flag",
    "event_id", "event_start_date", "event_end_date", "event_duration_days",
    "observed_or_imputed", "temperature_imputation_fraction",
    "input_hash", "pipeline_version",
]

RECON = []


def git_commit():
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=K.REPO_ROOT,
                           capture_output=True, text=True, timeout=20)
        c = r.stdout.strip() or "unknown"
        d = subprocess.run(["git", "status", "--porcelain"], cwd=K.REPO_ROOT,
                           capture_output=True, text=True, timeout=20).stdout.strip()
        return c + ("+dirty" if d else "")
    except Exception:
        return "unknown"


def input_fingerprint():
    h = hashlib.md5()
    with open(C.county_day_path(STATE), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return "md5:" + h.hexdigest()[:16]


def recon(run_id, quantity, rebuilt, pipeline, note=""):
    ok = int(rebuilt) == int(pipeline)
    RECON.append({"run_id": run_id, "quantity": quantity, "rebuilt": int(rebuilt),
                  "pipeline_published": int(pipeline),
                  "result": "PASS" if ok else "FAIL", "note": note})
    return ok


# =============================================================================
# 1. reference layers: climate divisions, imputation, county names
# =============================================================================
def build_climate_divisions():
    """Copy the county -> NOAA climate-division crosswalk into the package.

    Division NUMBERS come from the NOAA/NCEI primary crosswalk; the NAMES are
    secondary-source labels for the same grouping. Recorded in the file itself so
    the distinction travels with the data.
    """
    dst = K.climate_division_path()
    src = os.path.abspath(K.CLIMDIV_SOURCE)
    if not os.path.exists(src):
        raise FileNotFoundError(
            "county -> climate-division crosswalk not found at %s. It is required for the "
            "climate_division column and for the documented example-county rule." % src)
    cd = pd.read_csv(src, dtype={"county_fips": str, "climdiv_id": str})
    cd["state"] = STATE
    cd["source"] = K.CLIMDIV_PROVENANCE
    cd = cd[["state", "county_fips", "climdiv_id", "division_name", "source"]]
    cd.to_csv(dst, index=False)
    K.log("[ref] %d counties -> %d climate divisions  ->  %s"
          % (len(cd), cd["climdiv_id"].nunique(), os.path.relpath(dst, K.PKG_ROOT)))
    return cd


def load_reference():
    """Climate divisions + per-county imputation fraction + county names."""
    cdiv = build_climate_divisions()
    cov = pd.read_csv(os.path.join(K.REPO_ROOT, "outputs", STATE,
                                   "coverage_and_imputation_report.csv"),
                      dtype={"county_fips": str})
    cov["fully_imputed_county"] = (cov["fully_imputed_county"].astype(str).str.lower()
                                   .isin(("true", "1", "yes")))
    ref = cov.merge(cdiv[["county_fips", "climdiv_id", "division_name"]],
                    on="county_fips", how="left")
    miss = ref["climdiv_id"].isna().sum()
    if miss:
        raise ValueError("%d counties have no climate-division assignment" % miss)
    ref = ref.rename(columns={"division_name": "climate_division",
                              "pct_analysis_days_imputed": "temperature_imputation_pct"})
    ref["temperature_imputation_fraction"] = (ref["temperature_imputation_pct"] / 100.0).round(6)
    return ref


# =============================================================================
# 2. thresholds from the pipeline's cache (never recomputed here)
# =============================================================================
def load_thresholds(metric, percentile, window_key):
    """Read the cached walk-forward thresholds written by the pipeline.

    Using the cache rather than recomputing is deliberate: the canonical table
    must be built from exactly the thresholds that produced the published run
    tables, and the reconciliation at the end proves it did.

    float_precision="round_trip" IS REQUIRED, not cosmetic. pandas' default CSV
    float parser is fast but not correctly rounded: it can be one unit in the
    last place off. The pipeline compared the metric against its IN-MEMORY
    threshold with a strict ">", and Tmax/Tmin are quantised (0.1 degC steps), so
    a percentile frequently lands EXACTLY on an observed value. A cached
    threshold of 101.74999999999999 read back as 101.75 turns a genuine
    exceedance of 1.4e-14 degF into a non-exceedance, and the rebuild silently
    loses that county-day. Round-trip parsing recovers the pipeline's own bits.
    (Those knife-edge days are counted per run in qa/s02_knife_edge_days.csv --
    they are a handful out of ~10^5 and immaterial to every result here, but
    they are real and are reported rather than hidden.)
    """
    p = C.threshold_cache_path(STATE, metric, percentile, window_key)
    if not os.path.exists(p):
        raise FileNotFoundError(
            "threshold cache missing: %s\n(run pipeline/run_grid.py and "
            "scripts/s01_rerun_legacy.py first)" % p)
    thr = pd.read_csv(p, dtype={"county_fips": str}, float_precision="round_trip")
    key_name = "template_doy" if "template_doy" in thr.columns else "calendar_month"
    return thr, key_name


# =============================================================================
# 3. one run -> canonical rows + event / county tables
# =============================================================================
def classify_run(run, cd, thr, key_name, ref, input_hash, pipeline_version):
    """Rebuild one run and return (canonical_candidate_rows, events, daily_heatwave)."""
    metric, pctl, dur = run["metric"], run["percentile"], run["min_duration"]
    metric_col = C.METRICS[metric]["col"]
    rh_dependent = C.METRICS[metric]["rh_dependent"]

    an = cd[(cd["year"] >= C.ANALYSIS_YEARS[0]) & (cd["year"] <= C.ANALYSIS_YEARS[1])].copy()
    left_key = "template_doy" if key_name == "template_doy" else "month"
    an = an.merge(thr[["county_fips", key_name, "analysis_year", "threshold_value_f",
                       "n_reference_values"]],
                  left_on=["county_fips", left_key, "year"],
                  right_on=["county_fips", key_name, "analysis_year"], how="left")
    an["metric_value_f"] = an[metric_col]

    usable = an["metric_value_f"].notna() & an["threshold_value_f"].notna()
    # the purely relative statement, before floor and before artifact masking
    rel = np.where(usable, (an["metric_value_f"] > an["threshold_value_f"]).astype(float), np.nan)
    cand = rel.copy()
    if C.GRID_FLOOR_F is not None:                      # no floor in any of the 16
        cand = np.where(np.isnan(cand), np.nan,
                        ((cand == 1) & (an["metric_value_f"] >= C.GRID_FLOOR_F)).astype(float))
    if rh_dependent:                                    # confirmed RH-clip artifact -> unusable
        art = an["qc_rh_pin_likely_artifact"].fillna(False).to_numpy()
        cand = np.where(art, np.nan, cand)
    an["relative_exceedance_flag"] = rel
    an["candidate_day_flag"] = cand
    an = an.sort_values(["county_fips", "date"]).reset_index(drop=True)

    # persistence rule -> heatwave days + events (the pipeline's own logic, with the
    # per-day event columns switched ON so every heatwave day carries its event id)
    daily, ev = build_runs_and_events_panel(
        an, min_duration=dur, year_boundary_breaks_run=False,
        definition_id=run["definition_id"], state_fips=C.STATE_FIPS[STATE],
        with_event_columns=True)

    # ---- canonical rows: the candidate days ---------------------------------
    keep = daily["candidate_day_flag"] == 1
    can = daily.loc[keep].copy()
    can = can.merge(ref[["county_fips", "climate_division", "climdiv_id",
                         "temperature_imputation_fraction"]], on="county_fips", how="left")
    can["state"] = STATE
    can["run_id"] = run["run_id"]
    can["definition_id"] = run["definition_id"]
    can["metric"] = run["metric_code"]
    can["percentile"] = pctl
    can["minimum_duration"] = dur
    can["window"] = run["window_key"]
    can["reference_method"] = run["reference_method"]
    can["season_rule"] = run["season_rule"]
    can["absolute_floor"] = run["absolute_floor"]
    # The two value columns are ROUNDED for readability, but the classification
    # turns on a strict ">" that can be decided in the 14th decimal place (Tmax /
    # Tmin are quantised, so a percentile often lands exactly on an observed
    # value). Rounded columns therefore cannot reproduce the flags. exceedance_degF
    # is written UNROUNDED so the table is self-verifying: for these definitions
    # candidate_day_flag == 1 exactly where exceedance_degF > 0 and the day is not
    # a masked artifact.
    can["daily_metric_value"] = can["metric_value_f"].round(3)
    can["threshold_value"] = can["threshold_value_f"].round(3)
    can["exceedance_degF"] = can["metric_value_f"] - can["threshold_value_f"]
    can["observed_or_imputed"] = np.where(can["temp_imputed"], "imputed", "observed")
    can["input_hash"] = input_hash
    can["pipeline_version"] = pipeline_version
    can["date"] = can["date"].dt.strftime("%Y-%m-%d")
    for c in ("event_start_date", "event_end_date"):
        can[c] = pd.to_datetime(can[c]).dt.strftime("%Y-%m-%d")
    can["event_duration_days"] = can["event_duration_days"].astype("Int64")
    for c in ("relative_exceedance_flag", "candidate_day_flag", "heatwave_day_flag"):
        can[c] = can[c].astype("Int64")
    can = can[CANON_COLS]

    # ---- the heatwave-day frame and the event frame -------------------------
    hw = daily.loc[daily["heatwave_day_flag"] == 1].copy()
    if len(ev):
        ev = ev.merge(cd[["county_fips", "county_name"]].drop_duplicates(),
                      on="county_fips", how="left")
        ev["event_label"] = ev["event_id"]

    # how many evaluable county-days sit on the knife edge of the strict ">"?
    # (see load_thresholds) -- reported, never silently absorbed
    gap = (daily["metric_value_f"] - daily["threshold_value_f"]).abs()
    knife = {
        "run_id": run["run_id"], "definition_id": run["definition_id"],
        "window": run["window_key"],
        "evaluable_county_days": int(daily["candidate_day_flag"].notna().sum()),
        "days_within_1e-9_degF_of_threshold": int((gap < 1e-9).sum()),
        "days_within_1e-6_degF_of_threshold": int((gap < 1e-6).sum()),
        "days_within_0.01_degF_of_threshold": int((gap < 0.01).sum()),
        "candidate_days": int((daily["candidate_day_flag"] == 1).sum()),
    }
    return can, ev, hw, daily, knife


def eligibility_rows(daily, metric_code, window_key):
    """Valid-day denominators for one (metric, window): per county x year x month,
    the days on which the definition could be evaluated at all.

    Depends on metric and window only -- NOT on percentile (a missing threshold is
    missing at every percentile) and not on duration -- so it is computed once per
    (metric, window) pair and reused by every definition that shares them.
    """
    d = daily
    g = pd.DataFrame({
        "county_fips": d["county_fips"], "year": d["year"], "month": d["month"],
        "calendar_days": 1,
        "eligible_days": d["candidate_day_flag"].notna().astype(int),
        "missing_metric_days": d["metric_value_f"].isna().astype(int),
        "missing_threshold_days": d["threshold_value_f"].isna().astype(int),
        "artifact_excluded_days": (d["relative_exceedance_flag"].notna()
                                   & d["candidate_day_flag"].isna()).astype(int),
        "imputed_days": d["temp_imputed"].astype(int),
    })
    out = g.groupby(["county_fips", "year", "month"], as_index=False).sum()
    out.insert(0, "metric", metric_code)
    out.insert(1, "window", window_key)
    return out


# =============================================================================
# 4. driver
# =============================================================================
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", action="append", default=None, choices=K.WINDOW_ORDER)
    ap.add_argument("--definition", action="append", default=None)
    ap.add_argument("--no-canonical", action="store_true",
                    help="rebuild the aggregates but do not rewrite the canonical shards")
    args = ap.parse_args(argv)

    K.ensure_dirs()
    t0 = time.time()
    input_hash = input_fingerprint()
    pipeline_version = git_commit()

    runs = K.runs_expanded()
    if args.window:
        runs = [r for r in runs if r["window_key"] in args.window]
    if args.definition:
        runs = [r for r in runs if r["definition_id"] in args.definition]

    K.log("=" * 74)
    K.log("s02  CANONICAL LONG TABLE  --  %d run(s), %d definition(s), %d window(s)"
          % (len(runs), len({r["definition_id"] for r in runs}),
             len({r["window_key"] for r in runs})))
    K.log("=" * 74)
    K.log("input      : %s" % input_hash)
    K.log("pipeline   : %s" % pipeline_version)

    ref = load_reference()
    cd = p02.load_county_days(STATE)

    ev_all, cy_all, cm_all, elig_all, knife_all = [], [], [], [], []
    seen_elig = set()

    # group by the threshold set so each cached threshold file is read once and
    # serves both the >=2-day and >=3-day definition that share it
    groups = {}
    for r in runs:
        groups.setdefault((r["metric"], r["percentile"], r["window_key"]), []).append(r)

    for gi, ((metric, pctl, wkey), grp) in enumerate(sorted(groups.items()), 1):
        thr, key_name = load_thresholds(metric, pctl, wkey)
        K.log("-" * 74)
        K.log("[%d/%d] thresholds %s P%d %s  (%s rows, key=%s)"
              % (gi, len(groups), C.METRICS[metric]["code"], pctl, wkey,
                 "{:,}".format(len(thr)), key_name))
        for run in sorted(grp, key=lambda x: x["min_duration"]):
            t1 = time.time()
            can, ev, hw, daily, knife = classify_run(run, cd, thr, key_name, ref,
                                                     input_hash, pipeline_version)
            knife_all.append(knife)
            if not args.no_canonical:
                can.to_csv(K.canonical_path(run["definition_id"], run["window_key"]),
                           index=False, compression="gzip")

            # ---- event table -------------------------------------------------
            if len(ev):
                e = ev.copy()
                e["state"] = STATE
                e["run_id"] = run["run_id"]
                e["definition_id"] = run["definition_id"]
                e["metric"] = run["metric_code"]
                e["percentile"] = run["percentile"]
                e["minimum_duration"] = run["min_duration"]
                e["window"] = run["window_key"]
                imp = hw.groupby("event_id")["temp_imputed"].agg(["sum", "size"])
                e = e.merge(imp.rename(columns={"sum": "imputed_days_in_event",
                                                "size": "days_in_event"}),
                            left_on="event_id", right_index=True, how="left")
                pk = hw.loc[hw.groupby("event_id")["metric_value_f"].idxmax(),
                            ["event_id", "date", "metric_value_f", "threshold_value_f"]]
                pk.columns = ["event_id", "peak_day_date", "peak_metric_value",
                              "peak_day_threshold_value"]
                e = e.merge(pk, on="event_id", how="left")
                e["event_crosses_month"] = (e["start_date"].dt.month != e["end_date"].dt.month) | \
                                           (e["start_date"].dt.year != e["end_date"].dt.year)
                e["event_crosses_year"] = e["start_date"].dt.year != e["end_date"].dt.year
                e["event_contains_imputed_day"] = e["imputed_days_in_event"].fillna(0) > 0
                e["flag_long_event_for_review"] = (e["event_duration_days"]
                                                   >= K.LONG_EVENT_REVIEW_DAYS)
                ev_all.append(e)

            # ---- county-year / county-month (the project's own rules) --------
            cy = p02.county_year_table(ev, hw) if len(ev) else pd.DataFrame()
            cm = p02.county_month_table(ev, hw) if len(ev) else pd.DataFrame()
            for frame, store in ((cy, cy_all), (cm, cm_all)):
                if len(frame):
                    f = frame.copy()
                    f["state"] = STATE
                    f["run_id"] = run["run_id"]
                    f["definition_id"] = run["definition_id"]
                    f["metric"] = run["metric_code"]
                    f["percentile"] = run["percentile"]
                    f["minimum_duration"] = run["min_duration"]
                    f["window"] = run["window_key"]
                    store.append(f)

            # ---- eligibility denominators, once per (metric, window) ---------
            if (metric, wkey) not in seen_elig:
                elig_all.append(eligibility_rows(daily, run["metric_code"], wkey))
                seen_elig.add((metric, wkey))

            # ---- reconcile against the pipeline's own published run summary ---
            jp = os.path.join(K.tables_dir_for(run["definition_id"]),
                              "run_summary_%s.json" % run["window_key"])
            if os.path.exists(jp):
                with open(jp) as f:
                    summ = json.load(f)
                ok1 = recon(run["run_id"], "heatwave_days", len(hw),
                            summ["heatwave_days_QA_pooled"], "QA pooled county-days")
                ok2 = recon(run["run_id"], "heatwave_events", len(ev),
                            summ["heatwave_events_QA_pooled"], "QA pooled events")
                mark = "ok" if (ok1 and ok2) else "MISMATCH"
            else:
                RECON.append({"run_id": run["run_id"], "quantity": "run_summary_present",
                              "rebuilt": 0, "pipeline_published": 0, "result": "FAIL",
                              "note": "no run_summary json on disk for this run"})
                mark = "NO PIPELINE SUMMARY"
            K.log("      %-26s candidates=%-9s heatwave-days=%-9s events=%-7s  %s (%.0fs)"
                  % (run["run_id"], "{:,}".format(len(can)), "{:,}".format(len(hw)),
                     "{:,}".format(len(ev)), mark, time.time() - t1))
        del thr

    # =========================================================================
    # write the masters
    # =========================================================================
    K.log("-" * 74)
    ev_cols = ["state", "run_id", "definition_id", "metric", "percentile", "minimum_duration",
               "window", "event_id", "event_label", "county_fips", "county_name",
               "start_date", "end_date", "event_duration_days", "onset_year",
               "peak_day_date", "peak_metric_value", "peak_day_threshold_value",
               "days_in_event", "imputed_days_in_event", "event_contains_imputed_day",
               "event_crosses_month", "event_crosses_year", "flag_long_event_for_review"]
    if ev_all:
        E = pd.concat(ev_all, ignore_index=True)
        E["start_date"] = E["start_date"].dt.strftime("%Y-%m-%d")
        E["end_date"] = E["end_date"].dt.strftime("%Y-%m-%d")
        E["peak_day_date"] = pd.to_datetime(E["peak_day_date"]).dt.strftime("%Y-%m-%d")
        E["peak_metric_value"] = E["peak_metric_value"].round(2)
        E["peak_day_threshold_value"] = E["peak_day_threshold_value"].round(2)
        E = E[ev_cols].sort_values(["run_id", "county_fips", "start_date"])
        E.to_csv(os.path.join(K.DIR_TABLES, "master_event_table.csv.gz"),
                 index=False, compression="gzip")
        K.log("[write] master_event_table.csv.gz            %s events" % "{:,}".format(len(E)))

    idcols = ["state", "run_id", "definition_id", "metric", "percentile",
              "minimum_duration", "window"]
    if cy_all:
        CY = pd.concat(cy_all, ignore_index=True)
        el = pd.concat(elig_all, ignore_index=True)
        ely = (el.groupby(["metric", "window", "county_fips", "year"], as_index=False)
                 [["calendar_days", "eligible_days", "imputed_days"]].sum()
                 .rename(columns={"eligible_days": "eligible_county_days",
                                  "imputed_days": "imputed_county_days"}))
        CY = CY.merge(ely, on=["metric", "window", "county_fips", "year"], how="left")
        CY["heatwave_days_per_1000_eligible_days"] = (
            1000.0 * CY["heatwave_days"] / CY["eligible_county_days"]).round(2)
        CY = CY[idcols + [c for c in CY.columns if c not in idcols]]
        CY.sort_values(["run_id", "county_fips", "year"]).to_csv(
            os.path.join(K.DIR_TABLES, "master_county_year_summary.csv"), index=False)
        K.log("[write] master_county_year_summary.csv       %s rows" % "{:,}".format(len(CY)))

    if cm_all:
        CM = pd.concat(cm_all, ignore_index=True)
        el = pd.concat(elig_all, ignore_index=True)
        CM = CM.merge(el.rename(columns={"eligible_days": "eligible_county_days",
                                         "imputed_days": "imputed_county_days"}),
                      on=["metric", "window", "county_fips", "year", "month"], how="left")
        CM["heatwave_days_per_1000_eligible_days"] = (
            1000.0 * CM["heatwave_days"] / CM["eligible_county_days"]).round(2)
        CM = CM[idcols + [c for c in CM.columns if c not in idcols]]
        CM.sort_values(["run_id", "county_fips", "year", "month"]).to_csv(
            os.path.join(K.DIR_TABLES, "master_county_month_summary.csv"), index=False)
        K.log("[write] master_county_month_summary.csv      %s rows" % "{:,}".format(len(CM)))

    if elig_all:
        EL = pd.concat(elig_all, ignore_index=True).sort_values(
            ["metric", "window", "county_fips", "year", "month"])
        EL.to_csv(os.path.join(K.DIR_TABLES, "eligibility_county_month.csv"), index=False)
        K.log("[write] eligibility_county_month.csv         %s rows (%d metric x window)"
              % ("{:,}".format(len(EL)), len(seen_elig)))

    if knife_all:
        KN = pd.DataFrame(knife_all)
        KN.to_csv(os.path.join(K.DIR_QA, "s02_knife_edge_days.csv"), index=False)
        K.log("[write] qa/s02_knife_edge_days.csv                %d county-days across all runs "
              "sit within 1e-9 degF of their threshold"
              % int(KN["days_within_1e-9_degF_of_threshold"].sum()))

    R = pd.DataFrame(RECON)
    R["checked_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    R.to_csv(os.path.join(K.DIR_QA, "s02_reconciliation.csv"), index=False)
    n_fail = int((R["result"] == "FAIL").sum())
    K.log("=" * 74)
    K.log("reconciliation vs the pipeline's own run tables: %d check(s), %d failure(s)"
          % (len(R), n_fail))
    if n_fail:
        K.log(R[R["result"] == "FAIL"].to_string(index=False))
    K.log("s02 done in %.1f min" % ((time.time() - t0) / 60))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
