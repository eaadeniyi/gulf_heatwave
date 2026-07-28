# Source Verification: gridMET RH=100 Zero-Diurnal-Range Anomaly

**Scope:** The pilot QC flagged county-days where gridMET daily relative humidity is
pinned at exactly `100.000000` for BOTH `rmax_pct` AND `rmin_pct` (zero diurnal RH
range). The two multi-county dates were **2023-03-01** (Harris, Cameron, Travis) and
**2017-01-14** (Lubbock, Travis). This note investigates whether these are a real
widespread saturation event (rain/fog/overcast) or a data artifact, using only on-disk
data.

**Data used (on-disk only):**
- gridMET humidity: `data/raw/gulf_states/TX/weather/gridmet_county_day_humidity_TX.csv`
  (4,407,916 county-days, 254 counties, 1979-01-01 → 2026-07-06)
- GHCN county-day: `data/raw/gulf_states/TX/weather/ghcn_county_day_weather_TX.csv`
  (has `prcp_in`, `rhav_pct`, `adpt_dewpoint_f` — an independent, ground-station cross-check)

**No independent hourly / sub-daily RH or dewpoint source is available offline**, and gridMET
has no native dewpoint field on disk. GHCN `adpt_dewpoint_f` is a *daily-average* dewpoint from
only 1–2 stations per county, and `rhav_pct` is sparse (present for only 242 of 2,143 pin days).
So the judgement below is a **physically reasoned cross-check against ground observations, not a
direct external validation of gridMET's own grid cells.** The direction of the evidence is,
however, unambiguous.

---

## Verdict (differs by date)

| Date | Counties | Judgement | Confidence |
|------|----------|-----------|------------|
| **2023-03-01** | Cameron, Harris, Travis | **ARTIFACT** — false daytime saturation | High |
| **2017-01-14** | Lubbock, Travis | **REAL saturation / precipitation event** — pin defensible | High |

The two dates the pilot lumped together as "multi-county suspicious" have **opposite
resolutions.** They should not be treated as one phenomenon.

---

## Evidence

### 1. The pin is a discrete clip at exactly 100.000000, not a near-saturation continuum
- `rmax_pct == 100` exactly: 751,681 county-days (17.05%) — morning near-saturation is normal
  in humid Gulf air, **not suspicious by itself.**
- `rmin_pct == 100` exactly: **2,143 county-days (0.049%)**, and every one of these also has
  `rmax == 100`. The zero-diurnal-range pin is the rare anomaly.
- Only 125 county-days fall in the band `99.99 ≤ rmin < 100`. So values sit either just-below-100
  (genuine near-saturation, e.g. 99.99007) OR exactly `100.000000` — a **discrete spike / clipping
  behavior**, not a smooth approach to saturation.

### 2. 2023-03-01 is the single most widespread pin date in the 47-year record
Counties (of 254) pinned at both bounds on each date:
- **2023-03-01: 118 / 254 counties (46%)** — rank **#1 of 17,354 dates**.
- 2017-01-14: 74 / 254 counties — rank #8.

72 dates have ≥3 counties pinned; 45 dates have ≥10. Same-day, statewide pinning across dozens
of counties — from Brownsville on the coast to the arid Panhandle — is a recurring product-level
pattern, **not independent local saturation.** On 2023-03-01, 118 counties spanning every climate
zone in Texas simultaneously reported exactly `100.000000` for both RH bounds.

### 3. GHCN ground stations contradict saturation on 2023-03-01 (the decisive test)
Independent station observations on 2023-03-01 for the three flagged counties:

| County | PRCP (in) | #stations | rhav (%) | dewpoint (°F) | Tmax (°F) | Tmin (°F) |
|--------|-----------|-----------|----------|---------------|-----------|-----------|
| Cameron | **0.000** | 23 | 83.0 | 71.96 | 87.47 | 71.60 |
| Harris  | **0.000** | 38 | 79.5 | 69.08 | 85.34 | 71.66 |
| Travis  | **0.000** | 62 | 80.5 | 68.00 | 83.66 | 66.02 |

- **Zero precipitation** across 23–62 stations per county. No rain event.
- Station daily-average RH was **79.5–83%**, not 100%.
- Dewpoint (68–72°F) sitting ~15–16°F below the afternoon high (84–88°F) means the **daytime
  minimum RH was really ≈ 58–60%**, computed from the station dewpoint. Full-day saturation is
  incompatible with a mid-80s°F afternoon (statewide fog does not survive an 88°F high).
- Morning near-saturation IS real here (dewpoint 72°F ≈ Tmin 71.6°F for Cameron → `rmax=100`
  plausible). But that is captured by `rmax`; it does **not** justify `rmin=100`.

