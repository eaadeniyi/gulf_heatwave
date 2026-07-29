"""
=============================================================================
CONFIGURATION  --  the ONE place to change to run the heatwave pipeline for a
                   different state, metric, percentile, duration or window.
=============================================================================

This pipeline classifies "heatwave days" and "heatwave events" for the counties
of a US state, using a COUNTY-RELATIVE percentile of a daily heat metric plus a
consecutive-day persistence rule, on a walk-forward (expanding) climate
baseline. It was first developed for Texas but is deliberately NOT locked to
Texas -- everything state-specific is a parameter below.

------------------------------------------------------------------------------
TWO WAYS TO RUN
------------------------------------------------------------------------------
(A) THE DEFINITION GRID (the current round of work).  GRID_DEFINITIONS below
    lists every definition under test; each is crossed with every window in
    GRID_WINDOWS to give the RUN list (see grid_runs()). Execute with:

        python run_grid.py

(B) THE LEGACY SINGLE-DEFINITION PATH (how Definition 01 / 02 were produced).
    Set STATES + PERCENTILES + MIN_DURATION and run:

        python run_all.py

    This path is retained so the published Def 01 / Def 02 outputs in
    outputs/TX/def_p85_2d and def_p95_2d stay exactly reproducible. It is a
    special case of the grid code (metric "mhi", windows w15 + month).

------------------------------------------------------------------------------
HOW TO RUN IT FOR A NEW STATE
------------------------------------------------------------------------------
1. Make sure the state's daily weather inputs exist in the layout described in
   WEATHER_FILE_TEMPLATE below (GHCN county-day temperature + gridMET county-day
   humidity). In THIS project those exist only for the 5 Gulf states
   (TX, LA, MS, AL, FL) under data/raw/gulf_states/<ST>/weather/. Any other
   state needs its inputs downloaded into the same layout first.
2. Set STATES to the state abbreviation(s) you want, e.g. STATES = ["LA"].
3. (Optional, for the NWS-proxy step) add a per-state office table named
   nws_offices_<ST>.csv next to this file. Without it, the NWS-proxy step is
   skipped for that state (the relative-definition steps still run).
4. Run:  python run_grid.py     (the definition grid)
      or python run_all.py      (the legacy single-definition path)

------------------------------------------------------------------------------
WHAT A "DEFINITION" AND A "RUN" ARE
------------------------------------------------------------------------------
    definition = METRIC x PERCENTILE x MIN_DURATION
                 e.g. TMAX_P90_2D = county-relative daily maximum temperature
                 above its own 90th percentile, >= 2 consecutive days.
    run        = definition x THRESHOLD WINDOW
                 e.g. TMAX_P90_2D__w15

Every definition uses: county-relative percentile, strict ">" comparison, the
WALK-FORWARD baseline (year Y is judged against 1979..Y-1), year-round season,
and no absolute floor. Those are held FIXED across the grid on purpose, so that
any difference between two runs is attributable to metric, percentile, duration
or window -- and nothing else.
=============================================================================
"""
import os

# =============================================================================
# SECTION 1  --  STATE, STUDY PERIOD, BASELINE   (shared by both run paths)
# =============================================================================
STATES = ["TX"]                 # e.g. ["TX"], ["LA", "MS"], ...

ANALYSIS_YEARS = (2015, 2025)   # inclusive; the years we classify heatwaves in
BASELINE_START = 1979           # walk-forward baseline pools years BASELINE_START..(Y-1)

# --- quality-control --------------------------------------------------------
MIN_REF_OBS = 20                # threshold flagged 'low_n_ref' below this many baseline obs

# --- IDW gap-filling of missing daily temperature ---------------------------
#     Missing county-days are filled by inverse-distance weighting from other
#     counties that have data that day, using county CENTROID distances.
IDW_POWER = 2                   # weight = 1 / distance^IDW_POWER


