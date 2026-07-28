# Heatwave Definitions — Results (per definition), Figures, Meaning & Likely Questions

Statewide Texas, all **254 counties**, **2015–2025**, walk-forward baseline, centered
15-day window (primary). Numbers are pulled from each definition's own CSV outputs
(`outputs/TX/def_p85_2d/…` and `…/def_p95_2d/…`). This presents **each definition on
its own**; the two are not being pitted against each other.

Reminder of the unit: a **heatwave day** = one county on one date inside a run of ≥2
consecutive qualifying days; a **heatwave event** = one uninterrupted such run in one
county; **event duration** = its integer number of days. Both definitions are
**year-round, county-relative** ("unusually hot *for this county and time of year*") —
so they measure a *persistent apparent-heat anomaly*, not necessarily absolute heat.

---

# A. Definition 01 — relative **85th-percentile** daily-mean heat index, ≥2 days

### Results from the CSVs

| Statistic | Value | Source (CSV) |
|---|---|---|
| Total heatwave county-days (statewide, 11 yr) | **170,894** | `county_year_summary_w15` |
| Total heatwave events | **48,323** | `county_year_summary_w15` |
| Heatwave days **per county** (11-yr total): median | **677** (p25 568, p75 775; range 154–1,230) | `county_year_summary_w15` |
| Events per county: median | 145 (range ~47–309) | `county_year_summary_w15` |
| Event **duration**: median / mean / max | **3 d / 3.5 d / 48 d** | `heatwave_events_w15` |
| Events that are the minimum 2 days | **44%** | `heatwave_events_w15` |
| Events lasting ≥5 days | **21%** | `heatwave_events_w15` |
| Share of heatwave days in Jun–Sep | **37%** | `daily_heatwave_days_w15` |
| Top counties by heatwave days | La Salle 1,230; Hudspeth 1,198; Lavaca 1,122; Sherman 1,105; Terrell 1,091 | `county_year_summary_w15` |
| Longest single events | Presidio 2023-07-05→08-21 (**48 d**, peak mean-HI 99.5°F); Kendall 2022-07-01→08-09 (40 d, 106.2°F) | `heatwave_events_w15` |

### Figures (`outputs/TX/def_p85_2d/figures/`)

- `map01_heatwave_days_per_county` — choropleth of heatwave days per county.
- `map05_heatwave_days_by_year` — the same, split into 11 per-year maps (shared scale).
- `dist01_heatwave_days_hist` — distribution of per-county totals across the 254 counties.
- `res_annual_days` — statewide heatwave days each year.
- `res_event_duration` — how long events last (share by duration).
- `res_seasonal` — share of heatwave days by month (Jun–Sep outlined).
- `res_top_counties` — the 15 counties with the most heatwave days.

### What the numbers/figures mean

- **A broad "elevated-exposure" net.** At the 85th percentile the typical county spends
  ~677 days over 11 years (≈62/yr) in a ≥2-day heat anomaly. This is an *inclusive*
  screen: it captures a lot of moderately-anomalous heat.
- **Mostly short episodes, with a long tail.** 44% of events are the minimum 2 days and
  the median is 3 days, but 21% run ≥5 days and a few are very long (the 48-day Presidio
  2023 spell). The long tail is the relative construct stringing together persistently
  above-normal days — real, but better called a "prolonged apparent-heat anomaly" than a
  classic heatwave.
- **Only ~37% of days are in summer.** ~63% are cool-season "unusual-for-the-date" days
  (the December/February spikes in `res_seasonal`), i.e. warm anomalies that need not be
  absolutely hot. This is the defining feature (and caveat) of a year-round relative rule.

---

# B. Definition 02 — relative **95th-percentile** daily-mean heat index, ≥2 days

### Results from the CSVs

| Statistic | Value | Source (CSV) |
|---|---|---|
| Total heatwave county-days (statewide, 11 yr) | **52,786** | `county_year_summary_w15` |
| Total heatwave events | **17,428** | `county_year_summary_w15` |
| Heatwave days **per county** (11-yr total): median | **196** (p25 148, p75 254; range 18–516) | `county_year_summary_w15` |
| Event **duration**: median / mean / max | **2 d / 3.0 d / 31 d** | `heatwave_events_w15` |
| Events that are the minimum 2 days | **53%** | `heatwave_events_w15` |
| Events lasting ≥5 days | **14%** | `heatwave_events_w15` |
| Share of heatwave days in Jun–Sep | **36%** | `daily_heatwave_days_w15` |
| Top counties by heatwave days | La Salle 516; Presidio 513; Hudspeth 508; Kendall 478; Sherman 461 | `county_year_summary_w15` |
| Longest single events | Kendall 2022-07 (**31 d**, 106.2°F); Lee 2019-08 (25 d, 107.7°F); Presidio 2023-07 (24 d, 99.5°F) | `heatwave_events_w15` |

