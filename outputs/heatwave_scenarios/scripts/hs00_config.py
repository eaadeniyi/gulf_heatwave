"""
=============================================================================
hs00_config.py  --  configuration and the CONSTRUCTS registry for the
                    heatwave-definition scenario package.
=============================================================================
Implements plan revision 6 (C:\\Users\\eadeni1\\.claude\\plans\\sunny-munching-spindle.md).
This package is self-contained under outputs/heatwave_scenarios/, reads
outputs/TX/county_daily_heat.csv READ-ONLY, and imports (never modifies)
functions from pipeline/ (heat_index.py, p02_classify_and_report.py,
heatwave_run_logic.py).

CONSTRUCTS is the single source of truth: scenario_registry.csv is
regenerated from it on every invocation (never hand-edited), the same
non-drift guarantee as pipeline/definition_registry.csv.
=============================================================================
"""
import os, sys

# ---------------------------------------------------------------- paths
_HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE_ROOT = os.path.abspath(os.path.join(_HERE, ".."))          # outputs/heatwave_scenarios
OUTPUTS_ROOT = os.path.abspath(os.path.join(PACKAGE_ROOT, ".."))   # outputs/
PROJECT_ROOT = os.path.abspath(os.path.join(OUTPUTS_ROOT, ".."))   # texas_heatwave_pilot/
PIPELINE_DIR = os.path.join(PROJECT_ROOT, "pipeline")
REFERENCE_DIR = os.path.join(PROJECT_ROOT, "reference")

sys.path.insert(0, PIPELINE_DIR)   # so this package can import pipeline.* modules unmodified

TABLES_DIR = os.path.join(PACKAGE_ROOT, "tables")
FIGURES_DIR = os.path.join(PACKAGE_ROOT, "figures")
QA_DIR = os.path.join(PACKAGE_ROOT, "qa")
DATA_DICT_DIR = os.path.join(PACKAGE_ROOT, "data_dictionary")
REPORTS_DIR = os.path.join(PACKAGE_ROOT, "reports")
for _d in (TABLES_DIR, FIGURES_DIR, QA_DIR, DATA_DICT_DIR, REPORTS_DIR):
    os.makedirs(_d, exist_ok=True)

REGISTRY_FILE = os.path.join(TABLES_DIR, "scenario_registry.csv")
GRID_ROOT = os.path.join(OUTPUTS_ROOT, "TX", "grid")   # outputs/TX/grid/ -- source of reused Tmax cells


def county_day_path(state="TX"):
    return os.path.join(OUTPUTS_ROOT, state, "county_daily_heat.csv")


def construct_dir(construct_id, make=True):
    d = os.path.join(TABLES_DIR, construct_id)
    if make:
        os.makedirs(d, exist_ok=True)
    return d


# =============================================================================
# SECTION 1  --  shared study parameters
# =============================================================================
STATE = "TX"
ANALYSIS_YEARS = (2015, 2025)
BASELINE_START = 1979
FIXED_BASELINE = (1979, 2014)          # inclusive; EHF_TX_FIXED7914's reference period
PRIMARY_WINDOW = "w15"                 # centered 15-day window; the only window used in this round
COMPARISON_OP = ">"                    # candidate = metric strictly above threshold, project convention
JUNSEP_START = (6, 1)                  # (month, day) -- warm-season eligibility, inclusive
JUNSEP_END = (9, 30)


# =============================================================================
# SECTION 2  --  reference-adequacy rule (plan Sec.1, T95 blocking fix)
# =============================================================================
# Applies to EVERY threshold in this package (T95, ehf85_c2, and every Tmax/HIPROXY/
# HIXENV percentile threshold) -- NOT a bare n>=20 count, which was inherited from a
# different (day-of-year-windowed) context and is not defensible for an all-calendar-day
# or otherwise large reference pool.
MIN_REFERENCE_COMPLETENESS_FRACTION = 0.90
MIN_DISTINCT_REFERENCE_YEARS = 30              # of the 36 years in FIXED_BASELINE
MIN_VALID_DAYS_PER_QUALIFYING_YEAR = 300       # a year counts toward the distinct-year tally only if this complete
EXCESSIVE_REFERENCE_IMPUTATION_THRESHOLD = 0.50

# EHF severity reference floor (tighter than the general rule above; ehf85_c2 is a tail
# statistic of an already-thin positive-EHF subset, so needs its own stricter floor)
EHF_SEVERITY_MIN_POSITIVE_REFERENCE_VALUES = 100
EHF_SEVERITY_MIN_DISTINCT_YEARS = 10
EHF_SEVERITY_DEGENERATE_TOLERANCE_C2 = 1e-6

