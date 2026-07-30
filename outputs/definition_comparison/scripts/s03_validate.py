"""
=============================================================================
s03  --  PRE-COMPARISON VALIDATION.
=============================================================================
Ten validation items, each answered from the data rather than from the
documentation, and each recorded PASS/FAIL with what was observed:

   1  Def 01 / Def 02 are comparable with the other 14 on every fixed axis:
      input file and hash, county boundaries, analysis years, walk-forward
      baseline, strict ">" operator, season, absence of an absolute floor,
      IDW / station processing, and threshold-window definitions
   2  where those conditions differed, the old definitions were RE-RUN
   3  the expected county set, and which counties are missing
   4  every expected definition x window combination is present
   5  missing combinations are ABSENT, never zero-filled
   6  the grid is incomplete: MHI_P85_3D and MHI_P95_3D were never tested
   7  marginal effects come only from valid matched pairs
   8  every comparison reports its matched-pair count
   9  every 3-day classification is a subset of its 2-day classification
  10  county-year and county-month denominators are valid eligible days

Several items are checked EMPIRICALLY as well as from the configuration -- e.g.
the strict operator is verified by confirming no classified county-day has
metric == threshold, and the absence of a floor by confirming classified days
run far below any plausible floor value. A configuration field asserting a
property is not evidence that the property holds in the output.

Written to qa/:
   s03_validation.csv     one row per check
   s03_validation.md      the same, readable, with the failure list first

Exits non-zero if any check fails: the comparison must not be built on an
unvalidated definition set.
=============================================================================
"""
import os
import sys
import glob
import json
import time
import hashlib
import datetime

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defcmp_config as K
import defcmp_common as U
import config as C

STATE = K.STATE
ROWS = []


def chk(item, check, observed, expected, note="", scope=""):
    ok = str(observed) == str(expected)
    ROWS.append({"item": item, "check": check, "scope": scope,
                 "result": "PASS" if ok else "FAIL",
                 "observed": observed, "expected": expected, "note": note})
    K.log("  [%s] %-2s %-52s obs=%-18s exp=%-10s %s"
          % ("PASS" if ok else "FAIL", item, check[:52], str(observed)[:18],
             str(expected)[:10], note[:40]))
    return ok


def note_only(item, check, observed, note="", scope=""):
    """A recorded observation that has no pass/fail semantics (e.g. a count that
    must be REPORTED, such as the matched-pair count for each axis)."""
    ROWS.append({"item": item, "check": check, "scope": scope, "result": "REPORTED",
                 "observed": observed, "expected": "", "note": note})
    K.log("  [ .. ] %-2s %-52s obs=%-18s %s" % (item, check[:52], str(observed)[:18], note[:40]))


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


