"""
=============================================================================
e03  --  tables and figures for Parts 2 and 3.
=============================================================================
  fig05  Part 2 grid: percentile x duration, counts / per-county exposure /
         seasonality / day-level agreement among the nine definitions
  fig06  Part 2 seasonality: monthly classification RATE per definition
  fig07  THE FLOOR FIGURE: what an 80 degF and a 90 degF floor do to each of the
         nine relative definitions -- how many days survive, and whether the
         cool-season loading survives with them
  fig08  absolute-only vs county-relative: the two constructs side by side
  fig09  where the floor bites: per-county day loss, mapped

Tables: tables/e03_*.csv

UNITS AND CONVENTIONS carried from the rest of the project: heatwave day =
county-date inside a qualifying run; event = one uninterrupted run in one
county; duration = integer days; pooled cross-county totals are QA quantities
and are suffixed accordingly; per-county medians are the substantive figure;
rates use ELIGIBLE county-days as the denominator, not calendar days.

Jaccard here is agreement between two definitions on the SET of classified
(county, date) heatwave days. It is not accuracy: nothing in this data observes
a "true" heatwave day.
=============================================================================
"""
import os
import sys
import time
import itertools

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etx_config as K
import config as C

STATE = K.TEST_STATE
P = K.PRIMARY_WINDOW
YEARS = "%d-%d" % C.ANALYSIS_YEARS
DATE0 = np.datetime64("2015-01-01", "D")
_CTY = {}


def tidy(ax, grid_axis="y"):
    ax.set_axisbelow(True)
    if grid_axis:
        ax.grid(axis=grid_axis, color=K.COLOR_GRID, lw=0.6, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#999999")
    ax.tick_params(colors=K.COLOR_INK_SOFT, labelsize=8)
    return ax


def savefig(fig, name):
    p = os.path.join(K.DIR_FIG, name)
    fig.savefig(p, bbox_inches="tight", facecolor="white", dpi=140)
    plt.close(fig)
    K.log("      -> figures/%s" % name)


def footnote(fig, text, y=0.005):
    fig.text(0.005, y, text, fontsize=6.8, color=K.COLOR_INK_SOFT, va="bottom", wrap=True)


# =============================================================================
# loading
# =============================================================================
def run_tables_dir(definition_id):
    return os.path.join(K.PKG_ROOT, "runs", definition_id, "tables")


def load_day_set(definition_id, window):
    p = os.path.join(run_tables_dir(definition_id), "daily_heatwave_days_%s.csv.gz" % window)
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p, usecols=["county_fips", "date"], dtype={"county_fips": str})
    for c in pd.unique(d["county_fips"]):
        _CTY.setdefault(c, len(_CTY))
    ci = d["county_fips"].map(_CTY).to_numpy(dtype=np.int64)
    do = (pd.to_datetime(d["date"]).to_numpy(dtype="datetime64[D]") - DATE0).astype(np.int64)
    return np.unique(ci * 100000 + do)


def jaccard(a, b):
    if a is None or b is None:
        return np.nan
    inter = np.intersect1d(a, b, assume_unique=True).size
    union = a.size + b.size - inter
    return inter / union if union else np.nan


def load_county_month(definition_id, window):
    p = os.path.join(run_tables_dir(definition_id), "county_month_summary_%s.csv" % window)
    if not os.path.exists(p):
        return None
    return pd.read_csv(p, dtype={"county_fips": str})


def load_county_year(definition_id, window):
    p = os.path.join(run_tables_dir(definition_id), "county_year_summary_%s.csv" % window)
    if not os.path.exists(p):
        return None
    return pd.read_csv(p, dtype={"county_fips": str})


def eligibility():
    """Valid-day denominators, reused from the definition-comparison package.

    Those were built for the same metric, state and analysis years by the same
    pipeline, so reusing them keeps one definition of "eligible day" across both
    packages instead of inventing a second one.
    """
    p = os.path.join(K.REPO_ROOT, "outputs", "definition_comparison", "tables",
                     "eligibility_county_month.csv")
    if not os.path.exists(p):
        return None
    e = pd.read_csv(p, dtype={"county_fips": str})
    return e[(e["metric"] == "TMAX") & (e["window"] == P)]


def ref_counties():
    p = os.path.join(K.REPO_ROOT, "outputs", STATE, "coverage_and_imputation_report.csv")
    r = pd.read_csv(p, dtype={"county_fips": str})
    r["fully_imputed_county"] = (r["fully_imputed_county"].astype(str).str.lower()
                                 .isin(("true", "1", "yes")))
    return r


