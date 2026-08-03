# Extreme-temperature analysis, revision v2

_Gulf-state temperature description and Texas extreme-temperature classification, audited and revised._

Generated 2026-08-01 | git `550d9e5+dirty` | python 3.14.3, pandas 3.0.3, numpy 2.4.6

---

## 1  Purpose

To audit the delivered extreme-temperature package, correct the aggregation and terminology defects it contains, and reissue every affected table, figure, caption and finding in a form an advisor can review and a later analyst can link to occupational-injury data. The original package is untouched; this is a parallel, versioned revision.

## 2  Research question

Descriptively: what does the daily temperature record look like across the five Gulf states over 1979-2025, how has it differed between prespecified periods, and how sensitive is a county-level heat-event classification to the choice of definition, threshold, duration, absolute gate, county sample and data quality?

## 3  Epistemic level

**Descriptive.** The analysis may describe temperature distributions, period differences, classification sensitivity, event frequency, event timing, geographic patterns and agreement among definitions. It does **not** establish causal climate trends, occupational-injury effects, individual worker exposure, the objectively correct heatwave definition, or equivalence with National Weather Service advisories.

## 4  Data sources

| source | extent | used by |
|---|---|---|
| raw GHCN county-day records, five Gulf states | 1979-2025, observed only, no gap-filling | Part 1: figures E2, E2b, E3, E4, R1, R2, R4 |
| gap-filled county-day table, Texas | 2015-2025, inverse-distance gap-filled | Parts 2 and 3: figures E5 to E9, R5 to R10 |
| archived walk-forward threshold cache | 3 percentiles x 4 windows, read with float_precision='round_trip' | reproduction of the classification step |
| county coverage and imputation report, Texas | per county | every county-level data-quality indicator |
| county polygons (US Census) | 2020 TIGER/Line | figure E9 |

The analysis uses a county-by-day panel in which each record represents one county on one calendar date.

## 5  Current computation, as it stands

Every aggregation performed by the current package was read off its code and catalogued in `qa/02_existing_aggregation_inventory.csv` (22 entries), with the data lineage of every figure in `qa/02b_existing_figure_lineage.csv`. The current scripts were then re-executed with their outputs redirected to `current_vs_revised/reproduction/`, and **all 25 regenerated tables and figures reproduce bit-for-bit** (`qa/01_existing_pipeline_reproduction.csv`). The classification step was reproduced separately by an independent rebuild from the archived threshold cache: **120 of 120 exact set-equality checks on classified county-dates and event boundaries pass**.

The audit therefore rests on numbers that were reproduced before they were criticised.

## 6  Identified weaknesses

| package_step | quantity | issue | severity |
|---|---|---|---|
| e01 | 'balanced panel' membership | NOT balanced. One qualifying year in the 1980s and ten in the 2010s satisfies the rule, so the number of annual observations a county contributes still varies by period and by county | BLOCKING |
| e01 | state x period temperature level and change | counties with more qualifying years receive more weight; the state estimate is not a median across counties despite the docstring saying 'MEDIANS across qualifying counties' | BLOCKING |
| e01 | state x month level, and state x month period difference | same pooling defect as the annual case, and the county sample is selected on annual coverage while the statistic is monthly | BLOCKING |
| e01 | figure E2 distribution | title states a level; the object shown mixes between-county variation, year-to-year variation and long-term change. Counties with more reporting years get more visual weight | high |
| e01 | figure E3 / E4 change panels | a two-period difference described with trend language; no time-trend model is estimated anywhere in the package | high |
| e02 | run summary statistics | a cumulative 11-year total per county reported without saying so; fully imputed counties are included with no data-quality marker | high |
| e03 | monthly classification rate | the SAME denominator is applied to relative, hybrid and absolute-only constructs. An absolute rule needs no historical threshold, so its valid-record set is not the same set | BLOCKING |
| e03 | figure E5 panel B | a statewide pooled total used as a substantive panel of the main grid figure | high |
| e03 | figure E5 panel D | merges the shoulder months (May, October) with November-April into one category, which hides where the classifications actually fall | high |
| e03 | figure E8 panel A | a study-period cumulative total presented without the annual distribution behind it | high |
| e03 | figure E9 caption | not true by construction. Persistence, temporal dependence, warming relative to the walk-forward baseline, missingness, imputation and station composition all vary between counties | BLOCKING |
| e04 | written claims | every headline number inherits the pooled aggregation and the mis-specified panel; 'heatwave' is used for year-round relative constructs with no absolute condition | BLOCKING |

