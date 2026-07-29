"""
=============================================================================
STEP p05  --  CROSS-DEFINITION COMPARISON LAYER.
=============================================================================
56 separate run reports are unreadable, and the point of running a grid is the
comparison, not the individual cells. This step reduces the grid to the tables
and figures that answer "what does the choice of definition actually change?".

Tables written to <ST>/grid/_comparison/tables/:
  master_run_summary.csv          one headline row per run (written by run_grid.py)
  master_county_run_summary.csv   one row per county x run -- the substantive
                                  county-level layer, long format
  agreement_jaccard_matrix.csv    pairwise day-level agreement between runs, on
                                  the SET of (county, date) heatwave days
  agreement_jaccard_pairs.csv     the same, long format, with the axis that differs
  marginal_effects.csv            how much each axis (metric / percentile /
                                  duration / window) moves the counts, holding
                                  the other three fixed
  county_rank_stability.csv       Spearman correlation of county rankings between
                                  runs -- bears on whether county-level results
                                  survive a change of definition
  seasonality_by_run.csv          % of heatwave days by calendar month, per run

Figures written to <ST>/grid/_comparison/figures/:
  cmp01_jaccard_heatmap           day-level agreement across all runs
  cmp02_marginal_effects          the four axes, side by side
  cmp03_days_by_definition        per-county heatwave days per definition (box)
  cmp04_seasonality_grid          seasonality profile of every definition
  cmp05_window_effect             window sensitivity across all definitions
  cmp06_rank_stability            county-rank agreement heatmap

DAY-LEVEL AGREEMENT (Jaccard) is the project's established comparison metric:
walk-forward vs fixed baseline scored 0.923, and anchor-station vs multi-station
composite temperature scored only 0.45-0.73. Those two numbers are the yardstick
the definition contrasts here should be read against -- if changing the metric
moves agreement less than changing the temperature SOURCE did, the source problem
still dominates.
=============================================================================
"""
import os, sys, glob, time, itertools, json
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

PRIMARY_WINDOW = "w15"
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
# the two established yardsticks from earlier sensitivity work in this project
YARDSTICKS = {"walk-forward vs fixed baseline": 0.923,
              "anchor vs composite temperature (low)": 0.45,
              "anchor vs composite temperature (high)": 0.73}


def log(*a):
    print(*a, flush=True)


def available_runs(state):
    """Runs that actually have output on disk."""
    out = []
    for r in C.grid_runs():
        p = os.path.join(C.grid_definition_dir(state, r["definition_id"], make=False),
                         "tables", "run_summary_%s.json" % r["window_key"])
        if os.path.exists(p):
            out.append(r)
    return out


def short_label(r):
    return "%s.P%d.%dD.%s" % (r["metric_code"], r["percentile"], r["min_duration"], r["window_key"])


# =============================================================================
# 1. county x run master table
# =============================================================================
def build_county_run_table(state, runs):
    """One row per county x run: the substantive county-level layer."""
    frames = []
    for r in runs:
        tdir = os.path.join(C.grid_definition_dir(state, r["definition_id"], make=False), "tables")
        cy = pd.read_csv(os.path.join(tdir, "county_year_summary_%s.csv" % r["window_key"]),
                         dtype={"county_fips": str})
        g = cy.groupby("county_fips").agg(
            county_name=("county_name", "first"),
            heatwave_days=("heatwave_days", "sum"),
            heatwave_events=("heatwave_events_started", "sum"),
            heatwave_days_imputed=("heatwave_days_imputed", "sum"),
            longest_event_duration_days=("longest_event_duration_days", "max"),
            years_with_any_event=("heatwave_events_started", lambda s: int((s > 0).sum())),
        ).reset_index()
        for k in ("run_id", "definition_id", "def_number", "user_item", "metric_code",
                  "percentile", "min_duration", "window_key"):
            g[k] = r[k]
        frames.append(g)
    out = pd.concat(frames, ignore_index=True)
    out["heatwave_days_per_year"] = (out["heatwave_days"] /
                                     (C.ANALYSIS_YEARS[1] - C.ANALYSIS_YEARS[0] + 1)).round(2)
    cols = ["run_id", "definition_id", "def_number", "user_item", "metric_code", "percentile",
            "min_duration", "window_key", "county_fips", "county_name", "heatwave_days",
            "heatwave_days_per_year", "heatwave_events", "longest_event_duration_days",
            "years_with_any_event", "heatwave_days_imputed"]
    return out[cols].sort_values(["run_id", "county_fips"]).reset_index(drop=True)


