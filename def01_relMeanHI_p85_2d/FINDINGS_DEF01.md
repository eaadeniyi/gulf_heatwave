# Definition 01 — relative 85th-percentile daily-mean heat index, ≥2 consecutive days (walk-forward)

**Definition under examination (as specified):** a county-relative **85th-percentile
daily-MEAN heat index**, sustained **≥ 2 consecutive days**, using the **walk-forward
baseline** method. Study period **2015–2025**; **5 Texas pilot counties**.

## Method (consistent with how this pilot has been built)

- **Metric:** daily-mean heat-index proxy = `heat_index(Tmean, mean RH)`, where
  Tmean = (Tmax+Tmin)/2 and mean RH = (RHmax+RHmin)/2. This is the daily-**mean**
  proxy — distinct from the daily-**max** (Tmax+RHmin) proxy used in the earlier
  pilot primary. Still a *proxy*: components are daily, not concurrent hourly, and
  temperature (GHCN stations) and humidity (gridMET grid-mean) have different
  spatial support.
- **Threshold:** county-specific, **day-of-year ±15-day** centered window, 85th
  percentile, **walk-forward** (analysis year Y drawn from 1979 … Y−1). 20,130
  thresholds built; reference sample 1,088–1,426 obs each.
- **Candidate day:** daily-mean HI **>** its own walk-forward threshold (strict `>`).
- **Heatwave day:** a candidate day inside a run of **≥2 consecutive calendar days**.
- **Heatwave event:** one uninterrupted run within one county (its own record).
- **PRIMARY has NO absolute floor** — faithful to the definition as written. The
  `mean-HI ≥ 80°F` floor and a retain-all-artifacts variant are reported as
  sensitivities.
- **Artifacts:** the 3 confirmed RH-clip artifacts (2023-03-01) are set to missing
  in the primary (established data-quality practice from prior review).

## Terminology (per the reporting convention)

- **heatwave day** = one county on one date inside a qualifying run (county-date record).
- **heatwave event** = one uninterrupted run within one county.
- **event duration** = integer count of consecutive calendar dates.
- Pooled cross-county/-year totals are **QA-only**, never the headline.

## Results — reported at the county level (not pooled)

Full records live in the tables; a few **interpretable, non-pooled** examples:

- **Harris County, 2021:** 20 heatwave events; 73 heatwave days; durations
  2,2,2,2,2,3,3,3,3,3,3,4,4,4,4,4,4,5,8,9; **longest event 9 days**.
- **Harris County, 2023:** 22 heatwave events; 119 heatwave days; **longest 16 days**.
- **Cameron County, 2023:** 18 heatwave events; 129 heatwave days; **longest 20 days**
  (2023-07-08 → 2023-07-27).
- **Longest single events in the dataset:** Cameron 2023-07-08→07-27 (20 days),
  Cameron 2023-06-10→06-28 (19 days), Harris 2016-07-02→07-18 (17 days).

Each of those is a **real calendar run** — not a pooled average. No event "lasted
4.32 days."

### QA-only pooled totals (for pipeline sanity, NOT substantive headline)

| Scenario | heatwave days | heatwave events |
|---|---:|---:|
| PRIMARY (no floor, artifacts missing) | 3,448 | 955 |
| sensitivity: retain-all artifacts | 3,455 | 956 |
| sensitivity: mean-HI ≥ 80°F floor | 1,783 | 455 |

Per-county PRIMARY totals (2015–2025): Cameron 969 days/236 events; Harris 835/209;
Lubbock 645/210; El Paso 580/172; Travis 419/128.

## The floor sensitivity is the key methodological caveat

Adding a `mean-HI ≥ 80°F` absolute floor **roughly halves** the count (3,448 → 1,783
heatwave days). That is because a relative-only daily-mean definition flags many
**cool-season anomaly days** — days that are unusually warm *for that date* but not
hot in absolute terms (visible as the substantial Nov–Apr shading in
`fig04_county_month_heatmap`). Whether those belong in a "heatwave" analysis depends
on the downstream question:

- **No floor (primary here):** captures "unusually warm for this county and time of
  year," year-round — a *persistent apparent-heat anomaly* construct.
- **With ≥80°F floor:** restricts to anomalies that are also absolutely warm — closer
  to a conventional heatwave.

This is flagged for your decision; the definition as written implies no floor, so
that is the primary.

## Figures (`figures/`)

1. `fig01_annual_heatwave_days_by_county` — heatwave days per year, per county.
2. `fig02_annual_events_by_county` — heatwave events per year (onset-year), per county.
3. `fig03_event_duration_distribution` — count of real events by exact duration.
4. `fig04_county_month_heatmap` — heatwave days by county × month (2015–2025).
5. `fig05_threshold_by_dayofyear` — the walk-forward 85th-pctl threshold's annual cycle.
6. `fig06_event_timeline_cameron` — Gantt of individual Cameron events by year.

## Tables (`tables/`)

- `thresholds_walkforward_meanHI_doy.csv` — every county/day-of-year/analysis-year threshold.
- `daily_heatwave_classification.csv` — one row per county-date (PRIMARY).
- `heatwave_events.csv` — one row per event (label, county, start, end, duration, intensity).
- `county_month_summary.csv` — events started / active / heatwave days / longest, per county-month
  (month-crossing events counted once at onset; days allocated to their actual month).
- `county_year_summary.csv` — events (onset-year) / heatwave days / first–last span / longest.
- `sensitivity_scenarios_qc_totals.csv` — QA-only pooled totals for the 3 scenarios.

## Validation

All 6 mandated run/event unit tests pass (`../tests/test_run_logic.py`; the run/event
logic is metric-agnostic, so the tests validate this definition too).

## Caveats carried forward (unchanged by this definition)

- Proxy is daily, not hourly-concurrent; Tmax and RH have different spatial support.
- County temperature is a changing multi-station composite — the anchor-station
  sensitivity (`../tables/12b_*`) showed the temperature source can change classification
  materially; that caveat applies here too.
- Year-round relative construct is formally a "persistent apparent-heat anomaly"; the
  term "heatwave" is used per the definition's framing.
