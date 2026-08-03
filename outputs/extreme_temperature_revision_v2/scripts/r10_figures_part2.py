"""
=============================================================================
r10  --  revised Part 2 and Part 3 figures: E5, E5b, E6, E7, E8, E9 and the
         new sensitivity, distribution and audit figures.
=============================================================================
Naming discipline applied throughout:
  * a year-round relative construct with no absolute condition produces
    RELATIVE WARM-SPELL DAYS, never "heatwave days";
  * 80 degF and 90 degF are ABSOLUTE DAILY-HIGH GATES, never NWS thresholds,
    and a gate is a change of construct, not a correction;
  * statewide pooled totals never carry a substantive panel;
  * Jaccard is agreement, never accuracy;
  * "flat" is used only where the prespecified flatness criterion is met.
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
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K
import r_figlib as F
import config as C                                          # noqa: E402

T = K.DIR_TABLES
YRS = K.ANALYSIS_YEARS_LABEL
NOT_EXPOSURE = ("A county with more classified days does not thereby have greater "
                "worker heat exposure, and nothing here identifies an "
                "occupational-injury effect.")
JACCARD_NOTE = ("Jaccard measures AGREEMENT between two constructs on the set of "
                "classified county-dates. It does not measure accuracy: nothing in "
                "this data observes a true heat day. Nested percentiles and durations "
                "create structural subset relationships, so a high value between two "
                "nested rules is arithmetic, not evidence.")


def cell_label(p, d):
    return "TX-P%d-D%d" % (p, d)


# =============================================================================
def fig_e5(summ, season, flat):
    rel = summ[summ["construct_family"] == "relative"]
    pct, dur = K.PERCENTILES, K.DURATIONS
    fig = plt.figure(figsize=(17.6, 9.2))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.05], hspace=0.42, wspace=0.3)
    panels = [
        ("median_annual_classified_days",
         "A  Median cumulative number of classified days\nacross counties, %s" % YRS,
         "%.0f", "median_cumulative_classified_days_per_county"),
        ("median_annual_event_count",
         "B  Median annual event count across annual\ncounty-level observations",
         "%.1f", None),
        ("median_event_duration_days",
         "C  Median individual-event duration (days)", "%.1f", None),
    ]
    for k, (field, ttl, fmt, alt) in enumerate(panels):
        ax = fig.add_subplot(gs[0, k])
        use = alt if alt else field
        A = np.full((len(pct), len(dur)), np.nan)
        for i, p in enumerate(pct):
            for j, d in enumerate(dur):
                s = rel[(rel["percentile"] == p) & (rel["duration_days"] == d)]
                if len(s):
                    A[i, j] = float(s[use].iloc[0])
        im = ax.imshow(A, cmap=K.CMAP_SEQUENTIAL, aspect="auto")
        ax.set_xticks(range(len(dur)))
        ax.set_xticklabels(["at least\n%d days" % d for d in dur], fontsize=8.5)
        ax.set_yticks(range(len(pct)))
        ax.set_yticklabels(["%dth" % p for p in pct], fontsize=9)
        for i in range(len(pct)):
            for j in range(len(dur)):
                if np.isfinite(A[i, j]):
                    ax.text(j, i, fmt % A[i, j], ha="center", va="center",
                            fontsize=10.5, fontweight="bold",
                            color=("white" if A[i, j] > 0.62 * np.nanmax(A)
                                   else "#222222"))
        ax.set_title(ttl, fontsize=9.5, fontweight="bold", loc="left")
        ax.set_xlabel("minimum duration")
        if k == 0:
            ax.set_ylabel("percentile of the county- and calendar-date-specific\n"
                          "historical daily-high distribution")

    # ---- D: the three-way seasonal split -----------------------------------
    ax = fig.add_subplot(gs[1, :])
    labs, order = [], []
    for p in pct:
        for d in dur:
            cid = K.rel_id(p, d)
            s = rel[rel["construct_id"] == cid]
            if len(s):
                order.append(cid)
                labs.append(cell_label(p, d))
    y = np.arange(len(order))
    left = np.zeros(len(order))
    for key in ("warm", "shoulder", "cool"):
        vals = []
        for cid in order:
            s = season[(season["construct_id"] == cid) & (season["season"] == key)]
            vals.append(float(s["pct_of_classified_days"].iloc[0]) if len(s) else 0.0)
        vals = np.array(vals)
        sty = K.SEASON_STYLE[key]
        ax.barh(y, vals, left=left, height=0.62, color=sty["color"],
                edgecolor="white", lw=1.6, label=sty["label"], zorder=3)
        for yi, v, l0 in zip(y, vals, left):
            if v > 4:
                ax.text(l0 + v / 2, yi, "%.0f%%" % v, ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
        left += vals
    ax.set_yticks(y)
    ax.set_yticklabels(labs, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("percentage of classified relative warm-spell days")
    ax.set_title("D  When the classified days fall - three categories, not two",
                 fontsize=9.5, fontweight="bold", loc="left")
    ax.legend(fontsize=8.5, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.16), frameon=False)
    F.tidy(ax, grid_axis="x")

    F.title(fig, "Figure E5  County-specific relative warm spells: percentile by "
                 "minimum duration (%s window, %s, %s)"
                 % (K.PRIMARY_WINDOW, K.STATE_LABEL[K.TEST_STATE], YRS),
            "These are RELATIVE WARM SPELLS, not heatwaves: the rule is year-round, "
            "applies no absolute heat condition, and cool-season days qualify.",
            y=1.03)
    F.footnote(fig, "Panels A-C are county-level quantities: A is the median across "
                    "counties of each county's cumulative classified-day count over "
                    "%s; B is the median annual event count across annual county-level "
                    "observations, replacing the statewide pooled event total the "
                    "previous package showed here; C is the median across events of "
                    "the integer event duration - a median may fall between two "
                    "integers because it is a median across events, and no individual "
                    "event lasts a fraction of a day. Panel D splits the calendar "
                    "THREE ways: the shoulder months are no longer merged with the "
                    "cool season. %s" % (YRS, NOT_EXPOSURE), y=-0.02)
    p_ = F.savefig(fig, "r_fig_E5_percentile_duration_grid.png")
    F.spec("E5", os.path.basename(p_),
           "show how the percentile and the persistence rule each change what a "
           "relative warm-spell definition selects",
           "county (A), annual county-level observation (B), individual event (C), "
           "classified county-date (D)",
           "tables/construct_summary.csv; tables/seasonal_classification_shares.csv",
           "A: median across counties of cumulative classified days. B: median across "
           "annual county-level observations of the annual event count. C: median "
           "across events of the integer duration. D: share of classified days by "
           "season",
           "none in A-C; D is a share of classified days, not a rate",
           "that the percentile moves the count smoothly while the duration rule bites "
           "hardest at the long end, and that a substantial share of classified days "
           "falls in the shoulder months",
           "that any cell is the correct definition; that these are heatwaves; that "
           "the counts are comparable to an absolute hot-spell rule",
           "County-specific relative warm spells by percentile and minimum duration, "
           "%s window, %s, %s. Panel D reports June-September, May and October, and "
           "November-April separately." % (K.PRIMARY_WINDOW,
                                           K.STATE_LABEL[K.TEST_STATE], YRS),
           "all nine cells share one walk-forward baseline, one comparison operator "
           "and one state, so the grid isolates only the percentile and duration axes")


def fig_e5b(jm, cons):
    ids = [c for c in jm.index if c.startswith("TX-P") and "+A" not in c]
    A = jm.loc[ids, ids].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(8.8, 7.6))
    im = ax.imshow(A, cmap=K.CMAP_SEQUENTIAL, vmin=0, vmax=1)
    ax.set_xticks(range(len(ids)))
    ax.set_xticklabels(ids, rotation=90, fontsize=8)
    ax.set_yticks(range(len(ids)))
    ax.set_yticklabels(ids, fontsize=8)
    for i in range(len(ids)):
        for j in range(len(ids)):
            if np.isfinite(A[i, j]):
                ax.text(j, i, ("%.2f" % A[i, j]).lstrip("0") if A[i, j] < 1 else "1",
                        ha="center", va="center", fontsize=7,
                        color=("white" if A[i, j] > 0.6 else "#222222"))
    cb = fig.colorbar(im, ax=ax, shrink=0.78)
    cb.set_label("Jaccard overlap of classified county-dates", fontsize=8.5)
    ax.set_title("Figure E5b  Agreement among the relative warm-spell definitions\n"
                 "%s window, %s - fixed 0 to 1 scale"
                 % (K.PRIMARY_WINDOW, YRS), fontsize=11, fontweight="bold", loc="left")
    F.footnote(fig, "Jaccard overlap of county-dates classified by each relative "
                    "warm-spell definition. %s Labels carry the metric (TX, the daily "
                    "high), the percentile and the minimum duration." % JACCARD_NOTE)
    p_ = F.savefig(fig, "r_fig_E5b_agreement_jaccard.png")
    F.spec("E5b", os.path.basename(p_),
           "quantify how far the nine relative definitions agree on which county-dates "
           "they classify",
           "classified county-date",
           "tables/definition_agreement_jaccard_matrix.csv",
           "|A intersect B| / |A union B| over the sets of classified county-dates",
           "the union of the two classified sets",
           "that the definitions overlap substantially but are not interchangeable",
           "that high agreement establishes validity, accuracy, or that either "
           "definition is correct",
           "Jaccard overlap of county-dates classified by each relative warm-spell "
           "definition. Agreement, not accuracy; nested thresholds and durations "
           "create structural subset relationships.",
           "every pair here shares a baseline, a state and an operator, so agreement "
           "is higher than it would be across genuinely different constructs")


def fig_e6(rates, flat, season):
    rel = rates[rates["construct_family"] == "relative"]
    fig, axs = plt.subplots(1, 3, figsize=(16.0, 5.2), sharey=True)
    ymax = rel["classified_days_per_1000_valid"].max() * 1.12
    for ax, d in zip(axs, K.DURATIONS):
        for p in K.PERCENTILES:
            s = rel[(rel["percentile"] == p)
                    & (rel["duration_days"] == d)].sort_values("month")
            if not len(s):
                continue
            ax.plot(s["month"], s["classified_days_per_1000_valid"],
                    color=K.ORDINAL_RAMP[1], ls=K.PCTL_STYLE[p]["ls"], lw=2.0,
                    marker="^", ms=5, markeredgecolor="white", markeredgewidth=0.5,
                    label="%s percentile" % K.PCTL_STYLE[p]["label"], zorder=3)
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
        ax.set_ylim(0, ymax)
        ax.set_title("minimum duration: at least %d consecutive days" % d,
                     fontsize=10, fontweight="bold")
        ax.set_xlabel("calendar month")
        F.tidy(ax, grid_axis="both")
        F.warm_season_band(ax)
    axs[0].set_ylabel(K.RATE_AXIS)
    axs[0].legend(fontsize=8, title="percentile", title_fontsize=8, framealpha=0.95)
    n_flat = int(flat[flat["construct_family"] == "relative"]
                 ["meets_flatness_criterion"].sum())
    n_tot = int((flat["construct_family"] == "relative").sum())
    ratios = flat[flat["construct_family"] == "relative"]["max_over_min_ratio"]
    F.title(fig, "Figure E6  Statewide monthly classification rate aggregated across "
                 "counties and years",
            "Relative thresholds produce classifications in every month because each "
            "date is compared with its own historical distribution.", y=1.06)
    F.footnote(fig, "Unit: the daily county-level observation. The denominator is the "
                    "count of VALID daily county-level observations for THIS construct "
                    "family - the daily high present and a historical threshold "
                    "available - not a shared denominator borrowed from another "
                    "package. All three panels share one y-axis scale. FLATNESS: the "
                    "prespecified criterion is a highest-to-lowest monthly ratio of at "
                    "most 1.5 AND a coefficient of variation across the twelve monthly "
                    "rates of at most 0.15. %d of %d relative definitions meet it; the "
                    "observed ratios run from %.1f to %.1f, so these curves are NOT "
                    "flat and are not described as flat. See qa/flatness_criterion.csv."
               % (n_flat, n_tot, ratios.min(), ratios.max()), y=-0.06)
    p_ = F.savefig(fig, "r_fig_E6_monthly_classification_rate.png")
    F.spec("E6", os.path.basename(p_),
           "show when in the calendar a year-round relative rule fires, on a rate that "
           "is comparable between months of unequal length and coverage",
           "daily county-level observation",
           "tables/monthly_classification_rates.csv",
           "1000 x classified days in the month / valid daily county-level "
           "observations in the month, pooled over counties and years",
           "valid daily county-level observations for the RELATIVE family (daily high "
           "present and a historical threshold available)",
           "that relative thresholds produce classifications in every month, and that "
           "the monthly rate varies by a measured factor across the calendar",
           "that the curves are flat (the prespecified criterion is not met); that the "
           "cool season causes the off-season classifications",
           "Statewide monthly classification rate aggregated across counties and "
           "years, for the nine relative warm-spell definitions. Identical y-axis "
           "scales.",
           "pooling over counties and years hides between-county variation in the "
           "seasonal profile; the county layer is in "
           "tables/county_monthly_relative_warm_spells.csv")


def fig_e7(ge, rates, season):
    cells = [cell_label(p, d) for p in K.PERCENTILES for d in K.DURATIONS]
    fig = plt.figure(figsize=(17.0, 11.0))
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1.05], hspace=0.62, wspace=0.22)

    # A: retention and day-level agreement
    ax = fig.add_subplot(gs[0, 0])
    x = np.arange(len(cells))
    for k, g in enumerate(K.ABSOLUTE_GATES_F):
        v = [float(ge[(ge["label"] == c) & (ge["absolute_gate_f"] == g)]
                   ["pct_classified_days_retained"].iloc[0]) for c in cells]
        sty = K.GATE_STYLE[g]
        ax.bar(x + (k - 0.5) * 0.4, v, width=0.38, color=sty["color"],
               hatch=sty["hatch"], edgecolor="white", lw=0.7, label=sty["label"],
               zorder=3)
        for xi, vi in zip(x + (k - 0.5) * 0.4, v):
            ax.annotate("%.0f" % vi, (xi, vi), xytext=(0, 3),
                        textcoords="offset points", ha="center", fontsize=6.6)
    ax.set_xticks(x)
    ax.set_xticklabels(cells, rotation=45, ha="right", fontsize=8)
    ax.set_ylim(0, 116)
    ax.set_ylabel("% of classified days retained")
    ax.legend(fontsize=8, ncol=2, loc="upper center", frameon=False)
    ax.set_title("A  how many classified days survive the gate", fontsize=10,
                 fontweight="bold", loc="left")
    F.tidy(ax)

    # B: seasonal redistribution, three categories
    ax = fig.add_subplot(gs[0, 1])
    base = ge.drop_duplicates("label").set_index("label")
    stack_specs = [("no absolute gate", None), ("80 degF gate", 80.0),
                   ("90 degF gate", 90.0)]
    xs = np.arange(len(cells))
    for k, (lab, g) in enumerate(stack_specs):
        off = (k - 1) * 0.28
        bottom = np.zeros(len(cells))
        for key, col in (("warm", "pct_days_june_september"),
                         ("shoulder", "pct_days_may_and_october"),
                         ("cool", "pct_days_november_april")):
            if g is None:
                v = np.array([float(base.loc[c, col + "_no_gate"]) for c in cells])
            else:
                v = np.array([float(ge[(ge["label"] == c)
                                       & (ge["absolute_gate_f"] == g)]
                                    [col + "_with_gate"].iloc[0]) for c in cells])
            ax.bar(xs + off, v, bottom=bottom, width=0.25,
                   color=K.SEASON_STYLE[key]["color"], edgecolor="white", lw=0.8,
                   zorder=3)
            bottom += v
    ax.set_xticks(xs)
    ax.set_xticklabels(cells, rotation=45, ha="right", fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_ylabel("% of classified days")
    ax.set_title("B  where the classified days fall, before and after the gate\n"
                 "(left bar no gate, middle 80 degF, right 90 degF)", fontsize=10,
                 fontweight="bold", loc="left")
    ax.legend(handles=[Patch(facecolor=K.SEASON_STYLE[k]["color"],
                             label=K.SEASON_STYLE[k]["label"])
                       for k in ("warm", "shoulder", "cool")],
              fontsize=7.5, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.30), frameon=False)
    F.tidy(ax)

    # C: county-level geography of retention
    ax = fig.add_subplot(gs[1, 0])
    for k, g in enumerate(K.ABSOLUTE_GATES_F):
        med = [float(ge[(ge["label"] == c) & (ge["absolute_gate_f"] == g)]
                     ["median_county_retention_pct"].iloc[0]) for c in cells]
        lo = [float(ge[(ge["label"] == c) & (ge["absolute_gate_f"] == g)]
                    ["p10_county_retention_pct"].iloc[0]) for c in cells]
        hi = [float(ge[(ge["label"] == c) & (ge["absolute_gate_f"] == g)]
                    ["p90_county_retention_pct"].iloc[0]) for c in cells]
        sty = K.GATE_STYLE[g]
        off = (k - 0.5) * 0.22
        ax.errorbar(x + off, med,
                    yerr=[np.array(med) - np.array(lo), np.array(hi) - np.array(med)],
                    fmt=("s" if g == 80 else "D"), ms=6, color=sty["color"],
                    ecolor=sty["color"], elinewidth=1.6, capsize=3,
                    markeredgecolor="white", markeredgewidth=0.7, label=sty["label"],
                    zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(cells, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("% of a county's days retained\n(median, with 10th-90th percentile)")
    ax.set_title("C  the gate does not bite equally everywhere", fontsize=10,
                 fontweight="bold", loc="left")
    ax.legend(fontsize=8)
    F.tidy(ax)

    # D: annual county-level change in events and days
    ax = fig.add_subplot(gs[1, 1])
    for k, g in enumerate(K.ABSOLUTE_GATES_F):
        dv = [float(ge[(ge["label"] == c) & (ge["absolute_gate_f"] == g)]
                    ["annual_classified_day_change"].iloc[0]) for c in cells]
        de = [float(ge[(ge["label"] == c) & (ge["absolute_gate_f"] == g)]
                    ["annual_event_count_change"].iloc[0]) for c in cells]
        sty = K.GATE_STYLE[g]
        ax.bar(x + (k - 0.5) * 0.4, dv, width=0.38, color=sty["color"],
               hatch=sty["hatch"], edgecolor="white", lw=0.7,
               label="%s: classified days" % sty["label"], zorder=3)
        ax.plot(x + (k - 0.5) * 0.4, de, lw=0, marker="o", ms=5,
                mfc="white", mec=sty["color"], mew=1.6, zorder=4,
                label="%s: events" % sty["label"])
    ax.axhline(0, color="#333333", lw=1.0, zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels(cells, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("change in the median ANNUAL county-level count")
    ax.set_title("D  annual county-level change, not a pooled total", fontsize=10,
                 fontweight="bold", loc="left")
    ax.legend(fontsize=6.6, ncol=2)
    F.tidy(ax)

    # E: monthly rate profiles for two worked cells
    for j, (p, d) in enumerate(((90, 3), (85, 2))):
        ax = fig.add_subplot(gs[2, j])
        for g in [None] + list(K.ABSOLUTE_GATES_F):
            cid = K.rel_id(p, d) if g is None else K.hyb_id(p, d, g)
            s = rates[rates["construct_id"] == cid].sort_values("month")
            if not len(s):
                continue
            sty = K.GATE_STYLE[g]
            ax.plot(s["month"], s["classified_days_per_1000_valid"],
                    color=sty["color"], lw=2.1, marker="^", ms=5.2,
                    markeredgecolor="white", markeredgewidth=0.5, label=sty["label"],
                    zorder=3)
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
        ax.set_ylabel(K.RATE_AXIS)
        ax.set_xlabel("calendar month")
        ax.legend(fontsize=8)
        ax.set_title("%s  monthly rate, %s" % ("EF"[j], cell_label(p, d)),
                     fontsize=10, fontweight="bold", loc="left")
        F.tidy(ax, grid_axis="both")
        F.warm_season_band(ax)

    F.title(fig, "Figure E7  What an absolute daily-high gate does to a relative "
                 "warm-spell definition (%s window, %s, %s)"
                 % (K.PRIMARY_WINDOW, K.STATE_LABEL[K.TEST_STATE], YRS),
            "The gate changes the construct from purely relative heat to a hybrid "
            "relative-and-absolute definition. It is not a correction, and 80 degF "
            "and 90 degF are not National Weather Service advisory thresholds.",
            y=1.0)
    F.footnote(fig, "A day must satisfy BOTH its county- and calendar-date-specific "
                    "percentile threshold AND the absolute daily-high gate. Day-level "
                    "agreement with the ungated version, reported in "
                    "tables/absolute_gate_effect.csv, is numerically equal to the "
                    "retained share in panel A because the gated set is a strict "
                    "subset. Panel C shows that the retained share varies widely "
                    "between counties, so the gate redistributes exposure "
                    "geographically as well as seasonally. %s" % NOT_EXPOSURE,
               y=-0.012)
    p_ = F.savefig(fig, "r_fig_E7_absolute_gate_effect.png")
    F.spec("E7", os.path.basename(p_),
           "measure what an absolute daily-high gate does to each relative definition",
           "classified county-date (A, B), county (C), annual county-level observation "
           "(D), daily county-level observation (E, F)",
           "tables/absolute_gate_effect.csv; tables/monthly_classification_rates.csv",
           "retained share = gated classified days / ungated classified days; county "
           "retention = per-county ratio; annual change = difference in the median "
           "annual county-level count; monthly rate per 1,000 valid records",
           "for the rate panels, valid daily county-level observations for the "
           "construct's own family",
           "that the 90 degF gate concentrates classifications into warmer months, at "
           "the cost of roughly half the classified days, and that it does so "
           "unevenly across counties",
           "that the gate corrects the relative rule; that the gate is an NWS "
           "threshold; that the gated construct is the same construct",
           "Effect of an absolute daily-high gate on each relative warm-spell "
           "definition. The gate changes the construct to a hybrid "
           "relative-and-absolute definition.",
           "the gated variants are run at the primary threshold window only, so the "
           "window axis is not crossed with the gate axis")


def fig_e8(summ, av, rates, ann):
    fig = plt.figure(figsize=(17.2, 9.4))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 1], hspace=0.46, wspace=0.28)

    # A: annual county-level classified-day distributions
    ax = fig.add_subplot(gs[0, :2])
    order, colors, labs = [], [], []
    for g in K.ABSOLUTE_GATES_F:
        for d in K.DURATIONS:
            order.append(K.abs_id(g, d))
            colors.append(K.FAMILY_STYLE["absolute"]["color"])
            labs.append("absolute %d degF, D%d" % (int(g), d))
    for p in K.PERCENTILES:
        for d in K.DURATIONS:
            order.append(K.rel_id(p, d))
            colors.append(K.FAMILY_STYLE["relative"]["color"])
            labs.append("relative P%d, D%d" % (p, d))
    data = [ann[ann["construct_id"] == cid]["annual_classified_day_count"].to_numpy()
            for cid in order]
    bp = ax.boxplot(data, tick_labels=labs, patch_artist=True, showfliers=False,
                    widths=0.62, medianprops=dict(color="#111111", lw=1.6))
    for b, c in zip(bp["boxes"], colors):
        b.set_facecolor(c)
        b.set_alpha(0.7)
        b.set_edgecolor("#555555")
    ax.axhline(365, color="#8a2f24", ls=":", lw=1.2)
    ax.text(len(order) - 0.4, 368, "every day in a year", fontsize=7,
            color="#8a2f24", ha="right")
    ax.set_xticklabels(labs, rotation=45, ha="right", fontsize=7.5)
    ax.set_ylabel("classified days per county per YEAR")
    ax.set_title("A  annual county-level classified-day distributions", fontsize=10,
                 fontweight="bold", loc="left")
    ax.legend(handles=[Patch(facecolor=K.FAMILY_STYLE["absolute"]["color"],
                             label="Absolute hot spell"),
                       Patch(facecolor=K.FAMILY_STYLE["relative"]["color"],
                             label="County-specific relative warm spell")],
              fontsize=8, loc="upper right", bbox_to_anchor=(1.0, 0.93),
              framealpha=0.95)
    F.tidy(ax)

    # B: annual event-count distributions
    ax = fig.add_subplot(gs[0, 2])
    data = [ann[ann["construct_id"] == cid]["annual_event_count"].to_numpy()
            for cid in order]
    bp = ax.boxplot(data, tick_labels=labs, patch_artist=True, showfliers=False,
                    widths=0.62, medianprops=dict(color="#111111", lw=1.6))
    for b, c in zip(bp["boxes"], colors):
        b.set_facecolor(c)
        b.set_alpha(0.7)
        b.set_edgecolor("#555555")
    ax.set_xticklabels(labs, rotation=90, fontsize=5.6)
    ax.set_ylabel("events per county per YEAR")
    ax.set_title("B  annual event-count distributions", fontsize=10,
                 fontweight="bold", loc="left")
    F.tidy(ax)

    # C: monthly rates
    ax = fig.add_subplot(gs[1, 0])
    for g in K.ABSOLUTE_GATES_F:
        cid = K.abs_id(g, 2)
        s = rates[rates["construct_id"] == cid].sort_values("month")
        if len(s):
            ax.plot(s["month"], s["classified_days_per_1000_valid"],
                    color=K.GATE_STYLE[g]["color"], lw=2.2, marker="D", ms=5,
                    markeredgecolor="white", markeredgewidth=0.5,
                    label="absolute %d degF warm/hot spell" % int(g), zorder=3)
    s = rates[rates["construct_id"] == K.rel_id(90, 2)].sort_values("month")
    ax.plot(s["month"], s["classified_days_per_1000_valid"],
            color=K.FAMILY_STYLE["relative"]["color"], lw=2.2, marker="^", ms=5,
            markeredgecolor="#8a5f00", markeredgewidth=0.5,
            label="county-specific relative warm spell", zorder=3)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
    ax.set_ylabel(K.RATE_AXIS)
    ax.set_xlabel("calendar month")
    ax.legend(fontsize=7)
    ax.set_title("C  monthly classification rate (at least 2 days)", fontsize=10,
                 fontweight="bold", loc="left")
    F.tidy(ax, grid_axis="both")
    F.warm_season_band(ax)

    # D: agreement
    ax = fig.add_subplot(gs[1, 1])
    sub = av[av["duration_days"] == 2]
    xs = np.arange(len(sub))
    ax.bar(xs, sub["jaccard"], color="#8a8a8a", edgecolor="white", lw=0.6, zorder=3)
    for xi, v in zip(xs, sub["jaccard"]):
        ax.annotate("%.2f" % v, (xi, v), xytext=(0, 3), textcoords="offset points",
                    ha="center", fontsize=7.5)
    ax.set_xticks(xs)
    ax.set_xticklabels(["%s\nvs P%d" % (r["absolute_label"], r["percentile"])
                        for _, r in sub.iterrows()], fontsize=6.2, rotation=30,
                       ha="right")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Jaccard (agreement, not accuracy)")
    ax.set_title("D  do the two constructs pick the same county-dates?", fontsize=10,
                 fontweight="bold", loc="left")
    F.tidy(ax)

    # E: share of all valid records classified
    ax = fig.add_subplot(gs[1, 2])
    s = summ[summ["construct_id"].isin(order)].set_index("construct_id").loc[order]
    xs = np.arange(len(order))
    ax.barh(xs, s["classified_days_per_1000_valid"] / 10.0, color=colors,
            edgecolor="white", lw=0.6, zorder=3)
    for xi, v in zip(xs, s["classified_days_per_1000_valid"] / 10.0):
        ax.annotate("%.0f%%" % v, (v, xi), xytext=(3, 0), textcoords="offset points",
                    va="center", fontsize=7)
    ax.set_yticks(xs)
    ax.set_yticklabels(labs, fontsize=6.6)
    ax.invert_yaxis()
    ax.set_xlabel("% of ALL valid daily county-level observations classified")
    ax.set_title("E  is it an extreme?", fontsize=10, fontweight="bold", loc="left")
    F.tidy(ax, grid_axis="x")

    F.title(fig, "Figure E8  Absolute hot-spell definitions against the "
                 "county-specific relative warm-spell definition (%s, %s)"
                 % (K.STATE_LABEL[K.TEST_STATE], YRS),
            "Three constructs, not three variants of one: the absolute 80 degF "
            "warm-spell definition, the absolute 90 degF hot-spell definition, and "
            "the county-specific relative warm-spell definition.", y=1.03)
    F.footnote(fig, "An absolute rule has no baseline and therefore no threshold "
                    "window. Panels A and B replace the previous package's per-county "
                    "study-period medians with the ANNUAL county-level distributions "
                    "behind them. Panel E is the share of all valid daily county-level "
                    "observations that each rule classifies: a rule that classifies "
                    "half of every day in the record is not describing an extreme, "
                    "whatever it is called. Panel D is agreement, never accuracy. %s"
               % NOT_EXPOSURE, y=-0.02)
    p_ = F.savefig(fig, "r_fig_E8_absolute_vs_relative.png")
    F.spec("E8", os.path.basename(p_),
           "compare the absolute and relative construct families on the same "
           "county-level footing",
           "annual county-level observation (A, B), daily county-level observation "
           "(C, E), classified county-date (D)",
           "tables/county_annual_all_constructs.csv; "
           "tables/monthly_classification_rates.csv; tables/absolute_vs_relative.csv; "
           "tables/construct_summary.csv",
           "distributions across annual county-level observations; monthly rate per "
           "1,000 valid records; Jaccard over classified county-dates",
           "family-specific valid daily county-level observations",
           "that the absolute 80 degF rule classifies a very large share of all days, "
           "that the 90 degF rule is strongly seasonal, and that the absolute and "
           "relative rules select largely different county-dates",
           "that either construct is correct; that low agreement means one is wrong; "
           "that an absolute rule is a heat advisory",
           "Absolute hot-spell definitions against the county-specific relative "
           "warm-spell definition. Annual county-level distributions, monthly rates "
           "and day-level agreement.",
           "the absolute family is evaluated on Texas only and on the gap-filled "
           "county-day table, as the relative family is")


def fig_e9(cg, qual):
    try:
        import geopandas as gpd
    except Exception as e:                                  # noqa: BLE001
        K.log("   [E9] geopandas unavailable (%s) - maps skipped" % e)
        return
    g = gpd.read_file(C.COUNTY_SHAPEFILE)
    g = (g[g["STATEFP"] == C.STATE_FIPS[K.TEST_STATE]][["GEOID", "geometry"]]
         .rename(columns={"GEOID": "county_fips"}).to_crs(C.EQUAL_AREA_CRS))
    cell = cell_label(90, 3)
    sub80 = cg[(cg["label"] == cell) & (cg["absolute_gate_f"] == 80.0)]
    sub90 = cg[(cg["label"] == cell) & (cg["absolute_gate_f"] == 90.0)]

    for version, exclude in (("all_counties", False), ("excluding_fully_imputed", True)):
        s80 = sub80[~sub80["fully_imputed_county"]] if exclude else sub80
        s90 = sub90[~sub90["fully_imputed_county"]] if exclude else sub90
        fig, axs = plt.subplots(1, 4, figsize=(19.0, 5.0))
        for ax in axs:                       # base layer, so a zero-valued or
            g.plot(ax=ax, facecolor="#f2f2f2",   # excluded county is still visible
                   edgecolor="#b8b8b8", lw=0.25, zorder=1)
        m0 = g.merge(s80, on="county_fips", how="left")
        m0.plot(column="cumulative_classified_days_no_gate", cmap=K.CMAP_SEQUENTIAL,
                ax=axs[0], edgecolor="#b8b8b8", lw=0.25, legend=True, zorder=2,
                legend_kwds={"label": "cumulative relative warm-spell days, %s" % YRS,
                             "shrink": 0.55},
                missing_kwds={"color": "#e8e8e8"})
        lo = s80["cumulative_classified_days_no_gate"]
        axs[0].set_title("A  cumulative relative warm-spell days\n%s, no gate "
                         "(range %d to %d, ratio %.1fx)"
                         % (cell, lo.min(), lo.max(),
                            lo.max() / max(lo[lo > 0].min(), 1)),
                         fontsize=9.5, fontweight="bold", loc="left")
        for k, (s, gate) in enumerate(((s80, 80), (s90, 90)), start=1):
            mm = g.merge(s, on="county_fips", how="left")
            mm.plot(column="pct_retained", cmap=K.CMAP_SEQUENTIAL, ax=axs[k],
                    edgecolor="#b8b8b8", lw=0.25, legend=True, vmin=0, vmax=100,
                    zorder=2,
                    legend_kwds={"label": "%% of days retained, %d degF gate" % gate,
                                 "shrink": 0.55},
                    missing_kwds={"color": "#e8e8e8"})
            axs[k].set_title("%s  retained by the %d degF absolute gate\n"
                             "(median %.0f%%, 10th-90th %.0f-%.0f%%)"
                             % ("BC"[k - 1], gate, s["pct_retained"].median(),
                                s["pct_retained"].quantile(0.1),
                                s["pct_retained"].quantile(0.9)),
                             fontsize=9.5, fontweight="bold", loc="left")
        mq = g.merge(qual, on="county_fips", how="left")
        mq.plot(column="pct_analysis_days_imputed", cmap="Greys", ax=axs[3],
                edgecolor="#b8b8b8", lw=0.25, legend=True, vmin=0, vmax=100,
                zorder=2,
                legend_kwds={"label": "% of daily records gap-filled", "shrink": 0.55},
                missing_kwds={"color": "#e8e8e8"})
        fi = mq[mq["fully_imputed_county"].fillna(False)]
        if len(fi) and not exclude:
            fi.plot(ax=axs[3], facecolor="none", edgecolor="#c0392b", lw=1.1,
                    hatch="////", zorder=3)
            axs[3].legend(handles=[Patch(facecolor="none", edgecolor="#c0392b",
                                         hatch="////",
                                         label="fully imputed county (n=%d)" % len(fi))],
                          fontsize=8, loc="lower left", framealpha=0.95)
        axs[3].set_title("D  data quality: gap-filling by county", fontsize=9.5,
                         fontweight="bold", loc="left")
        for ax in axs:
            ax.axis("off")
        suffix = ("" if not exclude else
                  "  -  fully imputed counties EXCLUDED")
        F.title(fig, "Figure E9  Geography of the relative warm-spell definition and "
                     "of the absolute gate (%s, %s)%s" % (cell, YRS, suffix),
                "County-specific percentile thresholds reduce first-order differences "
                "in baseline climate, but event counts still vary widely between "
                "counties.", y=1.02)
        F.footnote(fig, "County-specific percentile thresholds reduce first-order "
                        "differences in baseline climate, but event counts may still "
                        "vary because of persistence, temporal dependence, warming "
                        "relative to the walk-forward baseline, missingness, "
                        "imputation and station composition. The observed spread in "
                        "panel A is a factor of %.1f between the highest and lowest "
                        "county, which is not what 'a similar number everywhere by "
                        "construction' would produce. Panel D carries the data-quality "
                        "indicator that must accompany any county-level ranking; "
                        "fully imputed counties are hatched, and a second version of "
                        "this figure excludes them entirely. %s"
                   % (lo.max() / max(lo[lo > 0].min(), 1), NOT_EXPOSURE), y=-0.02)
        p_ = F.savefig(fig, "r_fig_E9_county_geography_%s.png" % version)
        F.spec("E9" + ("" if not exclude else "b"), os.path.basename(p_),
               "show how the relative construct and the absolute gate vary "
               "geographically, alongside the data quality behind each county",
               "county",
               "tables/county_gate_effect.csv; tables/county_data_quality.csv",
               "cumulative classified days per county; per-county retained share; "
               "per-county share of gap-filled daily records",
               "none for the maps of counts; the retained share uses each county's own "
               "ungated count as its denominator",
               "that a county-specific percentile rule still produces a wide spread of "
               "county counts, and that an absolute gate removes more days in cooler "
               "counties",
               "that a relative rule equalises exposure by construction; that a county "
               "with more classified days has greater worker heat exposure",
               "Geography of the %s relative warm-spell definition and of the absolute "
               "daily-high gate. Panel D shows gap-filling by county; fully imputed "
               "counties are hatched." % cell,
               "22 of 254 counties have no observed temperature at all and are carried "
               "entirely by interpolation from neighbours")


# =============================================================================
# new figures
# =============================================================================
def fig_imputation(sens, ranks):
    p = sens[sens["construct_id"] == K.PRIMARY_CONSTRUCT]
    fig, axs = plt.subplots(1, 3, figsize=(16.4, 5.2))
    labs = [r["stratum_label"] for _, r in p.iterrows()]
    y = np.arange(len(p))
    shades = plt.get_cmap("YlOrBr")(np.linspace(0.25, 0.8, len(p)))
    for ax, col, ttl, fmt in (
            (axs[0], "median_annual_classified_days",
             "A  median annual classified days per county", "%.0f"),
            (axs[1], "pct_days_june_september",
             "B  %% of classified days in %s" % K.SEASON_LABEL["warm"], "%.1f"),
            (axs[2], "long_events_per_100_county_years",
             "C  events longer than %d days, per 100 county-years"
             % K.LONG_EVENT_DAYS, "%.2f")):
        v = p[col].to_numpy(dtype=float)
        ax.barh(y, v, color=shades, edgecolor="white", lw=0.6, zorder=3)
        for yi, vi, n in zip(y, v, p["counties"]):
            ax.annotate((fmt + "  (n=%d)") % (vi, n), (vi, yi), xytext=(4, 0),
                        textcoords="offset points", va="center", fontsize=7.2)
        ax.set_yticks(y)
        ax.set_yticklabels(labs if ax is axs[0] else [""] * len(y), fontsize=7.8)
        ax.invert_yaxis()
        ax.set_xlim(0, v.max() * 1.42)
        ax.set_title(ttl, fontsize=9.5, fontweight="bold", loc="left")
        F.tidy(ax, grid_axis="x")
    F.title(fig, "Figure R5  Observed against imputed counties: does the county "
                 "subset change the answer?",
            "Construct: %s. Each bar is the whole state summary recomputed on a "
            "different county subset." % K.PRIMARY_CONSTRUCT, y=1.06)
    F.footnote(fig, "A county's own classified-day count does not depend on which "
                    "other counties are included, so the ORDER of counties is "
                    "identical in every subset by construction (verified: Spearman "
                    "1.000 in all %d comparisons). What a data-quality subset changes "
                    "is which counties are eligible to be summarised. Dropping the "
                    "most heavily gap-filled counties raises the median annual "
                    "classified-day count and raises the long-event rate, so the "
                    "gap-filled counties sit at the low end of both. No county ranking "
                    "is published anywhere in this package without this indicator "
                    "attached. %s" % (len(ranks), NOT_EXPOSURE), y=-0.06)
    p_ = F.savefig(fig, "r_fig_R5_imputation_sensitivity.png")
    F.spec("R5", os.path.basename(p_),
           "test whether the county-level results depend on gap-filled data",
           "county subset",
           "tables/imputation_sensitivity.csv; "
           "tables/imputation_sensitivity_rankings.csv",
           "state summaries recomputed on six prespecified county subsets",
           "family-specific valid daily county-level observations within each subset",
           "that the summaries shift modestly when gap-filled counties are excluded, "
           "and in a consistent direction",
           "that the gap-filled counties are wrong, or that excluding them removes "
           "bias; the excluded counties are systematically rural",
           "Observed against imputed counties. The state summary for %s recomputed on "
           "six county subsets." % K.PRIMARY_CONSTRUCT,
           "the six subsets are nested, so they are not independent sensitivity cases")


def fig_timeline(cat, ann):
    cid = K.PRIMARY_CONSTRUCT
    c = cat[cat["construct_id"] == cid].copy()
    c["start"] = pd.to_datetime(c["event_start_date"])
    tot = (ann[ann["construct_id"] == cid].groupby("county_fips")
           ["annual_classified_day_count"].sum().sort_values())
    pick = [tot.index[-1], tot.index[len(tot) // 2],
            tot[tot > 0].index[0] if (tot > 0).any() else tot.index[0]]
    names = (c.drop_duplicates("county_fips").set_index("county_fips")["county_name"]
             .to_dict())
    fig, axs = plt.subplots(len(pick), 1, figsize=(16.0, 7.2), sharex=True)
    for ax, fips in zip(axs, pick):
        s = c[c["county_fips"] == fips]
        for _, e in s.iterrows():
            st = pd.Timestamp(e["event_start_date"])
            ax.barh(0, e["event_duration_days"], left=st, height=0.55,
                    color=(K.SEASON_STYLE[K.SEASON_OF[st.month]]["color"]),
                    edgecolor="white", lw=0.3, zorder=3)
        ax.set_yticks([])
        ax.set_ylim(-0.5, 0.5)
        ax.set_ylabel("%s\n(%s)" % (names.get(fips, fips), fips), fontsize=8.5,
                      rotation=0, ha="right", va="center")
        ax.set_title("%d events, %d classified days, longest %d days"
                     % (len(s), int(s["event_duration_days"].sum()),
                        int(s["event_duration_days"].max()) if len(s) else 0),
                     fontsize=8.5, loc="left", color=K.COLOR_INK_SOFT)
        F.tidy(ax, grid_axis="x")
    axs[-1].set_xlabel("date")
    axs[0].legend(handles=[Patch(facecolor=K.SEASON_STYLE[k]["color"],
                                 label="event starts in " + K.SEASON_STYLE[k]["label"])
                           for k in ("warm", "shoulder", "cool")],
                  fontsize=7.5, ncol=3, loc="upper left", framealpha=0.95)
    F.title(fig, "Figure R6  Individual event timeline, %s" % cid,
            "Every bar is one event in one county, drawn at its true start date with "
            "its true integer duration. Three counties: highest, median and lowest "
            "cumulative classified-day count.", y=1.05)
    F.footnote(fig, "Unit: the individual event. Colour marks the season in which the "
                    "event STARTS, which is why cool-season bars appear at all - a "
                    "year-round relative rule fires whenever a county departs from its "
                    "own history for that date. Source: "
                    "tables/individual_relative_warm_spell_events.csv. %s" % NOT_EXPOSURE,
               y=-0.05)
    p_ = F.savefig(fig, "r_fig_R6_event_timeline.png")
    F.spec("R6", os.path.basename(p_),
           "make individual events visible, rather than only their aggregates",
           "individual event",
           "tables/individual_relative_warm_spell_events.csv",
           "none; events are drawn at their recorded start date and integer duration",
           "none",
           "that events are discrete, dated objects of integer length, distributed "
           "through the whole calendar",
           "any statistical claim; three counties are illustrative, not a sample",
           "Individual event timeline for %s in three contrasting counties." % cid,
           "three counties chosen by their cumulative classified-day rank; not "
           "representative of the state")


def fig_long_events(ev):
    fig, axs = plt.subplots(1, 3, figsize=(16.6, 5.2),
                            gridspec_kw={"width_ratios": [1.15, 1, 1]})
    ax = axs[0]
    for fam in ("relative", "hybrid", "absolute"):
        s = ev[ev["construct_family"] == fam]["event_duration_days"]
        if not len(s):
            continue
        ax.hist(s, bins=np.arange(K.LONG_EVENT_DAYS, s.max() + 4, 3),
                histtype="stepfilled", alpha=0.55,
                color=K.FAMILY_STYLE[fam]["color"],
                edgecolor=K.FAMILY_STYLE[fam]["color"], lw=1.4,
                label="%s (n=%s)" % (K.FAMILY_STYLE[fam]["label"],
                                     "{:,}".format(len(s))), zorder=3)
    ax.axvline(K.LONG_EVENT_DAYS_STRICT, color="#8a2f24", ls=":", lw=1.2)
    ax.set_yscale("log")
    ax.text(K.LONG_EVENT_DAYS_STRICT + 4, 1.5,
            "strict audit threshold, %d days" % K.LONG_EVENT_DAYS_STRICT, fontsize=7,
            color="#8a2f24")
    ax.set_xlabel("event duration (days)")
    ax.set_ylabel("events (log scale)")
    ax.set_title("A  how long the long events are", fontsize=10, fontweight="bold",
                 loc="left")
    ax.legend(fontsize=7, loc="upper right", framealpha=0.95)
    F.tidy(ax)

    ax = axs[1]
    c = ev["audit_classification"].value_counts()
    y = np.arange(len(c))
    cols = {"physically_plausible": "#008300", "threshold_driven": "#ae5c13",
            "imputation_sensitive": "#c0392b",
            "station_composition_sensitive": "#2a78d6",
            "requires_manual_review": "#8a8a8a"}
    ax.barh(y, c.to_numpy(), color=[cols.get(i, "#8a8a8a") for i in c.index],
            edgecolor="white", lw=0.6, zorder=3)
    for yi, v in zip(y, c.to_numpy()):
        ax.annotate("%s  (%.0f%%)" % ("{:,}".format(int(v)), 100 * v / len(ev)),
                    (v, yi), xytext=(4, 0), textcoords="offset points", va="center",
                    fontsize=7.5)
    ax.set_yticks(y)
    ax.set_yticklabels([i.replace("_", " ") for i in c.index], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, c.max() * 1.4)
    ax.set_xlabel("events")
    ax.set_title("B  why each long event is long", fontsize=10, fontweight="bold",
                 loc="left")
    F.tidy(ax, grid_axis="x")

    ax = axs[2]
    s = ev.dropna(subset=["mean_exceedance_per_day_f"])
    rel = s[s["construct_family"] == "relative"]
    ax.scatter(rel["event_duration_days"], rel["mean_exceedance_per_day_f"],
               s=7, alpha=0.35, color=K.FAMILY_STYLE["relative"]["color"],
               edgecolors="none", zorder=3)
    ax.axhline(1.0, color="#8a2f24", ls=":", lw=1.2)
    ax.text(rel["event_duration_days"].max(), 1.1, "threshold-driven below this line",
            fontsize=7, color="#8a2f24", ha="right")
    ax.set_xlabel("event duration (days)")
    ax.set_ylabel("mean exceedance above the threshold (degF per day)")
    ax.set_title("C  are the long relative spells actually hot?", fontsize=10,
                 fontweight="bold", loc="left")
    F.tidy(ax, grid_axis="both")

    F.title(fig, "Figure R7  Long-event audit: every event longer than %d days"
                 % K.LONG_EVENT_DAYS,
            "%s events qualify. No event is deleted on the basis of its length; a long "
            "run is evidence about the RULE as much as about the data."
            % "{:,}".format(len(ev)), y=1.06)
    F.footnote(fig, "The longest runs come from the absolute family, where a rule of "
                    "the form 'daily high above 80 degF for at least two consecutive "
                    "days' runs for most of a Texas summer by construction. "
                    "Classification rules are in event_audits/LONG_EVENT_REVIEW.md and "
                    "reproducible from tables/long_event_audit.csv; per-day detail for "
                    "the longest %d events in each family is in event_audits/."
               % 150, y=-0.06)
    p_ = F.savefig(fig, "r_fig_R7_long_event_audit.png")
    F.spec("R7", os.path.basename(p_),
           "surface and classify the events long enough to need a human look",
           "individual event",
           "tables/long_event_audit.csv",
           "counts and distributions over events longer than %d days"
           % K.LONG_EVENT_DAYS,
           "none",
           "that long events are common in the absolute family by construction, and "
           "that most long relative spells clear their threshold by a wide margin",
           "that any long event is an error; the audit classifies, it does not delete",
           "Long-event audit. Every event longer than %d days, with the evidence "
           "needed to judge it." % K.LONG_EVENT_DAYS,
           "the station-composition flag uses the raw GHCN contributing-station count, "
           "which is unavailable for fully gap-filled county-dates")


def fig_distributions(ann, summ):
    fig, axs = plt.subplots(1, 2, figsize=(16.2, 6.0))
    rel = [K.rel_id(p, d) for p in K.PERCENTILES for d in K.DURATIONS]
    labs = [cell_label(p, d) for p in K.PERCENTILES for d in K.DURATIONS]
    for ax, col, ttl, unit in (
            (axs[0], "annual_classified_day_count",
             "A  annual county-level classified-day distributions",
             "classified relative warm-spell days per county per year"),
            (axs[1], "annual_event_count",
             "B  annual county-level event-count distributions",
             "events per county per year")):
        data = [ann[ann["construct_id"] == cid][col].to_numpy() for cid in rel]
        bp = ax.boxplot(data, tick_labels=labs, patch_artist=True, showfliers=False,
                        widths=0.62, medianprops=dict(color="#111111", lw=1.7))
        for b in bp["boxes"]:
            b.set_facecolor(K.FAMILY_STYLE["relative"]["color"])
            b.set_alpha(0.7)
            b.set_edgecolor("#555555")
        rng = np.random.default_rng(K.BOOTSTRAP_SEED)
        for i, v in enumerate(data, start=1):
            sel = rng.choice(v, size=min(400, v.size), replace=False)
            ax.plot(i + rng.uniform(-0.15, 0.15, size=sel.size), sel, lw=0,
                    marker="o", ms=1.6, color="#572b05", alpha=0.2, zorder=3)
            ax.annotate("%.0f" % np.median(v), xy=(i, np.median(v)), xytext=(0, 8),
                        textcoords="offset points", ha="center", fontsize=7.5,
                        fontweight="bold",
                        bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.5))
        ax.set_xticklabels(labs, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel(unit)
        ax.set_title(ttl, fontsize=10, fontweight="bold", loc="left")
        F.tidy(ax)
    F.title(fig, "Figure R8  Annual county-level distributions replace the pooled "
                 "totals",
            "Each box is the distribution over %d counties x %d years of one county's "
            "count in one year." % (254, 11), y=1.05)
    F.footnote(fig, "The previous package reported a statewide pooled event total and "
                    "a per-county median of an eleven-year cumulative count. Neither "
                    "shows the spread that matters for a later linkage to "
                    "county-level outcome data. Points are a random sample of at most "
                    "400 annual county-level observations per box, drawn with a fixed "
                    "seed. %s" % NOT_EXPOSURE, y=-0.055)
    p_ = F.savefig(fig, "r_fig_R8_annual_distributions.png")
    F.spec("R8", os.path.basename(p_),
           "replace pooled totals with the annual county-level distributions behind "
           "them",
           "annual county-level observation",
           "tables/county_annual_relative_warm_spells.csv",
           "distribution over county-years of the annual count",
           "none",
           "the spread of annual county-level counts within each definition, which a "
           "pooled total conceals",
           "any between-county comparison without the data-quality indicator",
           "Annual county-level distributions of classified days and event counts for "
           "the nine relative warm-spell definitions.",
           "includes fully imputed counties; figure R5 gives the subset sensitivity")


def fig_rates_all(rates, flat):
    fams = ["relative", "hybrid", "absolute"]
    fig, axs = plt.subplots(1, 3, figsize=(16.6, 5.2), sharey=True)
    ymax = rates["classified_days_per_1000_valid"].max() * 1.1
    for ax, fam in zip(axs, fams):
        s = rates[rates["construct_family"] == fam]
        ids = sorted(s["construct_id"].unique())
        cmap = plt.get_cmap("YlOrBr")(np.linspace(0.3, 0.85, len(ids)))
        for col, cid in zip(cmap, ids):
            g = s[s["construct_id"] == cid].sort_values("month")
            ax.plot(g["month"], g["classified_days_per_1000_valid"], color=col,
                    lw=1.5, marker="o", ms=3.2, zorder=3,
                    label=g["short_label"].iloc[0])
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
        ax.set_ylim(0, ymax)
        ax.set_xlabel("calendar month")
        ax.set_title("%s (%d constructs)" % (K.FAMILY_STYLE[fam]["label"], len(ids)),
                     fontsize=10, fontweight="bold", loc="left")
        ax.legend(fontsize=5.6, ncol=2, framealpha=0.95)
        F.tidy(ax, grid_axis="both")
        F.warm_season_band(ax)
    axs[0].set_ylabel(K.RATE_AXIS)
    F.title(fig, "Figure R9  Monthly classification rates, all three construct "
                 "families on one scale",
            "Each family uses its OWN valid-record denominator. The three "
            "denominators were tested for equality rather than assumed equal.",
            y=1.06)
    F.footnote(fig, "Denominators: relative - the daily high is present AND a "
                    "historical threshold exists; hybrid - relative eligibility AND an "
                    "evaluable gate; absolute - the daily high is present. In this "
                    "state and period all three come to the same %s valid daily "
                    "county-level observations, because the gap-filled county-day "
                    "table has a daily high on every county-date and a walk-forward "
                    "threshold exists for every one of them. That equality is "
                    "DOCUMENTED in qa/eligibility_denominator_comparison.csv, not "
                    "assumed: in a state or period with genuine gaps the three would "
                    "differ and each rate would need its own denominator."
               % "{:,}".format(int(rates[rates["construct_family"] == "absolute"]
                                   ["valid_daily_observations"].sum() / 6)), y=-0.06)
    p_ = F.savefig(fig, "r_fig_R9_monthly_rates_all_families.png")
    F.spec("R9", os.path.basename(p_),
           "compare the seasonal profile of all three construct families on one scale "
           "with family-specific denominators",
           "daily county-level observation",
           "tables/monthly_classification_rates.csv; "
           "qa/eligibility_denominator_comparison.csv",
           "1000 x classified days / valid daily county-level observations, per month, "
           "per construct",
           "family-specific valid daily county-level observations",
           "that the absolute family is strongly seasonal while the relative family "
           "fires all year, on a shared scale and correct denominators",
           "that the equality of the three denominators generalises beyond this state "
           "and period",
           "Monthly classification rates for all three construct families, on "
           "identical y-axis scales, each using its own valid-record denominator.",
           "the denominators coincide here only because the gap-filled input has no "
           "missing daily highs")


def fig_profiles(prof, ann, mon):
    cid = K.PRIMARY_CONSTRUCT
    fig, axs = plt.subplots(2, 3, figsize=(16.6, 8.4))
    for ax, (_, r) in zip(axs.ravel(), prof.iterrows()):
        a = ann[(ann["construct_id"] == cid)
                & (ann["county_fips"] == r["county_fips"])].sort_values("year")
        ax.bar(a["year"], a["annual_classified_day_count"],
               color=K.FAMILY_STYLE["relative"]["color"], edgecolor="white", lw=0.5,
               zorder=3, label="classified days")
        ax.plot(a["year"], a["annual_event_count"] * 5, lw=0, marker="o", ms=5,
                mfc="white", mec="#572b05", mew=1.4, zorder=4,
                label="events (x5 for scale)")
        ax.set_xticks(a["year"][::2])
        ax.set_xticklabels([str(int(y)) for y in a["year"][::2]], fontsize=7,
                           rotation=45)
        ax.set_ylabel("days per year", fontsize=8)
        flag = ("  [%s]" % r["data_quality_label"]
                if r["fully_imputed_county"] else "")
        ax.set_title("%s County (%s)\n%s%s"
                     % (r["county_name"], r["county_fips"], r["profile_role"], flag),
                     fontsize=8.8, fontweight="bold", loc="left",
                     color=("#c0392b" if r["fully_imputed_county"] else K.COLOR_INK))
        ax.annotate("peak month %s   %.0f%% in %s   %.0f%% gap-filled"
                    % (r["peak_month"], r["pct_days_june_september"],
                       K.SEASON_LABEL["warm"], r["pct_analysis_days_imputed"]),
                    xy=(0.02, 0.93), xycoords="axes fraction", fontsize=7,
                    color=K.COLOR_INK_SOFT)
        F.tidy(ax)
    axs[0, 0].legend(fontsize=7, loc="upper right", framealpha=0.95)
    F.title(fig, "Figure R10  County-level example profiles, %s" % cid,
            "Six counties chosen to span the range, INCLUDING a fully imputed one. "
            "Every county-level result in this package carries its data-quality "
            "indicator.", y=1.05)
    F.footnote(fig, "Full per-county series are in county_profiles/. The fully imputed "
                    "county has no observed temperature at any point in the study "
                    "period: its values are inverse-distance interpolations from "
                    "neighbouring counties and describe the interpolation as much as "
                    "the county. It is shown here precisely so that its classified-day "
                    "count can be compared with counties that have real observations. "
                    "%s" % NOT_EXPOSURE, y=-0.05)
    p_ = F.savefig(fig, "r_fig_R10_county_profiles.png")
    F.spec("R10", os.path.basename(p_),
           "show what the construct looks like for individual counties, with data "
           "quality attached",
           "annual county-level observation within one county",
           "tables/county_profile_examples.csv; "
           "tables/county_annual_relative_warm_spells.csv; county_profiles/",
           "none; annual counts are plotted directly",
           "none",
           "that annual counts vary strongly between years within a county, and that a "
           "fully imputed county still produces a plausible-looking series",
           "that these six counties are representative; that the fully imputed "
           "county's series describes its actual climate",
           "County-level example profiles for %s. Six counties spanning the range of "
           "classified-day counts, including one with no observed temperature." % cid,
           "chosen by rank on cumulative classified days, not sampled")


# =============================================================================
def main():
    K.ensure_dirs()
    F.SPECS.clear()   # the spec list is shared; each script owns its own part
    t0 = time.time()
    K.log("=" * 78)
    K.log("r10  revised Part 2 and Part 3 figures")
    K.log("=" * 78)
    summ = pd.read_csv(os.path.join(T, "construct_summary.csv"))
    season = pd.read_csv(os.path.join(T, "seasonal_classification_shares.csv"))
    rates = pd.read_csv(os.path.join(T, "monthly_classification_rates.csv"))
    flat = pd.read_csv(os.path.join(K.DIR_QA, "flatness_criterion.csv"))
    jm = pd.read_csv(os.path.join(T, "definition_agreement_jaccard_matrix.csv"),
                     index_col=0)
    ge = pd.read_csv(os.path.join(T, "absolute_gate_effect.csv"))
    av = pd.read_csv(os.path.join(T, "absolute_vs_relative.csv"))
    cg = pd.read_csv(os.path.join(T, "county_gate_effect.csv"),
                     dtype={"county_fips": str})
    qual = pd.read_csv(os.path.join(T, "county_data_quality.csv"),
                       dtype={"county_fips": str})
    ann = pd.read_csv(os.path.join(T, "county_annual_all_constructs.csv"),
                      dtype={"county_fips": str})
    mon = pd.read_csv(os.path.join(T, "county_monthly_all_constructs.csv"),
                      dtype={"county_fips": str})
    sens = pd.read_csv(os.path.join(T, "imputation_sensitivity.csv"))
    ranks = pd.read_csv(os.path.join(T, "imputation_sensitivity_rankings.csv"))
    ev = pd.read_csv(os.path.join(T, "long_event_audit.csv"),
                     dtype={"county_fips": str})
    prof = pd.read_csv(os.path.join(T, "county_profile_examples.csv"),
                       dtype={"county_fips": str})
    cat = pd.read_csv(os.path.join(T, "individual_relative_warm_spell_events.csv"),
                      dtype={"county_fips": str})

    fig_e5(summ, season, flat)
    fig_e5b(jm, summ)
    fig_e6(rates, flat, season)
    fig_e7(ge, rates, season)
    fig_e8(summ, av, rates, ann)
    fig_e9(cg, qual)
    fig_imputation(sens, ranks)
    fig_timeline(cat, ann)
    fig_long_events(ev)
    fig_distributions(ann, summ)
    fig_rates_all(rates, flat)
    fig_profiles(prof, ann, mon)

    n = F.write_specs(os.path.join(K.DIR_QA, "_figure_manifest_part2.csv"))
    K.log("[write] %d figure manifest entries" % n)
    K.log("r10 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
