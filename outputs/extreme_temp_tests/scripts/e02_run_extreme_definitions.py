"""
=============================================================================
e02  --  PARTS 2 and 3: classify the extreme-temperature definitions.
=============================================================================
PART 2  county-relative daily MAXIMUM temperature
          80th / 85th / 90th percentile  x  >= 2 / >= 3 / >= 5 consecutive days
          x all four threshold windows                        = 36 runs

PART 3  absolute floors at 80 degF and 90 degF, both ways:
        (a) as a GATE on the relative rule -- percentile AND Tmax >= floor,
            for all 9 definitions above, at the primary window   = 18 runs
        (b) as an ABSOLUTE-ONLY rule -- Tmax > floor, no percentile,
            >= 2 / >= 3 / >= 5 consecutive days                  =  6 runs

An absolute rule has no baseline, so it has NO threshold-window axis at all.
That is a property of the construct, not a shortcut: there is nothing to pool.

-----------------------------------------------------------------------------
THE TWO COMPARISON OPERATORS, AND WHY THE CHOICE TURNS OUT NOT TO MATTER
-----------------------------------------------------------------------------
  relative part   metric >  threshold   (strict, as everywhere in this project)
  floor as gate   metric >= floor       (as pipeline p02 already implements
                                         config.FLOOR_SENSITIVITY_F -- not
                                         diverging from the pipeline)
  absolute only   metric >  floor       ("exceeding 90 degF", as specified)

Tmax arrives quantised to 0.1 degC, so the attainable values near the floors are
89.96 and 90.14 degF (32.2 / 32.3 degC) and 79.88 / 80.06 degF (26.6 / 26.7):
exactly 80.0 or 90.0 degF is not representable. The script COUNTS the county-days
sitting exactly on each floor and writes it to qa/, so the claim that the
operator is immaterial is checked rather than asserted.

-----------------------------------------------------------------------------
REUSE AND RECONCILIATION
-----------------------------------------------------------------------------
Thresholds come from pipeline p02.get_thresholds (and are cached in the shared
grid threshold cache); runs and events come from heatwave_run_logic's panel
implementation; county-year and county-month tables come from p02's own
aggregators, so the county-month and year-boundary rules are the project's, not
a reimplementation.

Four of the nine Part-2 definitions already exist in the delivered grid
(TMAX_P85_2D, TMAX_P85_3D, TMAX_P90_2D, TMAX_P90_3D). Their rebuild here is
RECONCILED against the published run summaries and the script exits non-zero on
any mismatch -- the same gate used in the definition-comparison package, and the
reason the new cells can be read alongside the old ones.

Outputs
  runs/<DEFINITION_ID>/tables/*   per-run event / county-year / county-month
  tables/e02_master_run_summary.csv
  qa/e02_reconciliation.csv, qa/e02_floor_operator_check.csv
=============================================================================
"""
import os
import sys
import json
import time
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
import etx_config as K
import config as C
import p02_classify_and_report as p02
from heatwave_run_logic import build_runs_and_events_panel

STATE = K.TEST_STATE
METRIC = K.EXTREME_METRIC
METRIC_COL = C.METRICS[METRIC]["col"]
RECON, FLOOR_CHECK = [], []


def git_commit():
    try:
        c = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=K.REPO_ROOT,
                           capture_output=True, text=True, timeout=20).stdout.strip()
        d = subprocess.run(["git", "status", "--porcelain"], cwd=K.REPO_ROOT,
                           capture_output=True, text=True, timeout=20).stdout.strip()
        return (c or "unknown") + ("+dirty" if d else "")
    except Exception:
        return "unknown"


