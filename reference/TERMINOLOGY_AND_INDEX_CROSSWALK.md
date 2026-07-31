# Terminology and index crosswalk

This project has been naming quantities for its own convenience (`heatwave day`,
`county-year mean Tmax`, `walk-forward baseline`, `w15`). Those names are fine inside the
code but several of them are not what the literature calls these things, so a reader or
reviewer cannot map our tables onto published work — and in at least three places our
construct genuinely **differs** from the standard one, which needs saying out loud rather
than hiding behind a private vocabulary.

This file is the mapping. **Rule adopted: internal column names stay as they are (they are
referenced across two committed packages and by the reconciliation gates), but everything a
reader sees — axis labels, captions, prose, papers — uses the published name.** Where we
diverge from a standard, the divergence is stated rather than the standard's name being
borrowed for something it does not describe.

The two frameworks that cover almost everything we compute:

- **ETCCDI / WMO core climate indices** (27 indices; the standard vocabulary for temperature
  extremes: `TX`, `TN`, `TG`, `TXm`, `TX90p`, `WSDI`, `SU`, …).
- **Perkins & Alexander (2013), "On the Measurement of Heat Waves"** (*J. Climate* 26,
  4500–4517), which defines the five *aspects* of a heatwave (`HWN`, `HWF`, `HWD`, `HWM`,
  `HWA`) — these map one-to-one onto the quantities our event tables already carry.

---

## 1. Temperature variables and means

| our name / column | published name | meaning |
|---|---|---|
| `tmax_f` | **TX** | daily maximum temperature |
| `tmin_f` | **TN** | daily minimum temperature |
| `tmean_f` = (Tmax+Tmin)/2 | **TG** | daily mean temperature (this is the (TX+TN)/2 approximation, not a 24-h integral — say so when reporting) |
| "county-year mean Tmax" | **TXm**, *annual mean daily maximum temperature* | mean of TX over the averaging period |
| "county-year mean Tmin" | **TNm**, *annual mean daily minimum temperature* | mean of TN |
| "county-year mean Tmean" | **TGm**, *annual mean daily mean temperature* | mean of TG |
| `derived_tmean_meanrh_hi_f` | *daily mean heat-index proxy* — **no standard ETCCDI index**; describe in full as `heat_index(Tmean, mean RH)` | not comparable to an hourly or maximum heat index; keep calling it a proxy |
| Tmax − Tmin | **DTR** (diurnal temperature range) | relevant to our finding that TN is warming faster than TX, i.e. DTR is narrowing |

**The unit of observation is not part of the quantity's name.** "Annual mean daily maximum
temperature (TXm)" is the quantity; "one point per county-year" is the sampling. Putting
`county-year` into the axis label — as Figure E2 originally did — names a data structure, not
a physical quantity, and means nothing to a reader outside this repository.

## 2. Heatwave aspects — use Perkins & Alexander's names

Our event tables already contain all five aspects under home-made names:

| our name | published aspect | definition |
|---|---|---|
| heatwave **days** (county-dates in qualifying runs) | **HWF** — heatwave frequency | total number of heatwave days in the period |
| heatwave **events** | **HWN** — heatwave number | count of discrete qualifying spells |
| `longest_event_duration_days` | **HWD** — heatwave duration | length of the longest spell |
| `peak_metric_value_f` / `peak_*` | **HWA** — heatwave amplitude | hottest day of the hottest spell |
| `mean_metric_value_f` | **HWM** — heatwave magnitude | mean temperature across heatwave days |

Adopting these four-letter names in tables and papers connects our output to a well-cited
framework at no analytical cost. Our internal terms (heatwave day / event / duration) can
stay in the code and in plain-language explanation — they are unambiguous — but published
tables should carry the HWF/HWN/HWD/HWM/HWA labels too.

## 3. Threshold construction

