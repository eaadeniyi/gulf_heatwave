"""
=============================================================================
e01  --  PART 1: what the Gulf-state temperature record actually looks like.
=============================================================================
Reads the RAW GHCN county-day files for TX, LA, MS, AL and FL over their whole
available record and produces the four requested views, each with the coverage
controls that make it honest:

  fig01  annual series, 1979-2025      one line per state, Tmax / Tmin / Tmean
  fig02  by state                      distribution of county-year values, and
                                       the within-state spread across counties
  fig03  decadal change                levels by decade and decade-to-decade
                                       change, on a BALANCED county panel
  fig04  monthly climatology           month x state, plus which MONTHS warmed

THE TWO CONTROLS, AND WHY THEY DECIDE THE ANSWER

 1. COVERAGE GATE. A county-year enters the annual summaries only if it has >=
    %d valid daily values, and a county-month only if it has >= %d. Tmax is
    missing on 5-23%% of county-days depending on the state, and a county that
    reported only in summer would otherwise read as an unusually hot county.

 2. BALANCED COUNTY PANEL for anything comparing periods. The reporting network
    SHRINKS: in the 2020s Texas falls from 236 to 218 reporting counties,
    Mississippi 69 to 53, Louisiana 52 to 44. Comparing decades on whichever
    counties happened to report would mix a temperature change with a change of
    counties. Decadal figures therefore use only counties that clear the gate in
    every decade; the unbalanced version is computed alongside and reported, so
    the size of that confounding is visible instead of assumed away.

Also: 2026 is EXCLUDED everywhere (the pull ends 2026-07-05, so it is a partial
year - warm-biased in a monthly mix, cold-biased in an annual mean), and 1979
appears in the annual series but not in the decadal comparison, since it stands
alone before the first full decade.

State-level values are MEDIANS across qualifying counties, matching this
project's reporting convention; the interquartile band across counties is drawn
with them, because a single state number hides a 254-county spread.

Outputs: tables/e01_*.csv and figures/e01_*.png
=============================================================================
"""
import os
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etx_config as K
import config as C

__doc__ = __doc__ % (K.MIN_DAYS_PER_COUNTY_YEAR, K.MIN_DAYS_PER_COUNTY_MONTH)
Y0, Y1 = K.EDA_YEARS
YEARS_LABEL = "%d-%d" % (Y0, Y1)


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
# 1. build the county-year and county-month layers from the raw record
# =============================================================================
def load_state(state):
    """Raw GHCN county-days for one state, restricted to complete years."""
    p = C.ghcn_path(state)
    d = pd.read_csv(p, usecols=["county_fips", "county_name", "date", "tmax_f", "tmin_f",
                                "tmax_f_nstations", "tmin_f_nstations"],
                    dtype={"county_fips": str})
    d["date"] = pd.to_datetime(d["date"])
    d["year"] = d["date"].dt.year
    d["month"] = d["date"].dt.month
    d = d[(d["year"] >= Y0) & (d["year"] <= Y1)]
    d["tmean_f"] = (d["tmax_f"] + d["tmin_f"]) / 2.0
    d["state"] = state
    return d


def county_year_layer(d):
    """One row per county-year, with the coverage gate applied per variable."""
    out = []
    for col, _, short in K.TEMP_VARS:
        g = d.loc[d[col].notna()].groupby(["state", "county_fips", "county_name", "year"])
        a = g.agg(**{"n_days": (col, "size"), "mean_f": (col, "mean"),
                     "max_f": (col, "max"), "min_f": (col, "min"),
                     "p95_f": (col, lambda s: s.quantile(0.95))}).reset_index()
        a["variable"] = short
        a["passes_coverage_gate"] = a["n_days"] >= K.MIN_DAYS_PER_COUNTY_YEAR
        out.append(a)
    return pd.concat(out, ignore_index=True)


def county_month_layer(d):
    out = []
    for col, _, short in K.TEMP_VARS:
        g = d.loc[d[col].notna()].groupby(["state", "county_fips", "year", "month"])
        a = g.agg(**{"n_days": (col, "size"), "mean_f": (col, "mean")}).reset_index()
        a["variable"] = short
        a["passes_coverage_gate"] = a["n_days"] >= K.MIN_DAYS_PER_COUNTY_MONTH
        out.append(a)
    return pd.concat(out, ignore_index=True)


