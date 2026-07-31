# Extreme-temperature tests - findings

Three pieces of work: a temperature description for the five Gulf states, a county-relative daily-maximum-temperature grid, and the absolute-floor test. Parts 2 and 3 run on **TX** (2015-2025), the pilot state, on the same input table, walk-forward baseline and code path as the published definitions.

Every figure and table referenced here is in `figures/` and `tables/`; provenance and QA are in `qa/`. Rebuild with `python scripts/e01_...` through `e04_...` (about 8 minutes in total).

---

## Part 1 - Gulf-state temperature, 1979-2025

**Record and coverage.** All five states span 1979-01-01 to 2025-12-31. 2026 is excluded everywhere as a partial year, leaving 47 complete years. Tmax is present on 77-95% of county-days depending on the state (TX 91%, LA 77%, MS 82%, AL 86%, FL 95%), so the annual summaries use only county-years with at least 328 valid days.

**The reporting network shrinks, and it matters.** Counties clearing the coverage gate fall over the record (Figure E1, bottom panel). Comparing decades therefore uses a BALANCED panel - counties clearing the gate in every decade: TX 195, LA 37, MS 43, AL 44, FL 49. The difference is not cosmetic: Alabama's Tmax warming since the 1980s reads **+1.38 degF** on the balanced panel but only **+0.80 degF** on whichever counties happened to report, and Florida's Tmin warming reads +3.29 against +2.65. An unbalanced decadal comparison in this data is partly a station-network trend.

**Levels.** Median county-year Tmax over 1979-2025: TX 77.8, LA 77.6, MS 75.5, AL 75.0, FL 82.0. But the spread WITHIN a state is as large as the gap between states - Texas county-years span roughly 64-91 degF - so a state mean is a weak summary and the county remains the substantive unit (Figure E2).

**Decadal change, 1980s to 2020-2025* (balanced panel, degF):**

| state | Tmax | Tmin | Tmean |
|---|---|---|---|
| TX | +2.04 | +2.71 | +2.16 |
| LA | +1.75 | +2.64 | +2.56 |
| MS | +2.35 | +3.43 | +2.75 |
| AL | +1.38 | +2.71 | +1.68 |
| FL | +1.17 | +3.29 | +2.05 |

**Tmin is warming faster than Tmax in every one of the five states** (Figure E3). The gap is largest in Florida (+3.29 against +1.17) and Alabama (+2.71 against +1.38). The diurnal range is narrowing, which is directly relevant to this project: a night-time (Tmin) definition and a day-time (Tmax) definition are not just selecting different days, they are tracking quantities that are changing at different rates.

**Summer is the hottest season; the cool season is the fastest-warming one. These are two different quantities and they do not conflict.** Figure E4 keeps them in separate rows for that reason. In LEVEL, Jul-Aug TXm exceeds Dec-Feb TXm by 20-34 degF across the five states - June to September is unambiguously the hot part of the year. In CHANGE since the 1980s, Jul-Aug moved by -0.24 to +0.70 degF while Nov-Mar rose +2.10 to +3.43 degF, i.e. the cool season warmed **1.6-3.1 degF more** than mid-summer did. Jun-Sep still records the highest temperatures; it simply has not warmed much (`tables/e01_level_vs_change_summary.csv`).

Change in TXm (mean daily maximum temperature) by month, 1980s to 2020-2025*, balanced panel:

| state | Dec | Feb | Oct | Jul | Aug |
|---|---|---|---|---|---|
| TX | +6.2 | +1.0 | +3.8 | +0.4 | +1.0 |
| LA | +4.0 | +4.5 | +3.1 | +0.1 | +1.0 |
| MS | +4.9 | +4.8 | +3.4 | +0.4 | +0.1 |
| AL | +2.8 | +5.0 | +2.1 | +0.1 | -0.6 |
| FL | +0.8 | +3.7 | +0.0 | +0.4 | +0.6 |

December warmed **+6.2 degF in Texas** and +4.9 in Mississippi, and February +5.0 in Alabama, while June-August moved by at most +2.4 degF in any state and went NEGATIVE in 2 state-month combinations. This is the physical reason the year-round relative definitions load onto the cool season: the anomalies are largest where the warming is, and a walk-forward percentile threshold measures departure from each date's own history.

---

## Part 2 - county-relative daily maximum temperature

9 definitions (80th / 85th / 90th percentile x >= 2 / >= 3 / >= 5 consecutive days) at all four threshold windows = 36 runs. Reported at the `w15` window.

**Verification first.** Four of the nine cells already exist in the delivered definition grid. The rebuild reproduces all four exactly - 32/32 reconciliation checks pass on heatwave days and events - so the five new cells can be read directly alongside the earlier work.

**Per-county median heatwave days over 2015-2025:**

| percentile | >=2 days | >=3 days | >=5 days |
|---|---|---|---|
| 80th | 815 | 651 | 394 |
| 85th | 617 | 470 | 273 |
| 90th | 403 | 297 | 162 |

The two levers behave differently. The percentile moves the count smoothly (815 -> 403 days per county from the 80th to the 90th at >= 2 days, a factor of 2.0). The duration rule bites harder at the long end: at the 90th percentile, 403 days at >= 2 falls to 297 at >= 3 and 162 at >= 5, a factor of 2.5 from the shortest to the longest rule.

**The cool-season loading survives every one of the nine cells.** The share of heatwave days falling outside Jun-Sep runs from **49% to 63%** across the grid, and the monthly rate is close to flat all year (Figure E6). A longer persistence rule helps a little - 62% outside Jun-Sep at >= 2 days versus 49% at >= 5 - but never resolves it, and the peak month is October or August depending on the cell, never a mid-summer month for the looser cells. No choice of percentile or duration fixes this, which is what motivates Part 3.

