"""
=============================================================================
STEP p02  --  classify heatwave days/events and build the reporting tables.
=============================================================================
Generalised over METRIC x PERCENTILE x MIN_DURATION x THRESHOLD WINDOW, so the
same code produces every definition in the grid AND the published Definition
01 / 02 (which are the special case metric="mhi", windows w15 + month).

For one definition and one window this step:

  1. Builds the county-specific, calendar-aware, WALK-FORWARD percentile
     threshold of the chosen metric (baseline = all years from BASELINE_START up
     to the year BEFORE the analysis year, re-estimated each analysis year).
  2. Flags candidate days (metric strictly ABOVE its own threshold), sets
     confirmed RH-clip artifacts to missing (only for RH-dependent metrics --
     the artifact does not touch Tmax/Tmin), and applies the >= min_duration
     consecutive-day persistence rule to get heatwave days and events.
  3. Writes the substantive, county-level reporting tables (event /
     county-month / county-year) with the metric, its threshold and the other
     metrics' same-day values included; pooled statewide totals are written
     separately and labelled QA-only.

WHY THRESHOLDS ARE CACHED SEPARATELY
  A threshold depends on (metric, percentile, window) but NOT on min_duration --
  the persistence rule is applied afterwards. numpy also returns several
  percentiles of one baseline pool in a single pass. So the expensive step runs
  once per (metric, window) and is reused by every percentile and both durations:
  12 threshold passes cover all 56 runs of the grid.

Reporting terminology is fixed: heatwave day / heatwave event / integer event
duration. Nothing is state-, metric- or percentile-specific in the code.
=============================================================================
"""
import os, sys, time, json
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
from heatwave_run_logic import build_runs_and_events_panel

# fixed 366-day (month,day) -> day-of-year template (leap-safe: "Mar 1" always maps
# to the same slot whether or not the historical year had a Feb 29).
_TPL = pd.date_range("2000-01-01", "2000-12-31")
MD_TO_TDOY = {(d.month, d.day): i + 1 for i, d in enumerate(_TPL)}
N_TDOY = 366
# first/last template day-of-year of each calendar month (used by the month windows)
MONTH_TDOY_RANGE = {m: (min(v for (mm, _), v in MD_TO_TDOY.items() if mm == m),
                        max(v for (mm, _), v in MD_TO_TDOY.items() if mm == m))
                    for m in range(1, 13)}

# same-day context columns carried into the outputs for every definition, so a
# Tmin-based event can still be read against that day's Tmax and heat index
CONTEXT_COLS = ["tmax_f", "tmin_f", "tmean_f", "rmin_pct", "derived_tmean_meanrh_hi_f"]


def log(*a):
    print(*a, flush=True)


# =============================================================================
# 1. INPUT
# =============================================================================
def load_county_days(state, verbose=True):
    """Load the p01 county-day table once; every definition reads this same frame."""
    path = C.county_day_path(state)
    usecols = (["county_fips", "county_name", "date", "year", "month", "day",
                "temp_imputed", "qc_rh_pin_likely_artifact", "qc_status"] + CONTEXT_COLS)
    cd = pd.read_csv(path, usecols=usecols, dtype={"county_fips": str})
    cd["date"] = pd.to_datetime(cd["date"])
    md = list(zip(cd["month"].to_numpy(), cd["day"].to_numpy()))
    cd["template_doy"] = np.array([MD_TO_TDOY[k] for k in md], dtype=np.int16)
    for c in ("temp_imputed", "qc_rh_pin_likely_artifact"):
        cd[c] = cd[c].astype(str).str.lower().isin(("true", "1", "yes"))
    cd = cd.sort_values(["county_fips", "date"]).reset_index(drop=True)
    if verbose:
        log("[load] %s: %d county-days, %d counties, %s..%s"
            % (state, len(cd), cd["county_fips"].nunique(),
               cd["date"].min().date(), cd["date"].max().date()))
    return cd


