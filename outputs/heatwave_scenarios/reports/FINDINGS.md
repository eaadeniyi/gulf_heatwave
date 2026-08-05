# Findings — heatwave-definition scenario package (Texas, 2015–2025)

Four construct families, 27 runs, all 254 Texas counties. Every number here is recomputed in this
package; nothing is carried over from a previous write-up. Read `../README.md` for the layout and
rebuild command.

**Epistemic level: descriptive.** No health outcome appears anywhere in this package, so nothing
here can identify a *correct* definition — only how the definitions differ from one another.
Agreement between definitions is agreement, not accuracy.

**No definition is labelled primary.** Every construct carries `role ∈ {candidate, sensitivity,
benchmark}` and `decision_status = open`.

---

## 1. The headline: EHF is seasonally concentrated; the relative-percentile constructs are not

| construct family | % of classified dates in Jun–Sep | % in Nov–Apr |
|---|---:|---:|
| **EHF** (both baselines) | **98.8 – 98.9** | **0.0** |
| Tmax percentile (year-round) | 37.1 – 49.4 | 34.2 – 44.3 |
| Tmax+RHmin proxy (year-round) | 32.3 – 35.0 | 46.5 – 51.5 |
| Tmax+RHmax synthetic envelope | 19.6 – 28.2 | 55.3 – 69.3 |

Every prior round in this project found that 51–64% of relative-percentile heatwave days fall
outside Jun–Sep regardless of metric, percentile, duration or window, and concluded the cool-season
loading was intrinsic to the year-round relative construct. **This package reproduces that finding
for the percentile families and shows EHF does not share it** — 99% of positive-EHF assessment dates
fall in Jun–Sep.

**The mechanism is the threshold's calendar structure, not the metric.** The percentile constructs
compare each date against a *day-of-year-specific* threshold (a centered 15-day window), so an
unusually warm December day clears a low December bar. EHF compares a 3-day mean against **T95, a
single all-calendar-day 95th percentile per county** — a bar set by the whole year's distribution,
which in Texas only summer days clear. This is a property of how the threshold is defined, and it
would apply to any construct built the same way.

Two things this does **not** establish: that EHF is more correct (no outcome data is used anywhere
here), or that the cool-season dates flagged by the percentile constructs are errors — they are
genuine "unusual for this date" anomalies, which is what a day-of-year-relative rule is built to find.

## 2. Metric choice: matched comparison (Tmax vs Tmax+RHmin proxy)

Percentile, duration and window held identical; metric is the only axis that differs. Computed on
the pairwise-common eligible calendar.

| percentile | Tmax only | both | proxy only | Jaccard |
|---|---:|---:|---:|---:|
| 85th | 35,844 | 125,157 | 34,507 | **0.640** |
| 90th | 31,082 | 77,274 | 25,451 | **0.578** |
| 95th | 21,915 | 34,659 | 14,119 | **0.490** |

**Metric agreement falls as the threshold rises.** At the 85th percentile the two metrics share about
two-thirds of their classified dates; at the 95th, under half. The rarer the event, the more the
choice between dry-bulb and humidity-adjusted exposure decides *which* dates are selected.

This claim covers **daily classification only** — event-level differences are not claimed to isolate
metric choice, because the proxy's QC exclusions break event sequences that Tmax retains.

## 3. Cross-construct agreement

Across the 21 year-round ordinary constructs (210 pairs): median Jaccard **0.349**, range
**0.074 – 0.9999**.

- Highest (0.9999): each `HIXENV_*_RAW` against its own `_CONFEXCL` twin — they differ only by the
  3 confirmed artifact days, so on the common-eligible calendar they are nearly identical by
  construction. This is arithmetic, not evidence.
- Lowest (0.074): `TMAX_P80_D3_W15` vs `HIXENV_P975_D2_W15` — opposite ends of metric, percentile
  and duration simultaneously.
