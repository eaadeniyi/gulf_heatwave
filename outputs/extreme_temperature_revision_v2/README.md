# Extreme-temperature revision (v2)

A corrected and audited reissue of `outputs/extreme_temp_tests/`. **The original package is not modified.**

**Read `reports/FINDINGS_REVISED.md` first, then `reports/FINAL_REPORT.md`.**

| directory | contents |
|---|---|
| `config/` | resolved configuration and a snapshot of the config module |
| `data_dictionary/` | variable dictionary and the revised definition registry |
| `tables/` | every published table |
| `figures/` | revised E2 to E9 plus ten new figures |
| `county_profiles/` | per-county series for the example counties |
| `event_audits/` | long-event review and per-day detail |
| `qa/` | reproduction, aggregation inventory, checksums, QA suite |
| `scripts/` | the pipeline, in run order |
| `reports/` | the findings and the full report |
| `current_vs_revised/` | the reproduction of the current package and the comparison |

## Headline

| question | answer |
|---|---|
| Does the current package reproduce? | yes - all 25 tables and figures bit-for-bit, and 120 of 120 exact checks on the classification step |
| Was the 'balanced panel' balanced? | no - it required one qualifying year per period; a real minimum removes 20-45%% of it |
| Does the aggregation correction change the answer? | the point estimates move by up to 1.10 degF; more importantly the interval across counties, never reported before, is 0.8 to 2.5 degF wide |
| Is a summer daily low below 75 degF a defect? | no - it is the ordinary case across the region |
| Is the monthly classification rate flat? | no - 0 of 33 constructs meet the prespecified flatness criterion |
| Does a relative rule flag a similar number of days everywhere? | no - a factor of 12.7 between the highest and lowest county |
| Is there an external benchmark? | no - the only candidate is byte-identical to the project data |

## Rebuild

```bash
cd outputs/extreme_temperature_revision_v2/scripts
python run_revision.py            # every step in order, ~12 minutes
```

Individual steps are listed in `run_manifest.csv`. The pipeline stops if any blocking QA test fails; it does not continue by dropping failed records or changing assumptions.

Provenance: git `550d9e5+dirty`, python 3.14.3, pandas 3.0.3, bootstrap seed 20260801.
