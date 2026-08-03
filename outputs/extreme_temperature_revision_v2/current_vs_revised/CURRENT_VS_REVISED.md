# Current package against revised package

The original package at `outputs/extreme_temp_tests/` is unmodified. Its outputs were re-executed into `current_vs_revised/reproduction/` and reproduce bit-for-bit before any comparison was made.

## Period difference, 1980-1989 to 2020-2025, average daily high temperature

| state | current (pooled) | current counties | revised Sample A | Sample A 95% interval | Sample A counties | revised Sample B | Sample B counties |
|---|---|---|---|---|---|---|---|
| Texas | 2.04 | 195 | 1.94 | 1.53 to 2.48 | 140 | 2.27 | 148 |
| Louisiana | 1.75 | 37 | 2.08 | 1.79 to 2.64 | 26 | 2.20 | 23 |
| Mississippi | 2.35 | 43 | 1.86 | 1.22 to 3.60 | 25 | 2.11 | 23 |
| Alabama | 1.38 | 44 | 1.62 | 0.94 to 2.64 | 28 | 1.17 | 35 |
| Florida | 1.17 | 49 | 1.53 | 0.55 to 2.12 | 37 | 1.30 | 36 |

## County sample

| state | current 'balanced panel' | Sample A: consistent-county | Sample B: strict balanced |
|---|---|---|---|
| Texas | 195 | 140 | 148 |
| Louisiana | 37 | 26 | 23 |
| Mississippi | 43 | 25 | 23 |
| Alabama | 44 | 28 | 35 |
| Florida | 49 | 37 | 36 |

## Classification results

| quantity | current package | revised package |
|---|---|---|
| headline quantity for a definition | statewide pooled event total, and a per-county median of an 11-year cumulative count | median ANNUAL county-level event count and classified-day count, with the full distribution |
| seasonality | two categories: inside and outside June-September | three categories: June-September 37-51%, May and October 18-21%, November-April 28-45% across the nine relative definitions |
| monthly rate denominator | one shared denominator reused from another package for all three families | family-specific valid-record counts, tested for equality and documented |
| 'the monthly rate is nearly flat' | asserted with no criterion | criterion defined (highest/lowest month at most 1.5 and coefficient of variation at most 0.15); 0 of 33 constructs meet it, so the curves are NOT described as flat |
| geography of a relative rule | 'flags a similar number of days everywhere by construction' | measured: cumulative classified days for REL_TX_P90_D3_W15 range 59 to 747 across counties, a factor of 12.7 |
| the 90 degF value | 'floor', implicitly a correction | absolute daily-high gate; changes the construct to a hybrid relative-and-absolute definition; retains 58% of classified days and moves the June-September share from 43% to 74% |
| long events | not examined | 43,392 events longer than 15 days audited and classified; the longest is 243 days |

## Figure crosswalk

| current figure | revised figure | what changed |
|---|---|---|
| e01_fig02_distribution_by_state.png | r_fig_E2_distribution_by_state.png + r_fig_E2b_one_value_per_county.png | retitled; the three conflated sources of variation stated; an equal-county alternative added |
| e01_fig03_decadal_change.png | r_fig_E3_period_comparison.png | equal-county aggregation; bootstrap intervals; county counts; both samples; trend language removed; 2020-2025 labelled a six-year recent period |
| e01_fig04_monthly.png | r_fig_E4_monthly_level_and_difference.png | equal-county period difference; identical warm-season shading in both rows (the current figure shades different months in each); level and difference stated as different quantities |
| e03_fig05_part2_percentile_duration_grid.png | r_fig_E5_percentile_duration_grid.png | pooled event total replaced by the median annual county-level event count; season split three ways; 'heatwave days' renamed |
| e03_fig05b_part2_agreement.png | r_fig_E5b_agreement_jaccard.png | full labels; agreement-not-accuracy and structural-nesting stated |
| e03_fig06_part2_seasonality.png | r_fig_E6_monthly_classification_rate.png | construct-specific denominator; flatness criterion defined and evaluated; reader-facing unit language |
| e03_fig07_floor_effect.png | r_fig_E7_absolute_gate_effect.png | 'floor' renamed absolute daily-high gate; three-way season split; county geography of retention added; annual county-level change replaces pooled totals |
| e03_fig08_absolute_vs_relative.png | r_fig_E8_absolute_vs_relative.png | annual county-level distributions replace study-period medians; the share of all valid records classified added |
| e03_fig09_county_floor_effect_map.png | r_fig_E9_county_geography_all_counties.png + r_fig_E9_county_geography_excluding_fully_imputed.png | caption claim withdrawn and the spread measured; data-quality panel added; fully imputed counties hatched; a version excluding them added |
| (none) | r_fig_R1 to r_fig_R10 | current-versus-revised, sample comparison, benchmark, trend sensitivity, imputation sensitivity, event timeline, long-event audit, annual distributions, family rates, county profiles |