# =============================================================================
# 2. day-level agreement (Jaccard)
# =============================================================================
def load_day_sets(state, runs):
    """The SET of (county, date) heatwave days for each run.

    Encoded as sorted int64 rather than "fips|date" strings: 56 runs x ~150k
    heatwave county-days is ~8M keys, which as Python strings costs on the order of
    a gigabyte and makes every set operation slow. code = county_index * 100000 +
    date_ordinal is exact (no collisions for any realistic county/date count) and
    lets np.intersect1d work on sorted integer arrays.
    """
    sets = {}
    cty_index = {}
    for r in runs:
        tdir = os.path.join(C.grid_definition_dir(state, r["definition_id"], make=False), "tables")
        p = os.path.join(tdir, "daily_heatwave_days_%s.csv.gz" % r["window_key"])
        if not os.path.exists(p):
            continue
        d = pd.read_csv(p, usecols=["county_fips", "date"], dtype={"county_fips": str})
        for c in pd.unique(d["county_fips"]):
            cty_index.setdefault(c, len(cty_index))
        ci = d["county_fips"].map(cty_index).to_numpy(dtype=np.int64)
        do = pd.to_datetime(d["date"]).to_numpy(dtype="datetime64[D]").astype(np.int64)
        sets[r["run_id"]] = np.unique(ci * 100000 + do)
        log("   [days] %-24s %s heatwave county-days" % (r["run_id"],
                                                        "{:,}".format(len(sets[r["run_id"]]))))
    return sets


def jaccard_matrix(sets, runs):
    """Pairwise Jaccard index over the heatwave county-day sets."""
    ids = [r["run_id"] for r in runs if r["run_id"] in sets]
    n = len(ids)
    M = np.eye(n)
    for i, j in itertools.combinations(range(n), 2):
        a, b = sets[ids[i]], sets[ids[j]]
        inter = np.intersect1d(a, b, assume_unique=True).size
        union = a.size + b.size - inter
        M[i, j] = M[j, i] = inter / union if union else np.nan
    return pd.DataFrame(M, index=ids, columns=ids)


def jaccard_pairs(J, runs):
    """Long-format pair list, tagged with WHICH axis differs -- so the table can be
    read as 'changing only the percentile costs this much agreement'."""
    meta = {r["run_id"]: r for r in runs}
    rows = []
    for a, b in itertools.combinations(J.index, 2):
        ra, rb = meta[a], meta[b]
        diffs = [k for k, f in (("metric", "metric_code"), ("percentile", "percentile"),
                                ("duration", "min_duration"), ("window", "window_key"))
                 if ra[f] != rb[f]]
        rows.append({"run_a": a, "run_b": b, "jaccard": round(float(J.loc[a, b]), 4),
                     "n_axes_differing": len(diffs),
                     "axes_differing": "+".join(diffs) if diffs else "none",
                     "single_axis": diffs[0] if len(diffs) == 1 else "",
                     "metric_a": ra["metric_code"], "metric_b": rb["metric_code"],
                     "percentile_a": ra["percentile"], "percentile_b": rb["percentile"],
                     "duration_a": ra["min_duration"], "duration_b": rb["min_duration"],
                     "window_a": ra["window_key"], "window_b": rb["window_key"]})
    return pd.DataFrame(rows).sort_values(["n_axes_differing", "jaccard"]).reset_index(drop=True)


