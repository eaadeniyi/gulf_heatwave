"""
=============================================================================
Shared machinery for the definition-comparison package.
=============================================================================
Everything that more than one step needs lives here, so the validation step,
the table step and the figure steps cannot drift apart in how they define
"a matched pair", "day-level agreement" or "the primary window".

  DAY SETS          the SET of (county, date) heatwave days for a run, encoded
                    as sorted int64 so set algebra on ~150k-key sets is fast
  AGREEMENT         Jaccard index on those sets = |shared| / |union|
  MATCHED PAIRS     two runs identical on three of the four axes and differing
                    on exactly one -- the only pairs a marginal effect may be
                    computed from
  FIGURE STYLE      the fixed metric/percentile/duration encodings

WHAT JACCARD IS NOT
  It is agreement between two definitions, not accuracy of either. Neither
  definition is a gold standard: there is no observed "true heatwave day" in
  this data. A low Jaccard says the two definitions classify different days,
  and says nothing about which is right.
=============================================================================
"""
import os
import sys
import itertools

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defcmp_config as K
import config as C

DATE0 = np.datetime64("2015-01-01", "D")


# =============================================================================
# 1. day sets: the identity of the classified county-dates
# =============================================================================
_CTY_INDEX = {}


def county_code(fips_series):
    """Stable small integer per county, shared by every set in this session."""
    for c in pd.unique(fips_series):
        _CTY_INDEX.setdefault(c, len(_CTY_INDEX))
    return fips_series.map(_CTY_INDEX).to_numpy(dtype=np.int64)


def encode_days(fips_series, date_series):
    """(county, date) -> unique int64. Exact, no collisions: date offsets span
    ~4,018 values and are given 100,000 slots."""
    ci = county_code(fips_series)
    do = (pd.to_datetime(date_series).to_numpy(dtype="datetime64[D]") - DATE0).astype(np.int64)
    return np.unique(ci * 100000 + do)


def load_day_set(definition_id, window_key, flag="heatwave_day_flag"):
    """The (county, date) set for one run, read from its canonical shard."""
    p = K.canonical_path(definition_id, window_key)
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p, usecols=["county_fips", "date", flag], dtype={"county_fips": str})
    d = d[d[flag] == 1]
    return encode_days(d["county_fips"], d["date"])


def load_day_sets(runs, flag="heatwave_day_flag", verbose=True):
    sets = {}
    for r in runs:
        s = load_day_set(r["definition_id"], r["window_key"], flag=flag)
        if s is None:
            continue
        sets[r["run_id"]] = s
        if verbose:
            K.log("   [days] %-26s %10s %s" % (r["run_id"], "{:,}".format(len(s)),
                                               flag.replace("_flag", "s")))
    return sets


def jaccard(a, b):
    """|A and B| / |A or B| on sorted unique int64 arrays."""
    if a is None or b is None:
        return np.nan
    inter = np.intersect1d(a, b, assume_unique=True).size
    union = a.size + b.size - inter
    return inter / union if union else np.nan


def jaccard_matrix(sets, ids):
    n = len(ids)
    M = np.full((n, n), np.nan)
    for i in range(n):
        M[i, i] = 1.0
    for i, j in itertools.combinations(range(n), 2):
        M[i, j] = M[j, i] = jaccard(sets.get(ids[i]), sets.get(ids[j]))
    return pd.DataFrame(M, index=ids, columns=ids)


# =============================================================================
# 2. matched pairs: the only valid basis for a marginal effect
# =============================================================================
AXIS_FIELD = {"metric": "metric_code", "percentile": "percentile",
              "duration": "min_duration", "window": "window_key"}


def axes_differing(ra, rb):
    return [ax for ax, f in AXIS_FIELD.items() if ra[f] != rb[f]]


def matched_pairs(runs, only_available=None):
    """Every pair of runs differing on EXACTLY ONE axis.

    A pair is only returned if both of its runs actually exist (`only_available`
    is the set of run_ids present on disk). Nothing is inferred for the two
    untested MHI 3-day cells: they are simply absent, so no pair involving them
    is ever formed -- which is why the marginal effect of DURATION is estimated
    from fewer pairs than the other axes, and why every table reports its own
    matched-pair count.
    """
    meta = {r["run_id"]: r for r in runs}
    ids = [r["run_id"] for r in runs]
    if only_available is not None:
        ids = [i for i in ids if i in only_available]
    out = []
    for a, b in itertools.combinations(ids, 2):
        d = axes_differing(meta[a], meta[b])
        if len(d) != 1:
            continue
        ax = d[0]
        out.append({"axis": ax, "run_a": a, "run_b": b,
                    "definition_a": meta[a]["definition_id"],
                    "definition_b": meta[b]["definition_id"],
                    "value_a": meta[a][AXIS_FIELD[ax]], "value_b": meta[b][AXIS_FIELD[ax]],
                    "metric": meta[a]["metric_code"] if ax != "metric" else "",
                    "percentile": meta[a]["percentile"] if ax != "percentile" else "",
                    "min_duration": meta[a]["min_duration"] if ax != "duration" else "",
                    "window": meta[a]["window_key"] if ax != "window" else ""})
    return pd.DataFrame(out)


def matched_pair_counts(pairs):
    """n matched pairs per axis -- reported alongside every marginal effect."""
    return (pairs.groupby("axis").size().rename("n_matched_pairs")
            .reset_index().sort_values("axis"))