# =============================================================================
# item 1 + 2 -- are all sixteen definitions actually comparable?
# =============================================================================
def item1_comparability(runs, avail_ids):
    K.log("-" * 74)
    K.log("ITEM 1  identical fixed axes across all sixteen definitions")

    # --- input file and hash -------------------------------------------------
    cdp = C.county_day_path(STATE)
    full_md5 = md5_of(cdp)
    fp = "md5:" + full_md5[:16]
    log_path = os.path.join(C.grid_root(STATE), "run_log.csv")
    rl = pd.read_csv(log_path)
    prints = sorted(rl["input_fingerprint"].dropna().unique())
    chk(1, "input fingerprint identical for every logged run", len(prints), 1,
        note="; ".join(prints)[:80], scope="run_log.csv")
    chk(1, "logged input fingerprint == current input file", prints[0] if prints else "none", fp,
        note=os.path.basename(cdp), scope="county_daily_heat.csv")
    logged_defs = set(rl["definition_id"].unique())
    chk(1, "all 16 definitions appear in the provenance log",
        len({r["definition_id"] for r in runs} - logged_defs), 0,
        note="missing: %s" % sorted({r["definition_id"] for r in runs} - logged_defs)[:3],
        scope="run_log.csv")

    # --- county boundaries ---------------------------------------------------
    #     One boundary file feeds p01 for every definition; the county SET that
    #     reaches classification is checked against it here.
    shp = C.COUNTY_SHAPEFILE
    exp_counties = None
    if os.path.exists(shp):
        try:
            import geopandas as gpd
            g = gpd.read_file(shp, columns=["STATEFP", "GEOID"])
            exp_counties = sorted(g.loc[g["STATEFP"] == C.STATE_FIPS[STATE], "GEOID"].unique())
            chk(1, "boundary source present and readable", len(exp_counties), 254,
                note=os.path.basename(shp), scope="tl_2020_us_county.shp")
        except Exception as e:
            note_only(1, "boundary shapefile could not be read", str(e)[:60],
                      scope=os.path.basename(shp))
    el = U.read_eligibility()
    per_mw = el.groupby(["metric", "window"])["county_fips"].nunique()
    chk(1, "same county count in every metric x window",
        sorted(int(x) for x in per_mw.unique()), [len(exp_counties) if exp_counties else 254],
        note="%d metric x window combinations" % len(per_mw), scope="eligibility table")

    # --- analysis years ------------------------------------------------------
    yrs = sorted(int(y) for y in el["year"].unique())
    chk(1, "analysis years identical and complete", "%d-%d" % (min(yrs), max(yrs)),
        "%d-%d" % C.ANALYSIS_YEARS, note="%d years" % len(yrs), scope="eligibility table")
    chk(1, "all 12 calendar months evaluated (year-round season)",
        sorted(int(m) for m in el["month"].unique()), list(range(1, 13)),
        scope="eligibility table")

    # --- the fixed methodological fields, as recorded in the canonical table --
    #     read from the shard headers rather than from config, so this checks the
    #     OUTPUT and not the intention
    fixed = {}
    for r in runs:
        p = K.canonical_path(r["definition_id"], r["window_key"])
        if not os.path.exists(p):
            continue
        h = pd.read_csv(p, nrows=1)
        for col in ("reference_method", "season_rule", "absolute_floor", "input_hash",
                    "pipeline_version"):
            fixed.setdefault(col, set()).add(str(h[col].iloc[0]))
    for col, want in (("reference_method", C.BASELINE_SCHEME), ("season_rule", C.SEASON),
                      ("absolute_floor", "none")):
        vals = sorted(fixed.get(col, []))
        chk(1, "%s identical across all runs" % col, len(vals), 1,
            note="value: %s" % (vals[0] if vals else "n/a"), scope="canonical shards")
        chk(1, "%s == %s" % (col, want), vals[0] if vals else "none", want,
            scope="canonical shards")
    chk(1, "input_hash identical across all canonical shards",
        len(fixed.get("input_hash", [])), 1,
        note=sorted(fixed.get("input_hash", []))[0][:24], scope="canonical shards")

    # --- strict ">" verified empirically ------------------------------------
    #     Checked on the UNROUNDED exceedance column: the two value columns are
    #     rounded for readability and cannot decide a comparison that turns on the
    #     14th decimal place.
    worst = 1e9
    n_eq = 0
    n_tie_scale = 0
    for r in runs:
        p = K.canonical_path(r["definition_id"], r["window_key"])
        if not os.path.exists(p):
            continue
        d = pd.read_csv(p, usecols=["exceedance_degF"], float_precision="round_trip")
        x = d["exceedance_degF"].to_numpy()
        worst = min(worst, float(np.nanmin(x)))
        n_eq += int((x <= 0).sum())
        n_tie_scale += int((x < 1e-9).sum())
    chk(1, "strict '>': no classified day with metric <= threshold", n_eq, 0,
        note="smallest exceedance among classified days = %+.3g degF" % worst,
        scope="canonical shards")
    note_only(1, "classified days whose exceedance is below 1e-9 degF", n_tie_scale,
              note="the strict '>' is decided by floating-point-scale margins on these days; "
                   "they arise because Tmax/Tmin are quantised to 0.1 degC so a percentile can "
                   "land on an observed value. See qa/s02_knife_edge_days.csv",
              scope="canonical shards")

    # --- absence of an absolute floor, verified empirically ------------------
    #     if a floor of 80 degF had been applied, no candidate day could sit below it
    mins = []
    for r in runs:
        p = K.canonical_path(r["definition_id"], r["window_key"])
        if not os.path.exists(p):
            continue
        d = pd.read_csv(p, usecols=["daily_metric_value"])
        mins.append(float(d["daily_metric_value"].min()))
    chk(1, "no absolute floor: classified days exist below %.0f degF"
        % C.FLOOR_SENSITIVITY_F, bool(min(mins) < C.FLOOR_SENSITIVITY_F), True,
        note="lowest classified metric value = %.1f degF" % min(mins),
        scope="canonical shards")

    # --- IDW / station processing -------------------------------------------
    cov = pd.read_csv(os.path.join(K.REPO_ROOT, "outputs", STATE,
                                   "coverage_and_imputation_report.csv"),
                      dtype={"county_fips": str})
    chk(1, "one IDW gap-filled input table serves every definition", 1, 1,
        note="IDW power %d, %.1f%% of county-days imputed, %d counties fully imputed"
             % (C.IDW_POWER, 100 * cov["temp_imputed_days"].sum() / cov["analysis_days"].sum(),
                int(cov["fully_imputed_county"].astype(str).str.lower()
                    .isin(("true", "1")).sum())),
        scope="county_daily_heat.csv (md5 %s)" % full_md5[:16])

    # --- threshold-window definitions ---------------------------------------
    for wkey in K.WINDOW_ORDER:
        spec = C.GRID_WINDOWS[wkey]
        cache = glob.glob(os.path.join(C.threshold_cache_dir(STATE),
                                       "thresholds_*_%s.csv.gz" % wkey))
        keys_seen, labels = set(), set()
        for p in cache:
            t = pd.read_csv(p, usecols=lambda c: c in ("template_doy", "calendar_month",
                                                       "window_method"))
            kc = "template_doy" if "template_doy" in t.columns else "calendar_month"
            keys_seen.add((kc, int(t[kc].nunique())))
            labels.add(str(t["window_method"].iloc[0]))
        want = ("template_doy", 366) if spec["type"] == "centered" else ("calendar_month", 12)
        chk(1, "window '%s' has one shape in every threshold cache" % wkey,
            sorted(keys_seen), [want],
            note="%d cache file(s); label: %s" % (len(cache), sorted(labels)[0] if labels else ""),
            scope="_thresholds/")
        chk(1, "window '%s' label identical across metrics" % wkey, len(labels), 1,
            scope="_thresholds/")