**gridMET reported `rmin_pct = 100` (zero diurnal range) where the ground data imply ≈ 60%. The
2023-03-01 pin is physically false — an artifact.**

### 4. 2017-01-14 is a genuine cold-season saturation / precipitation event
| County | PRCP (in) | rhav (%) | Tmax (°F) | context |
|--------|-----------|----------|-----------|---------|
| Lubbock | 0.067 (then 0.85, 0.68) | 97.0 | 33.98 | cold, overcast, wintry precip onset |
| Travis  | 0.392 (then 0.91, 1.73) | 94.5 | 61.67 | genuine rain event |

Measurable-to-heavy precipitation, high station RH (94.5–97%), and cold temperatures. RH near 100%
on a cold, overcast, precipitating day is **physically plausible**, so the pin is defensible.
Note these are cold days (Tmax < 80°F), so the heat-index proxy equals Tmax regardless — **the RH
value inflates no heat metric here and is irrelevant to heatwave detection.**

### 5. Record-wide, the pin mostly (but not always) tracks real wet weather
Of 2,143 zero-range pin county-days (2,047 with GHCN precip available):
- **66.6% coincide with measurable precipitation (>0.01 in)** — median precip 0.049 in; median
  `rhav` 89%. So the pinning mechanism fires predominantly on genuinely wet/saturated days.
- **But 22.8% occur on bone-dry days (PRCP = 0).** 2023-03-01 for the three focus counties falls
  squarely in this dry, false-saturation subset (rhav 79.5–83%, below the 89% pin-day median).

Interpretation: the gridMET zero-range RH=100 value is a **saturation-clipping behavior** that is
harmless-to-correct on cold/wet days (like 2017-01-14) but produces **false all-day saturation on
warm, humid, rain-free days** (like 2023-03-01). Warm dry-day pins are the dangerous subset for a
heat-index study.

### 6. Why this matters — heat-index inflation on 2023-03-01
The false RH=100 inflates the derived heat-index proxy on 2023-03-01:

| County | Tmax | HI @ RH=100 (as flagged) | HI @ true RH (~60%) | Inflation |
|--------|------|--------------------------|---------------------|-----------|
| Cameron | 87.5°F | 119°F | 94°F | **+24°F** |
| Harris  | 85.3°F | 109°F | 89°F | **+20°F** |
| Travis  | 83.7°F | 102°F | 87°F | **+15°F** |

The artifact manufactures "extreme heat index" (up to 119°F) out of merely warm, humid, rain-free
early-spring days. This is exactly the failure mode a heat-index-based heatwave definition is
vulnerable to, and it lands in early March (pre-warm-season), where such HI values are otherwise
implausible.

---

## Bottom line
- **2023-03-01 (Cameron, Harris, Travis): data artifact.** Zero precipitation, station RH ~80%,
  dewpoint-implied daytime minimum RH ~60%, incompatible with all-day saturation under an
  84–88°F afternoon; and it is the most widespread pin date in the entire 47-year record,
  spanning arid and coastal counties alike. The gridMET `rmin_pct=100` / zero-diurnal-range is
  physically contradicted by ground observations and inflates the HI proxy by +15 to +24°F.
- **2017-01-14 (Lubbock, Travis): real saturation event.** Measurable precipitation, cold,
  station RH 94.5–97%; the pin is physically defensible and, being on cold days, does not affect
  any heat metric.
- **Recommendation:** treat exactly-`100.000000` zero-diurnal-range RH as suspect specifically on
  warm, dry (GHCN PRCP≈0) days — cap/impute `rmin_pct` from a dewpoint- or `rhav`-based estimate,
  or exclude such HI values — rather than blanket-dropping all pins (two-thirds are real wet days).

## Caveats (stated explicitly)
- No offline independent hourly/sub-daily RH, and no gridMET-native dewpoint. This is a
  physically-reasoned cross-check against GHCN ground stations, **not** a direct validation of
  gridMET's grid cells. It is entirely possible gridMET's model cells did internally compute
  saturation — but "the product is self-consistent" does not make it physically true; the station
  data show 2023-03-01 was not saturated.
- GHCN `adpt_dewpoint_f` is a daily-average from 1–2 stations/county; the RH-at-Tmax figures
  assume the daily-average dewpoint approximates the afternoon dewpoint. Raising true RH to 100%
  would require an afternoon dewpoint > ~84°F, which is not observed anywhere in TX and is
  contradicted by the 68–72°F daily-average dewpoints.
- `rhav_pct` is available for only 242 of 2,143 pin days (mostly recent years), so the record-wide
  rhav statistic is indicative, not comprehensive; the precip statistic (2,047/2,143 available) is
  robust.
