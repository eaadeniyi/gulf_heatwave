# Session handoff — Texas heatwave classification pipeline

Paste this into a new chat to resume with full context. Everything below reflects the
state at the end of the session.

---

## 0. LATEST ROUND (2026-07-31): EXTREME-TEMPERATURE + ABSOLUTE-FLOOR TESTS

In `outputs/extreme_temp_tests/` — **read `FINDINGS.md` first.** Three parts, own scripts
(`e01`–`e04`), nothing in `pipeline/` or `outputs/definition_comparison/` touched.

**Part 1 — Gulf-state temperature, 1979–2025, all 5 states** (TX/LA/MS/AL/FL) from the RAW
GHCN county-day record (observed only, no IDW: the question was what the record IS). 2026
excluded as a partial year. Coverage gate (≥328 valid days/county-year) + a BALANCED county
panel for all period comparisons, because the reporting network shrinks (TX 225→189 counties).
That control matters: Alabama's Tmax warming reads **+1.38 °F** balanced vs **+0.80 °F**
unbalanced.
- Warming since the 1980s (balanced, °F): **Tmax** MS +2.35, TX +2.04, LA +1.76, AL +1.38,
  FL +1.17. **Tmin is larger in every state**: MS +3.43, FL +3.29, TX/AL +2.71, LA +2.64 —
  the diurnal range is narrowing, so Tmin and Tmax definitions are diverging over time, not
  just disagreeing day to day.
- **The warming is concentrated OUTSIDE summer.** Tmax change by month: December **+6.2 °F in
  TX**, +4.9 MS; February +5.0 AL, +4.8 MS; October +3.8 TX — while **Jun–Aug moved ≤ +2.4 °F
  anywhere and went negative in 2 state-months.** This is the physical reason the year-round
  relative definitions load onto the cool season.

**Part 2 — county-relative Tmax, 80th/85th/90th × ≥2/≥3/≥5 days, all 4 windows (36 runs).**
The 4 cells that overlap the delivered grid reproduce it **exactly (32/32 checks)**. Per-county
median heatwave days at w15: 815 (P80/2D) → 162 (P90/5D). **The cool-season loading survives
all nine cells (49–63% outside Jun–Sep)** — no percentile or duration choice fixes it.

**Part 3 — absolute floors at 80 °F and 90 °F, tested BOTH ways** (the ask was ambiguous, so
both readings were run):
- **as a GATE** (percentile AND Tmax ≥ floor), 18 runs at w15: **90 °F takes the cool-season
  share from ~60% to 20–30% and keeps 49–66% of days; 80 °F only reaches 40–54%** and keeps
  75–86%. With a 90 °F floor, Nov–Mar go to ≈0 and the profile becomes single-peaked in August;
  unfloored, the peak month is **December**.
- **as ABSOLUTE-ONLY** (Tmax > floor, no percentile — no baseline, so no window axis), 6 runs:
  **Tmax > 80 °F flags a median 2,040 county-days = 51% of ALL days in Texas** — not an extreme
  criterion. Tmax > 90 °F flags 1,104 (27%) and is strongly seasonal (12% outside Jun–Sep).
  Agreement with the relative rules is only **Jaccard 0.08–0.28**: different constructs, not
  variants.
- The floor also changes the GEOGRAPHY (fig E9): a relative rule flags similar counts
  everywhere by construction; a floor concentrates exposure in the hottest counties.

