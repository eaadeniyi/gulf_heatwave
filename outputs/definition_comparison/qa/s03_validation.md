# s03 - pre-comparison validation

136 checks: **121 PASS, 0 FAIL**, 15 reported observations (no pass/fail semantics).

**Verdict: the sixteen definitions are comparable on every axis held fixed, and the comparison may be built**

## Item 1 - identical fixed axes across all sixteen definitions

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| input fingerprint identical for every logged run | run_log.csv | PASS | 1 | 1 | md5:f0276ee5888539f9 |
| logged input fingerprint == current input file | county_daily_heat.csv | PASS | md5:f0276ee5888539f9 | md5:f0276ee5888539f9 | county_daily_heat.csv |
| all 16 definitions appear in the provenance log | run_log.csv | PASS | 0 | 0 | missing: [] |
| boundary source present and readable | tl_2020_us_county.shp | PASS | 254 | 254 | tl_2020_us_county.shp |
| same county count in every metric x window | eligibility table | PASS | [254] | [254] | 12 metric x window combinations |
| analysis years identical and complete | eligibility table | PASS | 2015-2025 | 2015-2025 | 11 years |
| all 12 calendar months evaluated (year-round season) | eligibility table | PASS | [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] | [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] |  |
| reference_method identical across all runs | canonical shards | PASS | 1 | 1 | value: walk_forward_1979_to_Yminus1 |
| reference_method == walk_forward_1979_to_Yminus1 | canonical shards | PASS | walk_forward_1979_to_Yminus1 | walk_forward_1979_to_Yminus1 |  |
| season_rule identical across all runs | canonical shards | PASS | 1 | 1 | value: year_round |
| season_rule == year_round | canonical shards | PASS | year_round | year_round |  |
| absolute_floor identical across all runs | canonical shards | PASS | 1 | 1 | value: none |
| absolute_floor == none | canonical shards | PASS | none | none |  |
| input_hash identical across all canonical shards | canonical shards | PASS | 1 | 1 | md5:f0276ee5888539f9 |
| strict '>': no classified day with metric <= threshold | canonical shards | PASS | 0 | 0 | smallest exceedance among classified days = +3.55e-15 degF |
| classified days whose exceedance is below 1e-9 degF | canonical shards | REPORTED | 9222 |  | the strict '>' is decided by floating-point-scale margins on these days; they arise because Tmax/Tmin are quantised to 0.1 degC so a percentile can land on an observed value. See qa/s02_knife_edge_days.csv |
| no absolute floor: classified days exist below 80 degF | canonical shards | PASS | True | True | lowest classified metric value = 26.1 degF |
| one IDW gap-filled input table serves every definition | county_daily_heat.csv (md5 f0276ee5888539f9) | PASS | 1 | 1 | IDW power 2, 17.9% of county-days imputed, 22 counties fully imputed |
| window 'w05' has one shape in every threshold cache | _thresholds/ | PASS | [('template_doy', 366)] | [('template_doy', 366)] | 9 cache file(s); label: centered 5-day window (+/-2 days) |
| window 'w05' label identical across metrics | _thresholds/ | PASS | 1 | 1 |  |
| window 'w15' has one shape in every threshold cache | _thresholds/ | PASS | [('template_doy', 366)] | [('template_doy', 366)] | 9 cache file(s); label: centered 15-day window (+/-7 days) |
| window 'w15' label identical across metrics | _thresholds/ | PASS | 1 | 1 |  |
| window 'month' has one shape in every threshold cache | _thresholds/ | PASS | [('calendar_month', 12)] | [('calendar_month', 12)] | 9 cache file(s); label: calendar-month bucket |
| window 'month' label identical across metrics | _thresholds/ | PASS | 1 | 1 |  |
| window 'month_pm7' has one shape in every threshold cache | _thresholds/ | PASS | [('calendar_month', 12)] | [('calendar_month', 12)] | 9 cache file(s); label: calendar month +/- 7 days |
| window 'month_pm7' label identical across metrics | _thresholds/ | PASS | 1 | 1 |  |

## Item 2 - re-run of the published definitions

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| re-run verification has no failures | qa/s01_legacy_rerun_verification.csv | PASS | 0 | 0 | 46 checks |
| re-run definition present at all four windows | MHI_P85_2D | PASS | 4 | 4 | MHI_P85_2D: w05,w15,month,month_pm7 |
| re-run definition present at all four windows | MHI_P95_2D | PASS | 4 | 4 | MHI_P95_2D: w05,w15,month,month_pm7 |
| reason for re-running Def 01 / Def 02 |  | REPORTED | 3 conditions differed |  | published outputs came from an earlier p02 (different output schema, no event_id, no metric column), only 2 of 4 windows were ever run, and no input fingerprint was recorded -- so they were re-run on the current code path |