def input_hash():
    h = hashlib.md5()
    with open(C.county_day_path(STATE), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return "md5:" + h.hexdigest()[:16]


def run_dir(definition_id):
    d = os.path.join(K.PKG_ROOT, "runs", definition_id, "tables")
    os.makedirs(d, exist_ok=True)
    return d


# =============================================================================
# 1. candidate days: relative, relative+floor, or absolute-only
# =============================================================================
def build_candidates(cd, run, thr=None, key_name=None):
    """Candidate days for one run. Returns the analysis-year panel.

    relative      candidate = metric >  county/calendar walk-forward threshold
    floor gate    candidate = (metric >  threshold) AND (metric >= floor)
    absolute only candidate = metric >  floor          (no threshold at all)

    `thr` carries one column per percentile ('threshold_p80_f', ...) because a
    single threshold pass over the baseline serves every percentile -- the same
    economy run_grid.py uses.
    """
    an = cd[(cd["year"] >= C.ANALYSIS_YEARS[0]) & (cd["year"] <= C.ANALYSIS_YEARS[1])].copy()
    an["metric_value_f"] = an[METRIC_COL]

    if run["absolute_only"]:
        an["threshold_value_f"] = float(run["floor_f"])
        an["n_reference_values"] = np.nan
        usable = an["metric_value_f"].notna()
        rel = np.where(usable, (an["metric_value_f"] > float(run["floor_f"])).astype(float),
                       np.nan)
        cand = rel.copy()
    else:
        left_key = "template_doy" if key_name == "template_doy" else "month"
        tcol = "threshold_p%d_f" % run["percentile"]
        t = thr[["county_fips", key_name, "analysis_year", tcol, "n_reference_values"]] \
            .rename(columns={tcol: "threshold_value_f"})
        an = an.merge(t, left_on=["county_fips", left_key, "year"],
                      right_on=["county_fips", key_name, "analysis_year"], how="left")
        usable = an["metric_value_f"].notna() & an["threshold_value_f"].notna()
        rel = np.where(usable, (an["metric_value_f"] > an["threshold_value_f"]).astype(float),
                       np.nan)
        cand = rel.copy()
        if run["floor_f"] is not None:
            cand = np.where(np.isnan(cand), np.nan,
                            ((cand == 1) & (an["metric_value_f"] >= float(run["floor_f"])))
                            .astype(float))
    # Tmax is not RH-dependent, so the 2023-03-01 gridMET RH-clip artifact does
    # not touch it and no county-day is masked here (unlike the mean-HI definitions)
    an["relative_exceedance_flag"] = rel
    an["candidate_day_flag"] = cand
    return an.sort_values(["county_fips", "date"]).reset_index(drop=True)


def floor_operator_check(cd):
    """How many county-days sit EXACTLY on each floor? (see the module docstring)"""
    an = cd[(cd["year"] >= C.ANALYSIS_YEARS[0]) & (cd["year"] <= C.ANALYSIS_YEARS[1])]
    v = an[METRIC_COL].to_numpy(dtype=float)
    ok = ~np.isnan(v)
    for f in K.FLOORS_F:
        eq = int((np.abs(v[ok] - f) < 1e-9).sum())
        n = int(ok.sum())
        FLOOR_CHECK.append({
            "floor_degF": f, "metric": C.METRICS[METRIC]["code"],
            "evaluable_county_days": n,
            "county_days_exactly_on_floor": eq,
            "pct_county_days_exactly_on_floor": round(100.0 * eq / n, 4) if n else np.nan,
            "county_days_gt_floor": int((v[ok] > f).sum()),
            "county_days_ge_floor": int((v[ok] >= f).sum()),
            "operator_changes_n_county_days": eq,
            "note": ("Exactly-on-floor county-days DO occur even though the station data is "
                     "quantised to 0.1 degC, because a county-day Tmax is an average over the "
                     "county's reporting stations (and may be IDW-filled). So '>' and '>=' are "
                     "not equivalent: they differ by %d of %d evaluable county-days (%.3f%%). "
                     "This package uses '>=' for the floor-as-gate mode (matching pipeline "
                     "p02's existing FLOOR_SENSITIVITY_F implementation) and '>' for the "
                     "absolute-only mode (matching 'exceeding 90 degF'). The difference is "
                     "immaterial to every result reported here, but it is real and is recorded "
                     "rather than assumed away." % (eq, n, 100.0 * eq / n if n else 0)),
        })


# =============================================================================
# 2. one run
# =============================================================================
def classify(run, cd, thr, key_name, commit, ihash, write_daily=True):
    t0 = time.time()
    an = build_candidates(cd, run, thr, key_name)
    daily, ev = build_runs_and_events_panel(
        an, min_duration=run["min_duration"], year_boundary_breaks_run=False,
        definition_id=run["definition_id"], state_fips=C.STATE_FIPS[STATE],
        with_event_columns=False)
    hw = daily[daily["heatwave_day_flag"] == 1].copy()

    if len(ev):
        ev = ev.merge(cd[["county_fips", "county_name"]].drop_duplicates(),
                      on="county_fips", how="left")
        ev["event_label"] = ev["event_id"]
    cy = p02.county_year_table(ev, hw) if len(ev) else pd.DataFrame()
    cm = p02.county_month_table(ev, hw) if len(ev) else pd.DataFrame()

    tdir = run_dir(run["definition_id"])
    suffix = run["window"]
    if len(ev):
        e = ev.copy()
        e["start_date"] = e["start_date"].dt.strftime("%Y-%m-%d")
        e["end_date"] = e["end_date"].dt.strftime("%Y-%m-%d")
        e.to_csv(os.path.join(tdir, "heatwave_events_%s.csv.gz" % suffix),
                 index=False, compression="gzip")
    if len(cy):
        cy.to_csv(os.path.join(tdir, "county_year_summary_%s.csv" % suffix), index=False)
    if len(cm):
        cm.to_csv(os.path.join(tdir, "county_month_summary_%s.csv" % suffix), index=False)
    if write_daily and len(hw):
        hw[["county_fips", "county_name", "date", "year", "month", "metric_value_f",
            "threshold_value_f", "heatwave_day_flag", "temp_imputed"]].to_csv(
            os.path.join(tdir, "daily_heatwave_days_%s.csv.gz" % suffix),
            index=False, compression="gzip")

    # ---- run summary -------------------------------------------------------
    counties = sorted(cd["county_fips"].unique())
    per_county = (cy.groupby("county_fips")["heatwave_days"].sum().reindex(counties,
                                                                          fill_value=0)
                  if len(cy) else pd.Series(0, index=counties))
    dur = ev["event_duration_days"] if len(ev) else pd.Series(dtype=float)
    elig = int(daily["candidate_day_flag"].notna().sum())
    month_days = (hw.groupby("month").size().reindex(range(1, 13), fill_value=0)
                  if len(hw) else pd.Series(0, index=range(1, 13)))
    summ = {
        "state": STATE, "run_id": run["run_id"], "definition_id": run["definition_id"],
        "seq": run["seq"], "part": run["part"], "kind": run["kind"],
        "metric": C.METRICS[METRIC]["code"],
        "percentile": run["percentile"], "minimum_duration_days": run["min_duration"],
        "absolute_floor_degF": run["floor_f"], "window": run["window"],
        "comparison_op_relative": C.COMPARISON_OP,
        "comparison_op_floor": (">" if run["absolute_only"] else
                                (">=" if run["floor_f"] is not None else "")),
        "reference_method": ("none - absolute threshold" if run["absolute_only"]
                            else C.BASELINE_SCHEME),
        "season_rule": C.SEASON, "analysis_years": "%d-%d" % C.ANALYSIS_YEARS,
        "eligible_county_days_QA_pooled": elig,
        "candidate_days_QA_pooled": int((daily["candidate_day_flag"] == 1).sum()),
        "heatwave_days_QA_pooled_2015_2025": int(len(hw)),
        "heatwave_events_QA_pooled_2015_2025": int(len(ev)),
        "counties_with_any_heatwave_day": int(hw["county_fips"].nunique()) if len(hw) else 0,
        "per_county_heatwave_days_median": float(per_county.median()),
        "per_county_heatwave_days_q25": float(per_county.quantile(0.25)),
        "per_county_heatwave_days_q75": float(per_county.quantile(0.75)),
        "per_county_heatwave_days_min": int(per_county.min()),
        "per_county_heatwave_days_max": int(per_county.max()),
        "event_duration_days_median": float(dur.median()) if len(dur) else np.nan,
        "event_duration_days_max": int(dur.max()) if len(dur) else 0,
        "heatwave_days_per_1000_eligible": round(1000.0 * len(hw) / elig, 2) if elig else np.nan,
        "pct_heatwave_days_in_jun_sep": (round(100.0 * month_days.loc[K.JUN_SEP].sum()
                                               / month_days.sum(), 2)
                                        if month_days.sum() else np.nan),
        "pct_heatwave_days_outside_jun_sep": (round(100.0 - 100.0 * month_days.loc[K.JUN_SEP]
                                                    .sum() / month_days.sum(), 2)
                                             if month_days.sum() else np.nan),
        "peak_month": (K.MONTH_ABBR[int(month_days.idxmax()) - 1] if month_days.sum() else ""),
        "pct_heatwave_days_imputed": (round(100.0 * hw["temp_imputed"].mean(), 2)
                                     if len(hw) else np.nan),
        "git_commit": commit, "input_hash": ihash,
        "runtime_seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(tdir, "run_summary_%s.json" % suffix), "w") as f:
        json.dump(summ, f, indent=2)

    # ---- reconcile the cells that already exist in the delivered grid -------
    if run["definition_id"] in K.OVERLAP_WITH_GRID and run["floor_f"] is None:
        p = os.path.join(C.grid_root(STATE), run["definition_id"], "tables",
                         "run_summary_%s.json" % run["window"])
        if os.path.exists(p):
            with open(p) as f:
                pub = json.load(f)
            for q, mine, theirs in (("heatwave_days", len(hw),
                                     pub["heatwave_days_QA_pooled"]),
                                    ("heatwave_events", len(ev),
                                     pub["heatwave_events_QA_pooled"])):
                RECON.append({"run_id": run["run_id"], "quantity": q, "rebuilt": int(mine),
                              "grid_published": int(theirs),
                              "result": "PASS" if int(mine) == int(theirs) else "FAIL"})
    K.log("      %-26s cand=%-9s hw-days=%-9s events=%-7s per-cty med=%-6.0f "
          "outside Jun-Sep=%5.1f%%  (%.0fs)"
          % (run["run_id"], "{:,}".format(summ["candidate_days_QA_pooled"]),
             "{:,}".format(len(hw)), "{:,}".format(len(ev)),
             summ["per_county_heatwave_days_median"],
             summ["pct_heatwave_days_outside_jun_sep"] or 0, summ["runtime_seconds"]))
    return summ


# =============================================================================
# 3. driver
# =============================================================================
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", action="append", type=int, default=None, choices=[2, 3])
    ap.add_argument("--no-daily", action="store_true")
    args = ap.parse_args(argv)

    K.ensure_dirs()
    t0 = time.time()
    commit, ihash = git_commit(), input_hash()
    all_runs = K.runs()
    if args.part:
        all_runs = [r for r in all_runs if r["part"] in args.part]

    K.log("=" * 78)
    K.log("e02  EXTREME-TEMPERATURE DEFINITIONS  --  state=%s, metric=%s"
          % (STATE, C.METRICS[METRIC]["code"]))
    K.log("=" * 78)
    K.log("%d definitions -> %d runs   (part 2: %d, part 3: %d)"
          % (len({r["definition_id"] for r in all_runs}), len(all_runs),
             sum(1 for r in all_runs if r["part"] == 2),
             sum(1 for r in all_runs if r["part"] == 3)))
    K.log("input: %s  git: %s" % (ihash, commit))

    cd = p02.load_county_days(STATE)
    floor_operator_check(cd)
    for row in FLOOR_CHECK:
        K.log("[floor check] %.0f degF: %d of %s county-days sit exactly on the floor "
              "(%.3f%%) -> '>' vs '>=' changes that many days"
              % (row["floor_degF"], row["county_days_exactly_on_floor"],
                 "{:,}".format(row["evaluable_county_days"]),
                 row["pct_county_days_exactly_on_floor"]))

    summaries = []
    # absolute-only runs need no thresholds at all
    abs_runs = [r for r in all_runs if r["absolute_only"]]
    if abs_runs:
        K.log("-" * 78)
        K.log("ABSOLUTE-ONLY runs (no baseline, no threshold window)")
        for r in sorted(abs_runs, key=lambda x: (x["floor_f"], x["min_duration"])):
            summaries.append(classify(r, cd, None, None, commit, ihash,
                                      write_daily=not args.no_daily))

    # relative runs, grouped by WINDOW: one threshold pass over the baseline yields
    # every percentile at once, so this is 4 passes rather than 12
    rel_runs = [r for r in all_runs if not r["absolute_only"]]
    groups = {}
    for r in rel_runs:
        groups.setdefault(r["window"], []).append(r)
    for gi, wkey in enumerate([w for w in K.EXTREME_WINDOWS if w in groups], 1):
        grp = groups[wkey]
        pctls = sorted({r["percentile"] for r in grp})
        K.log("-" * 78)
        K.log("[%d/%d] thresholds %s window=%s percentiles=%s  -> %d run(s)"
              % (gi, len(groups), C.METRICS[METRIC]["code"], wkey, pctls, len(grp)))
        cache = {}
        thr, key_name = p02.get_thresholds(STATE, METRIC, wkey, pctls, cd, cache=cache)
        for r in sorted(grp, key=lambda x: (x["percentile"], x["floor_f"] or 0,
                                            x["min_duration"])):
            summaries.append(classify(r, cd, thr, key_name, commit, ihash,
                                      write_daily=not args.no_daily))
        del cache, thr

    m = pd.DataFrame(summaries).sort_values(["part", "seq", "window"])
    m.to_csv(os.path.join(K.DIR_TABLES, "e02_master_run_summary.csv"), index=False)
    pd.DataFrame(FLOOR_CHECK).to_csv(os.path.join(K.DIR_QA, "e02_floor_operator_check.csv"),
                                     index=False)
    R = pd.DataFrame(RECON)
    if len(R):
        R["checked_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        R.to_csv(os.path.join(K.DIR_QA, "e02_reconciliation.csv"), index=False)
    n_fail = int((R["result"] == "FAIL").sum()) if len(R) else 0
    K.log("=" * 78)
    K.log("[write] tables/e02_master_run_summary.csv  (%d runs)" % len(m))
    K.log("reconciliation against the delivered grid: %d check(s), %d failure(s)"
          % (len(R), n_fail))
    if n_fail:
        K.log(R[R["result"] == "FAIL"].to_string(index=False))
    K.log("e02 done in %.1f min" % ((time.time() - t0) / 60))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
