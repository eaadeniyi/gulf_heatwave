"""
=============================================================================
s05  --  CORE FIGURES 1-7, 11 and 12.
=============================================================================
Every figure here reads a table written by s02/s04 and renders it. No figure
computes a statistic of its own, so a figure and its table cannot disagree.

  fig01  definition design matrix (incl. the two untested cells)
  fig02  matched-pair count change vs day-level agreement, faceted by axis
  fig03  16 x 16 day-level Jaccard heatmap at the primary window
  fig04  county-rank stability: all counties | complete-data counties
  fig05  monthly classification RATE heatmap (per 1,000 eligible county-days)
  fig06  percentile / duration ladder over individual county-year records
  fig07  threshold-window sensitivity (a: agreement, b: paired county-year
         differences, c: threshold curves for the example counties)
  fig11  data-quality influence: imputation vs count and vs rank
  fig12  definition-pair disagreement: county map + monthly profile, per pair

ENCODING, FIXED EVERYWHERE (see defcmp_config.METRIC_STYLE)
  metric      colour AND marker AND hatch AND a text label. Never colour alone:
              Tmax and mean HI are only dE 7.3 apart under simulated
              deuteranopia, which is legal only with a second channel.
  percentile  line style (dotted 85th, dashed 90th, solid 95th)
  duration    marker fill (filled >=2 days, open >=3 days)
  window      position / panel, or a neutral grey ramp
  magnitude   one-hue sequential ramp; signed differences a two-hue diverging
              ramp with a neutral midpoint, deliberately not the metric hues
  untested    a single flat grey, labelled "not tested" -- never zero, never
              interpolated across
=============================================================================
"""
import os
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defcmp_config as K
import defcmp_common as U
import config as C

STATE = K.STATE
YEARS = "%d-%d" % C.ANALYSIS_YEARS
plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "figure.dpi": 110,
                     "axes.edgecolor": "#999999", "text.color": K.COLOR_INK,
                     "axes.labelcolor": K.COLOR_INK, "savefig.facecolor": "white"})


def defs_in_matrix_order():
    order = K.def_order()
    dmap = {d["definition_id"]: d for d in K.definitions_expanded()}
    return [dmap[d] for d in order]


# =============================================================================
# FIGURE 1 -- definition design matrix
# =============================================================================
def fig01_design_matrix(reg):
    cols = [("definition_id", "definition"), ("metric", "metric"),
            ("percentile", "pctl"), ("minimum_duration_days", "min\ndays"),
            ("round", "round"), ("windows_available", "windows available"),
            ("input_comparability_short", "input comparability"), ("status", "status")]
    r = reg.copy()
    r["input_comparability_short"] = np.where(
        r["status"] == "NOT TESTED", "n/a - never run",
        "identical: input hash, boundaries,\nIDW, baseline, '>', season, no floor")
    # tested definitions in matrix order, then the untested cells at the bottom
    order = K.def_order()
    r["__ord"] = r["definition_id"].map({d: i for i, d in enumerate(order)}).fillna(999)
    r = r.sort_values(["__ord", "definition_id"])

    nrow, ncol = len(r), len(cols)
    fig, ax = plt.subplots(figsize=(13.5, 0.42 * nrow + 2.0))
    ax.set_xlim(0, ncol)
    ax.set_ylim(0, nrow + 1.4)
    ax.axis("off")
    widths = [1.35, 0.95, 0.5, 0.5, 1.15, 1.5, 1.85, 1.25]
    widths = [w / sum(widths) * ncol for w in widths]
    xs = np.concatenate([[0], np.cumsum(widths)])

    for j, (_, hdr) in enumerate(cols):
        ax.text(xs[j] + 0.06, nrow + 0.55, hdr, fontsize=8.5, fontweight="bold",
                va="center", ha="left", color=K.COLOR_INK)
    ax.plot([0, ncol], [nrow + 0.2, nrow + 0.2], color="#666666", lw=1.2)

    for i, (_, row) in enumerate(r.iterrows()):
        y = nrow - i - 0.5
        untested = row["status"] == "NOT TESTED"
        if untested:
            ax.add_patch(Rectangle((0, y - 0.5), ncol, 1.0, facecolor=K.COLOR_NOT_TESTED,
                                   edgecolor="none", alpha=0.75, zorder=0))
        elif i % 2 == 0:
            ax.add_patch(Rectangle((0, y - 0.5), ncol, 1.0, facecolor="#f6f6f6",
                                   edgecolor="none", zorder=0))
        for j, (field, _) in enumerate(cols):
            v = row[field]
            x = xs[j] + 0.06
            if field == "metric":
                st = K.METRIC_STYLE[row["metric"]]
                ax.add_patch(Rectangle((x, y - 0.30), 0.16, 0.60,
                                       facecolor=("none" if untested else st["color"]),
                                       edgecolor=st["color"],
                                       hatch=(None if untested else st["hatch"]),
                                       lw=1.0, alpha=0.95, zorder=2))
                ax.plot([x + 0.08], [y], marker=st["marker"], ms=4.5,
                        color=("#ffffff" if not untested else st["color"]), zorder=3)
                ax.text(x + 0.24, y, st["short"], fontsize=8, va="center", ha="left",
                        color=(K.COLOR_INK_SOFT if untested else K.COLOR_INK))
                continue
            txt = "" if pd.isna(v) else str(v)
            if field == "definition_id":
                num = row["def_number"]
                pre = "Def %02d  " % int(num) if str(num).strip() not in ("", "nan") else "(none)  "
                txt = pre + txt
            weight = "bold" if field in ("definition_id", "status") else "normal"
            color = K.COLOR_INK_SOFT if untested else K.COLOR_INK
            if field == "status" and untested:
                color = "#8a4b08"
            ax.text(x, y, txt, fontsize=7.6, va="center", ha="left", color=color,
                    fontweight=weight, linespacing=1.15)

    ax.set_title("Figure 1  Definition design matrix - %d heatwave definitions, %s, %s\n"
                 "the two mean-HI 3-day cells were never run and are shown as NOT TESTED, "
                 "not as zero" % (len(K.DEFINITIONS), K.STATE_LABEL, YEARS),
                 fontsize=11.5, fontweight="bold", loc="left", pad=14)
    U.footnote(fig, "unit of analysis: one definition (metric x percentile x minimum duration). "
                    "'windows available' lists the threshold windows actually run. A complete "
                    "3 metrics x 3 percentiles x 2 durations factorial would have 18 "
                    "definitions; 16 were run.")
    U.savefig(fig, os.path.join(K.DIR_FIG_CORE, "fig01_definition_design_matrix.png"))