# =============================================================================
# 2. WALK-FORWARD PERCENTILE THRESHOLDS
# =============================================================================
def _window_keys(window_spec):
    """The (key, doy_lo, doy_hi) triples a window needs, and what the key means.

    Every window shape reduces to 'pool the baseline days whose template
    day-of-year falls in [lo, hi]', evaluated on a tripled day-of-year axis so
    intervals wrap cleanly across 1 Jan / 31 Dec:

      centered      366 keys, key = target day-of-year, interval = target +/- half
      month          12 keys, key = calendar month,     interval = that month
      month_collar   12 keys, key = calendar month,     interval = month +/- collar
    """
    wtype = window_spec["type"]
    if wtype == "centered":
        h = int(window_spec["half"])
        return "template_doy", [(d, d - h, d + h) for d in range(1, N_TDOY + 1)]
    if wtype == "month":
        return "calendar_month", [(m, MONTH_TDOY_RANGE[m][0], MONTH_TDOY_RANGE[m][1])
                                  for m in range(1, 13)]
    if wtype == "month_collar":
        col = int(window_spec["collar"])
        return "calendar_month", [(m, MONTH_TDOY_RANGE[m][0] - col, MONTH_TDOY_RANGE[m][1] + col)
                                  for m in range(1, 13)]
    raise ValueError("unknown window type: %r" % wtype)


def compute_thresholds(cd, metric_col, percentiles, window_spec, verbose=True):
    """Walk-forward county-relative percentile thresholds for one metric + window.

    Returns a long DataFrame: county_fips, <key>, analysis_year, n_reference_values,
    and one 'threshold_p<PCTL>_f' column per requested percentile.

    Walk-forward means the threshold used to judge year Y is estimated ONLY from
    years BASELINE_START..Y-1, re-estimated for every Y (year Y never helps define
    its own normal).
    """
    key_name, keys = _window_keys(window_spec)
    percentiles = sorted(percentiles)
    pcols = ["threshold_p%d_f" % p for p in percentiles]
    years = list(range(C.ANALYSIS_YEARS[0], C.ANALYSIS_YEARS[1] + 1))

    sub = cd.loc[cd[metric_col].notna(), ["county_fips", "year", "template_doy", metric_col]]
    counties = sorted(sub["county_fips"].unique())
    n_keys = len(keys)
    lo = np.array([k[1] for k in keys], dtype=np.int32)
    hi = np.array([k[2] for k in keys], dtype=np.int32)
    key_vals = np.array([k[0] for k in keys], dtype=np.int32)

    n_out = len(counties) * len(years) * n_keys
    out_thr = np.full((n_out, len(percentiles)), np.nan)
    out_n = np.zeros(n_out, dtype=np.int32)
    out_cty = np.empty(n_out, dtype=object)
    out_key = np.empty(n_out, dtype=np.int32)
    out_yr = np.empty(n_out, dtype=np.int32)

    t0 = time.time()
    pos = 0
    for ci, (fips, g) in enumerate(sub.groupby("county_fips", sort=True)):
        yrs = g["year"].to_numpy(dtype=np.int32)
        td = g["template_doy"].to_numpy(dtype=np.int32)
        val = g[metric_col].to_numpy(dtype=np.float64)
        for y in years:
            m = yrs <= (y - 1)                     # walk-forward: strictly prior years
            # tripled day-of-year axis so a window can wrap across the year boundary
            bt = np.concatenate([td[m] - N_TDOY, td[m], td[m] + N_TDOY])
            bv = np.tile(val[m], 3)
            order = np.argsort(bt, kind="stable")
            bt, bv = bt[order], bv[order]
            i0 = np.searchsorted(bt, lo, side="left")
            i1 = np.searchsorted(bt, hi, side="right")
            sl = slice(pos, pos + n_keys)
            out_cty[sl] = fips
            out_key[sl] = key_vals
            out_yr[sl] = y
            out_n[sl] = i1 - i0
            for j in range(n_keys):
                if i1[j] > i0[j]:
                    out_thr[pos + j, :] = np.percentile(bv[i0[j]:i1[j]], percentiles)
            pos += n_keys
        if verbose and (ci + 1) % 50 == 0:
            log("      thresholds: %d/%d counties (%.0fs)" % (ci + 1, len(counties), time.time() - t0))

    thr = pd.DataFrame({"county_fips": out_cty[:pos], key_name: out_key[:pos],
                        "analysis_year": out_yr[:pos], "n_reference_values": out_n[:pos]})
    for j, pc in enumerate(pcols):
        thr[pc] = out_thr[:pos, j]
    if verbose:
        log("      thresholds done: %d rows, percentiles=%s (%.0fs)"
            % (len(thr), percentiles, time.time() - t0))
    return thr, key_name


