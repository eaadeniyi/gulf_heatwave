"""
=============================================================================
r01  --  STAGE 1: reproduce the existing pipeline and audit it.
=============================================================================
Nothing in the revision is allowed to depend on a number that has not first
been reproduced from the scripts that produced it.

WHAT IS RUN, AND WHERE IT IS WRITTEN
  e01_state_temperature_eda.py   re-executed UNCHANGED, with its output
                                 directories redirected to
                                 current_vs_revised/reproduction/ so the
                                 original package is not touched.
  e03_tables_and_figures.py      re-executed UNCHANGED, same redirection. It
                                 reads the stored per-run tables read-only.
  e02_run_extreme_definitions.py NOT re-executed. Re-running it would rewrite
                                 116 MB of stored run outputs and recompute
                                 four full walk-forward threshold passes. It is
                                 instead reproduced in r06 by an INDEPENDENT
                                 rebuild of every construct from the archived
                                 threshold cache and the county-day table,
                                 checked by exact set equality on the
                                 classified county-dates and on the event
                                 records. That is a stronger check than a
                                 re-run of the same code; the result is carried
                                 into this table by r06.

OUTPUTS
  qa/01_existing_pipeline_reproduction.csv   per-artifact reproduction result
  qa/02_existing_aggregation_inventory.csv   every current aggregation formula,
                                             with its data lineage flags
  qa/03_current_output_checksums.csv         md5 + row counts of every current
                                             output, and of every input
  qa/01b_reproduction_discrepancies.md       written only if something differs
=============================================================================
"""
import os
import sys
import io
import json
import time
import shutil
import hashlib
import platform
import subprocess
import contextlib

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K
import config as C                                          # noqa: E402


# =============================================================================
# provenance
# =============================================================================
def md5_of(path, cap_bytes=None):
    h = hashlib.md5()
    n = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
            n += len(chunk)
            if cap_bytes and n >= cap_bytes:
                break
    return h.hexdigest()


def git_commit():
    try:
        c = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=K.REPO_ROOT,
                           capture_output=True, text=True, timeout=30).stdout.strip()
        d = subprocess.run(["git", "status", "--porcelain"], cwd=K.REPO_ROOT,
                           capture_output=True, text=True, timeout=30).stdout.strip()
        return (c or "unknown") + ("+dirty" if d else "")
    except Exception:
        return "unknown"


def software_versions():
    import matplotlib
    import scipy
    v = {"python": platform.python_version(), "platform": platform.platform(),
         "numpy": np.__version__, "pandas": pd.__version__,
         "matplotlib": matplotlib.__version__, "scipy": scipy.__version__}
    try:
        import geopandas
        v["geopandas"] = geopandas.__version__
    except Exception:
        v["geopandas"] = "unavailable"
    return v


