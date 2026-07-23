# Definition 01 — relative 85th-percentile daily-mean heat index, ≥2 consecutive days (walk-forward)

**Definition under examination:** a county-relative **85th-percentile daily-MEAN heat
index**, sustained **≥ 2 consecutive days**, using the **walk-forward baseline** method.
Study period **2015–2025**; **5 Texas pilot counties**.

## Terminology (used consistently in every table, figure, and statement)

- **Heatwave day** — one county on one date inside a qualifying ≥2-day run (a county-date record).
- **Heatwave event** — one uninterrupted run of heatwave days within one county (its own record).
- **Event duration** — the integer number of consecutive calendar dates (end − start + 1).
- Cross-county / cross-year **pooled totals are QA-only** and are never the headline.
  A pooled **average** duration is not reported as a primary statistic.
- Construct label: this is a year-round relative measure, i.e. a **persistent apparent-heat
  anomaly** ("heatwave" is used as the colloquial term for the ≥2-day run).

## Method

- **Metric:** daily-mean heat-index proxy = `heat_index(Tmean, mean RH)`, Tmean=(Tmax+Tmin)/2,
  mean RH=(RHmax+RHmin)/2. A daily *proxy* (not hourly-concurrent); temperature (GHCN stations)
  and humidity (gridMET grid-mean) have different spatial support.
- **Two threshold windows, reported alongside each other** (both walk-forward, year Y ← 1979…Y−1,
  85th percentile):
  - **`w15`** — centered **15-day-total** window (target day ± 7 days). ~513–690 reference obs/threshold.
  - **`month`** — **calendar-month** bucket (85th pctl of all days in that calendar month). ~1,016–1,426 obs.
- **Candidate day:** daily-mean HI **>** its own walk-forward threshold (strict `>`).
- **Heatwave day:** candidate inside a run of **≥ 2 consecutive calendar days**.
- **PRIMARY has no absolute floor** (faithful to the definition as written). Confirmed
  RH-clip artifacts (2023-03-01) set to missing. A `mean-HI ≥ 80°F` floor is a QA sensitivity.

## Temperatures and thresholds are now in the tables

Every **heatwave-day** record (`daily_heatwave_days_<W>.csv`) carries Tmax, Tmin, Tmean,
RHmax, RHmin, mean RH, the daily-mean HI proxy, its **county-day threshold**, and the
**exceedance** (proxy − threshold). Every **event** record (`heatwave_events_<W>.csv`)
carries the peak-day date and that day's Tmax/Tmin/Tmean/RHmax/RHmin/**threshold**, plus
event max-Tmax, mean-Tmean, peak and cumulative exceedance.

## Results — reported at the county level (not pooled)

Interpretable, non-pooled examples (centered 15-day window unless noted):

- **Harris County, 2021:** 21 heatwave events; 78 heatwave days; durations
  2,2,2,2,2,2,3,3,3,3,3,4,4,4,4,4,4,4,6,8,10; **longest event 10 days**.
- **Cameron County, 2023:** the single **longest events** in the pilot are here — a run of
  ~20 consecutive days in Jul 2023 and ~19 days in Jun 2023 (see `heatwave_events_w15.csv`).

Each is a **real calendar run**, never an average. No event "lasted 4.3 days."

### QA-only pooled totals (pipeline sanity, NOT the headline)

| Window | PRIMARY heatwave days | events | +floor≥80°F days | events |
|---|---:|---:|---:|---:|
| `w15` (centered 15-day) | 3,703 | 1,013 | 1,833 | 468 |
| `month` (calendar month) | 3,755 | 1,019 | 1,908 | 479 |

Per-county QA totals are close between windows (e.g. Harris `w15` 880 days/223 events vs
`month` 892/224; Cameron `w15` 1,006/243 vs `month` 979/231) — the ±7 and month windows
give similar counts, since both draw on a comparable stretch of the annual cycle.

## The two key caveats (flagged, not silently resolved)

