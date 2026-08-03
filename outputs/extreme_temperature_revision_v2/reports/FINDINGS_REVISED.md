# Revised findings

Revision v2 of the extreme-temperature package. Every number here is recomputed; nothing is carried over from the previous findings. The original package is unchanged and remains at `outputs/extreme_temp_tests/`.

The analysis uses a county-by-day panel in which each record represents one county on one calendar date.

**Epistemic level: descriptive.** Period differences are differences, not trends. Agreement between definitions is agreement, not accuracy. No health outcome appears anywhere in this package.

---

## Part 1 - Gulf-state temperature, 1979-2025

### The three variables are not interchangeable

| state | Average daily high temperature | Average daily low temperature | Average daily temperature |
|---|---|---|---|
| Alabama | 89.0 | 67.3 | 78.1 |
| Florida | 90.7 | 71.5 | 81.1 |
| Louisiana | 90.6 | 70.6 | 80.7 |
| Mississippi | 89.7 | 67.9 | 78.8 |
| Texas | 92.6 | 69.3 | 81.0 |

June-September **average daily highs** run 89 to 93 degF. June-September **average daily lows** run 67 to 72 degF - below 75 degF in every state. That is ordinary for inland, northern, rural and elevated counties and is not a data-quality signal. A rule that every summer temperature must exceed 75 degF would flag the average daily low across the entire region; it is not applied here.

### Period differences, corrected

The previous decadal table was computed as a median over all pooled annual county-level observations, so a county with ten qualifying years counted ten times and one with two counted twice. Recomputed with every county contributing exactly one value per period:

| state | current (pooled) | current counties | revised Sample A | Sample A 95% interval | Sample A counties | revised Sample B | Sample B counties |
|---|---|---|---|---|---|---|---|
| Texas | 2.04 | 195 | 1.94 | 1.53 to 2.48 | 140 | 2.27 | 148 |
| Louisiana | 1.75 | 37 | 2.08 | 1.79 to 2.64 | 26 | 2.20 | 23 |
| Mississippi | 2.35 | 43 | 1.86 | 1.22 to 3.60 | 25 | 2.11 | 23 |
| Alabama | 1.38 | 44 | 1.62 | 0.94 to 2.64 | 28 | 1.17 | 35 |
| Florida | 1.17 | 49 | 1.53 | 0.55 to 2.12 | 37 | 1.30 | 36 |

The point estimates move modestly. The interval is the new information: it is 0.8 to 2.5 degF wide, and it overlaps zero in no state but overlaps between states in every pairing, so the previous package's ordering of states by 'warming' is not supported.

### Level and difference are different quantities

June-September remains the hottest part of the year in every state. The largest period differences are in the cool season. Both statements are true and they do not conflict: a month that changed more between two periods is not thereby hotter. Figure E4 keeps them in separate rows and shades the same months in both.

### Slopes, reported separately from differences

The annual state summary increased by 0.32 to 0.54 degF per decade across the five states under this descriptive model (Theil-Sen on the annual median across counties, consistent-county sample). This result may reflect climate change, station-network composition, data coverage, or remaining inhomogeneity and does not isolate causation.

---

## Part 2 - county-specific relative warm spells

These are **relative warm spells**, not heatwaves. The rule is year-round, applies no absolute heat condition, and cool-season days qualify. The threshold is the **county- and calendar-date-specific** historical percentile, not the percentile of the county's year-round distribution.

| definition | median classified days per county-year | median events per county-year | median event duration (days) | % Jun-Sep | % May+Oct | % Nov-Apr | peak month |
|---|---|---|---|---|---|---|---|
| TX-P80-D2 | 71.0 | 19.0 | 3.0 | 36.5 | 18.3 | 45.1 | Oct |
| TX-P80-D3 | 54.0 | 11.0 | 4.0 | 40.3 | 19.0 | 40.6 | Oct |
| TX-P80-D5 | 31.0 | 4.0 | 7.0 | 49.0 | 21.0 | 30.0 | Aug |
| TX-P85-D2 | 51.0 | 15.0 | 3.0 | 37.1 | 18.6 | 44.3 | Oct |
| TX-P85-D3 | 38.0 | 8.0 | 4.0 | 41.4 | 19.6 | 39.0 | Aug |
| TX-P85-D5 | 20.0 | 3.0 | 7.0 | 50.5 | 21.2 | 28.3 | Aug |
| TX-P90-D2 | 33.0 | 10.0 | 3.0 | 37.6 | 18.9 | 43.5 | Aug |
| TX-P90-D3 | 23.0 | 5.0 | 4.0 | 42.5 | 20.0 | 37.5 | Aug |
| TX-P90-D5 | 12.0 | 2.0 | 6.0 | 51.3 | 21.0 | 27.7 | Aug |

### The seasonal split, in three categories

The previous package reported one number: the share outside June-September. Splitting the shoulder months out changes the reading. Across the nine definitions, June-September carries 37 to 51% of classified days, May and October carry 18 to 21%, and November-April carry 28 to 45%. The shoulder months are not a rounding detail: they are close to a fifth of all classified days, and merging them with November-April overstates how much of the signal is genuinely off-season.

### The monthly rate is not flat

