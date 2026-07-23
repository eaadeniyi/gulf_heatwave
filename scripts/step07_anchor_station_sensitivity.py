"""
R3 Issue 8 (highest-value next sensitivity): stable single-airport ANCHOR
station vs the changing multi-station county COMPOSITE.

County composite Tmax (used everywhere else in this pilot) is an unweighted
mean of whichever GHCN stations report that day -- a set that changes over
1979-2025 (station provenance, quality_control/05). This can inject step
changes from network composition rather than climate. Here we rebuild each
county's temperature from a SINGLE full-span airport anchor, pair it with the
SAME gridMET RHmin (humidity source unchanged), rerun the identical
walk-forward day-of-year threshold + classification, and compare.

To isolate the station-composition effect from the RH-artifact question, BOTH
sides use retain-all (composite retain-all vs anchor retain-all).

Anchors (full-span USW airports, from provenance):
  Harris   48201 -> IAH        USW00012960
  El Paso  48141 -> El Paso IntlUSW00023044
  Lubbock  48303 -> Lubbock AP  USW00023042
  Travis   48453 -> Camp Mabry  USW00013958
  Cameron  48061 -> Brownsville USW00012919

Outputs:
  tables/events/07_daily_ANCHOR_yearround_retainall.csv
  tables/12b_anchor_vs_composite_comparison.csv
  tables/12b_anchor_vs_composite_summary.md
"""
import os, sys, time
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

ROOT = r"C:\Users\eadeni1\OneDrive - Louisiana State University\Documents\doc\heatWaveUS"
sys.path.insert(0, os.path.join(ROOT, "gulf_eda", "scripts"))
from eda_util import heat_index_f
sys.path.insert(0, os.path.join(ROOT, "texas_heatwave_pilot", "scripts"))
from heatwave_run_logic import build_runs_and_events

PILOT = os.path.join(ROOT, "texas_heatwave_pilot")
TAB = os.path.join(PILOT, "tables")
EV = os.path.join(TAB, "events")
HI_COL = "derived_tmax_rhmin_hi_proxy_f"

ANCHORS = {  # county_fips -> (station_id, county_name)
    "48201": ("USW00012960", "Harris (Houston)"),
    "48141": ("USW00023044", "El Paso"),
    "48303": ("USW00023042", "Lubbock"),
    "48453": ("USW00013958", "Travis (Austin)"),
    "48061": ("USW00012919", "Cameron (Brownsville)"),
}
ANCHOR_IDS = {v[0] for v in ANCHORS.values()}
STATION_TO_FIPS = {v[0]: k for k, v in ANCHORS.items()}

WINDOW, PCTL, AN0, AN1, BASE_START, MIN_DUR, HI_FLOOR = 15, 85, 2015, 2025, 1979, 2, 80
_tpl = pd.date_range("2000-01-01", "2000-12-31")
MD_TO_TDOY = {(d.month, d.day): i + 1 for i, d in enumerate(_tpl)}
TDOY_TO_MD = {v: k for k, v in MD_TO_TDOY.items()}
N_TDOY = 366


def log(*a):
    print(*a, flush=True)


log("=" * 70)
log("R3 Issue 8: anchor-station vs county-composite sensitivity")
log("=" * 70)

# ---- 1. pull anchor TMAX/TMIN from the raw station-day file (chunked filter) ----
log("[1] extracting anchor-station TMAX/TMIN from raw station-day file (chunked)...")
path = os.path.join(ROOT, "data", "raw", "gulf_states", "TX", "weather", "ghcn_station_day_TX.csv")
keep = []
t0 = time.time()
for chunk in pd.read_csv(path, dtype={"station_id": str}, chunksize=1_000_000):
    c = chunk[chunk["station_id"].isin(ANCHOR_IDS) & chunk["element"].isin(["TMAX", "TMIN"])]
    if len(c):
        keep.append(c)
