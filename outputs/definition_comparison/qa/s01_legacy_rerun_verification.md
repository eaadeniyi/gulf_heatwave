# s01 - published-definition re-run verification

Def 01 (`MHI_P85_2D`) and Def 02 (`MHI_P95_2D`) were re-run through the current `p02` at all four threshold windows, then compared against the originally published outputs on the two windows the published round ran (`w15`, `month`). The published directories were read-only.

- input file: `outputs/TX/county_daily_heat.csv` (md5:f0276ee5888539f9)
- git commit: `1818bb9`
- checks run: 46, failures: 0

**Result: PASS - the re-run reproduces the published Def 01 / Def 02 results exactly, so all sixteen definitions can be compared on one code path**

| check | scope | result | observed | expected | note |
|---|---|---|---|---|---|
| county-year keys present in both | MHI_P85_2D[w15] | PASS | 0 | 0 | 2791 county-years compared |
| county-year exact: heatwave_days | MHI_P85_2D[w15] | PASS | 0 | 0 | rows differing / 2791 |
| county-year exact: heatwave_events_started | MHI_P85_2D[w15] | PASS | 0 | 0 | rows differing / 2791 |
| county-year exact: longest_event_duration_days | MHI_P85_2D[w15] | PASS | 0 | 0 | rows differing / 2791 |
| county-year exact: heatwave_days_imputed | MHI_P85_2D[w15] | PASS | 0 | 0 | rows differing / 2791 |
| event set: published-only events | MHI_P85_2D[w15] | PASS | 0 | 0 | 48323 published events |
| event set: rerun-only events | MHI_P85_2D[w15] | PASS | 0 | 0 | 48323 rerun events |
| event count | MHI_P85_2D[w15] | PASS | 48323 | 48323 |  |
| published headline: heatwave days (QA pooled) | MHI_P85_2D[w15] | PASS | 170894 | 170894 |  |
| published headline: heatwave events | MHI_P85_2D[w15] | PASS | 48323 | 48323 |  |
| published headline: per-county median days | MHI_P85_2D[w15] | PASS | 677 | 677 | raw median = 677.0 |
| published headline: per-county min days | MHI_P85_2D[w15] | PASS | 154 | 154 |  |
| published headline: per-county max days | MHI_P85_2D[w15] | PASS | 1230 | 1230 |  |
| county-year keys present in both | MHI_P85_2D[month] | PASS | 0 | 0 | 2793 county-years compared |
| county-year exact: heatwave_days | MHI_P85_2D[month] | PASS | 0 | 0 | rows differing / 2793 |
| county-year exact: heatwave_events_started | MHI_P85_2D[month] | PASS | 0 | 0 | rows differing / 2793 |
| county-year exact: longest_event_duration_days | MHI_P85_2D[month] | PASS | 0 | 0 | rows differing / 2793 |
| county-year exact: heatwave_days_imputed | MHI_P85_2D[month] | PASS | 0 | 0 | rows differing / 2793 |
| event set: published-only events | MHI_P85_2D[month] | PASS | 0 | 0 | 47470 published events |
| event set: rerun-only events | MHI_P85_2D[month] | PASS | 0 | 0 | 47470 rerun events |
| event count | MHI_P85_2D[month] | PASS | 47470 | 47470 |  |
| new window produced | MHI_P85_2D[w05] | PASS | True | True | window absent from the published round |
| new window produced | MHI_P85_2D[month_pm7] | PASS | True | True | window absent from the published round |
| county-year keys present in both | MHI_P95_2D[w15] | PASS | 0 | 0 | 2709 county-years compared |
| county-year exact: heatwave_days | MHI_P95_2D[w15] | PASS | 0 | 0 | rows differing / 2709 |
| county-year exact: heatwave_events_started | MHI_P95_2D[w15] | PASS | 0 | 0 | rows differing / 2709 |
| county-year exact: longest_event_duration_days | MHI_P95_2D[w15] | PASS | 0 | 0 | rows differing / 2709 |
| county-year exact: heatwave_days_imputed | MHI_P95_2D[w15] | PASS | 0 | 0 | rows differing / 2709 |
| event set: published-only events | MHI_P95_2D[w15] | PASS | 0 | 0 | 17428 published events |
| event set: rerun-only events | MHI_P95_2D[w15] | PASS | 0 | 0 | 17428 rerun events |
| event count | MHI_P95_2D[w15] | PASS | 17428 | 17428 |  |
| published headline: heatwave days (QA pooled) | MHI_P95_2D[w15] | PASS | 52786 | 52786 |  |
| published headline: heatwave events | MHI_P95_2D[w15] | PASS | 17428 | 17428 |  |
| published headline: per-county median days | MHI_P95_2D[w15] | PASS | 196 | 196 | raw median = 195.5 |
| published headline: per-county min days | MHI_P95_2D[w15] | PASS | 18 | 18 |  |
| published headline: per-county max days | MHI_P95_2D[w15] | PASS | 516 | 516 |  |
| county-year keys present in both | MHI_P95_2D[month] | PASS | 0 | 0 | 2727 county-years compared |
| county-year exact: heatwave_days | MHI_P95_2D[month] | PASS | 0 | 0 | rows differing / 2727 |
| county-year exact: heatwave_events_started | MHI_P95_2D[month] | PASS | 0 | 0 | rows differing / 2727 |
| county-year exact: longest_event_duration_days | MHI_P95_2D[month] | PASS | 0 | 0 | rows differing / 2727 |
| county-year exact: heatwave_days_imputed | MHI_P95_2D[month] | PASS | 0 | 0 | rows differing / 2727 |
| event set: published-only events | MHI_P95_2D[month] | PASS | 0 | 0 | 17517 published events |
| event set: rerun-only events | MHI_P95_2D[month] | PASS | 0 | 0 | 17517 rerun events |
| event count | MHI_P95_2D[month] | PASS | 17517 | 17517 |  |
| new window produced | MHI_P95_2D[w05] | PASS | True | True | window absent from the published round |
| new window produced | MHI_P95_2D[month_pm7] | PASS | True | True | window absent from the published round |