def decade_of(year):
    for lo, hi in K.DECADES:
        if lo <= year <= hi:
            return K.DECADE_LABEL[(lo, hi)]
    return None


def balanced_counties(cy):
    """Counties that clear the coverage gate in EVERY decade, per state+variable.

    The whole decadal comparison rests on this: without it, the 2020s are
    computed on a different (smaller) set of counties than the 1980s.
    """
    g = cy[cy["passes_coverage_gate"] & cy["decade"].notna()]
    have = (g.groupby(["state", "variable", "county_fips"])["decade"].nunique()
            .rename("n_decades").reset_index())
    n_dec = len(K.DECADES)
    keep = have[have["n_decades"] == n_dec][["state", "variable", "county_fips"]]
    keep["in_balanced_panel"] = True
    return keep


# =============================================================================
# 2. state-level summaries
# =============================================================================
def state_year_summary(cy):
    g = cy[cy["passes_coverage_gate"]].groupby(["state", "variable", "year"])
    s = g.agg(counties=("county_fips", "nunique"),
              median_f=("mean_f", "median"),
              q25_f=("mean_f", lambda x: x.quantile(0.25)),
              q75_f=("mean_f", lambda x: x.quantile(0.75)),
              min_county_f=("mean_f", "min"), max_county_f=("mean_f", "max"),
              median_annual_max_f=("max_f", "median")).reset_index()
    for c in s.columns:
        if c.endswith("_f"):
            s[c] = s[c].round(3)
    return s


def state_decade_summary(cy, keep):
    """Decadal levels and changes, balanced and unbalanced side by side."""
    g = cy[cy["passes_coverage_gate"] & cy["decade"].notna()].merge(
        keep, on=["state", "variable", "county_fips"], how="left")
    g["in_balanced_panel"] = g["in_balanced_panel"].fillna(False)
    rows = []
    for panel, sub in (("all_reporting_counties", g),
                       ("balanced_panel", g[g["in_balanced_panel"]])):
        a = (sub.groupby(["state", "variable", "decade"])
             .agg(counties=("county_fips", "nunique"),
                  county_years=("mean_f", "size"),
                  median_f=("mean_f", "median"),
                  mean_f=("mean_f", "mean"),
                  q25_f=("mean_f", lambda x: x.quantile(0.25)),
                  q75_f=("mean_f", lambda x: x.quantile(0.75))).reset_index())
        a["panel"] = panel
        rows.append(a)
    out = pd.concat(rows, ignore_index=True)
    order = [K.DECADE_LABEL[d] for d in K.DECADES]
    out["decade_order"] = out["decade"].map({d: i for i, d in enumerate(order)})
    out = out.sort_values(["panel", "state", "variable", "decade_order"])
    # change from the first full decade, and from the previous decade
    out["change_vs_1980s_f"] = out.groupby(["panel", "state", "variable"])["median_f"] \
        .transform(lambda s: s - s.iloc[0]).round(3)
    out["change_vs_prev_decade_f"] = out.groupby(["panel", "state", "variable"])["median_f"] \
        .diff().round(3)
    out["is_partial_decade"] = out["decade"].isin(
        [K.DECADE_LABEL[d] for d in K.PARTIAL_DECADES])
    for c in ("median_f", "mean_f", "q25_f", "q75_f"):
        out[c] = out[c].round(3)
    return out.drop(columns=["decade_order"])


def state_month_summary(cm, keep):
    g = cm[cm["passes_coverage_gate"]].copy()
    g["decade"] = g["year"].map(decade_of)
    a = (g.groupby(["state", "variable", "month"])
         .agg(counties=("county_fips", "nunique"), county_months=("mean_f", "size"),
              median_f=("mean_f", "median"),
              q25_f=("mean_f", lambda x: x.quantile(0.25)),
              q75_f=("mean_f", lambda x: x.quantile(0.75))).reset_index())
    # decadal change BY MONTH, on the balanced panel: which months warmed?
    b = g.merge(keep, on=["state", "variable", "county_fips"], how="inner")
    d = (b[b["decade"].notna()].groupby(["state", "variable", "month", "decade"])["mean_f"]
         .median().reset_index())
    piv = d.pivot_table(index=["state", "variable", "month"], columns="decade",
                        values="mean_f")
    first, last = K.DECADE_LABEL[K.DECADES[0]], K.DECADE_LABEL[K.DECADES[-1]]
    if first in piv.columns and last in piv.columns:
        piv["change_%s_to_%s_f" % (first, last)] = (piv[last] - piv[first]).round(3)
    piv = piv.reset_index()
    for c in piv.columns:
        if piv[c].dtype.kind == "f":
            piv[c] = piv[c].round(3)
    for c in a.columns:
        if c.endswith("_f"):
            a[c] = a[c].round(3)
    return a, piv