# =============================================================================
# 3. marginal effects of each axis
# =============================================================================
def marginal_effects(master, pairs):
    """For each axis, the effect of changing ONLY that axis.

    Uses matched pairs: two runs identical on the other three axes. Reports the
    ratio of pooled heatwave days and the day-level Jaccard, so the axes can be
    ranked by how much they actually change the classification.
    """
    m = master.set_index("run_id")
    rows = []
    single = pairs[pairs["n_axes_differing"] == 1]
    for axis, grp in single.groupby("single_axis"):
        for _, p in grp.iterrows():
            a, b = p["run_a"], p["run_b"]
            if a not in m.index or b not in m.index:
                continue
            da, db = m.loc[a, "heatwave_days_QA_pooled"], m.loc[b, "heatwave_days_QA_pooled"]
            lo, hi = sorted([(da, a), (db, b)])
            v_lo, v_hi = _axis_value(m.loc[lo[1]], axis), _axis_value(m.loc[hi[1]], axis)
            # 'from' is the lower-count run, so direction carries information -- but the
            # PAIR label must be canonical, or one contrast (e.g. Tmax vs mean HI) splits
            # into two rows depending on which side happened to count more days
            pair = " vs ".join(sorted([str(v_lo), str(v_hi)]))
            rows.append({
                "axis": axis, "contrast_pair": pair,
                "from_run": lo[1], "to_run": hi[1],
                "from_value": v_lo, "to_value": v_hi,
                "days_from": int(lo[0]), "days_to": int(hi[0]),
                "days_ratio_hi_over_lo": round(hi[0] / lo[0], 4) if lo[0] else np.nan,
                "pct_change": round(100 * (hi[0] - lo[0]) / lo[0], 1) if lo[0] else np.nan,
                "jaccard": p["jaccard"],
            })
    df = pd.DataFrame(rows)
    if not len(df):
        return df, pd.DataFrame()
    summary = df.groupby("axis").agg(
        n_matched_pairs=("jaccard", "size"),
        jaccard_median=("jaccard", "median"),
        jaccard_min=("jaccard", "min"),
        jaccard_max=("jaccard", "max"),
        days_ratio_median=("days_ratio_hi_over_lo", "median"),
        days_ratio_min=("days_ratio_hi_over_lo", "min"),
        days_ratio_max=("days_ratio_hi_over_lo", "max"),
    ).reset_index().sort_values("jaccard_median")
    for c in summary.columns:
        if summary[c].dtype.kind == "f":
            summary[c] = summary[c].round(4)
    return df, summary


def _axis_value(row, axis):
    return {"metric": row.get("metric"), "percentile": row.get("percentile"),
            "duration": row.get("min_duration"), "window": row.get("window_key")}[axis]


# =============================================================================
# 4. county-rank stability + seasonality
# =============================================================================
def rank_stability(county_run):
    """Spearman correlation of per-county heatwave-day rankings between runs."""
    piv = county_run.pivot_table(index="county_fips", columns="run_id", values="heatwave_days")
    return piv.corr(method="spearman")


def seasonality_by_run(state, runs):
    rows = []
    for r in runs:
        tdir = os.path.join(C.grid_definition_dir(state, r["definition_id"], make=False), "tables")
        p = os.path.join(tdir, "county_month_summary_%s.csv" % r["window_key"])
        if not os.path.exists(p):
            continue
        cm = pd.read_csv(p, dtype={"county_fips": str})
        by = cm.groupby("month")["heatwave_days"].sum().reindex(range(1, 13), fill_value=0)
        tot = by.sum()
        row = {"run_id": r["run_id"], "definition_id": r["definition_id"],
               "metric_code": r["metric_code"], "percentile": r["percentile"],
               "min_duration": r["min_duration"], "window_key": r["window_key"],
               "heatwave_days_total": int(tot)}
        for m in range(1, 13):
            row["pct_" + MONTH_ABBR[m - 1]] = round(100 * by[m] / tot, 2) if tot else np.nan
        row["pct_jun_sep"] = round(100 * by.loc[[6, 7, 8, 9]].sum() / tot, 2) if tot else np.nan
        row["pct_outside_jun_sep"] = round(100 - row["pct_jun_sep"], 2) if tot else np.nan
        row["peak_month"] = MONTH_ABBR[int(by.idxmax()) - 1] if tot else ""
        rows.append(row)
    return pd.DataFrame(rows)