Three further defects were found that the current package does not record at all:

1. **18 raw county-dates have a daily high below the same day's daily low.** On 13 of them the county high and the county low were averaged over different numbers of stations, so the pair is not internally consistent. The current package never checks this. Handling is declared in `r00_config.INVERTED_RECORD_ACTION`; the records are preserved in `qa/quarantined_inverted_daily_records.csv`. None falls in the Texas classification window.
2. **The archived threshold cache does not survive a default CSV round trip.** 99,405 of 3,067,812 stored threshold values are misparsed by the pandas default float parser - `94.38799999999999` reads back as `94.388` - and with the project's strict `>` comparison that one bit flips the classification of county-dates sitting exactly on their threshold. Any downstream reuse of that cache must pass `float_precision='round_trip'`, or the thresholds should be archived in a binary format. See `qa/float_roundtrip_defect.csv`.
3. **There is no external benchmark in this repository.** The only second temperature product is byte-identical to the project data on all 2,938,070 matched daily records, despite its build script documenting a different county assignment. See section 9.

## 7  Revisions performed

| area | what changed |
|---|---|
| aggregation | state period summaries rebuilt as daily -> annual county value -> one value per county per period -> median across counties, with a county bootstrap interval |
| county sample | the mis-named 'balanced panel' replaced by Sample A (consistent-county) and Sample B (strict balanced), both prespecified and both reported |
| trend language | period differences relabelled as differences; Sen and least-squares slopes estimated separately under four county samples |
| terminology | plain-language variable labels; Tavg defined explicitly; TGm retired; reader-facing unit language throughout |
| construct naming | three families with explicit identifiers and reader names; year-round relative constructs are no longer called heatwaves |
| denominators | computed per construct family and tested for equality rather than shared by assumption |
| seasonality | three categories; the shoulder months are no longer merged into the cool season |
| event layer | full individual event catalogues with peak, exceedance, observed and gap-filled day counts and a review status |
| audits | long-event audit, six-way data-quality sensitivity, county profiles, palette validation |
| QA | a blocking test suite of 104 checks covering daily logic, coverage, period weighting, event logic, gate logic, denominators and output consistency |

## 8  Current versus revised, numerically

### Period difference, 1980-1989 to 2020-2025, average daily high temperature

| state | current (pooled) | current counties | revised Sample A | Sample A 95% interval | Sample A counties | revised Sample B | Sample B counties |
|---|---|---|---|---|---|---|---|
| Texas | 2.04 | 195 | 1.94 | 1.53 to 2.48 | 140 | 2.27 | 148 |
| Louisiana | 1.75 | 37 | 2.08 | 1.79 to 2.64 | 26 | 2.20 | 23 |
| Mississippi | 2.35 | 43 | 1.86 | 1.22 to 3.60 | 25 | 2.11 | 23 |
| Alabama | 1.38 | 44 | 1.62 | 0.94 to 2.64 | 28 | 1.17 | 35 |
| Florida | 1.17 | 49 | 1.53 | 0.55 to 2.12 | 37 | 1.30 | 36 |

The revised point estimates move by up to 1.10 degF. More consequential than the movement is what the current package never showed: the bootstrap interval across counties is 0.85 to 2.53 degF wide, so several of the state-to-state orderings asserted in the current findings are not supported by the data behind them.

### County sample

The current 'balanced panel' required only one qualifying year per period. Enforcing a real minimum removes a large share of it:

| state | current 'balanced panel' | Sample A: consistent-county | Sample B: strict balanced |
|---|---|---|---|
| Texas | 195 | 140 | 148 |
| Louisiana | 37 | 26 | 23 |
| Mississippi | 43 | 25 | 23 |
| Alabama | 44 | 28 | 35 |
| Florida | 49 | 37 | 36 |

### Classification results

