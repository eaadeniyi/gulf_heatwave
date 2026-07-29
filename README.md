# Heatwave classification pipeline (state-agnostic)

A reproducible, **state-general** pipeline that classifies county-level **heatwave
days** and **heatwave events** from daily weather, using a county-relative percentile
of a daily heat-index proxy plus a consecutive-day persistence rule on a walk-forward
climate baseline. Developed on Texas but **not locked to Texas** — the state,
percentile, study period, and windows are all set in `pipeline/config.py`.

> Descriptive **exposure classification** only. No injury-outcome, worker-heat-dose, or
> official-NWS-advisory claims. The heat index is a **daily proxy** (not hourly
> concurrent); county temperature is a multi-station composite with IDW gap-filling
> where stations are missing — so single-county values are noisy but the regional
> gradient is robust.

## Repository layout

```
pipeline/     the pipeline — config-driven, self-contained, state-agnostic
  config.py               the ONE place to change: states, metrics, percentiles, durations,
                          windows, the definition grid, years, paths
  definition_registry.csv THE RUN LIST — regenerated from config.py on every run and
                          iterated by run_grid.py, so it cannot drift from what ran
  heat_index.py           NWS Rothfusz heat index (bundled; no external dependency)
  heatwave_run_logic.py   shared run/event construction: a readable reference implementation
                          (the test oracle) + a vectorised panel version for the grid
  p01_build_countyday_idw.py   county-day table + IDW temperature gap-fill  (per state)
  p02_classify_and_report.py   thresholds + classification + event/county-month/county-year
                               tables, for any metric × percentile × duration × window
  p03_nws_proxy.py             NWS advisory-threshold proxy  (needs nws_offices_<ST>.csv)
  p04_figures.py               choropleth maps, distributions, seasonality, window sensitivity
  p05_definition_comparison.py cross-definition layer: Jaccard agreement, marginal effects,
                               county-rank stability, seasonality
  run_grid.py                  runs the DEFINITION GRID (+ registry, resume, provenance log)
  run_all.py                   legacy single-definition path (Def 01 / Def 02)
  nws_offices_TX.csv           per-state NWS office table (editable)

outputs/      results, per state and per definition (produced by the pipeline)
  TX/county_daily_heat.csv                 (large; git-ignored)
  TX/coverage_and_imputation_report.csv
  TX/nws_office_crosswalk.csv , nws_proxy_county_year.csv
  TX/def_p85_2d/  and  def_p95_2d/         Definition 01 (85th) and Definition 02 (95th)
      tables/    thresholds, heatwave_events, county_month_summary, county_year_summary, QA
      figures/   choropleth maps, seasonal, event-duration, distribution (both threshold windows)
      FINDINGS_DEF02.md   (Def 02 write-up)
  TX/grid/                                 the definition grid (Def 03–Def 16)
      <DEFINITION_ID>/tables|figures/      one folder per definition, window in each filename
      _thresholds/                         shared threshold cache (git-ignored, regenerable)
      _state_figures/                      definition-independent figures, rendered once
      _comparison/                         master tables + cross-definition figures
      run_log.csv                          append-only provenance (git commit, input hash)

reference/    presentation-ready deliverables + archived prior analysis
  REFERENCE_glossary_methods_results.md    glossary / data dictionary / methods
  RESULTS_PRESENTATION.md                  per-definition results + likely-questions
  Heatwave_Reference_Appendix.pptx         appendix deck
  Heatwave_Results_Deck.pptx               results deck (figures embedded)
  build_*.py                               scripts that build the docs/figures/decks
  archive_prior_analysis/                  earlier records kept for provenance (see below)

tests/        unit tests for the run/event logic (python tests/test_run_logic.py)
```

## Run it

```bash
cd pipeline
python run_grid.py            # the definition grid: 14 definitions × 4 windows = 56 runs
python p04_figures.py         # the full figure set for every run
python p05_definition_comparison.py   # the cross-definition comparison layer
```

`run_grid.py` supports filtering and resuming — `--metric tmax`, `--percentile 90`,
`--duration 3`, `--window w15`, `--def-number 7`, `--force`, `--registry-only`.
Runs already on disk are skipped unless `--force` is given.

The legacy single-definition path is still one command:

```bash
python run_all.py             # p01 → p03 → p02 → p04 for config.PERCENTILES (Def 01 / Def 02)
```

## Definitions

A **definition** is `METRIC × PERCENTILE × MIN_DURATION`; a **run** is a definition at one
threshold window. Held fixed across the whole grid: county-relative percentile, strict `>`,
walk-forward baseline (year Y judged against 1979…Y-1), year-round season, no absolute
floor. So any difference between two runs is attributable to metric, percentile, duration
or window — and nothing else.

| axis | values | id fragment |
| --- | --- | --- |
| metric | daily max temperature, daily min temperature, daily-mean heat index | `TMAX` / `TMIN` / `MHI` |
| percentile | 85th, 90th, 95th | `P85` / `P90` / `P95` |
| min duration | 2 or 3 consecutive days | `2D` / `3D` |
| threshold window | centered ±2 days; centered ±7 days; calendar month; calendar month ±7 days | `w05` / `w15` / `month` / `month_pm7` |

Run ids read `TMAX_P90_2D__w15`. The published **Definition 01** = `MHI_P85_2D` and
**Definition 02** = `MHI_P95_2D`; the grid adds **Def 03–Def 16**. Every specification,
status, output path and runtime lives in `pipeline/definition_registry.csv`.

`w15` pools the 15 days centred on the target date; `month_pm7` pools the whole calendar
month **plus a 7-day collar either side** (~45 days) — they are different windows, not two
names for the same thing.

### Regression gate

`p02` was generalised from one metric to any metric. `tests/test_reproduce_def01_def02.py`
re-runs Def 01 and Def 02 through the generalised code and asserts it still reproduces the
published outputs exactly — every county-year, the complete event set, and the documented
headline totals (170,894 / 48,323 and 52,786 / 17,428). Run it after touching `p02`.

## Run it for a different state

1. Put the state's daily inputs in the layout in `config.py` (`WEATHER_FILE_TEMPLATE`):
   GHCN county-day temperature + gridMET county-day humidity. (In this project those
   exist for the 5 Gulf states TX/LA/MS/AL/FL; other states need inputs downloaded.)
2. Set `STATES = ["LA"]` (etc.) in `config.py`.
3. Optionally add `nws_offices_<ST>.csv` for the NWS-proxy step.
4. `python run_all.py`. Nothing else is state-specific — FIPS, paths, geometry, and the
   office table are all parameters.

## `reference/archive_prior_analysis/`

Records from the earlier exploratory pilot and review rounds, kept for provenance
(superseded by the current `pipeline/` + `outputs/` but not reproduced there):
the methodology/change log, the fixed-baseline-vs-walk-forward and anchor-station-vs-
composite sensitivity findings, station provenance, the March-2023 gridMET-artifact
verification, QC audits, and the two earlier FINDINGS write-ups.

## Terminology

- **heatwave day** — one county on one date inside a qualifying ≥2-day run.
- **heatwave event** — one uninterrupted run of heatwave days within one county.
- **event duration** — integer consecutive calendar dates (end − start + 1).
- Cross-county pooled totals are **QA-only**, never the headline.