def label_of(pctl, dur):
    return "P%d.%dD" % (pctl, dur)


# =============================================================================
# tables
# =============================================================================
def t_part2_grid(m):
    """Percentile x duration, at every window: the Part-2 answer in table form."""
    p2 = m[(m["part"] == 2)].copy()
    p2["cell"] = p2.apply(lambda r: label_of(r["percentile"], r["minimum_duration_days"]),
                          axis=1)
    keep = ["definition_id", "cell", "percentile", "minimum_duration_days", "window",
            "candidate_days_QA_pooled", "heatwave_days_QA_pooled_2015_2025",
            "heatwave_events_QA_pooled_2015_2025", "per_county_heatwave_days_median",
            "per_county_heatwave_days_min", "per_county_heatwave_days_max",
            "event_duration_days_median", "event_duration_days_max",
            "heatwave_days_per_1000_eligible", "pct_heatwave_days_in_jun_sep",
            "pct_heatwave_days_outside_jun_sep", "peak_month"]
    out = p2[keep].sort_values(["window", "percentile", "minimum_duration_days"])
    out.to_csv(os.path.join(K.DIR_TABLES, "e03_part2_percentile_duration_grid.csv"),
               index=False)
    K.log("[table] e03_part2_percentile_duration_grid.csv  (%d rows)" % len(out))
    return out


def t_floor_effect(m, sets):
    """What each floor does to each relative definition, at the primary window."""
    rows = []
    base = m[(m["part"] == 2) & (m["window"] == P)]
    for _, b in base.iterrows():
        pctl, dur = b["percentile"], b["minimum_duration_days"]
        b_set = sets.get(b["definition_id"])
        for floor in K.FLOORS_F:
            fid = K.definition_id(pctl, dur, floor_f=floor)
            f = m[(m["definition_id"] == fid) & (m["window"] == P)]
            if not len(f):
                continue
            f = f.iloc[0]
            f_set = sets.get(fid)
            rows.append({
                "cell": label_of(pctl, dur), "percentile": pctl,
                "minimum_duration_days": dur, "window": P, "floor_degF": floor,
                "definition_no_floor": b["definition_id"], "definition_with_floor": fid,
                "heatwave_days_no_floor_QA": int(b["heatwave_days_QA_pooled_2015_2025"]),
                "heatwave_days_with_floor_QA": int(f["heatwave_days_QA_pooled_2015_2025"]),
                "pct_days_retained": round(
                    100.0 * f["heatwave_days_QA_pooled_2015_2025"]
                    / b["heatwave_days_QA_pooled_2015_2025"], 2)
                if b["heatwave_days_QA_pooled_2015_2025"] else np.nan,
                "events_no_floor_QA": int(b["heatwave_events_QA_pooled_2015_2025"]),
                "events_with_floor_QA": int(f["heatwave_events_QA_pooled_2015_2025"]),
                "per_county_median_no_floor": int(b["per_county_heatwave_days_median"]),
                "per_county_median_with_floor": int(f["per_county_heatwave_days_median"]),
                "counties_with_any_day_no_floor": int(b["counties_with_any_heatwave_day"]),
                "counties_with_any_day_with_floor": int(f["counties_with_any_heatwave_day"]),
                "pct_outside_jun_sep_no_floor": b["pct_heatwave_days_outside_jun_sep"],
                "pct_outside_jun_sep_with_floor": f["pct_heatwave_days_outside_jun_sep"],
                "pct_outside_jun_sep_change": round(
                    f["pct_heatwave_days_outside_jun_sep"]
                    - b["pct_heatwave_days_outside_jun_sep"], 2),
                "peak_month_no_floor": b["peak_month"],
                "peak_month_with_floor": f["peak_month"],
                "event_duration_median_no_floor": b["event_duration_days_median"],
                "event_duration_median_with_floor": f["event_duration_days_median"],
                "jaccard_with_vs_without_floor": round(jaccard(b_set, f_set), 4),
            })
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(K.DIR_TABLES, "e03_floor_effect.csv"), index=False)
    K.log("[table] e03_floor_effect.csv  (%d definition x floor rows)" % len(out))
    return out


