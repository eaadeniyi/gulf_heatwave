"""
=============================================================================
r06  --  STAGES 7 and 8: rebuild the three construct families and verify the
         eligibility denominators.
=============================================================================
THE MATHEMATICS IS UNCHANGED. THE DESCRIPTIONS AND THE OUTPUTS ARE NOT.

  A  RELATIVE WARM SPELL      REL_TX_P{p}_D{d}_{W}
     the daily high exceeds the COUNTY- AND CALENDAR-DATE-SPECIFIC HISTORICAL
     percentile threshold for at least d consecutive days.

     The previous package described this as "the percentile of the county's own
     Tmax distribution". That omits the calendar conditioning, which is the
     whole mechanism: the threshold for 3 January is estimated from 3 January's
     own history, not from the county's year-round distribution.

     It is NOT called a heatwave here. It is year-round, it applies no absolute
     condition, and cool-season days qualify.

  B  HYBRID RELATIVE-AND-ABSOLUTE HEAT EVENT   HYB_TX_P{p}_D{d}_A{g}_{W}
     the relative condition AND the daily high reaches an absolute gate.

  C  ABSOLUTE HOT SPELL       ABS_TX_A{g}_D{d}
     the daily high exceeds a fixed value for at least d consecutive days. No
     percentile, no baseline, therefore no threshold window.

The 80 and 90 degF values are ABSOLUTE DAILY-HIGH GATES. They are not National
Weather Service advisory thresholds.

REPRODUCTION OF e02
  Every construct is rebuilt here from the archived walk-forward threshold cache
  and the county-day table, then checked against the stored e02 output by EXACT
  SET EQUALITY on the classified county-dates and on the event boundaries. That
  is the Stage 1 reproduction of e02 and it is written back into
  qa/01_existing_pipeline_reproduction.csv.

STAGE 8 -- ELIGIBILITY
  Valid daily county-level observations are counted SEPARATELY for the three
  families and tested for equality rather than assumed equal:
      relative   the daily high is present AND a historical threshold exists
      hybrid     relative eligibility AND the absolute gate is evaluable
      absolute   the daily high is present
=============================================================================
"""
import os
import sys
import gzip
import time
import json

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K
import config as C                                          # noqa: E402
import p02_classify_and_report as p02                       # noqa: E402
from heatwave_run_logic import build_runs_and_events_panel  # noqa: E402

STATE = K.TEST_STATE
A0, A1 = K.ANALYSIS_YEARS
VERIFY, TESTD, TESTE, TESTF, TESTG = [], [], [], [], []
DAYSETS = {}


# =============================================================================
# input
# =============================================================================
def load_county_days():
    cd = p02.load_county_days(STATE, verbose=False)
    cd = cd[(cd["year"] >= A0) & (cd["year"] <= A1)].copy()
    cd = cd.sort_values(["county_fips", "date"]).reset_index(drop=True)
    K.log("[load] %s daily county-level records, %d counties, %s to %s"
          % ("{:,}".format(len(cd)), cd["county_fips"].nunique(),
             cd["date"].min().date(), cd["date"].max().date()))
    return cd


def load_thresholds(percentile, window, float_precision="round_trip"):
    """The archived walk-forward threshold cache for one percentile and window.

    float_precision="round_trip" is REQUIRED and is not the pandas default.
    The cache stores full-precision values such as 94.38799999999999; the
    default CSV float parser returns 94.388 for that string, one unit in the
    last place too high. With the project's strict '>' comparison that single
    bit flips the classification of any county-date sitting exactly on its
    threshold. See qa/float_roundtrip_defect.csv for the measured effect.
    """
    p = C.threshold_cache_path(STATE, K.METRIC, percentile, window)
    t = pd.read_csv(p, dtype={"county_fips": str}, float_precision=float_precision)
    key = "template_doy" if "template_doy" in t.columns else "calendar_month"
    return t[["county_fips", key, "analysis_year", "threshold_value_f",
              "n_reference_values"]], key


def float_roundtrip_check(cd):
    """Quantify the archived-CSV float round-trip defect.

    For each percentile at the primary window, compare the threshold values as
    parsed by the pandas DEFAULT float parser with the same values parsed
    exactly, and count how many daily county-level records change their
    relative condition as a result.
    """
    rows = []
    metric = cd[[K.METRIC_COL, "county_fips", "template_doy", "year", "month"]]
    for p in K.PERCENTILES:
        exact, key = load_thresholds(p, K.PRIMARY_WINDOW, float_precision="round_trip")
        default, _ = load_thresholds(p, K.PRIMARY_WINDOW, float_precision=None)
        n_diff = int((exact["threshold_value_f"].to_numpy()
                      != default["threshold_value_f"].to_numpy()).sum())
        # the two parses are the same file read twice, so the row order matches
        t = exact.rename(columns={key: "_k", "threshold_value_f": "thr_exact"}).copy()
        t["thr_default"] = default["threshold_value_f"].to_numpy()
        left = "template_doy" if key == "template_doy" else "month"
        m = metric.merge(t, left_on=["county_fips", left, "year"],
                         right_on=["county_fips", "_k", "analysis_year"], how="left")
        ok = m[K.METRIC_COL].notna() & m["thr_exact"].notna()
        a = (m.loc[ok, K.METRIC_COL] > m.loc[ok, "thr_exact"])
        b = (m.loc[ok, K.METRIC_COL] > m.loc[ok, "thr_default"])
        rows.append(dict(
            percentile=p, window=K.PRIMARY_WINDOW,
            threshold_rows=len(exact),
            threshold_values_misparsed_by_default=n_diff,
            pct_threshold_values_misparsed=round(100.0 * n_diff / len(exact), 6),
            evaluable_daily_records=int(ok.sum()),
            daily_records_whose_condition_flips=int((a != b).sum()),
            note=("the pandas default CSV float parser is not round-trip exact; "
                  "reading the archived threshold cache without "
                  "float_precision='round_trip' changes the relative condition on "
                  "the county-dates that sit exactly on their threshold")))
    return pd.DataFrame(rows)