# =============================================================================
# 3. loading the package's own tables
# =============================================================================
def available_runs(runs=None):
    """The runs that have a canonical shard on disk."""
    runs = runs or K.runs_expanded()
    return [r for r in runs
            if os.path.exists(K.canonical_path(r["definition_id"], r["window_key"]))]


def read_master_county_year():
    return pd.read_csv(os.path.join(K.DIR_TABLES, "master_county_year_summary.csv"),
                       dtype={"county_fips": str})


def read_master_county_month():
    return pd.read_csv(os.path.join(K.DIR_TABLES, "master_county_month_summary.csv"),
                       dtype={"county_fips": str})


def read_master_events():
    return pd.read_csv(os.path.join(K.DIR_TABLES, "master_event_table.csv.gz"),
                       dtype={"county_fips": str})


def read_eligibility():
    return pd.read_csv(os.path.join(K.DIR_TABLES, "eligibility_county_month.csv"),
                       dtype={"county_fips": str})


def read_reference():
    """County reference layer: names, climate division, imputation, flags."""
    cov = pd.read_csv(os.path.join(K.REPO_ROOT, "outputs", K.STATE,
                                   "coverage_and_imputation_report.csv"),
                      dtype={"county_fips": str})
    cov["fully_imputed_county"] = (cov["fully_imputed_county"].astype(str).str.lower()
                                   .isin(("true", "1", "yes")))
    cdiv = pd.read_csv(K.climate_division_path(), dtype={"county_fips": str, "climdiv_id": str})
    ref = cov.merge(cdiv[["county_fips", "climdiv_id", "division_name"]],
                    on="county_fips", how="left")
    ref = ref.rename(columns={"division_name": "climate_division",
                              "pct_analysis_days_imputed": "temperature_imputation_pct"})
    ref["data_complete"] = ref["temperature_imputation_pct"] <= K.IMPUTATION_MAX_PCT
    # the canonical-table column name too, so a frame from here can be handed
    # straight to s02.classify_run() (s07 does exactly that when it rebuilds the
    # daily panels for the event audits)
    ref["temperature_imputation_fraction"] = (ref["temperature_imputation_pct"] / 100.0).round(6)
    return ref


def county_totals(cy, run_id):
    """Per-county heatwave days + events for one run, over ALL counties.

    Counties with no heatwave day are absent from the county-year table, so they
    are reindexed back in at zero HERE -- a genuine zero (the definition was
    evaluated and flagged nothing), which is different from an absent
    definition-window combination, and is never done for the latter.
    """
    ref = read_reference()
    sub = cy[cy["run_id"] == run_id]
    g = sub.groupby("county_fips")[["heatwave_days", "heatwave_events_started"]].sum()
    g = g.reindex(sorted(ref["county_fips"].unique()), fill_value=0)
    return g.reset_index().merge(ref, on="county_fips", how="left")


# =============================================================================
# 4. figure style
# =============================================================================
def style_for(metric_code):
    return K.METRIC_STYLE[metric_code]


def def_label(d, with_window=None):
    """The label used on every axis: metric.percentile.duration[.window]."""
    s = "%s.P%d.%dD" % (d["metric_code"], d["percentile"], d["min_duration"])
    return s + (".%s" % with_window if with_window else "")


def tidy_axes(ax, grid_axis="y"):
    """Recessive grid and spines, so the data is the only prominent ink."""
    ax.set_axisbelow(True)
    if grid_axis:
        ax.grid(axis=grid_axis, color=K.COLOR_GRID, lw=0.6, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#999999")
    ax.tick_params(colors=K.COLOR_INK_SOFT, labelsize=8)
    return ax


def metric_legend_handles(metrics=("TMAX", "TMIN", "MHI")):
    """Legend proxies carrying colour AND marker -- identity is never colour alone."""
    from matplotlib.lines import Line2D
    out = []
    for m in metrics:
        st = K.METRIC_STYLE[m]
        out.append(Line2D([0], [0], color=st["color"], marker=st["marker"], lw=2,
                          markersize=7, label=st["short"]))
    return out


def pctl_legend_handles(pctls=(85, 90, 95)):
    from matplotlib.lines import Line2D
    return [Line2D([0], [0], color=K.COLOR_INK_SOFT, ls=K.PCTL_STYLE[p]["ls"], lw=1.8,
                   label=K.PCTL_STYLE[p]["label"]) for p in pctls]


def duration_legend_handles():
    from matplotlib.lines import Line2D
    return [Line2D([0], [0], color=K.COLOR_INK_SOFT, marker="o", lw=0,
                   markerfacecolor=(K.COLOR_INK_SOFT if d == 2 else "none"),
                   markersize=7, label=K.DUR_STYLE[d]["label"]) for d in (2, 3)]


def footnote(fig, text, y=0.005):
    fig.text(0.005, y, text, fontsize=6.8, color=K.COLOR_INK_SOFT, va="bottom", wrap=True)


def unit_banner(ax, unit_text):
    """Every figure states its unit of analysis, in the same place, every time."""
    ax.set_title(ax.get_title(), loc="left")
    ax.text(0.0, 1.005, "unit of analysis: %s" % unit_text, transform=ax.transAxes,
            fontsize=7, color=K.COLOR_INK_SOFT, va="bottom", ha="left")


def savefig(fig, path, dpi=150):
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=dpi)
    import matplotlib.pyplot as plt
    plt.close(fig)
    K.log("      -> %s" % os.path.relpath(path, K.PKG_ROOT))
