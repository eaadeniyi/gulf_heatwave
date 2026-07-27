# Heatwave Classification — Reference: Definitions, Data Dictionary, Methods & Results

A single reference for the terms, column names, statistics, calculations, naming choices,
and conclusions produced in this project. Written to be copied into slides / an appendix.

Scope: county-level heatwave classification for Texas (5-county pilot → all 254 counties),
study period **2015–2025**, climate baseline from **1979**. Descriptive **exposure
classification** only — no injury-outcome, worker-heat-dose, or official-NWS-advisory claims.

---

## 1. The heatwave definitions

Each "definition" is one percentile choice; everything else is shared.

| Definition | Rule | Meaning |
|---|---|---|
| **Definition 01** | county-relative **85th-percentile** daily-mean heat index, **≥ 2 consecutive days**, walk-forward baseline | days that are in the hottest ~15% for that county and time of year, sustained ≥2 days |
| **Definition 02** | county-relative **95th-percentile** daily-mean heat index, **≥ 2 consecutive days**, walk-forward baseline | days in the hottest ~5% for that county and time of year, sustained ≥2 days |

**Shared design choices (both definitions):**

| Element | Choice | Why |
|---|---|---|
| Metric | daily-**mean** heat index (see §2) | measures the day's overall apparent-heat burden, not just the afternoon peak |
| Baseline | **walk-forward** (expanding): for analysis year Y, the reference pool is all years **1979 … Y-1** | classifies each year against all history observed *up to that point*; adapts as climate shifts |
| Threshold type | **county-relative percentile** | "unusually hot *for this county and time of year*", so a mild-but-anomalous day in a cool place and a hot day in a hot place are treated comparably |
| Persistence | **≥ 2 consecutive days** | a heatwave is sustained heat, not a single hot day |
| Absolute floor | **none in the primary** (an `≥80°F` floor is a reported sensitivity) | faithful to the definition as written; the floor is explored separately |
| Artifacts | 3 confirmed RH-clip artifact days set to **missing** | bad data should not manufacture heatwave days (see §7) |

**Two threshold windows** are computed and reported side by side (they define *how* the
percentile is pooled across the calendar):

| Window | Definition | Reference sample size |
|---|---|---|
| **`w15`** (centered 15-day-total) | the target calendar day **± 7 days** (15 days total), across baseline years | ~500–700 obs per threshold |
| **`month`** (calendar-month bucket) | all days in the **same calendar month**, across baseline years | ~1,000–1,400 obs per threshold |

---

## 2. The heat metric (heat-index proxy)

**Heat index** ("feels-like" temperature) combines air temperature and relative humidity
into one apparent-temperature value, via the NWS **Rothfusz regression** (with the official
low-humidity and high-humidity adjustment terms; the ≤80°F simple-average fallback below
80°F). *(Note: earlier this session the shared `heat_index_f` was corrected to include the
two NWS adjustment terms; the effect on Gulf-climate results was verified negligible.)*

| Proxy | Formula | Used for | Column name |
|---|---|---|---|
| **daily-MEAN HI** | `heat_index(Tmean, mean RH)`, where Tmean = (Tmax+Tmin)/2 and mean RH = (RHmax+RHmin)/2 | the two heatwave **definitions** | `derived_tmean_meanrh_hi_f` (a.k.a. `hi_mean_f`) |
| **daily-MAX HI** | `heat_index(Tmax, RHmin)` — hottest temp paired with that day's lowest humidity (an afternoon-like pairing) | the **NWS advisory-threshold proxy** (NWS thresholds are daytime-max values) | `derived_tmax_rhmin_hi_proxy_f` |

**Why "proxy" (not "heat index"):** inputs are **daily** (Tmax/Tmin/RHmax/RHmin), not
hourly-concurrent, so this is a derived approximation of apparent heat, not an observed
hourly maximum. Also, temperature (GHCN stations) and humidity (gridMET grid) have
**different spatial support**. Both facts mean the value is a county-level *proxy*.

Data sources: temperature = **NOAA GHCN-Daily** (station→county); humidity = **gridMET**
(4-km grid→county); county geometry = **2020 Census TIGER/Line**.

---

## 3. How the threshold and classification are computed