# =============================================================================
# SECTION 2  --  THE DAILY HEAT METRICS AVAILABLE
# =============================================================================
# Every one of these columns already exists in outputs/<ST>/county_daily_heat.csv
# (built by p01), so switching metric needs NO re-run of p01 and guarantees all
# definitions see exactly the same underlying weather data.
#
#   tmax : daily maximum temperature                      (dry-bulb)
#   tmin : daily minimum temperature                      (dry-bulb; "warm nights")
#   mhi  : daily-MEAN heat-index proxy = heat_index(Tmean, mean RH), where
#          Tmean = (Tmax+Tmin)/2 and mean RH = (RHmax+RHmin)/2. A DAILY PROXY,
#          not an hourly heat index. This is the metric of Definitions 01/02.
#
# 'rh_dependent' drives artifact handling: the confirmed 2023-03-01 gridMET
# RH-clip artifact inflates the HEAT INDEX but leaves Tmax/Tmin untouched, so
# those county-days are set to missing only for rh_dependent metrics.
METRICS = {
    "tmax": {"col": "tmax_f", "code": "TMAX", "short": "Tmax",
             "label": "daily maximum temperature", "unit": "degF", "rh_dependent": False},
    "tmin": {"col": "tmin_f", "code": "TMIN", "short": "Tmin",
             "label": "daily minimum temperature", "unit": "degF", "rh_dependent": False},
    "mhi":  {"col": "derived_tmean_meanrh_hi_f", "code": "MHI", "short": "mean HI",
             "label": "daily-mean heat index", "unit": "degF", "rh_dependent": True},
}

# A daily-MAX heat-index proxy = heat_index(Tmax, RHmin) also exists in the
# county-day table as derived_tmax_rhmin_hi_proxy_f. It is NOT part of this grid;
# it feeds the NWS advisory-threshold proxy step (p03) only.


# =============================================================================
# SECTION 3  --  THRESHOLD WINDOWS
# =============================================================================
# A window defines HOW baseline days are POOLED to estimate the county's
# percentile threshold for a given target date. Three shapes:
#
#   centered     : target day +/- 'half' days             -> threshold per day-of-year
#   month        : all days in the same calendar month     -> threshold per month
#   month_collar : the calendar month EXTENDED by 'collar' days on each side
#                  -> threshold per month, pooled over a wider slice of calendar
#
# 'month_collar' with collar=7 is "calendar month threshold +/- 7 days": for a
# July target date the baseline pool runs 24 Jun -- 7 Aug (~45 days), i.e. all of
# July plus a 7-day collar either side. It is deliberately DISTINCT from w15
# (which pools only the 15 days centred on the target date itself).
GRID_WINDOWS = {
    "w05":       {"type": "centered", "half": 2, "order": 1,
                  "label": "centered 5-day window (+/-2 days)"},
    "w15":       {"type": "centered", "half": 7, "order": 2,
                  "label": "centered 15-day window (+/-7 days)"},
    "month":     {"type": "month", "order": 3,
                  "label": "calendar-month bucket"},
    "month_pm7": {"type": "month_collar", "collar": 7, "order": 4,
                  "label": "calendar month +/- 7 days"},
}

# Window keys w15 and month are intentionally the SAME names used by the
# published Def 01 / Def 02 outputs, so window labels stay comparable across
# every document and deck already written.


