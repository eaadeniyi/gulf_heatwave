"""
=============================================================================
hs02_classify.py  --  classify every construct in the registry.
=============================================================================
Implements plan revision 6, sections 1-4 and 6.

Percentile-threshold constructs (Tmax / HIPROXY / HIXENV) reuse
pipeline.p02_classify_and_report.compute_thresholds() (generic: takes any
metric_col string + window_spec, unmodified) and
pipeline.heatwave_run_logic.build_runs_and_events_panel() (unmodified). A
package-local candidate-builder replaces pipeline.p02.build_candidates(),
because that function is hard-wired to pipeline.config.METRICS (which only
knows tmax/tmin/mhi) and to the single legacy qc_rh_pin_likely_artifact flag,
whereas this package needs three QC tiers (RAW/CONFEXCL/PROBEXCL) driven by
its own qc_category field -- same core logic (strict '>' comparison against
a walk-forward threshold), parameterised for this package's needs instead of
duplicated into pipeline.config.METRICS.

EHF constructs do not use compute_thresholds()/build_candidates() at all --
occurrence is `ehf_c2_<baseline> > 0` directly. Two event tables are built:
  ehf_positive_periods.csv        reuses build_runs_and_events_panel(), min_duration=1
  ehf_thermal_support_events.csv  a NEW interval-merge over each positive date's
                                  3-day support window [date-2, date]

Reused Tmax cells (role: reused_from_grid=True in the registry) are read from
outputs/TX/grid/ and fingerprint-verified, never recomputed.
=============================================================================
"""
import os, sys, time, json, hashlib
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hs00_config as H
sys.path.insert(0, H.PIPELINE_DIR)
from p02_classify_and_report import compute_thresholds, MD_TO_TDOY
from heatwave_run_logic import build_runs_and_events_panel
import config as PC   # pipeline/config.py -- read-only, for GRID_WINDOWS' w15 spec only

W15_SPEC = PC.GRID_WINDOWS["w15"]

QC_EXCLUDE_SETS = {
    "RAW": set(),
    "CONFEXCL": {"confirmed_artifact"},
    "PROBEXCL": {"confirmed_artifact", "rule_flagged_probable_artifact"},
}


def log(*a):
    print(*a, flush=True)


# =============================================================================
# 1. load the derived-variables table written by hs01
# =============================================================================
def load_derived(state="TX"):
    path = os.path.join(H.TABLES_DIR, "_derived_variables_%s.csv.gz" % state)
    cd = pd.read_csv(path, dtype={"county_fips": str})
    cd["date"] = pd.to_datetime(cd["date"])
    md = list(zip(cd["month"].to_numpy(), cd["day"].to_numpy()))
    cd["template_doy"] = np.array([MD_TO_TDOY[k] for k in md], dtype=np.int16)
    cd = cd.sort_values(["county_fips", "date"]).reset_index(drop=True)
    return cd


# =============================================================================
# 2. package-local candidate builder (percentile-threshold constructs only)
# =============================================================================
def build_candidates_local(cd, metric_col, percentile, thr, qc_tier=None):
    """Strict '>' comparison against the walk-forward w15 threshold, with this
    package's own QC-tier exclusion (not the legacy single artifact flag)."""
    tcol = "threshold_p%d_f" % percentile
    right = ["county_fips", "template_doy", "analysis_year"]
    left = ["county_fips", "template_doy", "year"]

    an = cd[(cd["year"] >= H.ANALYSIS_YEARS[0]) & (cd["year"] <= H.ANALYSIS_YEARS[1])].copy()
    an = an.merge(thr[right + [tcol, "n_reference_values"]], left_on=left, right_on=right,
                 how="left", suffixes=("", "_thr"))
    an = an.rename(columns={tcol: "threshold_value_f"})
    an["metric_value_f"] = an[metric_col]
    an["exceedance_f"] = an["metric_value_f"] - an["threshold_value_f"]

    usable = an["metric_value_f"].notna() & an["threshold_value_f"].notna()
    cand = np.where(usable, (an["metric_value_f"] > an["threshold_value_f"]).astype(float), np.nan)

    n_excluded = 0
    if qc_tier and QC_EXCLUDE_SETS[qc_tier]:
        excl = an["qc_category"].isin(QC_EXCLUDE_SETS[qc_tier]).to_numpy()
        n_excluded = int((excl & ~np.isnan(cand)).sum())
        cand = np.where(excl, np.nan, cand)
    an["candidate_day_flag"] = cand
    an["classification_eligible"] = (~pd.isna(cand)).astype(int) if qc_tier is None else np.where(
        an["qc_category"].isin(QC_EXCLUDE_SETS.get(qc_tier, set())), 0, (~pd.isna(cand)).astype(int))
    return an.sort_values(["county_fips", "date"]).reset_index(drop=True), n_excluded


