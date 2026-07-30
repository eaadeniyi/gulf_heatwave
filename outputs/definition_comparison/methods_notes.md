# Methods notes

## 1. What is being compared

16 county-level heatwave definitions for Texas, 2015-2025, each crossed with 4 threshold windows = 64 runs. A definition is `metric x percentile x minimum duration`; a run is `definition x window`.

Held fixed across all 16: county-relative percentile, strict `>`, walk-forward baseline (1979 to the year before the analysis year, re-estimated annually), year-round season, **no absolute floor**, IDW gap-filling of missing temperature, and one identical input county-day table. Any difference between two runs is therefore attributable to metric, percentile, duration or window.

## 2. Units, and the reporting rules they enforce

| unit | definition |
|---|---|
| heatwave day | one county on one date inside a qualifying run |
| heatwave event | one uninterrupted qualifying run within one county |
| event duration | integer count of consecutive dates, `end - start + 1` |
| candidate day | metric strictly above its own threshold, before the persistence rule |
| eligible day | a county-day the definition could be evaluated on |

- Pooled cross-county totals appear only in fields suffixed `_QA_pooled` and are never a substantive result.
- No pooled average event duration is reported anywhere; medians, quartiles and maxima are.
- Event durations are integers in every table and label.
- Cumulative 2015-2025 counts are named `_2015_2025` and never described as annual.
- Year-round relative anomalies are never called hazardous heat: with no absolute floor and no seasonal restriction, a qualifying day is 'unusual for its own date'.

### County-month rule

An event crossing two months is counted ONCE in `heatwave_events_started`, in its onset month; it is counted as ACTIVE in every month it touches (`heatwave_events_active`); and its heatwave DAYS are allocated to the calendar month each day actually falls in.

### Year-boundary rule

A run is NOT broken at 31 December (`year_boundary_breaks_run=False`): one physical episode stays one event. It is counted once in its onset year, and its days are allocated to their actual calendar years.

## 3. Prespecified choices

| choice | value | basis |
|---|---|---|
| primary window | `w15` | the window Def 01/02 were published on |
| data-completeness cut | <= 10% imputed days (188 of 254 counties) | the INPUT imputation distribution (median 0.5%, q75 11.7%), not any heatwave result |
| long-event review length | 21 days | three continuous weeks is implausible as one physical episode |
| example counties | 10, one per NOAA climate division | lowest imputation % within the division, ties by lowest FIPS |
| shortlist | `TMAX_P90_2D`, `TMIN_P90_2D`, `MHI_P90_2D`, `MHI_P85_2D`, `MHI_P95_2D` | one definition per metric at the middle percentile and shorter duration, plus the two published definitions |
| detailed pairs | 6 single-axis contrasts | each isolates one axis; fixed before results were seen |
| event-timeline anchor | first 2020 event under `MHI_P90_2D` | fixed definition and fixed year, so windows are not chosen for magnitude |

Example counties selected by that rule: Bailey (High Plains), Baylor (Low Rolling Plains), Callahan (North Central), Anderson (East Texas), Brewster (Trans-Pecos), Burnet (Edwards Plateau), Bexar (South Central), Brazoria (Upper Coast), Atascosa (South Texas), Cameron (Lower Valley).

## 4. The canonical long table

One row per county x date x definition x window, stored at its informative support: **every candidate day** (a strict superset of the heatwave days, including isolated candidates). The full cross-product would be 65.3 million rows, ~90% of them recording only 'nowhere near threshold'.

Consequences, handled explicitly: a county-day absent from a shard is 'not a candidate for that definition' - not missing data and not a zero to impute; and **denominators never come from this table**, they come from `eligibility_county_month.csv`.

`exceedance_degF` is stored UNROUNDED while the two value columns are rounded for readability, so the table remains self-verifying: for these definitions `candidate_day_flag == 1` exactly where `exceedance_degF > 0` and the day is not a masked artifact.

## 5. Validation and provenance

- **Input provenance.** `tests/test_input_provenance.py` re-derives the county-day table from the raw GHCN and gridMET files and confirms it is byte-identical (md5 `f0276ee5888539f9dd4df1b3c7d2435e`), over the full 1979-2025 record.
- **Def 01/02 comparability.** The published outputs came from an earlier `p02` (different schema, only 2 of 4 windows, no recorded input fingerprint), so both definitions were RE-RUN on the current code path. 46/46 verification checks pass, including the complete event set and the published headline totals (Def 01 170,894 days / 48,323 events; Def 02 52,786 / 17,428). The published directories were never modified. (`qa/s01_legacy_rerun_verification.md`)
- **Rebuild reconciliation.** The canonical table's own heatwave-day and event counts are checked against every run's published pipeline summary: 128/128 agree exactly. (`qa/s02_reconciliation.csv`)
- **Pre-comparison validation.** 136 checks: 121 pass, 0 fail, plus 15 reported observations. (`qa/s03_validation.md`)

### Two QA findings worth carrying forward

**(a) Float parsing changes classification.** pandas' default CSV float parser is not correctly rounded. A cached threshold written as `101.74999999999999` reads back as `101.75`, and under a strict `>` that silently drops county-days. Reading thresholds with `float_precision="round_trip"` is required, not cosmetic; before the fix, 19 of 128 reconciliation checks were off by 1-4 county-days.

**(b) Exact ties are metric-dependent, and that is an asymmetry between definitions.** Tmax/Tmin are quantised to 0.1 degC, so a percentile frequently lands exactly on an observed value: 1.13% of evaluable county-days for Tmax and 1.44% for Tmin sit within 1e-9 degF of their own threshold, against **0.00%** for the derived mean heat index. The choice of strict `>` over `>=` therefore excludes ~1-2% of days for the temperature definitions and **no days at all** for the mean-HI definitions. That is a data-quantisation artefact, not physics, and it slightly biases every Tmax/Tmin-vs-mean-HI comparison in this package. (`qa/s02_knife_edge_days.csv`)

## 6. Known gaps in this package

1. **The design is not balanced.** `MHI_P85_3D` and `MHI_P95_3D` were never run, so the duration axis rests on 28 matched pairs against 60 for the percentile axis. They are carried as NOT TESTED everywhere and never zero-filled.
2. **Temperature-field homogeneity is unresolved and dominates.** Earlier work found anchor-station vs multi-station composite temperature agreeing at only 0.45-0.73 - larger than the effect of most definition choices measured here. Single-county results are not reliable until that is settled.
3. **No absolute floor or seasonal rule.** Every definition puts 51-64% of its heatwave days outside Jun-Sep. This is intrinsic to the year-round relative construct, not a metric artefact, so it cannot be fixed by choosing a different definition from this set.
4. **Station counts are only available for temperature.** The classification table does not retain them; Figure 10 reads them from the raw GHCN file. There is no equivalent provenance for the gridMET humidity field, so a mean-HI event's humidity provenance cannot be audited the same way.
5. **No outcome data is used anywhere.** Nothing in this package can identify a correct definition, and the decision table does not attempt to.

## 7. Environment

- python 3.14.3, pandas 3.0.3, numpy 2.4.6, matplotlib 3.11.0
- No new dependencies were added; `tabulate` is absent, so markdown tables are written by a local helper (`defcmp_config.md_table`).
- Regenerate with `python scripts/run_package.py` (see README.md).