# =============================================================================
# SECTION 4  --  THE DEFINITION GRID  (the current round of work)
# =============================================================================
# def_number continues the project's existing definition series:
#     Def 01 = MHI_P85_2D  (published: outputs/TX/def_p85_2d)
#     Def 02 = MHI_P95_2D  (published: outputs/TX/def_p95_2d)
# 'user_item' is the item number in the request that specified this round, kept
# so the results can be read straight back against that list.
#
# Held FIXED across every definition: walk-forward baseline 1979..Y-1, strict ">",
# year-round season, no absolute floor, county-relative percentile.
GRID_DEFINITIONS = [
    # -- 2 consecutive days -------------------------------------------------
    {"def_number":  3, "user_item":  1, "metric": "tmax", "percentile": 90, "min_duration": 2},
    {"def_number":  4, "user_item":  2, "metric": "tmin", "percentile": 90, "min_duration": 2},
    {"def_number":  5, "user_item":  3, "metric": "tmax", "percentile": 85, "min_duration": 2},
    {"def_number":  6, "user_item":  4, "metric": "tmin", "percentile": 85, "min_duration": 2},
    {"def_number":  7, "user_item":  5, "metric": "tmax", "percentile": 95, "min_duration": 2},
    {"def_number":  8, "user_item":  6, "metric": "tmin", "percentile": 95, "min_duration": 2},
    {"def_number":  9, "user_item":  7, "metric": "mhi",  "percentile": 90, "min_duration": 2},
    # -- 3 consecutive days -------------------------------------------------
    {"def_number": 10, "user_item":  8, "metric": "tmax", "percentile": 90, "min_duration": 3},
    {"def_number": 11, "user_item":  9, "metric": "tmin", "percentile": 90, "min_duration": 3},
    {"def_number": 12, "user_item": 10, "metric": "tmax", "percentile": 85, "min_duration": 3},
    {"def_number": 13, "user_item": 11, "metric": "tmin", "percentile": 85, "min_duration": 3},
    {"def_number": 14, "user_item": 12, "metric": "tmax", "percentile": 95, "min_duration": 3},
    {"def_number": 15, "user_item": 13, "metric": "tmin", "percentile": 95, "min_duration": 3},
    {"def_number": 16, "user_item": 14, "metric": "mhi",  "percentile": 90, "min_duration": 3},
]

# Already-published definitions, listed so the comparison layer can pull them in
# as extra cells where a like-for-like window exists (no re-run needed).
LEGACY_DEFINITIONS = [
    {"def_number": 1, "definition_id": "MHI_P85_2D", "metric": "mhi", "percentile": 85,
     "min_duration": 2, "windows": ["w15", "month"], "output_dir_name": "def_p85_2d"},
    {"def_number": 2, "definition_id": "MHI_P95_2D", "metric": "mhi", "percentile": 95,
     "min_duration": 2, "windows": ["w15", "month"], "output_dir_name": "def_p95_2d"},
]

# --- fixed methodological choices, recorded explicitly for the registry ------
COMPARISON_OP = ">"                     # candidate day = metric STRICTLY above threshold
BASELINE_SCHEME = "walk_forward_1979_to_Yminus1"
SEASON = "year_round"
GRID_FLOOR_F = None                     # no absolute floor anywhere in the grid


# =============================================================================
# SECTION 5  --  LEGACY SINGLE-DEFINITION PATH (Def 01 / Def 02 reproducibility)
# =============================================================================
# Used only by run_all.py / the p02 and p04 back-compat wrappers.
PERCENTILES = [95]               # 85 -> Def 01 ; 95 -> Def 02
MIN_DURATION = 2                 # a heatwave EVENT is a run of >= this many days
METRIC = "mean"                  # legacy label for the daily-MEAN heat index
LEGACY_METRIC_KEY = "mhi"        # the METRICS key it corresponds to
LEGACY_WINDOWS = ["w15", "month"]

# --- absolute floor on the legacy PRIMARY definition ------------------------
#     None  = no floor (a purely relative "anomalous-for-this-date" definition;
#             this is the definition as specified). A floor value (e.g. 80) would
#             additionally require the heat index to reach that many degrees F.
PRIMARY_FLOOR_F = None
FLOOR_SENSITIVITY_F = 80.0       # floor used only for the reported sensitivity scenario

# Back-compat alias: older code referred to config.WINDOWS as a {key: spec} dict.
WINDOWS = GRID_WINDOWS


# =============================================================================
# SECTION 6  --  PATHS  (templated so nothing is hardcoded to one state)
# =============================================================================
# Repo layout: this file lives in <heatWaveUS>/texas_heatwave_pilot/pipeline/ ,
# so the project root (which contains data/, gulf_eda/) is 2 levels up.
_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

# {ST} is replaced with the state abbreviation at run time.
WEATHER_DIR_TEMPLATE = os.path.join(PROJECT_ROOT, "data", "raw", "gulf_states", "{ST}", "weather")
GHCN_FILE_TEMPLATE = "ghcn_county_day_weather_{ST}.csv"      # temperature (Tmax/Tmin/PRCP)
GRIDMET_FILE_TEMPLATE = "gridmet_county_day_humidity_{ST}.csv"  # humidity (RHmax/RHmin)