# =============================================================================
# 3. figures
# =============================================================================
def fig01_annual(sy, coverage):
    vars_ = [v[2] for v in K.TEMP_VARS]
    fig, axs = plt.subplots(len(vars_) + 1, 1, figsize=(13.5, 12.0), sharex=True,
                            gridspec_kw={"height_ratios": [1, 1, 1, 0.55]})
    for ax, short in zip(axs, vars_):
        for st in K.STATES:
            s = sy[(sy["state"] == st) & (sy["variable"] == short)].sort_values("year")
            sty = K.STATE_STYLE[st]
            ax.fill_between(s["year"], s["q25_f"], s["q75_f"], color=sty["color"],
                            alpha=0.13, lw=0, zorder=2)
            ax.plot(s["year"], s["median_f"], color=sty["color"], lw=1.6, zorder=3,
                    marker=sty["marker"], ms=3.4, label=sty["label"])
        ax.set_ylabel("%s (degF)" % short)
        ax.set_title("%s - median across qualifying counties, band = interquartile range "
                     "across counties" % short, fontsize=9.5, fontweight="bold", loc="left")
        tidy(ax, grid_axis="both")
    # coverage panel: the reason the gate and the balanced panel exist
    ax = axs[-1]
    for st in K.STATES:
        c = coverage[coverage["state"] == st].sort_values("year")
        sty = K.STATE_STYLE[st]
        ax.plot(c["year"], c["counties_passing_gate"], color=sty["color"], lw=1.4,
                marker=sty["marker"], ms=3.0)
    ax.set_ylabel("counties passing\nthe coverage gate")
    ax.set_xlabel("year")
    ax.set_title("data coverage - counties with >= %d valid daily Tmax values that year "
                 "(this is why period comparisons use a balanced panel)"
                 % K.MIN_DAYS_PER_COUNTY_YEAR, fontsize=9, fontweight="bold", loc="left")
    tidy(ax, grid_axis="both")
    axs[0].legend(fontsize=8, ncol=5, loc="upper left", framealpha=0.95)
    fig.suptitle("Figure E1  Gulf-state temperature, %s - annual series by state"
                 % YEARS_LABEL, fontsize=13, fontweight="bold", y=0.995, x=0.01, ha="left")
    footnote(fig, "unit of analysis: county-year (a county's mean daily value for that year), "
                  "summarised as the MEDIAN across counties that pass the coverage gate; no "
                  "cross-county mean is used. Source: raw GHCN county-day files - OBSERVED "
                  "values only, no IDW gap-filling, so a county contributes only where it "
                  "actually reported. 2026 is excluded as a partial year (record ends "
                  "2026-07-05). Rising coverage in the bottom panel around 1980 reflects the "
                  "station network, not the climate.", y=-0.01)
    savefig(fig, "e01_fig01_annual_series_by_state.png")