## Item 3 - expected county set

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| county count matches the Census county list | all definitions | PASS | 254 | 254 | Census list for state 48 |
| counties expected but absent from the analysis | all definitions | PASS | 0 | 0 | none |
| counties analysed but not in the Census list | all definitions | PASS | 0 | 0 | none |
| counties with no heatwave day in ANY definition |  | REPORTED | 0 |  | none -- every county is classified by at least one definition |
| counties with 100% imputed temperature |  | REPORTED | 22 |  | flagged in every county-level comparison; never silently dropped |
| counties at or below the prespecified 10% imputation cut |  | REPORTED | 188 |  | the 'complete-data' panel population |

## Item 4 - definition x window combinations

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| expected combinations |  | PASS | 64 | 64 | 16 definitions x 4 windows |
| combinations present as canonical shards |  | PASS | 64 | 64 | none missing |
| pipeline run summary present for every combination |  | PASS | 64 | 64 |  |
| county-year table present for every combination |  | PASS | 64 | 64 |  |
| county-month table present for every combination |  | PASS | 64 | 64 |  |

## Item 5 - missing combinations are absent, not zero

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| no county-year rows for untested cells |  | PASS | 0 | 0 | a zero row would read as 'tested and found nothing' |
| no county-month rows for untested cells |  | PASS | 0 | 0 | a zero row would read as 'tested and found nothing' |
| no event rows for untested cells |  | PASS | 0 | 0 | a zero row would read as 'tested and found nothing' |
| no canonical shard for untested cells |  | PASS | 0 | 0 |  |
| genuine zero rows in the county-year table |  | REPORTED | 0 |  | county-years evaluated with no heatwave day -- distinct from an absent cell |

## Item 6 - the grid is incomplete (two untested cells)

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| full factorial size |  | PASS | 18 | 18 | 3 metrics x 3 percentiles x 2 durations |
| definitions tested |  | PASS | 16 | 16 |  |
| untested cells identified exactly |  | PASS | ['MHI_P85_3D', 'MHI_P95_3D'] | ['MHI_P85_3D', 'MHI_P95_3D'] | never zero-filled, never interpolated across |

## Item 7 - marginal effects from valid matched pairs only

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| every pair differs on exactly one axis |  | PASS | 0 | 0 | 240 matched pairs total |
| no pair references an absent run |  | PASS | 0 | 0 |  |

## Item 8 - matched-pair counts

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| matched pairs on the duration axis |  | REPORTED | 28 |  | reported with every marginal effect for this axis |
| matched pairs on the metric axis |  | REPORTED | 56 |  | reported with every marginal effect for this axis |
| matched pairs on the percentile axis |  | REPORTED | 60 |  | reported with every marginal effect for this axis |
| matched pairs on the window axis |  | REPORTED | 96 |  | reported with every marginal effect for this axis |
| duration pairs limited by the untested mean-HI cells |  | PASS | 28 | 28 | 7 of 9 metric x percentile cells have both durations, x 4 windows |

