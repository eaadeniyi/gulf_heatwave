# Heatwave classification pipeline (state-agnostic)

A reproducible, **state-general** pipeline that classifies county-level **heatwave
days** and **heatwave events** from daily weather, using a county-relative
percentile of a daily heat-index proxy plus a consecutive-day persistence rule on
a walk-forward climate baseline. Developed on Texas but **not locked to Texas** —
the state, percentile, study period, and windows are all set in `config.py`.

> Descriptive **exposure classification** only. No injury-outcome, worker-heat-dose,
> or official-NWS-advisory claims. The heat index is a **daily proxy** (not hourly
> concurrent), and county temperature is a multi-station composite (+ IDW imputation
> where stations are missing) — see caveats in each definition's FINDINGS.

## What a "definition" is

```
Definition = county-relative <PERCENTILE>th-percentile daily-MEAN heat index,
             sustained >= MIN_DURATION consecutive days, walk-forward baseline.
```
`PERCENTILES = [85]` → Definition 01; `[95]` → Definition 02; `[85, 95]` → both.
Only the percentile changes between definitions; all other logic is shared.

## Run it

```bash
python run_all.py
```
Runs, for every state × percentile in `config.py`:
`p01` build county-day table + IDW gap-fill → `p03` NWS proxy → `p02` classify +
reporting tables → `p04` choropleth figures. (Or run `p01`–`p04` individually.)

## Run it for a DIFFERENT state

1. Ensure the state's daily inputs exist in the expected layout (see `config.py`,
   `WEATHER_FILE_TEMPLATE`): GHCN county-day temperature + gridMET county-day
   humidity under `data/raw/gulf_states/<ST>/weather/`. In this project those exist
   for the 5 Gulf states (TX, LA, MS, AL, FL); other states need their inputs
   downloaded into the same layout first.
2. In `config.py` set e.g. `STATES = ["LA"]`.
3. (Optional) add a per-state NWS office table `nws_offices_<ST>.csv` (same columns
   as `nws_offices_TX.csv`). Without it, the NWS-proxy step is skipped for that
   state; the relative-definition steps still run.
4. `python run_all.py`

Everything state-specific is a parameter: the 2-digit FIPS (from `config.STATE_FIPS`),
file paths (templated), county centroids/geometry (filtered from the national
shapefile by FIPS), and the NWS office table. No code edits are needed to switch state.

## Files

| File | Role |
|---|---|
| `config.py` | the ONE place to change: states, percentiles, years, windows, paths |
| `heatwave_run_logic.py` | shared run/event construction (also used by unit tests) |
| `p01_build_countyday_idw.py` | county-day table + IDW temperature gap-fill (per state) |
| `p02_classify_and_report.py` | thresholds + classification + event/county-month/county-year tables (per state × percentile) |
| `p03_nws_proxy.py` | NWS advisory-threshold proxy (per state; needs `nws_offices_<ST>.csv`) |
| `p04_figures.py` | choropleth maps + distributions (per state × percentile) |
| `run_all.py` | runs the four steps in order for everything in `config.py` |
| `nws_offices_TX.csv` | per-state NWS office locations + thresholds (editable) |

## Outputs

```
outputs/<ST>/county_daily_heat.csv            (per state; large; git-ignored)
outputs/<ST>/coverage_and_imputation_report.csv
outputs/<ST>/nws_office_crosswalk.csv , nws_proxy_county_year.csv
outputs/<ST>/def_p<PCTL>_<DUR>d/tables/       (thresholds, events, county-month, county-year, QA)
outputs/<ST>/def_p<PCTL>_<DUR>d/figures/      (choropleth maps, distribution)
```

## Terminology (used consistently)

- **heatwave day** — one county on one date inside a qualifying ≥`MIN_DURATION`-day run.
- **heatwave event** — one uninterrupted run of heatwave days within one county.
- **event duration** — integer consecutive calendar dates (end − start + 1).
- Cross-county pooled totals are **QA-only**, never the headline.
