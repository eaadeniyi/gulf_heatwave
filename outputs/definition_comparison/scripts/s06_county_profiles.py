"""
=============================================================================
s06  --  FIGURE 8: an automated report card for every county.
=============================================================================
One PNG plus two CSVs for each of the 254 counties, all at the primary
threshold window, each panel labelled with its own unit:

  header   data completeness: analysis days, native vs IDW-imputed days, the
           imputation percentage, whether the county passes the prespecified
           completeness cut, whether it is 100% imputed, its climate division,
           and the RH-clip artifact days excluded
  panel A  16 definitions x 11 years, heatwave DAYS               (county-year)
  panel B  16 definitions x 11 years, heatwave EVENTS started     (county-year)
  panel C  16 definitions x 12 months, heatwave days per 1,000 eligible
           county-days                                            (county-month)
  panel D  16 x 16 day-level Jaccard WITHIN this county           (county-date)

  <fips>/county_year_summary.csv    the numbers behind panels A and B
  <fips>/county_month_summary.csv   the numbers behind panel C
  <fips>/jaccard_matrix.csv         the matrix behind panel D

The two untested mean-HI 3-day cells appear as flat grey "NOT TESTED" rows in
every panel -- never as zeros, which would read as "evaluated, found nothing".

A county's report card is a DESCRIPTION of how the definitions behave there. It
is not evidence that one definition is right for that county: none of these
panels contains an observed outcome.

USAGE
    python s06_county_profiles.py                  # all 254 counties
    python s06_county_profiles.py --county 48201   # one county
    python s06_county_profiles.py --limit 5        # first 5, for a quick look
=============================================================================
"""
import os
import sys
import time
import argparse

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defcmp_config as K
import defcmp_common as U
import config as C

STATE = K.STATE
YEARS = list(range(C.ANALYSIS_YEARS[0], C.ANALYSIS_YEARS[1] + 1))
YLAB = "%d-%d" % C.ANALYSIS_YEARS
DEF_ORDER = K.def_order()
UNTESTED = [u["definition_id"] for u in K.UNTESTED_CELLS]
ROWS = DEF_ORDER + UNTESTED


def row_labels():
    out = []
    for d in ROWS:
        mc, p, dur = d.split("_")[0], int(d.split("_")[1][1:]), int(d.split("_")[2][0])
        out.append("%s.P%d.%dD" % (mc, p, dur))
    return out


def _grid(ax, data, xticklabels, cmap, cbar_label, fig, fmt="%.0f", vmax=None,
          mark_jun_sep=False):
    """One heatmap panel with untested rows masked to flat grey."""
    masked = np.ma.masked_invalid(data)
    cm = plt.get_cmap(cmap).copy()
    cm.set_bad(K.COLOR_NOT_TESTED)
    vmax = vmax if vmax is not None else (np.nanmax(data) if np.isfinite(np.nanmax(data)) else 1)
    im = ax.imshow(masked, cmap=cm, aspect="auto", vmin=0, vmax=max(vmax, 1e-9))
    ax.set_xticks(range(len(xticklabels)))
    ax.set_xticklabels(xticklabels, fontsize=6.5, rotation=0)
    ax.set_yticks(range(len(ROWS)))
    ax.set_yticklabels(row_labels(), fontsize=6.2)
    for i, d in enumerate(ROWS):
        ax.get_yticklabels()[i].set_color(K.METRIC_STYLE[d.split("_")[0]]["color"])
    for i in range(data.shape[0]):
        if d_is_untested(i):
            ax.text(data.shape[1] / 2 - 0.5, i, "NOT TESTED", ha="center", va="center",
                    fontsize=6.2, color="#8a4b08", fontweight="bold")
            continue
        for j in range(data.shape[1]):
            v = data[i, j]
            if not np.isfinite(v):
                continue
            ax.text(j, i, fmt % v, ha="center", va="center", fontsize=5.2,
                    color=("white" if v > 0.62 * vmax else "#222222"))
    ax.set_xticks(np.arange(-0.5, data.shape[1], 1), minor=True)
    ax.set_yticks(np.arange(-0.5, data.shape[0], 1), minor=True)
    ax.grid(which="minor", color="white", lw=0.5)
    ax.tick_params(which="minor", length=0)
    if mark_jun_sep:
        ax.add_patch(Rectangle((4.5, -0.5), 4.0, data.shape[0], fill=False,
                               edgecolor="#8a4b08", lw=1.6, zorder=5))
    cb = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.015)
    cb.set_label(cbar_label, fontsize=6.5)
    cb.ax.tick_params(labelsize=6)
    return im


def d_is_untested(i):
    return ROWS[i] in UNTESTED


def county_jaccard(day_sets_by_county, fips):
    """16 x 16 day-level Jaccard inside ONE county."""
    n = len(ROWS)
    M = np.full((n, n), np.nan)
    for i, di in enumerate(ROWS):
        if di in UNTESTED:
            continue
        a = day_sets_by_county.get((di, fips))
        if a is None:
            a = np.array([], dtype=np.int64)
        M[i, i] = 1.0 if a.size else np.nan
        for j in range(i + 1, n):
            dj = ROWS[j]
            if dj in UNTESTED:
                continue
            b = day_sets_by_county.get((dj, fips), np.array([], dtype=np.int64))
            inter = np.intersect1d(a, b, assume_unique=True).size
            union = a.size + b.size - inter
            M[i, j] = M[j, i] = (inter / union) if union else np.nan
    return M