def get_thresholds(state, metric, window_key, percentiles, cd, cache=None, verbose=True):
    """Thresholds for (metric, window), covering every percentile needed.

    Memoised in `cache` and mirrored to gzipped CSV under grid/_thresholds/ so a
    re-run or a later definition never recomputes them.
    """
    ck = (state, metric, window_key)
    if cache is not None and ck in cache:
        thr, key_name, have = cache[ck]
        if set(percentiles).issubset(have):
            return thr, key_name
    metric_col = C.METRICS[metric]["col"]
    spec = C.GRID_WINDOWS[window_key]
    if verbose:
        log("   [thresholds] metric=%s window=%s percentiles=%s  (%s)"
            % (metric, window_key, sorted(percentiles), spec["label"]))
    thr, key_name = compute_thresholds(cd, metric_col, percentiles, spec, verbose=verbose)
    if cache is not None:
        cache[ck] = (thr, key_name, set(percentiles))
    # mirror to disk, one file per percentile (that is the unit other steps reuse)
    for p in percentiles:
        path = C.threshold_cache_path(state, metric, p, window_key)
        cols = ["county_fips", key_name, "analysis_year", "n_reference_values", "threshold_p%d_f" % p]
        t = thr[cols].rename(columns={"threshold_p%d_f" % p: "threshold_value_f"}).copy()
        t["metric"] = metric
        t["metric_col"] = metric_col
        t["percentile"] = p
        t["window_key"] = window_key
        t["window_method"] = spec["label"]
        t["baseline"] = C.BASELINE_SCHEME
        t["threshold_quality_flag"] = np.where(t["n_reference_values"] < C.MIN_REF_OBS,
                                               "low_n_ref", "ok")
        t.to_csv(path, index=False, compression="gzip")
    return thr, key_name


# =============================================================================
# 3. CANDIDATE DAYS
# =============================================================================
def build_candidates(cd, metric, percentile, thr, key_name, floor_f=None):
    """Join thresholds onto the analysis years and flag candidate days.

    candidate day = metric STRICTLY above its own county/calendar threshold.
      NaN metric or NaN threshold -> NaN (missing, breaks a run)
      confirmed RH-clip artifact  -> NaN, but ONLY for RH-dependent metrics; the
                                    artifact inflates the heat index and leaves
                                    Tmax/Tmin untouched, so temperature
                                    definitions legitimately keep those days.
    """
    metric_col = C.METRICS[metric]["col"]
    rh_dependent = C.METRICS[metric]["rh_dependent"]
    tcol = "threshold_p%d_f" % percentile
    right = ["county_fips", key_name, "analysis_year"]
    left = ["county_fips", "template_doy" if key_name == "template_doy" else "month", "year"]

    an = cd[(cd["year"] >= C.ANALYSIS_YEARS[0]) & (cd["year"] <= C.ANALYSIS_YEARS[1])].copy()
    an = an.merge(thr[right + [tcol, "n_reference_values"]], left_on=left, right_on=right, how="left")
    an = an.rename(columns={tcol: "threshold_value_f"})
    an["metric_value_f"] = an[metric_col]
    an["exceedance_f"] = an["metric_value_f"] - an["threshold_value_f"]

    usable = an["metric_value_f"].notna() & an["threshold_value_f"].notna()
    cand = np.where(usable, (an["metric_value_f"] > an["threshold_value_f"]).astype(float), np.nan)
    if floor_f is not None:                       # optional absolute floor (off in the grid)
        cand = np.where(np.isnan(cand), np.nan,
                        ((cand == 1) & (an["metric_value_f"] >= floor_f)).astype(float))
    n_artifact = 0
    if rh_dependent:
        art = an["qc_rh_pin_likely_artifact"].fillna(False).to_numpy()
        n_artifact = int((art & ~np.isnan(cand)).sum())
        cand = np.where(art, np.nan, cand)
    an["candidate_day_flag"] = cand
    an = an.sort_values(["county_fips", "date"]).reset_index(drop=True)
    return an, n_artifact


