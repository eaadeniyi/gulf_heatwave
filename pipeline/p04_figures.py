"""
=============================================================================
STEP p04  --  figures, per RUN (definition x threshold window).
=============================================================================
At statewide scale a state has hundreds of counties, so per-county line charts
are unreadable -- the per-run figures are CHOROPLETH MAPS plus distributions.
All figures are state- and metric-agnostic: counties come from the shapefile by
FIPS, titles are composed from the run's own specification.

Produced per RUN, in <DEF_ID>/figures/ with the window key in the filename:
  map01   heatwave DAYS per county (pooled analysis period)
  map02   heatwave EVENTS per county (pooled)
  dist01  distribution of per-county heatwave-day totals
  seas01  seasonality: heatwave days by calendar month (the year-round question)
  map05   heatwave days per county BY YEAR (small multiples, shared color scale)

Produced per DEFINITION (once, comparing its 4 windows):
  cmpwin  per-county heatwave days, each window against the primary window

Produced ONCE per state and copied into every run folder (identical by
construction -- they describe the input data, not the definition):
  map03   data-quality: % of county-days IDW-imputed
  map04   NWS advisory-threshold PROXY days per county   (if the NWS step ran)
=============================================================================
"""
import os, sys, glob, shutil, json, time
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

PRIMARY_WINDOW = "w15"          # the centered 15-day window is the reporting primary
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_GEO = {}


def log(*a):
    print(*a, flush=True)


def counties_gdf(state):
    """State county polygons in equal-area projection (cached across runs)."""
    if state not in _GEO:
        g = gpd.read_file(C.COUNTY_SHAPEFILE)
        g = g[g["STATEFP"] == C.STATE_FIPS[state]].to_crs(C.EQUAL_AREA_CRS)
        _GEO[state] = g[["GEOID", "geometry"]].rename(columns={"GEOID": "county_fips"})
    return _GEO[state]


def choropleth(state, series, title, path, cmap="YlOrRd", label="value", note="", vmax=None):
    g = counties_gdf(state).merge(series.rename("val").reset_index(), on="county_fips", how="left")
    fig, ax = plt.subplots(figsize=(9, 8))
    g.plot(column="val", cmap=cmap, linewidth=0.2, edgecolor="#888", ax=ax, legend=True, vmax=vmax,
           missing_kwds={"color": "#dddddd", "label": "no data"},
           legend_kwds={"label": label, "shrink": 0.6})
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.axis("off")
    if note:
        fig.text(0.005, 0.02, note, fontsize=7.5, color="#555", wrap=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=110)
    plt.close(fig)


# =============================================================================
# state-level figures (definition-INDEPENDENT: rendered once, copied per run)
# =============================================================================
def build_state_figures(state, force=False):
    """The two figures that describe the INPUT data rather than any definition."""
    sdir = C.state_output_dir(state)
    fdir = C.state_figure_dir(state)
    made = {}

    p3 = os.path.join(fdir, "map03_pct_days_imputed_per_county.png")
    if force or not os.path.exists(p3):
        cov = pd.read_csv(os.path.join(sdir, "coverage_and_imputation_report.csv"),
                          dtype={"county_fips": str}).set_index("county_fips")
        choropleth(state, cov["pct_analysis_days_imputed"],
                   "Data quality: percent of county-days IDW-imputed", p3,
                   cmap="Purples", label="% analysis days imputed",
                   note="Darker = more reliance on inverse-distance interpolation from neighbours. "
                        "Identical for every definition (describes the input data).")
        log("  [state fig] map03")
    made["map03_pct_days_imputed_per_county.png"] = p3

    p4 = os.path.join(fdir, "map04_nws_advisory_threshold_days.png")
    nws = os.path.join(sdir, "nws_proxy_county_year.csv")
    if os.path.exists(nws):
        if force or not os.path.exists(p4):
            ny = pd.read_csv(nws, dtype={"county_fips": str})
            choropleth(state, ny.groupby("county_fips")["advisory_threshold_days"].sum(),
                       "NWS advisory-threshold PROXY days per county, %d-%d" % C.ANALYSIS_YEARS, p4,
                       cmap="OrRd", label="advisory-threshold days (period total)",
                       note="PROXY (daily max-HI vs local office threshold); NOT official advisories; "
                            "approximate crosswalk. Identical for every definition.")
            log("  [state fig] map04")
        made["map04_nws_advisory_threshold_days.png"] = p4
    return made