raw = pd.concat(keep, ignore_index=True)
log("    pulled %d anchor station-element rows in %.1fs" % (len(raw), time.time() - t0))
raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
wide = raw.pivot_table(index=["station_id", "date"], columns="element", values="value", aggfunc="first").reset_index()
wide["county_fips"] = wide["station_id"].map(STATION_TO_FIPS)
wide = wide.rename(columns={"TMAX": "tmax_anchor_f", "TMIN": "tmin_anchor_f"})
wide["year"] = wide["date"].dt.year
wide = wide[(wide["year"] >= BASE_START) & (wide["year"] <= AN1)]

# ---- 2. attach gridMET RHmin (same humidity source as composite) ----
log("[2] pairing with gridMET RHmin + computing anchor HI proxy...")
h = pd.read_csv(os.path.join(ROOT, "data", "raw", "gulf_states", "TX", "weather",
                              "gridmet_county_day_humidity_TX.csv"),
                usecols=["county_fips", "date", "rmin_pct"], dtype={"county_fips": str})
h["county_fips"] = h["county_fips"].str.zfill(5)
h["date"] = pd.to_datetime(h["date"], errors="coerce")
a = wide.merge(h, on=["county_fips", "date"], how="left").dropna(subset=["tmax_anchor_f", "rmin_pct"])
a[HI_COL] = heat_index_f(a["tmax_anchor_f"], a["rmin_pct"])
a["month"] = a["date"].dt.month
a["day"] = a["date"].dt.day
a["template_doy"] = a.apply(lambda r: MD_TO_TDOY[(int(r["month"]), int(r["day"]))], axis=1)
a["county_name"] = a["county_fips"].map(lambda f: ANCHORS[f][1])

# ---- 3. walk-forward day-of-year thresholds for the anchor series ----
log("[3] anchor walk-forward day-of-year thresholds...")
def build_wf_thresholds(df):
    rows = []
    for fips in df["county_fips"].unique():
        full = df[df["county_fips"] == fips][["year", "template_doy", HI_COL]]
        for y in range(AN0, AN1 + 1):
            base = full[full["year"] <= y - 1]
            lo = base.assign(td=base["template_doy"] - N_TDOY)
            mid = base.assign(td=base["template_doy"])
            hi = base.assign(td=base["template_doy"] + N_TDOY)
            trip = pd.concat([lo, mid, hi]).sort_values("td")
            tarr, harr = trip["td"].values, trip[HI_COL].values
            for target in range(1, N_TDOY + 1):
                i0 = np.searchsorted(tarr, target - WINDOW, "left")
                i1 = np.searchsorted(tarr, target + WINDOW, "right")
                w = harr[i0:i1]
                m, d = TDOY_TO_MD[target]
                rows.append((fips, m, d, y, np.percentile(w, PCTL) if w.size else np.nan))
    return pd.DataFrame(rows, columns=["county_fips", "calendar_month", "calendar_day", "analysis_year", "thr"])

thr = build_wf_thresholds(a)

# ---- 4. classify anchor analysis period (retain-all) ----
log("[4] classifying anchor 2015-2025 (retain-all)...")
an = a[(a["year"] >= AN0) & (a["year"] <= AN1)].merge(
    thr, left_on=["county_fips", "month", "day", "year"],
    right_on=["county_fips", "calendar_month", "calendar_day", "analysis_year"], how="left")
an["candidate_day_flag"] = np.where(an[HI_COL].isna() | an["thr"].isna(), np.nan,
                                    (((an[HI_COL] > an["thr"]) & (an[HI_COL] >= HI_FLOOR)).astype(float)))
parts = []
for fips, g in an.groupby("county_fips"):
    g = g.sort_values("date").set_index("date")
    gf = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))
    gf["county_fips"] = fips
    gf = gf.reset_index().rename(columns={"index": "date"})
    parts.append(build_runs_and_events(gf, min_duration=MIN_DUR, year_boundary_breaks_run=False,
                                       definition_id="HI85_2D_ANCHOR", state_fips="48"))
anchor = pd.concat(parts, ignore_index=True)
anchor["year"] = anchor["date"].dt.year
anchor["month"] = anchor["date"].dt.month
anchor[["county_fips", "county_name", "date", "year", "month", "tmax_anchor_f", HI_COL,
        "thr", "candidate_day_flag", "heatwave_day_flag", "event_id"]].to_csv(
    os.path.join(EV, "07_daily_ANCHOR_yearround_retainall.csv"), index=False)

