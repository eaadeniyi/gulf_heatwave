# Texas Heatwave Classification Pilot — Methodology Log

Generated 2026-07-16, **revised same day after an external methodological
review**. Scoped to 5 Texas counties, 2015–2025 analysis period, as a
standalone test of the approach before any wider rollout. **New and separate**
from the existing `gulf_eda/` 5-state work — nothing there was modified.

## 1. Input sources

- **Temperature**: NOAA GHCN-Daily, daily Tmax/Tmin, aggregated to county-day
  upstream by `scripts/U_download_gulf_weather.py` (nearest-station /
  point-in-polygon assignment — see §3).
- **Humidity**: gridMET/METDATA, daily RHmax/RHmin, aggregated to county-day
  upstream by `scripts/V_download_gulf_gridmet.py` (unweighted mean of 4 km
  grid-cell centroids inside the county polygon — see §3).
- **No hourly and no dewpoint data exist** in this project — the largest gap
  vs. the literal specification (Part C Steps 5–8 skipped).

## 2. Processing decisions

1. Heat-index formula: corrected `heat_index_f()` (full NWS Rothfusz +
   low/high-humidity adjustments, verified against wpc.ncep.noaa.gov).
2. Primary metric: **`derived_tmax_rhmin_hi_proxy_f`** — Tmax paired with
   same-day RHmin. A **proxy**, not a validated county daily-maximum HI (§3,
   Issue 1).
3. Thresholds: county-**calendar-day**, centered ±15-day (31-day) window,
   leap-safe via a fixed 366-day (month,day) template; Feb 29 handled as its
   own target (no interpolation).
4. Reference period: **walk-forward** (year Y ← 1979 … Y−1) is primary. The
   fixed **1979–2014** baseline HAS been built and compared head-to-head
   (thresholds `06b`, full output family `07/08/09_*FIXED7914`, comparison
   `11_*`). The fixed **1981–2010** baseline remains not-yet-run (deferred by
   user). [Single current-state statement — supersedes any earlier draft note
   that called both fixed baselines deferred.]
5. Candidate = relative exceedance (strict `>`) **AND** an absolute floor;
   components stored separately.
6. Runs/events per spec Step 14 (`heatwave_run_logic.py`, shared with the unit
   tests). Missing calendar days are explicit reindexed rows and break runs.
7. Min duration 2 days; spec-format event IDs; onset/continuation/final flags
   verified against the spec's worked example.

## 3. Corrections applied after external review (2026-07-16)

**Issue 1 — proxy naming + withdrawn "validated" claim.** Renamed
`derived_max_hi_f` → `derived_tmax_rhmin_hi_proxy_f` everywhere. The earlier
"already validated" description of the Tmax–RHmin convention is **withdrawn**;
it is an assumed approximation. The two components are not observed
concurrently and have different spatial supports (GHCN station-based
temperature; gridMET grid-mean humidity). Suggested manuscript sentence:
"Daily peak apparent heat was approximated by combining county-assigned daily
maximum temperature with county-aggregated daily minimum relative humidity;
the components were not observed concurrently and have different spatial
supports."

**Issue 2 — three-level QC + scenario reruns.** `qc_status` ∈
{valid, suspicious_retain, invalid_missing}, now propagated into
`county_daily_quality_flag`. Event tables carry
`event_contains_suspicious_day`, `n_suspicious_days`, `peak_day_qc_status`.
The flagged file is renamed `02_suspicious_meteorological_values.csv`
(implausible, not "invalid"). Events are built under four scenarios so the
influence is quantified:
- retain-all, year-round, HI-floor — **PRIMARY** (789 events, 3,018 hw-days)
- suspicious→missing — 788 events, 3,011 hw-days
- warm-season Jun–Sep — 327 events, 1,413 hw-days
- Tmax-floor sensitivity — 816 events, 3,093 hw-days

Impact of the 6 suspicious heatwave-days (all around 2023‑02‑28 → 03‑02):
Cameron's Feb 20–Mar 2 event **survives but its peak HI drops 118.6 → 91.2 °F**
when the two suspicious days are removed; Harris behaves the same; **Travis's
3-day event dissolves entirely** (all 3 days were flagged) — so that event's
existence depends on suspect data.

**Issue 3 — completeness reporting fixed.** The old numerator used a bitwise
`&` on two counts and the denominator was mislabeled 1979–2025 while data run
to 2026. Now reported per period with correct joint-valid numerators: full raw
source 17,354 days/county (99.97–99.99%), fixed 1979–2014 13,149 days (100%
except Lubbock 99.97%), analysis 2015–2025 4,018 days (100%).