| quantity | current package | revised package |
|---|---|---|
| headline quantity for a definition | statewide pooled event total, and a per-county median of an 11-year cumulative count | median ANNUAL county-level event count and classified-day count, with the full distribution |
| seasonality | two categories: inside and outside June-September | three categories: June-September 37-51%, May and October 18-21%, November-April 28-45% across the nine relative definitions |
| monthly rate denominator | one shared denominator reused from another package for all three families | family-specific valid-record counts, tested for equality and documented |
| 'the monthly rate is nearly flat' | asserted with no criterion | criterion defined (highest/lowest month at most 1.5 and coefficient of variation at most 0.15); 0 of 33 constructs meet it, so the curves are NOT described as flat |
| geography of a relative rule | 'flags a similar number of days everywhere by construction' | measured: cumulative classified days for REL_TX_P90_D3_W15 range 59 to 747 across counties, a factor of 12.7 |
| the 90 degF value | 'floor', implicitly a correction | absolute daily-high gate; changes the construct to a hybrid relative-and-absolute definition; retains 58% of classified days and moves the June-September share from 43% to 74% |
| long events | not examined | 43,392 events longer than 15 days audited and classified; the longest is 243 days |

## 9  Validity risks

- **Temperature source.** No independent temperature product is available in this repository, so the county aggregation is unvalidated. Earlier work found anchor-station against multi-station composite agreeing at only 0.45 to 0.73, which is larger than most of the definition effects measured here. This remains the dominant unresolved risk.
- **Station-network composition.** The reporting network changes over the record. Samples A and B control which counties are compared but not which stations are inside a county in a given year; the stable-station sensitivity is thin outside Texas and Florida (Louisiana 1 county, Mississippi 0, Alabama 2).
- **Gap-filling.** 22 of 254 Texas counties have no observed temperature at all and are carried entirely by interpolation. They are marked everywhere and a sensitivity excluding them is reported, but their classified days describe the interpolation as much as the county.
- **Different inputs for Part 1 and Parts 2-3.** Part 1 uses the observed record; Parts 2 and 3 use the gap-filled table, as the rest of the project does. The two are not on the same input by design, and no quantity is carried between them.
- **Sample selection.** Samples A and B exclude between a third and three quarters of counties depending on the state, and the excluded counties are disproportionately rural and short-record. This is a coverage restriction, not a random sample.
- **Knife-edge comparisons.** With a strict `>` comparison, a county-date sitting exactly on its threshold is decided by the last bit of a stored float. This affects a handful of records but is a reproducibility hazard for anyone reusing the archived thresholds.
- **No health outcome anywhere in this package**, so nothing here can identify a correct definition, and agreement between definitions is not evidence of accuracy.

## 10  Claims this package supports

- "Average daily high temperatures were highest during the prespecified warm season."
- "Average daily lows remained below 75 degF in some state-month summaries."
- "The recent-period median differed from the 1980s median under this aggregation."
- "Relative and absolute definitions identified different county-dates."
- "The 90 degF gate concentrated classifications into warmer months."
- "The result is sensitive to data coverage, county weighting, and station-network composition."
- "The analysis does not establish causality."

## 11  Claims this package does NOT support

- "Every summer temperature should exceed 75 degF."
- "The current balanced panel fully controls station-network change."
- "The period difference proves a climate trend."
- "The cool season causes the off-season classifications."
- "The 90 degF floor is an NWS advisory threshold."
- "The relative percentile definition gives every county equal exposure."
- "The Jaccard Index measures accuracy."
- "A county with more classified days necessarily has greater worker heat exposure."
- "The classifications caused occupational accidents."

## 12  Unresolved decisions

1. **The temperature source.** An independent, spatially consistent product (nClimGrid-Daily, PRISM or Daymet temperature) must be obtained before any county-level result is treated as settled. Nothing in this package narrows that question.
2. **Handling of the 18 inverted county-dates.** The declared rule quarantines the whole county-date. An advisor may prefer to keep the high and the low as separately valid station means. The choice changes nothing measurable here but should be signed off.
3. **Which sample is primary.** Sample A retains more counties, Sample B is strictly balanced. Their intervals overlap in every state, so the choice is currently a matter of preference rather than of evidence.
4. **Whether to adopt an absolute gate at all.** The gate makes the construct part-absolute. That is a research-question decision, not a sensitivity setting, and it should be made before linkage rather than after.
5. **Whether the shoulder months belong with summer.** May and October carry 18 to 21% of classified days across the relative definitions. A June-September season and a May-October season are materially different exposure windows.
6. **Extension beyond Texas.** Parts 2 and 3 are state-agnostic but only Texas has a built county-day table.

## 13  Recommended primary definition

**HYB_TX_P90_D3_A90_W15** - the county-specific 90th-percentile daily-high warm spell with a minimum duration of three days and a 90 degF absolute gate, at the w15 threshold window.