The previous package described the monthly profile as 'close to flat all year'. Under a prespecified criterion - highest-to-lowest monthly ratio at most 1.5 AND coefficient of variation at most 0.15 - **0 of 33 constructs meet it**. Among the 29 constructs whose quietest month is non-zero the ratio runs from 1.9 to 36387.8; the remaining 4 have at least one month with NO classified days at all, which is the strongest possible departure from flatness. The curves are not flat and are not described as flat.

---

## Part 3 - absolute daily-high gates

80 degF and 90 degF are **absolute daily-high gates** chosen for this sensitivity test. They are not National Weather Service advisory thresholds, and a gate is not a correction: it changes the construct from a purely relative warm spell to a hybrid relative-and-absolute heat event.

| definition | gate (degF) | % days retained | Jaccard vs no gate | % Jun-Sep, no gate | % Jun-Sep, with gate | county retention, median | county retention, 10th pct | county retention, 90th pct |
|---|---|---|---|---|---|---|---|---|
| TX-P90-D3 | 80.00 | 81.94 | 0.82 | 42.52 | 51.89 | 81.27 | 67.62 | 92.28 |
| TX-P90-D3 | 90.00 | 57.52 | 0.58 | 42.52 | 73.86 | 58.62 | 41.82 | 68.70 |

The 90 degF gate moves the June-September share from 43% to 74% and keeps 58% of the classified days. The 80 degF gate keeps 82% and moves the share only to 52%.

**The gate does not bite equally everywhere.** For the 90 degF gate the retained share runs from 42% at the 10th percentile of counties to 69% at the 90th. A gate redistributes exposure geographically as well as seasonally, concentrating it in the hottest counties.

### An 80 degF absolute rule is not an extreme-heat criterion

| definition | median classified days per county-year | median events per county-year | median event duration (days) | classified days per 1,000 valid records | % Jun-Sep |
|---|---|---|---|---|---|
| TX->80-D2 | 184.0 | 13.0 | 4.0 | 518.0 | 62.5 |
| TX->80-D3 | 177.0 | 10.0 | 6.0 | 498.0 | 64.8 |
| TX->80-D5 | 165.0 | 6.0 | 10.0 | 463.9 | 69.3 |
| TX->90-D2 | 100.0 | 10.0 | 5.0 | 275.0 | 87.6 |
| TX->90-D3 | 96.0 | 7.0 | 7.0 | 262.4 | 89.5 |
| TX->90-D5 | 88.0 | 5.0 | 11.0 | 241.2 | 91.7 |

A daily high above 80 degF for at least two consecutive days classifies 52% of every valid daily county-level observation in the record, with a median of 184 classified days per county per year. Whatever that measures, it is not an extreme. The longest single run in the whole package is 243 consecutive days.

---

## What is new in this revision, and was not visible before

1. **A county-level spread the previous caption denied.** For REL_TX_P90_D3_W15, cumulative classified days range from 59 to 747 across counties, a factor of 12.7. The claim that a relative percentile rule 'flags a similar number of days everywhere by construction' is not supported.
2. **18 inverted daily records** - a daily high below the same day's daily low - of which 13 have their high and low averaged over different station sets. The previous package does not check for this.
3. **The archived thresholds do not survive a default CSV read.** 99,405 of 3,067,812 values are misparsed by the pandas default float parser, which flips classification on knife-edge county-dates.
4. **There is no external benchmark.** The only candidate is byte-identical to the project data on all 2,938,070 matched records. Nothing in this project's county temperature values has been externally validated.
5. **43,392 events run longer than 15 days** and are now audited and classified; 23190 are flagged station-composition-sensitive and 6192 imputation-sensitive.

## Caveats worth carrying forward

- **Temperature source.** No independent temperature product is available in this repository, so the county aggregation is unvalidated. Earlier work found anchor-station against multi-station composite agreeing at only 0.45 to 0.73, which is larger than most of the definition effects measured here. This remains the dominant unresolved risk.
- **Station-network composition.** The reporting network changes over the record. Samples A and B control which counties are compared but not which stations are inside a county in a given year; the stable-station sensitivity is thin outside Texas and Florida (Louisiana 1 county, Mississippi 0, Alabama 2).
- **Gap-filling.** 22 of 254 Texas counties have no observed temperature at all and are carried entirely by interpolation. They are marked everywhere and a sensitivity excluding them is reported, but their classified days describe the interpolation as much as the county.
- **Different inputs for Part 1 and Parts 2-3.** Part 1 uses the observed record; Parts 2 and 3 use the gap-filled table, as the rest of the project does. The two are not on the same input by design, and no quantity is carried between them.
- **Sample selection.** Samples A and B exclude between a third and three quarters of counties depending on the state, and the excluded counties are disproportionately rural and short-record. This is a coverage restriction, not a random sample.
- **Knife-edge comparisons.** With a strict `>` comparison, a county-date sitting exactly on its threshold is decided by the last bit of a stored float. This affects a handful of records but is a reproducibility hazard for anyone reusing the archived thresholds.
- **No health outcome anywhere in this package**, so nothing here can identify a correct definition, and agreement between definitions is not evidence of accuracy.

See `reports/FINAL_REPORT.md` for the full audit, the recommended primary definition and the next actions.