def load_day_sets_by_county():
    """(definition, county) -> sorted array of date ordinals, primary window only."""
    out = {}
    for d in DEF_ORDER:
        p = K.canonical_path(d, K.PRIMARY_WINDOW)
        if not os.path.exists(p):
            continue
        t = pd.read_csv(p, usecols=["county_fips", "date", "heatwave_day_flag"],
                        dtype={"county_fips": str})
        t = t[t["heatwave_day_flag"] == 1]
        ordinals = (pd.to_datetime(t["date"]).to_numpy(dtype="datetime64[D]")
                    .astype(np.int64))
        for fips, idx in pd.Series(range(len(t))).groupby(t["county_fips"].to_numpy()):
            out[(d, fips)] = np.sort(ordinals[idx.to_numpy()])
        K.log("   [load] %s: %d counties" % (d, t["county_fips"].nunique()))
    return out


def build_card(fips, ref_row, cy, cm, el, day_sets):
    name = ref_row["county_name"]
    outdir = K.county_profile_dir(fips)

    # ---- panel data ---------------------------------------------------------
    A = np.full((len(ROWS), len(YEARS)), np.nan)
    B = np.full((len(ROWS), len(YEARS)), np.nan)
    Cc = np.full((len(ROWS), 12), np.nan)
    cyc = cy[(cy["county_fips"] == fips) & (cy["window"] == K.PRIMARY_WINDOW)]
    cmc = cm[(cm["county_fips"] == fips) & (cm["window"] == K.PRIMARY_WINDOW)]
    elc = el[el["county_fips"] == fips]
    for i, d in enumerate(ROWS):
        if d in UNTESTED:
            continue
        metric = d.split("_")[0]
        s = cyc[cyc["definition_id"] == d].set_index("year")
        for j, y in enumerate(YEARS):
            A[i, j] = float(s["heatwave_days"].get(y, 0))
            B[i, j] = float(s["heatwave_events_started"].get(y, 0))
        m = (cmc[cmc["definition_id"] == d].groupby("month")["heatwave_days"].sum()
             .reindex(range(1, 13), fill_value=0))
        e = (elc[(elc["metric"] == metric) & (elc["window"] == K.PRIMARY_WINDOW)]
             .groupby("month")["eligible_days"].sum().reindex(range(1, 13)))
        Cc[i, :] = (1000.0 * m / e).to_numpy()
    D = county_jaccard(day_sets, fips)

    # ---- figure -------------------------------------------------------------
    fig = plt.figure(figsize=(17.0, 11.6))
    gs = fig.add_gridspec(2, 2, hspace=0.30, wspace=0.20,
                          left=0.055, right=0.98, top=0.855, bottom=0.055)
    axA, axB = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])
    axC, axD = fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])

    _grid(axA, A, [str(y) for y in YEARS], K.CMAP_SEQUENTIAL,
          "heatwave days in that county-year", fig)
    axA.set_title("A  heatwave DAYS by definition and year   (unit: county-year)",
                  fontsize=9, fontweight="bold", loc="left")
    _grid(axB, B, [str(y) for y in YEARS], K.CMAP_SEQUENTIAL,
          "heatwave events STARTED in that county-year", fig)
    axB.set_title("B  heatwave EVENTS started by definition and year   (unit: county-year; "
                  "an event is counted once, in its onset year)",
                  fontsize=9, fontweight="bold", loc="left")
    _grid(axC, Cc, K.MONTH_ABBR, K.CMAP_SEQUENTIAL,
          "heatwave days per 1,000 eligible county-days", fig, fmt="%.0f",
          mark_jun_sep=True)
    axC.set_title("C  seasonality as a RATE by definition and month   (unit: county-month, "
                  "%s pooled; box = Jun-Sep)" % YLAB, fontsize=9, fontweight="bold", loc="left")

    masked = np.ma.masked_invalid(D)
    cm_ = plt.get_cmap(K.CMAP_SEQUENTIAL).copy()
    cm_.set_bad(K.COLOR_NOT_TESTED)
    im = axD.imshow(masked, cmap=cm_, vmin=0, vmax=1, aspect="auto")
    axD.set_xticks(range(len(ROWS)))
    axD.set_xticklabels(row_labels(), rotation=90, fontsize=6.0)
    axD.set_yticks(range(len(ROWS)))
    axD.set_yticklabels(row_labels(), fontsize=6.0)
    for i, d in enumerate(ROWS):
        col = K.METRIC_STYLE[d.split("_")[0]]["color"]
        axD.get_xticklabels()[i].set_color(col)
        axD.get_yticklabels()[i].set_color(col)
    for b in K.metric_family_boundaries():
        axD.axhline(b - 0.5, color="#222222", lw=0.8)
        axD.axvline(b - 0.5, color="#222222", lw=0.8)
    for i in range(len(ROWS)):
        for j in range(len(ROWS)):
            if np.isfinite(D[i, j]):
                axD.text(j, i, ("%.2f" % D[i, j]).lstrip("0"), ha="center", va="center",
                         fontsize=4.6, color=("white" if D[i, j] > 0.6 else "#222222"))
    cb = fig.colorbar(im, ax=axD, shrink=0.85, pad=0.015)
    cb.set_label("Jaccard within this county (fixed 0-1)", fontsize=6.5)
    cb.ax.tick_params(labelsize=6)
    axD.set_title("D  do the definitions agree on WHICH DAYS, in this county?   "
                  "(unit: county-date)", fontsize=9, fontweight="bold", loc="left")

    # ---- header -------------------------------------------------------------
    imp = ref_row["temperature_imputation_pct"]
    art = int(elc["artifact_excluded_days"].max()) if len(elc) else 0
    flag = ("DATA-QUALITY FLAG: temperature is 100% IDW-imputed - this county has no native "
            "station record and must not be read as an independent observation"
            if ref_row["fully_imputed_county"] else
            ("DATA-QUALITY FLAG: temperature imputation %.1f%% exceeds the prespecified %.0f%% "
             "cut - excluded from the complete-data panels" % (imp, K.IMPUTATION_MAX_PCT)
             if not ref_row["data_complete"] else
             "completeness: passes the prespecified %.0f%% imputation cut"
             % K.IMPUTATION_MAX_PCT))
    fig.suptitle("Figure 8  County report card - %s County (FIPS %s), %s\n"
                 "%d heatwave definitions, %s, threshold window %s"
                 % (name, fips, K.STATE_LABEL, len(DEF_ORDER), YLAB, K.PRIMARY_WINDOW),
                 fontsize=13, fontweight="bold", x=0.055, ha="left", y=0.985)
    hdr = ("climate division: %s (%s)     |     analysis days: %s     |     "
           "native: %s     |     IDW-imputed: %s (%.1f%%)     |     "
           "RH-clip artifact days excluded (mean HI only): %d"
           % (ref_row["climate_division"], ref_row["climdiv_id"],
              "{:,}".format(int(ref_row["analysis_days"])),
              "{:,}".format(int(ref_row["native_analysis_days"])),
              "{:,}".format(int(ref_row["temp_imputed_days"])), imp, art))
    fig.text(0.055, 0.935, hdr, fontsize=8.2, color=K.COLOR_INK)
    fig.text(0.055, 0.913, flag, fontsize=8.2, fontweight="bold",
             color=("#8a4b08" if not ref_row["data_complete"] else "#1a6b3c"))
    fig.text(0.055, 0.888,
             "Grey rows = the two mean-HI 3-day cells, never run: shown as NOT TESTED, not as "
             "zero. Counts are cumulative over %s, never annual. Jaccard is agreement between "
             "definitions, not accuracy - no panel here contains an observed outcome." % YLAB,
             fontsize=7.2, color=K.COLOR_INK_SOFT)

    path = os.path.join(outdir, "fig08_report_card_%s.png" % fips)
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=105)
    plt.close(fig)

    # ---- the CSVs behind the panels ----------------------------------------
    cyc.to_csv(os.path.join(outdir, "county_year_summary.csv"), index=False)
    cmo = cmc.copy()
    cmo.to_csv(os.path.join(outdir, "county_month_summary.csv"), index=False)
    pd.DataFrame(D, index=ROWS, columns=ROWS).to_csv(os.path.join(outdir, "jaccard_matrix.csv"))
    return path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--county", action="append", default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    K.ensure_dirs()
    t0 = time.time()
    ref = U.read_reference()
    cy = U.read_master_county_year()
    cm = U.read_master_county_month()
    el = U.read_eligibility()

    K.log("=" * 74)
    K.log("s06  COUNTY REPORT CARDS (Figure 8)")
    K.log("=" * 74)
    day_sets = load_day_sets_by_county()

    counties = sorted(ref["county_fips"].unique())
    if args.county:
        counties = [c for c in counties if c in set(args.county)]
    if args.limit:
        counties = counties[:args.limit]
    K.log("rendering %d county report card(s)" % len(counties))

    refi = ref.set_index("county_fips")
    for n, fips in enumerate(counties, 1):
        build_card(fips, refi.loc[fips], cy, cm, el, day_sets)
        if n % 25 == 0 or n == len(counties):
            K.log("   %3d/%d  (%.1f min elapsed)" % (n, len(counties), (time.time() - t0) / 60))

    # a small index so the 254 folders are navigable
    idx = ref[["county_fips", "county_name", "climate_division", "climdiv_id",
               "temperature_imputation_pct", "fully_imputed_county", "data_complete"]].copy()
    idx["report_card"] = idx["county_fips"].map(
        lambda f: "county_profiles/%s/fig08_report_card_%s.png" % (f, f))
    idx.sort_values(["climdiv_id", "county_name"]).to_csv(
        os.path.join(K.DIR_COUNTY, "INDEX.csv"), index=False)
    K.log("=" * 74)
    K.log("s06 done: %d cards in %.1f min" % (len(counties), (time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
