# Required tables - index

| # | table | file | unit of analysis |
|---|---|---|---|
| 1 | Definition registry | `table1_definition_registry.csv` | one definition (16 tested + 2 untested) |
| 2 | Run-level QA summary | `table2_run_qa_summary.csv` | one run = definition x window (64); pooled fields labelled _QA_pooled |
| 3 | County-year summary | `master_county_year_summary.csv` | county x year x run |
| 4 | County-month summary | `master_county_month_summary.csv` | county x year x month x run |
| 5 | Individual-event table | `master_event_table.csv.gz` | one heatwave event (integer duration) |
| 6 | Definition-pair agreement | `table6_definition_pair_agreement.csv` | one pair of runs; day-level sets of county-dates |
| 7 | Matched-pair marginal effects | `table7_matched_pair_marginal_effects.csv + table7b_marginal_effects_summary.csv` | one matched pair (single axis differing); summary reports n pairs per axis |
| 8 | Long-event and data-quality audit | `table8a_long_event_audit.csv + table8b_county_data_quality.csv` | one event >= 21 days; one county |

Tables 3-5 are written by `s02_canonical_long.py` (they are the aggregation levels of the canonical long table); tables 1, 2, 6, 7 and 8 by `s04_tables.py`. Support tables read by the figures are prefixed `support_`.