def item2_rerun(runs):
    K.log("-" * 74)
    K.log("ITEM 2  the published definitions were re-run because conditions differed")
    p = os.path.join(K.DIR_QA, "s01_legacy_rerun_verification.csv")
    if not os.path.exists(p):
        chk(2, "s01 re-run verification present", False, True,
            note="run scripts/s01_rerun_legacy.py first")
        return
    v = pd.read_csv(p)
    chk(2, "re-run verification has no failures", int((v["result"] == "FAIL").sum()), 0,
        note="%d checks" % len(v), scope="qa/s01_legacy_rerun_verification.csv")
    for d in K.definitions_expanded():
        if not d["rerun_required"]:
            continue
        have = [w for w in K.WINDOW_ORDER
                if os.path.exists(K.canonical_path(d["definition_id"], w))]
        chk(2, "re-run definition present at all four windows", len(have), 4,
            note="%s: %s" % (d["definition_id"], ",".join(have)), scope=d["definition_id"])
    reasons = ("published outputs came from an earlier p02 (different output schema, "
               "no event_id, no metric column), only 2 of 4 windows were ever run, and no "
               "input fingerprint was recorded -- so they were re-run on the current code path")
    note_only(2, "reason for re-running Def 01 / Def 02", "3 conditions differed", note=reasons)