def fig02_by_state(cy, sy):
    fig, axs = plt.subplots(1, 3, figsize=(15.0, 5.6))
    for ax, (col, _, short) in zip(axs, K.TEMP_VARS):
        data, labels, colors = [], [], []
        for st in K.STATES:
            v = cy[(cy["state"] == st) & (cy["variable"] == short)
                   & cy["passes_coverage_gate"]]["mean_f"].to_numpy()
            data.append(v)
            labels.append(st)
            colors.append(K.STATE_STYLE[st]["color"])
        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, showfliers=False,
                        widths=0.62, medianprops=dict(color="#111111", lw=1.8))
        for b, c in zip(bp["boxes"], colors):
            b.set_facecolor(c)
            b.set_alpha(0.55)
            b.set_edgecolor(c)
        for i, (v, st) in enumerate(zip(data, K.STATES), start=1):
            x = i + np.random.default_rng(7).uniform(-0.16, 0.16, size=v.size)
            ax.plot(x, v, lw=0, marker=K.STATE_STYLE[st]["marker"], ms=1.8,
                    color=K.STATE_STYLE[st]["color"], alpha=0.25, zorder=3)
            ax.annotate("%.1f" % np.median(v), xy=(i, np.median(v)), xytext=(0, 8),
                        textcoords="offset points", ha="center", fontsize=7.5,
                        fontweight="bold", color="#111111",
                        bbox=dict(fc="white", ec="none", alpha=0.8, pad=0.5))
        ax.set_title("%s" % short, fontsize=10, fontweight="bold")
        ax.set_ylabel("county-year mean %s (degF)" % short)
        ax.set_xlabel("state")
        tidy(ax)
    fig.suptitle("Figure E2  Gulf-state temperature, %s - by state\n"
                 "every point is one county-year; boxes give the interquartile range across "
                 "all county-years in the state" % YEARS_LABEL,
                 fontsize=12.5, fontweight="bold", y=1.02, x=0.01, ha="left")
    footnote(fig, "unit of analysis: county-year. Includes only county-years passing the "
                  "coverage gate (>= %d valid days). The spread WITHIN a state is comparable "
                  "to the spread BETWEEN states - Texas alone spans a wider range than the "
                  "gap between state medians - so a state-level mean is a weak summary of "
                  "exposure and county-level values are the substantive layer."
             % K.MIN_DAYS_PER_COUNTY_YEAR, y=-0.03)
    savefig(fig, "e01_fig02_distribution_by_state.png")


def fig03_decadal(sd):
    order = [K.DECADE_LABEL[d] for d in K.DECADES]
    bal = sd[sd["panel"] == "balanced_panel"]
    unb = sd[sd["panel"] == "all_reporting_counties"]
    fig, axs = plt.subplots(2, 3, figsize=(15.5, 9.0))
    for j, (col, _, short) in enumerate(K.TEMP_VARS):
        # --- levels by decade (balanced panel) ---------------------------------
        ax = axs[0, j]
        for st in K.STATES:
            b = bal[(bal["state"] == st) & (bal["variable"] == short)]
            b = b.set_index("decade").reindex(order).reset_index()
            sty = K.STATE_STYLE[st]
            ax.plot(range(len(order)), b["median_f"], color=sty["color"], lw=1.8,
                    marker=sty["marker"], ms=6, label=sty["label"], zorder=3)
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels(order, fontsize=8, rotation=20)
        ax.set_ylabel("median county %s (degF)" % short)
        ax.set_title("%s - level by decade (balanced panel)" % short, fontsize=9.5,
                     fontweight="bold", loc="left")
        tidy(ax, grid_axis="both")
        # --- change vs the 1980s, balanced vs unbalanced ----------------------
        ax = axs[1, j]
        x = np.arange(len(K.STATES))
        for k, (panel, sub, hatch, alpha) in enumerate(
                (("balanced panel", bal, None, 0.85),
                 ("all reporting counties", unb, "//", 0.45))):
            vals = []
            for st in K.STATES:
                s = sub[(sub["state"] == st) & (sub["variable"] == short)
                        & (sub["decade"] == order[-1])]
                vals.append(float(s["change_vs_1980s_f"].iloc[0]) if len(s) else np.nan)
            ax.bar(x + (k - 0.5) * 0.38, vals, width=0.36,
                   color=[K.STATE_STYLE[s]["color"] for s in K.STATES],
                   alpha=alpha, hatch=hatch, edgecolor="white", lw=0.7, zorder=3,
                   label=panel)
        ax.axhline(0, color="#333333", lw=1.0, zorder=2)
        ax.set_xticks(x)
        ax.set_xticklabels(K.STATES, fontsize=8.5)
        ax.set_ylabel("change in median county %s\n1980s to %s (degF)" % (short, order[-1]))
        ax.set_title("%s - warming since the 1980s" % short, fontsize=9.5,
                     fontweight="bold", loc="left")
        if j == 0:
            ax.legend(fontsize=7, loc="upper left")
        tidy(ax)
    axs[0, 0].legend(fontsize=7.5, ncol=2, loc="upper left")
    fig.suptitle("Figure E3  Gulf-state temperature - decadal change, %s" % YEARS_LABEL,
                 fontsize=13, fontweight="bold", y=0.995, x=0.01, ha="left")
    footnote(fig, "unit of analysis: county-year, aggregated to a decade as the MEDIAN across "
                  "county-years. Top row uses the BALANCED panel (only counties clearing the "
                  "coverage gate in every decade), which is what makes decades comparable; the "
                  "bottom row shows both panels so the effect of the shrinking reporting "
                  "network is visible. %s is only six years and is marked with an asterisk. "
                  "1979 is excluded from this figure: it stands alone before the first full "
                  "decade." % order[-1], y=-0.01)
    savefig(fig, "e01_fig03_decadal_change.png")