# =============================================================================
# 4. REPORTING TABLES  (county-level = substantive; pooled totals = QA only)
# =============================================================================
def event_table(hw, ev, metric):
    """One row per heatwave event, carrying the peak day's metric, threshold and
    the other metrics' same-day values."""
    if not len(ev):
        return pd.DataFrame()
    m = C.METRICS[metric]
    g = hw.groupby("run_id", sort=True)
    agg = g.agg(county_name=("county_name", "first"),
                peak_metric_value_f=("metric_value_f", "max"),
                mean_metric_value_f=("metric_value_f", "mean"),
                tmax_max_f=("tmax_f", "max"), tmin_max_f=("tmin_f", "max"),
                tmean_mean_f=("tmean_f", "mean"),
                mean_hi_max_f=("derived_tmean_meanrh_hi_f", "max"),
                peak_exceedance_f=("exceedance_f", "max"),
                cumulative_exceedance_f=("exceedance_f", lambda s: float(np.maximum(0, s).sum())),
                n_imputed_days=("temp_imputed", "sum"))
    pidx = g["metric_value_f"].idxmax()
    peak = hw.loc[pidx.to_numpy(), ["date", "threshold_value_f"] + CONTEXT_COLS]
    peak.index = pidx.index

    out = ev.set_index("run_id").join(agg).join(
        peak.rename(columns={"date": "peak_day_date", "threshold_value_f": "peak_day_threshold_f",
                             "tmax_f": "peak_day_tmax_f", "tmin_f": "peak_day_tmin_f",
                             "tmean_f": "peak_day_tmean_f", "rmin_pct": "peak_day_rmin_pct",
                             "derived_tmean_meanrh_hi_f": "peak_day_mean_hi_f"})).reset_index()
    out["event_label"] = (out["county_fips"] + "_" + out["onset_year"].astype(str) + "_"
                          + out["seq"].map(lambda s: "%03d" % s))
    out["metric"] = m["code"]
    out["event_contains_imputed_day"] = out["n_imputed_days"] > 0
    for c in ["peak_metric_value_f", "mean_metric_value_f", "tmax_max_f", "tmin_max_f",
              "tmean_mean_f", "mean_hi_max_f", "peak_exceedance_f", "cumulative_exceedance_f",
              "peak_day_threshold_f", "peak_day_tmax_f", "peak_day_tmin_f", "peak_day_tmean_f",
              "peak_day_rmin_pct", "peak_day_mean_hi_f"]:
        out[c] = out[c].astype(float).round(2)
    cols = ["event_label", "event_id", "county_fips", "county_name", "metric",
            "start_date", "end_date", "event_duration_days",
            "peak_metric_value_f", "peak_day_date", "peak_day_threshold_f", "peak_exceedance_f",
            "mean_metric_value_f", "cumulative_exceedance_f",
            "peak_day_tmax_f", "peak_day_tmin_f", "peak_day_tmean_f", "peak_day_rmin_pct",
            "peak_day_mean_hi_f", "tmax_max_f", "tmin_max_f", "tmean_mean_f", "mean_hi_max_f",
            "n_imputed_days", "event_contains_imputed_day", "onset_year"]
    return out.sort_values(["county_fips", "start_date"])[cols].reset_index(drop=True)


def county_year_table(ev, hw):
    """One row per county-year: events started (by onset year) + heatwave days."""
    if not len(ev):
        return pd.DataFrame()
    e = ev.groupby(["county_fips", "onset_year"]).agg(
        county_name=("county_name", "first"),
        heatwave_events_started=("event_label", "size"),
        first_event_start_date=("start_date", "min"),
        last_event_end_date=("end_date", "max"),
        longest_event_duration_days=("event_duration_days", "max")).reset_index()
    e = e.rename(columns={"onset_year": "year"})
    d = hw.groupby(["county_fips", "year"]).agg(
        heatwave_days=("heatwave_day_flag", "size"),
        heatwave_days_imputed=("temp_imputed", "sum")).reset_index()
    out = e.merge(d, on=["county_fips", "year"], how="outer")
    for c in ["heatwave_events_started", "heatwave_days", "heatwave_days_imputed",
              "longest_event_duration_days"]:
        out[c] = out[c].fillna(0).astype(int)
    for c in ["first_event_start_date", "last_event_end_date"]:
        out[c] = pd.to_datetime(out[c]).dt.date
    return out.sort_values(["county_fips", "year"]).reset_index(drop=True)