Reasoning, and the reasoning is about the research question rather than about the numbers. A purely relative rule (`REL_TX_P90_D3_W15`) places 57% of its classified days outside June-September and 38% in November-April; for an occupational heat-exposure measure a reader will interpret that as hazardous heat, and it is not. Adding the 90 degF gate moves the June-September share from 43% to 74% and retains 58% of the classified days. The three-day minimum removes the shortest runs without the 2.5x reduction the five-day rule imposes.

This recommendation is conditional in two ways that must travel with it. First, the gate makes the construct **part absolute**, so it must be named and described as a hybrid relative-and-absolute heat event, never as a heatwave and never as an NWS-equivalent. Second, no health outcome appears anywhere in this package, so nothing here can establish that this definition is the correct one - only that it matches the stated research question better than the alternatives tested.

## 14  Sensitivity definitions

| construct | role |
|---|---|
| REL_TX_P90_D3_W15 | the same construct with no absolute gate - isolates what the gate does |
| HYB_TX_P90_D3_A80_W15 | the weaker gate - shows that 80 degF is too low to change the character of the definition |
| ABS_TX_A90_D3 | absolute only - the hazard-style construct the relative family is usually contrasted against |
| REL_TX_P85_D3_W15 | a looser percentile at the same duration |
| REL_TX_P90_D2_W15 and REL_TX_P90_D5_W15 | the duration axis at the recommended percentile |
| REL_TX_P90_D3_W05, REL_TX_P90_D3_MON | the threshold-window axis, available in the annual layer for all four windows |
| Sample A and Sample B | the county-selection axis for every Part 1 result |
| six county subsets | the data-quality axis for every Part 2 result |

## 15  Reproducibility record

| item | value |
|---|---|
| git commit | 550d9e5+dirty |
| python | 3.14.3 |
| pandas / numpy / matplotlib / scipy | 3.0.3 / 2.4.6 / 3.11.0 / 1.18.0 |
| geopandas | 1.1.3 |
| platform | Windows-11-10.0.26200-SP0 |
| bootstrap seed | 20260801 |
| bootstrap resamples | 2000 |
| configuration | config/resolved_configuration.csv, config/r00_config_snapshot.py |
| input checksums | qa/03_current_output_checksums.csv |
| run manifest | run_manifest.csv |
| QA suite | qa/QA_TEST_SUITE.csv, qa/QA_REPORT.md |

Run the whole revision with `python scripts/run_revision.py`. Each step stops the pipeline if a blocking QA test fails; `qa/QA_TEST_SUITE.csv` records all 104 checks (94 pass, 0 fail, 10 reported).

## 16  Next action

1. Obtain an independent, spatially consistent temperature product (nClimGrid-Daily, PRISM or Daymet temperature) for 1979-2025 and re-run r05. Until that exists, no county-level temperature value in this project has been externally checked, and this is the single highest-value next step.
2. Get advisor sign-off on the recommended primary definition and on the handling of the 18 inverted county-dates.
3. Fix the archived threshold cache: store thresholds in a binary format, or add `float_precision='round_trip'` to every reader in the pipeline.
4. Build the county-day table for Louisiana, Mississippi, Alabama and Florida so Parts 2 and 3 stop being Texas-only.
5. Decide the exposure window (June-September against May-October) before linkage, because it changes the classified-day count by 18 to 21%.
6. Only then link to occupational-injury data, carrying the data-quality indicator for every county into the linked dataset.

---

## Figure specifications

Every figure below is reproducible from the named table and script. The full machine-readable version is `tables/figure_data_manifest.csv`.

### E2 - `r_fig_E2_distribution_by_state.png`

| field | value |
|---|---|
| purpose | show how county-level annual temperature values are distributed within and between states |
| unit of analysis | annual county-level observation |
| input table | tables/county_annual_temperature.csv |
| aggregation | no aggregation; every qualifying annual county-level observation is plotted, with a box summarising the state's pooled distribution |
| denominator | none (a distribution, not a rate) |
| result supported | that the within-state spread is comparable to the between-state spread, so a single state number is a weak summary of exposure |
| result NOT supported | a climatological normal; a period level; a trend; any separation of spatial from temporal variation |
| limitation | counties with more qualifying years carry more visual weight; see E2b |

> Distribution of county-level annual average temperatures by state, 1979-2025. Each point is one county's annual value; boxes summarise qualifying annual county-level observations. The figure combines spatial variation among counties, year-to-year variation and long-term change.