1. **Threshold (per county, per calendar day/month, per analysis year).** Gather the
   baseline heat-index values in the chosen window (±7 days, or the calendar month) across
   all years 1979…Y-1, and take the **85th (or 95th) percentile** (`numpy.percentile`,
   linear interpolation). This value is the county's own "unusually hot" bar for that date
   and year. Stored as `threshold_value_f`.
2. **Candidate day.** A day is a *candidate* if its daily-mean HI is **strictly greater
   than** its own threshold (`>`). `exceedance_f = daily-mean HI − threshold`.
3. **Heatwave day.** A candidate day that belongs to a run of **≥ 2 consecutive calendar
   days** of candidates. (A run is broken by a missing day, a non-consecutive date, or a
   non-candidate day.)
4. **Heatwave event.** One uninterrupted run of heatwave days within one county. Its
   **duration** = end − start + 1 (integer days).

**IDW gap-filling of missing temperature (statewide only).** Many rural counties lack
station data on some/all days. Missing daily temperature is filled by **inverse-distance
weighting (IDW)** from surrounding counties: for a missing county-day, value =
Σ(wᵢ·vᵢ)/Σ(wᵢ) over counties with data that day, with weight **wᵢ = 1/dᵢ²** and dᵢ = distance
between **county centroids** (equal-area CONUS Albers projection, EPSG:5070). Every imputed
county-day is flagged (`temp_imputed`) so interpolated values never pass as observed.
Statewide, **12.8%** of temperature county-days were imputed; **22** counties had no native
station data at all, **93** were fully native.

---

## 4. Column dictionary

### 4a. Daily heatwave-day table (`daily_heatwave_days_<window>.csv`) — one row per heatwave county-date

| Column | Meaning | How computed |
|---|---|---|
| `county_fips` | 5-digit county FIPS code | key |
| `county_name` | county name | from Census shapefile |
| `date`, `year`, `month` | calendar date of the heatwave day | — |
| `tmax_f`, `tmin_f`, `tmean_f` | daily max/min/mean air temperature (°F) | Tmean = (Tmax+Tmin)/2 |
| `rmin_pct` | daily minimum relative humidity (%) | gridMET |
| `derived_tmean_meanrh_hi_f` (`hi_mean_f`) | daily-mean heat-index proxy (°F) | `heat_index(Tmean, mean RH)` |
| `threshold_value_f` | this county-date-year's percentile threshold (°F) | §3 step 1 |
| `exceedance_f` | how far above threshold (°F) | mean-HI − threshold |
| `heatwave_day_flag` | 1 = this county-date is a heatwave day | §3 steps 2–3 |
| `event_id` | id of the event this day belongs to | run construction |
| `event_duration_days` | length of that event (days) | end − start + 1 |
| `temp_imputed` | True if temperature was IDW-filled | §3 |
| `qc_status` | data-quality label (see §5) | QC rules |

### 4b. Event table (`heatwave_events_<window>.csv`) — one row per heatwave event

| Column | Meaning |
|---|---|
| `event_label` | human-readable id, `<countyFIPS>_<onsetYear>_<seq>` (e.g. `48201_2023_012`) |
| `county_fips`, `county_name` | the county the event belongs to |
| `start_date`, `end_date` | first and last day of the event |
| `event_duration_days` | integer consecutive-day length |
| `peak_mean_hi_f` | highest daily-mean HI reached during the event (°F) |
| `peak_day_date` | the event's hottest day (by mean HI) |
| `peak_day_tmax_f` / `peak_day_tmean_f` / `peak_day_rmin_pct` | temperature & humidity on the peak day |
| `peak_day_threshold_f` | the threshold in force on the peak day |
| `tmax_max_f` | highest Tmax during the event |
| `tmean_mean_f` | mean of Tmean over the event days |
| `peak_exceedance_f` | largest single-day exceedance (°F above threshold) |
| `cumulative_exceedance_f` | Σ of positive exceedance over the event (°F·days) — total "dose" of anomaly |
| `n_imputed_days` / `event_contains_imputed_day` | how many event days used IDW-filled temp |
| `onset_year` | the year the event started (used to count annual events) |

### 4c. County-month summary (`county_month_summary_<window>.csv`) — one row per county-year-month

| Column | Meaning |
|---|---|
| `heatwave_events_started` | events whose **onset** is in this month |
| `heatwave_events_active` | events overlapping this month (may have started earlier) |
| `heatwave_days` | heatwave days falling in this month |
| `longest_event_duration_days` | longest active event touching this month |
| `event_ids_started` / `event_ids_active` | the actual event labels |

