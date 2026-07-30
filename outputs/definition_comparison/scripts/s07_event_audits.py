"""
=============================================================================
s07  --  FIGURE 9 (individual event timelines) and FIGURE 10 (long-event audit).
=============================================================================
FIGURE 9  event_audits/fig09_timeline_<fips>_<county>.png
  For each example county, ONE calendar window shown for all five shortlisted
  definitions, stacked. Each panel draws the daily metric against that county's
  own walk-forward threshold and marks:
      qualifying runs (heatwave events)  shaded, with exact start and end dates
                                         and the INTEGER duration labelled
      isolated candidate days            candidate but too short to qualify:
                                         ringed, because they are the reason a
                                         run stopped
      imputed records                    open markers (IDW-filled temperature)
      observed records                   filled markers
  The window is anchored mechanically (see EVENT_TIMELINE_REFERENCE_* in the
  config): the first event of the middle study year under one fixed reference
  definition. Showing the SAME days for all five definitions is the point --
  it is where "the metric changes which days, not how many" becomes visible.

FIGURE 10  event_audits/fig10_long_event_<run>_<event_id>.png
  Every event at or above the prespecified review length (>= %d days), longest
  first, at the primary window. Each figure carries the daily metric and
  threshold, the daily exceedance, the imputation state of every day, the
  CONTRIBUTING STATION COUNT for Tmax and Tmin, and month boundaries -- the
  things needed to judge whether a three-week "event" is a heat episode or an
  artefact of gap-filled data.

  NOTHING IS DELETED. Long events stay in every table and every count. This
  step only makes them inspectable. Where the cap limits how many are DRAWN,
  the ones not drawn are listed in event_audits/fig10_not_individually_plotted.csv.

STATION COUNTS come from the RAW GHCN county-day file (tmax_f_nstations,
tmin_f_nstations), because p01 does not carry them into the classification
table. That is the only place in this package that reads a raw input.
=============================================================================
""" % 21
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
import matplotlib.dates as mdates
from matplotlib.lines import Line2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defcmp_config as K
import defcmp_common as U
import config as C
import p02_classify_and_report as p02
import s02_canonical_long as s02

STATE = K.STATE
plt.rcParams.update({"font.size": 9, "axes.titlesize": 10,
                     "axes.edgecolor": "#999999", "savefig.facecolor": "white"})


# =============================================================================
# inputs
# =============================================================================
def load_station_counts():
    """Per-county-day contributing station counts, from the RAW GHCN input.

    p01 uses these to build the county-day series but does not retain them, so
    the audit reads them back from the source file. Without this, "station count"
    could not be shown at all -- and inventing it was not an option.
    """
    p = C.ghcn_path(STATE)
    if not os.path.exists(p):
        K.log("   [warn] raw GHCN file absent (%s): station counts unavailable" % p)
        return None
    sc = pd.read_csv(p, usecols=["county_fips", "date", "tmax_f_nstations",
                                 "tmin_f_nstations"], dtype={"county_fips": str})
    sc["date"] = pd.to_datetime(sc["date"])
    sc = sc[(sc["date"].dt.year >= C.ANALYSIS_YEARS[0])
            & (sc["date"].dt.year <= C.ANALYSIS_YEARS[1])]
    K.log("   [load] station counts: %s county-days from %s"
          % ("{:,}".format(len(sc)), os.path.basename(p)))
    return sc


def daily_frames(definition_ids, window_key, cd, ref):
    """Rebuild the full daily panel (candidate and non-candidate days) for each
    definition, using the same code path as the canonical table."""
    out = {}
    runs = {r["definition_id"]: r for r in K.runs_expanded() if r["window_key"] == window_key}
    for d in definition_ids:
        r = runs[d]
        thr, key_name = s02.load_thresholds(r["metric"], r["percentile"], window_key)
        _, ev, _, daily, _ = s02.classify_run(r, cd, thr, key_name, ref, "n/a", "n/a")
        out[d] = (daily[["county_fips", "county_name", "date", "year", "month",
                         "metric_value_f", "threshold_value_f", "candidate_day_flag",
                         "heatwave_day_flag", "event_id", "event_start_date",
                         "event_end_date", "event_duration_days", "temp_imputed"]],
                  ev)
        K.log("   [rebuild] %-14s %s heatwave days, %s events"
              % (d, "{:,}".format(int(daily['heatwave_day_flag'].sum())), "{:,}".format(len(ev))))
    return out