**So the floor/season decision now has numbers:** a 90 °F Tmax gate is the option the data
supports, at the cost of ~half the classified days and a renamed construct ("unusual for this
date AND hot in absolute terms"). An 80 °F floor is too low to change the definition's
character in Texas.

**QA note:** 643 county-days sit exactly on the 80 °F floor (2 on 90 °F) because a county-day
Tmax is a multi-station average, so `>` vs `>=` is not equivalent — 0.063% of days, immaterial
here but recorded in `qa/e02_floor_operator_check.csv`.

Parts 2–3 are **TX only**; both are state-agnostic and run for another Gulf state once that
state's county-day table is built (only TX has one).

---

## 0a. PREVIOUS ROUND (2026-07-30): the 16-definition COMPARISON PACKAGE

A self-contained comparison package for **all 16 definitions** (Def 01/02 + the 14 grid
definitions) × 4 threshold windows = **64 runs**, in `outputs/definition_comparison/`.
**Read `DECISION_TABLE.md` first, then `figure_captions.md`, then `methods_notes.md`.**
Rebuild with `python outputs/definition_comparison/scripts/run_package.py` (~20 min).

**Def 01/02 were RE-RUN onto the current code path** (`scripts/s01_rerun_legacy.py`) because the
published outputs were not comparable as they stood: they came from an older p02 (different
output schema — no `event_id`, no `metric` column), only 2 of the 4 windows were ever run, and no
input fingerprint was recorded. The re-run reproduces the published results **exactly** (46/46
checks: every county-year, the complete event set, 170,894/48,323 and 52,786/17,428) and now sits
at `outputs/TX/grid/MHI_P85_2D` and `MHI_P95_2D` alongside the other 14. `def_p85_2d`/`def_p95_2d`
were never touched.

**Contents:** a canonical long table (one row per county × date × definition × window, stored at
its candidate-day support, 107 MB gzipped); the 8 required tables; 12 figure families —
design matrix, count-vs-agreement, 16×16 day-level Jaccard, county-rank stability, monthly RATE
heatmap, percentile/duration ladder over 2,794 county-years, window sensitivity, **254 county
report cards**, event timelines, long-event audit, data-quality influence, pair disagreement;
and a `qa/` record (provenance, reconciliation, 136 validation checks).

**Headline results (w15, 254 counties) — consistent with the 56-run round and sharper:**
1. **Axis ranking by day-level effect: metric 0.333 < percentile 0.492 < window 0.687 <
   duration 0.747** (Jaccard medians, lower = bigger effect; 240 matched pairs).
2. **Metric changes WHICH days, not HOW MANY** — median count ratio 1.12× at median Jaccard
   0.333. Percentile is the count lever (2.03×, up to 3.54×).
3. **County rankings are more stable than day agreement** (median ρ 0.744 vs median Jaccard
   0.323) and the complete-data subset (188 counties) barely changes it — *but* Tmax-vs-Tmin
   rank agreement is only **0.40–0.56** against 0.96 within a metric family. The metric axis
   breaks county ORDER too, which no other axis does.
4. **Cool-season loading confirmed as a RATE, not just a share:** 51–64% of heatwave days fall
   outside Jun–Sep in all 16 definitions, measured per 1,000 **eligible** county-days. December
   is the peak month by rate for every mean-HI definition.
5. **734 events ≥ 21 days at w15** (3,133 across all 64 runs, longest 69 d); 150 audited
   individually with station counts and imputation state, the remaining 584 tabulated. None
   deleted.

**Two QA findings that change how the pipeline must be read:**
- **(a) Float parsing changed classification.** pandas' default CSV float parser is not
  correctly rounded: a cached threshold written `101.74999999999999` reads back as `101.75`, and
  under the strict `>` that silently drops county-days. Threshold caches must be read with
  `float_precision="round_trip"` (19 of 128 reconciliation checks were off by 1–4 county-days
  before the fix).
- **(b) Exact ties are metric-dependent.** Tmax/Tmin are quantised to 0.1 °C, so a percentile
  often lands exactly on an observed value: **1.13% (Tmax) / 1.44% (Tmin) / 0.00% (mean HI)** of
  evaluable county-days sit on their own threshold. So `>` vs `>=` removes ~1–2% of days from the
  temperature definitions and **none** from mean HI — an asymmetry inside every
  Tmax/Tmin-vs-mean-HI comparison. Quantify it before leaning on those contrasts.

**Test gate fixed:** `tests/test_reproduce_def01_def02.py` had been unable to compare the event
sets since events were gzipped (it looked for `.csv`); it now accepts either and passes in full.

**MHI_P85_3D / MHI_P95_3D remain NOT TESTED** and are carried as such everywhere (never zero,
never interpolated across). They are the reason the duration axis rests on 28 matched pairs
against 60 for percentile. Their thresholds are already cached, so running them is cheap.

---

## 0b. PREVIOUS ROUND (2026-07-29): the definition grid — 14 definitions × 4 windows

A **definition grid** was added on top of Def 01/02: `metric × percentile × min duration`,
each crossed with 4 threshold windows = **56 runs**, all 254 TX counties, 2015–2025.
Metrics: **Tmax**, **Tmin**, **daily-mean heat index**. Percentiles: 85/90/95 (mean HI at 90
only — 85/95 are Def 01/02). Durations: ≥2, ≥3 days. Windows: `w05` (centered ±2), `w15`
(centered ±7), `month`, `month_pm7` (calendar month ±7 days). Everything else held fixed
(walk-forward, strict `>`, year-round, no floor) so differences are attributable to those
four axes only.

**Read `outputs/TX/grid/_comparison/FINDINGS_DEFINITION_GRID.md` first** — it is the
substantive result of this round. Headline conclusions:

1. **Metric changes WHICH days, not HOW MANY** — the key finding. Tmax vs Tmin at matched
   percentile/duration/window: day-level Jaccard **0.245**, yet Tmin counts only 13% more
   days. Mean HI vs Tmax at the 90th: pooled counts 1.7% apart but Jaccard 0.35–0.39. Three
   metrics that look interchangeable in count tables disagree on **60–75% of exposure days**.
2. **Axis ranking by day-level effect:** metric 0.292 < percentile 0.493 < window 0.693 <
   duration 0.747 (Jaccard medians; lower = bigger effect). Metric changes classification
   *more than switching the temperature data source did* (yardstick 0.45–0.73).
3. **Percentile is the count lever:** 95th→85th = 3.08× heatwave days.
4. **Window matters least.** `month` vs `month_pm7` = 0.886 (near-duplicates); `w05` vs `w15`
   = 0.851. Counts fall monotonically with pooling width in all 14 definitions. The previous
   round's w15/month reporting was robust. `month_pm7` could be dropped in future rounds.
5. **Duration is nested by construction** — ≥3-day days are a strict subset of ≥2-day days
   (verified: 0 exceptions, Jaccard == count ratio exactly). ~25% of days lost per extra day.
6. **Cool-season loading is INTRINSIC, not a heat-index artifact.** Every one of the 14
   definitions puts 51–63% of heatwave days outside Jun–Sep and 29–33% in Nov–Feb. Changing
   metric/percentile/duration/window does not fix it ⇒ **the floor / season decision can no
   longer be deferred** (this closes an open question from the previous round).
7. **County rankings are unstable across definitions:** Spearman median 0.754 (0.300–0.996),
   only 37% of pairs > 0.90. Reinforces the existing "trust the regional gradient" caveat.

**How definitions are tracked:** `pipeline/definition_registry.csv` is **regenerated from
config.py on every run and iterated by the runner**, so it cannot drift from what actually
ran. IDs are `TMAX_P90_2D` (definition) and `TMAX_P90_2D__w15` (run). Def 01 = `MHI_P85_2D`,
Def 02 = `MHI_P95_2D`; the grid is Def 03–Def 16, each mapped to its request item number.
`outputs/TX/grid/run_log.csv` records git commit + input hash per run.

**Refactor safety.** p02 was generalised from one metric to any metric, and the run/event
logic gained a vectorised panel implementation (the grid needs ~1M county-days × 56 runs).
Both are gated by tests: `tests/test_reproduce_def01_def02.py` proves the generalised code
still reproduces the published Def 01/02 exactly (every county-year, the complete event set,
170,894/48,323 and 52,786/17,428); `tests/test_panel_equivalence.py` proves the vectorised
logic equals the readable reference implementation (471 frame comparisons);
`tests/test_windows.py` proves all four windows pool the calendar days they claim to. **Run
all four test files after touching p02 or heatwave_run_logic.py.**

**Input provenance.** The grid does NOT re-run p01 — it reuses `outputs/TX/county_daily_heat.csv`
(all three metrics are already derived in it, so nothing p01 does changes between definitions).
That shortcut is verified, not assumed: `tests/test_input_provenance.py` re-runs p01 from the
raw **GHCN** (`ghcn_county_day_weather_TX.csv`, Tmax/Tmin/precip) and **gridMET**
(`gridmet_county_day_humidity_TX.csv`, RHmax/RHmin) files into a temp dir and confirms it
reproduces the consumed table **byte-identically** (md5 `f0276ee5888539f9dd4df1b3c7d2435e`,
matching the fingerprint in `grid/run_log.csv`), and that the table spans the full
1979–2025 record so walk-forward thresholds are estimated from the source data. Re-run it
when the raw inputs change or to re-establish provenance for a published result set (~1 min).

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
  pipeline/        config.py (STATES, METRICS, GRID_WINDOWS, GRID_DEFINITIONS, years, paths,
                   full US FIPS map), definition_registry.csv (THE RUN LIST, regenerated),
                   heat_index.py (bundled NWS Rothfusz), heatwave_run_logic.py (readable
                   reference impl + vectorised panel impl),
                   p01_build_countyday_idw.py, p02_classify_and_report.py (any metric x
                   percentile x duration x window), p03_nws_proxy.py, p04_figures.py,
                   p05_definition_comparison.py, p06_results_tables.py,
                   run_grid.py (the grid), run_all.py (legacy Def 01/02), nws_offices_TX.csv
  outputs/TX/      county_daily_heat.csv (git-ignored, ~700MB), coverage_and_imputation_report.csv,
                   nws_office_crosswalk.csv, nws_proxy_county_year.csv,
                   def_p85_2d/  and  def_p95_2d/  -> tables/ + figures/ + FINDINGS_DEF02.md
                   grid/        <DEFINITION_ID>/tables|figures  (Def 03-16, window in filename)
                                _thresholds/       shared threshold cache (git-ignored)
                                _state_figures/    definition-independent figs, rendered once
                                _comparison/       FINDINGS_DEFINITION_GRID.md,
                                                   RESULTS_TABLES_DEFINITION_GRID.md,
                                                   tables/ (master + agreement + marginal),
                                                   figures/ cmp01-cmp06
                                run_log.csv        provenance per run
  reference/       REFERENCE_glossary_methods_results.md, RESULTS_PRESENTATION.md,
                   Heatwave_Reference_Appendix.pptx, Heatwave_Results_Deck.pptx (25 slides),
                   build_*.py, archive_prior_analysis/ (superseded records kept for provenance)
  tests/           test_run_logic.py (8/8), test_panel_equivalence.py (vectorised == reference),
                   test_reproduce_def01_def02.py (published results defended),
                   test_windows.py (all 4 windows pool the right calendar days)
  README.md  .gitignore  HANDOFF.md
```
Deleted in the prior session (superseded; recoverable from git history): `figures/`,
`def01_relMeanHI_p85_2d/`, `statewide_TX_def01/`, `scripts/`, `tables/`.

### How to run
```bash
cd pipeline
python run_grid.py                     # the 56-run definition grid (~7.5 min); resumable
python p04_figures.py                  # full figure set per run (~15 min, ~400 PNGs)
python p05_definition_comparison.py    # agreement / marginal effects / rank stability
python p06_results_tables.py           # regenerate RESULTS_TABLES_DEFINITION_GRID.md
python run_all.py                      # LEGACY single-definition path (Def 01 / Def 02)
```
`run_grid.py` filters and resumes: `--metric tmax --percentile 90 --duration 3 --window w15
--def-number 7 --force --registry-only --no-daily`. Runs already on disk are skipped unless
`--force`. Add a definition by appending one line to `GRID_DEFINITIONS` in `config.py`.
Thresholds depend on metric × window only (not duration), so 12 threshold passes serve all
56 runs and are cached to `grid/_thresholds/`.

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

1. **Floor / season decision — now UNAVOIDABLE.** The grid showed the cool-season loading is
   intrinsic to the year-round relative construct: all 14 definitions put 51–63% of heatwave
   days outside Jun–Sep and 29–33% in Nov–Feb, at every metric, percentile, duration and
   window. So it cannot be fixed by choosing a different definition — it needs either the
   `mean-HI≥80°F` (or `Tmax≥80°F`) absolute floor made primary, or a declared seasonal window.
   Currently no-floor is primary. **This is the top open decision.**
2. **Temperature homogeneity:** resolve the composite-station/IDW noise (anchor-only exposure or a
   homogenized composite) before injury linkage or trusting single-county rankings. The grid
   sharpened this: county rankings move a lot across definitions too (Spearman median 0.754,
   range 0.300–0.996), so county-level ranking has two independent sources of instability.
3. **Metric choice needs an explicit exposure-pathway rationale.** The grid's main finding is
   that the metric is the biggest lever on *which* days are flagged (Tmax vs Tmin Jaccard
   0.245) while barely changing the count (1.13×) — so a count-based justification is not
   sufficient, and this decision should be made on physiological/occupational grounds.
4. **NWS office thresholds:** several are flagged `approximate` in `pipeline/nws_offices_TX.csv`
   (EWX, LUB, AMA, MAF, SJT, CRP, SHV, LCH) — correct against authoritative office criteria.
5. **Extend to other Gulf states** (LA/MS/AL/FL) — works out of the box via `config.STATES`;
   the grid runs there too (`run_grid.py --state LA`) once p01 has built that state's table.
6. **Deferred:** fixed 1981–2010 baseline; hourly heat-index validation (needs hourly/dewpoint data
   this project doesn't have).
7. **Presentation:** decks are neutral navy/red — restyle to the user's PowerPoint template if given.
   The grid's results are NOT yet in the decks (`reference/` docs still describe Def 01/02 only).
8. **Possible further definitions** — natural additions given the grid: a compound day-and-night
   definition (Tmax > pctl AND Tmin > pctl same day, the "no overnight relief" construct), an
   absolute-threshold definition (HI ≥ 100/103°F), and the missing mean-HI cells
   (85th/95th at ≥3 days) which would complete a balanced 3×3×2 factorial. Each is one line
   in `GRID_DEFINITIONS` (the compound one needs a small metric-combination hook).

---

## 7. One-paragraph primer (if you only paste one thing)

> Resuming the Texas heatwave classification pipeline (repo: github.com/eaadeniyi/gulf_heatwave,
> local `heatWaveUS/texas_heatwave_pilot/`). State-agnostic, config-driven pipeline in `pipeline/`.
> **Def 01/02** (county-relative 85th/95th percentile daily-MEAN heat index, ≥2 days, walk-forward
> baseline 1979→Y-1) are in `outputs/TX/def_p85_2d` and `def_p95_2d`. **A 14-definition grid
> (Def 03–16) × 4 threshold windows = 56 runs** is in `outputs/TX/grid/` — metric (Tmax / Tmin /
> mean HI) × percentile (85/90/95) × duration (≥2/≥3 d) × window (`w05`, `w15`, `month`,
> `month_pm7`), everything else held fixed; run list in `pipeline/definition_registry.csv`,
> results in `grid/_comparison/FINDINGS_DEFINITION_GRID.md`. **Grid headline: the metric changes
> WHICH days (Tmax vs Tmin Jaccard 0.245) but not HOW MANY (1.13×); percentile is the count lever
> (95th→85th = 3.08×); window matters least; and the cool-season loading is intrinsic to the
> year-round relative construct in ALL 14 definitions, so the floor/season decision can no longer
> be deferred.** All 254 TX counties, 2015–2025, IDW-gap-filled temperature. Reporting uses
> heatwave day/event/duration, county-level (pooled totals QA-only), no pooled-average durations.
> Python at "C:/Program Files/Python314/python.exe"; no gh CLI (push via credential manager).
> Four test files gate the code — run them all after touching p02 or heatwave_run_logic.py.
> Key open items: the floor/season decision, temperature-composite homogeneity before injury
> linkage, an exposure-pathway rationale for the metric, and approximate NWS office thresholds.
> See HANDOFF.md for full detail.
```
