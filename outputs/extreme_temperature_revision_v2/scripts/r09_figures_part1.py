"""
=============================================================================
r09  --  revised Part 1 figures: E2, E3, E4 and the new comparison figures.
=============================================================================
  E2   distribution of county-level annual temperature values by state
  E2b  the same, with every county contributing ONE 1979-2025 value
  E3   county-level temperature comparison across periods
  E4   monthly LEVEL (top) and monthly PERIOD DIFFERENCE (bottom)
  F1   current pooled result against the revised equal-county result
  F8   consistent-county sample against strict-balanced sample
  F9   external benchmark: what was attempted and why it is unavailable
  F11  descriptive trend sensitivity (Sen slope and OLS slope)

Every panel is drawn from a saved table; nothing is recomputed here except
plotting arithmetic. Titles avoid trend language: a difference between two
period summaries is called a difference, never warming, never a rate.
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
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K
import r_figlib as F

T = K.DIR_TABLES
NOT_CAUSAL = ("This is a descriptive comparison. It does not establish a causal "
              "climate trend, an occupational-injury effect, or individual worker "
              "exposure.")


# =============================================================================
def fig_e2(annual, cp):
    """E2: the distribution, with the required title and the required warning."""
    fig, axs = plt.subplots(1, 3, figsize=(15.4, 5.8))
    q = annual[annual["meets_annual_coverage_requirement"]]
    for ax, var in zip(axs, K.VAR_KEYS):
        data, labels, colors = [], [], []
        for st in K.STATES:
            v = q[(q["state"] == st) & (q["variable"] == var)]["period_mean_f"].to_numpy()
            data.append(v)
            labels.append(st)
            colors.append(K.STATE_STYLE[st]["color"])
        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, showfliers=False,
                        widths=0.6, medianprops=dict(color="#111111", lw=1.8))
        for b, c in zip(bp["boxes"], colors):
            b.set_facecolor(c)
            b.set_alpha(0.5)
            b.set_edgecolor(c)
        rng = np.random.default_rng(K.BOOTSTRAP_SEED)
        for i, (v, st) in enumerate(zip(data, K.STATES), start=1):
            x = i + rng.uniform(-0.15, 0.15, size=v.size)
            ax.plot(x, v, lw=0, marker=K.STATE_STYLE[st]["marker"], ms=1.7,
                    color=K.STATE_STYLE[st]["color"], alpha=0.22, zorder=3)
            ax.annotate("%.1f" % np.median(v), xy=(i, np.median(v)), xytext=(0, 9),
                        textcoords="offset points", ha="center", fontsize=8,
                        fontweight="bold", color="#111111",
                        bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.6))
            ax.annotate("n=%s" % "{:,}".format(v.size), xy=(i, ax.get_ylim()[0]),
                        xytext=(0, 4), textcoords="offset points", ha="center",
                        fontsize=6.5, color=K.COLOR_INK_SOFT)
        ax.set_title(K.VAR_PERIOD_LABEL[var], fontsize=10.5, fontweight="bold")
        ax.set_ylabel("%s (degF)" % K.VAR_PERIOD_LABEL[var])
        ax.set_xlabel("state")
        F.tidy(ax)
    F.title(fig, "Figure E2  Distribution of county-level annual average "
                 "temperatures by state, %s" % K.YEARS_LABEL,
            "Each point represents one county's annual value; boxes summarize "
            "qualifying annual county-level observations.", y=1.045)
    fig.text(0.005, 0.965,
             "This figure combines THREE sources of variation and separates none of "
             "them: spatial variation among counties, year-to-year variation, and "
             "long-term change over the record. It is NOT a climatological normal.",
             fontsize=9, color="#8a2f24", fontweight="bold", ha="left", va="top")
    F.footnote(fig, "%s Unit of analysis: the annual county-level observation - one "
                    "county's mean daily value for one year - restricted to years with "
                    "at least %d valid daily county-level observations. Counties with "
                    "more reporting years contribute more points, so the boxes are NOT "
                    "an equal-county summary; figure E2b gives the equal-county "
                    "version. Source: raw observed GHCN county-day records, no "
                    "gap-filling. %s"
               % (K.PANEL_SENTENCE, K.MIN_DAYS_PER_COUNTY_YEAR, NOT_CAUSAL), y=-0.05)
    p = F.savefig(fig, "r_fig_E2_distribution_by_state.png")
    F.spec("E2", os.path.basename(p),
           "show how county-level annual temperature values are distributed within "
           "and between states",
           "annual county-level observation",
           "tables/county_annual_temperature.csv",
           "no aggregation; every qualifying annual county-level observation is "
           "plotted, with a box summarising the state's pooled distribution",
           "none (a distribution, not a rate)",
           "that the within-state spread is comparable to the between-state spread, "
           "so a single state number is a weak summary of exposure",
           "a climatological normal; a period level; a trend; any separation of "
           "spatial from temporal variation",
           "Distribution of county-level annual average temperatures by state, "
           "%s. Each point is one county's annual value; boxes summarise qualifying "
           "annual county-level observations. The figure combines spatial variation "
           "among counties, year-to-year variation and long-term change."
           % K.YEARS_LABEL,
           "counties with more qualifying years carry more visual weight; see E2b")


def fig_e2b(cp):
    """E2b: one value per county, so reporting frequency carries no visual weight."""
    fig, axs = plt.subplots(1, 3, figsize=(15.4, 5.6))
    s = cp[cp["sample"] == K.SAMPLE_A_NAME]
    per_county = (s.groupby(["state", "variable", "county_fips"], observed=True)
                  ["county_period_value_f"].mean().reset_index())
    for ax, var in zip(axs, K.VAR_KEYS):
        data, labels, colors = [], [], []
        for st in K.STATES:
            v = per_county[(per_county["state"] == st)
                           & (per_county["variable"] == var)]["county_period_value_f"]
            data.append(v.to_numpy())
            labels.append(st)
            colors.append(K.STATE_STYLE[st]["color"])
        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, showfliers=False,
                        widths=0.6, medianprops=dict(color="#111111", lw=1.8))
        for b, c in zip(bp["boxes"], colors):
            b.set_facecolor(c)
            b.set_alpha(0.5)
            b.set_edgecolor(c)
        rng = np.random.default_rng(K.BOOTSTRAP_SEED)
        for i, (v, st) in enumerate(zip(data, K.STATES), start=1):
            ax.plot(i + rng.uniform(-0.13, 0.13, size=v.size), v, lw=0,
                    marker=K.STATE_STYLE[st]["marker"], ms=3.4,
                    color=K.STATE_STYLE[st]["color"],
                    markeredgecolor=K.STATE_STYLE[st]["edge"], markeredgewidth=0.4,
                    alpha=0.75, zorder=3)
            ax.annotate("%.1f" % np.median(v), xy=(i, np.median(v)), xytext=(0, 9),
                        textcoords="offset points", ha="center", fontsize=8,
                        fontweight="bold", color="#111111",
                        bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.6))
            ax.annotate("%d counties" % v.size, xy=(i, ax.get_ylim()[0]),
                        xytext=(0, 4), textcoords="offset points", ha="center",
                        fontsize=6.5, color=K.COLOR_INK_SOFT)
        ax.set_title(K.VAR_PERIOD_LABEL[var], fontsize=10.5, fontweight="bold")
        ax.set_ylabel("%s (degF)" % K.VAR_PERIOD_LABEL[var])
        ax.set_xlabel("state")
        F.tidy(ax)
    F.title(fig, "Figure E2b  County-level temperature by state, %s - one value per "
                 "county" % K.YEARS_LABEL,
            "Each point is a single county's whole-record value, so a county with 47 "
            "reporting years carries no more weight than one with 30.", y=1.05)
    F.footnote(fig, "Unit of analysis: the county. Each county contributes ONE value, "
                    "the mean of its period values across the five comparison periods, "
                    "computed on the consistent-county sample (Sample A). Compare with "
                    "figure E2, where every qualifying annual county-level observation "
                    "is plotted and counties with longer records dominate. %s"
               % NOT_CAUSAL, y=-0.05)
    p = F.savefig(fig, "r_fig_E2b_one_value_per_county.png")
    F.spec("E2b", os.path.basename(p),
           "remove the reporting-frequency weighting from E2",
           "county",
           "tables/county_period_temperature.csv",
           "county period mean over the five periods; one value per county",
           "none (a distribution, not a rate)",
           "the between-county distribution of temperature level within each state, "
           "with equal weight per county",
           "a trend; a causal claim; a statement about counties excluded from "
           "Sample A",
           "County-level temperature by state, %s, with every county contributing a "
           "single value. Sample A (consistent-county)." % K.YEARS_LABEL,
           "restricted to Sample A counties, which excludes between 37%% and 72%% of "
           "counties depending on the state")


# =============================================================================
def fig_e3(sp, comp):
    """E3: period levels and period differences, equal-county, with intervals."""
    fig, axs = plt.subplots(2, 3, figsize=(16.0, 10.4),
                            gridspec_kw={"hspace": 0.55, "wspace": 0.28})
    x = np.arange(len(K.PERIOD_ORDER))
    for j, var in enumerate(K.VAR_KEYS):
        # ---- top: period level, Sample A ----------------------------------
        ax = axs[0, j]
        ends = []
        for st in K.STATES:
            s = sp[(sp["sample"] == K.SAMPLE_A_NAME) & (sp["state"] == st)
                   & (sp["variable"] == var)].set_index("period").reindex(
                K.PERIOD_ORDER).reset_index()
            ax.fill_between(x, s["median_ci_low_f"], s["median_ci_high_f"],
                            color=K.STATE_STYLE[st]["color"], alpha=0.16, lw=0,
                            zorder=2)
            F.state_line(ax, x, s["median_across_counties_f"], st, lw=1.8, ms=6,
                         zorder=3)
            ends.append((st, x[-1], float(s["median_across_counties_f"].iloc[-1])))
        F.label_series_ends(ax, ends)
        ax.set_xticks(x)
        ax.set_xticklabels([p if p != K.RECENT_PERIOD else p + "\n(6 years)"
                            for p in K.PERIOD_ORDER], fontsize=7.5, rotation=20)
        ax.set_ylabel("%s (degF)" % K.VAR_PERIOD_LABEL[var])
        ax.set_title("%s - period level" % K.VAR_PERIOD_LABEL[var], fontsize=9.5,
                     fontweight="bold", loc="left")
        ax.set_xlim(-0.4, len(x) - 0.1)
        F.tidy(ax, grid_axis="both")
        # ---- bottom: difference from the base period, both samples ---------
        ax = axs[1, j]
        xs = np.arange(len(K.STATES))
        for k, sample in enumerate(K.SAMPLES):
            vals, los, his, ns = [], [], [], []
            for st in K.STATES:
                s = sp[(sp["sample"] == sample) & (sp["state"] == st)
                       & (sp["variable"] == var) & (sp["period"] == K.RECENT_PERIOD)]
                if len(s):
                    r = s.iloc[0]
                    vals.append(r["difference_of_medians_vs_base_f"])
                    los.append(r["difference_ci_low_f"])
                    his.append(r["difference_ci_high_f"])
                    ns.append(int(r["contributing_counties"]))
                else:
                    vals.append(np.nan); los.append(np.nan); his.append(np.nan)
                    ns.append(0)
            sty = K.SAMPLE_STYLE[sample]
            off = (k - 0.5) * 0.4
            ax.bar(xs + off, vals, width=0.36, color=sty["color"], alpha=0.85,
                   hatch=sty["hatch"], edgecolor="white", lw=0.7, zorder=3,
                   label=sty["label"])
            ax.errorbar(xs + off, vals,
                        yerr=[np.array(vals) - np.array(los),
                              np.array(his) - np.array(vals)],
                        fmt="none", ecolor="#333333", elinewidth=1.0, capsize=2.5,
                        zorder=4)
            for xi, v, n in zip(xs + off, vals, ns):
                ax.annotate("%+.2f\nn=%d" % (v, n), (xi, v), xytext=(0, 6),
                            textcoords="offset points", ha="center", fontsize=6.2,
                            color=K.COLOR_INK)
        ax.axhline(0, color="#333333", lw=1.0, zorder=2)
        ax.set_xticks(xs)
        ax.set_xticklabels(K.STATES, fontsize=8.5)
        ax.set_ylabel("difference in %s\n%s to %s (degF)"
                      % (K.VAR_PERIOD_LABEL[var].lower(), K.BASE_PERIOD,
                         K.RECENT_PERIOD))
        ax.set_title("difference from %s" % K.BASE_PERIOD, fontsize=9.5,
                     fontweight="bold", loc="left")
        if j == 0:
            ax.legend(fontsize=7.5, loc="upper left", framealpha=0.95)
        F.tidy(ax)
    axs[0, 0].legend(fontsize=7, ncol=2, loc="lower right", framealpha=0.95)
    F.title(fig, "Figure E3  County-level temperature comparison across periods, "
                 "%s to %s" % (K.BASE_PERIOD, K.RECENT_PERIOD),
            "%s is a SIX-YEAR RECENT PERIOD, not a decade. Bars show the difference "
            "between two period summaries with a 95%% bootstrap interval across "
            "counties; they are not a trend or a rate." % K.RECENT_PERIOD, y=1.0)
    F.footnote(fig, "Aggregation: daily county-level observations -> annual "
                    "county-level observation -> ONE value per county per period -> "
                    "median across counties. Counties are resampled %d times for the "
                    "interval; annual observations are never resampled. Sample A "
                    "requires at least 8 qualifying years in each full decade and 5 in "
                    "%s; Sample B requires exactly %d annual observations in every "
                    "period. Shading in the top row is the 95%% interval on the level. "
                    "%s"
               % (K.BOOTSTRAP_N, K.RECENT_PERIOD, K.SAMPLE_B_YEARS_PER_PERIOD,
                  NOT_CAUSAL), y=-0.012)
    p = F.savefig(fig, "r_fig_E3_period_comparison.png")
    F.spec("E3", os.path.basename(p),
           "compare county-level temperature summaries between prespecified periods "
           "with equal weight per county",
           "county (one value per county per period)",
           "tables/state_period_temperature_equal_county.csv",
           "county period mean of annual county-level observations, then the median "
           "across counties; difference of medians against %s" % K.BASE_PERIOD,
           "none (a level and a difference of levels, not a rate)",
           "that the recent-period median differs from the %s median under this "
           "aggregation, and by how much, with an interval and a county count"
           % K.BASE_PERIOD,
           "a climate trend, a warming rate, or any causal attribution; the two "
           "samples are sensitivity cases, not independent replications",
           "County-level temperature comparison across periods, %s to %s. Each county "
           "contributes one value per period; the state summary is the median across "
           "counties with a 95%% bootstrap interval over counties. %s is a six-year "
           "recent period." % (K.BASE_PERIOD, K.RECENT_PERIOD, K.RECENT_PERIOD),
           "Sample A and Sample B retain different county sets, and both exclude a "
           "large share of counties; the excluded counties are not missing at random")


# =============================================================================
def fig_e4(sanity, smp):
    """E4: LEVEL on top, PERIOD DIFFERENCE below, shaded identically."""
    fig, axs = plt.subplots(2, 2, figsize=(15.2, 9.8),
                            gridspec_kw={"height_ratios": [1.1, 1]})
    for ax, var in zip(axs[0], ("Tmax", "Tmin")):
        ends = []
        for st in K.STATES:
            s = sanity[(sanity["state"] == st)
                       & (sanity["variable"] == var)].sort_values("month")
            ax.fill_between(s["month"], s["p25_across_counties_f"],
                            s["p75_across_counties_f"],
                            color=K.STATE_STYLE[st]["color"], alpha=0.13, lw=0,
                            zorder=2)
            F.state_line(ax, s["month"], s["median_across_counties_f"], st, lw=1.8,
                         ms=5, zorder=3)
            ends.append((st, 12, float(s["median_across_counties_f"].iloc[-1])))
        F.label_series_ends(ax, ends)
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
        ax.set_xlim(0.5, 13.0)
        ax.set_ylabel("%s (degF)" % K.VAR_PERIOD_LABEL[var])
        ax.set_title("LEVEL - %s by calendar month" % K.VAR_PERIOD_LABEL[var],
                     fontsize=9.5, fontweight="bold", loc="left")
        F.tidy(ax, grid_axis="both")
        F.warm_season_band(ax)
    axs[0, 0].legend(fontsize=7.5, ncol=2, loc="lower center", framealpha=0.95)

    diff = smp[(smp["sample"] == K.SAMPLE_A_NAME)
               & (smp["period"] == K.RECENT_PERIOD)]
    for ax, var in zip(axs[1], ("Tmax", "Tmin")):
        x = np.arange(12)
        w = 0.8 / len(K.STATES)
        for i, st in enumerate(K.STATES):
            s = diff[(diff["state"] == st) & (diff["variable"] == var)].sort_values(
                "month")
            v = s.set_index("month").reindex(range(1, 13))[
                "median_paired_county_difference_f"].to_numpy()
            ax.bar(x + i * w - 0.4 + w / 2, v, width=w * 0.9,
                   color=K.STATE_STYLE[st]["color"],
                   edgecolor=K.STATE_STYLE[st]["edge"], lw=0.4,
                   label=K.STATE_STYLE[st]["label"], zorder=3)
        ax.axhline(0, color="#333333", lw=1.0, zorder=2)
        ax.set_xticks(x)
        ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
        ax.set_xlim(-0.7, 11.7)
        ax.set_ylabel("difference in %s\n%s minus %s (degF)"
                      % (K.VAR_PERIOD_LABEL[var].lower(), K.RECENT_PERIOD,
                         K.BASE_PERIOD))
        ax.set_title("DIFFERENCE - %s, %s minus %s"
                     % (K.VAR_PERIOD_LABEL[var], K.RECENT_PERIOD, K.BASE_PERIOD),
                     fontsize=9.5, fontweight="bold", loc="left")
        F.tidy(ax)
        # the SAME warm-season band as the top row, on the 0-11 bar axis
        F.warm_season_band(ax, label=False, x0=4.5, x1=8.5)
    axs[1, 0].legend(fontsize=7, ncol=3, loc="upper left", framealpha=0.95)

    F.title(fig, "Figure E4  Monthly county-level temperature: LEVEL and PERIOD "
                 "DIFFERENCE", None, y=1.055)
    fig.text(0.005, 1.028,
             "Top row: Median county-level monthly average temperature, %s.    "
             "Bottom row: Difference between %s and %s monthly county-level values."
             % (K.YEARS_LABEL, K.BASE_PERIOD, K.RECENT_PERIOD),
             fontsize=9.5, color=K.COLOR_INK, ha="left", va="top")
    fig.text(0.005, 0.996,
             "TEMPERATURE LEVEL AND PERIOD DIFFERENCE ARE DIFFERENT QUANTITIES. "
             "%s remains the hottest part of the year in every state (top). A larger "
             "period difference in winter or autumn does NOT mean those months are "
             "hotter than summer (bottom); it means they changed more between the two "
             "periods." % K.WARM_SEASON_PHRASE,
             fontsize=9.2, color="#8a2f24", fontweight="bold", ha="left", va="top")
    F.footnote(fig, "Top row: each county contributes one value per calendar month, "
                    "averaged over its qualifying monthly county-level summaries; the "
                    "line is the median across counties and the band the interquartile "
                    "range across counties (tables/"
                    "revised_temperature_monthly_sanity_check.csv). Bottom row: the "
                    "median across counties of each county's own %s-minus-%s "
                    "difference, on the consistent-county sample (tables/"
                    "state_month_period_temperature_equal_county.csv). Both rows shade "
                    "the SAME months. A monthly county-level summary needs at least %d "
                    "valid daily county-level observations. %s"
               % (K.RECENT_PERIOD, K.BASE_PERIOD, K.MIN_DAYS_PER_COUNTY_MONTH,
                  NOT_CAUSAL), y=-0.012)
    p = F.savefig(fig, "r_fig_E4_monthly_level_and_difference.png")
    F.spec("E4", os.path.basename(p),
           "keep the seasonal LEVEL and the seasonal PERIOD DIFFERENCE visually and "
           "verbally separate",
           "county (one value per county per month, and per county per period)",
           "tables/revised_temperature_monthly_sanity_check.csv; "
           "tables/state_month_period_temperature_equal_county.csv",
           "top: median across counties of each county's monthly value. bottom: "
           "median across counties of each county's own period difference",
           "none (levels and differences of levels)",
           "that June-September has the highest temperatures, and separately that the "
           "cool season shows the larger period difference",
           "that the cool season is hotter than summer; that the difference is a "
           "trend; that the cool season causes off-season classifications",
           "Monthly county-level temperature. Top: median county-level monthly "
           "average temperature, %s. Bottom: difference between %s and %s monthly "
           "county-level values, consistent-county sample. Prespecified warm season: "
           "June-September." % (K.YEARS_LABEL, K.BASE_PERIOD, K.RECENT_PERIOD),
           "the bottom row is a two-period difference on a fixed county sample, not a "
           "fitted monthly trend")


# =============================================================================
def fig_current_vs_revised(comp):
    """F1: what the aggregation correction actually changes."""
    fig, axs = plt.subplots(1, 3, figsize=(16.0, 5.4))
    for ax, var in zip(axs, K.VAR_KEYS):
        c = comp[(comp["variable"] == var) & (comp["period"] == K.RECENT_PERIOD)]
        xs = np.arange(len(K.STATES))
        cur = [float(c[(c["state"] == st) & (c["sample"] == K.SAMPLE_A_NAME)]
                     ["current_published_change_vs_base_f"].iloc[0]) for st in K.STATES]
        ax.bar(xs - 0.28, cur, width=0.26, color=K.CURRENT_STYLE["color"],
               hatch=K.CURRENT_STYLE["hatch"], edgecolor="white", lw=0.6,
               label="Current: pooled annual observations", zorder=3)
        for k, sample in enumerate(K.SAMPLES):
            s = c[c["sample"] == sample]
            v = [float(s[s["state"] == st]["revised_change_vs_base_f"].iloc[0])
                 for st in K.STATES]
            lo = [float(s[s["state"] == st]["revised_change_ci_low_f"].iloc[0])
                  for st in K.STATES]
            hi = [float(s[s["state"] == st]["revised_change_ci_high_f"].iloc[0])
                  for st in K.STATES]
            sty = K.SAMPLE_STYLE[sample]
            off = 0.0 + k * 0.28
            ax.bar(xs + off, v, width=0.26, color=sty["color"], hatch=sty["hatch"],
                   edgecolor="white", lw=0.6, label="Revised: " + sty["label"],
                   zorder=3)
            ax.errorbar(xs + off, v,
                        yerr=[np.array(v) - np.array(lo), np.array(hi) - np.array(v)],
                        fmt="none", ecolor="#333333", elinewidth=1.0, capsize=2.5,
                        zorder=4)
        ax.axhline(0, color="#333333", lw=1.0, zorder=2)
        ax.set_xticks(xs)
        ax.set_xticklabels(K.STATES, fontsize=9)
        ax.set_ylabel("difference, %s to %s (degF)" % (K.BASE_PERIOD, K.RECENT_PERIOD))
        ax.set_title(K.VAR_PERIOD_LABEL[var], fontsize=10, fontweight="bold",
                     loc="left")
        F.tidy(ax)
    axs[0].legend(fontsize=7.5, loc="upper left", framealpha=0.95)
    F.title(fig, "Figure R1  What the aggregation correction changes",
            "The current package weights each county by how many years it reported. "
            "The revised estimate gives every county exactly one value per period and "
            "reports an interval across counties - which the current package never "
            "did.", y=1.06)
    F.footnote(fig, "Grey bars reproduce the published current result (tables/"
                    "e01_state_decade_temperature.csv of the current package, balanced "
                    "panel). Coloured bars are the revised equal-county estimate with a "
                    "95%% bootstrap interval over counties. The point estimates move by "
                    "up to %.2f degF; the intervals are wide enough that several "
                    "state-to-state orderings in the current package are not supported. "
                    "%s"
               % (comp["change_absolute_difference_f"].abs().max(), NOT_CAUSAL),
               y=-0.06)
    p = F.savefig(fig, "r_fig_R1_current_vs_revised_period_comparison.png")
    F.spec("R1", os.path.basename(p),
           "show the size of the aggregation defect being corrected",
           "county (revised) versus pooled annual county-level observation (current)",
           "tables/period_comparison_current_vs_revised.csv",
           "current: median over pooled annual observations. revised: median across "
           "counties of each county's period mean",
           "none",
           "that the choice of aggregation changes the reported period difference, and "
           "that the revised difference carries a wide interval",
           "that either estimate is the true change; that the difference is a trend",
           "The aggregation correction. Grey: the current pooled result. Coloured: the "
           "revised equal-county result with a 95% bootstrap interval across counties.",
           "the two estimates also use different county samples, so the change mixes "
           "the weighting correction with the sample correction; "
           "tables/period_comparison_current_vs_revised.csv separates them")


def fig_samples(sp, members):
    """F8: consistent-county against strict-balanced."""
    fig, axs = plt.subplots(1, 2, figsize=(14.0, 5.4),
                            gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axs[0]
    xs = np.arange(len(K.STATES))
    counts = {}
    for k, sample in enumerate(K.SAMPLES + ["current"]):
        if sample == "current":
            continue
        n = [int(((members["sample"] == sample) & (members["state"] == st)
                  & (members["variable"] == "Tmax")).sum()) for st in K.STATES]
        counts[sample] = n
        sty = K.SAMPLE_STYLE[sample]
        ax.bar(xs + (k - 0.5) * 0.38, n, width=0.36, color=sty["color"],
               hatch=sty["hatch"], edgecolor="white", lw=0.6, label=sty["label"],
               zorder=3)
        for xi, v in zip(xs + (k - 0.5) * 0.38, n):
            ax.annotate("%d" % v, (xi, v), xytext=(0, 3),
                        textcoords="offset points", ha="center", fontsize=7)
    ax.set_xticks(xs)
    ax.set_xticklabels(K.STATES, fontsize=9)
    ax.set_ylabel("counties retained (daily high temperature)")
    ax.set_title("A  how many counties each rule keeps", fontsize=10,
                 fontweight="bold", loc="left")
    ax.legend(fontsize=7.5)
    F.tidy(ax)

    ax = axs[1]
    for k, sample in enumerate(K.SAMPLES):
        v, lo, hi = [], [], []
        for st in K.STATES:
            s = sp[(sp["sample"] == sample) & (sp["state"] == st)
                   & (sp["variable"] == "Tmax") & (sp["period"] == K.RECENT_PERIOD)]
            r = s.iloc[0]
            v.append(r["difference_of_medians_vs_base_f"])
            lo.append(r["difference_ci_low_f"])
            hi.append(r["difference_ci_high_f"])
        sty = K.SAMPLE_STYLE[sample]
        off = (k - 0.5) * 0.3
        ax.errorbar(np.array(v), xs + off,
                    xerr=[np.array(v) - np.array(lo), np.array(hi) - np.array(v)],
                    fmt=("o" if k == 0 else "s"), ms=7, color=sty["color"],
                    ecolor=sty["color"], elinewidth=2.0, capsize=3,
                    markeredgecolor="white", markeredgewidth=0.8, label=sty["label"],
                    zorder=3)
        for vi, yi in zip(v, xs + off):
            ax.annotate("%+.2f" % vi, (vi, yi), xytext=(0, 8),
                        textcoords="offset points", ha="center", fontsize=7)
    ax.axvline(0, color="#333333", lw=1.0, zorder=2)
    ax.set_yticks(xs)
    ax.set_yticklabels([K.STATE_LABEL[s] for s in K.STATES], fontsize=9)
    ax.set_xlabel("difference in average daily high temperature, %s to %s (degF)"
                  % (K.BASE_PERIOD, K.RECENT_PERIOD))
    ax.set_title("B  does the sample rule change the answer?", fontsize=10,
                 fontweight="bold", loc="left")
    ax.legend(fontsize=7.5, loc="lower right")
    F.tidy(ax, grid_axis="x")
    F.title(fig, "Figure R2  Consistent-county sample against strict-balanced sample",
            "Sample A requires a minimum number of qualifying years in every period. "
            "Sample B requires the SAME number in every period. Neither is the "
            "current package's rule, which required only one qualifying year per "
            "period.", y=1.06)
    F.footnote(fig, "The intervals overlap for every state, so the two sample rules do "
                    "not give materially different answers here - but they retain "
                    "different counties, and both retain far fewer than the current "
                    "'balanced panel'. Bars and intervals: 95%% bootstrap over "
                    "counties, %d resamples. %s" % (K.BOOTSTRAP_N, NOT_CAUSAL), y=-0.06)
    p = F.savefig(fig, "r_fig_R2_consistent_vs_strict_balanced.png")
    F.spec("R2", os.path.basename(p),
           "test whether the period difference depends on which balancing rule is used",
           "county",
           "tables/sample_membership_counties.csv; "
           "tables/state_period_temperature_equal_county.csv",
           "county period mean, then median across counties, under two prespecified "
           "county-selection rules",
           "none",
           "that the two sample rules retain different county sets but give period "
           "differences whose intervals overlap in every state",
           "that either sample is unbiased, or that the excluded counties resemble the "
           "retained ones",
           "Consistent-county sample against strict-balanced sample. Panel A: counties "
           "retained. Panel B: the period difference with a 95% bootstrap interval "
           "across counties.",
           "both samples exclude the counties with the shortest records, which are "
           "disproportionately rural")


def fig_benchmark(idt, summary):
    """F9: the benchmark result is a negative one, and is drawn as such."""
    fig, axs = plt.subplots(1, 2, figsize=(14.4, 5.2),
                            gridspec_kw={"width_ratios": [1.1, 1]})
    ax = axs[0]
    lab = ["%s %s" % (r["state"], r["variable"]) for _, r in idt.iterrows()]
    y = np.arange(len(lab))
    share = idt["share_identical"].to_numpy() * 100.0
    ax.barh(y, share, color="#8a8a8a", edgecolor="white", lw=0.6, zorder=3)
    for yi, v, n in zip(y, share, idt["matched_daily_records"]):
        ax.annotate("%.2f%%  (%s records)" % (v, "{:,}".format(int(n))), (v, yi),
                    xytext=(4, 0), textcoords="offset points", va="center",
                    fontsize=7, color=K.COLOR_INK)
    ax.set_yticks(y)
    ax.set_yticklabels(lab, fontsize=8)
    ax.set_xlim(0, 128)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("percentage of matched daily records that are IDENTICAL")
    ax.set_title("A  the candidate benchmark is the same data", fontsize=10,
                 fontweight="bold", loc="left")
    F.tidy(ax, grid_axis="x")

    ax = axs[1]
    ax.axis("off")
    rows = [(r["comparison_label"], "available" if r["available"] else "NOT AVAILABLE")
            for _, r in summary.iterrows()]
    ax.text(0, 1.0, "B  status of each required comparison", fontsize=10,
            fontweight="bold", va="top", transform=ax.transAxes)
    for i, (name, st) in enumerate(rows):
        yy = 0.88 - i * 0.125
        ax.text(0.02, yy, name, fontsize=9, va="center", transform=ax.transAxes,
                color=K.COLOR_INK)
        ax.text(0.98, yy, st, fontsize=9, va="center", ha="right",
                transform=ax.transAxes, fontweight="bold",
                color=("#c0392b" if st != "available" else "#008300"))
        ax.plot([0.02, 0.98], [yy - 0.055, yy - 0.055], color="#e0e0e0", lw=0.8,
                transform=ax.transAxes, clip_on=False)
    ax.text(0.02, 0.06,
            "An independent, spatially consistent product\n"
            "(nClimGrid-Daily, PRISM, Daymet temperature) is\n"
            "not present in this repository. Obtaining one is a\n"
            "recommended next action.",
            fontsize=8, va="bottom", transform=ax.transAxes, color="#8a2f24",
            fontweight="bold")
    F.title(fig, "Figure R3  External benchmarking could not be performed",
            "The only second county-day temperature table in the repository is "
            "byte-identical to the project data on every matched record, so it "
            "duplicates rather than validates it.", y=1.06)
    F.footnote(fig, "Candidate: %s. Its build script documents a nearest-station "
                    "county assignment, which would have made it a usable method "
                    "benchmark; the delivered file does not differ from the project "
                    "data at all. Evidence: qa/benchmark_identity_test.csv. No "
                    "agreement statistic is reported against it, because agreement "
                    "with a copy of oneself is not validation." % K.BENCHMARK_NAME,
               y=-0.06)
    p = F.savefig(fig, "r_fig_R3_external_benchmark.png")
    F.spec("R3", os.path.basename(p),
           "record that external validation was attempted and why it failed",
           "daily county-level record (panel A); required comparison (panel B)",
           "qa/benchmark_identity_test.csv; tables/benchmark_comparison_summary.csv",
           "share of matched daily records that are identical between the two products",
           "matched daily county-level records",
           "that no independent temperature product is available in this repository, "
           "so none of the required external comparisons can be made",
           "any statement that the project temperature values agree, or disagree, with "
           "an independent product",
           "External benchmarking could not be performed. The candidate product is "
           "identical to the project data on all 2,938,070 matched daily county-level "
           "records.",
           "the identity test covers only the benchmark's 2015-2024 window; nothing is "
           "known about earlier years either way")


def fig_trends(tr, ser):
    """F11: descriptive slopes, with the required wording."""
    fig, axs = plt.subplots(1, 2, figsize=(15.4, 5.6),
                            gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axs[0]
    s = ser[ser["series"] == "consistent_county_sample_A"]
    ends = []
    for st in K.STATES:
        g = s[(s["state"] == st) & (s["variable"] == "Tmax")].sort_values("year")
        F.state_line(ax, g["year"], g["median_across_counties_f"], st, lw=1.2, ms=2.6,
                     alpha=0.9)
        ends.append((st, float(g["year"].iloc[-1]),
                     float(g["median_across_counties_f"].iloc[-1])))
    F.label_series_ends(ax, ends)
    ax.set_xlabel("year")
    ax.set_ylabel("%s (degF)" % K.VAR_PERIOD_LABEL["Tmax"])
    ax.set_title("A  annual median across counties, consistent-county sample",
                 fontsize=10, fontweight="bold", loc="left")
    ax.legend(fontsize=7, ncol=3, loc="lower right", framealpha=0.95)
    F.tidy(ax, grid_axis="both")

    ax = axs[1]
    series = ["all_reporting_counties", "consistent_county_sample_A",
              "consistent_county_excluding_recent_period", "stable_station_subset"]
    marks = ["o", "s", "D", "^"]
    ys = np.arange(len(K.STATES))
    for k, lab in enumerate(series):
        v, lo, hi = [], [], []
        for st in K.STATES:
            g = tr[(tr["series"] == lab) & (tr["state"] == st)
                   & (tr["variable"] == "Tmax")]
            if len(g):
                v.append(g["sen_slope_f_per_decade"].iloc[0])
                lo.append(g["sen_ci_low_f_per_decade"].iloc[0])
                hi.append(g["sen_ci_high_f_per_decade"].iloc[0])
            else:
                v.append(np.nan); lo.append(np.nan); hi.append(np.nan)
        off = (k - 1.5) * 0.17
        col = ["#2a78d6", "#008300", "#ae5c13", "#4a3aa7"][k]
        ax.errorbar(v, ys + off,
                    xerr=[np.array(v) - np.array(lo), np.array(hi) - np.array(v)],
                    fmt=marks[k], ms=5.5, color=col, ecolor=col, elinewidth=1.4,
                    capsize=2.5, markeredgecolor="white", markeredgewidth=0.6,
                    label=lab.replace("_", " "), zorder=3)
    ax.axvline(0, color="#333333", lw=1.0, zorder=2)
    ax.set_yticks(ys)
    ax.set_yticklabels([K.STATE_LABEL[s] for s in K.STATES], fontsize=9)
    ax.set_xlabel("Sen slope, degF per decade (95% interval)")
    ax.set_title("B  descriptive slope under four sensitivity cases", fontsize=10,
                 fontweight="bold", loc="left")
    ax.legend(fontsize=6.8, loc="lower right", framealpha=0.95)
    F.tidy(ax, grid_axis="x")
    F.title(fig, "Figure R4  Descriptive trend sensitivity, daily high temperature",
            "A period difference is not a trend. These are Theil-Sen slopes fitted to "
            "the annual median across counties, reported as descriptive models.",
            y=1.06)
    F.footnote(fig, "The annual state summary increased by between %.2f and %.2f degF "
                    "per decade across the five states under this descriptive model "
                    "(consistent-county sample). This result may reflect climate "
                    "change, station-network composition, data coverage, or remaining "
                    "inhomogeneity and does not isolate causation. The stable-station "
                    "subset is thin - %s - so that case is weak outside Texas and "
                    "Florida. An ordinary least-squares slope is reported alongside in "
                    "tables/trend_sensitivity.csv."
               % (tr[(tr["series"] == "consistent_county_sample_A")
                     & (tr["variable"] == "Tmax")]["sen_slope_f_per_decade"].min(),
                  tr[(tr["series"] == "consistent_county_sample_A")
                     & (tr["variable"] == "Tmax")]["sen_slope_f_per_decade"].max(),
                  ", ".join("%s n=%d" % (st, int(
                      tr[(tr["series"] == "stable_station_subset")
                         & (tr["state"] == st)
                         & (tr["variable"] == "Tmax")]["counties_median"].iloc[0]))
                      for st in K.STATES
                      if len(tr[(tr["series"] == "stable_station_subset")
                                & (tr["state"] == st)
                                & (tr["variable"] == "Tmax")]))),
               y=-0.06)
    p = F.savefig(fig, "r_fig_R4_trend_sensitivity.png")
    F.spec("R4", os.path.basename(p),
           "estimate descriptive time-trend slopes so period differences are not "
           "mistaken for trends",
           "annual median across counties",
           "tables/state_annual_series.csv; tables/trend_sensitivity.csv",
           "Theil-Sen slope on the annual median across counties; 95% distribution-free "
           "Sen interval; OLS reported as a sensitivity case",
           "none",
           "that the annual state summary increased by X degF per decade under this "
           "descriptive model, and that the estimate is stable across four county "
           "samples",
           "causal attribution; separation of climate change from station-network "
           "change; any claim about individual counties",
           "Descriptive trend sensitivity for the average daily high temperature. "
           "Theil-Sen slopes on the annual median across counties, under four county "
           "samples.",
           "the stable-station subset contains fewer than three counties in Louisiana, "
           "Mississippi and Alabama, so that sensitivity case is uninformative there")


# =============================================================================
def main():
    K.ensure_dirs()
    F.SPECS.clear()   # the spec list is shared; each script owns its own part
    t0 = time.time()
    K.log("=" * 78)
    K.log("r09  revised Part 1 figures")
    K.log("=" * 78)
    annual = pd.read_csv(os.path.join(T, "county_annual_temperature.csv"),
                         dtype={"county_fips": str})
    cp = pd.read_csv(os.path.join(T, "county_period_temperature.csv"),
                     dtype={"county_fips": str})
    sp = pd.read_csv(os.path.join(T, "state_period_temperature_equal_county.csv"))
    smp = pd.read_csv(os.path.join(T, "state_month_period_temperature_equal_county.csv"))
    sanity = pd.read_csv(os.path.join(T, "revised_temperature_monthly_sanity_check.csv"))
    comp = pd.read_csv(os.path.join(T, "period_comparison_current_vs_revised.csv"))
    members = pd.read_csv(os.path.join(T, "sample_membership_counties.csv"),
                          dtype={"county_fips": str})
    tr = pd.read_csv(os.path.join(T, "trend_sensitivity.csv"))
    ser = pd.read_csv(os.path.join(T, "state_annual_series.csv"))
    idt = pd.read_csv(os.path.join(K.DIR_QA, "benchmark_identity_test.csv"))
    bsum = pd.read_csv(os.path.join(T, "benchmark_comparison_summary.csv"))

    fig_e2(annual, cp)
    fig_e2b(cp)
    fig_e3(sp, comp)
    fig_e4(sanity, smp)
    fig_current_vs_revised(comp)
    fig_samples(sp, members)
    fig_benchmark(idt, bsum)
    fig_trends(tr, ser)

    n = F.write_specs(os.path.join(K.DIR_QA, "_figure_manifest_part1.csv"))
    K.log("[write] %d figure manifest entries" % n)
    K.log("r09 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