# US county polygons (used for centroids + choropleth maps). Any state works:
# we filter by the state's 2-digit FIPS code (STATE_FIPS below).
COUNTY_SHAPEFILE = os.path.join(PROJECT_ROOT, "data", "raw", "census",
                                "county_shapefile", "tl_2020_us_county.shp")

# All outputs go here, organized per state and per definition.
OUTPUT_ROOT = os.path.abspath(os.path.join(_HERE, "..", "outputs"))

# Path to this pipeline dir (for locating per-state NWS office tables etc.)
PIPELINE_DIR = _HERE

# Where the definition-grid outputs live, under the per-state output dir.
GRID_DIR_NAME = "grid"              # outputs/<ST>/grid/<DEFINITION_ID>/
THRESHOLD_CACHE_DIR_NAME = "_thresholds"   # shared: thresholds depend on metric
                                           # x percentile x window only, NOT duration
COMPARISON_DIR_NAME = "_comparison"        # cross-definition master tables + figures
STATE_FIGURE_DIR_NAME = "_state_figures"   # definition-independent figures (rendered once)
REGISTRY_FILE = os.path.join(_HERE, "definition_registry.csv")

# --- Heat-index helper is bundled in this pipeline (pipeline/heat_index.py) --


# =============================================================================
# SECTION 7  --  US STATE ABBREVIATION -> 2-DIGIT FIPS
# =============================================================================
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15",
    "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56",
}
STATE_NAME = {
    "AL": "Alabama", "FL": "Florida", "LA": "Louisiana", "MS": "Mississippi",
    "TX": "Texas",  # (only the Gulf-state names needed here; extend as required)
}

# --- Equal-area CRS for centroid distances + maps (CONUS Albers) ------------
EQUAL_AREA_CRS = 5070


# =============================================================================
# SECTION 8  --  helpers so every step resolves paths/IDs the same way
# =============================================================================
def weather_dir(state):
    return WEATHER_DIR_TEMPLATE.format(ST=state)


def ghcn_path(state):
    return os.path.join(weather_dir(state), GHCN_FILE_TEMPLATE.format(ST=state))


def gridmet_path(state):
    return os.path.join(weather_dir(state), GRIDMET_FILE_TEMPLATE.format(ST=state))


def state_output_dir(state):
    """Per-state outputs (county-day table, coverage, NWS proxy)."""
    d = os.path.join(OUTPUT_ROOT, state)
    os.makedirs(d, exist_ok=True)
    return d


def county_day_path(state):
    """The per-county daily table built by p01 -- input to every definition."""
    return os.path.join(state_output_dir(state), "county_daily_heat.csv")


# ---------------------------------------------------------------- grid naming
def definition_code(metric, percentile, min_duration):
    """Canonical definition id, e.g. 'TMAX_P90_2D'. Machine-parseable + readable."""
    return "%s_P%d_%dD" % (METRICS[metric]["code"], percentile, min_duration)


def run_code(metric, percentile, min_duration, window_key):
    """Canonical run id = definition + window, e.g. 'TMAX_P90_2D__w15'."""
    return "%s__%s" % (definition_code(metric, percentile, min_duration), window_key)


def definition_sentence(metric, percentile, min_duration, window_key=None):
    """The definition written out in the project's reporting language."""
    m = METRICS[metric]
    s = ("county-relative %s above its own %dth percentile, sustained >= %d consecutive days, "
         "walk-forward baseline %d..Y-1" % (m["label"], percentile, min_duration, BASELINE_START))
    if window_key:
        s += "; threshold window: %s" % GRID_WINDOWS[window_key]["label"]
    return s


