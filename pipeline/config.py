"""
=============================================================================
CONFIGURATION  --  the ONE place to change to run the heatwave pipeline for a
                   different state, percentile, or study period.
=============================================================================

This pipeline classifies "heatwave days" and "heatwave events" for the counties
of a US state, using a COUNTY-RELATIVE percentile of a daily heat-index proxy
plus a consecutive-day persistence rule, on a walk-forward (expanding) climate
baseline. It was first developed for Texas but is deliberately NOT locked to
Texas -- everything state-specific is a parameter below.

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
4. Run:  python run_all.py      (runs every step for every configured state)
   or run the steps individually: p01 -> p02 -> p03 -> p04.

------------------------------------------------------------------------------
WHAT EACH DEFINITION IS
------------------------------------------------------------------------------
Each entry in PERCENTILES produces one "definition":
    Definition = county-relative <PCTL>th-percentile daily-MEAN heat index,
                 sustained >= MIN_DURATION consecutive days, walk-forward baseline.
    e.g. PERCENTILES = [85, 95] builds Definition 01 (85th) and Definition 02 (95th).
Only the percentile changes between them; all other logic is shared.
=============================================================================
"""
import os

# --- states to process (abbreviations). Add/replace freely. -----------------
STATES = ["TX"]                 # e.g. ["TX"], ["LA", "MS"], ...

# --- percentile(s): each one is a separate heatwave definition. -------------
#     85 -> Definition 01 ; 95 -> Definition 02 ; add more if desired.
PERCENTILES = [95]

# --- study window and climate baseline --------------------------------------
ANALYSIS_YEARS = (2015, 2025)   # inclusive; the years we classify heatwaves in
BASELINE_START = 1979           # walk-forward baseline pools years BASELINE_START..(Y-1)
MIN_DURATION = 2                # a heatwave EVENT is a run of >= this many days

# --- the daily heat metric --------------------------------------------------
#     "mean" = daily-MEAN heat index = heat_index(Tmean, mean RH). This is the
#     metric these definitions use. (A daily-MAX proxy also exists in the county
#     -day table and is what the NWS-proxy step uses -- see p03.)
METRIC = "mean"

# --- absolute floor on the PRIMARY definition -------------------------------
#     None  = no floor (a purely relative "anomalous-for-this-date" definition;
#             this is the definition as specified). A floor value (e.g. 80) would
#             additionally require the heat index to reach that many degrees F.
#             The floor is explored as a SENSITIVITY regardless of this setting.
PRIMARY_FLOOR_F = None
FLOOR_SENSITIVITY_F = 80.0      # floor used only for the reported sensitivity scenario

# --- threshold windows (reported alongside each other) ----------------------
#     Each window defines HOW the county-specific percentile threshold is pooled
#     across the calendar for a given target date:
#       centered : target day +/- 'half' days (a 2*half+1 day window)
#       month    : all days in the same calendar month
WINDOWS = {
    "w15": {"type": "centered", "half": 7,   # centered 15-day-total window (target +/-7)
            "label": "centered 15-day-total (+/-7) window"},
    "month": {"type": "month",
              "label": "calendar-month bucket"},
}

# --- IDW gap-filling of missing daily temperature ---------------------------
#     Missing county-days are filled by inverse-distance weighting from other
#     counties that have data that day, using county CENTROID distances.
IDW_POWER = 2                   # weight = 1 / distance^IDW_POWER

# --- quality-control -------------------------------------------------------
MIN_REF_OBS = 20                # threshold flagged 'low_n_ref' below this many baseline obs

# =============================================================================
# PATHS  --  templated so nothing is hardcoded to one state.
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

# --- Heat-index helper lives in the project's gulf_eda utilities ------------
HEAT_INDEX_MODULE_DIR = os.path.join(PROJECT_ROOT, "gulf_eda", "scripts")

# =============================================================================
# US STATE ABBREVIATION -> 2-DIGIT FIPS  (so any state can be selected)
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
# Small helpers so every step resolves paths/config the same way.
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


def definition_id(percentile):
    return "relMeanHI_p%d_%dd_walkforward" % (percentile, MIN_DURATION)


def definition_output_dir(state, percentile):
    """Per-state, per-definition outputs (thresholds, events, summaries, figures)."""
    d = os.path.join(OUTPUT_ROOT, state, "def_p%d_%dd" % (percentile, MIN_DURATION))
    os.makedirs(os.path.join(d, "tables"), exist_ok=True)
    os.makedirs(os.path.join(d, "figures"), exist_ok=True)
    return d


def nws_office_table(state):
    """Per-state NWS office table path (may not exist -> NWS step skipped)."""
    return os.path.join(PIPELINE_DIR, "nws_offices_%s.csv" % state)