# EHF severity cut points (ratio = ehf_c2 / ehf85_c2); standard Nairn-Fawcett/BoM convention
EHF_SEVERITY_SEVERE_RATIO = 1.0
EHF_SEVERITY_EXTREME_RATIO = 3.0

EHF_HIGH_IMPUTATION_SUPPORT_THRESHOLD = 0.20   # fraction of the 30-day acclimatization window


# =============================================================================
# SECTION 3  --  artifact QC -- exact keys, verified against the project record
# =============================================================================
# Verified directly against
# reference/archive_prior_analysis/quality_control/06_march2023_anomaly_verification.md
# -- NOT re-derived from the screening rule below, and never regenerated from it.
CONFIRMED_ARTIFACT_KEYS = [
    {"county_fips": "48061", "date": "2023-03-01", "county_name": "Cameron"},
    {"county_fips": "48201", "date": "2023-03-01", "county_name": "Harris"},
    {"county_fips": "48453", "date": "2023-03-01", "county_name": "Travis"},
]
CONFIRMATION_BASIS = (
    "Zero measured precipitation across 23-62 GHCN stations per county; station-average RH "
    "79.5-83% (not 100%); dewpoint-implied true afternoon RH ~58-60%, physically incompatible "
    "with saturation under an 84-88F afternoon high; the single most widespread same-day "
    "RH=100/100 pin in the 47-year record (118/254 counties, rank #1 of 17,354 dates)."
)
VERIFICATION_SOURCE = (
    "reference/archive_prior_analysis/quality_control/06_march2023_anomaly_verification.md"
)

# Explicitly NOT in the confirmed list: 2017-01-14 (Lubbock, Travis) -- that document's own
# investigation found a GENUINE cold-season precipitation/saturation event (measurable rain,
# station RH 94.5-97%, Tmax<80F so the heat-index proxy equals Tmax regardless). Stays
# qc_category=valid under every tier, on every construct, always.
KNOWN_VALID_MULTICOUNTY_PIN_DATES = [
    {"county_fips": "48303", "date": "2017-01-14", "county_name": "Lubbock"},
    {"county_fips": "48453", "date": "2017-01-14", "county_name": "Travis"},
]

# The broader screening rule (project-wide, applied identically to rmax/rmin), matching the
# existing qc_rh_pin_likely_artifact logic in pipeline/p01_build_countyday_idw.py exactly:
#   round(rmax_pct,6)==100.0 AND round(rmin_pct,6)==100.0 AND prcp_in<0.01 AND tmax_f>=80
# Computed SEPARATELY from CONFIRMED_ARTIFACT_KEYS above and never used to generate or
# validate that list -- they are different data objects (plan Sec.5).
RH_PIN_TOLERANCE = 1e-6      # round(...,6)==100.0 equivalent
NO_RAIN_PRCP_IN_THRESHOLD = 0.01
WARM_TMAX_F_THRESHOLD = 80.0

QC_CATEGORIES = ("confirmed_artifact", "rule_flagged_probable_artifact", "valid")
QC_TIERS = ("RAW", "CONFEXCL", "PROBEXCL")   # RAW: all retained | CONFEXCL: confirmed_artifact
                                              # excluded | PROBEXCL: confirmed + rule_flagged excluded


# =============================================================================
# SECTION 4  --  example counties (plan Sec.9) -- named now, not selected post-hoc
# =============================================================================
EXAMPLE_COUNTIES = [
    {"county_fips": "48201", "county_name": "Harris", "region": "gulf_coast_humid_urban"},
    {"county_fips": "48113", "county_name": "Dallas", "region": "north_central_urban"},
    {"county_fips": "48141", "county_name": "El Paso", "region": "far_west_arid"},
]
EXAMPLE_SELECTION_RULE = (
    "One Gulf Coast humid county, one north-central urban county, one far-west arid county -- "
    "geographically standard Texas climate-region examples, frozen before any result was computed."
)
EXAMPLE_SELECTED_BEFORE_RESULTS = True


# =============================================================================
# SECTION 5  --  threshold uncertainty -- exact construct list + frozen date windows (plan Sec.8)
# =============================================================================
UNCERTAINTY_CONSTRUCT_IDS = [
    "TMAX_P85_D3_W15",
    "TMAX_P975_D3_W15",
    "HIPROXY_P95_D2_W15_CONFEXCL",
    "HIXENV_P975_D2_W15_CONFEXCL",
]
UNCERTAINTY_DATE_WINDOWS = [
    ("05-25", "06-07"),   # spring -> summer boundary
    ("07-10", "07-20"),   # mid-summer
    ("08-10", "08-20"),   # mid-summer
    ("09-24", "10-07"),   # summer -> fall boundary
]