def county_month_table(ev, hw):
    """One row per county-month. A month-crossing event is counted ONCE at its
    onset month and counted as ACTIVE in every month it touches; heatwave DAYS are
    allocated to the calendar month they actually fall in."""
    if not len(ev):
        return pd.DataFrame()
    start_ym = ev["start_date"].dt.year.to_numpy() * 12 + (ev["start_date"].dt.month.to_numpy() - 1)
    end_ym = ev["end_date"].dt.year.to_numpy() * 12 + (ev["end_date"].dt.month.to_numpy() - 1)
    n_months = (end_ym - start_ym + 1)
    idx = np.repeat(np.arange(len(ev)), n_months)
    offset = np.arange(n_months.sum()) - np.repeat(np.cumsum(n_months) - n_months, n_months)
    ym = start_ym[idx] + offset
    act = pd.DataFrame({"county_fips": ev["county_fips"].to_numpy()[idx],
                        "year": ym // 12, "month": ym % 12 + 1,
                        "event_label": ev["event_label"].to_numpy()[idx],
                        "duration": ev["event_duration_days"].to_numpy()[idx],
                        "onset": offset == 0})
    a = act.groupby(["county_fips", "year", "month"]).agg(
        heatwave_events_started=("onset", "sum"),
        heatwave_events_active=("event_label", "nunique"),
        longest_event_duration_days=("duration", "max")).reset_index()
    d = hw.groupby(["county_fips", "year", "month"]).agg(
        heatwave_days=("heatwave_day_flag", "size"),
        heatwave_days_imputed=("temp_imputed", "sum")).reset_index()
    out = a.merge(d, on=["county_fips", "year", "month"], how="outer")
    for c in ["heatwave_events_started", "heatwave_events_active",
              "longest_event_duration_days", "heatwave_days", "heatwave_days_imputed"]:
        out[c] = out[c].fillna(0).astype(int)
    return out.sort_values(["county_fips", "year", "month"]).reset_index(drop=True)


def run_summary(state, run, hw, ev, cy, n_counties, n_artifact_missing, elapsed):
    """The headline row for this run in the cross-definition master table.

    Deliberately reports MEDIAN and RANGE of per-county heatwave days and MEDIAN
    and MAX event duration. Pooled cross-county totals are included but named
    _QA_ because they are QA quantities in this project, not headline results.
    """
    per_county = cy.groupby("county_fips")["heatwave_days"].sum()
    per_county = per_county.reindex(sorted(set(cy["county_fips"])), fill_value=0)
    dur = ev["event_duration_days"] if len(ev) else pd.Series(dtype=float)
    jun_sep = hw["month"].isin([6, 7, 8, 9]).mean() if len(hw) else np.nan
    return {
        "run_id": run["run_id"], "definition_id": run["definition_id"],
        "def_number": run["def_number"], "user_item": run["user_item"],
        "metric": run["metric_code"], "metric_label": run["metric_label"],
        "percentile": run["percentile"], "min_duration": run["min_duration"],
        "window_key": run["window_key"], "window_label": run["window_label"],
        "window_order": run["window_order"],
        "counties_total": n_counties,
        "counties_with_any_heatwave_day": int(hw["county_fips"].nunique()) if len(hw) else 0,
        "heatwave_days_QA_pooled": int(len(hw)),
        "heatwave_events_QA_pooled": int(len(ev)),
        "per_county_heatwave_days_median": float(per_county.median()),
        "per_county_heatwave_days_q25": float(per_county.quantile(0.25)),
        "per_county_heatwave_days_q75": float(per_county.quantile(0.75)),
        "per_county_heatwave_days_min": int(per_county.min()),
        "per_county_heatwave_days_max": int(per_county.max()),
        "event_duration_median_days": float(dur.median()) if len(dur) else np.nan,
        "event_duration_q75_days": float(dur.quantile(0.75)) if len(dur) else np.nan,
        "event_duration_max_days": int(dur.max()) if len(dur) else 0,
        "pct_heatwave_days_jun_sep": round(100 * float(jun_sep), 2) if len(hw) else np.nan,
        "pct_heatwave_days_imputed": (round(100 * float(hw["temp_imputed"].mean()), 2)
                                      if len(hw) else np.nan),
        "artifact_county_days_set_missing": int(n_artifact_missing),
        "artifact_handling": run["artifact_handling"],
        "baseline": run["baseline"], "season": run["season"],
        "absolute_floor": run["absolute_floor"], "comparison_op": run["comparison_op"],
        "analysis_years": run["analysis_years"],
        "runtime_seconds": round(elapsed, 1),
    }


