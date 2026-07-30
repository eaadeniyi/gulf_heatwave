# Data dictionary

Units are carried in the column names: `_QA_pooled` marks a pooled cross-county quantity (never a substantive result), `_2015_2025` marks a cumulative count (never annual), and every event duration is an integer number of consecutive dates.

## `canonical_long/*.csv.gz`

| column | definition | kind |
|---|---|---|
| county_fips | 5-digit county FIPS | identifier |
| county_name | county name | identifier |
| climate_division | NOAA climate-division name (numbers primary source, names secondary labels) | identifier |
| climdiv_id | NOAA climate-division number | identifier |
| date | calendar date (YYYY-MM-DD) | identifier |
| year | calendar year of the date | identifier |
| month | calendar month of the date | identifier |
| run_id | definition_id + '__' + window | identifier |
| definition_id | METRIC_Pxx_nD, e.g. TMAX_P90_2D | identifier |
| metric | TMAX \| TMIN \| MHI | design |
| percentile | 85 \| 90 \| 95 | design |
| minimum_duration | minimum consecutive days for a qualifying run | design |
| window | w05 \| w15 \| month \| month_pm7 | design |
| reference_method | walk_forward_1979_to_Yminus1 | design |
| season_rule | year_round | design |
| absolute_floor | none in all 16 definitions | design |
| daily_metric_value | the day's metric, degF, ROUNDED to 3 dp for readability | measurement |
| threshold_value | the county's own walk-forward percentile threshold, degF, ROUNDED to 3 dp | measurement |
| exceedance_degF | metric minus threshold, UNROUNDED - the column that reproduces the strict '>' | measurement |
| n_reference_values | baseline observations behind the threshold (low_n_ref below 20) | quality |
| relative_exceedance_flag | 1 if metric > threshold, before any floor and before artifact masking | flag |
| candidate_day_flag | 1 if a candidate day (relative exceedance, floor if any, not an artifact day) | flag |
| heatwave_day_flag | 1 if a candidate day inside a run of >= minimum_duration consecutive days | flag |
| event_id | state_county_year_seq_definition; null on non-heatwave days | identifier |
| event_start_date | first date of the event | event |
| event_end_date | last date of the event | event |
| event_duration_days | INTEGER consecutive dates, end - start + 1 | event |
| observed_or_imputed | 'observed' or 'imputed' (IDW-filled temperature) for this county-day | quality |
| temperature_imputation_fraction | county-level fraction of analysis days whose temperature was IDW-filled | quality |
| input_hash | md5 prefix of the input county-day table | provenance |
| pipeline_version | git commit (+dirty) | provenance |

## `eligibility_county_month.csv`

| column | definition | kind |
|---|---|---|
| eligible_days | county-days the definition could be evaluated on - THE DENOMINATOR | denominator |
| calendar_days | county-days in the month | denominator |
| missing_metric_days | metric absent for that county-day | quality |
| missing_threshold_days | no threshold estimable for that county-day | quality |
| artifact_excluded_days | confirmed RH-clip artifact days excluded (RH-dependent metrics only) | quality |

## `master_county_month_summary.csv`

| column | definition | kind |
|---|---|---|
| heatwave_events_started | events whose ONSET falls in this month (an event is counted once) | event |
| heatwave_events_active | events touching this month (a month-crossing event counts in each) | event |

## `master_county_year_summary.csv`

| column | definition | kind |
|---|---|---|
| heatwave_events_started | events whose onset falls in this year (year boundary does not split an event) | event |

## `table2_run_qa_summary.csv`

| column | definition | kind |
|---|---|---|
| *_QA_pooled* | pooled across counties - a QA quantity, never a substantive result | QA |

## `table6_definition_pair_agreement.csv`

| column | definition | kind |
|---|---|---|
| jaccard_day_level | shared county-dates / union; AGREEMENT between two definitions, not accuracy | comparison |

## `table7_matched_pair_marginal_effects.csv`

| column | definition | kind |
|---|---|---|
| count_ratio_hi_over_lo | pooled heatwave days, higher run / lower run, within a matched pair | comparison |

## `table8a_long_event_audit.csv`

| column | definition | kind |
|---|---|---|
| disposition | always RETAINED - long events are flagged for review, never deleted | QA |

