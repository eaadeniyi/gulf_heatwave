# QA test suite

The revised pipeline stops if any blocking test fails. Tests are executed by the step that generates the data and then RE-CHECKED here against the written tables, so a test cannot pass in memory and be contradicted by what was saved.

| result | checks |
|---|---|
| PASS | 94 |
| REPORT | 7 |
| FLAG | 3 |

## TEST A - daily temperature logic

| check | result | blocking | detail |
|---|---|---|---|
| annual_high_at_least_annual_low_in_the_written_panel | PASS | True | 0 annual county-level observations with a mean high below the mean low |
| annual_average_equals_the_mean_of_the_annual_high_and_low_on_equal_days | PASS | True | on the 11,437 annual county-level observations where all three variables rest on the same number of days, max \|Tavg - (Tmax+Tmin)/2\| = 0.001000 degF (the written table is rounded to 3 decimal places) |
| annual_average_identity_among_QUALIFYING_observations | PASS | True | among the 19,171 annual county-level observations where all three variables meet the coverage requirement, max \|Tavg - (Tmax+Tmin)/2\| = 0.895 degF, median 0.00050, 99th percentile 0.287. The tolerance is 1 degF: the residual is the per-variable coverage gate admitting slightly different day sets, not an arithmetic error. |
| per_variable_coverage_gate_can_rest_on_different_day_sets | REPORT | False | 10,238 of 21,675 annual county-level observations have different valid-day counts for the high, the low and the average, because the coverage gate is applied per variable. Where they differ the gap is usually negligible (median 0.038 degF) but reaches 7.52 degF in the worst case. CONSEQUENCE: do not compute an annual average from the annual high and the annual low; use the Tavg rows, which are built from daily values. |
| fahrenheit_conversion_verified_against_known_values | PASS | True | failed cases: [] |
| inverted_records_quarantined_and_reported | REPORT | False | 18 raw county-dates removed by the declared rule 'quarantine_whole_county_date_and_report' and preserved in qa/quarantined_inverted_daily_records.csv |
| fahrenheit_conversion_0C | PASS | True | 0.0 degC must equal 32.0 degF |
| fahrenheit_conversion_100C | PASS | True | 100.0 degC must equal 212.0 degF |
| fahrenheit_conversion_-40C | PASS | True | -40.0 degC must equal -40.0 degF |
| fahrenheit_conversion_37C | PASS | True | 37.0 degC must equal 98.6 degF |
| tmax_not_below_tmin_in_analysis_panel | PASS | True | a daily high below the same day's daily low is physically impossible; checked AFTER the declared quarantine |
| inverted_county_dates_quarantined_from_raw_input | FLAG | False | raw county-dates removed by the declared rule 'quarantine_whole_county_date_and_report'; all are written unaltered to qa/quarantined_inverted_daily_records.csv |
| tavg_equals_mean_of_tmax_tmin | PASS | True | Tavg is DEFINED as (Tmax + Tmin) / 2; tolerance 1e-06 degF |
| tmax_within_plausible_range | PASS | False | prespecified range (-40.0, 135.0) degF; flagged, never edited |
| tmin_within_plausible_range | PASS | False | prespecified range (-50.0, 110.0) degF; flagged, never edited |
| no_duplicated_county_date | PASS | True | a duplicated county-date would double-weight that day |
| tmax_not_below_tmin_in_analysis_panel | PASS | True | a daily high below the same day's daily low is physically impossible; checked AFTER the declared quarantine |
| inverted_county_dates_quarantined_from_raw_input | FLAG | False | raw county-dates removed by the declared rule 'quarantine_whole_county_date_and_report'; all are written unaltered to qa/quarantined_inverted_daily_records.csv |
| tavg_equals_mean_of_tmax_tmin | PASS | True | Tavg is DEFINED as (Tmax + Tmin) / 2; tolerance 1e-06 degF |
| tmax_within_plausible_range | PASS | False | prespecified range (-40.0, 135.0) degF; flagged, never edited |
| tmin_within_plausible_range | PASS | False | prespecified range (-50.0, 110.0) degF; flagged, never edited |
| no_duplicated_county_date | PASS | True | a duplicated county-date would double-weight that day |
| tmax_not_below_tmin_in_analysis_panel | PASS | True | a daily high below the same day's daily low is physically impossible; checked AFTER the declared quarantine |
| inverted_county_dates_quarantined_from_raw_input | FLAG | False | raw county-dates removed by the declared rule 'quarantine_whole_county_date_and_report'; all are written unaltered to qa/quarantined_inverted_daily_records.csv |
| tavg_equals_mean_of_tmax_tmin | PASS | True | Tavg is DEFINED as (Tmax + Tmin) / 2; tolerance 1e-06 degF |
| tmax_within_plausible_range | PASS | False | prespecified range (-40.0, 135.0) degF; flagged, never edited |
| tmin_within_plausible_range | PASS | False | prespecified range (-50.0, 110.0) degF; flagged, never edited |
| no_duplicated_county_date | PASS | True | a duplicated county-date would double-weight that day |
| tmax_not_below_tmin_in_analysis_panel | PASS | True | a daily high below the same day's daily low is physically impossible; checked AFTER the declared quarantine |
| inverted_county_dates_quarantined_from_raw_input | PASS | False | raw county-dates removed by the declared rule 'quarantine_whole_county_date_and_report'; all are written unaltered to qa/quarantined_inverted_daily_records.csv |
| tavg_equals_mean_of_tmax_tmin | PASS | True | Tavg is DEFINED as (Tmax + Tmin) / 2; tolerance 1e-06 degF |
| tmax_within_plausible_range | PASS | False | prespecified range (-40.0, 135.0) degF; flagged, never edited |
| tmin_within_plausible_range | PASS | False | prespecified range (-50.0, 110.0) degF; flagged, never edited |
| no_duplicated_county_date | PASS | True | a duplicated county-date would double-weight that day |
| tmax_not_below_tmin_in_analysis_panel | PASS | True | a daily high below the same day's daily low is physically impossible; checked AFTER the declared quarantine |
| inverted_county_dates_quarantined_from_raw_input | PASS | False | raw county-dates removed by the declared rule 'quarantine_whole_county_date_and_report'; all are written unaltered to qa/quarantined_inverted_daily_records.csv |
| tavg_equals_mean_of_tmax_tmin | PASS | True | Tavg is DEFINED as (Tmax + Tmin) / 2; tolerance 1e-06 degF |
| tmax_within_plausible_range | PASS | False | prespecified range (-40.0, 135.0) degF; flagged, never edited |
| tmin_within_plausible_range | PASS | False | prespecified range (-50.0, 110.0) degF; flagged, never edited |
| no_duplicated_county_date | PASS | True | a duplicated county-date would double-weight that day |