# =============================================================================
# SECTION 6  --  the CONSTRUCTS registry (27 runs; the single source of truth)
# =============================================================================
def _tmax_row(construct_id, percentile, duration, season, role, reused, source_run_id=None):
    return {
        "construct_id": construct_id, "family": "tmax", "metric": "tmax_f",
        "date_representation": "daily_threshold_classification",
        "event_definition_type": "consecutive_daily_exceedance_event",
        "percentile": percentile, "min_duration": duration, "window": PRIMARY_WINDOW,
        "baseline": "walk_forward", "season_rule": season, "qc_tier": "n/a",
        "role": role, "selection_basis": "user-specified" if role == "candidate" else "percentile_sweep_sensitivity",
        "decision_status": "open",
        "reused_from_grid": reused,
        "source_run_id": source_run_id,
        "cross_family_comparable_events": False,
    }


def _hiproxy_row(construct_id, percentile, duration, season, qc_tier, role):
    return {
        "construct_id": construct_id, "family": "hiproxy", "metric": "derived_tmax_rhmin_hi_proxy_f",
        "date_representation": "daily_threshold_classification",
        "event_definition_type": "consecutive_daily_exceedance_event",
        "percentile": percentile, "min_duration": duration, "window": PRIMARY_WINDOW,
        "baseline": "walk_forward", "season_rule": season, "qc_tier": qc_tier,
        "role": role,
        "selection_basis": "user-specified" if role == "candidate" else "qc_or_percentile_sensitivity",
        "decision_status": "open", "reused_from_grid": False, "source_run_id": None,
        "cross_family_comparable_events": False,
    }


def _hixenv_row(construct_id, percentile, qc_tier, role):
    return {
        "construct_id": construct_id, "family": "hixenv", "metric": "synthetic_tmax_rhmax_hi_f",
        "date_representation": "daily_threshold_classification",
        "event_definition_type": "consecutive_daily_exceedance_event",
        "percentile": percentile, "min_duration": 2, "window": PRIMARY_WINDOW,
        "baseline": "walk_forward", "season_rule": "year_round", "qc_tier": qc_tier,
        "role": role, "selection_basis": "qc_or_percentile_sensitivity",
        "decision_status": "open", "reused_from_grid": False, "source_run_id": None,
        "cross_family_comparable_events": False,
    }


def _ehf_row(construct_id, baseline, role):
    return {
        "construct_id": construct_id, "family": "ehf", "metric": "ehf_c2",
        "date_representation": "positive_ehf_assessment_date",
        "event_definition_type": "positive_ehf_assessment_period",
        "percentile": None, "min_duration": 1, "window": None,
        "baseline": baseline, "season_rule": "year_round", "qc_tier": "n/a",
        "role": role,
        "selection_basis": "user-specified" if role == "candidate" else "literature_comparable_benchmark",
        "decision_status": "open", "reused_from_grid": False, "source_run_id": None,
        "cross_family_comparable_events": False,   # NEVER compared directly to other families' event counts
        "literature_replication_status": "adapted_not_exact" if baseline == "fixed_1979_2014" else "adaptation",
    }