# =============================================================================
# FIGURE 2 -- count change vs day-level agreement, per axis
# =============================================================================
def fig02_count_vs_agreement(marg, summary):
    axes_order = list(summary.sort_values("jaccard_median")["axis"])
    fig, axs = plt.subplots(1, len(axes_order), figsize=(4.0 * len(axes_order), 4.6),
                           sharey=True, sharex=True)
    xmax = float(marg["pct_count_difference"].max()) * 1.08
    for k, (ax, axis) in enumerate(zip(np.atleast_1d(axs), axes_order)):
        sub = marg[marg["axis"] == axis]
        s = summary[summary["axis"] == axis].iloc[0]
        for _, p in sub.iterrows():
            mc = str(p["metric_held"]) if p["metric_held"] in K.METRIC_STYLE else None
            st = K.METRIC_STYLE.get(mc, {"color": K.COLOR_INK_SOFT, "marker": "s"})
            ax.plot(p["pct_count_difference"], p["jaccard_day_level"],
                    marker=st["marker"], ms=7.5, mfc=st["color"], mec="white", mew=0.9,
                    lw=0, alpha=0.9, zorder=3)
        ax.axhline(s["jaccard_median"], color="#333333", ls="-", lw=1.1, zorder=2)
        ax.text(xmax * 0.98, s["jaccard_median"] + 0.018, "median %.3f" % s["jaccard_median"],
                fontsize=7.5, ha="right", va="bottom", color="#333333",
                bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.6))
        ax.axvline(s["count_ratio_median"] * 100 - 100, color="#333333", ls=":", lw=1.0, zorder=2)
        # the yardsticks are labelled ONCE, in the left panel, so the labels cannot
        # collide with the per-panel median annotation in the other three
        for name, v in K.YARDSTICKS.items():
            ax.axhline(v, color="#8a4b08", ls="--", lw=0.9, zorder=1)
            if k == 0:
                ax.text(xmax * 0.02, v - 0.045, name, fontsize=6.2, color="#8a4b08")
        ax.set_title("%s\n%d matched pairs | median ratio %.2fx"
                     % (axis.upper(), int(s["n_matched_pairs"]), s["count_ratio_median"]),
                     fontsize=9.5, fontweight="bold")
        ax.set_xlabel("count difference (%)")
        ax.set_ylim(0, 1.03)
        ax.set_xlim(-2, xmax)
        U.tidy_axes(ax, grid_axis="both")
    np.atleast_1d(axs)[0].set_ylabel("Jaccard index (day-level agreement)")
    handles = U.metric_legend_handles() + [
        Line2D([0], [0], color=K.COLOR_INK_SOFT, marker="s", lw=0, ms=7,
               label="metric axis (no single metric held)"),
        Line2D([0], [0], color="#8a4b08", ls="--", lw=1, label="earlier-round yardsticks")]
    np.atleast_1d(axs)[-1].legend(handles=handles, fontsize=6.8, loc="lower right",
                                 framealpha=0.95, title="metric held fixed",
                                 title_fontsize=7)
    fig.suptitle("Figure 2  Changing ONE definition axis: how much the COUNT moves vs how much "
                 "the CLASSIFIED DAYS move", fontsize=12, fontweight="bold", y=1.02)
    U.footnote(fig, "unit of analysis: one matched pair of runs (identical on the other three "
                    "axes). x = percentage difference in pooled heatwave days (QA quantity), "
                    "y = Jaccard on the SET of (county, date) heatwave days. Jaccard measures "
                    "AGREEMENT between two definitions, not accuracy of either: there is no "
                    "observed true heatwave day in this data. Yardsticks are this project's "
                    "earlier sensitivity results (walk-forward vs fixed baseline 0.923; "
                    "anchor vs composite temperature 0.45-0.73).", y=-0.02)
    U.savefig(fig, os.path.join(K.DIR_FIG_CORE, "fig02_count_change_vs_agreement.png"))


# =============================================================================
# shared matrix renderer (figures 3 and 4)
# =============================================================================
def _matrix_panel(ax, M, labels, dmeta, cmap, vmin, vmax, annotate=True, fontsize=5.6):
    im = ax.imshow(M, cmap=cmap, vmin=vmin, vmax=vmax)
    n = len(labels)
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(labels, rotation=90, fontsize=6.4)
    ax.set_yticklabels(labels, fontsize=6.4)
    for i, lab in enumerate(labels):
        mc = lab.split(".")[0]
        col = K.METRIC_STYLE[mc]["color"]
        ax.get_xticklabels()[i].set_color(col)
        ax.get_yticklabels()[i].set_color(col)
    for b in K.metric_family_boundaries():
        ax.axhline(b - 0.5, color="white", lw=2.0)
        ax.axvline(b - 0.5, color="white", lw=2.0)
        ax.axhline(b - 0.5, color="#222222", lw=0.9)
        ax.axvline(b - 0.5, color="#222222", lw=0.9)
    if annotate:
        norm = plt.Normalize(vmin, vmax)
        for i in range(n):
            for j in range(n):
                v = M[i, j]
                if np.isnan(v):
                    continue
                ax.text(j, i, ("%.2f" % v).lstrip("0") if v < 1 else "1",
                        ha="center", va="center", fontsize=fontsize,
                        color=("white" if norm(v) > 0.6 else "#222222"))
    ax.set_xticks(np.arange(-0.5, n, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n, 1), minor=True)
    ax.grid(which="minor", color="white", lw=0.6)
    ax.tick_params(which="minor", length=0)
    return im


