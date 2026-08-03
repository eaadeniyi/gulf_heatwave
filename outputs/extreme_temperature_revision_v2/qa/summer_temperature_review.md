# Warm-season temperature review

The analysis uses a county-by-day panel in which each record represents one county on one calendar date.

This review exists because a previous reading of the record treated a summer value below 75 degF as suspect. That rule is not supported and is not applied here. The three daily variables answer different questions and have different expected magnitudes:

| variable | definition | warm-season expectation |
|---|---|---|
| Daily high temperature (Tmax) | daily maximum air temperature | should be well above 75 degF in June-September in these states |
| Daily low temperature (Tmin) | daily minimum air temperature | may plausibly be below 75 degF, especially in inland, northern, rural and elevated counties |
| Daily average temperature (Tavg) | (Tmax + Tmin) / 2 | may fall on either side of 75 degF depending on state and month |

An average of daily minimum temperatures is the AVERAGE DAILY LOW. It is not 'the minimum temperature of the month'.

## What the record shows, June-September

| state | Average daily high temperature | Average daily low temperature | Average daily temperature |
|---|---|---|---|
| AL | 89.0 | 67.3 | 78.1 |
| FL | 90.7 | 71.5 | 81.1 |
| LA | 90.6 | 70.6 | 80.7 |
| MS | 89.7 | 67.9 | 78.8 |
| TX | 92.6 | 69.3 | 81.0 |

- **Average daily high temperature.** Median across counties ranges 89.0 to 92.6 degF across the five states. 0 of 511 contributing counties have a June-September value below 75 degF (0%). Expected: above 75 degF.
- **Average daily low temperature.** Median across counties ranges 67.3 to 71.5 degF across the five states. 500 of 511 contributing counties have a June-September value below 75 degF (98%). Expected: below or above 75 degF.
- **Average daily temperature.** Median across counties ranges 78.1 to 81.1 degF across the five states. 12 of 511 contributing counties have a June-September value below 75 degF (2%). Expected: near 75 degF.

A June-September average daily low below 75 degF is therefore the ordinary case in much of this region, not a data-quality signal. It is not flagged.

## June-August compared with June-September

| state | variable_label | median_across_counties_f_jun_aug | contributing_counties | median_across_counties_f_jun_sep | difference_f |
|---|---|---|---|---|---|
| AL | Average daily temperature | 79.20 | 66 | 78.08 | 1.12 |
| AL | Average daily high temperature | 90.02 | 66 | 88.98 | 1.04 |
| AL | Average daily low temperature | 68.46 | 66 | 67.31 | 1.15 |
| FL | Average daily temperature | 81.39 | 66 | 81.08 | 0.31 |
| FL | Average daily high temperature | 91.13 | 66 | 90.68 | 0.45 |
| FL | Average daily low temperature | 71.97 | 66 | 71.53 | 0.44 |
| LA | Average daily temperature | 81.69 | 59 | 80.67 | 1.02 |
| LA | Average daily high temperature | 91.55 | 59 | 90.61 | 0.94 |
| LA | Average daily low temperature | 71.89 | 59 | 70.57 | 1.32 |
| MS | Average daily temperature | 80.14 | 73 | 78.82 | 1.32 |
| MS | Average daily high temperature | 90.56 | 73 | 89.66 | 0.90 |
| MS | Average daily low temperature | 69.40 | 73 | 67.93 | 1.47 |
| TX | Average daily temperature | 82.35 | 247 | 80.96 | 1.39 |
| TX | Average daily high temperature | 93.82 | 247 | 92.63 | 1.19 |
| TX | Average daily low temperature | 70.84 | 247 | 69.30 | 1.54 |

September is cooler than June-August in every state and variable, so the wider June-September window sits below the June-August window. The prespecified warm season for this project is June-September; both are reported so the choice is visible.

## A defect the previous package did not check for

18 raw daily county-level records out of 8,678,621 have a **daily high below the same day's daily low**.

On 13 of the 18, the county daily high and the county daily low were averaged over **different numbers of stations**. The source file aggregates each element over whatever stations reported that element that day, so a county's high and its low can describe different station sets and are not guaranteed to be internally consistent. The station observations are not in question; the county aggregation is.

**Declared handling.** The affected county-dates are quarantined from the analysis panel in full, written unaltered to `qa/quarantined_inverted_daily_records.csv`, and reported here. The raw input files are not modified. 0 of them fall inside the Texas 2015-2025 classification window, so no Part 2 or Part 3 result depends on this choice. The handling rule is `r00_config.INVERTED_RECORD_ACTION` and is an open item for advisor sign-off.