def apply_season_restriction(an, season_rule):
    """June-September eligibility, imposed BEFORE run construction (plan Sec.10):
    outside the window -> analysis_eligible=0, candidate_flag=NA, breaking any run
    (May 31 cannot connect into Jun 1; Sep 30 cannot connect into Oct 1)."""
    if season_rule == "year_round":
        an["analysis_eligible"] = 1
        return an
    m0, d0 = H.JUNSEP_START
    m1, d1 = H.JUNSEP_END
    in_season = ((an["month"] > m0) | ((an["month"] == m0) & (an["day"] >= d0))) & \
                ((an["month"] < m1) | ((an["month"] == m1) & (an["day"] <= d1)))
    an["analysis_eligible"] = in_season.astype(int)
    an.loc[~in_season, "candidate_day_flag"] = np.nan
    an.loc[~in_season, "classification_eligible"] = 0
    return an


# =============================================================================
# 3. EHF thermal-support interval merge (new function; plan Sec.1)
# =============================================================================
def merge_support_intervals(dates_sorted):
    """dates_sorted: sorted array of positive-EHF assessment dates for ONE county.
    support(d) = [d-2, d]. Merges any intervals that overlap or touch (next.start
    <= current.end) -- two assessment dates 2 days apart merge into one event even
    if the day between them isn't itself positive, because their 3-day support
    windows share that boundary day."""
    if len(dates_sorted) == 0:
        return []
    starts = dates_sorted - pd.Timedelta(days=2)
    ends = dates_sorted.copy()
    merged = []
    cur_s, cur_e = starts[0], ends[0]
    for s, e in zip(starts[1:], ends[1:]):
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    return merged


def build_ehf_events(ehf_df, baseline_suffix, state_fips, definition_id):
    """Returns (daily_flagged_df, positive_periods_df, thermal_support_df)."""
    col = "ehf_c2_%s" % baseline_suffix
    an = ehf_df.copy()
    if baseline_suffix == "wf":
        an = an[(an["year"] >= H.ANALYSIS_YEARS[0]) & (an["year"] <= H.ANALYSIS_YEARS[1])].copy()
    an["candidate_day_flag"] = np.where(an[col].isna(), np.nan, (an[col] > 0).astype(float))

    daily, ev_runs = build_runs_and_events_panel(
        an, min_duration=1, year_boundary_breaks_run=False,
        definition_id=definition_id, state_fips=state_fips, with_event_columns=False)
    daily = daily.rename(columns={"heatwave_day_flag": "ehf_positive_flag"})
    hw = daily[daily["ehf_positive_flag"] == 1].copy()
    ev_runs["event_definition_type"] = "positive_ehf_assessment_period"
    ev_runs = ev_runs.rename(columns={"start_date": "ehf_assessment_period_start",
                                      "end_date": "ehf_assessment_period_end"})

    support_rows = []
    for fips, g in hw.groupby("county_fips", sort=True):
        merged = merge_support_intervals(np.sort(g["date"].to_numpy()))
        for i, (s, e) in enumerate(merged, start=1):
            support_rows.append({
                "county_fips": fips, "seq": i,
                "ehf_support_start_date": pd.Timestamp(s), "ehf_support_end_date": pd.Timestamp(e),
                "support_duration_days": int((pd.Timestamp(e) - pd.Timestamp(s)).days) + 1,
                "event_definition_type": "merged_thermal_support_interval",
            })
    support_df = pd.DataFrame(support_rows)
    if len(support_df):
        support_df["event_id"] = (state_fips + "_" + support_df["county_fips"].astype(str).str[-3:] + "_" +
                                  support_df["ehf_support_start_date"].dt.year.astype(str) + "_" +
                                  support_df["seq"].map(lambda s: "%03d" % s) + "_" + definition_id + "_SUPPORT")
    return daily, hw, ev_runs, support_df


# =============================================================================
# 4. reuse verification for the 6 Tmax cells pulled from outputs/TX/grid/
# =============================================================================
def source_grid_dir(source_run_id):
    """source_run_id like 'TMAX_P85_3D__w15' -> outputs/TX/grid/TMAX_P85_3D/tables/..._w15.csv*"""
    definition_id, window_key = source_run_id.split("__")
    return os.path.join(H.GRID_ROOT, definition_id, "tables"), window_key


def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_grid_table(tdir, stem, wkey):
    """Grid event tables are stored gzipped (they were compressed to keep the repo
    manageable: 268MB -> 68MB across 56 runs); the county summaries are plain CSV.
    Accept either, so this works regardless of which form a given table is in."""
    for ext in (".csv", ".csv.gz"):
        p = os.path.join(tdir, "%s_%s%s" % (stem, wkey, ext))
        if os.path.exists(p):
            return pd.read_csv(p, dtype={"county_fips": str}), p
    raise FileNotFoundError("no %s_%s.csv[.gz] under %s" % (stem, wkey, tdir))