DAILY_KEEP = ["county_fips", "county_name", "date", "year", "month", "metric_value_f",
              "threshold_value_f", "exceedance_f", "heatwave_day_flag", "event_id",
              "event_duration_days", "tmax_f", "tmin_f", "derived_tmean_meanrh_hi_f",
              "temp_imputed", "qc_status"]


# =============================================================================
# 5. DRIVERS
# =============================================================================
def run_one(state, run, cd, cache=None, outdir=None, write_daily=True, verbose=True):
    """Classify and report ONE run (= one definition at one threshold window)."""
    t0 = time.time()
    state_fips = C.STATE_FIPS[state]
    metric, pctl, dur, wkey = run["metric"], run["percentile"], run["min_duration"], run["window_key"]
    if outdir is None:
        outdir = C.grid_definition_dir(state, run["definition_id"])
    tdir = os.path.join(outdir, "tables")
    os.makedirs(tdir, exist_ok=True)
    if verbose:
        log("-" * 72)
        log("run %s  (Def %02d, item %s)" % (run["run_id"], run["def_number"], run["user_item"]))
        log("   %s" % C.definition_sentence(metric, pctl, dur, wkey))

    thr, key_name = get_thresholds(state, metric, wkey, [pctl], cd, cache=cache, verbose=verbose)
    an, n_artifact = build_candidates(cd, metric, pctl, thr, key_name, floor_f=C.GRID_FLOOR_F)
    daily, ev_runs = build_runs_and_events_panel(
        an, min_duration=dur, year_boundary_breaks_run=False,
        definition_id=run["definition_id"], state_fips=state_fips, with_event_columns=False)

    hw = daily[daily["heatwave_day_flag"] == 1].copy()
    ev = event_table(hw, ev_runs, metric)          # county_name comes from the aggregation
    cy = county_year_table(ev, hw)
    cm = county_month_table(ev, hw)

    # events are gzipped: the low-percentile 2-day definitions run to ~50k events x 26
    # columns (~9 MB each), and 56 of those would dominate the repository. pandas reads
    # .csv.gz transparently. The county-level summaries stay plain CSV -- they are small
    # and the ones most likely to be opened by hand.
    ev.to_csv(os.path.join(tdir, "heatwave_events_%s.csv.gz" % wkey), index=False,
              compression="gzip")
    cy.to_csv(os.path.join(tdir, "county_year_summary_%s.csv" % wkey), index=False)
    cm.to_csv(os.path.join(tdir, "county_month_summary_%s.csv" % wkey), index=False)
    if write_daily:
        hw[[c for c in DAILY_KEEP if c in hw.columns]].to_csv(
            os.path.join(tdir, "daily_heatwave_days_%s.csv.gz" % wkey), index=False, compression="gzip")
    # QA-only statewide pooled totals per year
    if len(hw):
        sy = hw.groupby("year").agg(heatwave_days_QA=("heatwave_day_flag", "size"),
                                    counties_with_any=("county_fips", "nunique"),
                                    heatwave_events_QA=("run_id", "nunique")).reset_index()
    else:
        sy = pd.DataFrame(columns=["year", "heatwave_days_QA", "counties_with_any", "heatwave_events_QA"])
    sy.to_csv(os.path.join(tdir, "state_year_qc_%s.csv" % wkey), index=False)

    summ = run_summary(state, run, hw, ev, cy, cd["county_fips"].nunique(), n_artifact, time.time() - t0)
    with open(os.path.join(tdir, "run_summary_%s.json" % wkey), "w") as f:
        json.dump(summ, f, indent=2)
    if verbose:
        log("   -> events=%d  heatwave-days(QA pooled)=%d  per-county median=%.0f  "
            "duration median/max=%.0f/%d  Jun-Sep=%.0f%%  (%.0fs)"
            % (summ["heatwave_events_QA_pooled"], summ["heatwave_days_QA_pooled"],
               summ["per_county_heatwave_days_median"], summ["event_duration_median_days"] or 0,
               summ["event_duration_max_days"], summ["pct_heatwave_days_jun_sep"] or 0,
               summ["runtime_seconds"]))
    return summ