def _labels_for(ids, dmeta):
    return ["%s.P%d.%dD" % (dmeta[i]["metric_code"], dmeta[i]["percentile"],
                            dmeta[i]["min_duration"]) for i in ids]


def fig03_jaccard_heatmap(J):
    dmeta = {d["definition_id"]: d for d in K.definitions_expanded()}
    ids = [d for d in K.def_order() if d in J.index]
    M = J.loc[ids, ids].to_numpy(dtype=float)
    labels = _labels_for(ids, dmeta)
    fig, ax = plt.subplots(figsize=(11.2, 9.6))
    im = _matrix_panel(ax, M, labels, dmeta, K.CMAP_SEQUENTIAL, 0.0, 1.0)
    cb = fig.colorbar(im, ax=ax, shrink=0.62, pad=0.02)
    cb.set_label("Jaccard index (shared county-dates / union), fixed 0-1 scale", fontsize=8)
    ax.set_title("Figure 3  Do two definitions classify the SAME county-dates?\n"
                 "day-level agreement between all %d definitions at the %s window, %s, %s"
                 % (len(ids), K.PRIMARY_WINDOW, K.STATE_LABEL, YEARS),
                 fontsize=11.5, fontweight="bold", loc="left")
    off = np.mean([1.0])
    U.footnote(fig, "unit of analysis: the SET of (county, date) heatwave days. Rows/columns are "
                    "ordered by metric, then percentile, then minimum duration; black lines "
                    "separate the metric families and tick labels carry the metric colour. "
                    "Jaccard is agreement, NOT accuracy - neither definition is a gold "
                    "standard. High agreement here does not imply similar county rankings, and "
                    "similar county rankings do not imply high agreement here (Figure 4).")
    U.savefig(fig, os.path.join(K.DIR_FIG_CORE, "fig03_jaccard_heatmap_primary_window.png"))


def fig04_rank_stability(S_all, S_cmp, n_all, n_cmp):
    dmeta = {d["definition_id"]: d for d in K.definitions_expanded()}
    ids = [d for d in K.def_order() if d in S_all.index]
    labels = _labels_for(ids, dmeta)
    fig, axs = plt.subplots(1, 2, figsize=(19.5, 9.2))
    for ax, S, title, n in ((axs[0], S_all, "A  all counties", n_all),
                            (axs[1], S_cmp, "B  counties with <= %.0f%% imputed temperature"
                             % K.IMPUTATION_MAX_PCT, n_cmp)):
        M = S.loc[ids, ids].to_numpy(dtype=float)
        im = _matrix_panel(ax, M, labels, dmeta, K.CMAP_SEQUENTIAL, 0.0, 1.0, fontsize=5.2)
        ax.set_title("%s  (n = %d counties)" % (title, n), fontsize=10, fontweight="bold",
                     loc="left")
    cb = fig.colorbar(im, ax=axs, shrink=0.55, pad=0.015)
    cb.set_label("Spearman rho of per-county heatwave-day totals, fixed 0-1 scale", fontsize=8)
    fig.suptitle("Figure 4  Do the definitions rank COUNTIES the same way?  %s, %s"
                 % (K.STATE_LABEL, YEARS), fontsize=12.5, fontweight="bold", x=0.02, ha="left")
    U.footnote(fig, "unit of analysis: county (cumulative %s heatwave days per county, not "
                    "annual). Panel B repeats panel A on the prespecified complete-data "
                    "subset. A HIGH rho here with a LOW Jaccard in Figure 3 means the "
                    "definitions disagree about WHICH DAYS are heatwave days while still "
                    "ordering counties similarly - rank agreement is not day-level agreement, "
                    "and neither is accuracy." % YEARS)
    U.savefig(fig, os.path.join(K.DIR_FIG_CORE, "fig04_county_rank_stability.png"))


