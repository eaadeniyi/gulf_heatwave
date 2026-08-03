# Long-event audit

Every event longer than 15 days is listed in `tables/long_event_audit.csv` with the evidence needed to judge it. **No event is deleted on the basis of its length.** A long run is evidence about the RULE that produced it as much as about the data.

## How many, and under which construct

| construct_family | construct_id | long_events | longest_event_days | median_long_event_days | all_events | pct_of_events_that_are_long |
|---|---|---|---|---|---|---|
| absolute | ABS_TX_A80_D2 | 5498 | 243 | 52.00 | 37261 | 14.76 |
| absolute | ABS_TX_A80_D3 | 5498 | 243 | 52.00 | 27024 | 20.34 |
| absolute | ABS_TX_A80_D5 | 5498 | 243 | 52.00 | 16744 | 32.84 |
| absolute | ABS_TX_A90_D2 | 4803 | 148 | 26.00 | 27360 | 17.55 |
| absolute | ABS_TX_A90_D3 | 4803 | 148 | 26.00 | 20935 | 22.94 |
| absolute | ABS_TX_A90_D5 | 4803 | 148 | 26.00 | 14619 | 32.85 |
| relative | REL_TX_P80_D5_W15 | 732 | 69 | 19.00 | 13312 | 5.50 |
| relative | REL_TX_P80_D3_W15 | 732 | 69 | 19.00 | 32503 | 2.25 |
| relative | REL_TX_P80_D2_W15 | 732 | 69 | 19.00 | 53220 | 1.38 |
| hybrid | HYB_TX_P80_D3_A80_W15 | 725 | 69 | 19.00 | 23342 | 3.11 |
| hybrid | HYB_TX_P80_D2_A80_W15 | 725 | 69 | 19.00 | 38323 | 1.89 |
| hybrid | HYB_TX_P80_D5_A80_W15 | 725 | 69 | 19.00 | 10369 | 6.99 |
| hybrid | HYB_TX_P80_D2_A90_W15 | 659 | 69 | 19.00 | 21741 | 3.03 |
| hybrid | HYB_TX_P80_D5_A90_W15 | 659 | 69 | 19.00 | 7239 | 9.10 |
| hybrid | HYB_TX_P80_D3_A90_W15 | 659 | 69 | 19.00 | 14263 | 4.62 |
| relative | REL_TX_P85_D2_W15 | 467 | 66 | 18.00 | 42631 | 1.10 |
| relative | REL_TX_P85_D3_W15 | 467 | 66 | 18.00 | 24535 | 1.90 |
| relative | REL_TX_P85_D5_W15 | 467 | 66 | 18.00 | 9457 | 4.94 |
| hybrid | HYB_TX_P85_D2_A80_W15 | 466 | 66 | 18.00 | 32060 | 1.45 |
| hybrid | HYB_TX_P85_D5_A80_W15 | 466 | 66 | 18.00 | 7701 | 6.05 |
| hybrid | HYB_TX_P85_D3_A80_W15 | 466 | 66 | 18.00 | 18547 | 2.51 |
| hybrid | HYB_TX_P85_D3_A90_W15 | 440 | 66 | 18.00 | 11615 | 3.79 |
| hybrid | HYB_TX_P85_D2_A90_W15 | 440 | 66 | 18.00 | 18569 | 2.37 |
| hybrid | HYB_TX_P85_D5_A90_W15 | 440 | 66 | 18.00 | 5526 | 7.96 |
| hybrid | HYB_TX_P90_D3_A80_W15 | 227 | 47 | 18.00 | 13301 | 1.71 |
| hybrid | HYB_TX_P90_D2_A80_W15 | 227 | 47 | 18.00 | 24189 | 0.94 |
| relative | REL_TX_P90_D2_W15 | 227 | 47 | 18.00 | 30503 | 0.74 |
| relative | REL_TX_P90_D3_W15 | 227 | 47 | 18.00 | 16701 | 1.36 |
| hybrid | HYB_TX_P90_D5_A80_W15 | 227 | 47 | 18.00 | 5043 | 4.50 |
| relative | REL_TX_P90_D5_W15 | 227 | 47 | 18.00 | 6005 | 3.78 |
| hybrid | HYB_TX_P90_D5_A90_W15 | 220 | 47 | 18.00 | 3723 | 5.91 |
| hybrid | HYB_TX_P90_D2_A90_W15 | 220 | 47 | 18.00 | 14366 | 1.53 |
| hybrid | HYB_TX_P90_D3_A90_W15 | 220 | 47 | 18.00 | 8613 | 2.55 |

