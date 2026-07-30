# Decision table

A reading of the comparison, not a selection. **No injury, illness or other health outcome is used anywhere in this package**, and no figure in it can identify a correct definition - every quantity here is agreement or count, and neither is accuracy. The final primary definition must not be chosen using injury-outcome results.

Scope: 16 definitions x 4 windows, Texas, 2015-2025, 254 counties, primary window `w15`.

## PRIMARY CANDIDATE

**`MHI_P90_2D`, `TMAX_P90_2D`**

Middle percentile, shorter duration, day-time exposure pathway. Mean HI carries humidity, which matters for evaporative cooling during outdoor work; Tmax is the dry-bulb comparator and is the more transparent, more widely reproducible metric. At matched percentile and duration these two differ on most classified days (Jaccard 0.383 for the Tmax-vs-mean-HI pair) while counting almost the same number, so they are genuine alternatives rather than a robustness pair.

*Conditions before use:* Requires the floor/season decision to be made FIRST (both put 51-64% of heatwave days outside Jun-Sep), and requires the temperature-composite homogeneity question to be settled before any county-level use.

## PRIMARY CANDIDATE (CONTINUITY)

**`MHI_P85_2D`, `MHI_P95_2D`**

The two definitions already published by this project. Retaining one of them keeps the new work comparable with what has been reported; the re-run here reproduces the published results exactly, so continuity costs nothing analytically.

*Conditions before use:* The 85th flags roughly 3.2x the days of the 95th - a construct choice about how unusual a day must be, not a robustness setting. Choose deliberately, not by inheritance.

## SENSITIVITY CASE

**`TMAX_P85_2D`, `TMAX_P95_2D`, `TMAX_P85_3D`, `TMAX_P95_3D`, `MHI_P90_3D`, `TMAX_P90_3D`**

Single-axis variants of a primary candidate: the percentile ladder and the persistence rule. The percentile moves counts substantially (median 2.03x) and the duration rule is strictly nested - >=3-day heatwave days are a verified subset of >=2-day days - so both behave as interpretable sensitivity dials rather than new constructs.

*Conditions before use:* Report alongside the primary, never as an alternative headline. Duration sensitivities for mean HI are only available at the 90th percentile.

## SENSITIVITY CASE (WINDOW)

**`all definitions at w05 / month / month_pm7`**

The threshold window is the least consequential axis: median Jaccard 0.699 against the primary window over 96 matched pairs. Compared DIRECTLY, month and month_pm7 are near-duplicates (median Jaccard 0.886 over 16 pairs) while w05 vs w15 differ more (0.851). Window choice can be reported as a robustness check rather than explored as a design question.

*Conditions before use:* month_pm7 adds almost nothing beyond month and could be dropped from future rounds; w05 is the one window that differs enough to be worth retaining.

## DIFFERENT CONSTRUCT

**`TMIN_P85_2D`, `TMIN_P90_2D`, `TMIN_P95_2D`, `TMIN_P85_3D`, `TMIN_P90_3D`, `TMIN_P95_3D`**

Night-time minimum temperature measures absence of overnight recovery, not day-time work exposure. At matched percentile and duration Tmin and Tmax agree on only 0.250 of classified county-dates while differing in count by ~12%. The separation shows up in county ORDER as well, which nothing else in this package does: rank agreement is 0.96 within a metric family but only 0.38-0.56 (median 0.47) between the Tmax and Tmin families. Together that is the clearest evidence here that the metric selects a different phenomenon rather than a different amount of the same one.

*Conditions before use:* Do not report as a variant of a Tmax or mean-HI result, and do not average with them. If used, state the exposure pathway (no overnight recovery) explicitly.

## NOT TESTED

**`MHI_P85_3D`, `MHI_P95_3D`**

Never run. These two cells would complete the 3 x 3 x 2 factorial and are the reason the duration axis is estimated from 28 matched pairs rather than 60.

*Conditions before use:* One line each in config.GRID_DEFINITIONS; the thresholds they need are already cached, so running them is cheap. Never substitute zero or an interpolated value.

## NEEDS DATA-QUALITY VALIDATION

**`all Tmax and Tmin definitions`**

Two independent issues. (i) The exact-tie asymmetry: 1.13% (Tmax) and 1.44% (Tmin) of evaluable county-days sit exactly on their threshold because the input is quantised to 0.1 degC, against 0.00% for mean HI - so the strict `>` silently removes days from the temperature definitions only. (ii) 66 of 254 counties exceed the 10% imputation cut and 22 have no native station record at all.

*Conditions before use:* Quantify the `>` vs `>=` effect before comparing a temperature definition against mean HI on day-level agreement; resolve the anchor-vs-composite temperature question (earlier agreement 0.45-0.73) before any county ranking.

**`every definition in this package`**

All 16 are year-round and carry no absolute floor, so 51-64% of their heatwave days fall outside Jun-Sep and 3133 long events (>= 21 days, longest 69) exist across the runs, 622 of them at least half IDW-imputed.

*Conditions before use:* Make the floor-or-season decision before publication. Until then, describe results as persistent apparent-heat anomalies relative to the local date, never as hazardous heatwaves.

---

## What the comparison established, in one paragraph

Across 16 definitions at the w15 window, the four design axes do not do the same job. Day-level effect, largest first: metric 0.333 < percentile 0.492 < window 0.687 < duration 0.747. The METRIC changes which county-dates are classified more than anything else (median Jaccard 0.333 over 56 matched pairs) while barely changing the count (median 1.12x) - so a count-based justification for a metric is not sufficient, and the choice has to be argued on exposure-pathway grounds. The PERCENTILE is the count lever (median 2.03x). The WINDOW matters least (median Jaccard 0.699 vs the primary window). County RANKINGS are much more stable (median rho 0.744) than day-level agreement (median Jaccard 0.323), which means rank stability must not be quoted as evidence that the definitions agree about exposure. And the cool-season loading (51-64% of heatwave days outside Jun-Sep in every definition) is intrinsic to the year-round relative construct, so it cannot be resolved by choosing a different definition from this set - it needs the floor-or-season decision.
