# Heatwave-definition scenario package (Texas, 2015–2025)

Four construct families × 27 runs, all 254 Texas counties. Self-contained: reads
`outputs/TX/county_daily_heat.csv` **read-only** and imports `pipeline/` functions unmodified, so
`p01` is untouched and every existing package's recorded input fingerprint stays valid.

**Read `reports/FINDINGS.md` first.**

## Headline

| question | answer |
|---|---|
| Does any construct avoid the cool-season loading every prior round found intrinsic? | Yes — EHF puts 98.8–98.9% of its dates in Jun–Sep; the percentile families put 20–49% |
| Why? | EHF's T95 is a single **all-calendar-day** 95th percentile; the percentile constructs use a **day-of-year-specific** threshold a warm winter day can clear |
| Does metric choice matter more at higher thresholds? | Yes — Tmax vs Tmax+RHmin proxy agreement falls 0.640 → 0.578 → 0.490 across the 85th/90th/95th |
| Fixed vs walk-forward EHF? | The fixed 1979–2014 baseline flags ~4% more assessment dates (74,358 vs 71,515) |
| Does excluding the confirmed humidity artifacts change much? | Barely — 6 classified dates at the 95th percentile; 90 of 12,078 thresholds moved, by ≤0.59 °F |
| Does one baseline year control a threshold? | No at the 85th percentile (≤1.11 °F); the 97.5th-percentile envelope is more volatile (14.19 °F) |
| Can any of this identify the *correct* definition? | **No** — no health outcome is used anywhere in this package |

## Construct families

| family | metric | construct ids | runs |
|---|---|---|---|
| EHF | daily mean temperature (°C) | `EHF_TX_FIXED7914`, `EHF_TX_WALKFORWARD` | 2 |
| Tmax | daily maximum temperature | `TMAX_P{80,85,90,95,975}_D3_W15`, `TMAX_P{85,90,95}_D2_W15`, `TMAX_P85_D3_W15_JUNSEP` | 9 |
| Tmax+RHmin proxy | afternoon-aligned, nonconcurrent daily-extrema proxy | `HIPROXY_P{85,90,95}_D2_W15_CONFEXCL`, `..._JUNSEP_CONFEXCL`, `..._PROBEXCL` | 5 |
| Tmax+RHmax envelope | **synthetic, nonconcurrent** envelope (methodological sensitivity) | `HIXENV_P{80,85,90,95,975}_D2_W15_{RAW,CONFEXCL}`, `..._P95_..._PROBEXCL` | 11 |

Every construct carries `role ∈ {candidate, sensitivity, benchmark}` and `decision_status = open`.
**No construct is labelled primary** — that decision has not been made.

The QC tier is always visible in the construct id (`_RAW` / `_CONFEXCL` / `_PROBEXCL`), never hidden
in the registry alone. `_CONFEXCL` (the default) excludes only the 3 independently verified artifacts;
`_PROBEXCL` additionally excludes 135 rule-flagged records that have not received equivalent
verification.

## Rebuild

```bash
cd outputs/heatwave_scenarios/scripts
python hs01_derive_variables.py    # ~3 min  -- envelope, QC categories, EHF components, T95, severity
python hs02_classify.py            # ~8 min  -- all 27 constructs
python hs03_reports.py             # ~20 s   -- registry, per-construct tables, QA summary
python hs05_comparison.py          # ~3 min  -- agreement matrices, matched comparison, LOYO
python hs04_figures.py             # ~1 min  -- 7 figures
```

Tests (14, all passing) — run them after touching any script:

```bash
cd outputs/heatwave_scenarios/tests
for t in test_*.py; do python "$t"; done
```

## Layout

```
scripts/     hs00_config.py  the CONSTRUCTS registry -- single source of truth; scenario_registry.csv
                             is regenerated from it every run and cannot drift
             hs01_derive_variables.py   hs02_classify.py   hs03_reports.py
             hs04_figures.py            hs05_comparison.py
tables/      scenario_registry.csv          27 runs, full spec + fingerprint + provenance
             scenario_summary_QA.csv        pooled QA quantities ONLY -- never a headline number
             ehf_summary.csv                both EHF event tables, both baselines
             temperature_percentile_summary.csv, heat_index_proxy_summary.csv,
             synthetic_envelope_summary.csv
             agreement_jaccard_yearround_21x21.csv / _pairs.csv
             matched_metric_comparison.csv  warmseason_candidate_pair_comparison.csv
             ehf_cross_family_overlap.csv   threshold_loyo_sensitivity.csv
             <CONSTRUCT_ID>/tables/         per-construct county-year, county-month, events
figures/     fig01 EHF components · fig02 seasonality · fig03 percentile sweeps
             fig04 21×21 agreement · fig05 matched metric · fig06 EHF overview · fig07 LOYO
tests/       14 test files
reports/     FINDINGS.md
```

## Reporting conventions enforced throughout

- **Primary results are per-record**: county-date, event, county-month, county-year. Pooled
  cross-county quantities live in `scenario_summary_QA.csv` with every field `_QA`-suffixed, and are
  never presented as headline numbers.
- **EHF is never mixed with ordinary daily classifications** in an agreement output. Its assessment
  dates summarise a trailing 3-day period; it is excluded from the 21×21 matrix and reported
  separately with `ehf_date_representation` populated on every row. EHF event counts are never
  compared directly to consecutive-day event counts (`median_annual_event_count_QA` is `NA` for EHF
  rows by construction).
- **EHF units are °C²** (`ehf_c2`, `ehisig_c`, `ehiaccl_c`) — never written into a `_f` field.
- **Jaccard** = |A ∩ B| / |A ∪ B| over positive classifications within the pairwise-common eligible
  universe — *not* divided by the universe size; `NA` (never 0 or 1) when the positive union is empty.
- **Excluded or missing input is `NA`**, never a published 0, and it breaks a consecutive run.
- The Tmax+RHmax construct is always a **"nonconcurrent synthetic envelope"**, never "maximum heat
  index" or "conservative exposure"; the Tmax+RHmin construct is **"afternoon-aligned, nonconcurrent"**,
  never "physically co-occurring".

## Scope deliberately not built this round

Baseline-imputation sensitivity tiers beyond the recorded completeness/coverage fields; a fourth QC
category; full shared-calendar event-level reconstruction for the matched comparison; Louisiana
(needs `pipeline/p01_build_countyday_idw.py` run for LA first — raw inputs exist, the county-day
table does not). Two further definitions can be appended to `hs00_config.CONSTRUCTS` without
restructuring.

Provenance: every registry row carries `git_commit`, `input_fingerprint` (md5 of the county-day
table) and `definition_fingerprint` (hash of every methodological setting).