def reuse_tmax_construct(construct):
    tdir, wkey = source_grid_dir(construct["source_run_id"])
    cy, cy_path = _read_grid_table(tdir, "county_year_summary", wkey)
    cm, _ = _read_grid_table(tdir, "county_month_summary", wkey)
    ev, ev_path = _read_grid_table(tdir, "heatwave_events", wkey)
    fingerprint = {
        "source_run_id": construct["source_run_id"],
        "source_county_year_path": cy_path, "source_county_year_hash": file_md5(cy_path),
        "source_events_path": ev_path, "source_events_hash": file_md5(ev_path),
        "reused_without_recalculation": True,
    }
    return cy, cm, ev, fingerprint


# =============================================================================
# driver: run every construct, write per-construct tables
# =============================================================================
def run_all(state="TX"):
    t0 = time.time()
    fips = "48"
    cd = load_derived(state)
    log("[load] derived table: %d rows" % len(cd))

    threshold_cache = {}   # (metric_col, percentile) -> (thr_df, key_name)
    ehf_df = cd   # the derived table already carries every EHF column

    results = {}
    for construct in H.CONSTRUCTS:
        cid = construct["construct_id"]
        t1 = time.time()
        ddir = H.construct_dir(cid)
        tdir = os.path.join(ddir, "tables")
        os.makedirs(tdir, exist_ok=True)

        if construct["reused_from_grid"]:
            cy, cm, ev, fp = reuse_tmax_construct(construct)
            cy.to_csv(os.path.join(tdir, "county_year_summary.csv"), index=False)
            cm.to_csv(os.path.join(tdir, "county_month_summary.csv"), index=False)
            ev.to_csv(os.path.join(tdir, "heatwave_events.csv.gz"), index=False, compression="gzip")
            with open(os.path.join(tdir, "reuse_fingerprint.json"), "w") as f:
                json.dump(fp, f, indent=2)
            log("[%s] reused from outputs/TX/grid/ (%s)" % (cid, construct["source_run_id"]))
            results[cid] = {"status": "reused", "n_events": len(ev)}
            continue

        if construct["family"] == "ehf":
            baseline_suffix = "fixed" if construct["baseline"] == "fixed_1979_2014" else "wf"
            daily, hw, positive_periods, support_df = build_ehf_events(
                ehf_df, baseline_suffix, fips, cid)
            positive_periods.to_csv(os.path.join(tdir, "ehf_positive_periods.csv"), index=False)
            support_df.to_csv(os.path.join(tdir, "ehf_thermal_support_events.csv"), index=False)
            hw.to_csv(os.path.join(tdir, "ehf_positive_assessment_dates.csv.gz"), index=False,
                     compression="gzip")
            log("[%s] EHF: %d positive assessment dates, %d positive-periods, %d thermal-support events (%.0fs)"
                % (cid, len(hw), len(positive_periods), len(support_df), time.time() - t1))
            results[cid] = {"status": "done", "n_positive_dates": len(hw),
                           "n_positive_periods": len(positive_periods),
                           "n_thermal_support_events": len(support_df)}
            continue

        # ---- percentile-threshold construct (Tmax / HIPROXY / HIXENV) ----
        metric_col = construct["metric"]
        pctl = construct["percentile"]
        key = (metric_col, pctl)
        if key not in threshold_cache:
            thr, key_name = compute_thresholds(cd, metric_col, [pctl], W15_SPEC, verbose=False)
            threshold_cache[key] = (thr, key_name)
        thr, key_name = threshold_cache[key]

        an, n_excluded = build_candidates_local(cd, metric_col, pctl, thr,
                                                qc_tier=construct.get("qc_tier") if construct["qc_tier"] != "n/a" else None)
        an = apply_season_restriction(an, construct["season_rule"])

        daily, ev_runs = build_runs_and_events_panel(
            an, min_duration=construct["min_duration"], year_boundary_breaks_run=False,
            definition_id=cid, state_fips=fips, with_event_columns=False)
        hw = daily[daily["heatwave_day_flag"] == 1].copy()
        ev_runs = ev_runs.merge(hw[["run_id", "county_name"]].drop_duplicates("run_id"),
                                on="run_id", how="left")

        hw.to_csv(os.path.join(tdir, "daily_classified.csv.gz"), index=False, compression="gzip")
        ev_runs.to_csv(os.path.join(tdir, "events.csv.gz"), index=False, compression="gzip")
        log("[%s] %d classified dates, %d events, %d excluded-by-QC dates (%.0fs)"
            % (cid, len(hw), len(ev_runs), n_excluded, time.time() - t1))
        results[cid] = {"status": "done", "n_classified": len(hw), "n_events": len(ev_runs),
                        "n_excluded_by_qc": n_excluded}

    log("[done] all %d constructs in %.1f min" % (len(H.CONSTRUCTS), (time.time() - t0) / 60))
    return results


if __name__ == "__main__":
    run_all()
