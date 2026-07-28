# GHCN station provenance — Texas heatwave pilot (5 counties)

Compiled 2026-07-21 by direct inspection of the on-disk GHCN-Daily files for TX
and the build script `scripts/U_download_gulf_weather.py`. Companion table:
`05_station_provenance.csv` (one row per temperature-contributing station per
county). This documents where each pilot county's daily Tmax/Tmin actually comes
from, and — importantly — states what the files on disk **cannot** tell us.

## How stations become a county value (from the build script)

- **Assignment:** each GHCN station is placed in a county by **point-in-polygon**
  spatial join (`geopandas.sjoin(..., predicate="within")`) against the 2020
  TIGER county shapefile. Any station falling outside every county polygon is
  back-filled to the **nearest county centroid** (`cKDTree`). Assignment is by
  station coordinates only; it is fixed for the station's whole record (a station
  is never reassigned between counties over time).
- **Aggregation:** the county-day value actually used
  (`ghcn_county_day_weather_TX.csv`, columns `tmax_f`, `tmin_f`) is the **simple
  unweighted arithmetic mean of every in-county station reporting that element on
  that day.** A companion `*_nstations` column records how many stations fed each
  cell. No distance weighting, no reference-station homogenization, no anomaly
  standardization.
- **Consequence:** a county's Tmax/Tmin is **not a single fixed station**. It is
  a *composite of a station set that changes membership over 1979–2025* as
  stations open and close. See discontinuity section below.

## Critical limitation — station identity is NOT preserved in the aggregate

`ghcn_county_day_weather_TX.csv` keeps only the **mean** and a **count**
(`*_nstations`). It does **not** record which station IDs were averaged on any
given day. Which stations contributed can therefore **only** be reconstructed
by re-deriving it from `ghcn_station_day_TX.csv` (the long station-day file),
which is what this provenance table does. If only the county aggregate were on
disk, per-county station identity would be **unrecoverable**.

## No time-of-observation or flag metadata survives on disk

The raw NOAA `by_year` source files carry MFLAG, QFLAG, SFLAG, and an
observation-time field. The build pipeline reads them but writes **only**
`station_id, date, element, value` to `ghcn_station_day_TX.csv` (verified: that
file has exactly 4 columns, elements TMAX/TMIN/PRCP). Therefore, for this pilot:

- **No observation-time / time-of-day metadata** exists in any on-disk file. The
  per-station observing window (and hence time-of-observation bias, a real
  concern when mixing midnight-resetting USW airport stations with morning-reset
  USC COOP observers) **cannot be assessed from what is on disk.** (Conceptual
  treatment is in `04_source_time_conventions.md`, from GHCN documentation — not
  from station-level data here.)