### E2b - `r_fig_E2b_one_value_per_county.png`

| field | value |
|---|---|
| purpose | remove the reporting-frequency weighting from E2 |
| unit of analysis | county |
| input table | tables/county_period_temperature.csv |
| aggregation | county period mean over the five periods; one value per county |
| denominator | none (a distribution, not a rate) |
| result supported | the between-county distribution of temperature level within each state, with equal weight per county |
| result NOT supported | a trend; a causal claim; a statement about counties excluded from Sample A |
| limitation | restricted to Sample A counties, which excludes between 37%% and 72%% of counties depending on the state |

> County-level temperature by state, 1979-2025, with every county contributing a single value. Sample A (consistent-county).

### E3 - `r_fig_E3_period_comparison.png`

| field | value |
|---|---|
| purpose | compare county-level temperature summaries between prespecified periods with equal weight per county |
| unit of analysis | county (one value per county per period) |
| input table | tables/state_period_temperature_equal_county.csv |
| aggregation | county period mean of annual county-level observations, then the median across counties; difference of medians against 1980-1989 |
| denominator | none (a level and a difference of levels, not a rate) |
| result supported | that the recent-period median differs from the 1980-1989 median under this aggregation, and by how much, with an interval and a county count |
| result NOT supported | a climate trend, a warming rate, or any causal attribution; the two samples are sensitivity cases, not independent replications |
| limitation | Sample A and Sample B retain different county sets, and both exclude a large share of counties; the excluded counties are not missing at random |

> County-level temperature comparison across periods, 1980-1989 to 2020-2025. Each county contributes one value per period; the state summary is the median across counties with a 95% bootstrap interval over counties. 2020-2025 is a six-year recent period.

### E4 - `r_fig_E4_monthly_level_and_difference.png`

| field | value |
|---|---|
| purpose | keep the seasonal LEVEL and the seasonal PERIOD DIFFERENCE visually and verbally separate |
| unit of analysis | county (one value per county per month, and per county per period) |
| input table | tables/revised_temperature_monthly_sanity_check.csv; tables/state_month_period_temperature_equal_county.csv |
| aggregation | top: median across counties of each county's monthly value. bottom: median across counties of each county's own period difference |
| denominator | none (levels and differences of levels) |
| result supported | that June-September has the highest temperatures, and separately that the cool season shows the larger period difference |
| result NOT supported | that the cool season is hotter than summer; that the difference is a trend; that the cool season causes off-season classifications |
| limitation | the bottom row is a two-period difference on a fixed county sample, not a fitted monthly trend |

> Monthly county-level temperature. Top: median county-level monthly average temperature, 1979-2025. Bottom: difference between 1980-1989 and 2020-2025 monthly county-level values, consistent-county sample. Prespecified warm season: June-September.

### R1 - `r_fig_R1_current_vs_revised_period_comparison.png`

| field | value |
|---|---|
| purpose | show the size of the aggregation defect being corrected |
| unit of analysis | county (revised) versus pooled annual county-level observation (current) |
| input table | tables/period_comparison_current_vs_revised.csv |
| aggregation | current: median over pooled annual observations. revised: median across counties of each county's period mean |
| denominator | none |
| result supported | that the choice of aggregation changes the reported period difference, and that the revised difference carries a wide interval |
| result NOT supported | that either estimate is the true change; that the difference is a trend |
| limitation | the two estimates also use different county samples, so the change mixes the weighting correction with the sample correction; tables/period_comparison_current_vs_revised.csv separates them |

> The aggregation correction. Grey: the current pooled result. Coloured: the revised equal-county result with a 95% bootstrap interval across counties.

### R2 - `r_fig_R2_consistent_vs_strict_balanced.png`

| field | value |
|---|---|
| purpose | test whether the period difference depends on which balancing rule is used |
| unit of analysis | county |
| input table | tables/sample_membership_counties.csv; tables/state_period_temperature_equal_county.csv |
| aggregation | county period mean, then median across counties, under two prespecified county-selection rules |
| denominator | none |
| result supported | that the two sample rules retain different county sets but give period differences whose intervals overlap in every state |
| result NOT supported | that either sample is unbiased, or that the excluded counties resemble the retained ones |
| limitation | both samples exclude the counties with the shortest records, which are disproportionately rural |

> Consistent-county sample against strict-balanced sample. Panel A: counties retained. Panel B: the period difference with a 95% bootstrap interval across counties.

### R3 - `r_fig_R3_external_benchmark.png`

