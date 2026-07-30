"""
=============================================================================
DEFINITION-COMPARISON PACKAGE  --  configuration and prespecified choices
=============================================================================
This package compares SIXTEEN county-level heatwave definitions for Texas,
2015-2025, and is deliberately separate from the pipeline that produced them:

    pipeline/            produces one definition x window at a time (p01..p06)
    outputs/definition_comparison/   compares all of them, once, in one place

Everything in this file that could bias a comparison is PRESPECIFIED here --
the primary window, the data-completeness cut, the long-event review length,
the example counties, and the definition pairs examined in detail. They are
set from properties of the INPUT data (imputation fractions, climate regions)
or from earlier methodological rounds, never from the heatwave results being
compared. Changing one of them means changing this file, which shows up in
git and in run_manifest.csv.

-----------------------------------------------------------------------------
THE SIXTEEN DEFINITIONS
-----------------------------------------------------------------------------
    definition = METRIC x PERCENTILE x MIN_DURATION
    run        = definition x THRESHOLD WINDOW

  Def 01-02   the previously published round: daily-MEAN heat index at the
              85th / 95th percentile, >= 2 days. Published as
              outputs/TX/def_p85_2d and def_p95_2d, where only the w15 and
              month windows were ever run, using an EARLIER version of p02
              whose output schema differs from the current one. This package
              therefore RE-RUNS them through the current code at all four
              windows (s01_rerun_legacy.py) and proves the re-run reproduces
              the published numbers exactly before using it.
  Def 03-16   the definition grid: Tmax / Tmin / mean HI x 85/90/95th x
              >=2 / >=3 days (mean HI only at the 90th), all four windows.

  NOT TESTED  MHI_P85_3D and MHI_P95_3D. The 3 x 3 x 2 factorial would have
              18 definitions; these two cells were never run. They are carried
              through every table and figure as an explicit "not tested"
              status and are NEVER filled with zero, and no line is drawn
              across them.

Held FIXED across all sixteen: county-relative percentile, strict ">",
walk-forward baseline 1979..Y-1, year-round season, no absolute floor, IDW
gap-filling of missing temperature, the same input county-day table.
=============================================================================
"""
import os
import sys

# --------------------------------------------------------------------------
# paths: this file lives in <repo>/outputs/definition_comparison/scripts/
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
PKG_ROOT = os.path.abspath(os.path.join(HERE, ".."))          # outputs/definition_comparison
REPO_ROOT = os.path.abspath(os.path.join(PKG_ROOT, "..", ".."))
PIPELINE_DIR = os.path.join(REPO_ROOT, "pipeline")
sys.path.insert(0, PIPELINE_DIR)
import config as C                                            # noqa: E402  (the pipeline config)

STATE = "TX"
STATE_LABEL = "Texas"

# package sub-directories (created on demand by ensure_dirs())
DIR_FIG_CORE = os.path.join(PKG_ROOT, "figures", "core")
DIR_FIG_SUPP = os.path.join(PKG_ROOT, "figures", "supplement")
DIR_COUNTY = os.path.join(PKG_ROOT, "county_profiles")
DIR_TABLES = os.path.join(PKG_ROOT, "tables")
DIR_CANON = os.path.join(PKG_ROOT, "tables", "canonical_long")
DIR_EVENTS = os.path.join(PKG_ROOT, "event_audits")
DIR_DICT = os.path.join(PKG_ROOT, "data_dictionary")
DIR_QA = os.path.join(PKG_ROOT, "qa")
ALL_DIRS = [DIR_FIG_CORE, DIR_FIG_SUPP, DIR_COUNTY, DIR_TABLES, DIR_CANON,
            DIR_EVENTS, DIR_DICT, DIR_QA]


def ensure_dirs():
    for d in ALL_DIRS:
        os.makedirs(d, exist_ok=True)