# =============================================================================
# per-run figures
# =============================================================================
def figures_for_run(state, run, state_figs=None, verbose=True):
    """The full figure set for one run (one definition at one threshold window)."""
    ddir = C.grid_definition_dir(state, run["definition_id"])
    tdir, fdir = os.path.join(ddir, "tables"), os.path.join(ddir, "figures")
    wkey = run["window_key"]
    sname = C.STATE_NAME.get(state, state)
    cy_path = os.path.join(tdir, "county_year_summary_%s.csv" % wkey)
    if not os.path.exists(cy_path):
        if verbose:
            log("  [skip] %s -- no tables yet" % run["run_id"])
        return 0

    subtitle = ("%s | Def %02d (item %s) | %s > %dth pctl, >=%d consecutive days | %s | "
                "walk-forward %d..Y-1 | IDW gap-filled"
                % (sname, run["def_number"], run["user_item"], run["metric_short"],
                   run["percentile"], run["min_duration"], run["window_label"], C.BASELINE_START))
    head = "%s %dth pctl, >=%dd" % (run["metric_short"], run["percentile"], run["min_duration"])

    cy = pd.read_csv(cy_path, dtype={"county_fips": str})
    all_counties = counties_gdf(state)["county_fips"].tolist()
    pool = (cy.groupby("county_fips").agg(days=("heatwave_days", "sum"),
                                          events=("heatwave_events_started", "sum"))
            .reindex(all_counties, fill_value=0))
    n = 0

    choropleth(state, pool["days"], "Heatwave DAYS per county, %d-%d\n%s" % (C.ANALYSIS_YEARS + (head,)),
               os.path.join(fdir, "map01_heatwave_days_per_county_%s.png" % wkey),
               label="heatwave days (period total)", note=subtitle + " | grey = no data")
    n += 1
    choropleth(state, pool["events"], "Heatwave EVENTS per county, %d-%d\n%s" % (C.ANALYSIS_YEARS + (head,)),
               os.path.join(fdir, "map02_heatwave_events_per_county_%s.png" % wkey),
               label="heatwave events (period total)", note=subtitle)
    n += 1

    # ---- distribution of per-county heatwave-day totals ---------------------
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(pool["days"], bins=30, color="#C44E52", edgecolor="white")
    med = pool["days"].median()
    ax.axvline(med, color="k", ls="--", lw=1.2, label="median = %.0f" % med)
    ax.set_xlabel("Heatwave days per county (%d-%d total)" % C.ANALYSIS_YEARS)
    ax.set_ylabel("Number of counties")
    ax.set_title("Per-county heatwave-day totals (%d counties) -- %s" % (len(pool), head),
                 fontsize=11, fontweight="bold")
    ax.legend()
    fig.text(0.005, 0.005, subtitle, fontsize=7, color="#555")
    fig.tight_layout()
    fig.savefig(os.path.join(fdir, "dist01_heatwave_days_hist_%s.png" % wkey),
                bbox_inches="tight", facecolor="white", dpi=110)
    plt.close(fig)
    n += 1

    # ---- seasonality: which calendar months the heatwave days fall in -------
    cm_path = os.path.join(tdir, "county_month_summary_%s.csv" % wkey)
    if os.path.exists(cm_path):
        cm = pd.read_csv(cm_path, dtype={"county_fips": str})
        by_month = cm.groupby("month")["heatwave_days"].sum().reindex(range(1, 13), fill_value=0)
        pct = 100 * by_month / by_month.sum() if by_month.sum() else by_month
        fig, ax = plt.subplots(figsize=(9, 5))
        cols = ["#4C72B0"] * 12
        for m in (6, 7, 8, 9):
            cols[m - 1] = "#C44E52"
        ax.bar(range(1, 13), pct.to_numpy(), color=cols, edgecolor="white")
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(MONTH_ABBR)
        ax.set_ylabel("% of all heatwave days")
        jj = pct.loc[[6, 7, 8, 9]].sum()
        ax.set_title("Seasonality of heatwave days -- %s\nJun-Sep = %.0f%% (red), "
                     "outside Jun-Sep = %.0f%%" % (head, jj, 100 - jj),
                     fontsize=11, fontweight="bold")
        fig.text(0.005, 0.005, subtitle + " | a year-round RELATIVE definition flags "
                 "'unusual for the date', which can occur in any month", fontsize=7, color="#555")
        fig.tight_layout()
        fig.savefig(os.path.join(fdir, "seas01_heatwave_days_by_month_%s.png" % wkey),
                    bbox_inches="tight", facecolor="white", dpi=110)
        plt.close(fig)
        n += 1

    # ---- per-year small multiples (shared colour scale) ---------------------
    yrs = list(range(C.ANALYSIS_YEARS[0], C.ANALYSIS_YEARS[1] + 1))
    peryr = cy.set_index(["county_fips", "year"])["heatwave_days"]
    vmax = int(cy["heatwave_days"].max()) if len(cy) else 1
    ncol = 4
    nrow = int(np.ceil(len(yrs) / ncol))
    geo = counties_gdf(state)
    fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 3.6 * nrow))
    axes = np.array(axes).ravel()
    for k, yr in enumerate(yrs):
        ax = axes[k]
        vals = (peryr.xs(yr, level="year") if yr in set(cy["year"]) else pd.Series(dtype=float))
        g = geo.merge(vals.rename("val").reset_index(), on="county_fips", how="left")
        g["val"] = g["val"].fillna(0)
        g.plot(column="val", cmap="YlOrRd", vmin=0, vmax=vmax, linewidth=0.1,
               edgecolor="#999", ax=ax)
        ax.set_title(str(yr), fontsize=11)
        ax.axis("off")
    for k in range(len(yrs), len(axes)):
        axes[k].axis("off")
    sm = plt.cm.ScalarMappable(cmap="YlOrRd", norm=plt.Normalize(vmin=0, vmax=vmax))
    fig.colorbar(sm, ax=axes[-1], shrink=0.7,
                 label="heatwave days/yr (shared scale 0-%d)" % vmax)
    fig.suptitle("Heatwave days per county BY YEAR (shared scale) -- %s\n%s" % (head, subtitle),
                 fontsize=11, fontweight="bold")
    fig.savefig(os.path.join(fdir, "map05_heatwave_days_by_year_%s.png" % wkey),
                bbox_inches="tight", facecolor="white", dpi=100)
    plt.close(fig)
    n += 1

    # ---- copy in the definition-independent state figures ------------------
    for fname, src in (state_figs or {}).items():
        dst = os.path.join(fdir, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copyfile(src, dst)
            n += 1
    if verbose:
        log("  [figs] %-24s %d file(s)" % (run["run_id"], n))
    return n


def window_comparison_figure(state, defn, verbose=True):
    """For one definition: per-county heatwave days under each window, against the
    primary window. Shows directly how much the window choice matters."""
    ddir = C.grid_definition_dir(state, defn["definition_id"])
    tdir, fdir = os.path.join(ddir, "tables"), os.path.join(ddir, "figures")
    series = {}
    for wkey in sorted(C.GRID_WINDOWS, key=lambda k: C.GRID_WINDOWS[k]["order"]):
        p = os.path.join(tdir, "county_year_summary_%s.csv" % wkey)
        if os.path.exists(p):
            cy = pd.read_csv(p, dtype={"county_fips": str})
            series[wkey] = cy.groupby("county_fips")["heatwave_days"].sum()
    if PRIMARY_WINDOW not in series or len(series) < 2:
        return 0
    base = series[PRIMARY_WINDOW]
    others = [w for w in series if w != PRIMARY_WINDOW]
    fig, axes = plt.subplots(1, len(others), figsize=(4.6 * len(others), 4.6), squeeze=False)
    for ax, w in zip(axes[0], others):
        s = series[w].reindex(base.index)
        ax.scatter(base, s, s=10, alpha=0.55, color="#4C72B0", edgecolor="none")
        lim = [0, max(base.max(), s.max()) * 1.05]
        ax.plot(lim, lim, "k--", lw=1)
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        r = np.corrcoef(base.fillna(0), s.fillna(0))[0, 1]
        ax.set_xlabel("%s (primary)" % PRIMARY_WINDOW)
        ax.set_ylabel(w)
        ax.set_title("%s vs %s\nr = %.4f" % (w, PRIMARY_WINDOW, r), fontsize=10)
    head = "%s %dth pctl, >=%dd" % (defn["metric_short"], defn["percentile"], defn["min_duration"])
    fig.suptitle("Threshold-window sensitivity -- %s (per-county heatwave days, %d-%d)"
                 % (head, C.ANALYSIS_YEARS[0], C.ANALYSIS_YEARS[1]),
                 fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(fdir, "cmpwin01_window_sensitivity.png"),
                bbox_inches="tight", facecolor="white", dpi=110)
    plt.close(fig)
    if verbose:
        log("  [figs] %-24s window-sensitivity panel" % defn["definition_id"])
    return 1


# =============================================================================
# drivers
# =============================================================================
def run_grid_figures(state, runs=None, force=False):
    t0 = time.time()
    log("=" * 72)
    log("p04  figures  --  state=%s" % state)
    log("=" * 72)
    state_figs = build_state_figures(state, force=force)
    if runs is None:
        runs = C.grid_runs()
    total = 0
    for i, run in enumerate(runs, 1):
        log("[%d/%d]" % (i, len(runs)))
        total += figures_for_run(state, run, state_figs=state_figs)
    for defn in C.grid_definitions_expanded():
        total += window_comparison_figure(state, defn)
    log("[done] %d figure file(s) for %s in %.1f min" % (total, state, (time.time() - t0) / 60))
    return total


def run_state_percentile(state, pctl):
    """LEGACY entry point (run_all.py) -- figures for the published Def 01 / 02
    output folders, which use the legacy directory layout."""
    sname = C.STATE_NAME.get(state, state)
    ddir = C.definition_output_dir(state, pctl)
    tdir, fdir = os.path.join(ddir, "tables"), os.path.join(ddir, "figures")
    sdir = C.state_output_dir(state)
    log("p04  figures (legacy)  --  state=%s percentile=%d" % (state, pctl))
    subtitle = ("%s | rel %dth-pctl daily-mean HI, >=%d days, walk-forward, IDW gap-filled"
                % (sname, pctl, C.MIN_DURATION))
    cy = pd.read_csv(os.path.join(tdir, "county_year_summary_%s.csv" % PRIMARY_WINDOW),
                     dtype={"county_fips": str})
    pool = cy.groupby("county_fips").agg(days=("heatwave_days", "sum"),
                                         events=("heatwave_events_started", "sum"))
    choropleth(state, pool["days"], "Heatwave DAYS per county, %d-%d" % C.ANALYSIS_YEARS,
               os.path.join(fdir, "map01_heatwave_days_per_county.png"),
               label="heatwave days (period total)", note=subtitle + " | grey = no data")
    choropleth(state, pool["events"], "Heatwave EVENTS per county, %d-%d" % C.ANALYSIS_YEARS,
               os.path.join(fdir, "map02_heatwave_events_per_county.png"),
               label="heatwave events (period total)", note=subtitle)
    cov = pd.read_csv(os.path.join(sdir, "coverage_and_imputation_report.csv"),
                      dtype={"county_fips": str}).set_index("county_fips")
    choropleth(state, cov["pct_analysis_days_imputed"],
               "Data quality: percent of county-days IDW-imputed",
               os.path.join(fdir, "map03_pct_days_imputed_per_county.png"),
               cmap="Purples", label="% analysis days imputed",
               note="Darker = more reliance on inverse-distance interpolation from neighbours")
    nws_path = os.path.join(sdir, "nws_proxy_county_year.csv")
    if os.path.exists(nws_path):
        ny = pd.read_csv(nws_path, dtype={"county_fips": str})
        choropleth(state, ny.groupby("county_fips")["advisory_threshold_days"].sum(),
                   "NWS advisory-threshold PROXY days per county, %d-%d" % C.ANALYSIS_YEARS,
                   os.path.join(fdir, "map04_nws_advisory_threshold_days.png"),
                   cmap="OrRd", label="advisory-threshold days (period total)",
                   note="PROXY (daily max-HI vs local office threshold); NOT official advisories")
    log("  [legacy figures written]")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", action="append", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--legacy", action="store_true", help="figures for the published Def 01/02 dirs")
    a = ap.parse_args()
    for st in (a.state or C.STATES):
        if a.legacy:
            for p in C.PERCENTILES:
                run_state_percentile(st, p)
        else:
            run_grid_figures(st, force=a.force)