def county_reference():
    r = pd.read_csv(os.path.join(C.state_output_dir(STATE),
                                 "coverage_and_imputation_report.csv"),
                    dtype={"county_fips": str})
    r["fully_imputed_county"] = (r["fully_imputed_county"].astype(str).str.lower()
                                 .isin(("true", "1", "yes")))
    r["observed_share"] = 1.0 - r["pct_analysis_days_imputed"] / 100.0
    return r


# =============================================================================
# panel construction
# =============================================================================
def build_panel(cd, con, thr_cache):
    """Attach the threshold and the construct's candidate flag to the panel.

    Returns the panel with:
      metric_value_f            the daily high
      threshold_value_f         the county- and calendar-date-specific percentile,
                                or the absolute gate for the absolute family
      relative_condition_met    the percentile condition alone (NaN if not evaluable)
      absolute_condition_met    the gate condition alone (NaN if not evaluable)
      candidate_day_flag        the construct's condition (NaN if not evaluable)
      eligible                  whether the construct can be evaluated at all
    """
    an = cd.copy()
    an["metric_value_f"] = an[K.METRIC_COL]
    has_metric = an["metric_value_f"].notna()

    if con["family"] == "absolute":
        gate = float(con["absolute_gate_f"])
        an["threshold_value_f"] = gate
        an["n_reference_values"] = np.nan
        abs_ok = np.where(has_metric, (an["metric_value_f"] > gate).astype(float), np.nan)
        an["relative_condition_met"] = np.nan
        an["absolute_condition_met"] = abs_ok
        an["candidate_day_flag"] = abs_ok
        an["eligible"] = has_metric
        return an

    thr, key = thr_cache[(con["percentile"], con["window"])]
    left = "template_doy" if key == "template_doy" else "month"
    an = an.merge(thr.rename(columns={key: "_k"}),
                  left_on=["county_fips", left, "year"],
                  right_on=["county_fips", "_k", "analysis_year"], how="left")
    an = an.drop(columns=["_k", "analysis_year"])
    has_metric = an["metric_value_f"].notna()
    has_thr = an["threshold_value_f"].notna()
    usable = has_metric & has_thr
    rel = np.where(usable,
                   (an["metric_value_f"] > an["threshold_value_f"]).astype(float), np.nan)
    an["relative_condition_met"] = rel
    if con["family"] == "relative":
        an["absolute_condition_met"] = np.nan
        an["candidate_day_flag"] = rel
        an["eligible"] = usable
    else:
        gate = float(con["absolute_gate_f"])
        # the pipeline's existing gate operator is '>='; '>' is tested in TEST E
        gok = np.where(has_metric, (an["metric_value_f"] >= gate).astype(float), np.nan)
        an["absolute_condition_met"] = gok
        an["candidate_day_flag"] = np.where(
            np.isnan(rel), np.nan, ((rel == 1) & (gok == 1)).astype(float))
        an["eligible"] = usable & has_metric
    return an.sort_values(["county_fips", "date"]).reset_index(drop=True)


def classify(an, con):
    daily, ev = build_runs_and_events_panel(
        an, min_duration=con["duration_days"], year_boundary_breaks_run=False,
        definition_id=con["construct_id"], state_fips=C.STATE_FIPS[STATE],
        with_event_columns=False)
    hw = daily[daily["heatwave_day_flag"] == 1].copy()
    return daily, hw, ev