1. **Floor sensitivity.** A `mean-HI ≥ 80°F` floor roughly **halves** the count (3,703 → 1,833
   for `w15`), because a relative-only daily-mean definition flags many **cool-season anomaly
   days** — unusually warm *for that date* but not absolutely hot (visible as Nov–Apr shading
   in the per-year `fig04` panels). Keep no-floor (per the definition) or add the floor
   depending on whether the downstream question is "anomalous for this county/date" vs
   "conventionally hot."
2. **Window choice** (`w15` vs `month`) changes counts only modestly here; both reported.

## NWS advisory-threshold PROXY (separate sensitivity)

A **different question** — "did apparent heat reach a level comparable to the *local* NWS
office's advisory / extreme-warning criteria?" — using the daily **max**-HI proxy and each
county's forecast-office thresholds (`nws_office_thresholds.csv`; current term
**Extreme Heat Warning**, per 2025-03-04 NWS change). **PROXY only** — daily proxy, not
hourly-concurrent, and it cannot reproduce office duration / overnight-minimum / spatial-
coverage rules.

| County | Office | Advisory / Extreme HI (°F) | Advisory-threshold days (2015–25) | Warning-threshold days | Status |
|---|---|---|---:|---:|---|
| Harris (Houston) | HGX | 108 / 113 | 172 | 10 | documented |
| Cameron (Brownsville) | BRO | 111 / 115 | 56 | 5 | documented |
| Travis (Austin) | EWX | 105 / 110 | 54 | 0 | approximate — verify |
| El Paso | EPZ | 105 / 110 | 1 | 0 | SR standard |
| Lubbock | LUB | 105 / 110 | 1 | 0 | approximate — verify |

This crisply shows the **relative-vs-absolute tension**: arid El Paso and Lubbock have
essentially **no** NWS-threshold days (their max HI rarely reaches 105°F) yet plenty of
*relative* heatwave days — they are "unusually warm for themselves" without being
absolutely hot. EWX and LUB thresholds are flagged approximate and are trivially editable
in `nws_office_thresholds.csv`.

## Figures (`figures/`)

Per window (`w15`, `month`): `fig01_*` annual heatwave days by county; `fig02_*` annual
events by county; `fig03_*` event-duration **distribution** (count of real events by exact
duration — no averages); `fig04_*_county_month_heatmap_by_year` — **11 per-year panels,
NOT merged, shared color scale**; `fig05_*` walk-forward threshold by time of year.
Cross-cutting: `fig06_event_timeline_cameron_w15` (Gantt of individual events);
`fig07_window_comparison_annual_days` (w15 vs month); `fig08_nws_proxy_threshold_days`.

## Tables (`tables/`)

Per window: `thresholds_<W>.csv`, `daily_heatwave_days_<W>.csv` (heatwave days only, with
temps+threshold), `daily_classification_<W>.csv` (all analysis days), `heatwave_events_<W>.csv`,
`county_month_summary_<W>.csv`, `county_year_summary_<W>.csv`. Plus
`nws_office_thresholds.csv`, `nws_proxy_daily.csv`, `nws_proxy_county_year.csv`, and
`sensitivity_scenarios_qc_totals.csv` (QA-only).

County-month fields: county_fips, county_name, year, month, **heatwave_events_started**,
**heatwave_events_active**, **heatwave_days**, **longest_event_duration_days**,
**event_ids_started**, **event_ids_active** (month-crossing events counted once at onset,
active in every month touched, days allocated to their actual month).
County-year fields: county_fips, county_name, year, **heatwave_events_started** (onset-year),
**heatwave_days**, **first_event_start_date**, **last_event_end_date**,
**longest_event_duration_days**, event_durations, event_ids.

## Validation

All 6 mandated run/event unit tests pass (`../tests/test_run_logic.py`; the run/event logic
is metric- and window-agnostic).

## Carried-forward caveats

Daily proxy (not hourly-concurrent); Tmax and RH have different spatial support; county
temperature is a **changing multi-station composite** — the anchor-station sensitivity
(`../tables/12b_*`) showed the temperature source can change classification materially. These
apply to this definition too and remain open before any statewide / injury-linkage use.