# =============================================================================
# 1. THE DEFINITION SET
# =============================================================================
# 'source' distinguishes the two rounds; 'rerun_required' marks the definitions
# whose published outputs came from an earlier code version and are therefore
# re-run here before being compared (see the module docstring).
DEFINITIONS = [
    # def_number, metric, percentile, min_duration, source
    dict(def_number=1,  metric="mhi",  percentile=85, min_duration=2,
         source="published_round1", rerun_required=True,  published_dir="def_p85_2d"),
    dict(def_number=2,  metric="mhi",  percentile=95, min_duration=2,
         source="published_round1", rerun_required=True,  published_dir="def_p95_2d"),
    dict(def_number=3,  metric="tmax", percentile=90, min_duration=2,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=4,  metric="tmin", percentile=90, min_duration=2,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=5,  metric="tmax", percentile=85, min_duration=2,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=6,  metric="tmin", percentile=85, min_duration=2,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=7,  metric="tmax", percentile=95, min_duration=2,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=8,  metric="tmin", percentile=95, min_duration=2,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=9,  metric="mhi",  percentile=90, min_duration=2,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=10, metric="tmax", percentile=90, min_duration=3,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=11, metric="tmin", percentile=90, min_duration=3,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=12, metric="tmax", percentile=85, min_duration=3,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=13, metric="tmin", percentile=85, min_duration=3,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=14, metric="tmax", percentile=95, min_duration=3,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=15, metric="tmin", percentile=95, min_duration=3,
         source="grid_round2", rerun_required=False, published_dir=None),
    dict(def_number=16, metric="mhi",  percentile=90, min_duration=3,
         source="grid_round2", rerun_required=False, published_dir=None),
]

# The two cells that complete the 3 x 3 x 2 factorial but were never run.
# Carried everywhere as status "not_tested"; never zero-filled, never interpolated.
UNTESTED_CELLS = [
    dict(definition_id="MHI_P85_3D", metric="mhi", percentile=85, min_duration=3,
         status="not_tested", note="mean-HI 3-day cell never run; completes the factorial"),
    dict(definition_id="MHI_P95_3D", metric="mhi", percentile=95, min_duration=3,
         status="not_tested", note="mean-HI 3-day cell never run; completes the factorial"),
]

WINDOW_ORDER = ["w05", "w15", "month", "month_pm7"]

# --- prespecified analysis choices -------------------------------------------
PRIMARY_WINDOW = "w15"
#   Prespecified in the earlier rounds: w15 (centered +/-7 days) is the window
#   Def 01/02 were published on and the window every cross-definition figure
#   here uses when ONE common window is required.

IMPUTATION_MAX_PCT = 10.0
#   The data-completeness cut for the "complete-data" panels. Chosen from the
#   INPUT imputation distribution alone (median 0.5%, q75 11.7%, 22 counties
#   100% imputed): "at least 90% of analysis days natively observed". 188 of
#   254 counties qualify. Never chosen from heatwave counts.

LONG_EVENT_REVIEW_DAYS = 21
#   An "event" of three continuous weeks of days each individually unusual for
#   its own date is implausible as one physical heat episode, so every event of
#   this length or longer is plotted and audited rather than trusted or deleted.

EVENT_TIMELINE_DAYS_PAD = 10        # days of context either side of a plotted event
MIN_REF_OBS = C.MIN_REF_OBS         # threshold flagged low_n_ref below this many baseline obs

SHORTLIST_DEFINITIONS = ["TMAX_P90_2D", "TMIN_P90_2D", "MHI_P90_2D",
                         "MHI_P85_2D", "MHI_P95_2D"]
#   The definitions carried into the data-quality figures and the event audits.
#   THE RULE: one definition per metric at the MIDDLE percentile and the SHORTER
#   duration (so no metric is privileged and neither extreme percentile drives
#   the picture), plus the two previously published definitions so the new work
#   stays connected to what has already been reported. Fixed before any result
#   was looked at; it is not a ranking.

LONG_EVENT_PLOT_CAP = 150
#   How many long events are drawn INDIVIDUALLY (longest first) at the primary
#   window. Every long event at every window is listed in
#   tables/table8a_long_event_audit.csv regardless -- none is ever deleted -- and
#   s07 logs and tabulates exactly which ones were not drawn, so a cap can never
#   be mistaken for "there were no others".

EVENT_TIMELINE_REFERENCE_DEFINITION = "MHI_P90_2D"
EVENT_TIMELINE_REFERENCE_YEAR = 2020
#   The event-timeline windows (Figure 9) are anchored mechanically: in each
#   example county, take the FIRST event starting in the middle year of the study
#   period under this one reference definition, and show that same calendar window
#   for every shortlisted definition. Anchoring on a fixed definition and a fixed
#   year rather than on "an interesting event" is what stops the examples being
#   selected for what they show.

THRESHOLD_CURVE_DEFINITION = "MHI_P90_2D"
THRESHOLD_CURVE_YEAR = 2025
#   The definition and analysis year used for the threshold-curve panels. Mean HI
#   at the 90th is the only mean-HI definition available at all four windows, and
#   2025 is the last walk-forward year, i.e. the widest baseline (1979-2024).