# =============================================================================
# 5. figures
# =============================================================================
def fig_jaccard_heatmap(J, runs, path):
    meta = {r["run_id"]: r for r in runs}
    order = sorted(J.index, key=lambda x: (meta[x]["metric_code"], meta[x]["percentile"],
                                           meta[x]["min_duration"], meta[x]["window_order"]))
    M = J.loc[order, order]
    labels = [short_label(meta[x]) for x in order]
    fig, ax = plt.subplots(figsize=(0.28 * len(order) + 5, 0.28 * len(order) + 4))
    im = ax.imshow(M.to_numpy(), cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(labels, rotation=90, fontsize=6)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(labels, fontsize=6)
    fig.colorbar(im, ax=ax, shrink=0.7, label="Jaccard index (day-level agreement)")
    ax.set_title("Day-level agreement between heatwave definitions\n"
                 "(shared (county, date) heatwave days / union), %d-%d, %s"
                 % (C.ANALYSIS_YEARS[0], C.ANALYSIS_YEARS[1], "Texas"),
                 fontsize=11, fontweight="bold")
    fig.text(0.005, 0.005, "Yardsticks from this project's earlier sensitivity work: "
             "walk-forward vs fixed baseline = 0.923; anchor-station vs multi-station "
             "composite temperature = 0.45-0.73.", fontsize=7, color="#555")
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=130)
    plt.close(fig)


def fig_marginal_effects(mdf, summary, path):
    if not len(mdf):
        return
    axes_order = list(summary.sort_values("jaccard_median")["axis"])
    fig, axs = plt.subplots(1, 2, figsize=(13, 5))
    # (a) day-level agreement when only that axis changes
    data = [mdf.loc[mdf["axis"] == a, "jaccard"].to_numpy() for a in axes_order]
    bp = axs[0].boxplot(data, tick_labels=axes_order, patch_artist=True, showfliers=True)
    for b in bp["boxes"]:
        b.set_facecolor("#4C72B0")
        b.set_alpha(0.75)
    for name, v in YARDSTICKS.items():
        axs[0].axhline(v, ls="--", lw=1, color="#C44E52")
        axs[0].text(0.02, v + 0.012, name, fontsize=6.5, color="#C44E52",
                    transform=axs[0].get_yaxis_transform())
    axs[0].set_ylim(0, 1.02)
    axs[0].set_ylabel("Jaccard (day-level agreement)")
    axs[0].set_title("Change ONE axis: how much does the\nset of heatwave days change?",
                     fontsize=10, fontweight="bold")
    axs[0].set_xlabel("axis changed (lower = bigger effect on classification)")
    # (b) ratio of heatwave-day counts
    data2 = [mdf.loc[mdf["axis"] == a, "days_ratio_hi_over_lo"].to_numpy() for a in axes_order]
    bp2 = axs[1].boxplot(data2, tick_labels=axes_order, patch_artist=True, showfliers=True)
    for b in bp2["boxes"]:
        b.set_facecolor("#DD8452")
        b.set_alpha(0.85)
    axs[1].axhline(1.0, ls="--", lw=1, color="k")
    axs[1].set_ylabel("heatwave days: higher run / lower run")
    axs[1].set_title("Change ONE axis: how much does the\nheatwave-day COUNT change?",
                     fontsize=10, fontweight="bold")
    axs[1].set_xlabel("axis changed")
    fig.suptitle("Marginal effect of each definition choice (matched pairs: the other "
                 "three axes held fixed)", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=120)
    plt.close(fig)


def fig_days_by_definition(county_run, path):
    sub = county_run[county_run["window_key"] == PRIMARY_WINDOW]
    if not len(sub):
        return
    order = (sub.groupby("definition_id")["heatwave_days"].median()
             .sort_values(ascending=False).index.tolist())
    data = [sub.loc[sub["definition_id"] == d, "heatwave_days"].to_numpy() for d in order]
    colors = {"TMAX": "#C44E52", "TMIN": "#4C72B0", "MHI": "#55A868"}
    fig, ax = plt.subplots(figsize=(max(9, 0.62 * len(order)), 6))
    bp = ax.boxplot(data, tick_labels=order, patch_artist=True, showfliers=True)
    for b, d in zip(bp["boxes"], order):
        b.set_facecolor(colors.get(d.split("_")[0], "#888"))
        b.set_alpha(0.8)
    ax.set_ylabel("Heatwave days per county, %d-%d" % C.ANALYSIS_YEARS)
    ax.set_xlabel("definition (window = %s)" % PRIMARY_WINDOW)
    plt.setp(ax.get_xticklabels(), rotation=60, ha="right", fontsize=8)
    ax.set_title("Per-county heatwave days by definition\n"
                 "each box = 254 Texas counties; red = Tmax, blue = Tmin, green = mean heat index",
                 fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=120)
    plt.close(fig)