def t_absolute_vs_relative(m, sets):
    """The absolute-only construct against the matched relative definitions."""
    rows = []
    ab = m[m["kind"] == K.FLOOR_MODE_ABSOLUTE]
    for _, a in ab.iterrows():
        a_set = sets.get(a["definition_id"])
        for pctl in K.EXTREME_PERCENTILES:
            rid = K.definition_id(pctl, a["minimum_duration_days"])
            r = m[(m["definition_id"] == rid) & (m["window"] == P)]
            if not len(r):
                continue
            r = r.iloc[0]
            r_set = sets.get(rid)
            inter = (np.intersect1d(a_set, r_set, assume_unique=True).size
                     if a_set is not None and r_set is not None else np.nan)
            rows.append({
                "absolute_definition": a["definition_id"],
                "floor_degF": a["absolute_floor_degF"],
                "minimum_duration_days": a["minimum_duration_days"],
                "relative_definition": rid, "percentile": pctl, "window": P,
                "heatwave_days_absolute_QA": int(a["heatwave_days_QA_pooled_2015_2025"]),
                "heatwave_days_relative_QA": int(r["heatwave_days_QA_pooled_2015_2025"]),
                "ratio_absolute_over_relative": round(
                    a["heatwave_days_QA_pooled_2015_2025"]
                    / r["heatwave_days_QA_pooled_2015_2025"], 3)
                if r["heatwave_days_QA_pooled_2015_2025"] else np.nan,
                "per_county_median_absolute": int(a["per_county_heatwave_days_median"]),
                "per_county_median_relative": int(r["per_county_heatwave_days_median"]),
                "pct_outside_jun_sep_absolute": a["pct_heatwave_days_outside_jun_sep"],
                "pct_outside_jun_sep_relative": r["pct_heatwave_days_outside_jun_sep"],
                "county_dates_shared": int(inter) if inter == inter else np.nan,
                "county_dates_absolute_only": (int(a_set.size - inter)
                                               if a_set is not None and inter == inter
                                               else np.nan),
                "county_dates_relative_only": (int(r_set.size - inter)
                                               if r_set is not None and inter == inter
                                               else np.nan),
                "jaccard_absolute_vs_relative": round(jaccard(a_set, r_set), 4),
            })
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(K.DIR_TABLES, "e03_absolute_vs_relative.csv"), index=False)
    K.log("[table] e03_absolute_vs_relative.csv  (%d rows)" % len(out))
    return out


def t_agreement(m, sets):
    """Day-level agreement among every definition available at the primary window
    (relative, floored and absolute together)."""
    ids = [d for d in m.loc[(m["window"] == P) | (m["window"] == "none"),
                            "definition_id"].unique() if d in sets]
    ids = sorted(ids, key=lambda d: (0 if "ABS" not in d else 1, d))
    M = pd.DataFrame(np.nan, index=ids, columns=ids)
    for a in ids:
        M.loc[a, a] = 1.0
    for a, b in itertools.combinations(ids, 2):
        M.loc[a, b] = M.loc[b, a] = round(jaccard(sets[a], sets[b]), 4)
    M.to_csv(os.path.join(K.DIR_TABLES, "e03_agreement_matrix.csv"))
    K.log("[table] e03_agreement_matrix.csv  (%dx%d)" % M.shape)
    return M


def t_monthly_rates(m, elig):
    """Heatwave days per 1,000 eligible county-days, by definition x month."""
    if elig is None:
        return None
    em = elig.groupby("month", as_index=False)["eligible_days"].sum()
    rows = []
    for _, r in m.iterrows():
        cm = load_county_month(r["definition_id"], r["window"])
        if cm is None or not len(cm):
            continue
        by = cm.groupby("month")["heatwave_days"].sum().reindex(range(1, 13), fill_value=0)
        for mo in range(1, 13):
            e = float(em.loc[em["month"] == mo, "eligible_days"].iloc[0])
            rows.append({"definition_id": r["definition_id"], "window": r["window"],
                         "kind": r["kind"], "part": r["part"],
                         "percentile": r["percentile"],
                         "minimum_duration_days": r["minimum_duration_days"],
                         "floor_degF": r["absolute_floor_degF"], "month": mo,
                         "heatwave_days": int(by[mo]), "eligible_county_days": int(e),
                         "days_per_1000_eligible": round(1000.0 * by[mo] / e, 3)})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(K.DIR_TABLES, "e03_monthly_rates.csv"), index=False)
    K.log("[table] e03_monthly_rates.csv  (%d rows)" % len(out))
    return out