## Item 9 - duration nesting

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| 3-day days are a subset of 2-day days | MHI_P90_month | PASS | 0 | 0 | jaccard 0.7240, count ratio 0.7240 (equal iff nested) |
| jaccard equals the count ratio exactly | MHI_P90_month | PASS | 0.724037921 | 0.724037921 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | MHI_P90_month_pm7 | PASS | 0 | 0 | jaccard 0.7138, count ratio 0.7138 (equal iff nested) |
| jaccard equals the count ratio exactly | MHI_P90_month_pm7 | PASS | 0.713817575 | 0.713817575 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | MHI_P90_w05 | PASS | 0 | 0 | jaccard 0.7091, count ratio 0.7091 (equal iff nested) |
| jaccard equals the count ratio exactly | MHI_P90_w05 | PASS | 0.709097447 | 0.709097447 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | MHI_P90_w15 | PASS | 0 | 0 | jaccard 0.7056, count ratio 0.7056 (equal iff nested) |
| jaccard equals the count ratio exactly | MHI_P90_w15 | PASS | 0.705577678 | 0.705577678 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMAX_P85_month | PASS | 0 | 0 | jaccard 0.7864, count ratio 0.7864 (equal iff nested) |
| jaccard equals the count ratio exactly | TMAX_P85_month | PASS | 0.786433763 | 0.786433763 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMAX_P85_month_pm7 | PASS | 0 | 0 | jaccard 0.7804, count ratio 0.7804 (equal iff nested) |
| jaccard equals the count ratio exactly | TMAX_P85_month_pm7 | PASS | 0.780437452 | 0.780437452 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMAX_P85_w05 | PASS | 0 | 0 | jaccard 0.7806, count ratio 0.7806 (equal iff nested) |
| jaccard equals the count ratio exactly | TMAX_P85_w05 | PASS | 0.780636181 | 0.780636181 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMAX_P85_w15 | PASS | 0 | 0 | jaccard 0.7752, count ratio 0.7752 (equal iff nested) |
| jaccard equals the count ratio exactly | TMAX_P85_w15 | PASS | 0.775210554 | 0.775210554 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMAX_P90_month | PASS | 0 | 0 | jaccard 0.7535, count ratio 0.7535 (equal iff nested) |
| jaccard equals the count ratio exactly | TMAX_P90_month | PASS | 0.753505231 | 0.753505231 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMAX_P90_month_pm7 | PASS | 0 | 0 | jaccard 0.7430, count ratio 0.7430 (equal iff nested) |
| jaccard equals the count ratio exactly | TMAX_P90_month_pm7 | PASS | 0.74299842 | 0.74299842 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMAX_P90_w05 | PASS | 0 | 0 | jaccard 0.7500, count ratio 0.7500 (equal iff nested) |
| jaccard equals the count ratio exactly | TMAX_P90_w05 | PASS | 0.749971641 | 0.749971641 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMAX_P90_w15 | PASS | 0 | 0 | jaccard 0.7453, count ratio 0.7453 (equal iff nested) |
| jaccard equals the count ratio exactly | TMAX_P90_w15 | PASS | 0.745254201 | 0.745254201 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMAX_P95_month | PASS | 0 | 0 | jaccard 0.6952, count ratio 0.6952 (equal iff nested) |
| jaccard equals the count ratio exactly | TMAX_P95_month | PASS | 0.695241542 | 0.695241542 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMAX_P95_month_pm7 | PASS | 0 | 0 | jaccard 0.6836, count ratio 0.6836 (equal iff nested) |
| jaccard equals the count ratio exactly | TMAX_P95_month_pm7 | PASS | 0.68355563 | 0.68355563 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMAX_P95_w05 | PASS | 0 | 0 | jaccard 0.6990, count ratio 0.6990 (equal iff nested) |
| jaccard equals the count ratio exactly | TMAX_P95_w05 | PASS | 0.698968482 | 0.698968482 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMAX_P95_w15 | PASS | 0 | 0 | jaccard 0.6871, count ratio 0.6871 (equal iff nested) |
| jaccard equals the count ratio exactly | TMAX_P95_w15 | PASS | 0.687146493 | 0.687146493 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMIN_P85_month | PASS | 0 | 0 | jaccard 0.7969, count ratio 0.7969 (equal iff nested) |
| jaccard equals the count ratio exactly | TMIN_P85_month | PASS | 0.796906464 | 0.796906464 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMIN_P85_month_pm7 | PASS | 0 | 0 | jaccard 0.7932, count ratio 0.7932 (equal iff nested) |
| jaccard equals the count ratio exactly | TMIN_P85_month_pm7 | PASS | 0.793205233 | 0.793205233 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMIN_P85_w05 | PASS | 0 | 0 | jaccard 0.7912, count ratio 0.7912 (equal iff nested) |
| jaccard equals the count ratio exactly | TMIN_P85_w05 | PASS | 0.791226402 | 0.791226402 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMIN_P85_w15 | PASS | 0 | 0 | jaccard 0.7882, count ratio 0.7882 (equal iff nested) |
| jaccard equals the count ratio exactly | TMIN_P85_w15 | PASS | 0.788232182 | 0.788232182 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMIN_P90_month | PASS | 0 | 0 | jaccard 0.7613, count ratio 0.7613 (equal iff nested) |
| jaccard equals the count ratio exactly | TMIN_P90_month | PASS | 0.761349428 | 0.761349428 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMIN_P90_month_pm7 | PASS | 0 | 0 | jaccard 0.7587, count ratio 0.7587 (equal iff nested) |
| jaccard equals the count ratio exactly | TMIN_P90_month_pm7 | PASS | 0.758702229 | 0.758702229 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMIN_P90_w05 | PASS | 0 | 0 | jaccard 0.7496, count ratio 0.7496 (equal iff nested) |
| jaccard equals the count ratio exactly | TMIN_P90_w05 | PASS | 0.749581724 | 0.749581724 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMIN_P90_w15 | PASS | 0 | 0 | jaccard 0.7484, count ratio 0.7484 (equal iff nested) |
| jaccard equals the count ratio exactly | TMIN_P90_w15 | PASS | 0.748359707 | 0.748359707 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMIN_P95_month | PASS | 0 | 0 | jaccard 0.6996, count ratio 0.6996 (equal iff nested) |
| jaccard equals the count ratio exactly | TMIN_P95_month | PASS | 0.699626836 | 0.699626836 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMIN_P95_month_pm7 | PASS | 0 | 0 | jaccard 0.6964, count ratio 0.6964 (equal iff nested) |
| jaccard equals the count ratio exactly | TMIN_P95_month_pm7 | PASS | 0.696448136 | 0.696448136 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMIN_P95_w05 | PASS | 0 | 0 | jaccard 0.6975, count ratio 0.6975 (equal iff nested) |
| jaccard equals the count ratio exactly | TMIN_P95_w05 | PASS | 0.697504628 | 0.697504628 | algebraic consequence of nesting |
| 3-day days are a subset of 2-day days | TMIN_P95_w15 | PASS | 0 | 0 | jaccard 0.6933, count ratio 0.6933 (equal iff nested) |
| jaccard equals the count ratio exactly | TMIN_P95_w15 | PASS | 0.693345909 | 0.693345909 | algebraic consequence of nesting |
| duration-nesting cells checked |  | REPORTED | 28 |  | metric x percentile x window cells having both durations |