### Figures (`outputs/TX/def_p95_2d/figures/`)

Same file names as Definition 01, in the `def_p95_2d/figures/` folder
(`map01`, `map05`, `dist01`, `res_annual_days`, `res_event_duration`, `res_seasonal`,
`res_top_counties`).

### What the numbers/figures mean

- **A severe-tail screen.** At the 95th percentile the typical county spends ~196 days
  over 11 years (≈18/yr) in a heat anomaly — it isolates each county's most anomalous
  ~5% of days.
- **Shorter, sparser episodes.** The median event is the minimum 2 days and 53% of events
  are exactly 2 days (vs 44% at the 85th) — a stricter bar produces fewer sustained runs.
  Long events still occur (Kendall 2022, 31 days) but are rarer (14% ≥5 days).
- **Still a year-round relative measure.** ~36% of days in Jun–Sep — essentially the same
  seasonal spread as Definition 01, confirming the ~63%-cool-season pattern is a property
  of the *relative* method, not of the percentile chosen.

---

# B2. Threshold-window robustness (both definitions were run on BOTH windows)

Every definition is computed on **two** threshold windows — the centered 15-day
(`w15`, primary, shown above) **and** the calendar-month bucket (`month`). The
calendar-month outputs exist in each definition's folder
(`thresholds_month`, `county_year_summary_month`, `heatwave_events_month`,
`daily_heatwave_days_month`, `county_month_summary_month`). The two windows agree
almost exactly, so the window choice is not driving any result:

| Metric | Def 01 — 15-day | Def 01 — month | Def 02 — 15-day | Def 02 — month |
|---|---:|---:|---:|---:|
| Pooled heatwave-days | 170,894 | 171,115 | 52,786 | 53,273 |
| Pooled events | 48,323 | 47,470 | 17,428 | 17,517 |
| Per-county median days | 677 | 678 | 196 | 194 |
| Per-county range | 154–1,230 | 144–1,233 | 18–516 | 15–510 |
| Event duration median | 3 d | 3 d | 2 d | 2 d |
| **Per-county correlation (15-day vs month)** | **r = 0.994** | | **r = 0.987** | |

**Meaning:** the centered-15-day and calendar-month baselines produce essentially
the same catalog (differences < 1% in totals, r ≈ 0.99 per county). We report the
15-day as primary; the month window is a robustness check, not a different answer.

---

# C. Shared companion outputs (definition-independent)

These do not depend on the 85th/95th choice:

- **Data coverage / IDW imputation.** Statewide, ~13% of temperature county-days are
  IDW-interpolated; **22 counties have no native station** (fully imputed) and **93 are
  fully native**. See `map03_pct_days_imputed_per_county`. → single-county map texture is
  noisy; the regional gradient is the trustworthy signal.
- **NWS advisory-threshold proxy** (`nws_proxy_county_year.csv`, `map04`). Using each
  county's local NWS office heat-index thresholds against the daily-max HI proxy: humid
  eastern/coastal counties (Houston office ≈108°F) accumulate many advisory-threshold
  days, while arid far-west counties (El Paso office) record almost none — the same day
  can be a *relative* heatwave without reaching an *absolute* advisory level. This is a
  **proxy**, not an official advisory.

---

# D. Likely / scenario questions (with answers)

*Generated by a four-perspective reviewer panel — occupational epidemiology, climatology,
biostatistics, and a skeptical committee member — grounded in the numbers above.*

**Q1 (face validity). Only ~37% of "heatwave" days are in June–September — how is a warm
January day a heatwave?**
By design: both definitions are *year-round, county-relative* percentile rules, so they
flag days that are anomalously warm **for the date**, not absolutely hot. ~63% of days are
cool-season anomalies. For an absolute-heat framing, apply the optional **mean-HI ≥ 80°F
floor** (roughly halves the counts and removes most cool-season days) or restrict to a
warm season — and relabel the raw series a "persistent apparent-heat anomaly" index.