*Month-crossing rule:* an event is counted **once** at its onset month under "started",
appears "active" in every month it touches, and its **days** are allocated to their actual
calendar month — so nothing is double-counted.

### 4d. County-year summary (`county_year_summary_<window>.csv`) — one row per county-year

| Column | Meaning |
|---|---|
| `heatwave_events_started` | number of events with onset in that year |
| `heatwave_days` | total heatwave days that year |
| `first_event_start_date` / `last_event_end_date` | first-to-last event span |
| `longest_event_duration_days` | longest single event that year |
| `heatwave_days_imputed` | how many of those days used IDW-filled temperature |

### 4e. Threshold table (`thresholds_<window>.csv`)

| Column | Meaning |
|---|---|
| `threshold_value_f` | the percentile threshold (°F) for that county / calendar slot / analysis year |
| `n_reference_values` | how many baseline observations went into the percentile |
| `percentile` | 85 or 95 |
| `window_method` | "centered 15-day-total" or "calendar-month bucket" |
| `threshold_quality_flag` | `low_n_ref` if `n_reference_values < 20`, else `ok` |

### 4f. Quality-control & data-provenance columns

| Column / value | Meaning |
|---|---|
| `qc_status = valid` | clean observation |
| `qc_status = suspicious_retain` | implausible-but-kept (flagged, not deleted) |
| `qc_status = missing_input` | value could not be computed (missing source data) |
| `qc_status = invalid_physical` | physically impossible (e.g. Tmax<Tmin, RH out of 0–100) → nulled |
| `qc_rh_pin_likely_artifact` | RH clipped to exactly 100% on a warm, rain-free day (see §7) |
| `temp_imputed` | temperature was IDW-filled for this county-day |
| `rh_pin_class` | `confirmed_artifact` / `likely_real_wet` / `indeterminate` (row-level disposition of RH=100 pins) |

### 4g. NWS advisory-threshold proxy columns

