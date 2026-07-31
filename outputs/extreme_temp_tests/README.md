# Extreme-temperature tests

Three requested pieces of work, kept in their own package so the delivered 16-definition comparison in `outputs/definition_comparison/` is untouched.

**Read `FINDINGS.md` first.**

| part | what | scope | outputs |
|---|---|---|---|
| 1 | Gulf-state temperature description: annual, by state, decadal, monthly | TX, LA, MS, AL, FL; 1979-2025; observed GHCN record | `figures/e01_*`, `tables/e01_*` |
| 2 | county-relative daily MAX temperature, 80th/85th/90th percentile x >=2/>=3/>=5 consecutive days | TX, 2015-2025, 4 threshold windows (36 runs) | `figures/e03_fig05*`, `e03_fig06`, `tables/e03_part2_*` |
| 3a | the same 9 definitions with an absolute floor as a GATE (80 / 90 degF) | TX, 2015-2025, primary window (18 runs) | `figures/e03_fig07`, `e03_fig09`, `tables/e03_floor_effect.csv` |
| 3b | absolute-only definitions, Tmax > 80 / 90 degF | TX, 2015-2025, no window axis (6 runs) | `figures/e03_fig08`, `tables/e03_absolute_vs_relative.csv` |

## Headline

| question | answer |
|---|---|
| Has the Gulf warmed? | yes, and Tmin faster than Tmax in all 5 states (TX +2.71 vs +2.04 degF since the 1980s) |
| Where in the year? | the COOL season: December +6.2 degF in TX, July +0.4 |
| Does any percentile/duration choice fix the cool-season loading? | no - 49-63% of heatwave days fall outside Jun-Sep in all 9 cells |
| Does an 80 degF floor fix it? | no - cool-season share only falls to 40-54% |
| Does a 90 degF floor fix it? | largely yes - 20-30%, at the cost of about half the classified days |
| Is an absolute floor alone a heatwave definition? | not at 80 degF - it flags 51% of ALL days in Texas |
| Do absolute and relative rules pick the same days? | no - Jaccard 0.08-0.28 |

## Verification

Four Part-2 cells (`TMAX_P85_2D`, `TMAX_P85_3D`, `TMAX_P90_2D`, `TMAX_P90_3D`) already exist in the delivered definition grid. This package rebuilds them and reconciles against the published run summaries: **32/32 checks pass**, so the new cells are directly comparable with the earlier work. See `qa/e02_reconciliation.csv`.

## Rebuild

```bash
cd outputs/extreme_temp_tests/scripts
python e01_state_temperature_eda.py     # part 1  (~1 min)
python e02_run_extreme_definitions.py   # parts 2-3 classification (~5 min)
python e03_tables_and_figures.py        # tables + figures (~1 min)
python e04_report.py                    # FINDINGS.md + README.md
```

Provenance: git `475e4fa+dirty`, classification input `md5:f0276ee5888539f9`, python 3.14.3 / pandas 3.0.3.