# --- definition pairs examined day-by-day (Figure 12) ------------------------
# Prespecified single-axis contrasts at the primary window, one per axis, plus
# the project's own published pair. Chosen because they isolate an axis, NOT
# because of what they show.
DISAGREEMENT_PAIRS = [
    dict(axis="metric", a="TMAX_P90_2D", b="TMIN_P90_2D", window=PRIMARY_WINDOW,
         rationale="day vs night temperature at matched percentile/duration"),
    dict(axis="metric", a="TMAX_P90_2D", b="MHI_P90_2D", window=PRIMARY_WINDOW,
         rationale="dry-bulb vs humidity-inclusive metric at matched percentile/duration"),
    dict(axis="percentile", a="TMAX_P85_2D", b="TMAX_P95_2D", window=PRIMARY_WINDOW,
         rationale="the widest percentile contrast on one metric"),
    dict(axis="duration", a="TMAX_P90_2D", b="TMAX_P90_3D", window=PRIMARY_WINDOW,
         rationale="the persistence rule, everything else fixed"),
    dict(axis="percentile", a="MHI_P85_2D", b="MHI_P95_2D", window=PRIMARY_WINDOW,
         rationale="Def 01 vs Def 02 -- the pair already published by this project"),
    dict(axis="window", a="MHI_P90_2D", b="MHI_P90_2D", window=None,
         window_a="w15", window_b="month",
         rationale="the two windows reported side by side in every earlier round"),
]

# =============================================================================
# 2. VISUAL ENCODING  (fixed across every figure in the package)
# =============================================================================
# The metric palette is the project's established one (already in the decks).
# Measured OKLab separation under simulated colour-vision deficiency:
#     normal        Tmax/Tmin 22.8, Tmax/meanHI 26.2, Tmin/meanHI 22.0
#     deuteranope   Tmax/Tmin 18.2, Tmax/meanHI  7.3, Tmin/meanHI 20.6
# Tmax vs mean HI sits at the dE>=6 floor for deuteranopes, which is legal ONLY
# with a second, non-colour channel. So metric identity is ALWAYS carried by
# colour AND marker shape AND hatch AND a text label -- never by colour alone.
METRIC_STYLE = {
    "TMAX": dict(color="#C44E52", marker="^", hatch="//",  short="Tmax",
                 label="daily maximum temperature"),
    "TMIN": dict(color="#4C72B0", marker="v", hatch="\\\\", short="Tmin",
                 label="daily minimum temperature"),
    "MHI":  dict(color="#55A868", marker="o", hatch="..",  short="mean HI",
                 label="daily-mean heat index"),
}
# percentile -> line style (never colour)
PCTL_STYLE = {85: dict(ls=":", lw=1.6, label="85th"),
              90: dict(ls="--", lw=1.6, label="90th"),
              95: dict(ls="-", lw=1.6, label="95th")}
# duration -> marker fill (never colour)
DUR_STYLE = {2: dict(fillstyle="full", label=">=2 days"),
             3: dict(fillstyle="none", label=">=3 days")}
# window -> position/panel only, with a neutral grey ramp when a colour is needed
WINDOW_GREY = {"w05": "#111111", "w15": "#555555", "month": "#8c8c8c", "month_pm7": "#c0c0c0"}

CMAP_SEQUENTIAL = "Blues"     # magnitude: one hue, light -> dark
CMAP_DIVERGING = "PuOr"       # signed differences: two hues + neutral midpoint,
                              # deliberately NOT the metric hues
COLOR_NOT_TESTED = "#d9d9d9"  # the untested cells, everywhere
COLOR_GRID = "#dddddd"
COLOR_INK = "#222222"
COLOR_INK_SOFT = "#666666"
JUN_SEP = [6, 7, 8, 9]

# Day-level agreement yardsticks established by this project's earlier
# sensitivity work -- the reference lines every Jaccard figure is read against.
YARDSTICKS = {
    "walk-forward vs fixed baseline": 0.923,
    "anchor vs composite temperature (low)": 0.45,
    "anchor vs composite temperature (high)": 0.73,
}

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# =============================================================================
# 3. DERIVED HELPERS
# =============================================================================
def definitions_expanded():
    """The 16 definitions with ids, metric metadata and reporting labels filled in."""
    out = []
    for d in DEFINITIONS:
        m = C.METRICS[d["metric"]]
        st = METRIC_STYLE[m["code"]]
        out.append(dict(d,
                        definition_id=C.definition_code(d["metric"], d["percentile"],
                                                        d["min_duration"]),
                        metric_code=m["code"], metric_col=m["col"],
                        metric_label=m["label"], metric_short=m["short"],
                        rh_dependent=m["rh_dependent"],
                        color=st["color"], marker=st["marker"], hatch=st["hatch"],
                        short_label="%s.P%d.%dD" % (m["code"], d["percentile"],
                                                    d["min_duration"]),
                        artifact_handling=("rh_clip_2023_03_01_set_missing" if m["rh_dependent"]
                                           else "not_applicable_metric_independent_of_rh")))
    return sorted(out, key=lambda x: x["def_number"])