| field | value |
|---|---|
| purpose | record that external validation was attempted and why it failed |
| unit of analysis | daily county-level record (panel A); required comparison (panel B) |
| input table | qa/benchmark_identity_test.csv; tables/benchmark_comparison_summary.csv |
| aggregation | share of matched daily records that are identical between the two products |
| denominator | matched daily county-level records |
| result supported | that no independent temperature product is available in this repository, so none of the required external comparisons can be made |
| result NOT supported | any statement that the project temperature values agree, or disagree, with an independent product |
| limitation | the identity test covers only the benchmark's 2015-2024 window; nothing is known about earlier years either way |

> External benchmarking could not be performed. The candidate product is identical to the project data on all 2,938,070 matched daily county-level records.

### R4 - `r_fig_R4_trend_sensitivity.png`

| field | value |
|---|---|
| purpose | estimate descriptive time-trend slopes so period differences are not mistaken for trends |
| unit of analysis | annual median across counties |
| input table | tables/state_annual_series.csv; tables/trend_sensitivity.csv |
| aggregation | Theil-Sen slope on the annual median across counties; 95% distribution-free Sen interval; OLS reported as a sensitivity case |
| denominator | none |
| result supported | that the annual state summary increased by X degF per decade under this descriptive model, and that the estimate is stable across four county samples |
| result NOT supported | causal attribution; separation of climate change from station-network change; any claim about individual counties |
| limitation | the stable-station subset contains fewer than three counties in Louisiana, Mississippi and Alabama, so that sensitivity case is uninformative there |

> Descriptive trend sensitivity for the average daily high temperature. Theil-Sen slopes on the annual median across counties, under four county samples.

### E5 - `r_fig_E5_percentile_duration_grid.png`

| field | value |
|---|---|
| purpose | show how the percentile and the persistence rule each change what a relative warm-spell definition selects |
| unit of analysis | county (A), annual county-level observation (B), individual event (C), classified county-date (D) |
| input table | tables/construct_summary.csv; tables/seasonal_classification_shares.csv |
| aggregation | A: median across counties of cumulative classified days. B: median across annual county-level observations of the annual event count. C: median across events of the integer duration. D: share of classified days by season |
| denominator | none in A-C; D is a share of classified days, not a rate |
| result supported | that the percentile moves the count smoothly while the duration rule bites hardest at the long end, and that a substantial share of classified days falls in the shoulder months |
| result NOT supported | that any cell is the correct definition; that these are heatwaves; that the counts are comparable to an absolute hot-spell rule |
| limitation | all nine cells share one walk-forward baseline, one comparison operator and one state, so the grid isolates only the percentile and duration axes |

> County-specific relative warm spells by percentile and minimum duration, w15 window, Texas, 2015-2025. Panel D reports June-September, May and October, and November-April separately.

### E5b - `r_fig_E5b_agreement_jaccard.png`

| field | value |
|---|---|
| purpose | quantify how far the nine relative definitions agree on which county-dates they classify |
| unit of analysis | classified county-date |
| input table | tables/definition_agreement_jaccard_matrix.csv |
| aggregation | |A intersect B| / |A union B| over the sets of classified county-dates |
| denominator | the union of the two classified sets |
| result supported | that the definitions overlap substantially but are not interchangeable |
| result NOT supported | that high agreement establishes validity, accuracy, or that either definition is correct |
| limitation | every pair here shares a baseline, a state and an operator, so agreement is higher than it would be across genuinely different constructs |

> Jaccard overlap of county-dates classified by each relative warm-spell definition. Agreement, not accuracy; nested thresholds and durations create structural subset relationships.

### E6 - `r_fig_E6_monthly_classification_rate.png`

| field | value |
|---|---|
| purpose | show when in the calendar a year-round relative rule fires, on a rate that is comparable between months of unequal length and coverage |
| unit of analysis | daily county-level observation |
| input table | tables/monthly_classification_rates.csv |
| aggregation | 1000 x classified days in the month / valid daily county-level observations in the month, pooled over counties and years |
| denominator | valid daily county-level observations for the RELATIVE family (daily high present and a historical threshold available) |
| result supported | that relative thresholds produce classifications in every month, and that the monthly rate varies by a measured factor across the calendar |
| result NOT supported | that the curves are flat (the prespecified criterion is not met); that the cool season causes the off-season classifications |
| limitation | pooling over counties and years hides between-county variation in the seasonal profile; the county layer is in tables/county_monthly_relative_warm_spells.csv |