## TEST B - coverage

| check | result | blocking | detail |
|---|---|---|---|
| annual_records_meet_the_configured_annual_day_threshold | PASS | True | 0 annual county-level observations flagged as meeting a 328-day requirement with fewer days |
| monthly_records_meet_the_configured_monthly_day_threshold | PASS | True | 0 monthly county-level summaries flagged as meeting a 25-day requirement with fewer days |
| every_state_period_result_reports_a_contributing_county_count | PASS | True | 0 of 150 state-period rows lack a county count |
| every_state_month_period_cell_reports_a_county_count | PASS | True | 0 of 1800 state-month-period rows lack a county count |

## TEST C - period weighting

| check | result | blocking | detail |
|---|---|---|---|
| one_value_per_county_per_state_period | PASS | True | 0 duplicated (sample, state, variable, county, period) rows |
| same_county_count_in_every_period__consistent_county | PASS | True | county counts per period: {('AL', 'Tavg'): {'1980-1989': 26, '1990-1999': 26, '2000-2009': 26, '2010-2019': 26, '2020-2025': 26}, ('AL', 'Tmax'): {'1980-1989': 28, '1990-1999': 28, '2000-2009': 28, '2010-2019': 28, '2020-2025': 28}, ('AL', 'Tmin'): {'1980-1989': 27, '1990-1999': 27, '2000-2009': 27, '2010-2019': 27, '2020-2025': 27}, ('FL', 'Tavg'): {'1980-1989': 32, '1990-1999': 32, '2000-2009': 32, '2010-2019': 32, '2020-2025': 32}, ('FL', 'Tmax'): {'1980-1989': 37, '1990-1999': 37, '2000-2009': 37, '2010-2019': 37, '2020-2025': 37}, ('FL', 'Tmin'): {'1980-1989': 34, '1990-1999': 34, '2000-2 |
| same_county_count_in_every_period__strict_balanced | PASS | True | county counts per period: {('AL', 'Tavg'): {'1980-1989': 30, '1990-1999': 30, '2000-2009': 30, '2010-2019': 30, '2020-2025': 30}, ('AL', 'Tmax'): {'1980-1989': 35, '1990-1999': 35, '2000-2009': 35, '2010-2019': 35, '2020-2025': 35}, ('AL', 'Tmin'): {'1980-1989': 32, '1990-1999': 32, '2000-2009': 32, '2010-2019': 32, '2020-2025': 32}, ('FL', 'Tavg'): {'1980-1989': 34, '1990-1999': 34, '2000-2009': 34, '2010-2019': 34, '2020-2025': 34}, ('FL', 'Tmax'): {'1980-1989': 36, '1990-1999': 36, '2000-2009': 36, '2010-2019': 36, '2020-2025': 36}, ('FL', 'Tmin'): {'1980-1989': 36, '1990-1999': 36, '2000-2 |
| strict_balanced_contributes_identical_annual_counts | PASS | True | every county-period must use exactly 6 annual observations; observed range 6-6 |
| counties_excluded_for_insufficient_coverage__consistent_county | REPORT | False | AL/Tavg 38 of 64 excluded; AL/Tmax 37 of 65 excluded; AL/Tmin 37 of 64 excluded; FL/Tavg 34 of 66 excluded; FL/Tmax 29 of 66 excluded; FL/Tmin 32 of 66 excluded; LA/Tavg 33 of 59 excluded; LA/Tmax 33 of 59 excluded; LA/Tmin 33 of 59 excluded; MS/Tavg 55 of 73 excluded; MS/Tmax 48 of 73 excluded; MS/Tmin 55 of 73 excluded; TX/Tavg 119 of 247 excluded; TX/Tmax 107 of 247 excluded; TX/Tmin 112 of 247 excluded |
| counties_excluded_for_insufficient_coverage__strict_balanced | REPORT | False | AL/Tavg 34 of 64 excluded; AL/Tmax 30 of 65 excluded; AL/Tmin 32 of 64 excluded; FL/Tavg 32 of 66 excluded; FL/Tmax 30 of 66 excluded; FL/Tmin 30 of 66 excluded; LA/Tavg 36 of 59 excluded; LA/Tmax 36 of 59 excluded; LA/Tmin 36 of 59 excluded; MS/Tavg 52 of 73 excluded; MS/Tmax 50 of 73 excluded; MS/Tmin 52 of 73 excluded; TX/Tavg 108 of 247 excluded; TX/Tmax 99 of 247 excluded; TX/Tmin 102 of 247 excluded |
| duplicating_one_annual_record_does_not_change_the_state_estimate | PASS | True | duplicated 48001 in 1980; max change in any state-period median = 0 degF (the current pooled rule changes by 0.004 degF on the same perturbation) |

## TEST F - denominators

| check | result | blocking | detail |
|---|---|---|---|
| classification_rate_never_exceeds_1000_per_1000 | PASS | True | maximum observed rate 1000.000 per 1,000 |
| classified_days_never_exceed_valid_records | PASS | True | 0 violations |
| missing_exposure_is_not_coded_as_a_non_event | PASS | True | 0 monthly summaries carry a zero or missing denominator; the panel is built FROM the valid-record table, so a county-month with no valid records is absent rather than present as a zero |
| construct_family_denominators_tested_not_assumed | REPORT | False | relative == hybrid: True; relative == absolute: True. documented as equal for this state and period |

## TEST G - output consistency

| check | result | blocking | detail |
|---|---|---|---|
| figure_E5A_value_matches_the_csv | PASS | True | median cumulative classified days recomputed from county_annual_all_constructs.csv for all 9 relative constructs |
| figure_E5B_value_matches_the_csv | PASS | True | median annual event count recomputed for 33 constructs |
| figure_E5D_seasonal_shares_sum_to_100 | PASS | True | worst deviation 0.0100 percentage points |
| figure_E6_R9_rates_recompute_from_their_counts | PASS | True | worst deviation 0.000499 per 1,000 |
| figure_E7A_retained_share_matches_the_csv | PASS | True | recomputed for 18 gate rows |
| figure_E3_bars_have_point_estimate_and_interval | PASS | True | 0 of 150 state-period rows lack a difference or an interval |
| bootstrap_interval_contains_its_point_estimate | PASS | True | 0 violations |
| annual_classified_days_equal_the_sum_of_monthly_counts | PASS | True | 0 of 92202 county-years disagree across 33 constructs |
| event_durations_sum_to_classified_days | PASS | True | 0 of 33 constructs disagree |
| every_event_id_in_a_summary_exists_in_the_event_table | PASS | True | 651340 referenced ids, 0 absent from the catalogues |
| event_durations_are_integers | PASS | True | 0 events with a fractional duration |

## TESTS D to G as executed in r06

| check | result | blocking | detail |
|---|---|---|---|
| event_duration_is_an_integer | PASS | True | 0 events with a fractional duration |
| event_dates_are_consecutive | PASS | True | 0 events whose end minus start does not equal the duration |
| event_meets_its_minimum_duration | PASS | True | 0 events shorter than their own minimum |
| D3_subset_of_D2__P80 | PASS | True | 0 county-dates in the longer-duration set but not the shorter one |
| D5_subset_of_D3__P80 | PASS | True | 0 county-dates in the longer-duration set but not the shorter one |
| D5_subset_of_D2__P80 | PASS | True | 0 county-dates in the longer-duration set but not the shorter one |
| D3_subset_of_D2__P85 | PASS | True | 0 county-dates in the longer-duration set but not the shorter one |
| D5_subset_of_D3__P85 | PASS | True | 0 county-dates in the longer-duration set but not the shorter one |
| D5_subset_of_D2__P85 | PASS | True | 0 county-dates in the longer-duration set but not the shorter one |
| D3_subset_of_D2__P90 | PASS | True | 0 county-dates in the longer-duration set but not the shorter one |
| D5_subset_of_D3__P90 | PASS | True | 0 county-dates in the longer-duration set but not the shorter one |
| D5_subset_of_D2__P90 | PASS | True | 0 county-dates in the longer-duration set but not the shorter one |
| P90_subset_of_P85__D2 | PASS | True | 0 county-dates at the 90th percentile absent from the 85th |
| P85_subset_of_P80__D2 | PASS | True | 0 county-dates at the 85th percentile absent from the 80th |
| P90_subset_of_P80__D2 | PASS | True | 0 county-dates at the 90th percentile absent from the 80th |
| P90_subset_of_P85__D3 | PASS | True | 0 county-dates at the 90th percentile absent from the 85th |
| P85_subset_of_P80__D3 | PASS | True | 0 county-dates at the 85th percentile absent from the 80th |
| P90_subset_of_P80__D3 | PASS | True | 0 county-dates at the 90th percentile absent from the 80th |
| P90_subset_of_P85__D5 | PASS | True | 0 county-dates at the 90th percentile absent from the 85th |
| P85_subset_of_P80__D5 | PASS | True | 0 county-dates at the 85th percentile absent from the 80th |
| P90_subset_of_P80__D5 | PASS | True | 0 county-dates at the 90th percentile absent from the 80th |
| hybrid_days_satisfy_both_conditions | PASS | True | 0 of 46448 classified days fail one of the two conditions |
| hybrid_days_reach_the_absolute_gate | PASS | True | minimum daily high among classified days = 90.00 degF, gate = 90 degF |
| absolute_construct_uses_no_historical_threshold | PASS | True | the absolute construct's threshold column is the constant gate, not a percentile |
| absolute_eligibility_needs_only_the_daily_high | PASS | True | eligible records equal records with a daily high present |
| gate_operator_effect_reported_after_event_reconstruction | REPORT | False | with '>=' : 46448 classified days, 8613 events; with '>' : 46448 classified days, 8613 events; 2 daily records sit exactly on the 90 degF gate; the operator changes 0 classified days and 0 events |
| classification_rate_never_exceeds_1000_per_1000 | PASS | True | 0 monthly county-level summaries above 1000 per 1000 |
| classified_days_never_exceed_valid_records | PASS | True | 0 summaries with classified days but no valid records |
| classified_day_count_at_most_valid_observation_count | PASS | True | 0 summaries where classified days exceed valid records |
| missing_exposure_is_not_coded_as_a_non_event | PASS | True | 0 summaries carry a missing denominator; a missing record must not be counted as a zero |
| annual_classified_days_equal_the_sum_of_monthly_counts | PASS | True | 0 of 92202 county-years disagree, across 33 constructs with both layers |
| event_durations_sum_to_classified_days | PASS | True | 0 constructs disagree |
| every_event_id_in_a_summary_exists_in_the_event_table | PASS | True | 0 event ids referenced but absent |

## Stage 1 reproduction

| check | result | blocking | detail |
|---|---|---|---|
| current_pipeline_reproduces | PASS | True | 29 of 29 artifacts reproduce |
| classification_step_reproduces_by_independent_rebuild | PASS | True | 120 of 120 exact set-equality checks pass |
| archived_csv_float_roundtrip_defect_quantified | REPORT | False | 99,405 of 3,067,812 archived threshold values are misparsed by the pandas DEFAULT float parser, flipping the relative condition on 2 daily records; this package reads them with float_precision='round_trip' |

## figure palettes

| check | result | blocking | detail |
|---|---|---|---|
| figure_palettes_pass_the_colour_vision_checks | PASS | True | 4 of 4 palettes pass; worst normal-vision separation 16.3, worst colour-vision separation 12.4 |

## terminology compliance

| check | result | blocking | detail |
|---|---|---|---|
| retired_vocabulary_absent_from_qa_and_audit_prose | PASS | True | 0 unguarded use(s) across 3 files |

