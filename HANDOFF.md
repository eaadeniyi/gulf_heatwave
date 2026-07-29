# Session handoff — Texas heatwave classification pipeline

Paste this into a new chat to resume with full context. Everything below reflects the
state at the end of the session.

---

## 1. What this project is

A **state-agnostic pipeline** that classifies county-level **heatwave days** and
**heatwave events** from daily weather, for occupational-heat exposure research.
Developed on **Texas** (5-county pilot → all **254 counties**), study period
**2015–2025**, climate baseline from **1979**. It is **descriptive exposure
classification only** — not injury outcome, not worker heat dose, not official NWS
advisories.

- **GitHub (private):** https://github.com/eaadeniyi/gulf_heatwave  (branch `main`)
- **Local repo root:** `…/heatWaveUS/texas_heatwave_pilot/`  (this folder IS the git repo)
- **User:** Emmanuel Adeniyi (Emmanuel.Adeniyi@lsu.edu), LSU occupational epidemiology.

---

## 2. The two definitions examined (both complete)

```
Definition = county-relative <PCTL>th-percentile daily-MEAN heat index,
             sustained >= 2 consecutive days, walk-forward baseline.
```
- **Definition 01** = 85th percentile.  **Definition 02** = 95th percentile.
- Only the percentile differs; all other logic shared.

**Locked methodology (both definitions):**
- **Metric:** daily-MEAN heat-index proxy = `heat_index(Tmean, mean RH)`, Tmean=(Tmax+Tmin)/2,
  mean RH=(RHmax+RHmin)/2. (A daily-MAX proxy = `heat_index(Tmax, RHmin)` is also computed;
  it feeds the NWS proxy only.) It's a **daily proxy**, not hourly.
- **Threshold:** county-relative percentile, **walk-forward** (year Y ← baseline 1979…Y-1),
  computed on **two windows** reported side by side: **`w15`** = centered 15-day-total (±7 days,
  PRIMARY) and **`month`** = calendar-month bucket.
- **Candidate day:** daily-mean HI **>** its own threshold (strict `>`). No absolute floor in
  the primary (a `mean-HI≥80°F` floor is an available sensitivity, `config.FLOOR_SENSITIVITY_F`).
- **Persistence:** heatwave day = candidate in a run of **≥2 consecutive calendar days**;
  event = one uninterrupted run in one county; duration = end−start+1.
- **Artifacts:** 3 confirmed RH-clip artifact county-days (2023-03-01) set to **missing** in primary.
- **Missing temperature:** filled by **IDW** (inverse-distance-weighted, 1/d², county centroids,
  EPSG:5070); every imputed county-day flagged `temp_imputed`.

**Reporting convention (important — the user is strict about this):**
- Use only: **heatwave day** (county-date), **heatwave event** (one run in one county),
  **event duration** (integer days). Never "event-day".
- **Do NOT** headline a pooled AVERAGE duration ("4.3 days") — report medians / individual events.
- Cross-county pooled totals are **QA-only**, never the headline; substance is county-level.
- Year-round relative construct is a "persistent apparent-heat anomaly", not absolute heat.

---

## 3. Headline results (statewide TX, 254 counties, w15 window)

| | Def 01 (85th) | Def 02 (95th) |
|---|---:|---:|
| heatwave county-days (11-yr) | 170,894 | 52,786 |
| heatwave events | 48,323 | 17,428 |
| per-county heatwave days, median (range) | 677 (154–1,230) | 196 (18–516) |
| event duration, median / max | 3 d / 48 d | 2 d / 31 d |
| % of days in Jun–Sep | 37% | 36% |

- Def 02 ≈ **31%** of Def 01's days. Windows agree **r≈0.99** (w15 vs month).
- **~63% of heatwave days fall OUTSIDE summer** — cool-season "unusual-for-the-date" anomalies
  (December is actually the single highest month). The `≥80°F` floor roughly HALVES counts and
  removes most of these — this is the key open methodological choice.

**Sensitivity findings (archived in `reference/archive_prior_analysis/`):**
- **Fixed 1979–2014 vs walk-forward:** day-level Jaccard 0.923; fixed flags +6.5% more days
  and steeper trend slopes → walk-forward absorbs part of the warming signal; county rankings
  identical (El Paso −6 the only reversal).
- **Anchor-station vs multi-station composite temperature:** heatwave-day Jaccard only
  **0.45–0.73** → the temperature SOURCE changes classification MORE than the baseline choice.
  ⇒ single-county map texture is unreliable; trust the regional gradient. **This is the top
  prerequisite to resolve before injury linkage or firm county rankings.**
- **March 1, 2023 gridMET RH-clip artifact:** RH pinned at 100% in 118/254 counties, inflated
  HI proxy +15–24°F; confirmed artifact, set to missing.
- **NWS proxy:** arid El Paso/Lubbock ≈1 advisory-threshold day in 11 yr (max HI rarely reaches
  105°F) vs humid Houston 172 — the relative-vs-absolute tension.
- IDW: **12.8%** of temperature county-days imputed; 22 counties fully imputed, 93 fully native.

---

## 4. Clean repo layout (after cleanup)