def t_county_floor_effect(m, ref):
    """Per county: days lost when each floor is applied (the geography of the floor)."""
    rows = []
    for pctl in K.EXTREME_PERCENTILES:
        for dur in K.EXTREME_DURATIONS:
            base = load_county_year(K.definition_id(pctl, dur), P)
            if base is None:
                continue
            b = base.groupby("county_fips")["heatwave_days"].sum()
            for floor in K.FLOORS_F:
                f = load_county_year(K.definition_id(pctl, dur, floor_f=floor), P)
                fv = (f.groupby("county_fips")["heatwave_days"].sum() if f is not None
                      else pd.Series(dtype=float))
                idx = sorted(ref["county_fips"].unique())
                bb = b.reindex(idx, fill_value=0)
                ff = fv.reindex(idx, fill_value=0)
                t = pd.DataFrame({"county_fips": idx, "days_no_floor": bb.to_numpy(),
                                  "days_with_floor": ff.to_numpy()})
                t["days_lost"] = t["days_no_floor"] - t["days_with_floor"]
                t["pct_retained"] = (100.0 * t["days_with_floor"]
                                     / t["days_no_floor"].replace(0, np.nan)).round(2)
                t["cell"] = label_of(pctl, dur)
                t["percentile"] = pctl
                t["minimum_duration_days"] = dur
                t["floor_degF"] = floor
                rows.append(t)
    out = pd.concat(rows, ignore_index=True).merge(
        ref[["county_fips", "county_name", "pct_analysis_days_imputed",
             "fully_imputed_county"]], on="county_fips", how="left")
    out.to_csv(os.path.join(K.DIR_TABLES, "e03_county_floor_effect.csv"), index=False)
    K.log("[table] e03_county_floor_effect.csv  (%d rows)" % len(out))
    return out


# =============================================================================
# figures
# =============================================================================
def fig05_part2_grid(grid, M):
    g = grid[grid["window"] == P]
    pct, dur = K.EXTREME_PERCENTILES, K.EXTREME_DURATIONS
    fields = [("per_county_heatwave_days_median", "per-county median heatwave days", "%.0f"),
              ("heatwave_events_QA_pooled_2015_2025", "heatwave events (QA pooled)", "%.0f"),
              ("event_duration_days_median", "median event duration (days)", "%.1f"),
              ("pct_heatwave_days_outside_jun_sep", "% of heatwave days outside Jun-Sep",
               "%.0f")]
    fig, axs = plt.subplots(1, 4, figsize=(18.0, 4.5))
    for ax, (field, title, fmt) in zip(axs, fields):
        A = np.full((len(pct), len(dur)), np.nan)
        for i, p in enumerate(pct):
            for j, d in enumerate(dur):
                s = g[(g["percentile"] == p) & (g["minimum_duration_days"] == d)]
                if len(s):
                    A[i, j] = float(s[field].iloc[0])
        im = ax.imshow(A, cmap=K.CMAP_SEQUENTIAL, aspect="auto")
        ax.set_xticks(range(len(dur)))
        ax.set_xticklabels([">=%d d" % d for d in dur], fontsize=9)
        ax.set_yticks(range(len(pct)))
        ax.set_yticklabels(["%dth" % p for p in pct], fontsize=9)
        for i in range(len(pct)):
            for j in range(len(dur)):
                if np.isfinite(A[i, j]):
                    ax.text(j, i, fmt % A[i, j], ha="center", va="center", fontsize=9.5,
                            color=("white" if A[i, j] > 0.62 * np.nanmax(A) else "#222222"),
                            fontweight="bold")
        ax.set_title(title, fontsize=9.5, fontweight="bold")
        ax.set_xlabel("minimum duration")
        if ax is axs[0]:
            ax.set_ylabel("percentile of the county's own\nwalk-forward Tmax distribution")
    fig.suptitle("Figure E5  Part 2 - county-relative daily MAXIMUM temperature: "
                 "percentile x minimum duration (%s window, %s, %s)"
                 % (P, K.STATE_LABEL[STATE], YEARS),
                 fontsize=12.5, fontweight="bold", y=1.04, x=0.005, ha="left")
    footnote(fig, "units: per-county median heatwave DAYS is the substantive county-level "
                  "figure; the event count is pooled across counties and is a QA quantity; "
                  "event duration is an integer number of consecutive dates (median across "
                  "events). All nine cells share the same walk-forward baseline, strict '>', "
                  "year-round season and no absolute floor, so the only things varying are the "
                  "percentile and the persistence rule.", y=-0.06)
    savefig(fig, "e03_fig05_part2_percentile_duration_grid.png")

    # agreement among the nine, plus the floored and absolute definitions
    rel9 = [K.definition_id(p, d) for p in pct for d in dur]
    ids = [i for i in rel9 if i in M.index]
    fig, ax = plt.subplots(figsize=(8.4, 7.2))
    A = M.loc[ids, ids].to_numpy(dtype=float)
    im = ax.imshow(A, cmap=K.CMAP_SEQUENTIAL, vmin=0, vmax=1)
    lab = [i.replace("TMAX_", "") for i in ids]
    ax.set_xticks(range(len(ids))); ax.set_xticklabels(lab, rotation=90, fontsize=7.5)
    ax.set_yticks(range(len(ids))); ax.set_yticklabels(lab, fontsize=7.5)
    for i in range(len(ids)):
        for j in range(len(ids)):
            if np.isfinite(A[i, j]):
                ax.text(j, i, ("%.2f" % A[i, j]).lstrip("0") if A[i, j] < 1 else "1",
                        ha="center", va="center", fontsize=6.5,
                        color=("white" if A[i, j] > 0.6 else "#222222"))
    fig.colorbar(im, ax=ax, shrink=0.75,
                 label="Jaccard on the set of (county, date) heatwave days")
    ax.set_title("Figure E5b  Do the nine Part-2 definitions classify the same days?\n"
                 "%s window, %s - fixed 0-1 scale" % (P, YEARS),
                 fontsize=11, fontweight="bold", loc="left")
    footnote(fig, "unit: the SET of (county, date) heatwave days. Agreement, not accuracy. "
                  "Percentile and duration are both nested rules here, so the high values "
                  "along the diagonal blocks are structural: a stricter percentile or a longer "
                  "run can only ever remove days.")
    savefig(fig, "e03_fig05b_part2_agreement.png")