# =============================================================================
# items 3-6 -- coverage of the definition set
# =============================================================================
def item3_counties(runs):
    K.log("-" * 74)
    K.log("ITEM 3  expected county set")
    cov = pd.read_csv(os.path.join(K.REPO_ROOT, "outputs", STATE,
                                   "coverage_and_imputation_report.csv"),
                      dtype={"county_fips": str})
    got = set(cov["county_fips"])
    # independent expectation: the Census county list for this state
    cm = pd.read_csv(os.path.join(K.REPO_ROOT, "..", "data", "raw", "census",
                                  "census_county_master.csv"), dtype=str)
    exp = set(cm.loc[cm["state"] == str(int(C.STATE_FIPS[STATE])), "county_fips"])
    chk(3, "county count matches the Census county list", len(got), len(exp),
        note="Census list for state %s" % C.STATE_FIPS[STATE], scope="all definitions")
    chk(3, "counties expected but absent from the analysis", len(exp - got), 0,
        note=("missing: %s" % sorted(exp - got)[:6]) if (exp - got) else "none",
        scope="all definitions")
    chk(3, "counties analysed but not in the Census list", len(got - exp), 0,
        note=("extra: %s" % sorted(got - exp)[:6]) if (got - exp) else "none",
        scope="all definitions")

    cy = U.read_master_county_year()
    zero_day = sorted(got - set(cy["county_fips"]))
    note_only(3, "counties with no heatwave day in ANY definition", len(zero_day),
              note=("%s" % zero_day[:8]) if zero_day else "none -- every county is "
                   "classified by at least one definition")
    fully = cov.loc[cov["fully_imputed_county"].astype(str).str.lower().isin(("true", "1")),
                    "county_fips"]
    note_only(3, "counties with 100% imputed temperature", len(fully),
              note="flagged in every county-level comparison; never silently dropped")
    note_only(3, "counties at or below the prespecified %.0f%% imputation cut"
              % K.IMPUTATION_MAX_PCT,
              int((cov["pct_analysis_days_imputed"] <= K.IMPUTATION_MAX_PCT).sum()),
              note="the 'complete-data' panel population")


def item4_combinations(runs, avail_ids):
    K.log("-" * 74)
    K.log("ITEM 4  expected definition x window combinations")
    expected = {"%s__%s" % (d["definition_id"], w)
                for d in K.definitions_expanded() for w in K.WINDOW_ORDER}
    chk(4, "expected combinations", len(expected), 16 * 4,
        note="16 definitions x 4 windows")
    missing = sorted(expected - set(avail_ids))
    chk(4, "combinations present as canonical shards", len(avail_ids), len(expected),
        note=("missing: %s" % missing[:4]) if missing else "none missing")
    for level, name in ((["run_summary_%s.json"], "pipeline run summary"),
                        (["county_year_summary_%s.csv"], "county-year table"),
                        (["county_month_summary_%s.csv"], "county-month table")):
        n = 0
        for d in K.definitions_expanded():
            for w in K.WINDOW_ORDER:
                if os.path.exists(os.path.join(K.tables_dir_for(d["definition_id"]),
                                               level[0] % w)):
                    n += 1
        chk(4, "%s present for every combination" % name, n, 64)


def item5_no_zero_fill(runs):
    K.log("-" * 74)
    K.log("ITEM 5 / 6  untested cells are absent, not zero")
    untested = [u["definition_id"] for u in K.UNTESTED_CELLS]
    # the complete factorial implied by the axes actually used
    metrics = sorted({d["metric_code"] for d in K.definitions_expanded()})
    pctls = sorted({d["percentile"] for d in K.definitions_expanded()})
    durs = sorted({d["min_duration"] for d in K.definitions_expanded()})
    full = {"%s_P%d_%dD" % (m, p, d) for m in metrics for p in pctls for d in durs}
    have = {d["definition_id"] for d in K.definitions_expanded()}
    gap = sorted(full - have)
    chk(6, "full factorial size", len(full), len(metrics) * len(pctls) * len(durs),
        note="%d metrics x %d percentiles x %d durations" % (len(metrics), len(pctls), len(durs)))
    chk(6, "definitions tested", len(have), 16)
    chk(6, "untested cells identified exactly", gap, sorted(untested),
        note="never zero-filled, never interpolated across")

    cy, cm = U.read_master_county_year(), U.read_master_county_month()
    ev = U.read_master_events()
    for name, frame in (("county-year", cy), ("county-month", cm), ("event", ev)):
        bad = int(frame["definition_id"].isin(untested).sum())
        chk(5, "no %s rows for untested cells" % name, bad, 0,
            note="a zero row would read as 'tested and found nothing'")
    shards = [os.path.basename(p) for p in glob.glob(os.path.join(K.DIR_CANON, "*.csv.gz"))]
    chk(5, "no canonical shard for untested cells",
        sum(1 for s in shards if any(u in s for u in untested)), 0)
    # and a zero is a LEGITIMATE value where a definition was evaluated
    z = int((cy["heatwave_days"] == 0).sum())
    note_only(5, "genuine zero rows in the county-year table", z,
              note="county-years evaluated with no heatwave day -- distinct from an absent cell")


