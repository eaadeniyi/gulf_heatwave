# Source time conventions (review Issue 7)

Documents the native temporal / observation-day convention of each input
source, per the review's requirement, and the resulting comparability concern.
Compiled 2026-07-16 from each product's primary documentation (the two
canonical journal articles, Menne et al. 2012 and Abatzoglou 2013, are
paywalled and were not read full-text; the temporal statements below come from
the datasets' own official documentation, which is authoritative for this).

## Temperature — NOAA GHCN-Daily (GHCNd), TMAX / TMIN

| Attribute | Value |
|---|---|
| Record grain | one "station-day" |
| Observation-day window | ~24 h between the observer's successive min/max resets — **not standardized across the network** |
| Date reference | the **station's own local observation day (local time)**, not UTC |
| Documented UTC exception | source "S" (Global Summary of the Day) TAVG uses a period ending 2400 UTC |
| Time-of-observation bias | **known and NOT corrected** — GHCNd is explicitly not homogenized for changes in observing practice; carries flag `L` ("temperature appears lagged w.r.t. reported hour of observation") to *detect* but not fix mis-attribution |

Mechanism of concern: an afternoon thermometer reset can log a warm late-day
reading again as the next day's maximum ("carry-over"); morning vs. afternoon
observers shift extrema onto different calendar days. Airport/ASOS stations
tend to report local-midnight-to-midnight; many COOP stations are morning
observers.

Sources: <https://www.ncei.noaa.gov/pub/data/cdo/documentation/GHCND_documentation.pdf>,
<https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt>,
<https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily>,
<https://climatedataguide.ucar.edu/climate-data/ghcn-d-global-historical-climatology-network-daily-temperatures>.
Canonical: Menne et al. 2012, J. Atmos. Oceanic Technol., doi:10.1175/JTECH-D-11-00103.1.

## Humidity — gridMET / METDATA, rmax / rmin

| Attribute | Value |
|---|---|
| Daily window (temp/precip/humidity group, incl. rmax/rmin) | **24 h ending 1200 UTC** (~7 am EST / ~6 am CST) per ClimateEngine per-variable docs — a **morning-to-morning** day, applied uniformly at every grid cell |
| Documentation discrepancy | the Climatology Lab landing page instead says "midnight-to-midnight MST (7 UTC)" — i.e. a window ending 0700 UTC, ~5 h different. The two official-lineage sources are numerically inconsistent; not resolved here (attempt to read the netCDF variable-level metadata directly failed on the THREDDS/OPeNDAP port). |
| Basis | PRISM (spatial) + NLDAS-2 (temporal, hourly UTC reanalysis) |

Sources: <https://support.climateengine.org/article/66-gridmet>,
<https://climateengine.org/datasets/climatehydrology/gridmet_daily_4000/>,
<https://www.climatologylab.org/gridmet.html>.
Canonical: Abatzoglou 2013, Int. J. Climatol., doi:10.1002/joc.3413.

## Comparability — the two "days" are potentially offset

- gridMET rmax/rmin: **fixed, uniform** morning-to-morning window (~ending 1200
  UTC), identical everywhere.
- GHCN TMAX/TMIN: each **station's own local observation day**, non-uniform,
  unhomogenized, and variable over time.

For morning-observer COOP stations the two windows roughly align; for
midnight-resetting (airport/ASOS) stations they can span different clock hours
and attribute the same extreme to adjacent calendar dates. **No source asserts
that the two products' days coincide.**

### Why this compounds review Issue 1

This pilot's primary metric pairs GHCN Tmax with gridMET RHmin on the "same"
calendar date. That pairing already assumes the two extrema are concurrent
within a day (they are not — one is a daytime max temperature, the other a
daily-minimum humidity). This time-convention finding adds a second,
independent misalignment: the 24-hour *windows* defining those two daily
values may not even be the same 24 hours. Both caveats point the same way —
`derived_tmax_rhmin_hi_proxy_f` is a **proxy**, appropriate for
relative/anomaly classification, not a physically observed daily-maximum heat
index. This should be stated in any manuscript.

### Not documented anywhere found
- A uniform fixed-clock window for GHCN TMAX/TMIN (per-station-local by design).
- A reconciliation of gridMET's 0700-UTC vs 1200-UTC day statements.
- Any provider statement directly comparing the two products' day conventions.