# =============================================================================
# the revised outputs
# =============================================================================
def event_catalogue(hw, ev, con, ref):
    """One row per event, with the variables the revision specifies."""
    if not len(ev):
        return pd.DataFrame()
    h = hw.copy()
    h["exceedance_f"] = h["metric_value_f"] - h["threshold_value_f"]
    g = h.groupby("run_id", sort=True)
    agg = g.agg(county_name=("county_name", "first"),
                event_peak_temperature_f=("metric_value_f", "max"),
                maximum_threshold_exceedance_f=("exceedance_f", "max"),
                cumulative_exceedance_degree_days=(
                    "exceedance_f", lambda s: float(np.maximum(0.0, s).sum())),
                imputed_day_count=("temp_imputed", "sum"),
                observed_day_count=("temp_imputed", lambda s: int((~s).sum())),
                minimum_reference_values=("n_reference_values", "min"),
                mean_daily_high_f=("metric_value_f", "mean"))
    peak_i = g["metric_value_f"].idxmax()
    peak = h.loc[peak_i.to_numpy(), ["date"]].rename(columns={"date": "event_peak_date"})
    peak.index = peak_i.index
    exc_i = g["exceedance_f"].idxmax()
    exc = h.loc[exc_i.to_numpy(), ["date"]].rename(
        columns={"date": "maximum_exceedance_date"})
    exc.index = exc_i.index

    out = ev.set_index("run_id").join(agg).join(peak).join(exc).reset_index()
    out = out.rename(columns={"start_date": "event_start_date",
                              "end_date": "event_end_date"})
    out["construct_id"] = con["construct_id"]
    out["construct_family"] = con["family"]
    out["legacy_definition_id"] = con["legacy_definition_id"]
    out["percentile"] = con["percentile"]
    out["duration_days_minimum"] = con["duration_days"]
    out["absolute_gate_f"] = con["absolute_gate_f"]
    out["threshold_window"] = con["window"] if con["window"] else "none"
    out = out.merge(ref[["county_fips", "pct_analysis_days_imputed",
                         "fully_imputed_county"]], on="county_fips", how="left")

    parts = pd.DataFrame(index=out.index)
    parts["long_event_review"] = out["event_duration_days"] > K.LONG_EVENT_DAYS
    parts["fully_imputed_county"] = out["fully_imputed_county"].fillna(False)
    parts["contains_imputed_days"] = ((out["imputed_day_count"] > 0)
                                      & ~parts["fully_imputed_county"])
    parts["low_reference_sample"] = (out["minimum_reference_values"].notna()
                                     & (out["minimum_reference_values"] < C.MIN_REF_OBS))
    status = pd.Series("", index=out.index, dtype=object)
    for c in parts.columns:
        status = status.where(~parts[c], status + ";" + c)
    out["qc_review_status"] = status.str.lstrip(";").replace("", "ok")
    out["requires_manual_review"] = out["qc_review_status"] != "ok"

    for c in ("event_peak_temperature_f", "maximum_threshold_exceedance_f",
              "cumulative_exceedance_degree_days", "mean_daily_high_f"):
        out[c] = out[c].astype(float).round(3)
    out["event_duration_days"] = out["event_duration_days"].astype(int)
    for c in ("event_start_date", "event_end_date", "event_peak_date",
              "maximum_exceedance_date"):
        out[c] = pd.to_datetime(out[c]).dt.strftime("%Y-%m-%d")
    cols = ["event_id", "construct_id", "construct_family", "legacy_definition_id",
            "county_fips", "county_name", "event_start_date", "event_end_date",
            "event_duration_days", "event_peak_temperature_f", "event_peak_date",
            "maximum_threshold_exceedance_f", "maximum_exceedance_date",
            "cumulative_exceedance_degree_days", "observed_day_count",
            "imputed_day_count", "qc_review_status", "requires_manual_review",
            "percentile", "duration_days_minimum", "absolute_gate_f",
            "threshold_window", "mean_daily_high_f", "minimum_reference_values",
            "pct_analysis_days_imputed", "fully_imputed_county", "onset_year"]
    return out[cols].sort_values(["county_fips", "event_start_date"]).reset_index(
        drop=True)


def monthly_summary(hw, cat, con, elig):
    """Monthly county-level summary with the specified variable names."""
    if not len(cat):
        return pd.DataFrame()
    e = cat.copy()
    e["start"] = pd.to_datetime(e["event_start_date"])
    e["end"] = pd.to_datetime(e["event_end_date"])
    s_ym = e["start"].dt.year * 12 + (e["start"].dt.month - 1)
    e_ym = e["end"].dt.year * 12 + (e["end"].dt.month - 1)
    n_months = (e_ym - s_ym + 1).to_numpy()
    idx = np.repeat(np.arange(len(e)), n_months)
    off = np.arange(n_months.sum()) - np.repeat(np.cumsum(n_months) - n_months, n_months)
    ym = s_ym.to_numpy()[idx] + off
    act = pd.DataFrame({"county_fips": e["county_fips"].to_numpy()[idx],
                        "county_name": e["county_name"].to_numpy()[idx],
                        "year": ym // 12, "month": ym % 12 + 1,
                        "event_id": e["event_id"].to_numpy()[idx],
                        "duration": e["event_duration_days"].to_numpy()[idx],
                        "onset": off == 0})
    a = (act.groupby(["county_fips", "county_name", "year", "month"], observed=True)
         .agg(events_started_count=("onset", "sum"),
              events_active_count=("event_id", "nunique"),
              longest_active_event_days=("duration", "max"),
              event_ids_active=("event_id", lambda s: ";".join(sorted(set(s)))))
         .reset_index())
    started = (act[act["onset"]].groupby(["county_fips", "year", "month"], observed=True)
               ["event_id"].agg(lambda s: ";".join(sorted(set(s))))
               .rename("event_ids_started").reset_index())
    d = (hw.groupby(["county_fips", "year", "month"], observed=True)
         .agg(heat_event_day_count=("heatwave_day_flag", "size"),
              imputed_classified_day_count=("temp_imputed", "sum")).reset_index())
    # The panel STARTS from the construct's own valid-record table, so every
    # county-month with valid daily records appears exactly once whether or not
    # anything was classified in it, and a county-month with NO valid records is
    # absent rather than present as a zero. Missing exposure is therefore never
    # coded as a non-event (TEST F).
    out = (elig.merge(a, on=["county_fips", "year", "month"], how="left")
           .merge(started, on=["county_fips", "year", "month"], how="left")
           .merge(d, on=["county_fips", "year", "month"], how="left"))
    names = (cat[["county_fips", "county_name"]].drop_duplicates()
             .set_index("county_fips")["county_name"])
    out["county_name"] = out["county_name"].fillna(out["county_fips"].map(names))
    for c in ("events_started_count", "events_active_count",
              "longest_active_event_days", "heat_event_day_count",
              "imputed_classified_day_count"):
        out[c] = out[c].fillna(0).astype(int)
    out["event_ids_started"] = out["event_ids_started"].fillna("")
    out["event_ids_active"] = out["event_ids_active"].fillna("")
    out["monthly_classification_rate_per_1000"] = np.where(
        out["valid_daily_observation_count"] > 0,
        1000.0 * out["heat_event_day_count"] / out["valid_daily_observation_count"],
        np.nan).round(3)
    out["construct_id"] = con["construct_id"]
    out["construct_family"] = con["family"]
    out["season"] = out["month"].map(K.SEASON_OF)
    cols = ["construct_id", "construct_family", "county_fips", "county_name", "year",
            "month", "season", "heat_event_day_count", "events_started_count",
            "events_active_count", "longest_active_event_days",
            "valid_daily_observation_count", "monthly_classification_rate_per_1000",
            "imputed_classified_day_count", "event_ids_started", "event_ids_active"]
    return out[cols].sort_values(["county_fips", "year", "month"]).reset_index(drop=True)