# =============================================================================
# FIGURE 5 -- monthly classification RATE
# =============================================================================
def fig05_monthly_rate(rates, untested_rows=True):
    sub = rates[rates["window"] == K.PRIMARY_WINDOW]
    ids = [d for d in K.def_order() if d in set(sub["definition_id"])]
    piv = (sub.pivot_table(index="definition_id", columns="month",
                           values="heatwave_days_per_1000_eligible_county_days")
           .reindex(index=ids, columns=range(1, 13)))
    # one label convention everywhere: METRIC.Pxx.nD, matching Figures 3, 4, 7 and 8
    labels = ["%s.P%d.%dD" % (d.split("_")[0], int(d.split("_")[1][1:]),
                              int(d.split("_")[2][0])) for d in ids]
    rows = list(ids)
    data = piv.to_numpy(dtype=float)
    if untested_rows:
        for u in K.UNTESTED_CELLS:
            rows.append(u["definition_id"])
            data = np.vstack([data, np.full(12, np.nan)])
            labels.append("%s.P%d.%dD" % (C.METRICS[u["metric"]]["code"], u["percentile"],
                                          u["min_duration"]))
    fig, ax = plt.subplots(figsize=(11.0, 0.42 * len(rows) + 3.0))
    masked = np.ma.masked_invalid(data)
    cmap = plt.get_cmap(K.CMAP_SEQUENTIAL).copy()
    cmap.set_bad(K.COLOR_NOT_TESTED)
    im = ax.imshow(masked, cmap=cmap, aspect="auto", vmin=0,
                   vmax=float(np.nanmax(data)))
    ax.set_xticks(range(12))
    ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(labels, fontsize=7.4)
    for i, d in enumerate(rows):
        mc = d.split("_")[0]
        ax.get_yticklabels()[i].set_color(K.METRIC_STYLE[mc]["color"])
    for i in range(len(rows)):
        for j in range(12):
            v = data[i, j]
            if np.isnan(v):
                if j == 5:
                    ax.text(5.5, i, "NOT TESTED", ha="center", va="center", fontsize=7,
                            color="#8a4b08", fontweight="bold")
                continue
            ax.text(j, i, "%.0f" % v, ha="center", va="center", fontsize=6.2,
                    color=("white" if v > 0.62 * np.nanmax(data) else "#222222"))
    # mark Jun-Sep (label placed BELOW the grid so it cannot collide with the title)
    ax.add_patch(Rectangle((4.5, -0.5), 4.0, len(rows), fill=False, edgecolor="#8a4b08",
                           lw=2.0, zorder=5))
    ax.annotate("Jun-Sep", xy=(6.5, len(rows) - 0.5), xytext=(0, -16),
                textcoords="offset points", ha="center", va="top", fontsize=8.5,
                color="#8a4b08", fontweight="bold", annotation_clip=False)
    cb = fig.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
    cb.set_label("heatwave days per 1,000 ELIGIBLE county-days", fontsize=8)
    ax.set_title("Figure 5  Seasonality as a RATE, not a share: heatwave days per 1,000 "
                 "eligible county-days\nby definition and calendar month, %s window, %s, %s"
                 % (K.PRIMARY_WINDOW, K.STATE_LABEL, YEARS),
                 fontsize=11.5, fontweight="bold", loc="left")
    U.footnote(fig, "unit of analysis: county-month, aggregated over all counties and years "
                    "(county-days, not events). The denominator is ELIGIBLE county-days - days "
                    "on which the definition could be evaluated (metric present, threshold "
                    "present, not a confirmed RH-clip artifact) - so months of unequal length "
                    "and unequal data coverage are comparable. A month SHARE of all heatwave "
                    "days cannot make that distinction and is reported only as a supplement.")
    U.savefig(fig, os.path.join(K.DIR_FIG_CORE, "fig05_monthly_rate_heatmap.png"))

    # supplement: the share version, explicitly labelled as the weaker metric
    piv2 = (sub.pivot_table(index="definition_id", columns="month",
                            values="month_share_pct_of_all_heatwave_days")
            .reindex(index=ids, columns=range(1, 13)))
    fig, ax = plt.subplots(figsize=(11.0, 0.42 * len(ids) + 2.6))
    im = ax.imshow(piv2.to_numpy(dtype=float), cmap=K.CMAP_SEQUENTIAL, aspect="auto", vmin=0)
    ax.set_xticks(range(12)); ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
    ax.set_yticks(range(len(ids))); ax.set_yticklabels(labels[:len(ids)], fontsize=7.4)
    ax.add_patch(Rectangle((4.5, -0.5), 4.0, len(ids), fill=False, edgecolor="#8a4b08", lw=2))
    fig.colorbar(im, ax=ax, shrink=0.7, label="% of that definition's heatwave days")
    ax.set_title("Supplement to Figure 5  month SHARE of all heatwave days (weaker seasonal "
                 "metric)\nshown for comparison only - a share confounds 'many heatwave days' "
                 "with 'many days'", fontsize=10.5, fontweight="bold", loc="left")
    U.savefig(fig, os.path.join(K.DIR_FIG_SUPP, "fig05s_monthly_share_heatmap.png"))