# ---- 5. compare vs composite retain-all ----
log("[5] comparing anchor vs composite (retain-all both sides)...")
comp = pd.read_csv(os.path.join(EV, "07_daily_sensitivity_yearround_retainall.csv"), dtype={"county_fips": str})
comp["date"] = pd.to_datetime(comp["date"])
m = comp[["county_fips", "county_name", "date", "year", "tmax_f", "heatwave_day_flag", "candidate_day_flag"]].rename(
        columns={"tmax_f": "tmax_comp", "heatwave_day_flag": "hw_comp", "candidate_day_flag": "cand_comp"}).merge(
    anchor[["county_fips", "date", "tmax_anchor_f", "heatwave_day_flag", "candidate_day_flag"]].rename(
        columns={"heatwave_day_flag": "hw_anch", "candidate_day_flag": "cand_anch"}),
    on=["county_fips", "date"], how="inner")
for c in ["hw_comp", "hw_anch"]:
    m[c] = m[c].fillna(0).astype(int)

rows = []
for fips, g in m.groupby("county_fips"):
    name = ANCHORS[fips][1]
    def jac(x, y):
        i = int(((g[x] == 1) & (g[y] == 1)).sum()); u = int(((g[x] == 1) | (g[y] == 1)).sum())
        return round(i / u, 4) if u else np.nan
    by_year = g.groupby("year").agg(comp=("hw_comp", "sum"), anch=("hw_anch", "sum")).reset_index()
    slope = lambda s: round(float(np.polyfit(by_year["year"], by_year[s], 1)[0]), 3)
    rows.append({
        "county_fips": fips, "county_name": name, "anchor_station": ANCHORS[fips][0],
        "mean_tmax_bias_anchor_minus_comp": round((g["tmax_anchor_f"] - g["tmax_comp"]).mean(), 3),
        "hw_days_composite": int(g["hw_comp"].sum()), "hw_days_anchor": int(g["hw_anch"].sum()),
        "heatwave_day_jaccard": jac("hw_comp", "hw_anch"),
        "candidate_day_jaccard": jac("cand_comp", "cand_anch"),
        "trend_slope_composite": slope("comp"), "trend_slope_anchor": slope("anch"),
    })
res = pd.DataFrame(rows)
res["hw_days_diff_anchor_minus_comp"] = res["hw_days_anchor"] - res["hw_days_composite"]
res.to_csv(os.path.join(TAB, "12b_anchor_vs_composite_comparison.csv"), index=False)
log("\n" + res.to_string(index=False))

with open(os.path.join(TAB, "12b_anchor_vs_composite_summary.md"), "w", encoding="utf-8") as f:
    f.write("# Anchor-station vs county-composite temperature sensitivity (R3 Issue 8)\n\n")
    f.write("Same definition, humidity, thresholds, and run logic; ONLY the county\n")
    f.write("temperature source differs: single full-span airport anchor vs the\n")
    f.write("changing multi-station composite. Both retain-all.\n\n")
    f.write("- Mean Tmax bias (anchor - composite), by county: %s\n"
            % ", ".join("%s %+.2fF" % (r.county_name.split()[0], r.mean_tmax_bias_anchor_minus_comp) for r in res.itertuples()))
    f.write("- Heatwave-day Jaccard(composite, anchor): %s\n"
            % ", ".join("%s %.3f" % (r.county_name.split()[0], r.heatwave_day_jaccard) for r in res.itertuples()))
    f.write("- Total heatwave-days composite=%d anchor=%d (%+d)\n"
            % (res["hw_days_composite"].sum(), res["hw_days_anchor"].sum(),
               res["hw_days_anchor"].sum() - res["hw_days_composite"].sum()))
    f.write("\nIf anchor and composite disagree materially (low Jaccard or large Tmax\n")
    f.write("bias), the composite series carries station-composition signal that must\n")
    f.write("be controlled before interpreting trends or the walk-forward-vs-fixed gap.\n")
    f.write("Detail: `12b_anchor_vs_composite_comparison.csv`.\n")
log("\n[done] wrote 12b_anchor_vs_composite_comparison.csv + summary.md")