CONSTRUCTS = [
    # ---- EHF (2) ----
    _ehf_row("EHF_TX_FIXED7914", "fixed_1979_2014", "benchmark"),
    _ehf_row("EHF_TX_WALKFORWARD", "walk_forward", "candidate"),

    # ---- Tmax (9): 6 reused from outputs/TX/grid/, 3 new ----
    _tmax_row("TMAX_P80_D3_W15", 80, 3, "year_round", "sensitivity", reused=False),
    _tmax_row("TMAX_P85_D3_W15", 85, 3, "year_round", "candidate", reused=True, source_run_id="TMAX_P85_3D__w15"),
    _tmax_row("TMAX_P90_D3_W15", 90, 3, "year_round", "sensitivity", reused=True, source_run_id="TMAX_P90_3D__w15"),
    _tmax_row("TMAX_P95_D3_W15", 95, 3, "year_round", "sensitivity", reused=True, source_run_id="TMAX_P95_3D__w15"),
    _tmax_row("TMAX_P975_D3_W15", 97.5, 3, "year_round", "sensitivity", reused=False),
    _tmax_row("TMAX_P85_D2_W15", 85, 2, "year_round", "sensitivity", reused=True, source_run_id="TMAX_P85_2D__w15"),
    _tmax_row("TMAX_P90_D2_W15", 90, 2, "year_round", "sensitivity", reused=True, source_run_id="TMAX_P90_2D__w15"),
    _tmax_row("TMAX_P95_D2_W15", 95, 2, "year_round", "sensitivity", reused=True, source_run_id="TMAX_P95_2D__w15"),
    _tmax_row("TMAX_P85_D3_W15_JUNSEP", 85, 3, "june_september", "candidate", reused=False),

    # ---- HI-proxy (5): Tmax+RHmin, all new classifications ----
    _hiproxy_row("HIPROXY_P85_D2_W15_CONFEXCL", 85, 2, "year_round", "CONFEXCL", "sensitivity"),
    _hiproxy_row("HIPROXY_P90_D2_W15_CONFEXCL", 90, 2, "year_round", "CONFEXCL", "sensitivity"),
    _hiproxy_row("HIPROXY_P95_D2_W15_CONFEXCL", 95, 2, "year_round", "CONFEXCL", "candidate"),
    _hiproxy_row("HIPROXY_P95_D2_W15_JUNSEP_CONFEXCL", 95, 2, "june_september", "CONFEXCL", "candidate"),
    _hiproxy_row("HIPROXY_P95_D2_W15_PROBEXCL", 95, 2, "year_round", "PROBEXCL", "sensitivity"),

    # ---- Synthetic Tmax+RHmax envelope (11): all new ----
    _hixenv_row("HIXENV_P80_D2_W15_RAW", 80, "RAW", "sensitivity"),
    _hixenv_row("HIXENV_P85_D2_W15_RAW", 85, "RAW", "sensitivity"),
    _hixenv_row("HIXENV_P90_D2_W15_RAW", 90, "RAW", "sensitivity"),
    _hixenv_row("HIXENV_P95_D2_W15_RAW", 95, "RAW", "sensitivity"),
    _hixenv_row("HIXENV_P975_D2_W15_RAW", 97.5, "RAW", "sensitivity"),
    _hixenv_row("HIXENV_P80_D2_W15_CONFEXCL", 80, "CONFEXCL", "sensitivity"),
    _hixenv_row("HIXENV_P85_D2_W15_CONFEXCL", 85, "CONFEXCL", "sensitivity"),
    _hixenv_row("HIXENV_P90_D2_W15_CONFEXCL", 90, "CONFEXCL", "sensitivity"),
    _hixenv_row("HIXENV_P95_D2_W15_CONFEXCL", 95, "CONFEXCL", "sensitivity"),
    _hixenv_row("HIXENV_P975_D2_W15_CONFEXCL", 97.5, "CONFEXCL", "sensitivity"),
    _hixenv_row("HIXENV_P95_D2_W15_PROBEXCL", 95, "PROBEXCL", "sensitivity"),
]

assert len(CONSTRUCTS) == 27, "CONSTRUCTS must have exactly 27 rows per the approved plan; got %d" % len(CONSTRUCTS)
assert len({c["construct_id"] for c in CONSTRUCTS}) == 27, "construct_id values must be unique"


def constructs_by_family(family):
    return [c for c in CONSTRUCTS if c["family"] == family]


def get_construct(construct_id):
    for c in CONSTRUCTS:
        if c["construct_id"] == construct_id:
            return c
    raise KeyError(construct_id)


# runs entering the 21x21 year-round agreement matrix (Sec.7): excludes EHF, both JUNSEP
# runs, and both PROBEXCL sensitivity runs
def yearround_ordinary_construct_ids():
    ids = []
    for c in CONSTRUCTS:
        if c["family"] == "ehf":
            continue
        if c["season_rule"] != "year_round":
            continue
        if c.get("qc_tier") == "PROBEXCL":
            continue
        ids.append(c["construct_id"])
    return ids


WARMSEASON_PAIR = ("TMAX_P85_D3_W15_JUNSEP", "HIPROXY_P95_D2_W15_JUNSEP_CONFEXCL")
MATCHED_METRIC_PAIRS = [
    ("TMAX_P85_D2_W15", "HIPROXY_P85_D2_W15_CONFEXCL"),
    ("TMAX_P90_D2_W15", "HIPROXY_P90_D2_W15_CONFEXCL"),
    ("TMAX_P95_D2_W15", "HIPROXY_P95_D2_W15_CONFEXCL"),
]
PRESPECIFIED_ASYMMETRIC_PAIR = ("TMAX_P85_D3_W15", "HIXENV_P95_D2_W15_CONFEXCL")


if __name__ == "__main__":
    yr = yearround_ordinary_construct_ids()
    print("CONSTRUCTS: %d total" % len(CONSTRUCTS))
    print("year-round ordinary (feeds the 21x21 matrix): %d" % len(yr))
    assert len(yr) == 21, "expected exactly 21 year-round ordinary constructs, got %d" % len(yr)
    print("OK")