**Issue 4 — season framing.** Under the year-round design only **46.9%** of
heatwave-days fall in Jun–Sep and **66.2%** in May–Oct; the first-to-last-event
span averages 248 days (max 361). Year-round events are therefore relabeled
**"persistent apparent-heat anomalies,"** and a warm-season (Jun–Sep) companion
is produced side by side (`09_county_year_summary_{yearround,warmseason}.csv`).
Choice of which is primary is deferred to the user.

**Issue 5 — dual 80 °F floor.** The floor was applied to the derived HI but
mislabeled `minimum_valid_temperature_f`. Now two explicit flags:
`floor_hi_ge_80` (apparent-heat floor, PRIMARY) and `domain_tmax_ge_80`
(formula-domain, SENSITIVITY). The Tmax-floor admits 111 more candidate days,
concentrated in arid El Paso/Lubbock (the 114 days with hot air but sub-80 °F
apparent heat the review identified). Both event sets produced; choice deferred.

**Issue 6 — baselines.** Review recommends running walk-forward + fixed
1979–2014 + fixed 1981–2010 as separate definitions before interpretation.
**Fixed 1979–2014 is now built and compared** (see §4b / `11_*` /
`10_definition_registry.csv` row COMPLETED). Fixed 1981–2010 remains the only
deferred baseline.

**Issue 7 — source time conventions.** Documented in
`quality_control/04_source_time_conventions.md`: GHCN uses each station's
**local observation day** (unhomogenized, subject to observation-time bias,
carries flag `L`); gridMET rmax/rmin use a fixed ~24 h window ending ~1200 UTC
(with an unresolved 0700-vs-1200-UTC doc discrepancy). **The two daily windows
may not coincide**, which compounds the Issue 1 non-concurrency caveat.

## 4. Still-open items (flagged in `01_configuration.yaml`, not decided here)

- Primary season framing (year-round vs. warm-season).
- Primary absolute floor (apparent-heat HI≥80 vs. formula-domain Tmax≥80).
- Whether to build the two deferred fixed baselines.
- `>` vs `>=` exceedance operator (pilot uses spec-literal `>`; existing
  `gulf_eda` uses `>=`).
- Analysis period (assumed 2015–2025).
- The county-aggregation order (HI computed after county-mean T/RH, not before)
  and method (not land-area-weighted) — inherited from upstream extraction, not
  rebuilt this pass; a genuine deviation from spec Step 8.
- gridMET 0700-vs-1200-UTC day-definition discrepancy.

## 4b. Second-review corrections (2026-07-16, "R2")

**R2 Issue 1 (BLOCKING) — warm-season denominator.** The warm-season summary
previously divided Jun–Sep heatwave-days by full-year valid days. Fixed:
warm-season prevalence now uses the in-season (122-day) valid denominator.
Every county-year row now reports `valid_days_full_year`,
`valid_days_in_analysis_season_junsep`, and two labeled percentages
(`pct_annual_days_classified`, `pct_inseason_days_classified`) plus a
`pct_valid_days_heatwave_PRIMARY` whose basis is stamped per row. Verified:
Cameron 2015 = 14/122 = **11.48%** in-season (was mis-reported 3.84%).

**R2 Issue 3 — full output family per scenario.** All four scenarios (primary +
suspicious-missing + warm-season + Tmax-floor) now emit a daily classification
(`events/07_daily_*.csv`), an event table (`events/08_events_*.csv`), and a
county-year summary (`09_county_year_summary_*.csv`).

**R2 Issue 4/12C — peak dates.** Event tables now carry `peak_hi_date` and
`peak_exceedance_date` (they differ in ~7% of events).

**R2 Issue 6 — QC split.** `qc_status` now has four levels: valid /
suspicious_retain / **missing_input** / **invalid_physical** (previously
`invalid_missing` conflated missing source data with physically-impossible
values). Current counts: 86,709 valid, 50 suspicious, 11 missing_input, 0
invalid_physical.

**R2 Issue 6/12E — schema.** Event tables add `n_days_hi_ge_95f` /
`n_days_tmax_ge_95f`; flags/counts/durations cast to nullable-integer dtypes.

**R2 Issue 9 — fixed-baseline comparison (was the major missing component).**
Built fixed 1979–2014 day-of-year thresholds (identical windowing/definition,
only the reference pool differs) and compared head-to-head with walk-forward:
- Day-level Jaccard = **0.923** (the two largely agree on which days).
- Fixed flags **3,213** heatwave-days vs walk-forward **3,018** (+195) — the
  expanding baseline suppresses later-year counts as its threshold rises.
- County ranking **identical** under both baselines.
- Trend slopes are systematically **shallower under walk-forward** (e.g. Cameron
  3.4 vs 5.4 days/yr) — it absorbs part of the recent warming signal, exactly
  the review's concern. Outputs: `11_walkforward_vs_fixed_comparison.csv` /
  `_summary.md`. The 1981–2010 fixed baseline remains not-yet-run.