def fig06_part2_seasonality(rates):
    g = rates[(rates["part"] == 2) & (rates["window"] == P)]
    pct, dur = K.EXTREME_PERCENTILES, K.EXTREME_DURATIONS
    fig, axs = plt.subplots(1, 3, figsize=(15.5, 4.8), sharey=True)
    for ax, d in zip(axs, dur):
        for p in pct:
            s = g[(g["percentile"] == p) & (g["minimum_duration_days"] == d)] \
                .sort_values("month")
            if not len(s):
                continue
            ax.plot(s["month"], s["days_per_1000_eligible"], color="#C44E52",
                    ls=K.PCTL_STYLE[p]["ls"], lw=1.9, marker="^", ms=5,
                    label="%s percentile" % K.PCTL_STYLE[p]["label"], zorder=3)
        ax.axvspan(5.5, 9.5, color=K.COLOR_WARN, alpha=0.07, zorder=0)
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
        ax.set_title(">= %d consecutive days" % d, fontsize=10, fontweight="bold")
        ax.set_xlabel("calendar month")
        tidy(ax, grid_axis="both")
    axs[0].set_ylabel("heatwave days per 1,000\neligible county-days")
    axs[0].legend(fontsize=8, title="percentile", title_fontsize=8)
    axs[1].text(7.5, axs[1].get_ylim()[1] * 0.97, "Jun-Sep", ha="center", va="top",
                fontsize=8.5, color=K.COLOR_WARN)
    fig.suptitle("Figure E6  Part 2 seasonality - a year-round relative Tmax rule spreads "
                 "across the calendar (%s window, %s)" % (P, YEARS),
                 fontsize=12.5, fontweight="bold", y=1.03, x=0.005, ha="left")
    footnote(fig, "unit: county-month, pooled over counties and years; denominator is ELIGIBLE "
                  "county-days so months of unequal length and coverage are comparable. The "
                  "rate is nearly flat across the calendar because the threshold is estimated "
                  "from each date's OWN history - which is exactly what an absolute floor "
                  "changes (Figure E7).", y=-0.06)
    savefig(fig, "e03_fig06_part2_seasonality.png")