- **The GHCN measurement flag `L`** ("temperature appears lagged w.r.t. the
  reported hour of observation") **is not present anywhere on disk.** It was
  discarded at extraction. Records carrying an `L` MFLAG were **not** removed
  (the pipeline filters only on a non-blank QFLAG), so any lagged-temperature
  observations are **silently included in the values with no flag to identify
  them.** We cannot tell from disk whether any exist.
- **QFLAG-flagged observations were dropped** during the build. Good in
  principle, but there is **no on-disk record of how many** or for which
  station-days, so the QC drop rate per pilot station is also not recoverable
  here.

## Network type from station-ID prefix

| Prefix | Network | Notes |
|---|---|---|
| `USW` | ASOS/AWOS first-order (WBAN) | mostly airports; automated; tends to local-midnight-to-midnight day |
| `USC` | COOP cooperative observer | often manual; **variable observation time** (TOB risk) |
| `USR` | RAWS remote automated | interagency fire-weather stations |
| `US1` | CoCoRaHS volunteer | **precipitation/snow only — report NO temperature** |

Across the 5 pilot counties the inventory assigns **689** stations, but only
**31** ever report TMAX/TMIN. The overwhelming majority (≈95%) are `US1`
CoCoRaHS precip-only volunteers that never touch the temperature series — a
reminder that raw inventory station counts badly overstate temperature density.

## Discontinuity risk (station replacement)

Because each county value is a **mean of whatever stations are active that day**,
every time a station enters or leaves, the mean jumps by roughly the
between-station offset (elevation, siting, urban/airport vs. rural COOP). These
are **step changes unrelated to climate** and are the main homogeneity threat in
this pilot. None of the county series is homogenized. Each county nonetheless has
at least one **full-span anchor airport (USW) station** present 1979→2026, so a
single-anchor (drop-the-composite) sensitivity check is feasible for all five.

## Per-county summary

Values below: temp stations ever contributing / of which full-span anchors;
range of stations feeding the daily Tmax mean; and the years the contributing
set changed.

### 48201 Harris (Houston)
- **7** temperature stations ever; **2 full-span USW airport anchors**: Hobby
  (`USW00012918`) and Intercontinental/IAH (`USW00012960`), both 1979→2026.
- Daily Tmax mean fed by **2–4** stations (median 3–4).
- Set changes: 1979 start (4 incl. Houston WB City + San Jacinto COOP) → WB City
  retires 1990 → San Jacinto COOP retires ~1996 → Hooks Memorial AP
  (`USW00053910`) joins 1998 → drops to 3 in 2014 → Ellington AFB
  (`USW00012906`) appears 2025. **Discontinuity risk: moderate** (mix shifts, but
  two stable airport anchors dominate throughout).

### 48141 El Paso
- **6** temperature stations ever; **1 full-span USW anchor**: El Paso Intl
  (`USW00023044`), 1979→2026.
- Daily Tmax mean fed by **2–5** stations; **drops to a steady 2** from ~2013.
- Set changes: two long COOP records (La Tuna, Ysleta) retire (2009, 2012);
  Tornillo COOP (`USC00419088`) runs 1981→2026; Biggs AFB (`USW00023019`) appears
  2025. **Discontinuity risk: moderate–high** — the composition thins from 4–5
  stations to just 2 around 2009–2013, a compositional break in the middle of the
  record.

### 48303 Lubbock
- **2** temperature stations ever; **1 full-span USW anchor**: Lubbock airport
  (`USW00023042`), 1979→2026.
- Daily Tmax mean fed by **1** station until 2012, then **2** (Lubbock WFO COOP
  `USC00415409` joins Feb 2012).
- **Discontinuity risk: low but datable** — series is effectively a single
  airport station for 1979–2011, then a 2-station mean. The 2012 addition is a
  clean, testable step (compare airport-only vs. 2-station mean around 2012).

### 48453 Travis (Austin)
- **8** temperature stations ever; **1 full-span USW anchor**: Austin-Camp Mabry
  (`USW00013958`), 1979→2026. Bergstrom Intl (`USW00013904`) joins 1992.
- Daily Tmax mean feed **grows steadily from 1 station (1979) to ~6 (2020+)**.
- Set changes nearly every few years: Bergstrom 1992, Balcones RAWS 2000,
  Austin-6S COOP 2004, Great Hills COOP 2008, Lago Vista AP 2014, Austin
  Executive AP 2018. **Discontinuity risk: high** — this is the least stable
  composite; the station set roughly sextuples over the record, so early-vs-late
  comparisons are confounded by changing station mix unless reduced to the Camp
  Mabry anchor.

### 48061 Cameron (Brownsville / Harlingen)
- **8** temperature stations ever; **3 full-span anchors**: Brownsville airport
  (`USW00012919`, USW), Harlingen COOP (`USC00413943`), Port Isabel COOP
  (`USC00417179`), all 1979→2026.
- Daily Tmax mean fed by **3 (1979) rising to 7–8 (2016+)**.
- Set changes: S Padre Is COOP 1992, Harlingen Valley Intl AP 1997, Port Isabel
  AP 1998, Laguna Atascosa RAWS 2002, WFO Brownsville COOP 2016. **Discontinuity
  risk: moderate–high** — set roughly doubles, but three stable anchors (incl.
  the Brownsville airport) span the whole record.

## Bottom line

- Each pilot county's daily Tmax/Tmin is a **spatial mean of a time-varying set
  of GHCN stations**, dominated by 1–3 long-running airport/COOP anchors but
  perturbed by stations entering/leaving over 1979–2025.
- **Every county retains ≥1 full-span USW airport anchor**, so a single-anchor
  sensitivity re-run (to test whether composite membership changes drive any
  apparent trend or a heatwave classification) is possible for all five counties.
- **Cannot be determined from disk:** per-station observation time / TOB,
  presence of `L`-lagged (or any) GHCN flags, and the QFLAG drop rate — none of
  this metadata was retained by the pipeline; station identity itself survives
  only in the long station-day file, not in the county aggregate that the study
  uses.