**R2 Issue 12A — definition metadata.** thresholds (06), daily classifications
(07), county-year summaries (09), and event tables (08) all now carry
definition_id / construct_label / metric / reference_method / season /
floor_variable / floor_value / minimum_duration / comparison_operator.

**R2 Issues 10/13 — config staleness.** `time_reference` updated to
`source_specific_non_equivalent_daily_windows`; `excluded_season_day_breaks_run`
set true (active for the warm-season scenario); year-boundary and `>`-vs-`>=`
decisions documented as pre-expansion choices.

**Suspicious-day effect, stated precisely (R2):** setting the 50 suspicious
county-days to missing changes the classification by **7 event-days and 1
event** — 6 directly-suspicious heatwave-days removed, plus 1 previously-valid
day that loses two-day persistence when its adjacent suspicious neighbor is
removed. Severity impact is concentrated: Cameron's Feb 2023 event peak proxy
HI drops 118.6→91.2 °F; Travis's 3-day event dissolves entirely.

**Tmax-floor sensitivity is off-season only (R2 Issue 8):** the +75 net
event-days under the Tmax≥80 floor occur entirely Nov–Mar (arid El Paso,
Lubbock, Travis); **zero** difference in Jun–Sep. So the floor choice matters
for the year-round anomaly construct but not for warm-season heatwaves.

## 4c. Third-review workflow: investigations + verification (2026-07-16)

Two reviewer-requested investigations were run as subagents; five adversarial
verification subagents hit a session usage limit and did not run, so their
checks were **re-executed inline by the main agent instead** (all passed —
see below). Do not read the failed-subagent slots as skipped verification.

**Station provenance** (`quality_control/05_station_provenance.{csv,md}`).
County temperature is an **unweighted mean of a time-varying station set**
(point-in-polygon assignment, nearest-centroid fallback), not a single fixed
station. Of 689 stations assigned to the 5 counties, only 31 ever report
TMAX/TMIN (the rest are US1 precip-only volunteers). Every county keeps a
full-span USW airport anchor (Harris has 2: Hobby + IAH), so a single-anchor
sensitivity is feasible. **No time-of-observation metadata and no GHCN `L`
(lagged) flag survive on disk** — the build discards MFLAG/QFLAG/SFLAG/obstime;
L-flagged values were kept unmarked. Station-replacement discontinuity risk is
highest in Travis (feed grows 1→~6) and El Paso (thins 4-5→2 around 2009-13).

**March-2023 anomaly source verification**
(`quality_control/06_march2023_anomaly_verification.md`). **CONFIRMED DATA
ARTIFACT.** 2023-03-01 (Cameron, Harris, Travis) has gridMET RH pinned at
exactly 100.000000 (both bounds) while independent GHCN shows **zero precip**,
station RH only ~80%, and dewpoints of 68-72°F under 84-88°F highs — full-day
saturation is physically impossible. It is the **single most widespread pin
date in the entire 47-year, 254-county record (118/254 counties, 46%)** — the
signature of a product-level clip, not weather. The false RH=100 inflates the
HI proxy by **+15 to +24°F** (Cameron 118.6 vs true ~94; Harris 109 vs 89;
Travis 102 vs 87). By contrast 2017-01-14 is a **genuine** cold-wet saturation
(real precip, Tmax<80°F, affects no heat metric). Record-wide, 66.6% of
zero-range pins fall on wet days (real), 22.8% on dry days (artifact).

**Acted on the finding (PRCP-aware QC refinement).** step01 now sub-classifies
every RH=100 pin using GHCN precipitation (an independent source) as
`qc_rh_pin_likely_artifact` (pinned + PRCP≈0 + Tmax≥80) vs
`qc_rh_pin_likely_real_wet` (pinned + PRCP≥0.01in). In the 5 pilot counties: 3
likely-artifact, 19 likely-real-wet, of 31 total pins. The 3 artifacts are
**exactly** the 2023-03-01 Cameron/Harris/Travis event days that inflated the
proxy — so the cross-check cleanly isolates the HI-distorting days from
legitimate wet-day saturation. This is diagnostic only: qc_status /
classification are unchanged (primary still 789 events / 3,018 days); the
suspicious-set-missing sensitivity already quantifies the impact of removing
them. Recommended pre-rollout: cap/impute rmin from dewpoint on
likely-artifact days rather than trusting the clipped 100%.

**Inline adversarial verification (5 checks, all CONFIRMED):**
warm-season denominator (Cameron 2015 = 11.48% = 14/122); fixed-vs-walkforward
Jaccard independently = 0.9226, totals 3,018 vs 3,213, ranking identical; QC
4-level counts 86,709/50/11/0 with the 11 missing_input carrying no hard flag;
suspicious→missing effect = 7 days / 1 event; event arithmetic (Σ durations =
3,018, IDs unique, dates consecutive, peak/cumulative/peak-date spot-checks) and
metadata coverage all correct.

