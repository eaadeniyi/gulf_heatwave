"""
=============================================================================
run_grid.py  --  execute the DEFINITION GRID and keep the registry honest.
=============================================================================
The grid is 14 definitions x 4 threshold windows = 56 runs (see config.py).

    definition = METRIC x PERCENTILE x MIN_DURATION      e.g. TMAX_P90_2D
    run        = definition x WINDOW                     e.g. TMAX_P90_2D__w15

HOW DEFINITIONS ARE TRACKED
  definition_registry.csv is REGENERATED FROM config.py on every invocation and
  is the thing this script iterates. It cannot drift from what actually ran,
  which is the failure mode of a hand-maintained registry. Each row carries the
  full specification of one run plus its status, output path and last runtime.

  Alongside it:
    run_log.csv        append-only provenance -- when each run executed, against
                       which git commit and which input-file hash
    _comparison/tables/master_run_summary.csv
                       one headline row per run, written incrementally so partial
                       progress is usable

USAGE
  python run_grid.py                     # run everything not yet done
  python run_grid.py --force             # re-run everything
  python run_grid.py --metric tmax       # only Tmax definitions
  python run_grid.py --duration 3        # only the 3-day definitions
  python run_grid.py --window w15 --window month
  python run_grid.py --percentile 90
  python run_grid.py --registry-only     # just (re)write the registry, run nothing
  python run_grid.py --no-daily          # skip the large per-day heatwave files
=============================================================================
"""
import os, sys, time, json, hashlib, argparse, subprocess, datetime
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import p02_classify_and_report as p02

REGISTRY_COLS = [
    "run_id", "definition_id", "def_number", "user_item", "definition_sentence",
    "metric", "metric_code", "metric_col", "metric_label",
    "percentile", "comparison_op", "min_duration",
    "window_key", "window_type", "window_label", "window_half", "window_collar", "window_order",
    "baseline", "season", "absolute_floor", "artifact_handling", "analysis_years",
    "status", "last_run_utc", "runtime_seconds", "output_dir",
]


def log(*a):
    print(*a, flush=True)


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=os.path.dirname(C.PIPELINE_DIR), capture_output=True,
                              text=True, timeout=20).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def file_fingerprint(path):
    """md5 of the input county-day table, so every result is traceable to its input."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return "md5:" + h.hexdigest()[:16]


# =============================================================================
# registry
# =============================================================================
def build_registry(state, runs):
    """The authoritative run list, regenerated from config every time."""
    rows = []
    for r in runs:
        rows.append({
            "run_id": r["run_id"], "definition_id": r["definition_id"],
            "def_number": r["def_number"], "user_item": r["user_item"],
            "definition_sentence": C.definition_sentence(
                r["metric"], r["percentile"], r["min_duration"], r["window_key"]),
            "metric": r["metric"], "metric_code": r["metric_code"],
            "metric_col": r["metric_col"], "metric_label": r["metric_label"],
            "percentile": r["percentile"], "comparison_op": r["comparison_op"],
            "min_duration": r["min_duration"],
            "window_key": r["window_key"], "window_type": r["window_type"],
            "window_label": r["window_label"], "window_half": r["window_half"],
            "window_collar": r["window_collar"], "window_order": r["window_order"],
            "baseline": r["baseline"], "season": r["season"],
            "absolute_floor": r["absolute_floor"], "artifact_handling": r["artifact_handling"],
            "analysis_years": r["analysis_years"],
            "status": "not_run", "last_run_utc": "", "runtime_seconds": "",
            "output_dir": os.path.relpath(C.grid_definition_dir(state, r["definition_id"], make=False),
                                          os.path.dirname(C.PIPELINE_DIR)).replace("\\", "/"),
        })
    reg = pd.DataFrame(rows, columns=REGISTRY_COLS)

    # carry over status/timing from a previous registry, and mark rows whose
    # output already exists on disk as done (so --resume is based on real files)
    if os.path.exists(C.REGISTRY_FILE):
        old = pd.read_csv(C.REGISTRY_FILE,
                          dtype={"status": "object", "last_run_utc": "object",
                                 "runtime_seconds": "object"}).set_index("run_id")
        for col in ("status", "last_run_utc", "runtime_seconds"):
            if col in old.columns:
                reg[col] = reg["run_id"].map(old[col]).fillna(reg[col]).astype(object)
    reg["status"] = [_disk_status(state, r) for r in runs]

    # the two already-published definitions, recorded for provenance
    legacy = []
    for d in C.LEGACY_DEFINITIONS:
        for wkey in d["windows"]:
            m = C.METRICS[d["metric"]]
            legacy.append({
                "run_id": "%s__%s" % (d["definition_id"], wkey),
                "definition_id": d["definition_id"], "def_number": d["def_number"],
                "user_item": "published_earlier",
                "definition_sentence": C.definition_sentence(
                    d["metric"], d["percentile"], d["min_duration"], wkey),
                "metric": d["metric"], "metric_code": m["code"], "metric_col": m["col"],
                "metric_label": m["label"], "percentile": d["percentile"],
                "comparison_op": C.COMPARISON_OP, "min_duration": d["min_duration"],
                "window_key": wkey, "window_type": C.GRID_WINDOWS[wkey]["type"],
                "window_label": C.GRID_WINDOWS[wkey]["label"],
                "window_half": C.GRID_WINDOWS[wkey].get("half"),
                "window_collar": C.GRID_WINDOWS[wkey].get("collar"),
                "window_order": C.GRID_WINDOWS[wkey]["order"],
                "baseline": C.BASELINE_SCHEME, "season": C.SEASON, "absolute_floor": "none",
                "artifact_handling": "rh_clip_2023_03_01_set_missing",
                "analysis_years": "%d-%d" % C.ANALYSIS_YEARS,
                "status": "published_earlier", "last_run_utc": "", "runtime_seconds": "",
                "output_dir": "outputs/%s/%s" % (state, d["output_dir_name"]),
            })
    reg = pd.concat([reg, pd.DataFrame(legacy, columns=REGISTRY_COLS)], ignore_index=True)
    reg.to_csv(C.REGISTRY_FILE, index=False)
    return reg


def _disk_status(state, run):
    """'done' if this run's summary file is already on disk."""
    p = os.path.join(C.grid_definition_dir(state, run["definition_id"], make=False),
                     "tables", "run_summary_%s.json" % run["window_key"])
    return "done" if os.path.exists(p) else "not_run"