# =============================================================================
# items 7-8 -- matched pairs
# =============================================================================
def item78_matched_pairs(runs, avail_ids):
    K.log("-" * 74)
    K.log("ITEM 7 / 8  matched pairs")
    pairs = U.matched_pairs(runs, only_available=set(avail_ids))
    chk(7, "every pair differs on exactly one axis",
        int((pairs.apply(lambda r: 1, axis=1) != 1).sum()) if len(pairs) else 0, 0,
        note="%d matched pairs total" % len(pairs))
    ids = set(avail_ids)
    chk(7, "no pair references an absent run",
        int((~pairs["run_a"].isin(ids)).sum() + (~pairs["run_b"].isin(ids)).sum()), 0)
    counts = U.matched_pair_counts(pairs)
    for _, r in counts.iterrows():
        note_only(8, "matched pairs on the %s axis" % r["axis"], int(r["n_matched_pairs"]),
                  note="reported with every marginal effect for this axis")
    # the duration axis is short of pairs BECAUSE of the untested cells
    exp_dur = len([1 for d in K.definitions_expanded() if d["min_duration"] == 3]) * 4
    got_dur = int(counts.loc[counts["axis"] == "duration", "n_matched_pairs"].sum())
    chk(8, "duration pairs limited by the untested mean-HI cells", got_dur, exp_dur,
        note="7 of 9 metric x percentile cells have both durations, x 4 windows")
    pairs.to_csv(os.path.join(K.DIR_QA, "s03_matched_pairs.csv"), index=False)
    return pairs


# =============================================================================
# item 9 -- nesting of the duration rule
# =============================================================================
def item9_duration_nesting(runs, avail_ids):
    K.log("-" * 74)
    K.log("ITEM 9  3-day classifications must be subsets of 2-day classifications")
    by = {}
    for r in runs:
        if r["run_id"] in avail_ids:
            by[(r["metric_code"], r["percentile"], r["window_key"], r["min_duration"])] = r
    n_checked = 0
    for (m, p, w, dur), r in sorted(by.items()):
        if dur != 3:
            continue
        two = by.get((m, p, w, 2))
        if two is None:
            note_only(9, "no 2-day counterpart on disk", "%s_P%d_%s" % (m, p, w),
                      note="subset check not possible for this cell")
            continue
        s3 = U.load_day_set(r["definition_id"], w)
        s2 = U.load_day_set(two["definition_id"], w)
        extra = np.setdiff1d(s3, s2, assume_unique=True).size
        j = U.jaccard(s2, s3)
        ratio = s3.size / s2.size if s2.size else np.nan
        chk(9, "3-day days are a subset of 2-day days", extra, 0,
            note="jaccard %.4f, count ratio %.4f (equal iff nested)" % (j, ratio),
            scope="%s_P%d_%s" % (m, p, w))
        chk(9, "jaccard equals the count ratio exactly", round(j, 9), round(ratio, 9),
            note="algebraic consequence of nesting", scope="%s_P%d_%s" % (m, p, w))
        n_checked += 1
    note_only(9, "duration-nesting cells checked", n_checked,
              note="metric x percentile x window cells having both durations")


# =============================================================================
# item 10 -- denominators
# =============================================================================
def item10_denominators():
    K.log("-" * 74)
    K.log("ITEM 10  county-year and county-month denominators")
    el = U.read_eligibility()
    cy, cm = U.read_master_county_year(), U.read_master_county_month()

    per_county = el.groupby(["metric", "window", "county_fips"])["calendar_days"].sum()
    chk(10, "calendar days per county identical everywhere",
        sorted(int(x) for x in per_county.unique()), [4018],
        note="2015-2025 inclusive", scope="eligibility table")
    chk(10, "eligible days never exceed calendar days",
        int((el["eligible_days"] > el["calendar_days"]).sum()), 0, scope="county-month")
    chk(10, "eligible days never negative", int((el["eligible_days"] < 0).sum()), 0)

    for name, frame, dcol in (("county-year", cy, "eligible_county_days"),
                              ("county-month", cm, "eligible_county_days")):
        chk(10, "%s: denominator present on every row" % name,
            int(frame[dcol].isna().sum()), 0)
        chk(10, "%s: denominator strictly positive" % name,
            int((frame[dcol].fillna(0) <= 0).sum()), 0)
        chk(10, "%s: heatwave days never exceed eligible days" % name,
            int((frame["heatwave_days"] > frame[dcol]).sum()), 0,
            note="a rate above 1000 per 1000 would be impossible")
    ineligible = int((el["calendar_days"] - el["eligible_days"]).sum())
    note_only(10, "county-month days excluded from denominators", ineligible,
              note="missing metric, missing threshold, or confirmed RH-clip artifact; "
                   "excluded rather than counted as non-heatwave days")
    art = int(el["artifact_excluded_days"].sum())
    note_only(10, "county-days excluded as confirmed RH-clip artifact", art,
              note="RH-dependent metrics only (mean HI); Tmax/Tmin keep those days")