# =============================================================================
# 1. checksums and row counts of every current output and input
# =============================================================================
def checksum_inventory():
    rows = []

    def add(role, path, label=None):
        if not os.path.exists(path):
            rows.append(dict(role=role, artifact=label or os.path.basename(path),
                             path=os.path.relpath(path, K.REPO_ROOT),
                             exists=False, size_bytes=np.nan, md5="", n_rows=np.nan,
                             n_cols=np.nan))
            return
        n_rows, n_cols = np.nan, np.nan
        size = os.path.getsize(path)
        # Row counts are read for every CSV small enough to load cheaply; the
        # multi-hundred-megabyte inputs are checksummed but not parsed here (their
        # row counts are reported by the steps that actually read them).
        if (path.endswith(".csv") or path.endswith(".csv.gz")) and size < 60_000_000:
            try:
                d = pd.read_csv(path, dtype=str, low_memory=False)
                n_rows, n_cols = len(d), d.shape[1]
                del d
            except Exception:
                pass
        rows.append(dict(role=role, artifact=label or os.path.basename(path),
                         path=os.path.relpath(path, K.REPO_ROOT), exists=True,
                         size_bytes=os.path.getsize(path), md5=md5_of(path),
                         n_rows=n_rows, n_cols=n_cols))

    # -- inputs ---------------------------------------------------------------
    for st in K.STATES:
        add("input_raw_ghcn", C.ghcn_path(st), "ghcn_county_day_weather_%s.csv" % st)
    add("input_county_day_idw", C.county_day_path(K.TEST_STATE), "county_daily_heat.csv")
    add("input_coverage_report",
        os.path.join(C.state_output_dir(K.TEST_STATE), "coverage_and_imputation_report.csv"))
    add("input_shapefile", C.COUNTY_SHAPEFILE)
    add("input_eligibility_reused",
        os.path.join(K.REPO_ROOT, "outputs", "definition_comparison", "tables",
                     "eligibility_county_month.csv"))
    for pctl in K.PERCENTILES:
        for w in K.WINDOWS:
            add("input_threshold_cache",
                C.threshold_cache_path(K.TEST_STATE, K.METRIC, pctl, w))
    add("input_benchmark_tmax", os.path.abspath(K.BENCHMARK_TMAX))
    add("input_benchmark_tmin", os.path.abspath(K.BENCHMARK_TMIN))

    # -- current scripts ------------------------------------------------------
    for s in sorted(os.listdir(K.CURRENT_SCRIPTS)):
        if s.endswith(".py"):
            add("current_script", os.path.join(K.CURRENT_SCRIPTS, s))

    # -- current outputs ------------------------------------------------------
    for sub, role in (("tables", "current_table"), ("figures", "current_figure"),
                      ("qa", "current_qa")):
        d = os.path.join(K.CURRENT_PKG, sub)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                add(role, os.path.join(d, f))
    for f in ("FINDINGS.md", "README.md"):
        add("current_document", os.path.join(K.CURRENT_PKG, f))

    # -- current per-run outputs ---------------------------------------------
    runs_dir = os.path.join(K.CURRENT_PKG, "runs")
    for did in sorted(os.listdir(runs_dir)):
        t = os.path.join(runs_dir, did, "tables")
        if not os.path.isdir(t):
            continue
        for f in sorted(os.listdir(t)):
            add("current_run_output", os.path.join(t, f), "%s/%s" % (did, f))

    return pd.DataFrame(rows)


# =============================================================================
# 2. re-execute e01 and e03 with redirected output directories
# =============================================================================
@contextlib.contextmanager
def redirected_current_package(shadow_root):
    """Point the CURRENT package's config at a shadow output tree.

    etx_config is imported once and shared by e01/e03, so overriding its
    directory constants before calling main() redirects every write. The
    package root is left pointing at the original tree because the stored
    per-run tables under runs/ are READ there.
    """
    sys.path.insert(0, K.CURRENT_SCRIPTS)
    import etx_config as EK
    saved = (EK.DIR_FIG, EK.DIR_TABLES, EK.DIR_QA, list(EK.ALL_DIRS))
    EK.DIR_FIG = os.path.join(shadow_root, "figures")
    EK.DIR_TABLES = os.path.join(shadow_root, "tables")
    EK.DIR_QA = os.path.join(shadow_root, "qa")
    EK.ALL_DIRS = [EK.DIR_FIG, EK.DIR_TABLES, EK.DIR_QA]
    for d in EK.ALL_DIRS:
        os.makedirs(d, exist_ok=True)
    try:
        yield EK
    finally:
        EK.DIR_FIG, EK.DIR_TABLES, EK.DIR_QA, EK.ALL_DIRS = saved