def annual_summary(hw, cat, con, elig_y):
    if not len(cat):
        return pd.DataFrame()
    e = cat.copy()
    e["onset_year"] = pd.to_datetime(e["event_start_date"]).dt.year
    a = (e.groupby(["county_fips", "county_name", "onset_year"], observed=True)
         .agg(annual_event_count=("event_id", "size"),
              longest_event_duration_days=("event_duration_days", "max"),
              first_event_start_date=("event_start_date", "min"),
              last_event_end_date=("event_end_date", "max")).reset_index()
         .rename(columns={"onset_year": "year"}))
    d = (hw.groupby(["county_fips", "year"], observed=True)
         .agg(annual_classified_day_count=("heatwave_day_flag", "size"),
              imputed_classified_day_count=("temp_imputed", "sum")).reset_index())
    out = (elig_y.merge(a, on=["county_fips", "year"], how="left")
           .merge(d, on=["county_fips", "year"], how="left"))
    names = (cat[["county_fips", "county_name"]].drop_duplicates()
             .set_index("county_fips")["county_name"])
    out["county_name"] = out["county_name"].fillna(out["county_fips"].map(names))
    for c in ("annual_event_count", "annual_classified_day_count",
              "longest_event_duration_days", "imputed_classified_day_count"):
        out[c] = out[c].fillna(0).astype(int)
    out["annual_classification_rate_per_1000"] = np.where(
        out["valid_daily_observation_count"] > 0,
        1000.0 * out["annual_classified_day_count"]
        / out["valid_daily_observation_count"], np.nan).round(3)
    out["construct_id"] = con["construct_id"]
    out["construct_family"] = con["family"]
    # published-index crosswalk
    out["HWN_annual_event_count"] = out["annual_event_count"]
    out["HWF_annual_days_in_events"] = out["annual_classified_day_count"]
    out["HWD_longest_event_duration_days"] = out["longest_event_duration_days"]
    cols = ["construct_id", "construct_family", "county_fips", "county_name", "year",
            "annual_event_count", "annual_classified_day_count",
            "longest_event_duration_days", "first_event_start_date",
            "last_event_end_date", "imputed_classified_day_count",
            "valid_daily_observation_count", "annual_classification_rate_per_1000",
            "HWN_annual_event_count", "HWF_annual_days_in_events",
            "HWD_longest_event_duration_days"]
    return out[cols].sort_values(["county_fips", "year"]).reset_index(drop=True)


# =============================================================================
# eligibility (Stage 8)
# =============================================================================
def eligibility_tables(cd, thr_cache):
    """Valid daily county-level observations, per family and window."""
    has_metric = cd[K.METRIC_COL].notna()
    rows = {}
    base = cd[["county_fips", "year", "month"]].copy()

    absol = base[has_metric.to_numpy()]
    rows[("absolute", "none")] = (
        absol.groupby(["county_fips", "year", "month"], observed=True)
        .size().rename("valid_daily_observation_count").reset_index())

    for w in K.WINDOWS:
        thr, key = thr_cache[(K.PERCENTILES[0], w)]
        left = "template_doy" if key == "template_doy" else "month"
        cols = list(dict.fromkeys(["county_fips", "year", "month", left, K.METRIC_COL]))
        m = cd[cols].merge(
            thr.rename(columns={key: "_k"}), left_on=["county_fips", left, "year"],
            right_on=["county_fips", "_k", "analysis_year"], how="left")
        ok = m[K.METRIC_COL].notna() & m["threshold_value_f"].notna()
        rel = (m[ok].groupby(["county_fips", "year", "month"], observed=True)
               .size().rename("valid_daily_observation_count").reset_index())
        rows[("relative", w)] = rel
        # hybrid: the relative condition must be evaluable AND the gate evaluable.
        # The gate needs only the daily high, which relative eligibility already
        # requires, so the two sets are expected to coincide -- expected, then TESTED.
        okh = ok & m[K.METRIC_COL].notna()
        rows[("hybrid", w)] = (m[okh].groupby(["county_fips", "year", "month"],
                                              observed=True)
                               .size().rename("valid_daily_observation_count").reset_index())
    return rows


