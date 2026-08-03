# External benchmarking: what was attempted and what it showed

## Finding

**External benchmarking could not be performed with the contents of this repository.**

The candidate product is byte-identical to the project data on 2,938,070 of 2,938,070 matched daily county-level records (maximum absolute difference 0 degf), so it duplicates the project data rather than providing independent validation.

## Why the candidate product was rejected

The only second daily county-level temperature table in the repository is `data/raw/noaa/county_day_tmax.csv` and its `tmin` companion, produced by the national heatWaveUS pipeline. Its build script (`scripts/01_download_noaa_ghcn.py`) documents it as a **nearest-station** county assignment, which would have made it a usable method benchmark against this project's point-in-polygon station mean.

That documented difference does not exist in the delivered file. Comparing the two products daily record by daily record:

| state | variable | matched_daily_records | identical_records | share_identical | max_absolute_difference_f | verdict |
|---|---|---|---|---|---|---|
| TX | Tmax | 767112 | 767112 | 1 | 0 | DUPLICATE_NOT_INDEPENDENT |
| TX | Tmin | 766307 | 766307 | 1 | 0 | DUPLICATE_NOT_INDEPENDENT |
| LA | Tmax | 146445 | 146445 | 1 | 0 | DUPLICATE_NOT_INDEPENDENT |
| LA | Tmin | 146234 | 146234 | 1 | 0 | DUPLICATE_NOT_INDEPENDENT |
| MS | Tmax | 166469 | 166469 | 1 | 0 | DUPLICATE_NOT_INDEPENDENT |
| MS | Tmin | 166270 | 166270 | 1 | 0 | DUPLICATE_NOT_INDEPENDENT |
| AL | Tmax | 183059 | 183059 | 1 | 0 | DUPLICATE_NOT_INDEPENDENT |
| AL | Tmin | 182904 | 182904 | 1 | 0 | DUPLICATE_NOT_INDEPENDENT |
| FL | Tmax | 206566 | 206566 | 1 | 0 | DUPLICATE_NOT_INDEPENDENT |
| FL | Tmin | 206704 | 206704 | 1 | 0 | DUPLICATE_NOT_INDEPENDENT |

Every matched daily county-level record is identical to within floating point. The file duplicates the project data. Any agreement statistic computed against it would be a tautology, so none is reported as validation. The build-script docstring is inaccurate for the delivered file and that discrepancy is itself worth raising with whoever maintains the national pipeline.

## Status of each required comparison

| comparison | status | reason |
|---|---|---|
| monthly average daily high | **not available** | no independent product |
| monthly average daily low | **not available** | no independent product |
| annual average temperature | **not available** | no independent product |
| 1980s versus recent-period difference | **not available** | no independent product; the candidate also begins in 2015 and could not have reached 1980-1989 in any case |
| state ranking | **not available** | no independent product |
| seasonal shape | **not available** | no independent product |

## What would be needed

An independent, spatially consistent temperature product covering 1979-2025 for the five Gulf states at county resolution. Three candidates, none of which is currently in the repository:

| product | coverage | why it would work |
|---|---|---|
| NOAA nClimGrid-Daily | 1951-present, 5 km CONUS | independent gridding of the station network with its own homogenisation; the standard reference for US county-level temperature |
| PRISM AN81d | 1981-present, 4 km CONUS | independent interpolation with explicit elevation and coastal adjustment, which is where this project's county aggregation is weakest |
| Daymet v4 | 1980-present, 1 km North America | already used elsewhere in the wider heatWaveUS project for vapour pressure, so the ingestion path exists |

Until one of these is added, the following statements are **not** supported by this package and must not be made:

- that the county temperature values agree with an independent product
- that the station-to-county aggregation has been externally validated
- that the period differences survive an independent-data check

The unresolved temperature-source question recorded in the previous package (anchor-station versus multi-station composite agreeing at only 0.45-0.73) therefore remains open and is not narrowed by anything in this step.