def update_registry_row(run_id, status, runtime=None):
    if not os.path.exists(C.REGISTRY_FILE):
        return
    # status/last_run_utc/runtime_seconds start out empty, so pandas reads them back
    # as all-NaN float columns -- read them as strings so writing a value in place
    # does not fail on dtype
    reg = pd.read_csv(C.REGISTRY_FILE,
                      dtype={"status": "object", "last_run_utc": "object",
                             "runtime_seconds": "object"})
    i = reg.index[reg["run_id"] == run_id]
    if len(i):
        reg.loc[i, "status"] = status
        reg.loc[i, "last_run_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        if runtime is not None:
            reg.loc[i, "runtime_seconds"] = "%.1f" % runtime
        reg.to_csv(C.REGISTRY_FILE, index=False)


def append_run_log(state, summ, commit, fingerprint):
    path = os.path.join(C.grid_root(state), "run_log.csv")
    row = {"logged_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "state": state, "run_id": summ["run_id"], "definition_id": summ["definition_id"],
           "def_number": summ["def_number"], "git_commit": commit,
           "input_fingerprint": fingerprint,
           "heatwave_days_QA_pooled": summ["heatwave_days_QA_pooled"],
           "heatwave_events_QA_pooled": summ["heatwave_events_QA_pooled"],
           "per_county_heatwave_days_median": summ["per_county_heatwave_days_median"],
           "runtime_seconds": summ["runtime_seconds"]}
    df = pd.DataFrame([row])
    df.to_csv(path, mode="a", header=not os.path.exists(path), index=False)


def write_master(state, summaries):
    """Master headline table: one row per run. Rewritten after every run so
    partial progress is immediately usable."""
    if not summaries:
        return None
    d = C.comparison_dir(state)
    df = pd.DataFrame(summaries).sort_values(
        ["metric", "percentile", "min_duration", "window_order"]).reset_index(drop=True)
    df.to_csv(os.path.join(d, "tables", "master_run_summary.csv"), index=False)
    return df


# =============================================================================
# main
# =============================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the heatwave definition grid.")
    ap.add_argument("--state", action="append", default=None)
    ap.add_argument("--metric", action="append", default=None, choices=sorted(C.METRICS))
    ap.add_argument("--percentile", action="append", type=int, default=None)
    ap.add_argument("--duration", action="append", type=int, default=None)
    ap.add_argument("--window", action="append", default=None, choices=sorted(C.GRID_WINDOWS))
    ap.add_argument("--def-number", action="append", type=int, default=None)
    ap.add_argument("--force", action="store_true", help="re-run runs already on disk")
    ap.add_argument("--no-daily", action="store_true", help="skip the large per-day files")
    ap.add_argument("--registry-only", action="store_true", help="write the registry and stop")
    args = ap.parse_args(argv)

    states = args.state or C.STATES
    commit = git_commit()
    t_all = time.time()

    for state in states:
        all_runs = C.grid_runs()
        reg = build_registry(state, all_runs)
        log("=" * 72)
        log("DEFINITION GRID  --  state=%s" % state)
        log("=" * 72)
        log("%d definitions x %d windows = %d runs" %
            (len(C.GRID_DEFINITIONS), len(C.GRID_WINDOWS), len(all_runs)))
        log("registry: %s" % C.REGISTRY_FILE)
        log("threshold passes needed: %d  (thresholds depend on metric x window only)"
            % len(C.threshold_jobs()))
        if args.registry_only:
            log("[registry-only] wrote %d rows; nothing executed." % len(reg))
            continue

        # ---- select which runs to execute ---------------------------------
        runs = all_runs
        if args.metric:
            runs = [r for r in runs if r["metric"] in args.metric]
        if args.percentile:
            runs = [r for r in runs if r["percentile"] in args.percentile]
        if args.duration:
            runs = [r for r in runs if r["min_duration"] in args.duration]
        if args.window:
            runs = [r for r in runs if r["window_key"] in args.window]
        if args.def_number:
            runs = [r for r in runs if r["def_number"] in args.def_number]
        if not args.force:
            skipped = [r for r in runs if _disk_status(state, r) == "done"]
            runs = [r for r in runs if _disk_status(state, r) != "done"]
            if skipped:
                log("resuming: %d run(s) already on disk, skipped (use --force to redo)"
                    % len(skipped))
        if not runs:
            log("nothing to do for %s." % state)
            continue
        log("executing %d run(s)" % len(runs))

        # ---- execute -------------------------------------------------------
        fingerprint = file_fingerprint(C.county_day_path(state))
        log("input: %s  (%s)" % (os.path.basename(C.county_day_path(state)), fingerprint))
        cd = p02.load_county_days(state)

        summaries = []

        def on_summary(s):
            summaries.append(s)
            update_registry_row(s["run_id"], "done", s["runtime_seconds"])
            append_run_log(state, s, commit, fingerprint)
            write_master(state, _merge_existing(state, summaries))

        p02.run_grid_state(state, runs=runs, cd=cd, write_daily=not args.no_daily,
                           on_summary=on_summary)

        final = write_master(state, _merge_existing(state, summaries))
        log("=" * 72)
        log("GRID COMPLETE  --  state=%s  %d run(s) in %.1f min"
            % (state, len(summaries), (time.time() - t_all) / 60))
        if final is not None:
            log("master table: %s" % os.path.join(C.comparison_dir(state), "tables",
                                                  "master_run_summary.csv"))
            show = ["run_id", "heatwave_days_QA_pooled", "heatwave_events_QA_pooled",
                    "per_county_heatwave_days_median", "event_duration_median_days",
                    "pct_heatwave_days_jun_sep"]
            log("\n" + final[show].to_string(index=False))


def _merge_existing(state, summaries):
    """Combine this session's summaries with any already on disk from earlier runs,
    so the master table always covers every completed run rather than only the
    ones executed in this invocation."""
    have = {s["run_id"]: s for s in summaries}
    for r in C.grid_runs():
        if r["run_id"] in have:
            continue
        p = os.path.join(C.grid_definition_dir(state, r["definition_id"], make=False),
                         "tables", "run_summary_%s.json" % r["window_key"])
        if os.path.exists(p):
            try:
                with open(p) as f:
                    have[r["run_id"]] = json.load(f)
            except Exception:
                pass
    return list(have.values())


if __name__ == "__main__":
    main()