# =============================================================================
# FIGURE 9 -- event timelines, five definitions over one calendar window
# =============================================================================
def anchor_window(frames, fips):
    """The calendar window for one county: the first event of the reference year
    under the reference definition, padded, and at least 45 days wide."""
    ref_def = K.EVENT_TIMELINE_REFERENCE_DEFINITION
    _, ev = frames[ref_def]
    e = ev[ev["county_fips"] == fips].sort_values("start_date")
    if not len(e):
        return None, None, None
    same = e[e["start_date"].dt.year == K.EVENT_TIMELINE_REFERENCE_YEAR]
    if not len(same):                       # fall back to the nearest year with an event
        e = e.assign(_d=(e["start_date"].dt.year - K.EVENT_TIMELINE_REFERENCE_YEAR).abs())
        same = e.sort_values(["_d", "start_date"])
    row = same.iloc[0]
    lo = row["start_date"] - pd.Timedelta(days=K.EVENT_TIMELINE_DAYS_PAD)
    hi = row["end_date"] + pd.Timedelta(days=K.EVENT_TIMELINE_DAYS_PAD)
    if (hi - lo).days < 45:
        pad = (45 - (hi - lo).days) // 2 + 1
        lo, hi = lo - pd.Timedelta(days=pad), hi + pd.Timedelta(days=pad)
    return lo, hi, row