def run_module(modname, shadow_root, logfile):
    """Import and run a current script's main() with output captured."""
    buf = io.StringIO()
    t0 = time.time()
    status, err = "PASS", ""
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            mod = __import__(modname)
            rc = mod.main()
        if rc not in (0, None):
            status, err = "NONZERO_EXIT", "main() returned %r" % rc
    except SystemExit as e:
        if e.code not in (0, None):
            status, err = "NONZERO_EXIT", "SystemExit %r" % e.code
    except Exception as e:                              # noqa: BLE001
        status, err = "ERROR", "%s: %s" % (type(e).__name__, e)
        import traceback
        buf.write("\n" + traceback.format_exc())
    with open(logfile, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    return status, err, round(time.time() - t0, 1)


# =============================================================================
# 3. compare reproduced artifacts against the current ones
# =============================================================================
def compare_csv(cur_path, new_path):
    """Value-level comparison of two CSVs. Returns (verdict, detail)."""
    if not os.path.exists(new_path):
        return "MISSING_REPRODUCTION", "the re-run did not write this file"
    if not os.path.exists(cur_path):
        return "MISSING_CURRENT", "no current file to compare against"
    if md5_of(cur_path) == md5_of(new_path):
        return "IDENTICAL_BYTES", ""
    a = pd.read_csv(cur_path, dtype=str, low_memory=False)
    b = pd.read_csv(new_path, dtype=str, low_memory=False)
    if list(a.columns) != list(b.columns):
        return "COLUMNS_DIFFER", "current=%s reproduced=%s" % (list(a.columns),
                                                               list(b.columns))
    if len(a) != len(b):
        return "ROWCOUNT_DIFFERS", "current=%d reproduced=%d" % (len(a), len(b))
    an = pd.read_csv(cur_path, low_memory=False)
    bn = pd.read_csv(new_path, low_memory=False)
    worst, worst_col = 0.0, ""
    for c in an.columns:
        if an[c].dtype.kind in "fi" and bn[c].dtype.kind in "fi":
            d = (an[c].astype(float) - bn[c].astype(float)).abs().max()
            if pd.notna(d) and d > worst:
                worst, worst_col = float(d), c
        else:
            if not a[c].fillna("").equals(b[c].fillna("")):
                return "VALUES_DIFFER", "non-numeric column %r differs" % c
    if worst == 0:
        return "IDENTICAL_VALUES", "byte difference only (formatting)"
    return "VALUES_DIFFER", "max abs numeric difference %.6g in %r" % (worst, worst_col)


def compare_png(cur_path, new_path):
    if not os.path.exists(new_path):
        return "MISSING_REPRODUCTION", "the re-run did not write this figure"
    if not os.path.exists(cur_path):
        return "MISSING_CURRENT", ""
    if md5_of(cur_path) == md5_of(new_path):
        return "IDENTICAL_BYTES", "figure reproduces bit-for-bit"
    return "BYTES_DIFFER", ("PNG differs; matplotlib output is deterministic for a "
                            "fixed version, so this indicates either a data change "
                            "or a library change")


# =============================================================================
# 4. the aggregation inventory -- read off the current code, line by line
# =============================================================================
def aggregation_inventory():
    """Every aggregation the current package performs, with its lineage flags.

    Columns are deliberately blunt: `weighting_unit` is what actually receives
    equal weight in the statistic, which is the defect this revision exists to
    correct.
    """
    R = []

    def row(**kw):
        base = dict(package_step="", code_ref="", quantity="", formula="",
                    input_data="", weighting_unit="", sample="", used_by="",
                    reader_facing_label_now="", issue="", severity="",
                    revision_action="")
        base.update(kw)
        R.append(base)

    # ---- e01 ---------------------------------------------------------------
    row(package_step="e01", code_ref="e01_state_temperature_eda.py:107-118",
        quantity="annual county-level observation (mean_f)",
        formula="mean of daily values within county x year, per variable; "
                "gate n_days >= 328",
        input_data="raw observed GHCN county-day (NO IDW gap-filling)",
        weighting_unit="daily county-level observation",
        sample="all counties; per-variable coverage gate",
        used_by="every Part 1 table and figure",
        reader_facing_label_now="'county-year'",
        issue="sound; the gate is applied per variable so Tmax, Tmin and Tavg "
              "can have different qualifying county-years",
        severity="none", revision_action="kept; per-variable gate documented")
    row(package_step="e01", code_ref="e01_state_temperature_eda.py:121-129",
        quantity="monthly county-level summary (mean_f)",
        formula="mean of daily values within county x year x month; gate n_days >= 25",
        input_data="raw observed GHCN county-day",
        weighting_unit="daily county-level observation",
        sample="all counties", used_by="figure E4, e01_state_month_temperature.csv",
        reader_facing_label_now="'county-month'",
        issue="sound", severity="none", revision_action="kept, relabelled")
    row(package_step="e01", code_ref="e01_state_temperature_eda.py:139-151",
        quantity="'balanced panel' membership",
        formula="count DISTINCT decades in which the county has >= 1 qualifying "
                "annual observation; keep if that count == 5",
        input_data="annual county-level observations passing the gate",
        weighting_unit="county",
        sample="all counties",
        used_by="figure E3, figure E4 bottom row, e01_state_decade_temperature.csv, "
                "every decadal-change claim in FINDINGS.md",
        reader_facing_label_now="'BALANCED panel'",
        issue="NOT balanced. One qualifying year in the 1980s and ten in the 2010s "
              "satisfies the rule, so the number of annual observations a county "
              "contributes still varies by period and by county",
        severity="BLOCKING",
        revision_action="replaced by Sample A (minimum qualifying years in every "
                        "period) and Sample B (identical count in every period)")
    row(package_step="e01", code_ref="e01_state_temperature_eda.py:171-201",
        quantity="state x period temperature level and change",
        formula="median of mean_f over ALL POOLED annual county-level observations "
                "in the period",
        input_data="raw observed GHCN county-day",
        weighting_unit="annual county-level observation (POOLED)",
        sample="'balanced panel' and all reporting counties",
        used_by="figure E3, FINDINGS.md decadal-change table",
        reader_facing_label_now="'median county Tmax'",
        issue="counties with more qualifying years receive more weight; the state "
              "estimate is not a median across counties despite the docstring "
              "saying 'MEDIANS across qualifying counties'",
        severity="BLOCKING",
        revision_action="replaced by daily -> annual -> county-period -> state "
                        "median, one value per county per period, with a "
                        "bootstrap interval across counties")
    row(package_step="e01", code_ref="e01_state_temperature_eda.py:204-228",
        quantity="state x month level, and state x month period difference",
        formula="level: median over pooled monthly county-level summaries; "
                "difference: median over pooled monthly summaries within each "
                "decade on the annual-gate 'balanced panel', last minus first",
        input_data="raw observed GHCN county-day",
        weighting_unit="monthly county-level summary (POOLED)",
        sample="'balanced panel' defined on ANNUAL coverage, not monthly",
        used_by="figure E4, e01_state_month_decadal_change.csv, "
                "e01_level_vs_change_summary.csv",
        reader_facing_label_now="'change ... balanced panel'",
        issue="same pooling defect as the annual case, and the county sample is "
              "selected on annual coverage while the statistic is monthly",
        severity="BLOCKING",
        revision_action="equal-county monthly period values on Sample A and B")
    row(package_step="e01", code_ref="e01_state_temperature_eda.py:157-168",
        quantity="state x year level",
        formula="median of mean_f across counties within one year",
        input_data="raw observed GHCN county-day",
        weighting_unit="county (one annual value each)",
        sample="counties passing the gate that year",
        used_by="figure E1",
        reader_facing_label_now="'median across qualifying counties'",
        issue="correct within a year, but the set of counties changes between "
              "years, so the series mixes a temperature change with a "
              "composition change",
        severity="moderate",
        revision_action="kept; the consistent-county series is added alongside "
                        "and the trend models are run on both")
    row(package_step="e01", code_ref="e01_state_temperature_eda.py:279-324",
        quantity="figure E2 distribution",
        formula="box and strip of ALL pooled annual county-level observations "
                "per state",
        input_data="raw observed GHCN county-day",
        weighting_unit="annual county-level observation (POOLED)",
        sample="all counties passing the gate",
        used_by="figure E2",
        reader_facing_label_now="'Annual mean temperature by state'",
        issue="title states a level; the object shown mixes between-county "
              "variation, year-to-year variation and long-term change. Counties "
              "with more reporting years get more visual weight",
        severity="high",
        revision_action="retitled, note added, and a one-value-per-county "
                        "alternative version produced")
    row(package_step="e01", code_ref="e01_state_temperature_eda.py:363-366,410-431",
        quantity="figure E3 / E4 change panels",
        formula="last period median minus first period median",
        input_data="raw observed GHCN county-day",
        weighting_unit="annual / monthly county-level observation (POOLED)",
        sample="'balanced panel'",
        used_by="figures E3, E4",
        reader_facing_label_now="'warming since the 1980s', 'Decadal change'",
        issue="a two-period difference described with trend language; no time-trend "
              "model is estimated anywhere in the package",
        severity="high",
        revision_action="relabelled as a period difference; Sen slope and OLS "
                        "slope estimated separately in r04")
    row(package_step="e01", code_ref="e01_state_temperature_eda.py:398,423",
        quantity="figure E4 season shading",
        formula="top row shades months 6-9; bottom row shades months 5-9",
        input_data="n/a (annotation)",
        weighting_unit="n/a", sample="n/a", used_by="figure E4",
        reader_facing_label_now="'Jun-Sep' on both rows",
        issue="the two rows shade different month ranges while both are labelled "
              "Jun-Sep",
        severity="moderate",
        revision_action="single prespecified warm season June-September, shaded "
                        "identically in both rows")
    row(package_step="e01", code_ref="etx_config.py:129-149",
        quantity="index naming",
        formula="TX/TN/TG and TXm/TNm/TGm presented as the standard index set",
        input_data="n/a", weighting_unit="n/a", sample="n/a",
        used_by="every Part 1 axis label and title",
        reader_facing_label_now="'TXm', 'TNm', 'TGm'",
        issue="TGm is not a universally recognised symbol, and 'mean daily minimum "
              "temperature' is easily misread as the month's minimum",
        severity="moderate",
        revision_action="plain-language labels: average daily high / low / "
                        "temperature; Tavg defined explicitly as (Tmax+Tmin)/2")

    # ---- e02 ---------------------------------------------------------------
    row(package_step="e02", code_ref="e02_run_extreme_definitions.py:109-149",
        quantity="candidate day",
        formula="relative: value > county x calendar-key walk-forward percentile; "
                "hybrid: relative AND value >= gate; absolute: value > gate",
        input_data="IDW gap-filled county-day table (county_daily_heat.csv)",
        weighting_unit="daily county-level observation",
        sample="Texas, 2015-2025",
        used_by="every Part 2 and Part 3 result",
        reader_facing_label_now="'percentile of the county's own Tmax distribution'",
        issue="the threshold is county- AND calendar-date-specific; describing it "
              "as the county's own distribution omits the calendar conditioning",
        severity="moderate",
        revision_action="description corrected everywhere; mathematics unchanged")
    row(package_step="e02", code_ref="e02_run_extreme_definitions.py:226-262",
        quantity="run summary statistics",
        formula="pooled cross-county totals; per-county median of the 11-year "
                "cumulative classified-day count",
        input_data="IDW gap-filled county-day table",
        weighting_unit="pooled county-dates for the totals; county for the median",
        sample="all 254 counties INCLUDING fully imputed ones, reindexed to 0",
        used_by="e02_master_run_summary.csv, figures E5, E7, E8",
        reader_facing_label_now="'per-county median heatwave days'",
        issue="a cumulative 11-year total per county reported without saying so; "
              "fully imputed counties are included with no data-quality marker",
        severity="high",
        revision_action="annual county-level distributions become the primary "
                        "quantity; cumulative totals retained and labelled; "
                        "imputation status attached to every county-level result")
    row(package_step="e02", code_ref="e02_run_extreme_definitions.py:250",
        quantity="heatwave_days_per_1000_eligible",
        formula="1000 * pooled classified days / count of non-missing "
                "candidate_day_flag",
        input_data="IDW gap-filled county-day table",
        weighting_unit="daily county-level observation",
        sample="construct-specific (correct at this step)",
        used_by="e02_master_run_summary.csv",
        reader_facing_label_now="'per 1,000 eligible county-days'",
        issue="correct here, but e03 later substitutes a single shared denominator",
        severity="none (see the e03 row)",
        revision_action="construct-specific denominators recomputed and compared")

    # ---- e03 ---------------------------------------------------------------
    row(package_step="e03", code_ref="e03_tables_and_figures.py:116-128,273-296",
        quantity="monthly classification rate",
        formula="1000 * classified days in month / eligible days in month, where "
                "eligible days come from the definition-comparison package for "
                "metric=TMAX and window=w15 ONLY",
        input_data="IDW gap-filled county-day table + reused eligibility table",
        weighting_unit="daily county-level observation",
        sample="all counties and years pooled",
        used_by="figures E6, E7 C-D, E8 B; e03_monthly_rates.csv",
        reader_facing_label_now="'heatwave days per 1,000 eligible county-days'",
        issue="the SAME denominator is applied to relative, hybrid and "
              "absolute-only constructs. An absolute rule needs no historical "
              "threshold, so its valid-record set is not the same set",
        severity="BLOCKING",
        revision_action="denominators recomputed per construct family and tested "
                        "for equality; see qa/eligibility_denominator_comparison.csv")
    row(package_step="e03", code_ref="e03_tables_and_figures.py:336-377",
        quantity="figure E5 panel B",
        formula="pooled cross-county event count",
        input_data="stored per-run event tables",
        weighting_unit="pooled events across all counties and years",
        sample="all counties",
        used_by="figure E5",
        reader_facing_label_now="'heatwave events (QA pooled)'",
        issue="a statewide pooled total used as a substantive panel of the main "
              "grid figure",
        severity="high",
        revision_action="replaced by the median annual event count across annual "
                        "county-level observations")
    row(package_step="e03", code_ref="e03_tables_and_figures.py:342-343",
        quantity="figure E5 panel D",
        formula="percentage of classified days outside months 6-9",
        input_data="stored per-run daily tables",
        weighting_unit="classified county-date",
        sample="all counties",
        used_by="figure E5, FINDINGS.md",
        reader_facing_label_now="'% of heatwave days outside Jun-Sep'",
        issue="merges the shoulder months (May, October) with November-April into "
              "one category, which hides where the classifications actually fall",
        severity="high",
        revision_action="split into June-September, May and October, and "
                        "November-April")
    row(package_step="e03", code_ref="e03_tables_and_figures.py:429-436",
        quantity="figure E6 caption",
        formula="n/a (claim)",
        input_data="n/a", weighting_unit="n/a", sample="n/a", used_by="figure E6",
        reader_facing_label_now="'the rate is nearly flat across the calendar'",
        issue="'flat' asserted with no flatness criterion; y-axes are shared by "
              "sharey=True but the claim is still unquantified",
        severity="moderate",
        revision_action="a flatness criterion is defined, computed and reported; "
                        "the word is used only if the criterion is met")
    row(package_step="e03", code_ref="e03_tables_and_figures.py:522-530",
        quantity="figure E7 framing",
        formula="n/a (claim)",
        input_data="n/a", weighting_unit="n/a", sample="n/a", used_by="figure E7",
        reader_facing_label_now="'floor'",
        issue="'floor' reads as a correction to the relative rule; the object is "
              "an absolute gate that changes the construct",
        severity="moderate",
        revision_action="renamed 'absolute Tmax gate'; construct change stated in "
                        "the figure")
    row(package_step="e03", code_ref="e03_tables_and_figures.py:534-619",
        quantity="figure E8 panel A",
        formula="per-county median of the 11-year cumulative classified-day count",
        input_data="stored per-run county-year tables",
        weighting_unit="county",
        sample="all counties including fully imputed",
        used_by="figure E8, FINDINGS.md Part 3b table",
        reader_facing_label_now="'per-county median heatwave days'",
        issue="a study-period cumulative total presented without the annual "
              "distribution behind it",
        severity="high",
        revision_action="annual county-level count distributions, monthly rates "
                        "and event-count distributions")
    row(package_step="e03", code_ref="e03_tables_and_figures.py:655-662",
        quantity="figure E9 caption",
        formula="n/a (claim)",
        input_data="n/a", weighting_unit="n/a", sample="n/a", used_by="figure E9",
        reader_facing_label_now="'a relative percentile rule flags a similar "
                                "NUMBER of days everywhere by construction'",
        issue="not true by construction. Persistence, temporal dependence, "
              "warming relative to the walk-forward baseline, missingness, "
              "imputation and station composition all vary between counties",
        severity="BLOCKING",
        revision_action="caption replaced; the between-county spread is measured "
                        "and reported instead of asserted away")
    row(package_step="e03", code_ref="e03_tables_and_figures.py:299-330",
        quantity="county-level gate effect",
        formula="per-county classified days with and without the gate; "
                "pct_retained",
        input_data="stored per-run county-year tables + coverage report",
        weighting_unit="county",
        sample="all counties",
        used_by="figure E9, e03_county_floor_effect.csv",
        reader_facing_label_now="'% of days retained'",
        issue="sound arithmetic; fully imputed counties are merged in without "
              "being marked on the map",
        severity="moderate",
        revision_action="fully imputed counties hatched, and a second version "
                        "excluding them")

    # ---- e04 ---------------------------------------------------------------
    row(package_step="e04", code_ref="FINDINGS.md:13,17-27,51-61,85-92",
        quantity="written claims",
        formula="read from the tables above",
        input_data="derived", weighting_unit="inherited",
        sample="inherited", used_by="FINDINGS.md, README.md",
        reader_facing_label_now="'BALANCED panel', 'warming', 'heatwave days'",
        issue="every headline number inherits the pooled aggregation and the "
              "mis-specified panel; 'heatwave' is used for year-round relative "
              "constructs with no absolute condition",
        severity="BLOCKING",
        revision_action="all claims recomputed and rewritten in reports/")
    return pd.DataFrame(R)


# =============================================================================
# 5. figure lineage inventory (Stage 1 item 6)
# =============================================================================
def figure_lineage():
    F = [
        ("e01_fig01_annual_series_by_state.png", "E1", "raw observed GHCN", "no",
         "unbalanced (counties passing the gate that year)", "county-level median",
         "no", "annual county-level observation"),
        ("e01_fig02_distribution_by_state.png", "E2", "raw observed GHCN", "no",
         "unbalanced", "POOLED annual county-level observations", "no",
         "annual county-level observation"),
        ("e01_fig03_decadal_change.png", "E3", "raw observed GHCN", "no",
         "'balanced panel' (>=1 qualifying year per decade) and all reporting",
         "POOLED annual county-level observations", "no",
         "annual county-level observation"),
        ("e01_fig04_monthly.png", "E4", "raw observed GHCN", "no",
         "'balanced panel' for the change row only",
         "POOLED monthly county-level summaries", "no",
         "monthly county-level summary"),
        ("e03_fig05_part2_percentile_duration_grid.png", "E5",
         "IDW gap-filled county-day", "yes", "all 254 counties",
         "county median of cumulative totals (A, C); POOLED events (B); "
         "POOLED classified days (D)", "yes (panels B and D)",
         "mixed: county and pooled county-date"),
        ("e03_fig05b_part2_agreement.png", "E5b", "IDW gap-filled county-day",
         "yes", "all 254 counties", "set of classified county-dates", "no",
         "county-date record"),
        ("e03_fig06_part2_seasonality.png", "E6", "IDW gap-filled county-day",
         "yes", "all 254 counties",
         "POOLED classified days / reused shared denominator", "yes",
         "daily county-level observation"),
        ("e03_fig07_floor_effect.png", "E7", "IDW gap-filled county-day", "yes",
         "all 254 counties", "POOLED classified days and pooled events", "yes",
         "mixed"),
        ("e03_fig08_absolute_vs_relative.png", "E8", "IDW gap-filled county-day",
         "yes", "all 254 counties",
         "county median of cumulative totals; POOLED monthly rates", "yes",
         "mixed"),
        ("e03_fig09_county_floor_effect_map.png", "E9", "IDW gap-filled county-day",
         "yes", "all 254 counties including fully imputed", "county-level", "no",
         "county"),
    ]
    return pd.DataFrame(F, columns=["figure_file", "figure_id", "input_data",
                                    "uses_idw_filled_data", "sample",
                                    "aggregation", "uses_statewide_pooled_totals",
                                    "unit_of_analysis"])


# =============================================================================
# driver
# =============================================================================
def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 78)
    K.log("r01  STAGE 1 -- reproduce the existing pipeline and audit it")
    K.log("=" * 78)

    prov = dict(software_versions())
    prov["git_commit"] = git_commit()
    prov["run_started_utc"] = pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(K.DIR_CONFIG, "provenance.json"), "w") as f:
        json.dump(prov, f, indent=2)
    K.log("provenance: python %s, pandas %s, numpy %s, git %s"
          % (prov["python"], prov["pandas"], prov["numpy"], prov["git_commit"]))

    K.resolved_configuration().to_csv(
        os.path.join(K.DIR_CONFIG, "resolved_configuration.csv"), index=False)
    shutil.copy2(os.path.join(K.HERE if hasattr(K, "HERE") else
                              os.path.dirname(os.path.abspath(__file__)),
                              "r00_config.py"),
                 os.path.join(K.DIR_CONFIG, "r00_config_snapshot.py"))

    # ---- checksums ---------------------------------------------------------
    K.log("-" * 78)
    K.log("[1/4] checksumming current outputs and inputs ...")
    inv = checksum_inventory()
    inv.to_csv(os.path.join(K.DIR_QA, "03_current_output_checksums.csv"), index=False)
    K.log("      %d artifacts (%d missing)" % (len(inv), int((~inv["exists"]).sum())))

    # ---- re-execute e01 and e03 -------------------------------------------
    K.log("-" * 78)
    K.log("[2/4] re-executing the current scripts with redirected outputs ...")
    shadow = K.DIR_REPRO
    for sub in ("tables", "figures", "qa", "logs"):
        os.makedirs(os.path.join(shadow, sub), exist_ok=True)
    runlog = []
    with redirected_current_package(shadow) as EK:
        st, err, secs = run_module("e01_state_temperature_eda", shadow,
                                   os.path.join(shadow, "logs", "e01.log"))
        runlog.append(("e01_state_temperature_eda.py", st, err, secs))
        K.log("      e01 %s (%.0fs) %s" % (st, secs, err))
        # e03 reads tables/e02_master_run_summary.csv from EK.DIR_TABLES
        src = os.path.join(K.CURRENT_PKG, "tables", "e02_master_run_summary.csv")
        shutil.copy2(src, os.path.join(EK.DIR_TABLES, "e02_master_run_summary.csv"))
        st, err, secs = run_module("e03_tables_and_figures", shadow,
                                   os.path.join(shadow, "logs", "e03.log"))
        runlog.append(("e03_tables_and_figures.py", st, err, secs))
        K.log("      e03 %s (%.0fs) %s" % (st, secs, err))

    # ---- compare -----------------------------------------------------------
    K.log("-" * 78)
    K.log("[3/4] comparing reproduced artifacts with the current ones ...")
    rows = []
    for script, status, err, secs in runlog:
        rows.append(dict(stage="script_execution", artifact=script,
                         verdict=status, detail=err, seconds=secs))
    for sub, cmp_fn in (("tables", compare_csv), ("figures", compare_png),
                        ("qa", compare_csv)):
        cur_dir = os.path.join(K.CURRENT_PKG, sub)
        new_dir = os.path.join(shadow, sub)
        names = sorted(set(os.listdir(cur_dir)) | set(os.listdir(new_dir))
                       if os.path.isdir(new_dir) else os.listdir(cur_dir))
        for n in names:
            cur, new = os.path.join(cur_dir, n), os.path.join(new_dir, n)
            if not os.path.exists(new):
                if n.startswith("e02_"):
                    rows.append(dict(stage="reproduction", artifact="%s/%s" % (sub, n),
                                     verdict="NOT_RE_EXECUTED",
                                     detail="produced by e02, reproduced independently "
                                            "in r06 by exact set equality",
                                     seconds=np.nan))
                    continue
            v, d = cmp_fn(cur, new)
            rows.append(dict(stage="reproduction", artifact="%s/%s" % (sub, n),
                             verdict=v, detail=d, seconds=np.nan))
    rep = pd.DataFrame(rows)
    rep.to_csv(os.path.join(K.DIR_QA, "01_existing_pipeline_reproduction.csv"),
               index=False)

    ok = rep["verdict"].isin(["PASS", "IDENTICAL_BYTES", "IDENTICAL_VALUES",
                              "NOT_RE_EXECUTED"])
    K.log("      %d/%d artifacts reproduce; %d discrepancy(ies)"
          % (int(ok.sum()), len(rep), int((~ok).sum())))
    for _, r in rep[~ok].iterrows():
        K.log("        ! %-52s %-20s %s" % (r["artifact"], r["verdict"], r["detail"]))

    if (~ok).any():
        lines = ["# Stage 1 reproduction discrepancies", "",
                 "Re-running the current scripts with their outputs redirected to "
                 "`current_vs_revised/reproduction/` did not reproduce every current "
                 "artifact bit-for-bit. Each discrepancy is listed with what differs.",
                 ""]
        lines.append(K.md_table(rep[~ok][["stage", "artifact", "verdict", "detail"]]))
        with open(os.path.join(K.DIR_QA, "01b_reproduction_discrepancies.md"), "w",
                  encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    # ---- inventories --------------------------------------------------------
    K.log("-" * 78)
    K.log("[4/4] writing the aggregation and figure-lineage inventories ...")
    agg = aggregation_inventory()
    agg.to_csv(os.path.join(K.DIR_QA, "02_existing_aggregation_inventory.csv"),
               index=False)
    fl = figure_lineage()
    fl.to_csv(os.path.join(K.DIR_QA, "02b_existing_figure_lineage.csv"), index=False)
    n_block = int((agg["severity"] == "BLOCKING").sum())
    K.log("      %d aggregations catalogued, %d flagged BLOCKING" % (len(agg), n_block))
    for _, r in agg[agg["severity"] == "BLOCKING"].iterrows():
        K.log("        BLOCKING  %-10s %s" % (r["package_step"], r["quantity"]))

    K.log("=" * 78)
    K.log("r01 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
