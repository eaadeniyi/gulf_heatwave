"""
=============================================================================
r00  --  CONFIGURATION for the extreme-temperature REVISION (v2).
=============================================================================
This package is a REVISION of outputs/extreme_temp_tests/. It does not modify
that package; it reads its inputs and its stored outputs, recomputes what was
computed weakly, renames what was named misleadingly, and writes everything to
outputs/extreme_temperature_revision_v2/.

Everything a reader or a reviewer might want to change is HERE and is printed
into config/resolved_configuration.csv at run time, so no threshold, gate,
percentile or sample rule is buried in a script.

-----------------------------------------------------------------------------
THE UNIT OF ANALYSIS, STATED ONCE
-----------------------------------------------------------------------------
  "The analysis uses a county-by-day panel in which each record represents one
   county on one calendar date."

After that sentence the reader-facing outputs use ordinary language:
  county-day    -> "daily county-level observation" / "county-date record"
  county-month  -> "monthly county-level summary"
  county-year   -> "annual county-level observation"
  eligible      -> "valid"
Internal column names may keep the database terms; labels must not.

-----------------------------------------------------------------------------
THE THREE CONSTRUCT FAMILIES (they are NOT variants of one another)
-----------------------------------------------------------------------------
  A  RELATIVE WARM SPELL          REL_TX_P90_D3_W15
     daily high above the county- AND calendar-date-specific historical
     percentile, for at least D consecutive days. Year-round, no absolute
     condition -> NOT called a heatwave in this package.

  B  HYBRID RELATIVE-AND-ABSOLUTE HEAT EVENT   HYB_TX_P90_D3_A90_W15
     the relative condition AND an absolute daily-high gate.

  C  ABSOLUTE HOT SPELL           ABS_TX_A90_D3
     daily high above a fixed value for at least D consecutive days. No
     percentile, no baseline, therefore no threshold window.

"TX" in an identifier is the ETCCDI daily-maximum-temperature symbol, NOT the
state abbreviation. The state is carried separately (every Part 2/3 result here
is Texas). This collision is unfortunate but the identifier grammar was
specified; it is documented in data_dictionary/definition_registry_revised.csv.

The 80 degF and 90 degF values are ABSOLUTE DAILY-HIGH GATES chosen for this
sensitivity test. They are NOT National Weather Service advisory thresholds and
must never be described as such.
=============================================================================
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REV_ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUTPUTS_ROOT = os.path.abspath(os.path.join(REV_ROOT, ".."))
REPO_ROOT = os.path.abspath(os.path.join(OUTPUTS_ROOT, ".."))
PIPELINE_DIR = os.path.join(REPO_ROOT, "pipeline")
CURRENT_PKG = os.path.join(OUTPUTS_ROOT, "extreme_temp_tests")
CURRENT_SCRIPTS = os.path.join(CURRENT_PKG, "scripts")

sys.path.insert(0, PIPELINE_DIR)
import config as C                                          # noqa: E402

# --- output directories -----------------------------------------------------
DIR_CONFIG = os.path.join(REV_ROOT, "config")
DIR_DICT = os.path.join(REV_ROOT, "data_dictionary")
DIR_TABLES = os.path.join(REV_ROOT, "tables")
DIR_FIG = os.path.join(REV_ROOT, "figures")
DIR_PROFILES = os.path.join(REV_ROOT, "county_profiles")
DIR_EVENT_AUDITS = os.path.join(REV_ROOT, "event_audits")
DIR_QA = os.path.join(REV_ROOT, "qa")
DIR_REPORTS = os.path.join(REV_ROOT, "reports")
DIR_CVR = os.path.join(REV_ROOT, "current_vs_revised")
DIR_REPRO = os.path.join(DIR_CVR, "reproduction")
ALL_DIRS = [DIR_CONFIG, DIR_DICT, DIR_TABLES, DIR_FIG, DIR_PROFILES,
            DIR_EVENT_AUDITS, DIR_QA, DIR_REPORTS, DIR_CVR, DIR_REPRO]


def ensure_dirs():
    for d in ALL_DIRS:
        os.makedirs(d, exist_ok=True)


def log(*a):
    print(*a, flush=True)


class BlockingQAFailure(RuntimeError):
    """Raised when a QA test that must stop the pipeline fails."""


# =============================================================================
# PART 1  --  the five-state temperature description
# =============================================================================
STATES = ["TX", "LA", "MS", "AL", "FL"]
STATE_LABEL = {"TX": "Texas", "LA": "Louisiana", "MS": "Mississippi",
               "AL": "Alabama", "FL": "Florida"}

YEARS = (1979, 2025)            # 2026 excluded: the pull ends 2026-07-05
YEARS_LABEL = "%d-%d" % YEARS

MIN_DAYS_PER_COUNTY_YEAR = 328  # ~90% of 365 valid daily observations
MIN_DAYS_PER_COUNTY_MONTH = 25  # ~83% of a 30-day month

# --- comparison periods -----------------------------------------------------
# 2020-2025 is a SIX-YEAR RECENT PERIOD, not a decade, and is labelled that way
# everywhere. 1979 stands alone before the first full decade and is in the
# annual series but not in the period comparison.
PERIODS = [(1980, 1989), (1990, 1999), (2000, 2009), (2010, 2019), (2020, 2025)]
PERIOD_LABEL = {(1980, 1989): "1980-1989", (1990, 1999): "1990-1999",
                (2000, 2009): "2000-2009", (2010, 2019): "2010-2019",
                (2020, 2025): "2020-2025"}
PERIOD_NOTE = {(2020, 2025): "six-year recent period"}
PERIOD_ORDER = [PERIOD_LABEL[p] for p in PERIODS]
BASE_PERIOD = PERIOD_LABEL[PERIODS[0]]
RECENT_PERIOD = PERIOD_LABEL[PERIODS[-1]]


def period_length(p):
    return p[1] - p[0] + 1


def period_of(year):
    for p in PERIODS:
        if p[0] <= year <= p[1]:
            return PERIOD_LABEL[p]
    return None


def period_label_long(label):
    n = PERIOD_NOTE.get([p for p in PERIODS if PERIOD_LABEL[p] == label][0], "")
    return "%s (%s)" % (label, n) if n else label


# --- SAMPLE A: consistent-county sample -------------------------------------
#   A county must have at least this many QUALIFYING ANNUAL OBSERVATIONS in
#   EVERY comparison period. This is what the previous package's "balanced
#   panel" was called but did not enforce: it required only >= 1 qualifying
#   year per decade.
SAMPLE_A_MIN_YEARS = {(1980, 1989): 8, (1990, 1999): 8, (2000, 2009): 8,
                      (2010, 2019): 8, (2020, 2025): 5}
SAMPLE_A_NAME = "consistent_county"

# --- SAMPLE B: strict balanced sample ---------------------------------------
#   Every included county contributes EXACTLY the same number of annual
#   observations to every period. K is the length of the shortest period, so
#   the rule is attainable in all five periods.
#   Selection rule (documented, deterministic, no randomness): within each
#   period take the K qualifying years whose distance to the period midpoint is
#   smallest; ties are broken toward the EARLIER year.
SAMPLE_B_YEARS_PER_PERIOD = 6
SAMPLE_B_SELECTION_RULE = ("K qualifying years closest to the period midpoint; "
                           "ties broken toward the earlier year")
SAMPLE_B_NAME = "strict_balanced"

SAMPLES = [SAMPLE_A_NAME, SAMPLE_B_NAME]

# --- county-level period statistic ------------------------------------------
COUNTY_PERIOD_STAT = "mean"     # each county's annual values -> one period value
STATE_PERIOD_STAT = "median"    # across counties, one value per county

# --- bootstrap ---------------------------------------------------------------
BOOTSTRAP_N = 2000
BOOTSTRAP_CI = (2.5, 97.5)
BOOTSTRAP_SEED = 20260801       # fixed: results are reproducible bit-for-bit
BOOTSTRAP_UNIT = "county"       # counties are resampled, never county-years

# =============================================================================
# TERMINOLOGY
# =============================================================================
PANEL_SENTENCE = ("The analysis uses a county-by-day panel in which each record "
                  "represents one county on one calendar date.")

# daily variables ------------------------------------------------------------
#   Tavg is DEFINED here as (Tmax + Tmin) / 2 and is labelled as such wherever
#   it appears. TGm is NOT used: it is not a universally recognised symbol.
TEMP_VARS = [
    ("tmax_f", "Tmax", "TX", "Daily high temperature",
     "Average daily high temperature",
     "daily maximum air temperature"),
    ("tmin_f", "Tmin", "TN", "Daily low temperature",
     "Average daily low temperature",
     "daily minimum air temperature"),
    ("tavg_f", "Tavg", "TM", "Daily average temperature",
     "Average daily temperature",
     "daily average temperature, defined as (Tmax + Tmin) / 2"),
]
VAR_KEYS = [v[1] for v in TEMP_VARS]
VAR_COL = {v[1]: v[0] for v in TEMP_VARS}
VAR_SYMBOL = {v[1]: v[2] for v in TEMP_VARS}
VAR_DAILY_LABEL = {v[1]: v[3] for v in TEMP_VARS}
VAR_PERIOD_LABEL = {v[1]: v[4] for v in TEMP_VARS}
VAR_DEFINITION = {v[1]: v[5] for v in TEMP_VARS}


def axis_label(var, unit="degF"):
    """Reader-facing axis label, e.g. 'Average daily high temperature (degF)'."""
    return "%s (%s)" % (VAR_PERIOD_LABEL[var], unit)


# reader-facing unit language -------------------------------------------------
UNIT_LANGUAGE = {
    "county_day": "daily county-level observation",
    "county_date": "county-date record",
    "county_month": "monthly county-level summary",
    "county_year": "annual county-level observation",
    "eligible_county_days": "valid daily county-level observations",
    "classified_county_days": "county-dates classified as heatwave days",
    "rate": "classified days per 1,000 valid daily county-level observations",
}
RATE_AXIS = "Classified days per 1,000 valid\ndaily county-level observations"

# =============================================================================
# PARTS 2 AND 3  --  classification constructs
# =============================================================================
TEST_STATE = "TX"
ANALYSIS_YEARS = C.ANALYSIS_YEARS               # (2015, 2025)
ANALYSIS_YEARS_LABEL = "%d-%d" % ANALYSIS_YEARS
METRIC = "tmax"
METRIC_COL = C.METRICS[METRIC]["col"]
METRIC_SYMBOL = "TX"                            # ETCCDI daily maximum
METRIC_READER = "daily high temperature"

PERCENTILES = [80, 85, 90]
DURATIONS = [2, 3, 5]
WINDOWS = ["w05", "w15", "month", "month_pm7"]
PRIMARY_WINDOW = "w15"
WINDOW_CODE = {"w05": "W05", "w15": "W15", "month": "MON", "month_pm7": "MONPM7"}
WINDOW_READER = {
    "w05": "centred 5-day calendar window",
    "w15": "centred 15-day calendar window",
    "month": "calendar-month window",
    "month_pm7": "calendar month extended 7 days each side",
}
ABSOLUTE_GATES_F = [80.0, 90.0]

# seasons --------------------------------------------------------------------
WARM_SEASON = [6, 7, 8, 9]
SHOULDER_SEASON = [5, 10]
COOL_SEASON = [11, 12, 1, 2, 3, 4]
SEASON_LABEL = {"warm": "June-September", "shoulder": "May and October",
                "cool": "November-April"}
SEASON_OF = {}
for _m in WARM_SEASON:
    SEASON_OF[_m] = "warm"
for _m in SHOULDER_SEASON:
    SEASON_OF[_m] = "shoulder"
for _m in COOL_SEASON:
    SEASON_OF[_m] = "cool"
WARM_SEASON_PHRASE = "Prespecified warm season: June-September"

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# --- identifiers -------------------------------------------------------------
def rel_id(percentile, duration, window=PRIMARY_WINDOW):
    return "REL_%s_P%d_D%d_%s" % (METRIC_SYMBOL, percentile, duration,
                                  WINDOW_CODE[window])


def hyb_id(percentile, duration, gate_f, window=PRIMARY_WINDOW):
    return "HYB_%s_P%d_D%d_A%d_%s" % (METRIC_SYMBOL, percentile, duration,
                                      int(gate_f), WINDOW_CODE[window])


def abs_id(gate_f, duration):
    return "ABS_%s_A%d_D%d" % (METRIC_SYMBOL, int(gate_f), duration)


def rel_name(percentile, duration, window=PRIMARY_WINDOW):
    return ("County-specific %dth-percentile Tmax warm spell, minimum duration "
            "%s day%s" % (percentile, _spell(duration), "" if duration == 1 else "s"))


def hyb_name(percentile, duration, gate_f, window=PRIMARY_WINDOW):
    return ("County-specific %dth-percentile Tmax event with a %d degF absolute "
            "gate, minimum duration %s days" % (percentile, int(gate_f), _spell(duration)))


def abs_name(gate_f, duration):
    return ("Daily maximum temperature above %d degF for at least %s consecutive "
            "days" % (int(gate_f), _spell(duration)))


def _spell(n):
    return {2: "two", 3: "three", 5: "five"}.get(n, str(n))


# --- legacy crosswalk --------------------------------------------------------
def legacy_rel(percentile, duration):
    return "TMAX_P%d_%dD" % (percentile, duration)


def legacy_hyb(percentile, duration, gate_f):
    return "TMAX_P%d_%dD_F%d" % (percentile, duration, int(gate_f))


def legacy_abs(gate_f, duration):
    return "TMAX_ABS%d_%dD" % (int(gate_f), duration)


def constructs():
    """Every construct in this package, in reporting order.

    family: relative | hybrid | absolute
    Each row carries BOTH the revised identifier and the legacy directory name
    the stored run outputs are filed under, so nothing has to be re-classified.
    """
    out = []
    for p in PERCENTILES:
        for d in DURATIONS:
            for w in WINDOWS:
                out.append(dict(
                    family="relative", construct_id=rel_id(p, d, w),
                    legacy_definition_id=legacy_rel(p, d), legacy_window=w,
                    percentile=p, duration_days=d, absolute_gate_f=None, window=w,
                    reader_name=rel_name(p, d, w),
                    day_label="relative warm-spell day",
                    event_label="relative warm spell"))
    for g in ABSOLUTE_GATES_F:
        for p in PERCENTILES:
            for d in DURATIONS:
                w = PRIMARY_WINDOW
                out.append(dict(
                    family="hybrid", construct_id=hyb_id(p, d, g, w),
                    legacy_definition_id=legacy_hyb(p, d, g), legacy_window=w,
                    percentile=p, duration_days=d, absolute_gate_f=g, window=w,
                    reader_name=hyb_name(p, d, g, w),
                    day_label="hybrid heat-event day",
                    event_label="hybrid relative-and-absolute heat event"))
    for g in ABSOLUTE_GATES_F:
        for d in DURATIONS:
            out.append(dict(
                family="absolute", construct_id=abs_id(g, d),
                legacy_definition_id=legacy_abs(g, d), legacy_window="none",
                percentile=None, duration_days=d, absolute_gate_f=g, window=None,
                reader_name=abs_name(g, d),
                day_label="absolute hot-spell day",
                event_label="absolute hot spell"))
    return out


def constructs_primary():
    """Constructs available at the primary window (relative + hybrid) plus the
    absolute family, which has no window axis."""
    return [c for c in constructs()
            if (c["family"] != "relative" or c["window"] == PRIMARY_WINDOW)]


PRIMARY_CONSTRUCT = rel_id(90, 3, PRIMARY_WINDOW)   # used for worked examples

# =============================================================================
# AUDITS AND SENSITIVITIES
# =============================================================================
LONG_EVENT_DAYS = 15            # every event longer than this is audited
LONG_EVENT_DAYS_STRICT = 20     # reported separately

IMPUTATION_STRATA = [
    ("all_counties", "All counties"),
    ("any_observed", "Counties with any observed temperature"),
    ("imputation_lt_20pct", "Counties with less than 20% imputation"),
    ("imputation_lt_10pct", "Counties with less than 10% imputation"),
    ("not_fully_imputed", "Counties that are not fully imputed"),
    ("anchor_stations", "Anchor-station subset (stable reporting counties)"),
]
ANCHOR_MIN_OBSERVED_SHARE = 0.95   # anchor = >= 95% natively observed days

# physical plausibility (Fahrenheit); values outside are FLAGGED, never edited
PLAUSIBLE_TMAX_F = (-40.0, 135.0)
PLAUSIBLE_TMIN_F = (-50.0, 110.0)
TAVG_TOLERANCE_F = 1e-6
CELSIUS_TEST_CASES = [(0.0, 32.0), (100.0, 212.0), (-40.0, -40.0), (37.0, 98.6)]

# --- county-dates whose daily high is below their daily low ------------------
# QA TEST A found 18 such records in 8,678,621 raw daily county-level records
# (0.0002%). They are not measurement errors in the station data: on 14 of the
# 18, the county daily high and the county daily low were averaged over
# DIFFERENT NUMBERS OF STATIONS, so the county's "high" and "low" describe
# different station sets and are not guaranteed to be internally consistent.
# That is a property of the county aggregation used by the GHCN county-day
# pull, and it is reported as a finding rather than assumed away.
#
# DECLARED HANDLING (this is a prespecified rule, printed at run time, not a
# silent drop): the affected county-DATES are quarantined from the analysis
# panel in full - all three variables - and written unaltered to
# qa/quarantined_inverted_daily_records.csv. The raw input files are never
# modified. After quarantine the panel satisfies Tmax >= Tmin by construction
# and TEST A is re-run as a blocking check.
#
# None of the affected county-dates is a Texas record inside the 2015-2025
# classification window, so no Part 2 or Part 3 result depends on this choice.
# It remains an open item for advisor sign-off.
INVERTED_RECORD_ACTION = "quarantine_whole_county_date_and_report"
INVERTED_RECORD_MAX_TOLERATED = 100     # more than this is a systematic failure, not a
                                        # handful of aggregation artifacts -> hard stop

# =============================================================================
# VISUAL ENCODING
# =============================================================================
# The palettes below are VALIDATED, not chosen by eye. scripts/r_palette.py
# implements the project's visualisation standard - OKLCH lightness band, chroma
# floor, contrast against the surface, and colour-vision separation measured as
# Euclidean distance in OKLab x 100 under protanopia and deuteranopia simulated
# with Machado, Oliveira and Fernandes (2009) at severity 1.0 - and writes
# qa/palette_validation.csv. The inherited palette FAILED: Louisiana and Alabama
# were 1.90 apart under protanopia, i.e. indistinguishable.
#
# STATES are the only genuinely NOMINAL categorical dimension here, so they take
# five fixed hues assigned in a fixed order and never cycled. This ordering
# clears the all-pairs gate (worst normal 16.3, worst colour-vision 13.0), which
# a five-hue set usually cannot. Two of the five sit below the 3:1 contrast
# target; the standard relaxes that where the values are readable another way,
# and every figure here carries direct labels and a saved CSV. Each state also
# carries a distinct marker, so identity is never colour alone.
STATE_STYLE = {
    "TX": dict(color="#eda100", marker="^", label="Texas", edge="#8a5f00"),
    "LA": dict(color="#2a78d6", marker="o", label="Louisiana", edge="#1a4b87"),
    "MS": dict(color="#008300", marker="s", label="Mississippi", edge="#005200"),
    "AL": dict(color="#4a3aa7", marker="D", label="Alabama", edge="#2e2469"),
    "FL": dict(color="#e87ba4", marker="v", label="Florida", edge="#a63f68"),
}
# GATE STRENGTH is ORDINAL - no gate, then 80 degF, then 90 degF - so it takes a
# single hue in monotone lightness steps rather than three unrelated hues. The
# construct FAMILY is the same axis (purely relative, hybrid, absolute-only) and
# reuses the ramp, so a reader learns one encoding instead of two. Hatch is
# carried as a second encoding throughout.
ORDINAL_RAMP = ["#f2a663", "#ae5c13", "#572b05"]
FAMILY_STYLE = {
    "relative": dict(color=ORDINAL_RAMP[0], hatch=None, label="Relative warm spell"),
    "hybrid": dict(color=ORDINAL_RAMP[1], hatch="//",
                   label="Hybrid relative + absolute"),
    "absolute": dict(color=ORDINAL_RAMP[2], hatch="xx", label="Absolute hot spell"),
}
GATE_STYLE = {None: dict(color=ORDINAL_RAMP[0], hatch=None, label="no absolute gate"),
              80.0: dict(color=ORDINAL_RAMP[1], hatch="//",
                         label="80 degF absolute gate"),
              90.0: dict(color=ORDINAL_RAMP[2], hatch="xx",
                         label="90 degF absolute gate")}
# SEASON is a polarity around the shoulder months, so it takes a DIVERGING pair
# with a neutral grey midpoint: warm and cool at the poles, May and October in
# the middle. Never a rainbow, never a hue at the midpoint.
SEASON_STYLE = {"warm": dict(color="#c0392b", label=SEASON_LABEL["warm"]),
                "shoulder": dict(color="#8a8a8a", label=SEASON_LABEL["shoulder"]),
                "cool": dict(color="#2a78d6", label=SEASON_LABEL["cool"])}
SAMPLE_STYLE = {SAMPLE_A_NAME: dict(color="#2a78d6", hatch=None,
                                    label="Sample A: consistent-county"),
                SAMPLE_B_NAME: dict(color="#008300", hatch="\\\\",
                                    label="Sample B: strict balanced")}
CURRENT_STYLE = dict(color="#8a8a8a", hatch="..", label="Current package")
PCTL_STYLE = {80: dict(ls=":", label="80th"), 85: dict(ls="--", label="85th"),
              90: dict(ls="-", label="90th")}
DUR_STYLE = {2: dict(marker="o", ms=6.5), 3: dict(marker="s", ms=6),
             5: dict(marker="D", ms=5.5)}
CMAP_SEQUENTIAL = "YlOrBr"       # magnitude: one hue, light to dark
CMAP_DIVERGING = "RdBu_r"        # polarity: two hues, neutral midpoint
COLOR_GRID = "#dddddd"
COLOR_INK = "#222222"
COLOR_INK_SOFT = "#666666"
COLOR_WARN = "#8a4b08"

# =============================================================================
# EXTERNAL BENCHMARK
# =============================================================================
# The only second temperature product in this repository is the national
# heatWaveUS county-day table (data/raw/noaa/county_day_{tmax,tmin}.csv), built
# from the SAME GHCN-Daily station observations but with a DIFFERENT
# station-to-county assignment (nearest station, national pipeline) than the
# Gulf-states pull used here (point-in-polygon, station mean). It is therefore a
# METHOD benchmark, not an independent observing system, and it covers 2015-2024
# only. Both limitations are stated wherever it is used. A genuinely independent
# spatially consistent product (nClimGrid-Daily, PRISM, Daymet temperature) is
# NOT present in this repository and would have to be downloaded.
BENCHMARK_TMAX = os.path.join(REPO_ROOT, "..", "data", "raw", "noaa",
                              "county_day_tmax.csv")
BENCHMARK_TMIN = os.path.join(REPO_ROOT, "..", "data", "raw", "noaa",
                              "county_day_tmin.csv")
BENCHMARK_NAME = "heatWaveUS national GHCN county-day (nearest-station assignment)"
BENCHMARK_YEARS = (2015, 2024)
BENCHMARK_INDEPENDENCE = ("shares the GHCN-Daily station observations; differs in "
                          "station-to-county assignment and county aggregation")


# =============================================================================
# TERMINOLOGY ENFORCEMENT
# =============================================================================
# Reader-facing prose must not use the retired vocabulary. A match is allowed
# only where the surrounding text makes clear it is being quoted, negated, or
# attributed to the previous package - or, for "county-day", where it names an
# artefact ("the GHCN county-day table") rather than a unit of analysis.
RETIRED_VOCABULARY = [
    (r"\bheatwave day", "'heatwave day' for a year-round relative construct"),
    (r"\bTGm\b", "TGm as if a standard symbol"),
    (r"NWS (advisory )?threshold", "80/90 degF called an NWS threshold"),
    (r"\bbalanced panel\b", "'balanced panel' for the old at-least-one-year rule"),
    (r"warming rate", "'warming rate' without a fitted trend model"),
    (r"county-day\b", "'county-day' as a unit of analysis in reader-facing text"),
]
TERMINOLOGY_GUARDS = (
    "previous package", "current package", "current rule", "retired", "never",
    "not a", "is not", "must not", "no longer", "rather than", "instead of",
    "the old", "was called", "would have", "do not", "does not", "banned",
    "replaced", "not balanced", "not support", "not supported", "mis-named",
    "misnamed", "defect", "withdrawn", "asserted", "claimed", "renamed",
    "corrects the", "removes", "recomputed",
)
# "county-day" is acceptable when it names a file, table or panel
ARTEFACT_CONTEXTS = ("county-day table", "county-day records", "county-day file",
                     "county-by-day panel", "county-day temperature",
                     "county_day", "county-day pull")


def _inside_quotes(txt, lo, hi):
    """Is txt[lo:hi] inside a quoted span on its own line?

    Quoting a forbidden phrase in order to forbid it - as the claims-not-supported
    list does - is not a use of the phrase.
    """
    ls = txt.rfind("\n", 0, lo) + 1
    le = txt.find("\n", hi)
    line = txt[ls:le if le != -1 else len(txt)]
    a, b = lo - ls, hi - ls
    for q in ('"', "'", "“”"):
        opens = [i for i, ch in enumerate(line) if ch in q]
        for i in range(0, len(opens) - 1, 2):
            if opens[i] < a and b <= opens[i + 1]:
                return True
    return False


def terminology_violations(paths):
    """Unguarded uses of the retired vocabulary. Returns a list of tuples."""
    import re
    hits = []
    for path in paths:
        if not os.path.exists(path):
            continue
        txt = open(path, encoding="utf-8").read()
        for pat, why in RETIRED_VOCABULARY:
            for m in re.finditer(pat, txt, flags=re.I):
                ctx = txt[max(0, m.start() - 90):m.end() + 90].replace("\n", " ")
                low = ctx.lower()
                if any(k in low for k in TERMINOLOGY_GUARDS):
                    continue
                if "county-day" in pat and any(a in low for a in ARTEFACT_CONTEXTS):
                    continue
                if _inside_quotes(txt, m.start(), m.end()):
                    continue    # a quoted claim is a quotation, not an assertion
                hits.append((os.path.basename(path), why, ctx.strip()[:130]))
    return hits


def md_table(df, cols=None, max_rows=None, floatfmt="%.2f"):
    """Markdown table writer (no `tabulate` in this environment)."""
    import math
    d = df if cols is None else df[cols]
    truncated = 0
    if max_rows is not None and len(d) > max_rows:
        truncated = len(d) - max_rows
        d = d.head(max_rows)

    def cell(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return ""
        if isinstance(v, float):
            v = floatfmt % v
        return str(v).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(str(c) for c in d.columns) + " |",
             "|" + "|".join(["---"] * len(d.columns)) + "|"]
    for _, r in d.iterrows():
        lines.append("| " + " | ".join(cell(v) for v in r.tolist()) + " |")
    if truncated:
        lines += ["", "_...%d further row(s) omitted; see the CSV._" % truncated]
    return "\n".join(lines)


def resolved_configuration():
    """Every prespecified choice, as a table, written to config/ at run time."""
    rows = [
        ("study_period_part1", YEARS_LABEL, "Part 1 years; 2026 excluded (partial)"),
        ("analysis_years_part2_3", ANALYSIS_YEARS_LABEL, "classification years"),
        ("states_part1", ",".join(STATES), "Gulf states described in Part 1"),
        ("state_part2_3", TEST_STATE, "only state with a built county-day table"),
        ("min_days_per_county_year", MIN_DAYS_PER_COUNTY_YEAR,
         "valid daily observations required for an annual county-level observation"),
        ("min_days_per_county_month", MIN_DAYS_PER_COUNTY_MONTH,
         "valid daily observations required for a monthly county-level summary"),
        ("periods", " | ".join(PERIOD_ORDER), "comparison periods"),
        ("recent_period_length_years", period_length(PERIODS[-1]),
         "2020-2025 is a six-year recent period, not a decade"),
        ("sample_A_rule", "; ".join("%s>=%d yr" % (PERIOD_LABEL[k], v)
                                    for k, v in SAMPLE_A_MIN_YEARS.items()),
         "Sample A: minimum qualifying annual observations per period"),
        ("sample_B_years_per_period", SAMPLE_B_YEARS_PER_PERIOD,
         "Sample B: identical number of annual observations in every period"),
        ("sample_B_selection_rule", SAMPLE_B_SELECTION_RULE, "deterministic, no randomness"),
        ("county_period_statistic", COUNTY_PERIOD_STAT,
         "annual county-level observations -> one value per county per period"),
        ("state_period_statistic", STATE_PERIOD_STAT,
         "across counties, each county contributing exactly one value"),
        ("bootstrap_resamples", BOOTSTRAP_N, "resampling unit: %s" % BOOTSTRAP_UNIT),
        ("bootstrap_interval", "%.1f-%.1f pct" % BOOTSTRAP_CI, "percentile interval"),
        ("bootstrap_seed", BOOTSTRAP_SEED, "fixed seed; bit-reproducible"),
        ("percentiles", ",".join(str(p) for p in PERCENTILES), "relative thresholds"),
        ("durations_days", ",".join(str(d) for d in DURATIONS), "minimum run lengths"),
        ("threshold_windows", ",".join(WINDOWS), "baseline pooling windows"),
        ("primary_window", PRIMARY_WINDOW, WINDOW_READER[PRIMARY_WINDOW]),
        ("absolute_gates_f", ",".join("%d" % g for g in ABSOLUTE_GATES_F),
         "absolute daily-high gates; NOT National Weather Service thresholds"),
        ("warm_season_months", ",".join(str(m) for m in WARM_SEASON),
         WARM_SEASON_PHRASE),
        ("shoulder_season_months", ",".join(str(m) for m in SHOULDER_SEASON),
         SEASON_LABEL["shoulder"]),
        ("cool_season_months", ",".join(str(m) for m in COOL_SEASON),
         SEASON_LABEL["cool"]),
        ("long_event_audit_days", LONG_EVENT_DAYS, "every longer event is audited"),
        ("long_event_strict_days", LONG_EVENT_DAYS_STRICT, "reported separately"),
        ("relative_comparison_operator", C.COMPARISON_OP,
         "daily high strictly above the historical percentile"),
        ("hybrid_gate_operator", ">=", "as implemented in the pipeline; > is tested"),
        ("absolute_comparison_operator", ">", "'above 90 degF'"),
        ("baseline_scheme", C.BASELINE_SCHEME, "year Y judged on 1979..Y-1"),
        ("anchor_min_observed_share", ANCHOR_MIN_OBSERVED_SHARE,
         "anchor-station subset definition"),
        ("plausible_tmax_f", "%s" % (PLAUSIBLE_TMAX_F,), "flag only, never edit"),
        ("plausible_tmin_f", "%s" % (PLAUSIBLE_TMIN_F,), "flag only, never edit"),
        ("benchmark_product", BENCHMARK_NAME, BENCHMARK_INDEPENDENCE),
        ("benchmark_years", "%d-%d" % BENCHMARK_YEARS, "benchmark coverage"),
    ]
    import pandas as pd
    return pd.DataFrame(rows, columns=["setting", "value", "note"])