def grid_root(state):
    d = os.path.join(OUTPUT_ROOT, state, GRID_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def grid_definition_dir(state, definition_id, make=True):
    """Per-state, per-definition grid outputs (tables/ + figures/)."""
    d = os.path.join(grid_root(state), definition_id)
    if make:
        os.makedirs(os.path.join(d, "tables"), exist_ok=True)
        os.makedirs(os.path.join(d, "figures"), exist_ok=True)
    return d


def threshold_cache_dir(state):
    d = os.path.join(grid_root(state), THRESHOLD_CACHE_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def threshold_cache_path(state, metric, percentile, window_key):
    """Thresholds are shared by the 2-day and 3-day definitions of the same
    metric/percentile/window, so they are stored once here (gzipped: the
    centered windows are ~1M rows)."""
    return os.path.join(threshold_cache_dir(state),
                        "thresholds_%s_P%d_%s.csv.gz" % (METRICS[metric]["code"], percentile, window_key))


def comparison_dir(state, make=True):
    d = os.path.join(grid_root(state), COMPARISON_DIR_NAME)
    if make:
        os.makedirs(os.path.join(d, "figures"), exist_ok=True)
        os.makedirs(os.path.join(d, "tables"), exist_ok=True)
    return d


def state_figure_dir(state):
    """Definition-INDEPENDENT figures (IDW coverage, NWS proxy): identical for
    every definition, so rendered once here and copied into each run folder."""
    d = os.path.join(grid_root(state), STATE_FIGURE_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def grid_definitions_expanded():
    """The 14 grid definitions with their derived ids/labels filled in."""
    out = []
    for d in GRID_DEFINITIONS:
        m = METRICS[d["metric"]]
        out.append(dict(d,
                        definition_id=definition_code(d["metric"], d["percentile"], d["min_duration"]),
                        metric_col=m["col"], metric_code=m["code"], metric_label=m["label"],
                        metric_short=m["short"],
                        artifact_handling=("rh_clip_2023_03_01_set_missing" if m["rh_dependent"]
                                           else "not_applicable_metric_independent_of_rh")))
    return out


def grid_runs():
    """The full RUN list = definitions x windows, in a stable reporting order.
    This is what run_grid.py iterates and what definition_registry.csv records."""
    runs = []
    for d in grid_definitions_expanded():
        for wkey in sorted(GRID_WINDOWS, key=lambda k: GRID_WINDOWS[k]["order"]):
            w = GRID_WINDOWS[wkey]
            runs.append(dict(d,
                             run_id=run_code(d["metric"], d["percentile"], d["min_duration"], wkey),
                             window_key=wkey, window_type=w["type"], window_label=w["label"],
                             window_half=w.get("half"), window_collar=w.get("collar"),
                             window_order=w["order"],
                             comparison_op=COMPARISON_OP, baseline=BASELINE_SCHEME,
                             season=SEASON, absolute_floor="none",
                             analysis_years="%d-%d" % ANALYSIS_YEARS))
    return runs


def threshold_jobs():
    """Distinct (metric, window) -> percentiles needed.

    Thresholds do NOT depend on min_duration, and numpy computes several
    percentiles of the same baseline pool in ONE pass -- so the expensive
    threshold step runs once per (metric, window) rather than once per run.
    For this grid: 3 metrics x 4 windows = 12 threshold passes covering all
    56 runs.
    """
    jobs = {}
    for d in GRID_DEFINITIONS:
        for wkey in GRID_WINDOWS:
            jobs.setdefault((d["metric"], wkey), set()).add(d["percentile"])
    return {k: sorted(v) for k, v in sorted(jobs.items())}


# ---------------------------------------------------------- legacy naming
def definition_id(percentile):
    """Legacy Def 01/02 identifier (kept: it names the published output dirs)."""
    return "relMeanHI_p%d_%dd_walkforward" % (percentile, MIN_DURATION)


def definition_output_dir(state, percentile):
    """Legacy per-state, per-definition output dir (outputs/<ST>/def_p<PCTL>_<DUR>d)."""
    d = os.path.join(OUTPUT_ROOT, state, "def_p%d_%dd" % (percentile, MIN_DURATION))
    os.makedirs(os.path.join(d, "tables"), exist_ok=True)
    os.makedirs(os.path.join(d, "figures"), exist_ok=True)
    return d


def nws_office_table(state):
    """Per-state NWS office table path (may not exist -> NWS step skipped)."""
    return os.path.join(PIPELINE_DIR, "nws_offices_%s.csv" % state)