- EHF is **not** in this matrix. Its assessment dates summarise a trailing 3-day period, so a
  date-for-date Jaccard against single-day classifications is not an equivalent unit. Reported
  separately in `tables/ehf_cross_family_overlap.csv`: EHF's assessment-date agreement with the
  ordinary constructs runs **0.023 – 0.220**, highest against the Tmax family and lowest against
  the synthetic envelope.

## 4. EHF: fixed vs walk-forward baseline

| | positive assessment dates | positive-EHF periods | longest period | thermal-support events | longest support event |
|---|---:|---:|---:|---:|---:|
| `EHF_TX_FIXED7914` (benchmark) | 74,358 | 38,760 | 95 d | 36,456 | 97 d |
| `EHF_TX_WALKFORWARD` (candidate) | 71,515 | 11,169 | 94 d | 10,460 | 96 d |

The fixed 1979–2014 baseline flags ~4% more assessment dates than the expanding walk-forward
baseline, as expected: a walk-forward T95 absorbs recent warming into the threshold.

**Two event tables are reported, and they are not interchangeable.** `ehf_positive_periods` (runs of
consecutive positive assessment dates) is the benchmark, closest to BoM practice. Merging each
positive date's 3-day support window instead gives **fewer, longer** events — the merge joins
assessment dates whose support windows overlap even when the day between them is not itself positive.
Every reported count names which table it came from.

**Naming:** `EHF_TX_FIXED7914` is `adapted_not_exact` — BoM specifications use 1971–2000 or
1985–2014; neither matches this project's 1979–2014 baseline.

**Occurrence is determined by EHIsig alone.** Since `max(1, EHIaccl) ≥ 1 > 0`, `EHF > 0 ⟺ EHIsig > 0`
— verified with zero exceptions across 4,352,290 county-days (fixed) and 1,020,572 (walk-forward).
The acclimatisation term scales magnitude and accumulated severity; it never changes which dates
qualify. EHF should not be described as an occurrence rule that incorporates acclimatisation.

## 5. QC tiers: the artifact exclusion barely moves the classification

The default formal series excludes only the **3 independently confirmed** artifacts (Cameron, Harris,
Travis on 2023-03-01). A separate sensitivity additionally excludes the 135 rule-flagged probable
artifacts, which have **not** received equivalent independent verification.

| construct | RAW | CONFEXCL | PROBEXCL |
|---|---:|---:|---:|
| `HIXENV_P95_D2_W15` | 31,294 | 31,288 | 31,104 |
| `HIPROXY_P95_D2_W15` | — | 48,778 | 48,577 |

Excluding the confirmed artifacts removes 6 classified dates from the envelope at the 95th
percentile; the broader probable-artifact exclusion removes ~190 more.

**The 2017-01-14 pin, handled county by county.** This project's earlier investigation examined that
date for **Lubbock and Travis** and found a genuine cold-season saturation event (measurable rain,
station RH 94.5–97%, Tmax 34 °F / 62 °F — cold enough that the heat-index proxy equals Tmax and no
heat metric is affected). Both are classified `valid` here, under every tier. That verdict covers
those two counties, not the whole date: **Sterling County** on the same day has RH pinned 100/100
with **zero precipitation at Tmax 81 °F**, which meets the screening rule on its own merits and is
correctly classified `rule_flagged_probable_artifact`. No 2017-01-14 record is ever treated as a
*confirmed* artifact. This is the confirmed-vs-rule-flagged distinction doing exactly the work it
was introduced for — a date can be genuine in one county and suspect in another.

Threshold recomputation on the affected counties: excluding the confirmed artifacts changed 90 of
12,078 thresholds, by up to 0.59 °F. **Whether an exclusion moves a percentile is an empirical
outcome, not a requirement** — a zero change would have been an equally valid result.

## 6. Threshold stability (leave-one-baseline-year-out)

Dropping any single baseline year and reclassifying the entire annual sequence, for 4 named
constructs × 3 preselected counties × 4 frozen date windows (144 scenarios):

