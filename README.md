# Texas Heatwave Classification Pilot

A reproducible, county-level heatwave-classification pipeline for 5 Texas pilot
counties (Harris, El Paso, Lubbock, Travis, Cameron), built against a configurable
methodological specification. Descriptive **exposure classification** only — no
injury-outcome or worker-heat-dose claims.

## Layout

```
scripts/         core pipeline (step01..step07) + shared run/event logic
tests/           mandated unit tests for the run/event algorithm
tables/          configuration, thresholds, classifications, county-year summaries,
                 quality_control/ audits, definition registry, comparison outputs
  events/        per-scenario daily + event tables
def01_relMeanHI_p85_2d/   Definition 01 under examination (see its FINDINGS_DEF01.md)
```

## Pipeline (run in order, from the repo root's parent project)

Python: `"C:/Program Files/Python314/python.exe"` (pandas 3.0.3, numpy 2.4.6).

1. `scripts/step01_validate_and_build_county_day.py` — validate + build county-day table
2. `scripts/step02_build_dayofyear_thresholds.py` — walk-forward day-of-year thresholds
3. `scripts/step03_classify_and_build_events.py` — candidate/run/event classification (all scenarios)
4. `scripts/step04_county_year_summary.py` — county-year summaries
5. `scripts/step05_weather_value_factcheck.py` — weather-value QC / artifact audit
6. `scripts/step06_fixed_baseline_comparison.py` — fixed 1979-2014 vs walk-forward
7. `scripts/step07_anchor_station_sensitivity.py` — single-anchor vs composite temperature
8. `tests/test_run_logic.py` — unit tests (must pass)

### Definition 01
`def01_relMeanHI_p85_2d/scripts/`: `build_def01.py` → `report_def01.py` → `figures_def01.py`.

## Data dependency

Raw weather inputs live OUTSIDE this repo, under the parent project's
`data/raw/gulf_states/TX/weather/` (NOAA GHCN-Daily temperature + gridMET humidity).
Large regenerable daily tables are git-ignored; rebuild them by running the scripts.

## Key methodology notes

- **Heat-index proxy**, daily (not hourly-concurrent); Tmax and RH have different
  spatial support — treat as a county apparent-heat proxy, not an observed maximum.
- **Walk-forward** baseline (year Y ← 1979…Y−1) is primary; fixed 1979-2014 built
  for comparison (`tables/11_*`).
- County temperature is a **changing multi-station composite**; the anchor-station
  sensitivity (`tables/12b_*`) shows the temperature source can materially change
  classification — resolve before statewide rollout.
- Full methods / change history in `tables/12_methodology_log.md`.