def fig04_monthly(sm, mchange):
    order = [K.DECADE_LABEL[d] for d in K.DECADES]
    chg_col = "change_%s_to_%s_f" % (order[0], order[-1])
    fig, axs = plt.subplots(2, 2, figsize=(15.0, 9.4),
                            gridspec_kw={"height_ratios": [1.15, 1]})
    # --- monthly climatology, Tmax and Tmin -------------------------------
    for ax, short in zip(axs[0], ("Tmax", "Tmin")):
        for st in K.STATES:
            s = sm[(sm["state"] == st) & (sm["variable"] == short)].sort_values("month")
            sty = K.STATE_STYLE[st]
            ax.fill_between(s["month"], s["q25_f"], s["q75_f"], color=sty["color"],
                            alpha=0.12, lw=0, zorder=2)
            ax.plot(s["month"], s["median_f"], color=sty["color"], lw=1.8,
                    marker=sty["marker"], ms=5, label=sty["label"], zorder=3)
        ax.axvspan(5.5, 9.5, color=K.COLOR_WARN, alpha=0.07, zorder=0)
        ax.text(7.5, ax.get_ylim()[1], "Jun-Sep", ha="center", va="top", fontsize=8,
                color=K.COLOR_WARN)
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
        ax.set_ylabel("%s (degF)" % short)
        ax.set_title("%s by calendar month - median across counties, band = IQR across "
                     "counties" % short, fontsize=9.5, fontweight="bold", loc="left")
        tidy(ax, grid_axis="both")
    axs[0, 0].legend(fontsize=8, ncol=2, loc="lower center")
    # --- which months warmed, per state ----------------------------------
    for ax, short in zip(axs[1], ("Tmax", "Tmin")):
        m = mchange[mchange["variable"] == short]
        if chg_col not in m.columns:
            ax.axis("off")
            continue
        x = np.arange(12)
        w = 0.8 / len(K.STATES)
        for i, st in enumerate(K.STATES):
            s = m[m["state"] == st].sort_values("month")
            ax.bar(x + i * w - 0.4 + w / 2, s[chg_col].to_numpy(), width=w * 0.92,
                   color=K.STATE_STYLE[st]["color"], edgecolor="white", lw=0.4,
                   label=K.STATE_STYLE[st]["label"], zorder=3)
        ax.axhline(0, color="#333333", lw=1.0, zorder=2)
        ax.axvspan(4.5, 8.5, color=K.COLOR_WARN, alpha=0.07, zorder=0)
        ax.set_xticks(x)
        ax.set_xticklabels(K.MONTH_ABBR, fontsize=8)
        ax.set_ylabel("change in median %s\n%s to %s (degF)" % (short, order[0], order[-1]))
        ax.set_title("%s - which MONTHS warmed (balanced panel)" % short, fontsize=9.5,
                     fontweight="bold", loc="left")
        tidy(ax)
    axs[1, 0].legend(fontsize=7, ncol=3, loc="upper left")
    fig.suptitle("Figure E4  Gulf-state temperature by month, %s" % YEARS_LABEL,
                 fontsize=13, fontweight="bold", y=0.995, x=0.01, ha="left")
    footnote(fig, "unit of analysis: county-month (a county's mean daily value for that "
                  "calendar month), median across counties. Top row pools %s; bottom row is "
                  "the %s-minus-%s difference on the balanced county panel, so it isolates "
                  "the seasonal shape of the change from the seasonal cycle itself. A month "
                  "that warmed more than the summer months matters directly for a year-round "
                  "relative heatwave definition, because the threshold it must clear is "
                  "estimated from that month's own history."
             % (YEARS_LABEL, order[-1], order[0]), y=-0.01)
    savefig(fig, "e01_fig04_monthly.png")