**Q2 (metric). Why a daily-MEAN heat index — doesn't heat illness come from the afternoon
peak?**
The mean targets *persistent* day-and-night apparent heat (including warm overnight
minima, which matter physiologically) rather than a single peak. The trade-off is real: it
under-weights the afternoon peak and is a **daily proxy, not hourly** — so it is an
exposure *classification*, not a worker heat *dose*.

**Q3 (proxy validity). Heat index is defined on hourly data — how valid is a daily proxy?**
It is an approximate NWS heat-index proxy from GHCN-Daily temperature + gridMET humidity.
Absolute values carry uncertainty, so we treat the **regional gradient as robust** and
single-county texture and trend slopes as **descriptive only**.

**Q4 (data quality). With ~13% of county-days imputed and 22 counties fully imputed, can I
trust the county maps?**
Trust them **regionally, not pixel-by-pixel**. Fully-imputed counties carry no local
station, so their per-county totals (and the extreme min/max values) partly reflect data
density; flag or exclude them for any single-county claim. Statewide totals and the broad
gradient don't hinge on any one imputed county.

**Q5 (persistence). Is a 2-consecutive-day exceedance really a "wave," and is a 48-day
event credible?**
The ≥2-day rule is a minimum-persistence filter; the catalog is short-event-heavy (44%/53%
are exactly 2 days), so "elevated exposure" is a fairer label than "wave" for much of it.
The long tails (Presidio 48 d) are genuine persistent anomalies surfaced by the relative
rule — report the **duration distribution and median**, not the maximum, as typical.

**Q6 (thresholds). Why 85th and 95th specifically — aren't those arbitrary?**
They are conventional relative heat thresholds (the 95th has published precedent), chosen
to bracket a **moderate** and a **severe** cut. They are not claimed to be uniquely
correct; a fuller threshold-sensitivity sweep would be a reasonable extension.

**Q7 (mechanics). A percentile fixes the exceedance rate — isn't the day count preordained?**
The single-day rate is anchored (~15% at the 85th, ~5% at the 95th) by construction, but
the reported totals are also shaped by the ≥2-day persistence rule and the walk-forward
baseline, so they are not fully mechanical. The informative content is **where and when**
heat clusters, not the grand total — which we present as exposure frequencies, not
incidence.

**Q8 (windows). How sensitive are the results to the 15-day window vs a calendar month?**
Not sensitive — the two windows agree at **r ≈ 0.99** per county and give nearly identical
totals. Window choice is not driving anything; the consequential levers are the percentile
and the absolute-floor/season choice.

**Q9 (claims). What can these results actually support?**
County-level **environmental apparent-heat exposure classification**. They do **not**
support worker heat dose, causal injury claims, or official-advisory equivalence; any
downstream injury association should be read as an ecological exposure-window analysis.

**Q10 (the floor). If the ≥80°F floor fixes the cool-season problem, why isn't it the
default?**
Because the primary question is a *relative anomaly*; making an absolute floor the default
would answer a different question. It is offered as a **companion/sensitivity** that keeps
only days that are both anomalous **and** absolutely warm.

**Q11 (spatial noise). Some adjacent counties differ sharply (e.g., La Salle vs a neighbor)
— is that real climate?**
Largely **not** — it reflects the changing multi-station composite temperature plus IDW
imputation, not micro-climate. This is exactly why single-county rankings are presented
cautiously and the regional gradient is the headline.

**Q12 (choice). Which definition should be primary?**
It is a sensitivity/specificity choice, not a right/wrong one: the 85th is the *inclusive*
screen (more exposed days, more power), the 95th the *specific* severe tier (~⅓ the days).
A defensible plan reports one as primary and the other as a sensitivity bound, paired with
the ≥80°F floor for absolute-heat plausibility.

---

# E. Caveats to keep on any results slide

- Daily heat-index **proxy** (not hourly); temperature and humidity have different spatial support.
- County temperature is a **changing multi-station composite + IDW imputation** → single-county
  values noisy, regional gradient robust.
- **Year-round relative construct** = persistent apparent-heat anomaly; ~63% of days are sub-summer
  cool-season anomalies unless the ≥80°F floor is applied.
- NWS proxy is **approximate** and not an official advisory; trend slopes are **descriptive only**.
- **Exposure classification, not injury or worker-dose.**