## Item 10 - valid eligible-day denominators

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| calendar days per county identical everywhere | eligibility table | PASS | [4018] | [4018] | 2015-2025 inclusive |
| eligible days never exceed calendar days | county-month | PASS | 0 | 0 |  |
| eligible days never negative |  | PASS | 0 | 0 |  |
| county-year: denominator present on every row |  | PASS | 0 | 0 |  |
| county-year: denominator strictly positive |  | PASS | 0 | 0 |  |
| county-year: heatwave days never exceed eligible days |  | PASS | 0 | 0 | a rate above 1000 per 1000 would be impossible |
| county-month: denominator present on every row |  | PASS | 0 | 0 |  |
| county-month: denominator strictly positive |  | PASS | 0 | 0 |  |
| county-month: heatwave days never exceed eligible days |  | PASS | 0 | 0 | a rate above 1000 per 1000 would be impossible |
| county-month days excluded from denominators |  | REPORTED | 388 |  | missing metric, missing threshold, or confirmed RH-clip artifact; excluded rather than counted as non-heatwave days |
| county-days excluded as confirmed RH-clip artifact |  | REPORTED | 388 |  | RH-dependent metrics only (mean HI); Tmax/Tmin keep those days |

## Item 11 - the county-month allocation rule

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| events_started summed over months == total events |  | PASS | 0 | 0 | checked for 64 runs; a month-crossing event must not be counted twice |
| heatwave days summed over months == summed over years |  | PASS | 0 | 0 | days are allocated to their actual calendar month and year |
| events_active is never below events_started |  | PASS | 0 | 0 |  |
| events crossing a month boundary |  | REPORTED | 105017 |  | each is counted once at onset and active in every month it touches |
| month-crossing events show up as extra ACTIVE months |  | PASS | True | True | active minus started = 105077 extra county-months |

## Item 12 - the year-boundary rule

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| runs are not broken at 31 December |  | PASS | True | True | 10046 events span a year boundary; zero would mean runs were being split |
| every year-crossing event starts in December |  | PASS | 0 | 0 |  |
| every year-crossing event ends in January |  | PASS | 0 | 0 |  |
| onset_year equals the start date's year |  | PASS | 0 | 0 | the event is counted once, in its onset year |
| longest year-crossing event (days) |  | REPORTED | 20 |  | duration is end - start + 1 across the boundary, an integer |
| events_started summed over years == total events |  | PASS | 0 | 0 | a year-crossing event is counted once, not in both years |
| days of a year-crossing event appear in BOTH calendar years | MHI_P85_2D__month | PASS | True | True | example 48_001_2021_015_MHI_P85_2D in Anderson: 2021-12-23 to 2022-01-01 |