## 4d. Third-review (R3) corrections (2026-07-16)

**R3 Issue 2 (BLOCKING) — year-round in-season %.** The `pct_inseason_days_classified`
field divided a full-year heatwave-day numerator by the 122-day Jun-Sep
denominator, producing values >100% (Cameron 2017 = 122.13%). Fixed: summaries
now carry `heatwave_days_full_year`, `heatwave_days_in_junsep`,
`valid_days_full_year`, `valid_days_in_junsep`, and two correctly-matched
percentages (`pct_full_year_days_classified`, `pct_junsep_days_classified`).
A global assertion enforces no percentage >100% in any scenario. Cameron 2017
now = 50.0% Jun-Sep, 2023 = 78.69%.

**R3 Issue 3 — confirmed artifacts removed from PRIMARY.** The 3 confirmed
2023-03-01 RH-clip artifacts are now set to MISSING in the PRIMARY definition
(`HI85_2D`), so the missing-day run rule handles them. PRIMARY = **788 events /
3,011 heatwave-days** (was 789/3,018). The former retain-all definition is
preserved as an explicit sensitivity (`HI85_2D_RETAINALL`).

**R3 Issue 4 — row-level artifact provenance.** `02_suspicious_meteorological_values.csv`
now carries `rh_pin_class` (confirmed_artifact / likely_real_wet /
indeterminate), `verification_basis`, and `recommended_action` per row. Of 31
pins: 3 confirmed_artifact, 19 likely_real_wet, 9 indeterminate (cold-dry or
precip-missing; flagged manual_review, not auto-dropped).

**R3 Issue 5/6 — fixed baseline completed + registry/log reconciled.** Fixed
1979-2014 now emits the full output family (`07_daily` / `08_events` /
`09_county_year_summary` for HI85_2D_FIXED7914) with fully self-describing
`06b` threshold metadata. Registry row updated to COMPLETED. The earlier
methodology-log statement that both fixed baselines were deferred has been
corrected to a single current-state statement (1979-2014 built; only 1981-2010
deferred). Walk-forward-vs-fixed comparison unchanged (Jaccard 0.9226; 3,018 vs
3,213; El Paso -6 exception now explicitly noted; trend-slope claims stated
with restraint).

**R3 Issue 8 — anchor-station vs composite sensitivity (MAJOR FINDING).**
Rebuilt each county's temperature from a single full-span airport anchor
(IAH, El Paso Intl, Lubbock AP, Camp Mabry, Brownsville AP), same humidity,
same definition. **The temperature source changes classification far more than
the baseline choice does:** heatwave-day Jaccard(composite, anchor) = 0.45-0.73
(vs 0.92 for walk-forward-vs-fixed), and heatwave-day counts swing sharply
(Travis 424 -> 807, El Paso 354 -> 577, Harris 808 -> 606; mean Tmax bias up to
+1.55F). Trend slopes are NOT robust to the source (Cameron 3.4 -> 10.4 d/yr).
**Consequence:** the county-composite series carries substantial station-
composition signal; the walk-forward-vs-fixed trend gap CANNOT be interpreted
as a pure climate/baseline effect until station composition is controlled
(anchor-only or homogenized composite). This must be resolved before statewide
rollout or injury linkage. Detail: `12b_anchor_vs_composite_comparison.csv`.

**R3 Issue 11 — stale term.** Input-validation report footer updated from the
retired `invalid_missing` to the 4-level scheme (invalid_physical / missing_input
/ suspicious_retain / valid).

**R3 canonical file.** `07_county_daily_classification.csv` (top-level) is the
single canonical PRIMARY daily table; `events/07_daily_PRIMARY_*` is a
byte-identical per-scenario copy for the uniform scenario loop.

**Deferred (noted, not done this pass):** the R3 Issue 10 methodology/changelog/
audit three-file split (the substantive contradiction it flagged IS fixed; the
remaining item is document reorganization). Fixed 1981-2010 baseline. Hourly
proxy validation (no hourly/dewpoint data exists). Actual station-timing error
(metadata discarded upstream). Imputation-based artifact correction (set-missing
chosen instead).

## 5. Software versions
Python 3.14.3, pandas 3.0.3, numpy 2.4.6 (Windows).

## 6. Test results
All 6 spec-mandated sequences + 2 pilot-specific tests: **8/8 pass**
(`tests/test_run_logic.py`), run against the exact function used on real data.

## 7. Claim discipline (spec Part M)
Results describe **county-level environmental apparent-heat classifications**
under a prespecified relative + persistence definition. No claim of individual
worker heat dose, no causal injury claim, no "objectively correct" heatwave
definition. This pilot does not touch injury data.