def fig_seasonality_grid(seas, path):
    sub = seas[seas["window_key"] == PRIMARY_WINDOW].copy()
    if not len(sub):
        return
    sub = sub.sort_values(["metric_code", "percentile", "min_duration"])
    n = len(sub)
    ncol = 4
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.5 * ncol, 2.5 * nrow), squeeze=False)
    axes = axes.ravel()
    for k, (_, r) in enumerate(sub.iterrows()):
        ax = axes[k]
        vals = [r["pct_" + m] for m in MONTH_ABBR]
        cols = ["#4C72B0"] * 12
        for m in (6, 7, 8, 9):
            cols[m - 1] = "#C44E52"
        ax.bar(range(1, 13), vals, color=cols, edgecolor="white", linewidth=0.4)
        ax.set_title("%s\nJun-Sep %.0f%% | peak %s" % (r["definition_id"], r["pct_jun_sep"],
                                                       r["peak_month"]), fontsize=8.5)
        ax.set_xticks([1, 4, 7, 10])
        ax.set_xticklabels(["J", "A", "J", "O"], fontsize=7)
        ax.tick_params(labelsize=7)
    for k in range(n, len(axes)):
        axes[k].axis("off")
    fig.suptitle("Seasonality of heatwave days by definition (window = %s)\n"
                 "a year-round RELATIVE definition flags 'unusual for the date', so cool-season "
                 "days can qualify" % PRIMARY_WINDOW, fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=120)
    plt.close(fig)


def fig_window_effect(master, path):
    piv = master.pivot_table(index="definition_id", columns="window_key",
                             values="heatwave_days_QA_pooled")
    order = [w for w in sorted(C.GRID_WINDOWS, key=lambda k: C.GRID_WINDOWS[k]["order"])
             if w in piv.columns]
    piv = piv[order]
    if PRIMARY_WINDOW not in piv.columns:
        return
    rel = piv.div(piv[PRIMARY_WINDOW], axis=0)
    fig, ax = plt.subplots(figsize=(max(9, 0.62 * len(piv)), 5.5))
    x = np.arange(len(piv))
    w = 0.8 / len(order)
    for i, wk in enumerate(order):
        ax.bar(x + i * w - 0.4 + w / 2, rel[wk].to_numpy(), width=w,
               label="%s (%s)" % (wk, C.GRID_WINDOWS[wk]["label"]))
    ax.axhline(1.0, color="k", ls="--", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels(piv.index, rotation=60, ha="right", fontsize=8)
    ax.set_ylabel("heatwave days relative to %s" % PRIMARY_WINDOW)
    ax.legend(fontsize=7.5)
    ax.set_title("Threshold-window sensitivity across all definitions\n"
                 "(pooled heatwave days, each definition normalised to its %s value)"
                 % PRIMARY_WINDOW, fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=120)
    plt.close(fig)


def fig_rank_stability(S, runs, path):
    meta = {r["run_id"]: r for r in runs}
    order = [x for x in sorted(S.index, key=lambda x: (meta[x]["metric_code"], meta[x]["percentile"],
                                                       meta[x]["min_duration"],
                                                       meta[x]["window_order"]))]
    M = S.loc[order, order]
    labels = [short_label(meta[x]) for x in order]
    fig, ax = plt.subplots(figsize=(0.28 * len(order) + 5, 0.28 * len(order) + 4))
    im = ax.imshow(M.to_numpy(), cmap="RdYlBu_r", vmin=0, vmax=1)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(labels, rotation=90, fontsize=6)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(labels, fontsize=6)
    fig.colorbar(im, ax=ax, shrink=0.7, label="Spearman rho (county ranking)")
    ax.set_title("Do the definitions rank COUNTIES the same way?\n"
                 "Spearman correlation of per-county heatwave-day totals",
                 fontsize=11, fontweight="bold")
    fig.text(0.005, 0.005, "High rho with low day-level Jaccard means the definitions disagree on "
             "WHICH DAYS are heatwave days while still ranking counties similarly.",
             fontsize=7, color="#555")
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=130)
    plt.close(fig)