def run_grid_state(state, runs=None, cd=None, write_daily=True, on_summary=None):
    """Classify every run in the grid for one state.

    Executed grouped by (metric, window) rather than in definition order: that is
    the unit a threshold set covers, so each threshold pass is computed once, used
    by every percentile and both durations that need it, and then dropped before
    the next one is built. 12 threshold passes serve all 56 runs, and only one
    threshold frame is ever resident in memory.
    """
    if cd is None:
        cd = load_county_days(state)
    if runs is None:
        runs = C.grid_runs()

    # group the runs by the threshold set they need
    groups = {}
    for r in runs:
        groups.setdefault((r["metric"], r["window_key"]), []).append(r)

    summaries, done, total = [], 0, len(runs)
    for gi, ((metric, wkey), grp) in enumerate(sorted(groups.items()), 1):
        pctls = sorted({r["percentile"] for r in grp})
        log("=" * 72)
        log("threshold group %d/%d: metric=%s window=%s -> %d run(s), percentiles=%s"
            % (gi, len(groups), metric, wkey, len(grp), pctls))
        log("=" * 72)
        cache = {}                                  # holds exactly this group's thresholds
        get_thresholds(state, metric, wkey, pctls, cd, cache=cache)
        for r in sorted(grp, key=lambda x: (x["percentile"], x["min_duration"])):
            done += 1
            log("[%d/%d]" % (done, total))
            s = run_one(state, r, cd, cache=cache, write_daily=write_daily)
            summaries.append(s)
            if on_summary is not None:
                on_summary(s)
        del cache
    return pd.DataFrame(summaries)


# ---------------------------------------------------------------- legacy path
def run_state_percentile(state, pctl, cd=None, cache=None, outdir=None, write_daily=True):
    """LEGACY entry point (run_all.py): Definition 01 / 02 = daily-MEAN heat index,
    config.MIN_DURATION days, windows w15 + month. A special case of the grid code,
    kept so the published outputs stay reproducible from one command."""
    if cd is None:
        cd = load_county_days(state)
    if cache is None:
        cache = {}
    metric = C.LEGACY_METRIC_KEY
    m = C.METRICS[metric]
    out = []
    for wkey in C.LEGACY_WINDOWS:
        w = C.GRID_WINDOWS[wkey]
        run = {"run_id": C.run_code(metric, pctl, C.MIN_DURATION, wkey),
               "definition_id": C.definition_id(pctl),      # legacy id names the output dir
               "def_number": 1 if pctl == 85 else 2, "user_item": "legacy",
               "metric": metric, "metric_code": m["code"], "metric_label": m["label"],
               "percentile": pctl, "min_duration": C.MIN_DURATION,
               "window_key": wkey, "window_label": w["label"], "window_order": w["order"],
               "artifact_handling": "rh_clip_2023_03_01_set_missing",
               "baseline": C.BASELINE_SCHEME, "season": C.SEASON,
               "absolute_floor": "none" if C.PRIMARY_FLOOR_F is None else str(C.PRIMARY_FLOOR_F),
               "comparison_op": C.COMPARISON_OP,
               "analysis_years": "%d-%d" % C.ANALYSIS_YEARS}
        out.append(run_one(state, run, cd, cache=cache,
                           outdir=outdir or C.definition_output_dir(state, pctl),
                           write_daily=write_daily))
    return pd.DataFrame(out)


if __name__ == "__main__":
    for st in C.STATES:
        for p in C.PERCENTILES:
            run_state_percentile(st, p)