# =============================================================================
# FIGURE 6 -- percentile / duration ladder over county-year records
# =============================================================================
def fig06_ladder(cy, el):
    cyp = cy[cy["window"] == K.PRIMARY_WINDOW].copy()
    # rate per 1,000 eligible county-days keeps counties with different coverage comparable
    cyp["rate"] = cyp["heatwave_days_per_1000_eligible_days"]
    metrics = ["TMAX", "TMIN", "MHI"]
    fig, axs = plt.subplots(1, 3, figsize=(15.0, 5.4), sharey=True)
    for ax, mc in zip(axs, metrics):
        st = K.METRIC_STYLE[mc]
        sub = cyp[cyp["metric"] == mc]
        for dur, dst in K.DUR_STYLE.items():
            s = sub[sub["minimum_duration"] == dur]
            if not len(s):
                continue
            piv = s.pivot_table(index=["county_fips", "year"], columns="percentile",
                                values="rate")
            pctls = sorted(piv.columns)
            # one faint line per county-year; never drawn across an untested percentile
            if len(pctls) > 1:
                seg = piv[pctls].to_numpy(dtype=float)
                for k in range(len(pctls) - 1):
                    x = [pctls[k], pctls[k + 1]]
                    ok = ~np.isnan(seg[:, k]) & ~np.isnan(seg[:, k + 1])
                    ax.plot(np.tile(x, (ok.sum(), 1)).T, seg[ok][:, k:k + 2].T,
                            color=st["color"], lw=0.35,
                            alpha=(0.05 if dur == 2 else 0.035),
                            ls=("-" if dur == 2 else "--"), zorder=1)
            med = s.groupby("percentile")["rate"].median()
            ax.plot(med.index, med.to_numpy(), color="#111111", lw=2.4, zorder=4,
                    ls=("-" if dur == 2 else "--"))
            ax.plot(med.index, med.to_numpy(), color=st["color"], lw=1.5, zorder=5,
                    marker=st["marker"], ms=9, ls=("-" if dur == 2 else "--"),
                    mfc=(st["color"] if dur == 2 else "white"), mec=st["color"], mew=1.6)
            for p, v in med.items():
                ax.annotate("%.0f" % v, (p, v), textcoords="offset points",
                            xytext=(9, 5 if dur == 2 else -12), fontsize=7.5,
                            color=K.COLOR_INK, zorder=6)
        missing = [u for u in K.UNTESTED_CELLS if C.METRICS[u["metric"]]["code"] == mc]
        if missing:
            # Marked BELOW the axis, never inside the data area: a marker drawn at
            # y=0 would read as "tested, found nothing", which is exactly the
            # misreading these two cells must not invite.
            for u in missing:
                ax.annotate("not\ntested", xy=(u["percentile"], 0), xytext=(0, -34),
                            textcoords="offset points", ha="center", va="top",
                            fontsize=7, color="#8a4b08", fontweight="bold",
                            annotation_clip=False)
            ax.text(0.5, 0.955, "no >=3-day line: the %s cells were never run"
                    % ", ".join("P%d/3D" % u["percentile"] for u in missing),
                    transform=ax.transAxes, ha="center", va="top", fontsize=7.4,
                    color="#8a4b08", fontweight="bold")
        ax.set_xticks([85, 90, 95])
        # labelpad leaves room for the below-axis "not tested" marks in the mean-HI facet,
        # and is applied to all three so the facets stay aligned
        ax.set_xlabel("percentile of the county's own walk-forward distribution", labelpad=26)
        ax.set_title("%s  (%s)" % (st["short"], st["label"]), fontsize=10, fontweight="bold",
                     color=st["color"])
        U.tidy_axes(ax, grid_axis="y")
    axs[0].set_ylabel("heatwave days per 1,000 eligible county-days\n(one faint line per "
                      "county-year)")
    axs[0].legend(handles=U.duration_legend_handles(), fontsize=8, loc="upper right",
                  title="minimum duration", title_fontsize=8)
    fig.suptitle("Figure 6  Percentile and duration ladder over individual county-year records "
                 "(%s window, %s)" % (K.PRIMARY_WINDOW, YEARS),
                 fontsize=12, fontweight="bold", y=1.0)
    U.footnote(fig, "unit of analysis: county-year (2,794 per definition = 254 counties x 11 "
                    "years). Faint lines are individual county-years, heavy lines the MEDIAN "
                    "county-year; no pooled cross-county average is drawn. Lines are never "
                    "connected across the untested mean-HI 3-day cells - the >=3-day mean-HI "
                    "series exists at the 90th percentile only, so it is a single point with "
                    "no line.", y=-0.03)
    U.savefig(fig, os.path.join(K.DIR_FIG_CORE, "fig06_percentile_duration_ladder.png"))