def fig07_floor_effect(fl, rates):
    cells = [label_of(p, d) for p in K.EXTREME_PERCENTILES for d in K.EXTREME_DURATIONS]
    fig = plt.figure(figsize=(16.5, 10.4))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.05], hspace=0.42, wspace=0.22)

    # --- A: how many days survive the floor -------------------------------
    ax = fig.add_subplot(gs[0, 0])
    x = np.arange(len(cells))
    for k, floor in enumerate(K.FLOORS_F):
        v = [float(fl.loc[(fl["cell"] == c) & (fl["floor_degF"] == floor),
                          "pct_days_retained"].iloc[0])
             if len(fl[(fl["cell"] == c) & (fl["floor_degF"] == floor)]) else np.nan
             for c in cells]
        st = K.FLOOR_STYLE[floor]
        ax.bar(x + (k - 0.5) * 0.4, v, width=0.38, color=st["color"], hatch=st["hatch"],
               edgecolor="white", lw=0.7, label=st["label"], zorder=3)
        for xi, vi in zip(x + (k - 0.5) * 0.4, v):
            ax.annotate("%.0f" % vi, (xi, vi), xytext=(0, 3), textcoords="offset points",
                        ha="center", fontsize=6.8, color=K.COLOR_INK)
    ax.set_xticks(x); ax.set_xticklabels(cells, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("% of heatwave days retained")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8)
    ax.set_title("A  how many heatwave days survive the floor", fontsize=10,
                 fontweight="bold", loc="left")
    tidy(ax)

    # --- B: does the cool-season loading survive? -------------------------
    ax = fig.add_subplot(gs[0, 1])
    base = [float(fl.loc[fl["cell"] == c, "pct_outside_jun_sep_no_floor"].iloc[0])
            for c in cells]
    ax.plot(x, base, lw=0, marker="o", ms=8, mfc="#C44E52", mec="white", mew=1,
            label="no floor", zorder=4)
    for k, floor in enumerate(K.FLOORS_F):
        v = [float(fl.loc[(fl["cell"] == c) & (fl["floor_degF"] == floor),
                          "pct_outside_jun_sep_with_floor"].iloc[0])
             if len(fl[(fl["cell"] == c) & (fl["floor_degF"] == floor)]) else np.nan
             for c in cells]
        st = K.FLOOR_STYLE[floor]
        ax.plot(x, v, lw=0, marker=("s" if floor == 80 else "D"), ms=7.5, mfc=st["color"],
                mec="white", mew=1, label=st["label"], zorder=4)
        for xi, a, b in zip(x, base, v):
            ax.annotate("", xy=(xi, b), xytext=(xi, a),
                        arrowprops=dict(arrowstyle="->", color=st["color"], lw=1.0,
                                        alpha=0.55), zorder=2)
    ax.axhline(50, color=K.COLOR_WARN, ls=":", lw=1.1, zorder=1)
    ax.text(len(cells) - 0.4, 51, "half the days outside Jun-Sep", fontsize=7,
            color=K.COLOR_WARN, ha="right")
    ax.set_xticks(x); ax.set_xticklabels(cells, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("% of heatwave days OUTSIDE Jun-Sep")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_title("B  does the cool-season loading survive the floor?", fontsize=10,
                 fontweight="bold", loc="left")
    tidy(ax)

    # --- C/D: monthly profile, no floor vs each floor ---------------------
    for j, (p, d) in enumerate(((90, 2), (85, 3))):
        ax = fig.add_subplot(gs[1, j])
        for floor in [None] + list(K.FLOORS_F):
            did = K.definition_id(p, d, floor_f=floor)
            s = rates[(rates["definition_id"] == did) & (rates["window"] == P)] \
                .sort_values("month")
            if not len(s):
                continue
            st = K.FLOOR_STYLE[floor]
            ax.plot(s["month"], s["days_per_1000_eligible"], color=st["color"], lw=2.0,
                    marker="^", ms=5.5, label=st["label"], zorder=3)
        ax.axvspan(5.5, 9.5, color=K.COLOR_WARN, alpha=0.07, zorder=0)
        ax.set_xticks(range(1, 13)); ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
        ax.set_ylabel("heatwave days per 1,000\neligible county-days")
        ax.set_xlabel("calendar month")
        ax.legend(fontsize=8)
        ax.set_title("%s  monthly profile, %s  (%dth percentile, >= %d days)"
                     % ("CD"[j], K.definition_id(p, d), p, d), fontsize=10,
                     fontweight="bold", loc="left")
        tidy(ax, grid_axis="both")

    fig.suptitle("Figure E7  Part 3a - what an absolute floor does to a county-relative "
                 "Tmax definition (%s window, %s, %s)"
                 % (P, K.STATE_LABEL[STATE], YEARS),
                 fontsize=13, fontweight="bold", y=0.985, x=0.005, ha="left")
    footnote(fig, "The floor is applied as a GATE: a day must clear BOTH its own "
                  "county/calendar percentile threshold AND the absolute floor (Tmax >= floor). "
                  "Panels A and B share the definition ordering. This is the figure that bears "
                  "on the project's open floor-or-season decision: panel B shows whether the "
                  "cool-season share falls, and panels C-D show which months are actually "
                  "removed. Note that a floor makes the definition PART absolute, so the "
                  "result is no longer 'unusual for this date' alone - it is 'unusual for this "
                  "date AND hot in absolute terms', a different construct that must be "
                  "described as such.", y=-0.005)
    savefig(fig, "e03_fig07_floor_effect.png")


def fig08_absolute_vs_relative(m, av, rates):
    fig, axs = plt.subplots(1, 3, figsize=(17.0, 5.0))
    # --- A: counts -------------------------------------------------------
    ax = axs[0]
    labels, vals, colors, hatches = [], [], [], []
    for floor in K.FLOORS_F:
        for d in K.EXTREME_DURATIONS:
            s = m[(m["definition_id"] == K.definition_id(None, d, floor_f=floor,
                                                         absolute_only=True))]
            if len(s):
                labels.append("ABS%d.%dD" % (floor, d))
                vals.append(int(s["per_county_heatwave_days_median"].iloc[0]))
                colors.append(K.FLOOR_STYLE[floor]["color"])
                hatches.append(K.FLOOR_STYLE[floor]["hatch"])
    for p in K.EXTREME_PERCENTILES:
        for d in K.EXTREME_DURATIONS:
            s = m[(m["definition_id"] == K.definition_id(p, d)) & (m["window"] == P)]
            if len(s):
                labels.append("P%d.%dD" % (p, d))
                vals.append(int(s["per_county_heatwave_days_median"].iloc[0]))
                colors.append("#C44E52")
                hatches.append(None)
    x = np.arange(len(labels))
    ax.bar(x, vals, color=colors, hatch=hatches, edgecolor="white", lw=0.6, zorder=3)
    ax.axhline(4018, color=K.COLOR_WARN, ls=":", lw=1.1)
    ax.text(len(labels) - 0.5, 4018 * 0.97, "every day in %s" % YEARS, fontsize=7,
            color=K.COLOR_WARN, ha="right", va="top")
    for xi, v in zip(x, vals):
        ax.annotate("%d" % v, (xi, v), xytext=(0, 3), textcoords="offset points",
                    ha="center", fontsize=6.5)
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=90, fontsize=7)
    ax.set_ylabel("per-county median heatwave days, %s" % YEARS)
    ax.set_title("A  how much each construct flags", fontsize=10, fontweight="bold",
                 loc="left")
    tidy(ax)
    # --- B: seasonality --------------------------------------------------
    ax = axs[1]
    for floor in K.FLOORS_F:
        did = K.definition_id(None, 2, floor_f=floor, absolute_only=True)
        s = rates[rates["definition_id"] == did].sort_values("month")
        if len(s):
            st = K.FLOOR_STYLE[floor]
            ax.plot(s["month"], s["days_per_1000_eligible"], color=st["color"], lw=2.2,
                    marker="D", ms=5.5, label="Tmax > %.0f degF (absolute)" % floor, zorder=3)
    for p in (90,):
        s = rates[(rates["definition_id"] == K.definition_id(p, 2))
                  & (rates["window"] == P)].sort_values("month")
        if len(s):
            ax.plot(s["month"], s["days_per_1000_eligible"], color="#C44E52", lw=2.2,
                    ls="-", marker="^", ms=5.5,
                    label="%dth percentile (relative)" % p, zorder=3)
    ax.axvspan(5.5, 9.5, color=K.COLOR_WARN, alpha=0.07, zorder=0)
    ax.set_xticks(range(1, 13)); ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
    ax.set_ylabel("heatwave days per 1,000\neligible county-days")
    ax.legend(fontsize=7.5)
    ax.set_title("B  when each construct fires (>= 2 days)", fontsize=10,
                 fontweight="bold", loc="left")
    tidy(ax, grid_axis="both")
    # --- C: agreement ----------------------------------------------------
    ax = axs[2]
    sub = av[av["minimum_duration_days"] == 2]
    x = np.arange(len(sub))
    ax.bar(x, sub["jaccard_absolute_vs_relative"], color="#4C72B0", edgecolor="white",
           lw=0.6, zorder=3)
    for xi, v in zip(x, sub["jaccard_absolute_vs_relative"]):
        ax.annotate("%.2f" % v, (xi, v), xytext=(0, 3), textcoords="offset points",
                    ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(["%s\nvs P%d" % (r["absolute_definition"].replace("TMAX_", ""),
                                        r["percentile"]) for _, r in sub.iterrows()],
                       fontsize=6.8)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Jaccard (day-level agreement)")
    ax.set_title("C  do the two constructs pick the same days?", fontsize=10,
                 fontweight="bold", loc="left")
    tidy(ax)
    fig.suptitle("Figure E8  Part 3b - absolute-only (Tmax > floor) against county-relative "
                 "percentile definitions, %s, %s" % (K.STATE_LABEL[STATE], YEARS),
                 fontsize=12.5, fontweight="bold", y=1.03, x=0.005, ha="left")
    footnote(fig, "An absolute rule has NO baseline and therefore no threshold window: there is "
                  "nothing to pool. Panel A is the substantive per-county median (dotted line = "
                  "the total number of days in the study period, for scale); panel B uses "
                  "eligible county-days as the denominator; panel C is agreement, not accuracy. "
                  "A definition that flags a large share of ALL days is not describing extremes "
                  "regardless of how it is labelled.", y=-0.05)
    savefig(fig, "e03_fig08_absolute_vs_relative.png")


def fig09_county_floor_map(cfe, ref):
    try:
        import geopandas as gpd
    except Exception as e:
        K.log("   [fig09] geopandas unavailable (%s) - map skipped" % e)
        return
    g = gpd.read_file(C.COUNTY_SHAPEFILE)
    g = g[g["STATEFP"] == C.STATE_FIPS[STATE]][["GEOID", "geometry"]] \
        .rename(columns={"GEOID": "county_fips"}).to_crs(C.EQUAL_AREA_CRS)
    cell = label_of(90, 2)
    fig, axs = plt.subplots(1, 3, figsize=(17.5, 6.2))
    sub0 = cfe[(cfe["cell"] == cell) & (cfe["floor_degF"] == K.FLOORS_F[0])]
    m0 = g.merge(sub0, on="county_fips", how="left")
    m0.plot(column="days_no_floor", cmap=K.CMAP_SEQUENTIAL, ax=axs[0], edgecolor="white",
            lw=0.25, legend=True,
            legend_kwds={"label": "heatwave days, no floor", "shrink": 0.6})
    axs[0].set_title("A  TMAX_%s, no floor" % cell, fontsize=10, fontweight="bold",
                     loc="left")
    for k, floor in enumerate(K.FLOORS_F, start=1):
        sub = cfe[(cfe["cell"] == cell) & (cfe["floor_degF"] == floor)]
        mm = g.merge(sub, on="county_fips", how="left")
        mm.plot(column="pct_retained", cmap=K.CMAP_SEQUENTIAL, ax=axs[k], edgecolor="white",
                lw=0.25, legend=True, vmin=0, vmax=100,
                legend_kwds={"label": "%% of days retained with a %.0f degF floor" % floor,
                             "shrink": 0.6},
                missing_kwds={"color": "#d9d9d9", "label": "no days either way"})
        axs[k].set_title("%s  with a %.0f degF floor" % ("BC"[k - 1], floor), fontsize=10,
                         fontweight="bold", loc="left")
    for ax in axs:
        ax.axis("off")
    fig.suptitle("Figure E9  Where an absolute floor bites - %s, %s, %s window"
                 % (K.STATE_LABEL[STATE], YEARS, P),
                 fontsize=12.5, fontweight="bold", y=1.0, x=0.005, ha="left")
    footnote(fig, "unit: county. A county-relative percentile rule flags a similar NUMBER of "
                  "days everywhere by construction (panel A is comparatively flat); an absolute "
                  "floor does not, because it asks whether the county reaches a fixed "
                  "temperature. The retained share therefore falls with latitude and elevation "
                  "- the floor converts a definition that treats every county alike into one "
                  "that concentrates exposure in the hottest parts of the state. That is a "
                  "substantive change in what is being measured, not a data-cleaning step.",
             y=-0.02)
    savefig(fig, "e03_fig09_county_floor_effect_map.png")


# =============================================================================
# driver
# =============================================================================
def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 78)
    K.log("e03  TABLES AND FIGURES for parts 2 and 3")
    K.log("=" * 78)
    m = pd.read_csv(os.path.join(K.DIR_TABLES, "e02_master_run_summary.csv"))
    ref = ref_counties()
    elig = eligibility()

    K.log("loading day-level sets ...")
    sets = {}
    for _, r in m.iterrows():
        if r["window"] in (P, "none"):
            s = load_day_set(r["definition_id"], r["window"])
            if s is not None:
                sets[r["definition_id"]] = s
    K.log("   %d day sets, %s county-dates total"
          % (len(sets), "{:,}".format(sum(len(v) for v in sets.values()))))

    grid = t_part2_grid(m)
    fl = t_floor_effect(m, sets)
    av = t_absolute_vs_relative(m, sets)
    M = t_agreement(m, sets)
    rates = t_monthly_rates(m, elig)
    cfe = t_county_floor_effect(m, ref)

    K.log("-" * 78)
    K.log("figures")
    fig05_part2_grid(grid, M)
    if rates is not None:
        fig06_part2_seasonality(rates)
        fig07_floor_effect(fl, rates)
        fig08_absolute_vs_relative(m, av, rates)
    fig09_county_floor_map(cfe, ref)
    K.log("e03 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