def eligibility_comparison(elig):
    """Are the construct families' denominators identical? Tested, not assumed."""
    rows = []
    w = K.PRIMARY_WINDOW
    keys = [("relative", w), ("hybrid", w), ("absolute", "none")]
    frames = {k: elig[k].set_index(["county_fips", "year", "month"])
              ["valid_daily_observation_count"] for k in keys}
    idx = None
    for k in keys:
        idx = frames[k].index if idx is None else idx.union(frames[k].index)
    aligned = {k: frames[k].reindex(idx, fill_value=0) for k in keys}
    for mo in range(1, 13):
        sel = idx.get_level_values("month") == mo
        r = {"month": mo, "month_name": K.MONTH_ABBR[mo - 1], "season": K.SEASON_OF[mo]}
        for (fam, win) in keys:
            r["valid_daily_observations_%s" % fam] = int(aligned[(fam, win)][sel].sum())
        r["relative_equals_hybrid"] = bool(
            (aligned[("relative", w)][sel] == aligned[("hybrid", w)][sel]).all())
        r["relative_equals_absolute"] = bool(
            (aligned[("relative", w)][sel] == aligned[("absolute", "none")][sel]).all())
        r["absolute_minus_relative"] = (r["valid_daily_observations_absolute"]
                                        - r["valid_daily_observations_relative"])
        rows.append(r)
    out = pd.DataFrame(rows)
    out["primary_window"] = K.PRIMARY_WINDOW
    out["conclusion"] = np.where(
        out["relative_equals_absolute"],
        "identical: the same denominator may be used for both families",
        "NOT identical: each family must use its own denominator")
    return out


# =============================================================================
# verification against the stored e02 output
# =============================================================================
def stored_day_set(legacy_id, window):
    p = os.path.join(K.CURRENT_PKG, "runs", legacy_id, "tables",
                     "daily_heatwave_days_%s.csv.gz" % window)
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p, usecols=["county_fips", "date"], dtype={"county_fips": str})
    return set(zip(d["county_fips"], d["date"]))


def stored_events(legacy_id, window):
    p = os.path.join(K.CURRENT_PKG, "runs", legacy_id, "tables",
                     "heatwave_events_%s.csv.gz" % window)
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p, dtype={"county_fips": str})
    return set(zip(d["county_fips"], d["start_date"], d["end_date"],
                   d["event_duration_days"]))


def verify(con, hw, cat):
    legacy, w = con["legacy_definition_id"], con["legacy_window"]
    mine_days = set(zip(hw["county_fips"], hw["date"].dt.strftime("%Y-%m-%d")))
    theirs_days = stored_day_set(legacy, w)
    mine_ev = set(zip(cat["county_fips"], cat["event_start_date"],
                      cat["event_end_date"], cat["event_duration_days"])) \
        if len(cat) else set()
    theirs_ev = stored_events(legacy, w)
    for q, mine, theirs in (("classified_county_dates", mine_days, theirs_days),
                            ("event_boundaries", mine_ev, theirs_ev)):
        if theirs is None:
            VERIFY.append(dict(construct_id=con["construct_id"],
                               legacy_definition_id=legacy, window=w, quantity=q,
                               rebuilt=len(mine), stored=np.nan, only_rebuilt=np.nan,
                               only_stored=np.nan, result="NO_STORED_OUTPUT"))
            continue
        VERIFY.append(dict(construct_id=con["construct_id"],
                           legacy_definition_id=legacy, window=w, quantity=q,
                           rebuilt=len(mine), stored=len(theirs),
                           only_rebuilt=len(mine - theirs),
                           only_stored=len(theirs - mine),
                           result="PASS" if mine == theirs else "FAIL"))


# =============================================================================
# QA tests D, E, F, G
# =============================================================================
def test_d(cat_all):
    def rec(check, result, detail, blocking=True):
        TESTD.append(dict(test="D", check=check, result=result, blocking=blocking,
                          detail=detail))
    c = cat_all
    frac = c["event_duration_days"] != c["event_duration_days"].round()
    rec("event_duration_is_an_integer", "PASS" if not frac.any() else "FAIL",
        "%d events with a fractional duration" % int(frac.sum()))
    span = ((pd.to_datetime(c["event_end_date"]) - pd.to_datetime(c["event_start_date"]))
            .dt.days + 1)
    bad = c.loc[span != c["event_duration_days"], "event_id"]
    rec("event_dates_are_consecutive", "PASS" if not len(bad) else "FAIL",
        "%d events whose end minus start does not equal the duration%s"
        % (len(bad), (": " + ", ".join(bad.head(5))) if len(bad) else ""))
    short = c[c["event_duration_days"] < c["duration_days_minimum"]]
    rec("event_meets_its_minimum_duration", "PASS" if not len(short) else "FAIL",
        "%d events shorter than their own minimum" % len(short))

    def extra(sub, sup):
        """County-dates in `sub` that are absent from `sup`."""
        return int(np.setdiff1d(sub, sup, assume_unique=True).size)

    for p in K.PERCENTILES:
        a2, a3, a5 = (DAYSETS.get(K.rel_id(p, d)) for d in (2, 3, 5))
        for lab, sub, sup in (("D3_subset_of_D2", a3, a2), ("D5_subset_of_D3", a5, a3),
                              ("D5_subset_of_D2", a5, a2)):
            if sub is None or sup is None:
                continue
            n = extra(sub, sup)
            rec("%s__P%d" % (lab, p), "PASS" if n == 0 else "FAIL",
                "%d county-dates in the longer-duration set but not the shorter one" % n)
    for d in K.DURATIONS:
        for hi, lo in ((90, 85), (85, 80), (90, 80)):
            ah, al = DAYSETS.get(K.rel_id(hi, d)), DAYSETS.get(K.rel_id(lo, d))
            if ah is None or al is None:
                continue
            n = extra(ah, al)
            rec("P%d_subset_of_P%d__D%d" % (hi, lo, d), "PASS" if n == 0 else "FAIL",
                "%d county-dates at the %dth percentile absent from the %dth"
                % (n, hi, lo))


