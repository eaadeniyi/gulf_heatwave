# Definition 02 — relative 95th-percentile daily-mean heat index, ≥2 consecutive days (walk-forward), statewide Texas

**Definition:** a county-relative **95th-percentile daily-MEAN heat index**, sustained
**≥ 2 consecutive days**, **walk-forward** baseline, **2015–2025**, all **254 Texas
counties**. Identical to Definition 01 except the percentile is **95th** (vs 85th) — the
threshold is higher, so it flags only the most anomalous days.

Produced by the **generalized, state-agnostic pipeline** (`pipeline/`) with
`PERCENTILES = [95]`. Everything else is inherited from Definition 01: two windows
(centered 15-day-total ±7; calendar-month), no absolute floor in the primary,
confirmed RH-clip artifacts set to missing, IDW temperature gap-filling, and the same
heatwave day / heatwave event / integer event-duration reporting.

## Results (county-level; pooled totals QA-only)

- **Per-county heatwave days, 2015–2025 (w15):** median **196**, range **18–516**.
- QA-only pooled totals: **w15 ≈ 17,400 events / 52,800 heatwave-days**;
  **month ≈ 17,500 / 53,300** — the two windows agree closely.

### Definition 01 (85th) vs Definition 02 (95th), same everything else

| | Def 01 (85th) | Def 02 (95th) |
|---|---:|---:|
| pooled heatwave-days (w15) | ~170,900 | ~52,800 |
| pooled events (w15) | ~48,300 | ~17,400 |
| per-county heatwave days, median | 677 | 196 |

The 95th-percentile definition yields roughly **one-third** the heatwave days of the
85th — as expected, it captures only the top ~5%-anomalous days for each county/date
rather than the top ~15%. Events are fewer and (per the run-length behaviour seen in
earlier work) tend to be shorter, since sustained runs above a higher bar are rarer.

## Figures (`figures/`)

`map01` heatwave days/county, `map02` events/county, `map03` data-quality (% IDW-imputed),
`map04` NWS advisory-threshold proxy days/county, `dist01` per-county distribution,
`map05` per-year small-multiple maps (shared scale).

## Same carried-forward caveats as Definition 01

- Daily heat-index **proxy** (not hourly-concurrent); Tmax/RH different spatial support.
- County temperature is a **changing multi-station composite + IDW imputation** — the
  county-to-county texture of the maps is only as reliable as the underlying stations
  (`map03` shows which counties are heavily imputed); trust the regional gradient over
  single-county values.
- Even at the stricter 95th percentile this is a **year-round relative** construct
  ("persistent apparent-heat anomaly"); a `mean-HI≥80°F` absolute floor remains an
  available sensitivity (`config.FLOOR_SENSITIVITY_F`).
- NWS proxy: nearest-office crosswalk and most office thresholds are approximate (see
  `../nws_office_crosswalk.csv`, editable).

## Reproduce / extend

This definition is `python run_all.py` with `PERCENTILES = [95]` in `config.py`.
Set `PERCENTILES = [85]` to reproduce Definition 01; set `STATES = ["LA"]` (etc.) to run
another state whose inputs exist. See `pipeline/README.md`.