# =============================================================================
# FIGURE 7 -- threshold-window sensitivity
# =============================================================================
def fig07_window_sensitivity(wsens, examples):
    ids = [d for d in K.def_order() if d in set(wsens["definition_id"])]
    wins = [w for w in K.WINDOW_ORDER if w != K.PRIMARY_WINDOW]
    # generous hspace: panels A and B carry rotated definition labels that would
    # otherwise run into the next panel's heading
    fig = plt.figure(figsize=(15.5, 12.6))
    gs = fig.add_gridspec(3, 1, height_ratios=[1.05, 1.05, 1.25], hspace=0.95)

    # ---- panel A: Jaccard vs the primary window -----------------------------
    axA = fig.add_subplot(gs[0])
    x = np.arange(len(ids))
    w = 0.8 / len(wins)
    for i, wk in enumerate(wins):
        vals = [wsens.loc[(wsens["definition_id"] == d) & (wsens["window"] == wk),
                          "jaccard_vs_primary"].squeeze() for d in ids]
        axA.bar(x + i * w - 0.4 + w / 2, vals, width=w * 0.92,
                color=K.WINDOW_GREY[wk], edgecolor="white", lw=0.7,
                label="%s (%s)" % (wk, C.GRID_WINDOWS[wk]["label"]), zorder=3)
    axA.axhline(1.0, color="#8a4b08", ls="--", lw=1.0, zorder=2)
    axA.text(len(ids) - 0.4, 1.005, "identity with %s" % K.PRIMARY_WINDOW, fontsize=7,
             color="#8a4b08", ha="right")
    for name, v in (("anchor vs composite temperature (0.45-0.73)", 0.73),):
        axA.axhline(v, color="#8a4b08", ls=":", lw=0.9, zorder=2)
        axA.text(0.1, v - 0.055, name, fontsize=6.8, color="#8a4b08")
    axA.set_xticks(x)
    axA.set_xticklabels(["%s.P%d.%dD" % (d.split("_")[0], int(d.split("_")[1][1:]),
                                         int(d.split("_")[2][0])) for d in ids],
                        rotation=55, ha="right", fontsize=7.2)
    for i, d in enumerate(ids):
        axA.get_xticklabels()[i].set_color(K.METRIC_STYLE[d.split("_")[0]]["color"])
    axA.set_ylim(0, 1.05)
    axA.set_ylabel("Jaccard vs the %s window" % K.PRIMARY_WINDOW)
    axA.legend(fontsize=7, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.02),
               framealpha=0.95, borderaxespad=0)
    axA.set_title("A  day-level agreement with the primary window, every definition",
                  fontsize=10, fontweight="bold", loc="left", pad=26)
    U.tidy_axes(axA)

    # ---- panel B: paired county-year count differences ----------------------
    axB = fig.add_subplot(gs[1])
    for i, wk in enumerate(wins):
        med = [wsens.loc[(wsens["definition_id"] == d) & (wsens["window"] == wk),
                         "paired_diff_median"].squeeze() for d in ids]
        q25 = [wsens.loc[(wsens["definition_id"] == d) & (wsens["window"] == wk),
                         "paired_diff_q25"].squeeze() for d in ids]
        q75 = [wsens.loc[(wsens["definition_id"] == d) & (wsens["window"] == wk),
                         "paired_diff_q75"].squeeze() for d in ids]
        xx = x + i * w - 0.4 + w / 2
        axB.vlines(xx, q25, q75, color=K.WINDOW_GREY[wk], lw=3.2, alpha=0.55, zorder=2)
        axB.plot(xx, med, lw=0, marker="o", ms=5.2, color=K.WINDOW_GREY[wk],
                 mec="white", mew=0.8, zorder=3, label="%s" % wk)
    axB.axhline(0, color="#8a4b08", ls="--", lw=1.0, zorder=1)
    axB.set_xticks(x)
    axB.set_xticklabels(["%s.P%d.%dD" % (d.split("_")[0], int(d.split("_")[1][1:]),
                                         int(d.split("_")[2][0])) for d in ids],
                        rotation=55, ha="right", fontsize=7.2)
    for i, d in enumerate(ids):
        axB.get_xticklabels()[i].set_color(K.METRIC_STYLE[d.split("_")[0]]["color"])
    axB.set_ylabel("heatwave days per county-year\nminus the %s value" % K.PRIMARY_WINDOW)
    axB.legend(fontsize=7, ncol=3, loc="upper right", title="window", title_fontsize=7)
    axB.set_title("B  paired county-year differences from the primary window "
                  "(dot = median, bar = IQR; 2,794 paired county-years per definition)",
                  fontsize=10, fontweight="bold", loc="left")
    U.tidy_axes(axB)

    # ---- panel C: the threshold curves themselves --------------------------
    axC_specs = examples.head(4)
    gsC = gs[2].subgridspec(1, len(axC_specs), wspace=0.22)
    axC_first = None
    metric = K.THRESHOLD_CURVE_DEFINITION.split("_")[0].lower()
    mkey = {"tmax": "tmax", "tmin": "tmin", "mhi": "mhi"}[metric]
    pctl = int(K.THRESHOLD_CURVE_DEFINITION.split("_")[1][1:])
    for k, (_, ex) in enumerate(axC_specs.iterrows()):
        ax = fig.add_subplot(gsC[0, k])
        if k == 0:
            axC_first = ax
        for wk in K.WINDOW_ORDER:
            p = C.threshold_cache_path(STATE, mkey, pctl, wk)
            if not os.path.exists(p):
                continue
            t = pd.read_csv(p, dtype={"county_fips": str}, float_precision="round_trip")
            t = t[(t["county_fips"] == ex["county_fips"])
                  & (t["analysis_year"] == K.THRESHOLD_CURVE_YEAR)]
            if "template_doy" in t.columns:
                t = t.sort_values("template_doy")
                ax.plot(t["template_doy"], t["threshold_value_f"], lw=1.4,
                        color=K.WINDOW_GREY[wk], label=wk, zorder=3)
            else:
                t = t.sort_values("calendar_month")
                days = np.cumsum([0] + [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
                for mi, row in enumerate(t.itertuples()):
                    ax.plot([days[mi] + 1, days[mi + 1]],
                            [row.threshold_value_f] * 2, lw=1.8,
                            color=K.WINDOW_GREY[wk], zorder=3,
                            label=wk if mi == 0 else None)
        ax.set_title("%s Co. (%s)\n%.0f%% imputed" % (ex["county_name"],
                                                      ex["climate_division"],
                                                      ex["temperature_imputation_pct"]),
                     fontsize=8.5, fontweight="bold")
        ax.set_xticks([1, 92, 183, 275, 366])
        ax.set_xticklabels(["Jan", "Apr", "Jul", "Oct", "Dec"], fontsize=7)
        ax.set_xlabel("day of year")
        if k == 0:
            ax.set_ylabel("%s threshold (degF)\n%dth pctl, baseline 1979-%d"
                          % (C.METRICS[mkey]["short"], pctl, K.THRESHOLD_CURVE_YEAR - 1))
            ax.legend(fontsize=6.6, ncol=2, title="window", title_fontsize=6.6)
        U.tidy_axes(ax, grid_axis="both")
    # anchored to panel C's own axes so it cannot land on the county sub-titles
    if axC_first is not None:
        axC_first.annotate("C  the threshold curves being compared - %s, analysis year %d, "
                           "example counties selected by the documented climate-region + "
                           "completeness rule"
                           % (K.THRESHOLD_CURVE_DEFINITION, K.THRESHOLD_CURVE_YEAR),
                           xy=(0, 1), xycoords="axes fraction", xytext=(0, 34),
                           textcoords="offset points", fontsize=10, fontweight="bold",
                           ha="left", va="bottom", annotation_clip=False)
    fig.suptitle("Figure 7  Threshold-window sensitivity  (%s, %s)" % (K.STATE_LABEL, YEARS),
                 fontsize=12.5, fontweight="bold", y=0.98)
    U.footnote(fig, "units: panel A the SET of (county, date) heatwave days; panel B "
                    "county-year counts, paired county by county and year by year (never a "
                    "difference of two pooled totals); panel C the county's own threshold "
                    "curve in degF. Panels A and B share the definition ordering and the x "
                    "axis. The centered windows give a threshold per day of year; the "
                    "calendar-month windows give one step per month - which is the difference "
                    "the first two panels are measuring.", y=0.0)
    U.savefig(fig, os.path.join(K.DIR_FIG_CORE, "fig07_threshold_window_sensitivity.png"))


# =============================================================================
# FIGURE 11 -- data-quality influence
# =============================================================================
def fig11_data_quality(cy, ref):
    shortlist = [d for d in K.SHORTLIST_DEFINITIONS]
    sub = cy[(cy["window"] == K.PRIMARY_WINDOW) & (cy["definition_id"].isin(shortlist))]
    tot = (sub.groupby(["definition_id", "county_fips"], as_index=False)["heatwave_days"].sum())
    fig, axs = plt.subplots(2, len(shortlist), figsize=(3.35 * len(shortlist), 7.6),
                            sharex=True)
    axs = np.atleast_2d(axs)
    for k, d in enumerate(shortlist):
        st = K.METRIC_STYLE[d.split("_")[0]]
        t = tot[tot["definition_id"] == d].merge(ref, on="county_fips", how="right")
        t["heatwave_days"] = t["heatwave_days"].fillna(0)
        t["rank"] = t["heatwave_days"].rank(ascending=False, method="average")
        for row, (col, ylab) in enumerate((("heatwave_days",
                                            "heatwave days %s" % YEARS),
                                           ("rank", "county rank (1 = most days)"))):
            ax = axs[row, k]
            full = t["fully_imputed_county"]
            ax.plot(t.loc[~full, "temperature_imputation_pct"], t.loc[~full, col],
                    lw=0, marker=st["marker"], ms=4.6, mfc=st["color"], mec="white",
                    mew=0.5, alpha=0.75, zorder=3)
            ax.plot(t.loc[full, "temperature_imputation_pct"], t.loc[full, col],
                    lw=0, marker="X", ms=7.5, mfc="none", mec="#8a4b08", mew=1.5,
                    zorder=4, label="100%% imputed (n=%d)" % int(full.sum()))
            ax.axvline(K.IMPUTATION_MAX_PCT, color="#8a4b08", ls=":", lw=1.1, zorder=2)
            rho = t[["temperature_imputation_pct", col]].corr(method="spearman").iloc[0, 1]
            ax.text(0.97, 0.95 if row == 0 else 0.05, "Spearman rho = %+.3f" % rho,
                    transform=ax.transAxes, ha="right",
                    va="top" if row == 0 else "bottom", fontsize=7.5, color=K.COLOR_INK)
            if row == 1:
                ax.invert_yaxis()
                ax.set_xlabel("county temperature imputation (%)")
            if k == 0:
                ax.set_ylabel(ylab)
            if row == 0:
                ax.set_title("%s\n%s" % (d, st["short"]), fontsize=9, fontweight="bold",
                             color=st["color"])
            U.tidy_axes(ax, grid_axis="both")
    axs[0, 0].legend(fontsize=6.8, loc="lower left", framealpha=0.95)
    fig.suptitle("Figure 11  Does temperature imputation drive the county picture?  "
                 "shortlisted definitions, %s window, %s"
                 % (K.PRIMARY_WINDOW, YEARS), fontsize=12, fontweight="bold", y=1.0)
    U.footnote(fig, "The y scale of the TOP row differs by definition on purpose - this "
                    "figure asks about the ASSOCIATION with imputation within each "
                    "definition, not about levels between them (Figures 2 and 5 carry the "
                    "level comparisons). The bottom row shares one 1-%d rank scale. "
                    % len(ref), y=-0.075)
    U.footnote(fig, "unit of analysis: county (cumulative %s heatwave days and the county's "
                    "rank within this definition; not annual). Dotted line = the prespecified "
                    "%.0f%% completeness cut; crosses = the 22 counties whose temperature is "
                    "100%% IDW-imputed, which are flagged in every county-level comparison in "
                    "this package rather than dropped. Shortlist rule: one definition per "
                    "metric at the middle percentile and shorter duration, plus the two "
                    "published definitions." % (YEARS, K.IMPUTATION_MAX_PCT), y=-0.02)
    U.savefig(fig, os.path.join(K.DIR_FIG_CORE, "fig11_data_quality_influence.png"))


# =============================================================================
# FIGURE 12 -- definition-pair disagreement
# =============================================================================
def _load_counties_geo():
    try:
        import geopandas as gpd
    except Exception as e:
        K.log("   [fig12] geopandas unavailable (%s) - maps skipped" % e)
        return None
    g = gpd.read_file(C.COUNTY_SHAPEFILE)
    g = g[g["STATEFP"] == C.STATE_FIPS[STATE]][["GEOID", "geometry"]]
    return g.rename(columns={"GEOID": "county_fips"}).to_crs(C.EQUAL_AREA_CRS)


def fig12_pair_disagreement(idx, geo):
    for _, spec in idx.iterrows():
        tag = spec["pair"]
        pc = pd.read_csv(os.path.join(K.DIR_TABLES, "support_pair_disagreement_%s.csv" % tag),
                         dtype={"county_fips": str})
        pm = pd.read_csv(os.path.join(K.DIR_TABLES,
                                      "support_pair_disagreement_by_month_%s.csv" % tag))
        fig = plt.figure(figsize=(14.2, 6.4))
        gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1.0], wspace=0.16)

        # --- map of per-county disagreement rate -----------------------------
        ax = fig.add_subplot(gs[0])
        if geo is not None:
            m = geo.merge(pc, on="county_fips", how="left")
            m.plot(column="disagreement_rate_pct", cmap=K.CMAP_SEQUENTIAL, ax=ax,
                   edgecolor="white", lw=0.25, legend=True, vmin=0, vmax=100,
                   legend_kwds={"label": "county-dates classified by only ONE of the pair (%)",
                                "shrink": 0.6},
                   missing_kwds={"color": K.COLOR_NOT_TESTED, "label": "no data"})
            flagged = m[~m["data_complete"].fillna(False)]
            flagged.boundary.plot(ax=ax, edgecolor="#8a4b08", lw=0.7, zorder=4)
            ax.text(0.01, 0.02, "brown outline: %d counties above the %.0f%% imputation cut"
                    % (len(flagged), K.IMPUTATION_MAX_PCT), transform=ax.transAxes,
                    fontsize=7, color="#8a4b08")
        ax.axis("off")
        ax.set_title("A  where the two definitions disagree", fontsize=10, fontweight="bold",
                     loc="left")

        # --- monthly disagreement -------------------------------------------
        #     Colour rule: when the pair differs on METRIC, each side wears its own
        #     metric colour and marker, so the palette keeps its meaning. When the
        #     pair differs on any other axis both sides are the same metric, so two
        #     NEUTRAL colours are used instead of borrowing metric hues (which would
        #     imply a metric contrast that is not present).
        ax2 = fig.add_subplot(gs[1])
        mm = pm.set_index("month").reindex(range(1, 13)).fillna(0)
        ma, mb = spec["run_a"].split("_")[0], spec["run_b"].split("_")[0]
        if spec["axis"] == "metric":
            ca, cb = K.METRIC_STYLE[ma]["color"], K.METRIC_STYLE[mb]["color"]
            ha, hb = K.METRIC_STYLE[ma]["hatch"], K.METRIC_STYLE[mb]["hatch"]
        else:
            ca, cb = "#3d3d3d", "#a9a9a9"
            ha = hb = None
        ax2.bar(mm.index - 0.21, mm["a_only"], width=0.4, color=ca, hatch=ha,
                edgecolor="white", lw=0.6, label="only %s" % spec["run_a"], zorder=3)
        ax2.bar(mm.index + 0.21, mm["b_only"], width=0.4, color=cb, hatch=hb,
                edgecolor="white", lw=0.6, label="only %s" % spec["run_b"], zorder=3)
        ax2.plot(mm.index, mm["shared"], color="#333333", lw=1.6, marker="o", ms=4.5,
                 label="classified by BOTH", zorder=4)
        ax2.set_xticks(range(1, 13))
        ax2.set_xticklabels(K.MONTH_ABBR, fontsize=8)
        ax2.axvspan(5.5, 9.5, color="#8a4b08", alpha=0.07, zorder=0)
        ax2.text(7.5, ax2.get_ylim()[1] * 0.97, "Jun-Sep", ha="center", fontsize=8,
                 color="#8a4b08", va="top")
        ax2.set_ylabel("county-dates %s" % YEARS)
        ax2.legend(fontsize=7, loc="upper left")
        ax2.set_title("B  when they disagree (county-dates by calendar month)",
                      fontsize=10, fontweight="bold", loc="left")
        U.tidy_axes(ax2)

        fig.suptitle("Figure 12  Definition-pair disagreement - %s axis:  %s  vs  %s"
                     % (spec["axis"].upper(), spec["run_a"], spec["run_b"]),
                     fontsize=12, fontweight="bold", y=1.02, x=0.02, ha="left")
        U.footnote(fig, "unit of analysis: (county, date) heatwave day. Jaccard %.3f; "
                        "%s county-dates classified only by A, %s only by B, %s by both; "
                        "%d of 254 counties show at least one disagreement. Pair chosen in "
                        "advance to isolate the %s axis (%s). The full A-only and B-only "
                        "county-date lists are in tables/support_pair_days_%s_*.csv.gz."
                   % (spec["jaccard_day_level"],
                      "{:,}".format(int(spec["county_dates_a_only"])),
                      "{:,}".format(int(spec["county_dates_b_only"])),
                      "{:,}".format(int(spec["county_dates_shared"])),
                      int(spec["counties_with_any_disagreement"]), spec["axis"],
                      spec["rationale"], tag), y=-0.03)
        U.savefig(fig, os.path.join(K.DIR_FIG_CORE, "fig12_pair_disagreement_%s.png" % tag))