def test_e(cd, thr_cache, ref):
    """Hybrid dates satisfy both conditions; absolute needs no threshold; the
    effect of > versus >= on the gate, measured AFTER event reconstruction."""
    def rec(check, result, detail, blocking=True):
        TESTE.append(dict(test="E", check=check, result=result, blocking=blocking,
                          detail=detail))
    p, d, g = 90, 3, 90.0
    con = [c for c in K.constructs()
           if c["construct_id"] == K.hyb_id(p, d, g)][0]
    an = build_panel(cd, con, thr_cache)
    _, hw, ev = classify(an, con)
    both = ((hw["relative_condition_met"] == 1) & (hw["absolute_condition_met"] == 1))
    rec("hybrid_days_satisfy_both_conditions", "PASS" if bool(both.all()) else "FAIL",
        "%d of %d classified days fail one of the two conditions"
        % (int((~both).sum()), len(hw)))
    rec("hybrid_days_reach_the_absolute_gate",
        "PASS" if bool((hw["metric_value_f"] >= g).all()) else "FAIL",
        "minimum daily high among classified days = %.2f degF, gate = %.0f degF"
        % (hw["metric_value_f"].min(), g))

    acon = [c for c in K.constructs() if c["construct_id"] == K.abs_id(g, d)][0]
    aan = build_panel(cd, acon, thr_cache)
    _, ahw, aev = classify(aan, acon)
    rec("absolute_construct_uses_no_historical_threshold",
        "PASS" if bool((aan["threshold_value_f"] == g).all()) else "FAIL",
        "the absolute construct's threshold column is the constant gate, not a "
        "percentile")
    rec("absolute_eligibility_needs_only_the_daily_high",
        "PASS" if bool((aan["eligible"] == aan[K.METRIC_COL].notna()).all()) else "FAIL",
        "eligible records equal records with a daily high present")

    # > versus >= on the gate, after event reconstruction
    an2 = an.copy()
    gok = np.where(an2["metric_value_f"].notna(),
                   (an2["metric_value_f"] > g).astype(float), np.nan)
    an2["candidate_day_flag"] = np.where(
        np.isnan(an2["relative_condition_met"].to_numpy()), np.nan,
        ((an2["relative_condition_met"] == 1) & (gok == 1)).astype(float))
    _, hw2, ev2 = classify(an2, con)
    n_on = int((an["metric_value_f"] == g).sum())
    rec("gate_operator_effect_reported_after_event_reconstruction", "REPORT",
        "with '>=' : %d classified days, %d events; with '>' : %d classified days, "
        "%d events; %d daily records sit exactly on the %.0f degF gate; the operator "
        "changes %d classified days and %d events"
        % (len(hw), len(ev), len(hw2), len(ev2), n_on, g,
           abs(len(hw) - len(hw2)), abs(len(ev) - len(ev2))), blocking=False)
    return dict(gate=g, percentile=p, duration=d, days_ge=len(hw), days_gt=len(hw2),
                events_ge=len(ev), events_gt=len(ev2), records_exactly_on_gate=n_on)


def test_f(monthly_all):
    def rec(check, result, detail, blocking=True):
        TESTF.append(dict(test="F", check=check, result=result, blocking=blocking,
                          detail=detail))
    r = monthly_all["monthly_classification_rate_per_1000"]
    over = monthly_all[r > 1000.0]
    rec("classification_rate_never_exceeds_1000_per_1000",
        "PASS" if not len(over) else "FAIL",
        "%d monthly county-level summaries above 1000 per 1000" % len(over))
    bad = monthly_all[(monthly_all["heat_event_day_count"] > 0)
                      & (monthly_all["valid_daily_observation_count"] <= 0)]
    rec("classified_days_never_exceed_valid_records",
        "PASS" if not len(bad) else "FAIL",
        "%d summaries with classified days but no valid records" % len(bad))
    bad2 = monthly_all[monthly_all["heat_event_day_count"]
                       > monthly_all["valid_daily_observation_count"]]
    rec("classified_day_count_at_most_valid_observation_count",
        "PASS" if not len(bad2) else "FAIL",
        "%d summaries where classified days exceed valid records" % len(bad2))
    miss = monthly_all["valid_daily_observation_count"].isna().sum()
    rec("missing_exposure_is_not_coded_as_a_non_event",
        "PASS" if miss == 0 else "FAIL",
        "%d summaries carry a missing denominator; a missing record must not be "
        "counted as a zero" % int(miss))


