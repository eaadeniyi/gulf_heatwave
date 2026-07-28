# Statewide extension — Definition 01 across all 254 Texas counties

**Definition (unchanged from the pilot):** a county-relative **85th-percentile
daily-MEAN heat index**, sustained **≥ 2 consecutive days**, **walk-forward** baseline,
study period **2015–2025**. Now applied to **all 254 Texas counties** (the pilot's 5).
Two threshold windows reported alongside: **`w15`** = centered 15-day-total (±7);
**`month`** = calendar-month bucket. No absolute floor in the primary (faithful to the
definition); confirmed RH-clip artifacts set to missing.

Terminology and record structure are identical to the pilot: **heatwave day**
(county-date in a ≥2-day run), **heatwave event** (one uninterrupted run in one county),
integer **event duration**; county-level records are substantive, cross-county pooled
totals are QA-only.

## Coverage & IDW gap-filling (per your instruction)

All 254 counties are present in the source files, but temperature coverage is uneven:
**93 counties are fully native** (0% imputed), while **22 counties have no native station
data at all** in 2015–2025 and **45 counties are >50% imputed**. Missing temperature
county-days were filled by **inverse-distance-weighted (IDW) interpolation** from
surrounding counties — county **centroids** (EPSG:5070), weight = 1/distance², all
counties with data that day contributing (distant ones ≈ 0). Overall **12.8% of
temperature county-days were IDW-imputed**; gridMET humidity was already gap-free.

**Every imputed county-day is flagged** (`temp_imputed`) and carried through to the
event tables (`n_imputed_days`, `event_contains_imputed_day`) and county-year summaries
(`heatwave_days_imputed`). `fig_map03_pct_days_imputed_per_county` maps exactly which
counties rest on interpolation — read the results for dark-purple counties as
interpolated, not observed.

## Results (county-level; pooled totals are QA-only)

- **Per-county heatwave days, 2015–2025 (w15):** median **677**, range **154–1,230**.
- QA-only statewide pooled totals: **w15 ≈ 48,300 events / 170,900 heatwave-days**;
  **month ≈ 47,500 / 171,100** — the two windows agree closely per county
  (`fig_cmp01_w15_vs_month_scatter`).
- Maps: `fig_map01` (heatwave days/county), `fig_map02` (events/county),
  `fig_map05` (per-year small multiples, shared scale).

## IMPORTANT caveat — spatial noise is partly a data artifact, not climate

Some **adjacent counties differ implausibly** (e.g. La Salle 1,230 vs its neighbour
Zavala 154 heatwave-days). This is **not** real micro-climate: it is the same issue the
pilot's anchor-station sensitivity exposed — county temperature is a **changing
multi-station composite**, now compounded by **IDW imputation** in low-coverage counties.
So the county-to-county *texture* of these maps is unreliable; the broad regional gradient
is more trustworthy than any single county, and heavily-imputed counties (`fig_map03`)
should be treated with caution. Resolving this (anchor-station or homogenized composite
temperature) remains the top prerequisite before injury linkage or firm county rankings.

## NWS advisory-threshold PROXY (statewide, separate sensitivity)

county → NWS forecast office assigned by **nearest office** (approximate crosswalk — no
authoritative CWA shapefile locally; editable in `nws_office_crosswalk.csv`). Per-office
advisory / extreme-warning heat-index thresholds: **HGX (108/113) and BRO (111/115)
documented; FWD/EPZ near-documented; the other ~8 offices flagged approximate**
(defaulting to Southern-Region 105/110, or 108/113 for humid coastal/eastern offices).
Daily **max-HI** proxy, artifacts excluded. **PROXY only** — not official advisories (no
hourly HI, no duration / overnight-minimum / spatial-coverage rules).
Map: `fig_map04_nws_advisory_threshold_days`. As in the pilot, arid far-west counties
(EPZ office) record very few absolute-threshold days despite having relative-anomaly
heatwave days — the relative-vs-absolute contrast at statewide scale.

## Files

`tables/`: `statewide_county_daily_heat.csv` (git-ignored, large),
`coverage_and_imputation_report.csv`, per-window `thresholds_*`, `heatwave_events_*`,
`county_year_summary_*`, `county_month_summary_*` (git-ignored), `daily_heatwave_days_*`
(git-ignored), `state_year_qc_*`, plus `nws_office_crosswalk.csv`,
`nws_proxy_county_year.csv`, `nws_proxy_daily.csv` (git-ignored).
`figures/`: 4 choropleth maps + per-year small-multiple map + distribution + window scatter.
`scripts/`: `sw1_build_countyday_idw.py` → `sw2_classify_and_report.py` →
`sw3_nws_proxy_statewide.py` → `sw4_figures_statewide.py`.

## Carried-forward caveats

Daily proxy (not hourly-concurrent); Tmax/RH different spatial support; **changing
multi-station composite temperature + IDW imputation** (above); NWS crosswalk & most
office thresholds approximate; year-round relative construct = "persistent apparent-heat
anomaly" (the ~half of flagged days that are sub-80°F cool-season anomalies persist at
statewide scale — the `mean-HI≥80°F` floor sensitivity from the pilot applies here too).