| our name | published name | note |
|---|---|---|
| "walk-forward baseline" (year Y judged against 1979…Y−1) | **moving (shifting) baseline**, expanding-window form | the literature's contrast is *fixed* vs *moving* baseline; "walk-forward" is our coinage |
| archived fixed 1979–2014 sensitivity | **fixed baseline** | ETCCDI's own convention is a fixed 30-year reference (1961–1990 or 1981–2010) |
| `w05` (centred ±2 days) | **the ETCCDI/WMO standard window** — 5-day window centred on each calendar day | our `w05` *is* the international convention for percentile-based temperature indices |
| `w15` (centred ±7 days) | the **15-day** calendar-day window used in the heatwave literature (Perkins & Alexander's `CTX90pct`) | our primary window matches the heatwave papers rather than the index standard — a defensible choice, but state which convention you are following |
| `month`, `month_pm7` | no standard equivalent | calendar-month pooling is our own; report as a sensitivity, not as a recognised convention |
| "candidate day" | *threshold exceedance day* | fine as an internal term |
| absolute floor `Tmax > 90 °F` | **fixed-threshold index** — the ETCCDI family member is `SU` (*summer days*, TX > 25 °C); software convention is xclim's `tx_days_above(thresh=...)` | US public-health work usually just says "days with maximum temperature above 90 °F" |

## 4. Named relatives of our definitions

| our definition | closest published index | difference |
|---|---|---|
| `TMAX_P90_2D` etc. | **TX90p** (ETCCDI) counts days above the calendar-day 90th percentile | TX90p has **no persistence requirement** and is reported as a *percentage* of days; ours requires ≥N consecutive days and reports counts |
| `TMAX_P90_*D` with persistence | **WSDI** (warm spell duration index) | WSDI fixes the rule at **≥6 consecutive days**, 90th percentile, 5-day window, **fixed** 1961–1990 base — ours varies the duration (≥2/≥3/≥5), uses a moving baseline, and (at w15) a 15-day window |
| `TMAX_P90_2D` at `w15` | **`CTX90pct`** (Perkins & Alexander 2013) | closest match in the literature: calendar-day 90th percentile of TX on a 15-day window. Their heatwave definition uses ≥3 consecutive days |
| `TMAX_ABS90_*D` | `SU`-family fixed-threshold count / "days ≥ 90 °F" | ours adds a persistence rule, which the standard indices do not |
| `MHI_P85_2D` / `MHI_P95_2D` (Def 01/02) | no standard equivalent | percentile of a *daily mean heat-index proxy*; describe fully, do not imply an ETCCDI index |

## 5. Where we deliberately DIVERGE — state these in any write-up

1. **Spells crossing the year boundary.** ETCCDI's `WSDI` specifies that spells **cannot span
   years**. Our rule deliberately preserves one physical episode across 31 December and counts
   it once in its onset year. This is not cosmetic: **10,046 events span a year boundary** in
   the 64-run comparison. Our choice is defensible for a year-round definition — truncating a
   run at midnight on 31 December is an artefact of the calendar — but it is a divergence and
   must be declared, because it makes our event counts not directly comparable with `WSDI`.
2. **Moving rather than fixed baseline.** ETCCDI percentiles come from a fixed 30-year
   reference period. Ours expand each year (1979…Y−1). A moving baseline suppresses trend by
   construction (our own earlier sensitivity: fixed baseline flags +6.5% more days and steeper
   slopes), which is exactly the "saturation" problem the baseline literature describes. Any
   trend statement has to name the baseline.
3. **Percentile window.** `w15` (our primary) follows the heatwave literature; `w05` follows
   the ETCCDI/WMO index standard. If a result is meant to be compared with published *indices*,
   report `w05`; if with published *heatwave papers*, `w15`. Both exist in our output.
4. **Spatial unit.** ETCCDI indices are computed at stations or grid cells. Ours are computed
   on **county-day aggregates** (multi-station averages, IDW gap-filled). A county-day Tmax is
   not a station observation — this is why exact ties on an 80 °F floor occur at all (643
   county-days) when 0.1 °C-quantised station data could not produce them.
5. **Counts, not percentages.** `TX90p` is a percentage of days; we report day counts and, for
   rates, days per 1,000 *eligible* county-days. State the denominator.

## 6. Recommended reader-facing labels

| context | write this |
|---|---|
| annual temperature axis | `Annual mean daily maximum temperature, TXm (°F)` |
| monthly temperature axis | `Mean daily maximum temperature, TXm (°F)` |
| heatwave day counts | `Heatwave frequency, HWF (days)` |
| heatwave event counts | `Heatwave number, HWN (events)` |
| longest spell | `Heatwave duration, HWD (days)` |
| our threshold rule | `calendar-day 90th percentile of TX, 15-day window, moving baseline (1979 to year−1)` |
| our absolute rule | `days with TX above 90 °F, ≥2 consecutive days` |
| the caveat sentence | `year-round, county-relative and with no absolute floor, so a qualifying day is unusual for its own date rather than absolutely hot` |

## 7. Implementation status

- **Applied:** all `outputs/extreme_temp_tests/` figure axis labels and captions now use
  TX/TN/TG and TXm/TNm/TGm (`etx_config.axis_label()` is the single source).
- **Not applied, on purpose:** CSV column names and definition IDs (`TMAX_P90_2D`,
  `heatwave_days`, `per_county_heatwave_days_median`, …) are unchanged. They are referenced by
  two committed packages, by the reconciliation gates that prove our rebuilds match the
  published runs, and by `pipeline/definition_registry.csv`. Renaming them would invalidate
  those checks for a cosmetic gain. If you want the columns renamed too, it is a mechanical
  pass plus a re-run of both packages — say so and I will do it and re-verify.
- **Suggested next step for papers:** add `HWF` / `HWN` / `HWD` as alias columns beside the
  existing names in the event and county-year tables, so a table can be lifted straight into a
  manuscript.

## Sources

- ETCCDI core indices list and definitions (`TX90p`, `WSDI`, `SU`, `TXx`): <https://etccdi.pacificclimate.org/list_27_indices.shtml>
- ETCCDI index definitions incl. `TXm` and the 5-day centred percentile window: <https://www.met.ie/climate/climate-change-indices-etccdi>
- Copernicus / ECA&D indices dictionary (`TX`, `TN`, `TG` naming): <https://surfobs.climate.copernicus.eu/userguidance/indicesdictionary.php>
- Perkins, S. E. and Alexander, L. V. (2013). On the Measurement of Heat Waves. *Journal of Climate* 26, 4500–4517: <https://journals.ametsoc.org/view/journals/clim/26/13/jcli-d-12-00383.1.xml>
- IPCC AR6 WG1 Annex VI, Climatic Impact-driver and Extreme Indices: <https://www.ipcc.ch/report/ar6/wg1/downloads/report/IPCC_AR6_WGI_AnnexVI.pdf>
- xclim indicator naming (`tx_days_above`, etc.): <https://xclim.readthedocs.io/en/v0.38.0/indicators.html>
- Fixed vs moving baseline terminology and the saturation problem: <https://rmets.onlinelibrary.wiley.com/doi/10.1002/asl2.70017> and <https://www.sciencedirect.com/science/article/pii/S0079661124002106>
- Effect of baseline period on quantifying US climate extremes: <https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2023GL105204>