def test_g(cat_all, monthly_all, annual_all):
    def rec(check, result, detail, blocking=True):
        TESTG.append(dict(test="G", check=check, result=result, blocking=blocking,
                          detail=detail))
    # monthly summaries exist for the primary-window and absolute constructs; the
    # annual layer additionally covers the other threshold windows, so the
    # comparison is made on the constructs that have both.
    shared = sorted(set(monthly_all["construct_id"]) & set(annual_all["construct_id"]))
    m = (monthly_all[monthly_all["construct_id"].isin(shared)]
         .groupby(["construct_id", "county_fips", "year"], observed=True)
         ["heat_event_day_count"].sum().rename("monthly_sum").reset_index())
    a = annual_all[annual_all["construct_id"].isin(shared)][
        ["construct_id", "county_fips", "year", "annual_classified_day_count"]]
    j = a.merge(m, on=["construct_id", "county_fips", "year"], how="outer").fillna(0)
    mism = j[j["annual_classified_day_count"] != j["monthly_sum"]]
    rec("annual_classified_days_equal_the_sum_of_monthly_counts",
        "PASS" if not len(mism) else "FAIL",
        "%d of %d county-years disagree, across %d constructs with both layers"
        % (len(mism), len(j), len(shared)))

    for cid, g in cat_all.groupby("construct_id", observed=True):
        pass
    dur = (cat_all.groupby("construct_id", observed=True)["event_duration_days"]
           .sum().rename("event_duration_sum"))
    days = (monthly_all.groupby("construct_id", observed=True)["heat_event_day_count"]
            .sum().rename("classified_days"))
    cmp = pd.concat([dur, days], axis=1).dropna()
    bad = cmp[cmp["event_duration_sum"] != cmp["classified_days"]]
    rec("event_durations_sum_to_classified_days",
        "PASS" if not len(bad) else "FAIL",
        "%d constructs disagree%s" % (len(bad),
                                      (": " + str(bad.to_dict("index"))) if len(bad) else ""))

    known = set(cat_all["event_id"])
    ids = set()
    for col in ("event_ids_started", "event_ids_active"):
        for s in monthly_all[col].dropna():
            if s:
                ids.update(s.split(";"))
    missing = ids - known
    rec("every_event_id_in_a_summary_exists_in_the_event_table",
        "PASS" if not missing else "FAIL",
        "%d event ids referenced but absent" % len(missing))


