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
  config.py               the ONE place to change: states, percentiles, years, windows, paths
  heat_index.py           NWS Rothfusz heat index (bundled; no external dependency)
  heatwave_run_logic.py   shared run/event construction (also used by the unit tests)
  p01_build_countyday_idw.py   county-day table + IDW temperature gap-fill  (per state)
  p02_classify_and_report.py   thresholds + classification + event/county-month/county-year tables
  p03_nws_proxy.py             NWS advisory-threshold proxy  (needs nws_offices_<ST>.csv)
  p04_figures.py               choropleth maps + distributions
  run_all.py                   runs p01→p04 for everything in config.py
  nws_offices_TX.csv           per-state NWS office table (editable)

outputs/      results, per state and per definition (produced by the pipeline)
  TX/county_daily_heat.csv                 (large; git-ignored)
  TX/coverage_and_imputation_report.csv
  TX/nws_office_crosswalk.csv , nws_proxy_county_year.csv
  TX/def_p85_2d/  and  def_p95_2d/         Definition 01 (85th) and Definition 02 (95th)
      tables/    thresholds, heatwave_events, county_month_summary, county_year_summary, QA
      figures/   choropleth maps, seasonal, event-duration, distribution (both threshold windows)
      FINDINGS_DEF02.md   (Def 02 write-up)

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
python run_all.py
```
Runs, for every state × percentile in `config.py`: `p01` county-day + IDW → `p03` NWS
proxy → `p02` classification + reporting tables → `p04` figures.

## Definitions

`PERCENTILES = [85]` → **Definition 01**; `[95]` → **Definition 02**; `[85, 95]` → both.
Only the percentile changes; all other logic is shared. Each definition is computed on
**both** threshold windows (centered 15-day and calendar-month).

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