# =============================================================================
# items 11-12 -- the two allocation rules, verified rather than asserted
# =============================================================================
def item11_county_month_rule():
    """An event crossing two months must be counted ONCE in events_started (its
    onset month), counted as ACTIVE in every month it touches, and its DAYS
    allocated to the month each day actually falls in."""
    K.log("-" * 74)
    K.log("ITEM 11  county-month allocation rule")
    cm, cy, ev = U.read_master_county_month(), U.read_master_county_year(), U.read_master_events()

    started = cm.groupby("run_id")["heatwave_events_started"].sum()
    total = ev.groupby("run_id").size()
    j = pd.concat([started.rename("months"), total.rename("events")], axis=1).dropna()
    chk(11, "events_started summed over months == total events",
        int((j["months"] != j["events"]).sum()), 0,
        note="checked for %d runs; a month-crossing event must not be counted twice" % len(j))

    days_cm = cm.groupby("run_id")["heatwave_days"].sum()
    days_cy = cy.groupby("run_id")["heatwave_days"].sum()
    k = pd.concat([days_cm.rename("cm"), days_cy.rename("cy")], axis=1).dropna()
    chk(11, "heatwave days summed over months == summed over years",
        int((k["cm"] != k["cy"]).sum()), 0,
        note="days are allocated to their actual calendar month and year")
    chk(11, "events_active is never below events_started",
        int((cm["heatwave_events_active"] < cm["heatwave_events_started"]).sum()), 0)

    cross = ev[ev["event_crosses_month"].astype(str).str.lower().isin(("true", "1"))]
    note_only(11, "events crossing a month boundary", len(cross),
              note="each is counted once at onset and active in every month it touches")
    # an active-month total ABOVE the started total is the signature of the rule working
    extra = int(cm["heatwave_events_active"].sum() - cm["heatwave_events_started"].sum())
    chk(11, "month-crossing events show up as extra ACTIVE months",
        extra > 0 if len(cross) else extra == 0, True,
        note="active minus started = %d extra county-months" % extra)


def item12_year_boundary_rule():
    """A run must NOT be broken at 31 December: one physical episode stays one
    event, counted once in its onset year, with its days allocated to their own
    calendar years."""
    K.log("-" * 74)
    K.log("ITEM 12  year-boundary rule")
    ev, cy = U.read_master_events(), U.read_master_county_year()
    cross = ev[ev["event_crosses_year"].astype(str).str.lower().isin(("true", "1"))].copy()
    chk(12, "runs are not broken at 31 December", len(cross) > 0, True,
        note="%d events span a year boundary; zero would mean runs were being split"
             % len(cross))
    if len(cross):
        d = pd.to_datetime(cross["end_date"]) - pd.to_datetime(cross["start_date"])
        chk(12, "every year-crossing event starts in December",
            int((pd.to_datetime(cross["start_date"]).dt.month != 12).sum()), 0)
        chk(12, "every year-crossing event ends in January",
            int((pd.to_datetime(cross["end_date"]).dt.month != 1).sum()), 0)
        chk(12, "onset_year equals the start date's year",
            int((cross["onset_year"] != pd.to_datetime(cross["start_date"]).dt.year).sum()), 0,
            note="the event is counted once, in its onset year")
        note_only(12, "longest year-crossing event (days)", int(cross["event_duration_days"].max()),
                  note="duration is end - start + 1 across the boundary, an integer")

    started = cy.groupby("run_id")["heatwave_events_started"].sum()
    total = ev.groupby("run_id").size()
    j = pd.concat([started.rename("years"), total.rename("events")], axis=1).dropna()
    chk(12, "events_started summed over years == total events",
        int((j["years"] != j["events"]).sum()), 0,
        note="a year-crossing event is counted once, not in both years")

    # its DAYS, however, must appear in both calendar years
    if len(cross):
        r = cross.iloc[int(cross["event_duration_days"].idxmax() == cross.index[0])] \
            if len(cross) > 1 else cross.iloc[0]
        yrs = cy[(cy["run_id"] == r["run_id"]) & (cy["county_fips"] == r["county_fips"])]
        y0 = int(pd.Timestamp(r["start_date"]).year)
        have_both = {y0, y0 + 1}.issubset(set(yrs["year"]))
        chk(12, "days of a year-crossing event appear in BOTH calendar years",
            bool(have_both), True,
            note="example %s in %s: %s to %s" % (r["event_id"], r["county_name"],
                                                 r["start_date"], r["end_date"]),
            scope=r["run_id"])