def runs_expanded():
    """The 64 runs = 16 definitions x 4 windows, in stable reporting order."""
    runs = []
    for d in definitions_expanded():
        for wkey in WINDOW_ORDER:
            w = C.GRID_WINDOWS[wkey]
            runs.append(dict(d, run_id="%s__%s" % (d["definition_id"], wkey),
                             window_key=wkey, window_type=w["type"], window_label=w["label"],
                             window_order=w["order"],
                             reference_method=C.BASELINE_SCHEME,
                             season_rule=C.SEASON,
                             absolute_floor="none" if C.GRID_FLOOR_F is None else str(C.GRID_FLOOR_F),
                             comparison_op=C.COMPARISON_OP,
                             analysis_years="%d-%d" % C.ANALYSIS_YEARS))
    return runs


def def_order(primary_first=False):
    """Definition ids ordered by metric, then percentile, then duration -- the
    row/column order used by every matrix figure so they are all comparable."""
    ds = definitions_expanded()
    return [d["definition_id"] for d in
            sorted(ds, key=lambda x: (x["metric_code"], x["percentile"], x["min_duration"]))]


def metric_family_boundaries():
    """Index positions where the metric family changes in def_order() -- the
    lines drawn on the matrix figures."""
    order = def_order()
    ds = {d["definition_id"]: d["metric_code"] for d in definitions_expanded()}
    return [i for i in range(1, len(order)) if ds[order[i]] != ds[order[i - 1]]]


def tables_dir_for(definition_id):
    """Where a definition's per-run pipeline tables live.

    Every one of the 16 is stored under outputs/<ST>/grid/<DEFINITION_ID>/tables/,
    including the two re-run published definitions (s01 writes them there so all
    sixteen have one identical layout and schema). The ORIGINAL published Def
    01/02 outputs in outputs/<ST>/def_p85_2d and def_p95_2d are never touched.
    """
    return os.path.join(C.grid_root(STATE), definition_id, "tables")


def published_tables_dir(definition_id):
    """The original published output dir for Def 01/02 (read-only), or None."""
    for d in DEFINITIONS:
        if C.definition_code(d["metric"], d["percentile"], d["min_duration"]) == definition_id \
                and d.get("published_dir"):
            return os.path.join(C.OUTPUT_ROOT, STATE, d["published_dir"], "tables")
    return None


def canonical_path(definition_id, window_key):
    return os.path.join(DIR_CANON, "canonical_%s__%s.csv.gz" % (definition_id, window_key))


def county_profile_dir(county_fips):
    d = os.path.join(DIR_COUNTY, str(county_fips))
    os.makedirs(d, exist_ok=True)
    return d


def climate_division_path():
    return os.path.join(DIR_TABLES, "ref_county_climate_division.csv")


# Source of the county -> NOAA climate-division crosswalk copied into this
# package. Division NUMBERS are from the NOAA/NCEI primary crosswalk
# (county-to-climdivs.txt); division NAMES are from secondary sources and are
# labels only -- the grouping is what the analysis uses.
CLIMDIV_SOURCE = os.path.join(
    REPO_ROOT, "..", "gulf_eda", "expanding_baseline", "def_comparison",
    "v2_texas_audit", "followups", "tables", "texas_climate_divisions_official.csv")
CLIMDIV_PROVENANCE = ("NOAA/NCEI county-to-climdivs.txt (division numbers: primary source); "
                      "division names from secondary sources, labels only")


def log(*a):
    print(*a, flush=True)


def md_table(df, cols=None, max_rows=None):
    """GitHub-flavoured markdown table.

    Written out by hand because pandas' to_markdown needs `tabulate`, which is
    not installed in this environment (and this package deliberately adds no new
    dependencies -- see methods_notes.md).
    """
    d = df if cols is None else df[cols]
    if max_rows is not None and len(d) > max_rows:
        d = d.head(max_rows)
        truncated = len(df) - max_rows
    else:
        truncated = 0

    def cell(v):
        import math
        if v is None:
            return ""
        if isinstance(v, float) and math.isnan(v):
            return ""
        return str(v).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(str(c) for c in d.columns) + " |",
             "|" + "|".join(["---"] * len(d.columns)) + "|"]
    for _, r in d.iterrows():
        lines.append("| " + " | ".join(cell(v) for v in r.tolist()) + " |")
    if truncated:
        lines.append("")
        lines.append("_...%d further row(s) omitted; see the CSV._" % truncated)
    return "\n".join(lines)