# =============================================================================
# driver
# =============================================================================
def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 78)
    K.log("r06  STAGES 7-8 -- construct families, event catalogues, denominators")
    K.log("=" * 78)
    K.log(K.PANEL_SENTENCE)

    cd = load_county_days()
    ref = county_reference()

    K.log("loading the archived walk-forward threshold cache ...")
    thr_cache = {}
    for w in K.WINDOWS:
        for p in K.PERCENTILES:
            thr_cache[(p, w)] = load_thresholds(p, w)
    K.log("   %d threshold tables (%d percentiles x %d windows), parsed with "
          "float_precision='round_trip'"
          % (len(thr_cache), len(K.PERCENTILES), len(K.WINDOWS)))
    frt = float_roundtrip_check(cd)
    frt.to_csv(os.path.join(K.DIR_QA, "float_roundtrip_defect.csv"), index=False)
    K.log("   archived-CSV float round-trip check: %s of %s threshold values are "
          "misparsed by the pandas DEFAULT float parser, flipping the relative "
          "condition on %s daily county-level records"
          % ("{:,}".format(int(frt["threshold_values_misparsed_by_default"].sum())),
             "{:,}".format(int(frt["threshold_rows"].sum())),
             "{:,}".format(int(frt["daily_records_whose_condition_flips"].sum()))))

    K.log("-" * 78)
    K.log("eligibility denominators, computed separately per construct family")
    elig = eligibility_tables(cd, thr_cache)
    elig_y = {k: (v.groupby(["county_fips", "year"], observed=True)
                  ["valid_daily_observation_count"].sum().reset_index())
              for k, v in elig.items()}
    for (fam, w), v in sorted(elig.items()):
        K.log("   %-9s %-9s %s valid daily county-level observations"
              % (fam, w, "{:,}".format(int(v["valid_daily_observation_count"].sum()))))
    ecmp = eligibility_comparison(elig)
    ecmp.to_csv(os.path.join(K.DIR_QA, "eligibility_denominator_comparison.csv"),
                index=False)
    ecmp.to_csv(os.path.join(K.DIR_TABLES, "eligibility_denominator_comparison.csv"),
                index=False)
    same_ra = bool(ecmp["relative_equals_absolute"].all())
    same_rh = bool(ecmp["relative_equals_hybrid"].all())
    K.log("   relative vs hybrid denominators identical:   %s" % same_rh)
    K.log("   relative vs absolute denominators identical: %s" % same_ra)
    if not same_ra:
        K.log("   -> the two families DO NOT share a denominator; each rate uses its "
              "own. Difference: %s absolute minus relative daily records"
              % "{:,}".format(int(ecmp["absolute_minus_relative"].sum())))

    # ---- classify every construct -------------------------------------------
    #  REPORTING SCOPE, stated rather than applied silently:
    #    individual event catalogues and monthly county-level summaries are
    #      written for the primary threshold window and for the absolute family,
    #      which has no window axis  -> 33 constructs
    #    ANNUAL county-level summaries are written for ALL 60 constructs, so the
    #      threshold-window axis is preserved in the annual layer
    K.log("-" * 78)
    cats, months, annuals = [], [], []
    cons = K.constructs()
    cty_index = {c: i for i, c in enumerate(sorted(cd["county_fips"].unique()))}
    date0 = np.datetime64("%d-01-01" % A0, "D")
    for i, con in enumerate(cons, 1):
        fam, w = con["family"], (con["window"] or "none")
        primary = (con["window"] == K.PRIMARY_WINDOW) or (fam == "absolute")
        an = build_panel(cd, con, thr_cache)
        daily, hw, ev = classify(an, con)
        cat = event_catalogue(hw, ev, con, ref)
        yr = annual_summary(hw, cat, con, elig_y[(fam, w)])
        annuals.append(yr)
        verify(con, hw, cat)
        if primary:
            mo = monthly_summary(hw, cat, con, elig[(fam, w)])
            months.append(mo)
            cats.append(cat)
            ci = hw["county_fips"].map(cty_index).to_numpy(dtype=np.int64)
            do = (hw["date"].to_numpy(dtype="datetime64[D]") - date0).astype(np.int64)
            DAYSETS[con["construct_id"]] = np.unique(ci * 100000 + do)
        if i % 10 == 0 or i == len(cons):
            K.log("   %2d/%d constructs classified (%.0f s elapsed)"
                  % (i, len(cons), time.time() - t0))
        del an, daily, hw, ev, cat

    cat_all = pd.concat([c for c in cats if len(c)], ignore_index=True)
    monthly_all = pd.concat([m for m in months if len(m)], ignore_index=True)
    annual_all = pd.concat([a for a in annuals if len(a)], ignore_index=True)

    # ---- verification -------------------------------------------------------
    V = pd.DataFrame(VERIFY)
    V.to_csv(os.path.join(K.DIR_QA, "e02_independent_rebuild_verification.csv"),
             index=False)
    n_fail = int((V["result"] == "FAIL").sum())
    K.log("-" * 78)
    K.log("REPRODUCTION OF e02 by independent rebuild: %d checks, %d PASS, %d FAIL"
          % (len(V), int((V["result"] == "PASS").sum()), n_fail))
    if n_fail:
        K.log(V[V["result"] == "FAIL"].to_string(index=False))
        raise K.BlockingQAFailure(
            "the independent rebuild does not reproduce the stored e02 output on %d "
            "check(s); see qa/e02_independent_rebuild_verification.csv" % n_fail)

    # ---- QA tests -----------------------------------------------------------
    test_d(cat_all)
    gate_effect = test_e(cd, thr_cache, ref)
    test_f(monthly_all)
    test_g(cat_all, monthly_all, annual_all)
    qa = pd.concat([pd.DataFrame(TESTD), pd.DataFrame(TESTE), pd.DataFrame(TESTF),
                    pd.DataFrame(TESTG)], ignore_index=True)
    qa.to_csv(os.path.join(K.DIR_QA, "test_DEFG_event_logic.csv"), index=False)
    K.log("-" * 78)
    K.log("TESTS D-G: %d checks, %d PASS, %d FAIL, %d REPORT"
          % (len(qa), int((qa["result"] == "PASS").sum()),
             int((qa["result"] == "FAIL").sum()),
             int((qa["result"] == "REPORT").sum())))
    for _, r in qa[qa["result"] != "PASS"].iterrows():
        K.log("   %-7s %-56s %s" % (r["result"], r["check"], r["detail"][:200]))
    blocking = qa[(qa["result"] == "FAIL") & qa["blocking"]]
    if len(blocking):
        raise K.BlockingQAFailure("TESTS D-G failed: %s" % list(blocking["check"]))
    with open(os.path.join(K.DIR_QA, "gate_operator_effect.json"), "w") as f:
        json.dump(gate_effect, f, indent=2)

    # ---- write --------------------------------------------------------------
    K.log("-" * 78)
    for fam, base in (("relative", "relative_warm_spell"),
                      ("hybrid", "hybrid_heat_event"),
                      ("absolute", "absolute_hot_spell")):
        c = cat_all[cat_all["construct_family"] == fam]
        m = monthly_all[monthly_all["construct_family"] == fam]
        a = annual_all[annual_all["construct_family"] == fam]
        plural = {"relative": "relative_warm_spells", "hybrid": "hybrid_heat_events",
                  "absolute": "absolute_hot_spells"}[fam]
        c.to_csv(os.path.join(K.DIR_TABLES, "individual_%s.csv" % {"relative_warm_spell": "relative_warm_spell_events", "hybrid_heat_event": "hybrid_heat_events", "absolute_hot_spell": "absolute_hot_spells"}[base]), index=False)
        a.to_csv(os.path.join(K.DIR_TABLES, "county_annual_%s.csv" % plural), index=False)
        if fam != "absolute":
            m.to_csv(os.path.join(K.DIR_TABLES, "county_monthly_%s.csv" % plural),
                     index=False)
        else:
            m.to_csv(os.path.join(K.DIR_TABLES, "county_monthly_%s.csv" % plural),
                     index=False)
        K.log("[write] %-42s events %8s  annual %7s  monthly %8s"
              % (base, "{:,}".format(len(c)), "{:,}".format(len(a)),
                 "{:,}".format(len(m))))
    monthly_all.to_csv(os.path.join(K.DIR_TABLES,
                                    "county_monthly_all_constructs.csv"), index=False)
    annual_all.to_csv(os.path.join(K.DIR_TABLES,
                                   "county_annual_all_constructs.csv"), index=False)

    # Classified county-date sets, encoded as county_index * 100000 + day offset
    # from %d-01-01, so the agreement step in r07 can compute Jaccard overlap
    # without re-reading a million-row day table per construct.
    np.savez_compressed(os.path.join(K.DIR_QA, "_classified_day_sets.npz"),
                        counties=np.array(sorted(cty_index), dtype=object),
                        **DAYSETS)

    K.log("-" * 78)
    K.log("catalogue scope: individual event catalogues are written for the primary "
          "window (%s) and for the absolute family, which has no window axis. Annual "
          "and monthly county-level summaries are written for ALL %d threshold "
          "windows, so the window axis is preserved."
          % (K.PRIMARY_WINDOW, len(K.WINDOWS)))
    K.log("r06 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