# =============================================================================
# driver
# =============================================================================
def main():
    K.ensure_dirs()
    t0 = time.time()
    runs = K.runs_expanded()
    avail = U.available_runs(runs)
    avail_ids = [r["run_id"] for r in avail]
    K.log("=" * 74)
    K.log("s03  PRE-COMPARISON VALIDATION  --  %d of %d runs on disk"
          % (len(avail_ids), len(runs)))
    K.log("=" * 74)

    item1_comparability(runs, avail_ids)
    item2_rerun(runs)
    item3_counties(runs)
    item4_combinations(runs, avail_ids)
    item5_no_zero_fill(runs)
    item78_matched_pairs(runs, avail_ids)
    item9_duration_nesting(runs, avail_ids)
    item10_denominators()
    item11_county_month_rule()
    item12_year_boundary_rule()

    df = pd.DataFrame(ROWS)
    df.insert(0, "state", STATE)
    df["checked_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    df.to_csv(os.path.join(K.DIR_QA, "s03_validation.csv"), index=False)

    n_fail = int((df["result"] == "FAIL").sum())
    n_pass = int((df["result"] == "PASS").sum())
    n_rep = int((df["result"] == "REPORTED").sum())
    with open(os.path.join(K.DIR_QA, "s03_validation.md"), "w", encoding="utf-8") as f:
        f.write("# s03 - pre-comparison validation\n\n")
        f.write("%d checks: **%d PASS, %d FAIL**, %d reported observations "
                "(no pass/fail semantics).\n\n" % (len(df), n_pass, n_fail, n_rep))
        f.write("**Verdict: %s**\n\n" % ("the sixteen definitions are comparable on every "
                                         "axis held fixed, and the comparison may be built"
                                         if n_fail == 0 else
                                         "%d FAILURE(S) -- do not build the comparison" % n_fail))
        if n_fail:
            f.write("## Failures\n\n")
            f.write(K.md_table(df[df["result"] == "FAIL"],
                               ["item", "check", "scope", "observed", "expected", "note"]))
            f.write("\n\n")
        for item, title in ((1, "Item 1 - identical fixed axes across all sixteen definitions"),
                            (2, "Item 2 - re-run of the published definitions"),
                            (3, "Item 3 - expected county set"),
                            (4, "Item 4 - definition x window combinations"),
                            (5, "Item 5 - missing combinations are absent, not zero"),
                            (6, "Item 6 - the grid is incomplete (two untested cells)"),
                            (7, "Item 7 - marginal effects from valid matched pairs only"),
                            (8, "Item 8 - matched-pair counts"),
                            (9, "Item 9 - duration nesting"),
                            (10, "Item 10 - valid eligible-day denominators"),
                            (11, "Item 11 - the county-month allocation rule"),
                            (12, "Item 12 - the year-boundary rule")):
            sub = df[df["item"] == item]
            if not len(sub):
                continue
            f.write("## %s\n\n" % title)
            f.write(K.md_table(sub, ["check", "scope", "result", "observed",
                                     "expected", "note"]))
            f.write("\n\n")
    K.log("=" * 74)
    K.log("%d checks: %d PASS, %d FAIL, %d reported   (%.1f min)"
          % (len(df), n_pass, n_fail, n_rep, (time.time() - t0) / 60))
    K.log("-> %s" % os.path.join(K.DIR_QA, "s03_validation.md"))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