# =============================================================================
# driver
# =============================================================================
def run_state(state, with_day_level=True):
    t0 = time.time()
    cdir = C.comparison_dir(state)
    tdir, fdir = os.path.join(cdir, "tables"), os.path.join(cdir, "figures")
    runs = available_runs(state)
    log("=" * 72)
    log("p05  cross-definition comparison  --  state=%s  (%d runs on disk)" % (state, len(runs)))
    log("=" * 72)
    if not runs:
        log("no completed runs found -- run run_grid.py first.")
        return

    master_path = os.path.join(tdir, "master_run_summary.csv")
    if os.path.exists(master_path):
        master = pd.read_csv(master_path)
    else:
        rows = []
        for r in runs:
            p = os.path.join(C.grid_definition_dir(state, r["definition_id"], make=False),
                             "tables", "run_summary_%s.json" % r["window_key"])
            with open(p) as f:
                rows.append(json.load(f))
        master = pd.DataFrame(rows)
        master.to_csv(master_path, index=False)
    log("[1/6] master_run_summary: %d runs" % len(master))

    county_run = build_county_run_table(state, runs)
    county_run.to_csv(os.path.join(tdir, "master_county_run_summary.csv"), index=False)
    log("[2/6] master_county_run_summary: %d rows (%d counties x %d runs)"
        % (len(county_run), county_run["county_fips"].nunique(), county_run["run_id"].nunique()))

    seas = seasonality_by_run(state, runs)
    seas.to_csv(os.path.join(tdir, "seasonality_by_run.csv"), index=False)
    log("[3/6] seasonality_by_run: %d runs" % len(seas))

    S = rank_stability(county_run)
    S.to_csv(os.path.join(tdir, "county_rank_stability.csv"))
    log("[4/6] county_rank_stability: %dx%d" % S.shape)

    J = pairs = mdf = summary = None
    if with_day_level:
        log("[5/6] day-level agreement ...")
        sets = load_day_sets(state, runs)
        if sets:
            present = [r for r in runs if r["run_id"] in sets]
            J = jaccard_matrix(sets, present)
            J.to_csv(os.path.join(tdir, "agreement_jaccard_matrix.csv"))
            pairs = jaccard_pairs(J, present)
            pairs.to_csv(os.path.join(tdir, "agreement_jaccard_pairs.csv"), index=False)
            mdf, summary = marginal_effects(master, pairs)
            if len(mdf):
                mdf.to_csv(os.path.join(tdir, "marginal_effects.csv"), index=False)
                summary.to_csv(os.path.join(tdir, "marginal_effects_summary.csv"), index=False)
            log("      jaccard matrix %dx%d, %d pairs, %d single-axis pairs"
                % (J.shape[0], J.shape[1], len(pairs), int((pairs["n_axes_differing"] == 1).sum())))

    log("[6/6] figures ...")
    if J is not None:
        fig_jaccard_heatmap(J, [r for r in runs if r["run_id"] in J.index],
                            os.path.join(fdir, "cmp01_jaccard_heatmap.png"))
        log("      cmp01_jaccard_heatmap")
    if mdf is not None and len(mdf):
        fig_marginal_effects(mdf, summary, os.path.join(fdir, "cmp02_marginal_effects.png"))
        log("      cmp02_marginal_effects")
    fig_days_by_definition(county_run, os.path.join(fdir, "cmp03_days_by_definition.png"))
    log("      cmp03_days_by_definition")
    fig_seasonality_grid(seas, os.path.join(fdir, "cmp04_seasonality_grid.png"))
    log("      cmp04_seasonality_grid")
    fig_window_effect(master, os.path.join(fdir, "cmp05_window_effect.png"))
    log("      cmp05_window_effect")
    if S is not None and len(S):
        fig_rank_stability(S, [r for r in runs if r["run_id"] in S.index],
                           os.path.join(fdir, "cmp06_rank_stability.png"))
        log("      cmp06_rank_stability")

    log("[done] comparison layer for %s in %.1f min  ->  %s"
        % (state, (time.time() - t0) / 60, cdir))
    if summary is not None and len(summary):
        log("\nMARGINAL EFFECT OF EACH AXIS (lower jaccard = bigger effect):")
        log(summary.to_string(index=False))
    return master, county_run, J, summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", action="append", default=None)
    ap.add_argument("--no-day-level", action="store_true",
                    help="skip the Jaccard/day-level layer (needs the per-day files)")
    a = ap.parse_args()
    for st in (a.state or C.STATES):
        run_state(st, with_day_level=not a.no_day_level)