---

## Part 3 - absolute floors at 80 degF and 90 degF

### 3a. The floor as a GATE on the relative rule

A day must clear both its own county/calendar percentile threshold AND the absolute floor. 18 runs at the `w15` window (Figure E7, `tables/e03_floor_effect.csv`).

| floor | days retained | cool-season share (outside Jun-Sep) | day-level agreement with the unfloored version |
|---|---|---|---|
| none | 100% | 49-63% | 1.00 |
| 80 degF | 75-86% | 40-54% | 0.75-0.86 |
| 90 degF | 49-66% | 20-30% | 0.49-0.66 |

**The 90 degF floor largely resolves the cool-season problem; the 80 degF floor does not.** For `TMAX_P90_2D` the share outside Jun-Sep falls from 62% to 30% with a 90 degF floor but only to 54% with 80 degF. The monthly profiles (Figure E7 C-D) show the mechanism: a 90 degF floor drives November through March to essentially zero and leaves a single August-peaked season, whereas the unfloored definition peaks in **December**.

It is not free. A 90 degF floor discards **34-51% of the classified days**, and it changes what the definition means: the output is no longer 'unusual for this date' but 'unusual for this date AND hot in absolute terms'. That is a different construct and has to be described as one. Its geography also changes (Figure E9): a county-relative rule flags a broadly similar number of days everywhere by construction, while a floor concentrates exposure in the hottest counties - the retained share falls with latitude and elevation.

### 3b. The floor as an ABSOLUTE-ONLY definition

Tmax > floor with no percentile at all. An absolute rule has no baseline and therefore no threshold window - there is nothing to pool - so this is 6 runs (2 floors x 3 durations), Figure E8.

| definition | per-county median days | % of all days in 2015-2025 | outside Jun-Sep |
|---|---|---|---|
| TMAX_ABS80_2D | 2040 | 51 | 37.5 |
| TMAX_ABS90_2D | 1104 | 27 | 12.4 |

**An 80 degF floor is not an extreme-heat criterion in Texas.** Tmax above 80 degF for two or more consecutive days flags a median of **2040 county-days per county**, which is **51% of every day in the study period**. Whatever that measures, it is not an extreme. The 90 degF rule flags 1104 days (27% of all days) and is strongly seasonal (12% outside Jun-Sep), so it behaves like a hazard-style summer definition.

**The absolute and relative constructs are not variants of one another.** Day-level agreement between them is only **Jaccard 0.08-0.28** across every pairing tested. They flag largely different county-dates: the absolute rule fires in the hottest weeks of the hottest counties, the relative rule fires whenever a county departs from its own normal for the date, including in winter. Choosing between them is a choice of research question, not a sensitivity setting.

---

## What this means for the open decisions

1. **The floor/season decision now has numbers.** A 90 degF Tmax floor takes the cool-season share from ~59% to ~24% and costs about half the classified days; an 80 degF floor is too low to change the character of the definition in Texas. If the goal is an occupational heat-exposure measure that a reader will interpret as hazardous heat, the 90 degF gate (or a declared season) is the option the data supports - and the definition must then be renamed to reflect that it is part absolute.
2. **Part 1 explains why the problem existed.** Cool-season warming (December +6.2 degF in Texas) far exceeds summer warming (July +0.4), so a walk-forward relative threshold necessarily finds its largest departures outside summer. This is a property of the regional climate trend, not a bug in the classification.
3. **Tmin warming exceeds Tmax warming in all five states**, which strengthens the earlier finding that a Tmin definition is a different construct rather than a sensitivity case - the two metrics are diverging over time, not just disagreeing day to day.
4. **>= 5 consecutive days is a genuine third option** on the duration axis, not a minor extension: it cuts per-county exposure by roughly 2.5x relative to >= 2 days at the 90th percentile and lowers the cool-season share by about 14 points, because long runs are harder to sustain out of season.

---

## Caveats and choices worth knowing

- **Part 1 uses the OBSERVED GHCN record, not the IDW gap-filled table.** The question was what the record is over its available duration, so gap-filled values would describe the interpolation. The cost is uneven coverage, handled with the coverage gate and the balanced panel. Parts 2 and 3 use the pipeline's gap-filled county-day table, as every other definition in this project does - so Part 1 and Parts 2-3 are NOT on the same input, by design.
- **Parts 2 and 3 are Texas only.** Both are state-agnostic and run for another Gulf state as soon as that state's county-day table is built (`pipeline/p01_build_countyday_idw.py`); only Texas has one today.
- **Comparison operators.** The relative rule uses a strict `>` as everywhere in this project; the floor-as-gate uses `>=` (matching the pipeline's existing floor implementation) and the absolute-only rule uses `>` ('exceeding'). That is not purely cosmetic: 643 of 1,020,572 evaluable county-days sit exactly on the 80 degF floor and 2 on the 90 degF floor, because a county-day Tmax is an average over the county's reporting stations rather than a raw quantised reading. The affected share is 0.063% and changes no conclusion here, but it is recorded in `qa/e02_floor_operator_check.csv` rather than assumed away.
- **The floored variants were run at the primary window only.** The window was the least consequential of the four axes in the definition-comparison package (median Jaccard 0.687), and the floor is already crossed with 9 definitions x 2 floors. The other three windows are one config edit away.
- **Nothing here uses a health outcome**, so nothing here can identify a correct definition. Jaccard is agreement between two definitions, never accuracy.
- **The temperature-source question is still unresolved and still dominates.** Earlier work found anchor-station versus multi-station composite temperature agreeing at only 0.45-0.73 - larger than most of the definition effects measured here. County-level results remain provisional until that is settled.
