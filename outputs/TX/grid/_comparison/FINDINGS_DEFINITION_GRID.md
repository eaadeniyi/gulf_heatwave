# Findings — heatwave definition grid (Texas, 254 counties, 2015–2025)

**What was run.** 14 definitions × 4 threshold windows = **56 runs**. A *definition* is
`metric × percentile × minimum duration`; a *run* is a definition at one threshold window.

| axis | values tested |
| --- | --- |
| metric | daily maximum temperature (`TMAX`), daily minimum temperature (`TMIN`), daily-mean heat index (`MHI`) |
| percentile | 85th, 90th, 95th (`MHI` at 90th only — 85th/95th were completed in the previous round as Def 01/02) |
| minimum duration | ≥2 or ≥3 consecutive days |
| threshold window | `w05` centered ±2 d · `w15` centered ±7 d · `month` calendar-month bucket · `month_pm7` calendar month ±7 d |

**Held fixed across all 56 runs**, so any difference is attributable to those four axes and
nothing else: county-relative percentile, strict `>` comparison, walk-forward baseline
(year Y judged only against 1979…Y−1), year-round season, no absolute floor, IDW-gap-filled
temperature, identical input county-day table.

Numbers below are per-county **medians** unless labelled QA. Cross-county pooled totals are
QA quantities in this project and are used here only for the axis-comparison ratios, where a
single number per run is needed. Event duration is reported as median and max, never pooled-average.

---

## 1. The four choices do not matter equally — and they matter in *different ways*

Matched-pair analysis: for each contrast, two runs identical on the other three axes.
**Jaccard** = day-level agreement on the set of (county, date) heatwave days.
**Count ratio** = pooled heatwave days, higher run ÷ lower run.

| axis changed | matched pairs | Jaccard, median (range) | count ratio, median (range) |
| --- | --- | --- | --- |
| **metric** | 40 | **0.292** (0.178 – 0.510) | **1.13×** (1.01 – 1.23) |
| **percentile** | 48 | 0.493 (0.284 – 0.688) | **2.03×** (1.45 – 3.52) |
| window | 84 | 0.693 (0.547 – 0.933) | 1.07× (1.00 – 1.34) |
| duration | 28 | 0.747 (0.684 – 0.797) | 1.34× (1.25 – 1.46) |

Read against this project's two existing yardsticks — walk-forward vs fixed baseline scored
**0.923**, and anchor-station vs multi-station composite temperature scored **0.45–0.73** —
the **metric** axis (0.292) changes the classification *more than switching the temperature
data source did*, and **percentile** (0.493) is comparable to it. Window and duration sit at
or above the top of that band. (The 0.45–0.73 figure was measured on one definition, so this
is an order-of-magnitude comparison, not a strictly matched one.)

## 2. The main result: the metric changes *which* days, not *how many*

This is the finding that would not have surfaced from a count-based comparison.

- **Tmax vs Tmin**, at matched percentile, duration and window (24 pairs): Jaccard
  **0.245** (0.178–0.309) — they share roughly a quarter of their heatwave days — while Tmin
  counts only **13%** more days than Tmax.
- **Mean heat index vs Tmax** at the 90th percentile, `w15`: **110,243 vs 108,359** pooled
  heatwave days (QA) — **1.7% apart** — yet Jaccard is only **0.35–0.39**.

So three metrics that look near-interchangeable in any table of counts disagree on **60–75%
of the actual exposure days**. For any analysis that joins exposure to a dated outcome, day
identity is the thing that matters, which makes the metric the single most consequential
choice in the definition — and the one least visible in conventional count comparisons.

Per-county median heatwave days, `w15`, 2015–2025 (254 counties):

| percentile | duration | Tmax | Tmin | mean HI |
| --- | --- | --- | --- | --- |
| 85th | ≥2 d | 617 | 701 | *677* |
| 85th | ≥3 d | 470 | 556 | — |
| 90th | ≥2 d | 403 | 471 | 425 |
| 90th | ≥3 d | 298 | 349 | 290 |
| 95th | ≥2 d | 211 | 231 | *196* |
| 95th | ≥3 d | 141 | 156 | — |

*Italic* values are the previously published Def 01 / Def 02 (mean HI, ≥2 d), shown for
continuity. Mean HI sits between Tmax and Tmin at the 85th percentile but **below both** at
the 95th — the metrics do not even preserve their order across percentiles.

## 3. Percentile is the count lever

| contrast | Jaccard (median) | count ratio (median) |
| --- | --- | --- |
| 95th vs 85th | 0.325 | 3.08× |
| 95th vs 90th | 0.492 | 2.03× |
| 90th vs 85th | 0.659 | 1.52× |

Moving from the 95th to the 85th percentile roughly **triples** the heatwave-day count. This
axis moves both the count and the day identity, and is the one to fix first when the
intended event frequency is known.

## 4. Window matters least, and the two calendar-month variants are near-duplicates

| contrast | Jaccard (median) |
| --- | --- |
| `month` vs `month_pm7` | **0.886** — highest agreement of any contrast in the grid |
| `w05` vs `w15` | 0.851 |
| centered vs calendar-month (any combination) | 0.63 – 0.69 |

