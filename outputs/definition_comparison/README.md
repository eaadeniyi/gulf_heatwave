# Definition-comparison package - 16 heatwave definitions, Texas, 2015-2025

Compares 16 county-level heatwave definitions x 4 threshold windows = 64 runs over 254 counties, to show how the choice of **metric, percentile, minimum duration and threshold window** changes: the number of heatwave days, the number of events, the IDENTITY of the classified county-dates, seasonality, county rankings, event duration, and sensitivity to data quality.

**Read first:** `DECISION_TABLE.md`, then `figure_captions.md` (what each figure does and does not support), then `methods_notes.md`.

## Headline

| question | answer |
|---|---|
| Which axis changes WHICH days most? | metric (median Jaccard 0.333 over 56 matched pairs) |
| Which axis changes HOW MANY days most? | percentile (median 2.03x, up to 3.54x) |
| Which axis matters least? | threshold window (median Jaccard 0.699 vs the primary window) |
| Do county rankings survive? | more than day-level agreement does: median rho 0.744 vs median Jaccard 0.323 |
| Is the cool-season loading a metric artefact? | no - 51-64% of heatwave days fall outside Jun-Sep in every definition |
| Range of pooled heatwave days across definitions | 38,876 (TMAX_P95_3D) to 181,444 (TMIN_P85_2D) |

## Layout

```
figures/core/        Figures 1-7, 11, 12
figures/supplement/  the weaker variants, kept for comparison
county_profiles/     Figure 8: one report card per county + INDEX.csv
tables/              the 8 required tables, the canonical long table,
                     and the support tables the figures read
event_audits/        Figures 9-10: event timelines and the long-event audit
data_dictionary/     every column defined
qa/                  provenance, reconciliation and validation records
scripts/             s01..s08 + run_package.py (the only code)
figure_captions.md   the per-figure report
methods_notes.md     prespecified choices, units, reporting rules, QA notes
DECISION_TABLE.md    primary / sensitivity / different construct / needs work
run_manifest.csv     every file, its producer and its unit of analysis
```

## Regenerate

```bash
cd outputs/definition_comparison/scripts
python run_package.py            # everything, in order
python run_package.py --from s04 # from one step onward
```

Provenance of this build: git `1818bb9+dirty`, input `md5:f0276ee5888539f9`.

## Three things not to conclude from this package

1. **Jaccard is not accuracy.** No definition here is a gold standard and the data contains no observed heatwave day. Low agreement means two definitions classify different days, not that one is wrong.
2. **A high county-rank correlation is not day-level agreement.** The definitions largely agree on which counties are more exposed (median rho 0.744) while disagreeing on most individual days (median Jaccard 0.323).
3. **These are not hazardous-heat definitions.** All 16 are county-relative, year-round and carry no absolute floor, so a qualifying day is unusual FOR ITS OWN DATE. Do not describe the output as hazardous heatwaves without an absolute floor or a declared season.