```
texas_heatwave_pilot/            (= git repo root)
  pipeline/        config.py (STATES, PERCENTILES, years, windows, paths, full US FIPS map),
                   heat_index.py (bundled NWS Rothfusz), heatwave_run_logic.py,
                   p01_build_countyday_idw.py, p02_classify_and_report.py,
                   p03_nws_proxy.py, p04_figures.py, run_all.py, nws_offices_TX.csv, README.md
  outputs/TX/      county_daily_heat.csv (git-ignored, ~700MB), coverage_and_imputation_report.csv,
                   nws_office_crosswalk.csv, nws_proxy_county_year.csv,
                   def_p85_2d/  and  def_p95_2d/  -> tables/ + figures/ + FINDINGS_DEF02.md
  reference/       REFERENCE_glossary_methods_results.md, RESULTS_PRESENTATION.md,
                   Heatwave_Reference_Appendix.pptx, Heatwave_Results_Deck.pptx (25 slides),
                   build_*.py, archive_prior_analysis/ (superseded records kept for provenance)
  tests/           test_run_logic.py  (8/8 pass)
  README.md  .gitignore  HANDOFF.md
```
Deleted this session (superseded; recoverable from git history): `figures/`,
`def01_relMeanHI_p85_2d/`, `statewide_TX_def01/`, `scripts/`, `tables/`.

### How to run
```bash
cd pipeline && python run_all.py        # runs p01->p03->p02->p04 for every STATE x PERCENTILE in config.py
```
Change one definition/state by editing `pipeline/config.py` (`PERCENTILES`, `STATES`).
Figures live in `outputs/<ST>/def_p<PCTL>_2d/figures/` (both windows; `_month` suffix = month window).

---

## 5. Environment / gotchas (carry these into the new chat)

- **Python:** `"C:/Program Files/Python314/python.exe"`; pandas 3.0.3, numpy 2.4.6, geopandas,
  Pillow 12, python-pptx 1.0.2. Set `PYTHONIOENCODING=utf-8`; cap BLAS threads (OPENBLAS/OMP/MKL=1).
- **No `pyarrow`** → CSV only.  **No `gh` CLI** → push via Git Credential Manager (browser auth
  popup; the repo already has `origin` set and pushes work).
- **LibreOffice** at `C:\Program Files\LibreOffice\program\soffice.exe` renders pptx/docx→pdf for QA.
- **OneDrive path** can transiently lock files being written (e.g. an open .pptx) → write to the
  scratchpad and copy in, or retry.
- **Session usage limits** were hit during large Workflow subagent fan-outs; verification agents
  failed and were re-done inline. Keep parallel workflows modest.
- Data inputs: `data/raw/gulf_states/{ST}/weather/ghcn_county_day_weather_{ST}.csv` +
  `gridmet_county_day_humidity_{ST}.csv` (exist for TX/LA/MS/AL/FL); shapefile
  `data/raw/census/county_shapefile/tl_2020_us_county.shp`.

---

## 6. Open items / likely next steps

1. **Floor decision:** make `mean-HI≥80°F` the primary (removes cool-season anomalies, halves
   counts) or keep no-floor primary + floor sensitivity. Currently no-floor is primary.
2. **Temperature homogeneity:** resolve the composite-station/IDW noise (anchor-only exposure or a
   homogenized composite) before injury linkage or trusting single-county rankings.
3. **NWS office thresholds:** several are flagged `approximate` in `pipeline/nws_offices_TX.csv`
   (EWX, LUB, AMA, MAF, SJT, CRP, SHV, LCH) — correct against authoritative office criteria.
4. **Extend to other Gulf states** (LA/MS/AL/FL) — works out of the box via `config.STATES`.
5. **Deferred:** fixed 1981–2010 baseline; hourly heat-index validation (needs hourly/dewpoint data
   this project doesn't have).
6. **Presentation:** decks are neutral navy/red — restyle to the user's PowerPoint template if given.
7. Possibly more definitions (the "definition series" — Def 01/02 done; e.g. absolute-HI, Tmax-based,
   3-day persistence variants were discussed as options).

---

## 7. One-paragraph primer (if you only paste one thing)

> Resuming the Texas heatwave classification pipeline (repo: github.com/eaadeniyi/gulf_heatwave,
> local `heatWaveUS/texas_heatwave_pilot/`). State-agnostic, config-driven pipeline in `pipeline/`;
> results in `outputs/TX/def_p85_2d` and `def_p95_2d`. Two definitions done: county-relative 85th
> (Def 01) and 95th (Def 02) percentile daily-MEAN heat index, ≥2 consecutive days, walk-forward
> baseline 1979→Y-1, two windows (centered 15-day primary + calendar-month), no absolute floor in
> primary, IDW-gap-filled temperature, all 254 TX counties, 2015–2025. Reporting uses heatwave
> day/event/duration, county-level (pooled totals QA-only), no pooled-average durations. Python at
> "C:/Program Files/Python314/python.exe"; no gh CLI (push via credential manager). Key open items:
> the ≥80°F floor decision, temperature-composite homogeneity before injury linkage, and correcting
> approximate NWS office thresholds. See HANDOFF.md for full detail.
```