> Statewide monthly classification rate aggregated across counties and years, for the nine relative warm-spell definitions. Identical y-axis scales.

### E7 - `r_fig_E7_absolute_gate_effect.png`

| field | value |
|---|---|
| purpose | measure what an absolute daily-high gate does to each relative definition |
| unit of analysis | classified county-date (A, B), county (C), annual county-level observation (D), daily county-level observation (E, F) |
| input table | tables/absolute_gate_effect.csv; tables/monthly_classification_rates.csv |
| aggregation | retained share = gated classified days / ungated classified days; county retention = per-county ratio; annual change = difference in the median annual county-level count; monthly rate per 1,000 valid records |
| denominator | for the rate panels, valid daily county-level observations for the construct's own family |
| result supported | that the 90 degF gate concentrates classifications into warmer months, at the cost of roughly half the classified days, and that it does so unevenly across counties |
| result NOT supported | that the gate corrects the relative rule; that the gate is an NWS threshold; that the gated construct is the same construct |
| limitation | the gated variants are run at the primary threshold window only, so the window axis is not crossed with the gate axis |

> Effect of an absolute daily-high gate on each relative warm-spell definition. The gate changes the construct to a hybrid relative-and-absolute definition.

### E8 - `r_fig_E8_absolute_vs_relative.png`

| field | value |
|---|---|
| purpose | compare the absolute and relative construct families on the same county-level footing |
| unit of analysis | annual county-level observation (A, B), daily county-level observation (C, E), classified county-date (D) |
| input table | tables/county_annual_all_constructs.csv; tables/monthly_classification_rates.csv; tables/absolute_vs_relative.csv; tables/construct_summary.csv |
| aggregation | distributions across annual county-level observations; monthly rate per 1,000 valid records; Jaccard over classified county-dates |
| denominator | family-specific valid daily county-level observations |
| result supported | that the absolute 80 degF rule classifies a very large share of all days, that the 90 degF rule is strongly seasonal, and that the absolute and relative rules select largely different county-dates |
| result NOT supported | that either construct is correct; that low agreement means one is wrong; that an absolute rule is a heat advisory |
| limitation | the absolute family is evaluated on Texas only and on the gap-filled county-day table, as the relative family is |

> Absolute hot-spell definitions against the county-specific relative warm-spell definition. Annual county-level distributions, monthly rates and day-level agreement.

### E9 - `r_fig_E9_county_geography_all_counties.png`

| field | value |
|---|---|
| purpose | show how the relative construct and the absolute gate vary geographically, alongside the data quality behind each county |
| unit of analysis | county |
| input table | tables/county_gate_effect.csv; tables/county_data_quality.csv |
| aggregation | cumulative classified days per county; per-county retained share; per-county share of gap-filled daily records |
| denominator | none for the maps of counts; the retained share uses each county's own ungated count as its denominator |
| result supported | that a county-specific percentile rule still produces a wide spread of county counts, and that an absolute gate removes more days in cooler counties |
| result NOT supported | that a relative rule equalises exposure by construction; that a county with more classified days has greater worker heat exposure |
| limitation | 22 of 254 counties have no observed temperature at all and are carried entirely by interpolation from neighbours |

> Geography of the TX-P90-D3 relative warm-spell definition and of the absolute daily-high gate. Panel D shows gap-filling by county; fully imputed counties are hatched.

### E9b - `r_fig_E9_county_geography_excluding_fully_imputed.png`

| field | value |
|---|---|
| purpose | show how the relative construct and the absolute gate vary geographically, alongside the data quality behind each county |
| unit of analysis | county |
| input table | tables/county_gate_effect.csv; tables/county_data_quality.csv |
| aggregation | cumulative classified days per county; per-county retained share; per-county share of gap-filled daily records |
| denominator | none for the maps of counts; the retained share uses each county's own ungated count as its denominator |
| result supported | that a county-specific percentile rule still produces a wide spread of county counts, and that an absolute gate removes more days in cooler counties |
| result NOT supported | that a relative rule equalises exposure by construction; that a county with more classified days has greater worker heat exposure |
| limitation | 22 of 254 counties have no observed temperature at all and are carried entirely by interpolation from neighbours |

> Geography of the TX-P90-D3 relative warm-spell definition and of the absolute daily-high gate. Panel D shows gap-filling by county; fully imputed counties are hatched.

