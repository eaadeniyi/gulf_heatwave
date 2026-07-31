"""
=============================================================================
EXTREME-TEMPERATURE TESTS  --  configuration and prespecified choices.
=============================================================================
Three pieces of work, deliberately kept in their own package so the delivered
16-definition comparison in outputs/definition_comparison/ is not perturbed:

  PART 1  Gulf-state temperature description (TX, LA, MS, AL, FL) over the
          whole available record: by year, by state, by decade, by month.
  PART 2  county-relative daily MAXIMUM temperature at the 80th / 85th / 90th
          percentile x >= 2 / >= 3 / >= 5 consecutive days  (9 definitions).
  PART 3  absolute floors at 80 degF and 90 degF, tested BOTH ways:
            (a) as a GATE on the relative rule  (percentile AND Tmax >= floor)
            (b) as an ABSOLUTE-ONLY definition  (Tmax >= floor, no percentile)
          (a) answers "does a floor remove the cool-season loading?", which is
          this project's top open methodological decision. (b) answers "what
          does the floor alone select?", which is the hazard-style construct
          the relative definitions are usually contrasted against. They are
          different questions, so both are run rather than one being guessed.

-----------------------------------------------------------------------------
WHAT IS REUSED, AND WHY NOTHING IN THE PIPELINE IS EDITED
-----------------------------------------------------------------------------
The classification here calls the pipeline's own functions -- p02's threshold
builder and reporting tables, and heatwave_run_logic's run/event logic -- so
these results sit on exactly the code path that is defended by tests/ and that
produced the published definitions. Two capabilities the pipeline does not
currently expose from config are added HERE rather than there: a per-definition
absolute floor, and an absolute-only (percentile-free) rule. Both are thin
wrappers around the same candidate-day and persistence logic.

Overlapping cells are a free check: TMAX_P85_2D, TMAX_P85_3D, TMAX_P90_2D and
TMAX_P90_3D already exist in the definition grid, so e02 reconciles its rebuild
of those four against the published run summaries and fails loudly on any
difference.

-----------------------------------------------------------------------------
PART 1 DATA CHOICE (stated because it is a judgement call)
-----------------------------------------------------------------------------
Part 1 reads the RAW GHCN county-day files, not the IDW gap-filled county-day
table. Reasons:
  * the question is what the temperature record IS over its available duration,
    so gap-filled values would describe the interpolation, not the observations;
  * only TX has a built county-day table -- the other four would have to be
    generated, and the IDW field for a county with no station is a neighbour
    average, which must not enter a description of that county's climate.
The cost is that coverage varies over time and between states, so Part 1
carries an explicit coverage gate and a BALANCED county panel for anything
comparing periods. Those two controls are the difference between a temperature
trend and a station-network trend.
=============================================================================
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_ROOT = os.path.abspath(os.path.join(HERE, ".."))
REPO_ROOT = os.path.abspath(os.path.join(PKG_ROOT, "..", ".."))
PIPELINE_DIR = os.path.join(REPO_ROOT, "pipeline")
sys.path.insert(0, PIPELINE_DIR)
import config as C                                        # noqa: E402

DIR_FIG = os.path.join(PKG_ROOT, "figures")
DIR_TABLES = os.path.join(PKG_ROOT, "tables")
DIR_QA = os.path.join(PKG_ROOT, "qa")
ALL_DIRS = [DIR_FIG, DIR_TABLES, DIR_QA]


def ensure_dirs():
    for d in ALL_DIRS:
        os.makedirs(d, exist_ok=True)


# =============================================================================
# PART 1  --  the Gulf-state temperature description
# =============================================================================
STATES = ["TX", "LA", "MS", "AL", "FL"]
STATE_LABEL = {"TX": "Texas", "LA": "Louisiana", "MS": "Mississippi",
               "AL": "Alabama", "FL": "Florida"}

EDA_YEARS = (1979, 2025)
#   The GHCN pull runs 1979-01-01 to 2026-07-05, so 2026 is a partial year and
#   is EXCLUDED from every annual, decadal and monthly summary: a year ending in
#   July is warm-biased in a monthly mix and cold-biased in an annual mean, and
#   either way it is not comparable with a full year. 1979-2025 = 47 full years.

MIN_DAYS_PER_COUNTY_YEAR = 328
#   A county-year enters the annual summaries only with at least this many valid
#   daily observations (~90% of 365). Without a coverage gate, a county that
#   reported only in July would read as an unusually hot county.

MIN_DAYS_PER_COUNTY_MONTH = 25
#   The equivalent gate for the monthly summaries (~83% of a 30-day month).

DECADES = [(1980, 1989), (1990, 1999), (2000, 2009), (2010, 2019), (2020, 2025)]
DECADE_LABEL = {(1980, 1989): "1980s", (1990, 1999): "1990s", (2000, 2009): "2000s",
                (2010, 2019): "2010s", (2020, 2025): "2020-2025*"}
#   1979 sits alone before the first full decade and is therefore shown in the
#   annual series but excluded from the decadal comparison. 2020-2025 is six
#   years, not ten, and is marked with an asterisk everywhere it appears.
PARTIAL_DECADES = {(2020, 2025)}

BALANCED_PANEL = True
#   Decadal comparisons use only counties that clear the coverage gate in EVERY
#   decade, because the reporting network shrinks over time (in the 2020s Texas
#   drops from 236 to 218 reporting counties, Mississippi 69 to 53, Louisiana
#   52 to 44). An unbalanced comparison would confound a temperature change with
#   a change in which counties are being averaged. The unbalanced version is
#   computed too and reported beside it, so the size of that confounding is
#   visible rather than assumed away.

TEMP_VARS = [("tmax_f", "daily maximum temperature", "Tmax"),
             ("tmin_f", "daily minimum temperature", "Tmin"),
             ("tmean_f", "daily mean temperature ((Tmax+Tmin)/2)", "Tmean")]


# =============================================================================
# PART 2  --  county-relative daily-maximum-temperature definitions
# =============================================================================
TEST_STATE = "TX"
#   Parts 2 and 3 run on the pilot state, where the classification pipeline,
#   its baselines and its QA record already exist. Every definition here is
#   state-agnostic and runs for another state once that state's county-day table
#   is built (pipeline/p01_build_countyday_idw.py).

EXTREME_METRIC = "tmax"
EXTREME_PERCENTILES = [80, 85, 90]
EXTREME_DURATIONS = [2, 3, 5]
EXTREME_WINDOWS = ["w05", "w15", "month", "month_pm7"]
PRIMARY_WINDOW = "w15"
#   All four threshold windows are run so these nine definitions are directly
#   comparable with the existing 64-run grid; w15 is the reporting window, as in
#   every earlier round.

# =============================================================================
# PART 3  --  absolute floors
# =============================================================================
FLOORS_F = [80.0, 90.0]
FLOOR_METRIC = "tmax"          # "daily temperature" = daily maximum temperature
FLOOR_MODE_GATE = "relative_and_floor"
FLOOR_MODE_ABSOLUTE = "absolute_only"

FLOOR_GATE_WINDOWS = [PRIMARY_WINDOW]
#   The floored variants are run at the primary window only: the floor is
#   crossed with 9 definitions x 2 floors already, and the window axis was shown
#   to be the least consequential of the four (median Jaccard 0.687 in the
#   definition-comparison package).

FLOOR_ABSOLUTE_DURATIONS = EXTREME_DURATIONS
#   An absolute rule has no baseline, so it has NO window axis at all -- one run
#   per floor x duration, and that is a property of the construct, not a
#   shortcut.


def definition_id(percentile=None, min_duration=2, floor_f=None, absolute_only=False):
    """Definition ids that stay parseable and never collide.

        TMAX_P80_2D            relative only
        TMAX_P80_2D_F80        relative AND Tmax >= 80 degF
        TMAX_ABS90_2D          Tmax >= 90 degF, no percentile
    """
    code = C.METRICS[EXTREME_METRIC]["code"]
    if absolute_only:
        return "%s_ABS%d_%dD" % (code, int(floor_f), min_duration)
    base = "%s_P%d_%dD" % (code, percentile, min_duration)
    return base if floor_f is None else "%s_F%d" % (base, int(floor_f))


def definitions():
    """Every definition this package classifies, in reporting order."""
    out = []
    n = 0
    for p in EXTREME_PERCENTILES:                      # PART 2: relative, no floor
        for d in EXTREME_DURATIONS:
            n += 1
            out.append(dict(seq=n, part=2, kind="relative",
                            definition_id=definition_id(p, d),
                            percentile=p, min_duration=d, floor_f=None,
                            absolute_only=False, windows=list(EXTREME_WINDOWS)))
    for f in FLOORS_F:                                 # PART 3a: relative AND floor
        for p in EXTREME_PERCENTILES:
            for d in EXTREME_DURATIONS:
                n += 1
                out.append(dict(seq=n, part=3, kind=FLOOR_MODE_GATE,
                                definition_id=definition_id(p, d, floor_f=f),
                                percentile=p, min_duration=d, floor_f=f,
                                absolute_only=False, windows=list(FLOOR_GATE_WINDOWS)))
    for f in FLOORS_F:                                 # PART 3b: absolute only
        for d in FLOOR_ABSOLUTE_DURATIONS:
            n += 1
            out.append(dict(seq=n, part=3, kind=FLOOR_MODE_ABSOLUTE,
                            definition_id=definition_id(None, d, floor_f=f,
                                                        absolute_only=True),
                            percentile=None, min_duration=d, floor_f=f,
                            absolute_only=True, windows=["none"]))
    return out


def runs():
    """definition x window, flattened. An absolute-only definition has one run."""
    out = []
    for d in definitions():
        for w in d["windows"]:
            out.append(dict(d, window=w, run_id="%s__%s" % (d["definition_id"], w)))
    return out


# definitions that ALREADY exist in the delivered grid, so the rebuild can be
# reconciled against the published run summaries rather than merely trusted
OVERLAP_WITH_GRID = ["TMAX_P85_2D", "TMAX_P85_3D", "TMAX_P90_2D", "TMAX_P90_3D"]

# =============================================================================
# VISUAL ENCODING
# =============================================================================
# Metric colours are the project's established ones (Tmax red). The new axes need
# their own encodings, chosen so nothing collides with metric identity:
STATE_STYLE = {                     # part 1: state = colour + marker, 5 categories
    "TX": dict(color="#C44E52", marker="^", label="Texas"),
    "LA": dict(color="#4C72B0", marker="o", label="Louisiana"),
    "MS": dict(color="#55A868", marker="s", label="Mississippi"),
    "AL": dict(color="#8172B2", marker="D", label="Alabama"),
    "FL": dict(color="#CCB974", marker="v", label="Florida"),
}
PCTL_STYLE = {80: dict(ls=":", label="80th"), 85: dict(ls="--", label="85th"),
              90: dict(ls="-", label="90th")}
DUR_STYLE = {2: dict(marker="o", ms=7, label=">=2 days"),
             3: dict(marker="s", ms=6.5, label=">=3 days"),
             5: dict(marker="D", ms=6, label=">=5 days")}
FLOOR_STYLE = {None: dict(color="#C44E52", hatch=None, label="no floor"),
               80.0: dict(color="#DD8452", hatch="//", label="floor 80 degF"),
               90.0: dict(color="#8a4b08", hatch="xx", label="floor 90 degF")}

CMAP_SEQUENTIAL = "Blues"
CMAP_DIVERGING = "PuOr"          # signed decadal changes: two hues, neutral middle
COLOR_GRID = "#dddddd"
COLOR_INK = "#222222"
COLOR_INK_SOFT = "#666666"
COLOR_WARN = "#8a4b08"
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
JUN_SEP = [6, 7, 8, 9]


def log(*a):
    print(*a, flush=True)


def md_table(df, cols=None, max_rows=None):
    """Local markdown-table writer (no `tabulate` in this environment)."""
    d = df if cols is None else df[cols]
    truncated = 0
    if max_rows is not None and len(d) > max_rows:
        truncated = len(d) - max_rows
        d = d.head(max_rows)

    def cell(v):
        import math
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return ""
        return str(v).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(str(c) for c in d.columns) + " |",
             "|" + "|".join(["---"] * len(d.columns)) + "|"]
    for _, r in d.iterrows():
        lines.append("| " + " | ".join(cell(v) for v in r.tolist()) + " |")
    if truncated:
        lines += ["", "_...%d further row(s) omitted; see the CSV._" % truncated]
    return "\n".join(lines)