The four windows behave as **two families** — centered and calendar-month — with the two
members of each family close together. Counts fall **monotonically with pooling width** in
every one of the 14 definitions: `w05` > `w15` > `month` > `month_pm7`. Adding the ±7-day
collar to the calendar month removes about **9%** of heatwave days; a narrower window both
tracks the seasonal cycle more tightly and estimates the percentile from fewer reference
values, and both effects push toward more exceedances.

Two practical consequences. First, the previous round's reporting of `w15` and `month` side
by side was robust — the window choice is not where the sensitivity lives. Second,
`month_pm7` adds little beyond `month` (0.886 agreement, 9% fewer days) and could be dropped
from future rounds to save a quarter of the compute, if that is wanted.

## 5. Duration behaves exactly as specified (a structural check)

The ≥3-day heatwave days are a **strict subset** of the ≥2-day days — same candidate days,
stricter persistence — so Jaccard must equal the count ratio. Verified directly: for
`TMAX_P90 w15`, **zero** of the 80,755 three-day heatwave days fall outside the 108,359
two-day days, and Jaccard = |3d|/|2d| = **0.745254** on both routes; the identity holds for
all 28 duration pairs. Requiring a third day removes about **25%** of heatwave days.

This is an independent confirmation that the persistence logic does what the specification
says, on real data rather than test fixtures.

## 6. The cool-season loading is intrinsic to the year-round relative construct

Previously observed for the mean heat index (Def 01: ~63% of heatwave days outside Jun–Sep,
December the single highest month), and the natural hypothesis was that high winter humidity
was inflating the heat index. **The grid rules that out.** The pattern is present in every
definition, at every metric, percentile, duration and window:

- Days outside Jun–Sep: **51% – 63%** across all 14 definitions — a majority in every case.
- Nov–Feb share: **29% – 33%** in every definition, with December at 10–14% throughout.
- Stricter definitions are somewhat more summer-weighted (Tmin 95th ≥3 d = 48.8% Jun–Sep;
  mean HI 90th ≥2 d = 36.9%), but **none** is majority-summer.
- Peak month: the mean-HI definitions peak in **December**; Tmax/Tmin definitions mostly
  peak in **August** (Tmax 85th ≥2 d peaks in October) — but all still carry ~29–32% of their
  days in Nov–Feb. April is the consistent trough (0.8–6.3%).

**Consequence for an open decision.** The cool-season anomalies cannot be removed by
changing metric, percentile, duration or window. Restricting the construct to warm heat
therefore requires an explicit choice — an absolute floor (the `mean-HI ≥ 80°F` sensitivity
already scoped) or a declared seasonal window. That decision is now unavoidable rather than
deferrable.

## 7. County rankings are not stable across definitions

Spearman correlation of per-county heatwave-day totals between runs (1,540 pairs): median
**0.754**, range **0.300 – 0.996**; only **37%** of pairs exceed 0.90 and **23%** exceed 0.95.

Which counties look worst-affected therefore depends materially on the definition. Combined
with the known temperature-composite and IDW-imputation problem (anchor vs composite
0.45–0.73), **county-level ranking remains the weakest layer of this work** and the caveat
carried in the previous round still stands: trust the regional gradient, not single-county
texture.

---

## What this implies for the definition decision

1. **Justify the metric explicitly.** It is the largest single source of variation and is
   invisible in count comparisons. Tmin ("warm nights") and Tmax pick out substantially
   different days; whichever is chosen needs an exposure-pathway rationale rather than a
   count-based one.
2. **Set the percentile from the intended event frequency** — it is the count lever, moving
   heatwave days by up to 3×.
3. **The window is close to immaterial**; report one, note the other agrees. `w15` remains a
   defensible primary.
4. **Duration is a clean, well-behaved filter** (a strict subset relation, ~25% of days per
   extra required day).
5. **The floor / season question must now be answered** — no other axis in this grid
   addresses it.

## Caveats carried forward

Daily proxy, not hourly-concurrent heat index. Tmax and RH have different spatial support.
County temperature is a **changing multi-station composite with IDW gap-filling** (12.8% of
temperature county-days imputed; 22 counties fully imputed) — the top prerequisite before
injury linkage or firm county rankings, and unchanged by this round. Descriptive **exposure
classification only**: no injury-outcome, worker-heat-dose or official-advisory claims. The
year-round relative construct is a *persistent apparent-heat anomaly*, not absolute heat.

## Where the numbers live

- `RESULTS_TABLES_DEFINITION_GRID.md` — all tables, auto-generated from the outputs
  (regenerate with `pipeline/p06_results_tables.py`; never hand-edited).
- `tables/master_run_summary.csv` — one headline row per run (56).
- `tables/master_county_run_summary.csv` — 14,224 rows = 254 counties × 56 runs.
- `tables/marginal_effects.csv`, `marginal_effects_summary.csv` — the matched-pair analysis.
- `tables/agreement_jaccard_matrix.csv`, `agreement_jaccard_pairs.csv` — day-level agreement.
- `tables/county_rank_stability.csv`, `seasonality_by_run.csv`.
- `figures/cmp01`–`cmp06` — agreement heatmap, marginal effects, days by definition,
  seasonality grid, window effect, rank stability.
- `pipeline/definition_registry.csv` — every run's full specification, status and runtime.
- `run_log.csv` — provenance: git commit and input-file hash per run.