# =============================================================================
# driver
# =============================================================================
def main():
    K.ensure_dirs()
    t0 = time.time()
    T = K.DIR_TABLES
    K.log("=" * 74)
    K.log("s05  CORE FIGURES")
    K.log("=" * 74)

    reg = pd.read_csv(os.path.join(T, "table1_definition_registry.csv"))
    marg = pd.read_csv(os.path.join(T, "table7_matched_pair_marginal_effects.csv"))
    summ = pd.read_csv(os.path.join(T, "table7b_marginal_effects_summary.csv"))
    J = pd.read_csv(os.path.join(T, "support_jaccard_matrix_primary.csv"), index_col=0)
    S_all = pd.read_csv(os.path.join(T, "support_county_rank_spearman_all.csv"), index_col=0)
    S_cmp = pd.read_csv(os.path.join(T, "support_county_rank_spearman_complete.csv"), index_col=0)
    rates = pd.read_csv(os.path.join(T, "support_monthly_rate_by_definition.csv"))
    wsens = pd.read_csv(os.path.join(T, "support_window_sensitivity.csv"))
    examples = pd.read_csv(os.path.join(T, "support_example_counties.csv"),
                           dtype={"county_fips": str})
    pidx = pd.read_csv(os.path.join(T, "support_pair_disagreement_index.csv"))
    ref = U.read_reference()
    cy = U.read_master_county_year()
    el = U.read_eligibility()

    K.log("[fig 1] definition design matrix")
    fig01_design_matrix(reg)
    K.log("[fig 2] count change vs day-level agreement")
    fig02_count_vs_agreement(marg, summ)
    K.log("[fig 3] day-level Jaccard heatmap")
    fig03_jaccard_heatmap(J)
    K.log("[fig 4] county-rank stability")
    fig04_rank_stability(S_all, S_cmp, len(ref), int(ref["data_complete"].sum()))
    K.log("[fig 5] monthly classification rate")
    fig05_monthly_rate(rates)
    K.log("[fig 6] percentile / duration ladder")
    fig06_ladder(cy, el)
    K.log("[fig 7] threshold-window sensitivity")
    fig07_window_sensitivity(wsens, examples)
    K.log("[fig 11] data-quality influence")
    fig11_data_quality(cy, ref)
    K.log("[fig 12] definition-pair disagreement (%d pairs)" % len(pidx))
    geo = _load_counties_geo()
    fig12_pair_disagreement(pidx, geo)

    K.log("=" * 74)
    K.log("s05 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