def fig09_timelines(frames, examples, outdir):
    made = []
    for _, ex in examples.iterrows():
        fips, name = ex["county_fips"], ex["county_name"]
        lo, hi, anchor = anchor_window(frames, fips)
        if lo is None:
            K.log("   [skip] %s (%s): no event under the reference definition" % (name, fips))
            continue
        defs = [d for d in K.SHORTLIST_DEFINITIONS if d in frames]
        fig, axs = plt.subplots(len(defs), 1, figsize=(14.0, 2.35 * len(defs)), sharex=True)
        axs = np.atleast_1d(axs)
        for ax, d in zip(axs, defs):
            daily, _ = frames[d]
            s = daily[(daily["county_fips"] == fips) & (daily["date"] >= lo)
                      & (daily["date"] <= hi)].sort_values("date")
            mc = d.split("_")[0]
            st = K.METRIC_STYLE[mc]
            pctl = int(d.split("_")[1][1:])
            dur = int(d.split("_")[2][0])

            ax.plot(s["date"], s["threshold_value_f"], color="#444444",
                    ls=K.PCTL_STYLE[pctl]["ls"], lw=1.5, zorder=3,
                    label="%dth-percentile threshold" % pctl)
            ax.plot(s["date"], s["metric_value_f"], color=st["color"], lw=1.7, zorder=4,
                    label="%s (daily)" % st["short"])
            obs = ~s["temp_imputed"]
            ax.plot(s.loc[obs, "date"], s.loc[obs, "metric_value_f"], lw=0,
                    marker=st["marker"], ms=4.6, mfc=st["color"], mec="white", mew=0.5,
                    zorder=5)
            ax.plot(s.loc[~obs, "date"], s.loc[~obs, "metric_value_f"], lw=0,
                    marker=st["marker"], ms=5.4, mfc="none", mec=st["color"], mew=1.3,
                    zorder=5)
            # shade each qualifying run and label it. Labels are STAGGERED across three
            # offsets: consecutive events can start a few days apart, and overlapping
            # labels would make the exact dates - the point of the figure - unreadable.
            groups = list(s[s["heatwave_day_flag"] == 1].groupby("event_id", sort=True))
            for gi, (eid, g) in enumerate(groups):
                a, b = g["date"].min(), g["date"].max()
                ax.axvspan(a - pd.Timedelta(hours=12), b + pd.Timedelta(hours=12),
                           color=st["color"], alpha=0.14, zorder=1)
                d_int = int(g["event_duration_days"].iloc[0])
                partial = (g["date"].min() > pd.Timestamp(g["event_start_date"].iloc[0])) or \
                          (g["date"].max() < pd.Timestamp(g["event_end_date"].iloc[0]))
                ax.annotate("%s -> %s   %d day%s%s"
                            % (pd.Timestamp(g["event_start_date"].iloc[0]).date(),
                               pd.Timestamp(g["event_end_date"].iloc[0]).date(),
                               d_int, "s" if d_int != 1 else "",
                               "  (extends beyond this window)" if partial else ""),
                            xy=(a, ax.get_ylim()[1]),
                            xytext=(2, -11 - 9 * (gi % 3)),
                            textcoords="offset points", fontsize=6.8, color=st["color"],
                            fontweight="bold", zorder=6,
                            bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.4))
            # isolated candidate days: candidate, but not part of a qualifying run
            iso = s[(s["candidate_day_flag"] == 1) & (s["heatwave_day_flag"] == 0)]
            ax.plot(iso["date"], iso["metric_value_f"], lw=0, marker="o", ms=10,
                    mfc="none", mec="#8a4b08", mew=1.4, zorder=6)
            ax.set_ylabel("%s\n(degF)" % st["short"], fontsize=8)
            # the definition label sits ABOVE the axes, not inside it: an event that
            # starts early in the window puts its date label in the top-left corner
            ax.set_title("%s   %dth pctl, >= %d consecutive days" % (d, pctl, dur),
                         loc="left", fontsize=8.4, fontweight="bold", color=st["color"],
                         pad=3)
            U.tidy_axes(ax, grid_axis="both")
        axs[-1].xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        plt.setp(axs[-1].get_xticklabels(), fontsize=7.5, rotation=0)
        handles = [
            Line2D([0], [0], color="#444444", ls="--", lw=1.5, label="county's own threshold"),
            Line2D([0], [0], color=K.COLOR_INK_SOFT, marker="o", lw=0, ms=6,
                   mfc=K.COLOR_INK_SOFT, label="observed (native station data)"),
            Line2D([0], [0], color=K.COLOR_INK_SOFT, marker="o", lw=0, ms=6, mfc="none",
                   mew=1.3, label="IDW-imputed temperature"),
            Line2D([0], [0], color="#8a4b08", marker="o", lw=0, ms=9, mfc="none", mew=1.4,
                   label="isolated candidate day (too short to qualify)"),
        ]
        axs[0].legend(handles=handles, fontsize=6.8, loc="lower left", ncol=2,
                      framealpha=0.95)
        fig.suptitle("Figure 9  Event timelines - %s County (%s), %s division\n"
                     "the SAME %d days judged by five definitions; window anchored on the "
                     "first %d event under %s"
                     % (name, fips, ex["climate_division"], (hi - lo).days + 1,
                        K.EVENT_TIMELINE_REFERENCE_YEAR,
                        K.EVENT_TIMELINE_REFERENCE_DEFINITION),
                     fontsize=12, fontweight="bold", y=1.0, x=0.01, ha="left")
        U.footnote(fig, "unit of analysis: county-date. Shading marks a qualifying run "
                        "(a heatwave event); the label gives its exact start, end and INTEGER "
                        "duration, which may extend beyond the plotted window. Ringed points "
                        "are candidate days that failed the persistence rule - they are why a "
                        "run ended. Open markers are IDW-imputed temperature "
                        "(%.1f%% of this county's analysis days)."
                   % ex["temperature_imputation_pct"], y=-0.01)
        path = os.path.join(outdir, "fig09_timeline_%s_%s.png"
                            % (fips, str(name).replace(" ", "_")))
        fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=125)
        plt.close(fig)
        made.append(path)
        K.log("   [fig09] %s County  %s..%s" % (name, lo.date(), hi.date()))
    return made