## Classification

| classification | events | share_pct |
|---|---|---|
| station_composition_sensitive | 23190 | 53.44 |
| physically_plausible | 13014 | 29.99 |
| imputation_sensitive | 6192 | 14.27 |
| requires_manual_review | 966 | 2.23 |
| threshold_driven | 30 | 0.07 |

Rules, applied in code and reproducible from `tables/long_event_audit.csv`:

- **physically_plausible** - peak daily high at or above 90 degF, mean exceedance at least 2 degF per day, no imputation or station-composition flag. For the absolute family, any event without an imputation or station-composition flag, because an absolute rule has no exceedance to measure against a percentile.
- **threshold_driven** - mean exceedance below 1 degF per day. The run persists because the daily highs sit just above a low threshold, not because the weather is extreme.
- **imputation_sensitive** - at least half the event's days are IDW gap-filled, or the county has no observed temperature at all.
- **station_composition_sensitive** - the number of contributing stations changes inside the event window, or the county is carried by a single station.
- **requires_manual_review** - no rule fired, or more than one fired.

## The longest events

| event_id | construct_id | county_name | event_start_date | event_end_date | event_duration_days | event_peak_temperature_f | mean_exceedance_per_day_f | imputed_share_of_event | audit_classification |
|---|---|---|---|---|---|---|---|---|---|
| 48_427_2025_006_ABS_TX_A80_D2 | ABS_TX_A80_D2 | Starr | 2025-03-01 | 2025-10-29 | 243 | 107.06 | 16.26 | 0.06 | station_composition_sensitive |
| 48_427_2025_004_ABS_TX_A80_D3 | ABS_TX_A80_D3 | Starr | 2025-03-01 | 2025-10-29 | 243 | 107.06 | 16.26 | 0.06 | station_composition_sensitive |
| 48_427_2025_002_ABS_TX_A80_D5 | ABS_TX_A80_D5 | Starr | 2025-03-01 | 2025-10-29 | 243 | 107.06 | 16.26 | 0.06 | station_composition_sensitive |
| 48_131_2017_011_ABS_TX_A80_D2 | ABS_TX_A80_D2 | Duval | 2017-03-17 | 2017-10-24 | 222 | 104.00 | 12.90 | 0.00 | station_composition_sensitive |
| 48_131_2017_006_ABS_TX_A80_D3 | ABS_TX_A80_D3 | Duval | 2017-03-17 | 2017-10-24 | 222 | 104.00 | 12.90 | 0.00 | station_composition_sensitive |
| 48_131_2017_002_ABS_TX_A80_D5 | ABS_TX_A80_D5 | Duval | 2017-03-17 | 2017-10-24 | 222 | 104.00 | 12.90 | 0.00 | station_composition_sensitive |
| 48_427_2022_006_ABS_TX_A80_D2 | ABS_TX_A80_D2 | Starr | 2022-03-14 | 2022-10-18 | 219 | 108.02 | 17.95 | 0.00 | station_composition_sensitive |
| 48_427_2022_003_ABS_TX_A80_D3 | ABS_TX_A80_D3 | Starr | 2022-03-14 | 2022-10-18 | 219 | 108.02 | 17.95 | 0.00 | station_composition_sensitive |
| 48_427_2022_001_ABS_TX_A80_D5 | ABS_TX_A80_D5 | Starr | 2022-03-14 | 2022-10-18 | 219 | 108.02 | 17.95 | 0.00 | station_composition_sensitive |
| 48_215_2024_008_ABS_TX_A80_D2 | ABS_TX_A80_D2 | Hidalgo | 2024-04-24 | 2024-11-27 | 218 | 105.84 | 15.03 | 0.00 | station_composition_sensitive |
| 48_215_2024_007_ABS_TX_A80_D3 | ABS_TX_A80_D3 | Hidalgo | 2024-04-24 | 2024-11-27 | 218 | 105.84 | 15.03 | 0.00 | station_composition_sensitive |
| 48_215_2024_005_ABS_TX_A80_D5 | ABS_TX_A80_D5 | Hidalgo | 2024-04-24 | 2024-11-27 | 218 | 105.84 | 15.03 | 0.00 | station_composition_sensitive |
| 48_297_2025_007_ABS_TX_A80_D2 | ABS_TX_A80_D2 | Live Oak | 2025-04-09 | 2025-11-09 | 215 | 105.98 | 16.25 | 0.00 | physically_plausible |
| 48_489_2025_008_ABS_TX_A80_D2 | ABS_TX_A80_D2 | Willacy | 2025-04-10 | 2025-11-10 | 215 | 98.51 | 11.39 | 0.00 | station_composition_sensitive |
| 48_297_2025_007_ABS_TX_A80_D3 | ABS_TX_A80_D3 | Live Oak | 2025-04-09 | 2025-11-09 | 215 | 105.98 | 16.25 | 0.00 | physically_plausible |
| 48_489_2025_005_ABS_TX_A80_D3 | ABS_TX_A80_D3 | Willacy | 2025-04-10 | 2025-11-10 | 215 | 98.51 | 11.39 | 0.00 | station_composition_sensitive |
| 48_297_2025_006_ABS_TX_A80_D5 | ABS_TX_A80_D5 | Live Oak | 2025-04-09 | 2025-11-09 | 215 | 105.98 | 16.25 | 0.00 | physically_plausible |
| 48_489_2025_004_ABS_TX_A80_D5 | ABS_TX_A80_D5 | Willacy | 2025-04-10 | 2025-11-10 | 215 | 98.51 | 11.39 | 0.00 | station_composition_sensitive |
| 48_127_2024_007_ABS_TX_A80_D2 | ABS_TX_A80_D2 | Dimmit | 2024-04-24 | 2024-11-20 | 211 | 109.04 | 16.02 | 0.00 | station_composition_sensitive |
| 48_273_2024_005_ABS_TX_A80_D2 | ABS_TX_A80_D2 | Kleberg | 2024-04-24 | 2024-11-20 | 211 | 105.53 | 13.88 | 0.00 | station_composition_sensitive |
| 48_127_2024_006_ABS_TX_A80_D3 | ABS_TX_A80_D3 | Dimmit | 2024-04-24 | 2024-11-20 | 211 | 109.04 | 16.02 | 0.00 | station_composition_sensitive |
| 48_273_2024_005_ABS_TX_A80_D3 | ABS_TX_A80_D3 | Kleberg | 2024-04-24 | 2024-11-20 | 211 | 105.53 | 13.88 | 0.00 | station_composition_sensitive |
| 48_127_2024_005_ABS_TX_A80_D5 | ABS_TX_A80_D5 | Dimmit | 2024-04-24 | 2024-11-20 | 211 | 109.04 | 16.02 | 0.00 | station_composition_sensitive |
| 48_273_2024_005_ABS_TX_A80_D5 | ABS_TX_A80_D5 | Kleberg | 2024-04-24 | 2024-11-20 | 211 | 105.53 | 13.88 | 0.00 | station_composition_sensitive |
| 48_061_2024_007_ABS_TX_A80_D2 | ABS_TX_A80_D2 | Cameron | 2024-04-24 | 2024-11-19 | 210 | 100.67 | 10.95 | 0.00 | station_composition_sensitive |

Durations are integer counts of consecutive calendar dates. Where a median duration falls between two integers it is a median ACROSS events; no individual event lasts a fraction of a day.

## What the long events say about the rules

- The longest runs in the whole package come from the ABSOLUTE family. The longest is 243 days. A rule of the form 'daily high above 80 degF for at least two consecutive days' will run for most of a Texas summer by construction, which is a statement about the rule, not a defect in the data.
- Long RELATIVE warm spells are more interesting, because a walk-forward percentile threshold should be exceeded about (100 - p)% of the time. 4278 relative warm spells run beyond 15 days; 9 of those are classified threshold_driven, meaning the daily highs clear the threshold by under 1 degF per day on average.

Per-day detail for the longest 150 events in each family - daily high, threshold, exceedance, gate status, observed or imputed status, contributing station count, month boundaries and missing values - is in `event_audits/long_event_daily_detail_<family>.csv`. That cap is stated rather than applied silently; the summary table above covers every long event.