| state | county_fips | county_name | date | tmax_f | tmax_f_nstations | tmin_f | tmin_f_nstations | daily_low_minus_daily_high_f |
|---|---|---|---|---|---|---|---|---|
| TX | 48057 | Calhoun | 1995-10-29 00:00:00 | 51.08 | 1.00 | 66.02 | 1.00 | 14.94 |
| TX | 48057 | Calhoun | 1997-11-27 00:00:00 | 64.94 | 2.00 | 69.08 | 1.00 | 4.14 |
| TX | 48057 | Calhoun | 1999-03-17 00:00:00 | 71.96 | 2.00 | 74.48 | 2.00 | 2.52 |
| TX | 48057 | Calhoun | 2001-04-07 00:00:00 | 77.00 | 1.00 | 81.50 | 2.00 | 4.50 |
| TX | 48131 | Duval | 1983-12-06 00:00:00 | 48.02 | 1.00 | 50.00 | 1.00 | 1.98 |
| TX | 48131 | Duval | 1983-12-17 00:00:00 | 35.06 | 1.00 | 37.49 | 2.00 | 2.43 |
| TX | 48131 | Duval | 1983-12-20 00:00:00 | 35.06 | 1.00 | 37.94 | 1.00 | 2.88 |
| TX | 48131 | Duval | 1986-12-18 00:00:00 | 57.56 | 2.00 | 60.08 | 1.00 | 2.52 |
| TX | 48193 | Hamilton | 1982-11-25 00:00:00 | 35.06 | 1.00 | 37.94 | 1.00 | 2.88 |
| TX | 48209 | Hays | 1995-02-12 00:00:00 | 37.94 | 1.00 | 41.99 | 2.00 | 4.05 |
| TX | 48253 | Jones | 1995-03-02 00:00:00 | 24.08 | 1.00 | 24.44 | 2.00 | 0.36 |
| TX | 48309 | McLennan | 2001-01-01 00:00:00 | 30.92 | 2.00 | 30.98 | 3.00 | 0.06 |
| TX | 48321 | Matagorda | 1997-01-07 00:00:00 | 41.99 | 2.00 | 48.26 | 3.00 | 6.27 |
| TX | 48321 | Matagorda | 1997-01-13 00:00:00 | 33.08 | 2.00 | 38.30 | 3.00 | 5.22 |
| TX | 48481 | Wharton | 2000-01-31 00:00:00 | 50.99 | 2.00 | 51.98 | 1.00 | 0.99 |
| TX | 48501 | Yoakum | 1987-02-19 00:00:00 | 33.08 | 1.00 | 34.97 | 2.00 | 1.89 |
| LA | 22071 | Orleans | 1979-06-01 00:00:00 | 44.51 | 2.00 | 75.02 | 1.00 | 30.51 |
| MS | 28045 | Hancock | 2016-01-01 00:00:00 | 51.08 | 1.00 | 52.07 | 2.00 | 0.99 |

## What is flagged, and on what rule

| flag | n_records | denominator | rule | action |
|---|---|---|---|---|
| abrupt_annual_discontinuity_with_station_change | 8 | 58359 | >= 5 degF year-on-year change in the annual county value AND a >= 1.5x change in the mean number of contributing stations, in consecutive qualifying years | flagged for human review; no value altered |
| abrupt_annual_discontinuity_without_station_change | 109 | 58359 | >= 5 degF year-on-year change with no matching station change | flagged; most are genuine interannual variability |
| warm_season_daily_high_only_plausible_as_celsius | 0 | 82635 | qualifying June-September monthly average daily high below 50 degF | unit-conversion check; flagged, never converted |
| insufficient_annual_coverage | 6672 | 65031 | fewer than 328 valid daily county-level observations in the year | excluded from annual summaries, retained in the table |
| insufficient_monthly_coverage | 25437 | 763988 | fewer than 25 valid daily county-level observations in the month | excluded from monthly summaries, retained in the table |

Nothing above was altered, deleted or imputed. Coverage flags govern which records enter a summary; the records themselves stay in `tables/county_annual_temperature.csv` and `tables/county_monthly_temperature.csv` with their flags attached.

## Record extent and coverage

| state | state_name | daily_county_level_observations | counties_in_file | first_date | last_date | pct_daily_records_with_daily_high | annual_observations_meeting_coverage | annual_observations_total |
|---|---|---|---|---|---|---|---|---|
| TX | Texas | 4220797 | 254 | 1979-01-01 | 2025-12-31 | 90.73 | 9984 | 10848 |
| LA | Louisiana | 1048350 | 65 | 1979-01-01 | 2025-12-31 | 77.30 | 2140 | 2296 |
| MS | Mississippi | 1284436 | 82 | 1979-01-01 | 2025-12-31 | 81.79 | 2641 | 3058 |
| AL | Alabama | 1071761 | 67 | 1979-01-01 | 2025-12-31 | 85.62 | 2341 | 2634 |
| FL | Florida | 1053259 | 67 | 1979-01-01 | 2025-12-31 | 95.33 | 2609 | 2844 |

Full monthly distributions across counties, including the interquartile range, minimum, maximum, contributing county count, contributing monthly-summary count and the percentage of monthly records passing the coverage requirement, are in `tables/revised_temperature_monthly_sanity_check.csv`.