# =============================================================================
# FIGURE 10 -- one figure per long event
# =============================================================================
def fig10_long_events(frames, audit, stations, ref, outdir, cap):
    long_ev = audit[(audit["window"] == K.PRIMARY_WINDOW)].copy()
    long_ev = long_ev.sort_values(["event_duration_days", "run_id"], ascending=[False, True])
    total = len(long_ev)
    plotted = long_ev.head(cap)
    dropped = long_ev.iloc[cap:]
    K.log("   long events at the %s window: %d; drawing %d; %d listed but not drawn"
          % (K.PRIMARY_WINDOW, total, len(plotted), len(dropped)))
    if len(dropped):
        dropped.to_csv(os.path.join(outdir, "fig10_not_individually_plotted.csv"), index=False)

    rows = []
    for n, (_, e) in enumerate(plotted.iterrows(), 1):
        d = e["definition_id"]
        if d not in frames:
            continue
        daily, _ = frames[d]
        fips = e["county_fips"]
        lo = pd.Timestamp(e["start_date"]) - pd.Timedelta(days=K.EVENT_TIMELINE_DAYS_PAD)
        hi = pd.Timestamp(e["end_date"]) + pd.Timedelta(days=K.EVENT_TIMELINE_DAYS_PAD)
        s = daily[(daily["county_fips"] == fips) & (daily["date"] >= lo)
                  & (daily["date"] <= hi)].sort_values("date")
        if not len(s):
            continue
        sc = None
        if stations is not None:
            sc = stations[(stations["county_fips"] == fips) & (stations["date"] >= lo)
                          & (stations["date"] <= hi)].sort_values("date")
        mc = d.split("_")[0]
        st = K.METRIC_STYLE[mc]

        fig, axs = plt.subplots(3, 1, figsize=(13.2, 8.2), sharex=True,
                                gridspec_kw={"height_ratios": [2.5, 1.15, 1.0], "hspace": 0.12})
        # --- metric vs threshold ---------------------------------------------
        ax = axs[0]
        ax.plot(s["date"], s["threshold_value_f"], color="#444444", ls="--", lw=1.5,
                label="%dth-percentile threshold" % int(e["percentile"]), zorder=3)
        ax.plot(s["date"], s["metric_value_f"], color=st["color"], lw=1.8,
                label="%s (daily)" % st["short"], zorder=4)
        obs = ~s["temp_imputed"]
        ax.plot(s.loc[obs, "date"], s.loc[obs, "metric_value_f"], lw=0, marker=st["marker"],
                ms=5, mfc=st["color"], mec="white", mew=0.5, zorder=5)
        ax.plot(s.loc[~obs, "date"], s.loc[~obs, "metric_value_f"], lw=0, marker=st["marker"],
                ms=6, mfc="none", mec=st["color"], mew=1.4, zorder=5)
        inside = s[s["event_id"] == e["event_id"]]
        if len(inside):
            ax.axvspan(inside["date"].min() - pd.Timedelta(hours=12),
                       inside["date"].max() + pd.Timedelta(hours=12),
                       color=st["color"], alpha=0.14, zorder=1)
        iso = s[(s["candidate_day_flag"] == 1) & (s["heatwave_day_flag"] == 0)]
        ax.plot(iso["date"], iso["metric_value_f"], lw=0, marker="o", ms=10, mfc="none",
                mec="#8a4b08", mew=1.3, zorder=6, label="isolated candidate day")
        ax.set_ylabel("%s (degF)" % st["short"])
        ax.legend(fontsize=7, loc="lower left", ncol=3, framealpha=0.95)
        U.tidy_axes(ax, grid_axis="both")

        # --- daily exceedance -------------------------------------------------
        ax = axs[1]
        exc = (s["metric_value_f"] - s["threshold_value_f"])
        ax.bar(s["date"], exc, width=0.85,
               color=np.where(exc > 0, st["color"], "#bbbbbb"),
               edgecolor="white", lw=0.3, zorder=3)
        ax.axhline(0, color="#333333", lw=1.0, zorder=2)
        ax.set_ylabel("exceedance\n(degF above own\nthreshold)", fontsize=7.5)
        U.tidy_axes(ax, grid_axis="y")

        # --- data provenance: imputation + station counts --------------------
        ax = axs[2]
        ax.bar(s["date"], np.where(s["temp_imputed"], 1, 0), width=0.85, color="#8a4b08",
               alpha=0.55, zorder=3, label="temperature IDW-imputed")
        if sc is not None and len(sc):
            # station counts and the 0/1 imputation flag share ONE y axis on purpose:
            # a second y scale would be a dual-axis chart, which is never used here
            ax.plot(sc["date"], sc["tmax_f_nstations"], color="#222222", lw=1.3,
                    marker="^", ms=3.6, zorder=4, label="Tmax contributing stations")
            ax.plot(sc["date"], sc["tmin_f_nstations"], color="#777777", lw=1.1,
                    marker="v", ms=3.4, zorder=4, label="Tmin contributing stations")
            ax.set_ylabel("stations /\nimputed flag", fontsize=7.5)
            # headroom so the station line is not hidden behind the legend when the
            # count is a flat 1 (common: many counties have a single reporting station)
            top = float(np.nanmax([sc["tmax_f_nstations"].max(),
                                   sc["tmin_f_nstations"].max(), 1.0]))
            ax.set_ylim(0, top * 1.55)
        else:
            ax.set_ylabel("imputed flag", fontsize=7.5)
            ax.set_ylim(0, 1.55)
        ax.legend(fontsize=6.6, loc="upper left", ncol=3, framealpha=0.95)
        U.tidy_axes(ax, grid_axis="y")

        # --- month boundaries on every panel ---------------------------------
        months = pd.date_range(lo.normalize(), hi.normalize(), freq="MS")
        for a in axs:
            for m in months:
                a.axvline(m, color="#8a4b08", ls=":", lw=1.0, zorder=2)
        for m in months:
            axs[0].annotate(m.strftime("1 %b"), xy=(m, axs[0].get_ylim()[0]),
                            xytext=(2, 3), textcoords="offset points", fontsize=6.5,
                            color="#8a4b08")
        axs[-1].xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Y"))
        plt.setp(axs[-1].get_xticklabels(), fontsize=7, rotation=0)

        nst = ("Tmax stations min/median %s/%s"
               % (int(sc["tmax_f_nstations"].min()), int(sc["tmax_f_nstations"].median()))
               if sc is not None and len(sc) and sc["tmax_f_nstations"].notna().any()
               else "station counts unavailable")
        fig.suptitle("Figure 10  Long-event audit - %s, %s County (%s)\n"
                     "%s to %s = %d consecutive days  |  %s  |  %.0f%% of event days "
                     "IDW-imputed  |  county imputation %.1f%%  |  %s"
                     % (e["run_id"], e["county_name"], fips, e["start_date"], e["end_date"],
                        int(e["event_duration_days"]),
                        "crosses a month boundary" if e["event_crosses_month"] else
                        "within one month",
                        e["pct_event_days_imputed"], e["temperature_imputation_pct"], nst),
                     fontsize=10.5, fontweight="bold", y=0.985, x=0.01, ha="left")
        U.footnote(fig, "unit of analysis: county-date within one heatwave event. Reviewed "
                        "because its duration is at or above the prespecified %d-day review "
                        "length. RETAINED in every table and count - this figure exists to "
                        "make it inspectable, not to justify deleting it. A relative year-round "
                        "definition can produce a run this long from a persistent mild anomaly, "
                        "which is not the same thing as sustained hazardous heat."
                   % K.LONG_EVENT_REVIEW_DAYS, y=-0.01)
        path = os.path.join(outdir, "fig10_long_event_%s_%s.png"
                            % (e["run_id"], e["event_id"]))
        fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=115)
        plt.close(fig)

        rows.append({
            "run_id": e["run_id"], "event_id": e["event_id"], "county_fips": fips,
            "county_name": e["county_name"], "start_date": e["start_date"],
            "end_date": e["end_date"], "event_duration_days": int(e["event_duration_days"]),
            "pct_event_days_imputed": e["pct_event_days_imputed"],
            "county_temperature_imputation_pct": e["temperature_imputation_pct"],
            "tmax_stations_min": (int(sc["tmax_f_nstations"].min())
                                  if sc is not None and len(sc)
                                  and sc["tmax_f_nstations"].notna().any() else np.nan),
            "tmax_stations_median": (float(sc["tmax_f_nstations"].median())
                                     if sc is not None and len(sc)
                                     and sc["tmax_f_nstations"].notna().any() else np.nan),
            "tmin_stations_min": (int(sc["tmin_f_nstations"].min())
                                  if sc is not None and len(sc)
                                  and sc["tmin_f_nstations"].notna().any() else np.nan),
            "min_exceedance_degF_in_event": round(float(
                (inside["metric_value_f"] - inside["threshold_value_f"]).min()), 3)
            if len(inside) else np.nan,
            "median_exceedance_degF_in_event": round(float(
                (inside["metric_value_f"] - inside["threshold_value_f"]).median()), 3)
            if len(inside) else np.nan,
            "figure": os.path.basename(path),
            "disposition": "RETAINED - inspected, not deleted",
        })
        if n % 25 == 0 or n == len(plotted):
            K.log("   [fig10] %3d/%d drawn" % (n, len(plotted)))

    if rows:
        pd.DataFrame(rows).to_csv(
            os.path.join(outdir, "fig10_long_event_audit_with_station_counts.csv"), index=False)
    return len(rows), total