### R5 - `r_fig_R5_imputation_sensitivity.png`

| field | value |
|---|---|
| purpose | test whether the county-level results depend on gap-filled data |
| unit of analysis | county subset |
| input table | tables/imputation_sensitivity.csv; tables/imputation_sensitivity_rankings.csv |
| aggregation | state summaries recomputed on six prespecified county subsets |
| denominator | family-specific valid daily county-level observations within each subset |
| result supported | that the summaries shift modestly when gap-filled counties are excluded, and in a consistent direction |
| result NOT supported | that the gap-filled counties are wrong, or that excluding them removes bias; the excluded counties are systematically rural |
| limitation | the six subsets are nested, so they are not independent sensitivity cases |

> Observed against imputed counties. The state summary for REL_TX_P90_D3_W15 recomputed on six county subsets.

### R6 - `r_fig_R6_event_timeline.png`

| field | value |
|---|---|
| purpose | make individual events visible, rather than only their aggregates |
| unit of analysis | individual event |
| input table | tables/individual_relative_warm_spell_events.csv |
| aggregation | none; events are drawn at their recorded start date and integer duration |
| denominator | none |
| result supported | that events are discrete, dated objects of integer length, distributed through the whole calendar |
| result NOT supported | any statistical claim; three counties are illustrative, not a sample |
| limitation | three counties chosen by their cumulative classified-day rank; not representative of the state |

> Individual event timeline for REL_TX_P90_D3_W15 in three contrasting counties.

### R7 - `r_fig_R7_long_event_audit.png`

| field | value |
|---|---|
| purpose | surface and classify the events long enough to need a human look |
| unit of analysis | individual event |
| input table | tables/long_event_audit.csv |
| aggregation | counts and distributions over events longer than 15 days |
| denominator | none |
| result supported | that long events are common in the absolute family by construction, and that most long relative spells clear their threshold by a wide margin |
| result NOT supported | that any long event is an error; the audit classifies, it does not delete |
| limitation | the station-composition flag uses the raw GHCN contributing-station count, which is unavailable for fully gap-filled county-dates |

> Long-event audit. Every event longer than 15 days, with the evidence needed to judge it.

### R8 - `r_fig_R8_annual_distributions.png`

| field | value |
|---|---|
| purpose | replace pooled totals with the annual county-level distributions behind them |
| unit of analysis | annual county-level observation |
| input table | tables/county_annual_relative_warm_spells.csv |
| aggregation | distribution over county-years of the annual count |
| denominator | none |
| result supported | the spread of annual county-level counts within each definition, which a pooled total conceals |
| result NOT supported | any between-county comparison without the data-quality indicator |
| limitation | includes fully imputed counties; figure R5 gives the subset sensitivity |

> Annual county-level distributions of classified days and event counts for the nine relative warm-spell definitions.

### R9 - `r_fig_R9_monthly_rates_all_families.png`

| field | value |
|---|---|
| purpose | compare the seasonal profile of all three construct families on one scale with family-specific denominators |
| unit of analysis | daily county-level observation |
| input table | tables/monthly_classification_rates.csv; qa/eligibility_denominator_comparison.csv |
| aggregation | 1000 x classified days / valid daily county-level observations, per month, per construct |
| denominator | family-specific valid daily county-level observations |
| result supported | that the absolute family is strongly seasonal while the relative family fires all year, on a shared scale and correct denominators |
| result NOT supported | that the equality of the three denominators generalises beyond this state and period |
| limitation | the denominators coincide here only because the gap-filled input has no missing daily highs |

> Monthly classification rates for all three construct families, on identical y-axis scales, each using its own valid-record denominator.

### R10 - `r_fig_R10_county_profiles.png`

| field | value |
|---|---|
| purpose | show what the construct looks like for individual counties, with data quality attached |
| unit of analysis | annual county-level observation within one county |
| input table | tables/county_profile_examples.csv; tables/county_annual_relative_warm_spells.csv; county_profiles/ |
| aggregation | none; annual counts are plotted directly |
| denominator | none |
| result supported | that annual counts vary strongly between years within a county, and that a fully imputed county still produces a plausible-looking series |
| result NOT supported | that these six counties are representative; that the fully imputed county's series describes its actual climate |
| limitation | chosen by rank on cumulative classified days, not sampled |

> County-level example profiles for REL_TX_P90_D3_W15. Six counties spanning the range of classified-day counts, including one with no observed temperature.