| Column | Meaning |
|---|---|
| `nws_office` | the county's assigned NWS forecast office (nearest-office, approximate) |
| `advisory_hi_f` / `extreme_warning_hi_f` | that office's Heat-Advisory / Extreme-Heat-Warning heat-index thresholds (°F) |
| `nws_advisory_threshold_met` | 1 if the daily-max HI proxy ≥ advisory threshold |
| `nws_extreme_warning_threshold_met` | 1 if ≥ extreme-warning threshold |
| `advisory_threshold_days` | annual count of advisory-threshold days |
| `verification_status` | `documented` / `sr_standard` / `approximate` (honesty flag on each office's thresholds) |

---

## 5. Terminology & naming rationale

| Term / choice | Why we use it |
|---|---|
| **Heatwave day** (county-date) | the unit of analysis is one county on one date; avoids the ambiguous "event-day" |
| **Heatwave event** (one run in one county) | keeps each real, uninterrupted heat spell as its own record |
| **Event duration** (integer days) | reports real calendar length; we deliberately **do not** headline a pooled average like "4.3 days," which no real event lasted |
| **"persistent apparent-heat anomaly"** | the precise label for the year-round *relative* construct — a run of days unusually warm *for that date*, which is not always absolutely hot |
| **"proxy"** (heat-index, NWS) | flags that values are derived from daily (not hourly) data and can't reproduce official products |
| **QA-only pooled totals** | cross-county/-year sums are for pipeline sanity checks, not the substantive headline; substance is reported at county / county-month / county-year level |
| **`threshold_value_f`, `exceedance_f`, `n_reference_values`** | self-describing column names so any table is interpretable without the code |
| **walk-forward** | names the expanding-baseline design (as opposed to a fixed climatology) |

---

## 6. Statistical computations used (summary)

| Computation | What it is | How / why |
|---|---|---|
| **Percentile threshold** | 85th / 95th percentile of baseline heat index | `numpy.percentile` (linear interpolation); defines "unusually hot for here" |
| **Walk-forward pooling** | baseline re-estimated each year from 1979…Y-1 | classifies each year against prior-observed climate |
| **Persistence run-length** | consecutive-day counting with break rules | enforces the ≥2-day sustained-heat requirement |
| **Exceedance / cumulative exceedance** | HI − threshold; Σ of positive exceedance | intensity of a day / total anomaly "dose" of an event |
| **IDW imputation** | 1/distance² centroid-weighted interpolation | fills missing county temperatures; flagged |
| **Jaccard overlap** | \|A∩B\| / \|A∪B\| on heatwave-day sets | measures how much two definitions/methods agree on *which* days |
| **Descriptive trend slope** | linear fit of annual heatwave-days vs year | descriptive only (11 points, bounded counts) — **not** a formal trend estimate |
| **Fixed-vs-walk-forward comparison** | reclassify under a fixed 1979–2014 baseline | tests whether the expanding baseline suppresses later-year counts / trend |
| **Anchor-vs-composite sensitivity** | reclassify using a single airport station per county | tests how sensitive results are to the multi-station composite temperature |

---

## 7. Key results & conclusions (this session)

**Definition 01 vs Definition 02 (statewide, 254 counties, centered-15-day window):**

| | Def 01 (85th) | Def 02 (95th) |
|---|---:|---:|
| pooled heatwave-days (QA) | ~170,900 | ~52,800 |
| pooled events (QA) | ~48,300 | ~17,400 |
| per-county heatwave days, **median** | **677** | **196** |
| per-county range | 154–1,230 | 18–516 |

→ The stricter 95th-percentile definition yields **~⅓** the heatwave days of the 85th — it
keeps only each county's most anomalous ~5% of days.

**Absolute-floor sensitivity:** adding a `mean-HI ≥ 80°F` floor **roughly halves** the counts,
because a relative-only definition flags many **sub-80°F cool-season anomaly days** (unusually
warm for the date but not absolutely hot). *Example:* Harris County, **December 2021** — a
record-warm December — registered ~19 heatwave days at 80–85°F; under the 80°F floor these
drop to ~0. This is the single clearest illustration of the relative-vs-absolute distinction.

**Fixed vs walk-forward baseline (pilot):** day-level agreement **Jaccard = 0.923**; the fixed
1979–2014 baseline flags **+6.5%** more heatwave-days (3,213 vs 3,018) and steeper trend slopes
→ the walk-forward baseline **absorbs part of the warming signal**; county rankings unchanged.

**Anchor-station vs composite temperature (pilot):** heatwave-day **Jaccard only 0.45–0.73** —
i.e. the **temperature source changes classification more than the baseline choice does**
(e.g. Travis County 424 → 807 heatwave-days on a single-airport series). **Conclusion:** the
county-to-county texture of the maps is only as reliable as the underlying stations; trust the
regional gradient over single-county values, especially in heavily-imputed counties.

**Relative vs absolute (NWS proxy):** arid **El Paso / Lubbock** record ~1 NWS advisory-threshold
day in 11 years (their max HI rarely reaches 105°F) yet have plenty of *relative* heatwave days —
they are "unusually warm for themselves" without being absolutely hot. Humid **Houston** logs 172.

**Data-quality finding — March 1, 2023 artifact:** gridMET clipped RH to exactly 100% on a warm,
rain-free day in 118/254 counties simultaneously, inflating the HI proxy by **+15 to +24°F**.
Confirmed a product artifact (GHCN showed zero precip, station RH ~80%); the 3 affected pilot
county-days are set to missing in the primary.

---

## 8. Caveats & limitations (state on any results slide)

- **Daily proxy, not hourly** apparent heat; temperature and humidity have different spatial support.
- **Composite-station + IDW noise:** county temperature is a changing multi-station composite plus
  interpolation in low-coverage counties → single-county values are noisy; regional gradients are robust.
- **Year-round relative construct** = "persistent apparent-heat anomaly"; ~half the flagged days are
  sub-80°F cool-season anomalies unless the `≥80°F` floor is applied.
- **NWS proxy is approximate** (nearest-office crosswalk; most office thresholds flagged approximate) and
  is **not** an official advisory.
- **Trend slopes are descriptive** (11 annual points) — not formal trend inference.
- **Not** an injury or worker-heat-dose measure; this is exposure classification only.

---

## 9. Data & code

Pipeline is state-agnostic (config-driven) and on GitHub: **github.com/eaadeniyi/gulf_heatwave**.
Definitions are reproduced by setting `PERCENTILES = [85]` (Def 01) or `[95]` (Def 02) in `config.py`.