# =============================================================================
# driver
# =============================================================================
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=K.LONG_EVENT_PLOT_CAP)
    ap.add_argument("--skip-fig09", action="store_true")
    ap.add_argument("--skip-fig10", action="store_true")
    args = ap.parse_args(argv)

    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 74)
    K.log("s07  EVENT AUDITS (Figures 9 and 10)")
    K.log("=" * 74)

    ref = U.read_reference()
    examples = pd.read_csv(os.path.join(K.DIR_TABLES, "support_example_counties.csv"),
                           dtype={"county_fips": str})
    audit = pd.read_csv(os.path.join(K.DIR_TABLES, "table8a_long_event_audit.csv"),
                        dtype={"county_fips": str})
    cd = p02.load_county_days(STATE)
    stations = load_station_counts()

    need = set(K.SHORTLIST_DEFINITIONS) | set(
        audit.loc[audit["window"] == K.PRIMARY_WINDOW, "definition_id"].unique()[:200])
    need = [d for d in K.def_order() if d in need]
    K.log("rebuilding daily panels for %d definition(s) at the %s window"
          % (len(need), K.PRIMARY_WINDOW))
    frames = daily_frames(need, K.PRIMARY_WINDOW, cd, ref)

    if not args.skip_fig09:
        K.log("-" * 74)
        K.log("Figure 9: event timelines for %d example counties" % len(examples))
        fig09_timelines(frames, examples, K.DIR_EVENTS)
    if not args.skip_fig10:
        K.log("-" * 74)
        K.log("Figure 10: long-event audit (>= %d days)" % K.LONG_EVENT_REVIEW_DAYS)
        drawn, total = fig10_long_events(frames, audit, stations, ref, K.DIR_EVENTS, args.cap)
        K.log("   %d of %d long events at the primary window drawn individually"
              % (drawn, total))
    K.log("=" * 74)
    K.log("s07 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