# =============================================================================
# driver
# =============================================================================
def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 74)
    K.log("e01  GULF-STATE TEMPERATURE DESCRIPTION  --  %s, %d states"
          % (YEARS_LABEL, len(K.STATES)))
    K.log("=" * 74)

    cy_all, cm_all, cov_all, extent = [], [], [], []
    for st in K.STATES:
        d = load_state(st)
        cy = county_year_layer(d)
        cm = county_month_layer(d)
        cy_all.append(cy)
        cm_all.append(cm)
        tm = cy[cy["variable"] == "Tmax"]
        cov_all.append(tm[tm["passes_coverage_gate"]].groupby(["state", "year"])
                       .agg(counties_passing_gate=("county_fips", "nunique")).reset_index())
        extent.append({"state": st, "county_days_1979_2025": len(d),
                       "counties_in_file": d["county_fips"].nunique(),
                       "first_date": str(d["date"].min().date()),
                       "last_date": str(d["date"].max().date()),
                       "pct_county_days_with_tmax": round(100 * d["tmax_f"].notna().mean(), 1),
                       "median_stations_tmax": float(d["tmax_f_nstations"].median()),
                       "county_years_passing_gate":
                           int(tm["passes_coverage_gate"].sum()),
                       "county_years_total": int(len(tm))})
        K.log("[load] %s: %s county-days, %d counties, %.1f%% with Tmax, %d/%d county-years "
              "pass the gate"
              % (st, "{:,}".format(len(d)), d["county_fips"].nunique(),
                 100 * d["tmax_f"].notna().mean(), int(tm["passes_coverage_gate"].sum()),
                 len(tm)))
        del d

    cy = pd.concat(cy_all, ignore_index=True)
    cm = pd.concat(cm_all, ignore_index=True)
    cov = pd.concat(cov_all, ignore_index=True)
    cy["decade"] = cy["year"].map(decade_of)

    keep = balanced_counties(cy)
    K.log("-" * 74)
    bal_n = keep.groupby(["state", "variable"]).size().unstack(fill_value=0)
    K.log("balanced panel (counties clearing the gate in all %d decades):" % len(K.DECADES))
    K.log(bal_n.to_string())

    sy = state_year_summary(cy)
    sd = state_decade_summary(cy, keep)
    sm, mchange = state_month_summary(cm, keep)

    ex = pd.DataFrame(extent)
    ex.to_csv(os.path.join(K.DIR_TABLES, "e01_record_extent_and_coverage.csv"), index=False)
    cy.to_csv(os.path.join(K.DIR_TABLES, "e01_county_year_temperature.csv"), index=False)
    sy.to_csv(os.path.join(K.DIR_TABLES, "e01_state_year_temperature.csv"), index=False)
    sd.to_csv(os.path.join(K.DIR_TABLES, "e01_state_decade_temperature.csv"), index=False)
    sm.to_csv(os.path.join(K.DIR_TABLES, "e01_state_month_temperature.csv"), index=False)
    mchange.to_csv(os.path.join(K.DIR_TABLES, "e01_state_month_decadal_change.csv"),
                   index=False)
    keep.to_csv(os.path.join(K.DIR_TABLES, "e01_balanced_panel_counties.csv"), index=False)
    K.log("[write] 7 tables -> tables/e01_*.csv")

    K.log("-" * 74)
    K.log("figures")
    fig01_annual(sy, cov)
    fig02_by_state(cy, sy)
    fig03_decadal(sd)
    fig04_monthly(sm, mchange)

    # headline numbers, printed so the run itself reports the result
    order = [K.DECADE_LABEL[d] for d in K.DECADES]
    K.log("-" * 74)
    K.log("DECADAL CHANGE in median county Tmax, 1980s -> %s (degF):" % order[-1])
    for panel in ("balanced_panel", "all_reporting_counties"):
        row = []
        for st in K.STATES:
            s = sd[(sd["panel"] == panel) & (sd["state"] == st) & (sd["variable"] == "Tmax")
                   & (sd["decade"] == order[-1])]
            row.append("%s %+.2f" % (st, float(s["change_vs_1980s_f"].iloc[0])
                                     if len(s) else np.nan))
        K.log("   %-24s %s" % (panel, "   ".join(row)))
    K.log("e01 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