| construct | max threshold shift | classified dates changed (all 36 scenarios) |
|---|---:|---:|
| `TMAX_P85_D3_W15` | 1.11 °F | 328 |
| `TMAX_P975_D3_W15` | 2.31 °F | 97 |
| `HIPROXY_P95_D2_W15_CONFEXCL` | 2.43 °F | 145 |
| `HIXENV_P975_D2_W15_CONFEXCL` | 14.19 °F | 6 |

No single historical year controls a threshold at the 85th percentile. The synthetic envelope at the
97.5th percentile is the most threshold-unstable (14 °F swing from dropping one year) but the least
classification-sensitive (6 dates) — its upper tail is thin and volatile, but the days it selects are
far enough above the bar that a threshold shift rarely reclassifies them.

## 7. Reference adequacy

Under the completeness rule (≥90% day coverage, ≥30 distinct qualifying years, <50% reference-day
imputation), **238 of 254 counties** have an `ok` fixed-baseline T95. The other **16 fail on
`excessive_reference_imputation`** — their climatology is built mostly or entirely from IDW-interpolated
neighbours (4 counties are 100% imputed across the full 1979–2014 reference).

All 254 counties clear the tighter EHF severity floor (≥100 positive reference values, ≥10 distinct
years), so `ehf_severity_class` is computed everywhere rather than `undetermined`.

The previous convention would have been a bare `n ≥ 20` count, which all 254 counties pass trivially —
a county carried entirely by interpolation would have received an unflagged climatology.

## 8. Empirical note: the envelope is not universally above the proxy

`synthetic_tmax_rhmax_hi_f ≥ derived_tmax_rhmin_hi_proxy_f` holds on 4,360,407 of 4,360,418
county-days — but **11 exceptions exist**, all on cold days (Tmax 28.5–61.2 °F) at RHmax = 100%.
Reported as an empirical count over the observed domain, not asserted as a mathematical property: the
NWS procedure has conditional branches and adjustments, so monotonicity in RH is not guaranteed by
construction across every input.

---

## Independent validation

`TMAX_P80_D3_W15` produced **171,965 classified dates / 32,503 events** — matching, exactly,
`extreme_temperature_revision_v2`'s separately-built `REL_TX_P80_D3_W15`. The two packages share the
input table but were coded independently.

The 6 reused Tmax cells reconcile against `outputs/TX/grid/` on classified-date sets, complete event
sets and county-year tables, gated on a full methodological fingerprint.

## What this package supports / does not support

**Supports:** the constructs classify different county-dates conditional on a shared eligible calendar;
EHF's all-calendar-day threshold concentrates its dates in the warm season while day-of-year-relative
thresholds do not; metric choice matters more at higher percentiles; excluding confirmed humidity
artifacts changed thresholds and classifications by the reported (small) amount.

**Does not support:** that any construct is correct or best (no outcome data is used); that the
Tmax+RHmax envelope estimates observed exposure (its two inputs are nonconcurrent daily extrema, and
the direction of its bias relative to the unknown concurrent value is not established); that EHF
event counts are comparable to ordinary consecutive-day event counts; that county rankings represent
equally-observed exposure (16 counties' climatologies are imputation-dominated).

## Caveats carried forward

- **Temperature source remains unvalidated.** No independent product is available in this repository;
  earlier work found anchor-station vs multi-station composite agreeing at only 0.45–0.73, larger than
  most definition effects measured here. This is still the dominant unresolved risk.
- **Gap-filling.** 16 counties fail the reference-imputation floor; their thresholds describe the
  interpolation as much as the county.
- **Observation-day conventions.** GHCN Tmax/Tmin follow each station's own local observation day;
  gridMET humidity uses a fixed UTC-anchored window. Equivalence to the Australian 9am–9am EHF
  convention is **not established** and is not assumed (see `quality_control/04_source_time_conventions.md`).
- **Year-round relative constructs are relative warm spells**, not occupational heatwaves, until an
  absolute floor or a declared season is applied. The two `_JUNSEP` runs are the season-restricted
  reconstruction; everything else in the percentile families is year-round.
