# Figure report - 16 heatwave definitions, Texas, 2015-2025

For every figure: purpose, unit of analysis, input file, transformation, visual encoding, what the figure DOES support, what it does NOT support, a draft publication caption, and its known limitation.

Primary threshold window: `w15`. Data-completeness cut: 10% imputed (188 of 254 counties). Long-event review length: 21 days. All counts are cumulative over 2015-2025 unless stated; pooled cross-county totals are QA quantities only.

| # | figure | file |
|---|---|---|
| Figure 1 | Definition design matrix | `figures/core/fig01_definition_design_matrix.png` |
| Figure 2 | Matched-pair count change vs day-level agreement | `figures/core/fig02_count_change_vs_agreement.png` |
| Figure 3 | Day-level agreement matrix | `figures/core/fig03_jaccard_heatmap_primary_window.png` |
| Figure 4 | County-rank stability | `figures/core/fig04_county_rank_stability.png` |
| Figure 5 | Monthly classification rate | `figures/core/fig05_monthly_rate_heatmap.png` |
| Figure 6 | Percentile and duration ladder | `figures/core/fig06_percentile_duration_ladder.png` |
| Figure 7 | Threshold-window sensitivity | `figures/core/fig07_threshold_window_sensitivity.png` |
| Figure 8 | County report cards (254 counties) | `county_profiles/<fips>/fig08_report_card_<fips>.png` |
| Figure 9 | Individual event timelines | `event_audits/fig09_timeline_<fips>_<county>.png` |
| Figure 10 | Long-event audit | `event_audits/fig10_long_event_<run>_<event_id>.png` |
| Figure 11 | Data-quality influence | `figures/core/fig11_data_quality_influence.png` |
| Figure 12 | Definition-pair disagreement | `figures/core/fig12_pair_disagreement_<pair>.png` |

---

## Figure 1 - Definition design matrix

**File** `figures/core/fig01_definition_design_matrix.png`

**Purpose.** State the full design before any result is shown: what the 16 definitions are, which round each came from, which threshold windows exist for each, whether their inputs are comparable, and which cells were never run.

**Unit of analysis.** one definition (metric x percentile x minimum duration)

**Input file(s).** tables/table1_definition_registry.csv

**Transformation.** No statistics. The registry is rendered as a matrix; the two cells that complete the 3x3x2 factorial but were never run are appended as explicit NOT TESTED rows.

**Visual encoding.** Metric by colour + hatch + marker + text label. Untested rows in flat grey with the status spelled out. No quantitative colour scale.

**Result supported.** That 16 of the 18 factorial cells were run, that all four windows exist for every one of them, and that the fixed axes (input hash, boundaries, IDW, walk-forward baseline, strict '>', year-round season, no floor) are common to all 16.

**Result NOT supported.** Nothing about how any definition performs. It carries no counts, no agreement and no ranking, and it does not imply the design is balanced - it is not: the mean-HI metric has no >=3-day cell at the 85th or 95th percentile.

**Draft publication caption.**

> Design matrix of the 16 county-level heatwave definitions compared for Texas, 2015-2025. Each definition is a county-relative percentile of a daily heat metric sustained over a minimum number of consecutive days, on a walk-forward baseline (1979 to the year before the analysis year), evaluated year-round with a strict '>' and no absolute floor. Definitions 01-02 were published in an earlier round and were re-run on the current code path for this comparison; Definitions 03-16 are the current grid. The two mean-HI 3-day cells were never run and are shown as NOT TESTED rather than as zero.

**Known limitation.** A design matrix cannot show that the fixed axes were actually honoured in the output; that is what qa/s03_validation.md tests (121 checks passed, 0 failed).

---

## Figure 2 - Matched-pair count change vs day-level agreement

**File** `figures/core/fig02_count_change_vs_agreement.png`

**Purpose.** Separate the two things a definition choice can do: change HOW MANY heatwave days are counted, and change WHICH county-dates are classified. They are not the same, and a count table cannot tell them apart.

**Unit of analysis.** one matched pair of runs (identical on the other three axes); the underlying quantities are pooled heatwave days (QA) and the SET of (county, date) heatwave days

**Input file(s).** tables/table7_matched_pair_marginal_effects.csv, tables/table7b_marginal_effects_summary.csv

**Transformation.** Only pairs differing on exactly ONE axis are used (240 of 2016 pairs). For each, the percentage difference in pooled heatwave days and the Jaccard index of the two day sets. Faceted by axis; the median of each axis is drawn and the matched-pair count printed.

**Visual encoding.** One panel per axis (shared scales), point colour+shape = the metric held fixed, brown reference lines = this project's earlier sensitivity yardsticks.

**Result supported.** That the axes rank differently on the two questions. Day-level effect, largest first: metric 0.333 < percentile 0.492 < window 0.687 < duration 0.747 (Jaccard medians; lower = larger effect). Count effect: percentile moves counts most (median 2.03x, up to 3.54x), metric barely at all (median 1.12x) while disagreeing on most days (Jaccard 0.333).

**Result NOT supported.** Which axis matters for health, and which definition is right. Jaccard is agreement between two definitions, NOT accuracy: neither is a gold standard and this data contains no observed heatwave day. Nor does it support any statement about a single county - these are statewide matched-pair aggregates.

**Draft publication caption.**

> Effect of changing one definition axis at a time, Texas, 2015-2025. Each point is a matched pair of runs identical on the other three axes (n = 240 pairs). The x axis is the percentage difference in pooled heatwave county-days (a QA quantity); the y axis is the Jaccard index on the sets of classified (county, date) heatwave days. Changing the METRIC leaves the count nearly unchanged (median 1.12x) while changing which days are classified more than any other axis (median Jaccard 0.333); changing the PERCENTILE is the count lever (median 2.03x). Brown lines mark agreement values from this project's earlier sensitivity work for scale.

**Known limitation.** Matched-pair counts differ by axis (metric 56, percentile 60, duration 28, window 96). The duration axis has fewest pairs because the two mean-HI 3-day cells were never run, so its median rests on a smaller and differently-composed sample than the others.

---

## Figure 3 - Day-level agreement matrix

**File** `figures/core/fig03_jaccard_heatmap_primary_window.png`

**Purpose.** Show, for every pair of definitions at one common window, how much of the classified exposure they actually share.

**Unit of analysis.** the SET of (county, date) heatwave days

**Input file(s).** tables/support_jaccard_matrix_primary.csv (from the canonical long table)

**Transformation.** Jaccard = shared county-dates / union of county-dates, all 16 definitions at the w15 window, ordered by metric then percentile then duration, fixed 0-1 scale.

**Visual encoding.** One-hue sequential ramp, fixed 0-1; black lines separate metric families; tick labels carry the metric colour; every cell annotated.

**Result supported.** That definitions which look interchangeable in a count table often are not: off-diagonal agreement runs from 0.131 to 0.788 (median 0.323), with the lowest at TMAX_P95_3D vs TMIN_P85_2D. Blocks along the diagonal show that agreement is highest within a metric family.

**Result NOT supported.** Accuracy, or a ranking of definitions. It also does not describe any individual county - a statewide Jaccard can hide large county-level variation (see the per-county matrices in Figure 8).

**Draft publication caption.**

> Day-level agreement between 16 heatwave definitions, Texas, 2015-2025, w15 threshold window. Each cell is the Jaccard index between two definitions on the set of classified (county, date) heatwave days: 1.0 = identical sets, 0 = disjoint. Off-diagonal agreement ranges 0.13-0.79 (median 0.32). Agreement is highest within a metric family (blocks on the diagonal) and lowest between day-time and night-time temperature definitions. Jaccard measures agreement between definitions, not the accuracy of either.

**Known limitation.** One window only, so it says nothing about window sensitivity (Figure 7), and it is computed on pooled county-dates, so a county with many heatwave days contributes more than a county with few.

---

## Figure 4 - County-rank stability

**File** `figures/core/fig04_county_rank_stability.png`

**Purpose.** Ask whether the ORDER of counties survives a change of definition, and whether the answer depends on including counties with heavily imputed temperature.

**Unit of analysis.** county (cumulative 2015-2025 heatwave days per county, not annual)

**Input file(s).** tables/support_county_rank_spearman_all.csv, tables/support_county_rank_spearman_complete.csv

**Transformation.** Per-county heatwave-day totals per definition at the w15 window; Spearman correlation between every pair of definitions. Panel A all 254 counties; panel B the 188 counties at or below the prespecified 10% imputation cut.

**Visual encoding.** Same matrix layout, ordering and fixed 0-1 scale as Figure 3, so the two figures can be read against each other directly.

**Result supported.** That county ORDER is far more stable than day-level agreement: median rho 0.744 (range 0.380-0.991) across all counties, with 28% of pairs above 0.90, against a median Jaccard of 0.323 for the same pairs. Restricting to complete-data counties changes it very little (median 0.735), so the county ordering is not an artefact of the heavily imputed counties. The one place ordering DOES break down is the metric axis: rank agreement is 0.96 within a metric family but only 0.38-0.56 between the Tmax and Tmin families.

**Result NOT supported.** That the definitions agree on exposure. High rank correlation with low Jaccard means the definitions disagree about WHICH DAYS while ordering counties similarly - so a high rho here must NOT be read as day-level agreement, and neither quantity is accuracy. It also does not license trusting any individual county's rank.

**Draft publication caption.**

> Stability of county rankings across 16 heatwave definitions, Texas, 2015-2025, w15 window. Each cell is the Spearman correlation between two definitions' per-county heatwave-day totals over 2015-2025. Panel A: all 254 counties. Panel B: the 188 counties with at most 10% IDW-imputed temperature. County order is considerably more stable (median rho 0.74) than the underlying day-level agreement (median Jaccard 0.32, Figure 3): the definitions largely agree on which counties are more exposed while disagreeing on most of the specific days.

**Known limitation.** Rank correlation is insensitive to the SIZE of differences and to which counties move; a definition pair can score high while reordering the top of the distribution. It also inherits the temperature-source instability documented in earlier rounds (anchor vs composite station agreement 0.45-0.73), which is independent of the definition axis.

---

## Figure 5 - Monthly classification rate

**File** `figures/core/fig05_monthly_rate_heatmap.png (+ figures/supplement/fig05s_monthly_share_heatmap.png)`

**Purpose.** Characterise seasonality as a RATE per eligible day, so that month length and unequal data coverage cannot masquerade as seasonality.

**Unit of analysis.** county-month, pooled over counties and years

**Input file(s).** tables/support_monthly_rate_by_definition.csv (numerator: master_county_month_summary.csv; denominator: eligibility_county_month.csv)

**Transformation.** 1,000 x heatwave days / ELIGIBLE county-days per definition x month, where an eligible day is one the definition could be evaluated on (metric present, threshold present, not a confirmed RH-clip artifact). The month SHARE version is rendered separately as a supplement and labelled the weaker metric.

**Visual encoding.** One-hue sequential ramp with the untested cells in flat grey; Jun-Sep boxed in brown; every cell annotated.

**Result supported.** That the cool-season loading of these year-round relative definitions is intrinsic and not a property of one metric: across all 16 definitions 51-64% of heatwave days fall outside Jun-Sep, and the Jun-Sep rate exceeds the Oct-May rate by only 1.13-1.90x. Peak month by rate across the definitions: Aug, Dec, Oct.

**Result NOT supported.** That cool-season heatwave days are hazardous. These are days unusual FOR THEIR OWN DATE with no absolute floor and no seasonal restriction; a December day above its December threshold is a persistent apparent-heat anomaly, not physically hazardous heat. The figure also cannot say whether a floor or a seasonal window is the better remedy.

**Draft publication caption.**

> Seasonality of heatwave classification as a rate, Texas, 2015-2025, w15 window. Cells are heatwave days per 1,000 eligible county-days, by definition and calendar month; the denominator counts only days on which the definition could be evaluated, so months of different length and coverage are comparable. Every definition places 51-64% of its heatwave days outside June-September. Because these definitions are county-relative, year-round and carry no absolute floor, cool-season days qualify as 'unusual for the date' and must not be interpreted as hazardous heat.

**Known limitation.** Pooling over counties and years hides both the north-south gradient and year-to-year variation; the county-month panels in Figure 8 carry the county-level version. The eligible-day denominator treats an IDW-imputed day as eligible, which is a coverage choice, not a data-quality claim.

---

## Figure 6 - Percentile and duration ladder

**File** `figures/core/fig06_percentile_duration_ladder.png`

**Purpose.** Show how the percentile and the persistence rule move exposure at the level the project reports - individual county-years - rather than as pooled totals.

**Unit of analysis.** county-year (254 counties x 11 years = 2,794 records per definition)

**Input file(s).** master_county_year_summary.csv, eligibility_county_month.csv

**Transformation.** Heatwave days per 1,000 eligible county-days per county-year, plotted against percentile, faceted by metric, split by minimum duration. Faint line per county-year; heavy line the MEDIAN county-year. No line is drawn across an untested cell.

**Visual encoding.** Metric = facet + colour + marker; percentile = x position; duration = line style and marker fill (filled >=2 days, open >=3 days).

**Result supported.** The monotone effect of the percentile within every metric, the spread across county-years at a fixed definition (visible as the width of the faint bundle), and the size of the duration step where both durations exist (median count ratio 1.34x, day-level Jaccard 0.747).

**Result NOT supported.** Any mean-HI >=3-day statement at the 85th or 95th percentile: those cells were never run, so the mean-HI facet has a single >=3-day point at the 90th and no line. No pooled average across county-years is drawn or implied.

**Draft publication caption.**

> Effect of percentile and minimum duration on county-year heatwave exposure, Texas, 2015-2025, w15 window. Each faint line is one county-year (2,794 per definition); heavy lines are the median county-year. Rates use eligible county-days as denominator. Lines are not connected across the two mean-HI >=3-day cells, which were never run.

**Known limitation.** Overplotting: 2,794 faint lines per facet convey the envelope, not individual counties, and heavily imputed counties are not visually distinguished here (they are in Figure 11).

---

## Figure 7 - Threshold-window sensitivity

**File** `figures/core/fig07_threshold_window_sensitivity.png`

**Purpose.** Quantify how much the choice of baseline-pooling window changes the result, and show the threshold curves that produce the difference.

**Unit of analysis.** panel A the SET of (county, date) heatwave days; panel B county-year counts paired county by county and year by year; panel C the county's own threshold in degF by day of year

**Input file(s).** tables/support_window_sensitivity.csv, tables/support_example_counties.csv, outputs/TX/grid/_thresholds/

**Transformation.** Every definition compared with its own w15 run: Jaccard, and the distribution of (this window - primary window) heatwave days across 2,794 paired county-years. Panel C plots the cached walk-forward thresholds for MHI_P90_2D in analysis year 2025.

**Visual encoding.** Window = neutral grey ramp and bar position (never a metric colour); metric identity retained in the coloured tick labels; panels A and B share the definition ordering and x axis.

**Result supported.** That the window is the least consequential of the four axes: median Jaccard against the primary window 0.699 (lowest 0.588). Compared with each other rather than with the primary window, month and month_pm7 are near-duplicates (median Jaccard 0.886) while w05 vs w15 differ more (0.851). Paired county-year differences are small and centred near zero for the calendar-month windows.

**Result NOT supported.** That the window can be ignored in general - w05 differs more than the others - or that any window is more nearly correct. Panel C shows the mechanism, not a validation.

**Draft publication caption.**

> Threshold-window sensitivity of 16 heatwave definitions, Texas, 2015-2025. (A) day-level Jaccard between each definition's w15 run and its runs at the other three windows. (B) paired differences in county-year heatwave days relative to the w15 run (dot = median, bar = interquartile range over 2,794 paired county-years). (C) the underlying walk-forward threshold curves for MHI_P90_2D in 2025, for example counties chosen by a documented climate-region and data-completeness rule. Centered windows give a threshold per day of year; calendar-month windows give one step per month.

**Known limitation.** Panel C shows 4 of the 10 example counties and one definition in one year, chosen mechanically; it is an illustration of the pooling mechanism rather than a sensitivity estimate.

---

## Figure 8 - County report cards (254 counties)

**File** `county_profiles/<fips>/fig08_report_card_<fips>.png (+ INDEX.csv)`

**Purpose.** Give every county its own complete, auditable record: how each definition behaves there year by year, month by month, and how much the definitions agree there - with the county's data provenance stated in the header.

**Unit of analysis.** one county; panels are county-year, county-year, county-month and county-date

**Input file(s).** master_county_year_summary.csv, master_county_month_summary.csv, eligibility_county_month.csv, tables/canonical_long/*.csv.gz, outputs/TX/coverage_and_imputation_report.csv

**Transformation.** Per county: definition x year heatwave days; definition x year events STARTED (an event counted once, in its onset year); definition x month rate per 1,000 eligible county-days; and a 18 x 18 day-level Jaccard matrix computed on that county's days alone.

**Visual encoding.** Same sequential ramp, same definition ordering and the same flat-grey NOT TESTED rows as the statewide figures, so a county card can be read against Figures 3-5 without re-learning the layout.

**Result supported.** County-specific description: which definitions flag most days there, in which years and months, and whether the definitions agree with each other in that county. The header supports judging how much of the county's record is native observation (22 of 254 counties are 100% IDW-imputed and 66 are flagged above the 10% cut).

**Result NOT supported.** Any claim that one definition is correct for that county, and any county-to-county comparison drawn from single cards - the earlier anchor-vs-composite temperature work (agreement 0.45-0.73) means single-county texture is not reliable. Cards for the 66 flagged counties describe the IDW field, not an independent observation.

**Draft publication caption.**

> County report card, <county> County, Texas, 2015-2025. Panel A heatwave days and panel B heatwave events started, by definition and year; panel C heatwave days per 1,000 eligible county-days by definition and month (June-September boxed); panel D day-level Jaccard between definitions computed on this county's days alone. Header states analysis days, native versus IDW-imputed days and the county's climate division. Grey rows are the two mean-HI 3-day cells, never run.

**Known limitation.** A county with few heatwave days yields small and unstable Jaccard values in panel D, and the cards are cumulative over 2015-2025 - no annual rate is shown. Cards are produced for all 254 counties including fully imputed ones; the header flag, not the absence of a card, is what marks those.

---

## Figure 9 - Individual event timelines

**File** `event_audits/fig09_timeline_<fips>_<county>.png`

**Purpose.** Make the classification mechanics inspectable day by day: where the metric sits relative to the county's own threshold, which runs qualify, and which candidate days fail the persistence rule.

**Unit of analysis.** county-date within one calendar window

**Input file(s).** outputs/TX/county_daily_heat.csv + the cached thresholds, rebuilt through the same classification code as the canonical table

**Transformation.** For each example county one calendar window - the first event of 2020 under MHI_P90_2D, padded by 10 days and widened to at least 45 days - is shown for all 5 shortlisted definitions, stacked.

**Visual encoding.** Metric = colour + marker; threshold = grey line whose style encodes the percentile; qualifying runs shaded and labelled with exact start, end and INTEGER duration; imputed days as open markers; isolated candidate days ringed in brown.

**Result supported.** That the same days are treated differently by different definitions in the same county, that events end because a single day drops below threshold, and that integer durations and exact dates are preserved. It shows directly why a metric change can move classification without moving the count.

**Result NOT supported.** Anything general. These are 10 counties chosen by a documented climate-region and completeness rule and one anchored window each; they are illustrations, not evidence about the state, and the windows were not selected for magnitude.

**Draft publication caption.**

> Event timelines for <county> County, Texas. The same 45-day window judged by five heatwave definitions: daily metric against the county's own walk-forward percentile threshold, with qualifying runs shaded and labelled by exact start date, end date and integer duration. Open markers are IDW-imputed temperature; brown rings are candidate days that failed the minimum-duration rule and so ended a run. The window is anchored mechanically on the first 2020 event under MHI_P90_2D.

**Known limitation.** One window per county, and events may extend beyond it (labelled where they do). The example counties are the most data-complete in each climate division by construction, so they under-represent the imputation problem seen elsewhere.

---

## Figure 10 - Long-event audit

**File** `event_audits/fig10_long_event_<run>_<event_id>.png (+ fig10_long_event_audit_with_station_counts.csv, fig10_not_individually_plotted.csv)`

**Purpose.** Subject every implausibly long 'event' to inspection - with its data provenance attached - without deleting any of them.

**Unit of analysis.** county-date within one heatwave event; one figure per event

**Input file(s).** tables/table8a_long_event_audit.csv, the rebuilt daily panels, and the RAW GHCN county-day file for contributing station counts

**Transformation.** Every event at or above the prespecified 21-day review length. 3133 such events exist across all 64 runs (734 at the w15 window, longest 69 days, spanning 16 definitions); the longest 150 at the primary window are drawn individually and any remainder is listed in fig10_not_individually_plotted.csv.

**Visual encoding.** Three stacked panels sharing one time axis - metric vs threshold, daily exceedance, and data provenance (imputation flag plus Tmax/Tmin contributing station counts) - with month boundaries marked on all three. No dual y-scale anywhere.

**Result supported.** Judging whether a long run is a sustained anomaly or an artefact: 622 of the 3133 long events have at least half their days IDW-imputed. It also shows that long runs in a relative year-round definition can consist of days only marginally above threshold.

**Result NOT supported.** Deleting or truncating any event. Nothing here establishes that a long event is wrong - only that it should not be reported as sustained hazardous heat without a floor or a seasonal rule.

**Draft publication caption.**

> Long-event audit: <run>, <county> County, Texas. An event of <n> consecutive days flagged for review because it is at or above the prespecified 21-day review length. Panels show the daily metric against the county's own walk-forward threshold, the daily exceedance, and the data provenance of every day (IDW-imputation flag and the number of contributing GHCN stations for Tmax and Tmin), with calendar-month boundaries marked. All long events are retained in every table and count; this audit makes them inspectable.

**Known limitation.** Station counts come from the raw GHCN input because the classification table does not retain them; they describe the county-day temperature aggregation, not the humidity field, so a mean-HI event's humidity provenance is not shown. Only the primary window is drawn; long events at the other three windows are tabulated, not plotted.

---

## Figure 11 - Data-quality influence

**File** `figures/core/fig11_data_quality_influence.png`

**Purpose.** Test whether the county picture is being driven by how much of a county's temperature record was gap-filled rather than by climate.

**Unit of analysis.** county (cumulative 2015-2025 heatwave days, and the county's rank within a definition)

**Input file(s).** master_county_year_summary.csv, table8b_county_data_quality.csv

**Transformation.** Per-county heatwave-day totals and ranks for the 5 shortlisted definitions at the w15 window, plotted against the county's temperature-imputation percentage, with Spearman correlations annotated and fully imputed counties marked separately.

**Visual encoding.** Metric colour + marker per definition (facets); the 10% cut as a dotted brown line; the 22 fully imputed counties as brown crosses.

**Result supported.** Whether imputation and exposure are associated, and identifies exactly which counties would carry any such association (66 flagged above the cut, 22 of them fully imputed).

**Result NOT supported.** Causation in either direction, and any inference that a low correlation means imputation is harmless: IDW fills a county from its neighbours, so it can bias a county toward the regional mean without changing its total much. The earlier anchor-vs-composite finding (0.45-0.73) is the relevant magnitude, and this figure does not reproduce that test.

**Draft publication caption.**

> Influence of temperature imputation on county-level results, Texas, 2015-2025, w15 window, five shortlisted definitions. Top row: cumulative heatwave days per county against the percentage of that county's analysis days whose temperature was IDW gap-filled. Bottom row: the county's rank within the same definition. Dotted line marks the prespecified 10% completeness cut (188 of 254 counties qualify); crosses mark the 22 counties with no native station record. Spearman correlations are annotated.

**Known limitation.** Imputation percentage is a crude proxy for temperature-field quality: it counts imputed DAYS and says nothing about how far the imputed value sits from the truth, nor about the humidity field that the mean-HI definitions also depend on.

---

## Figure 12 - Definition-pair disagreement

**File** `figures/core/fig12_pair_disagreement_<pair>.png (6 pairs) (+ tables/support_pair_days_<pair>_a_only.csv.gz / _b_only.csv.gz)`

**Purpose.** Localise disagreement for prespecified single-axis contrasts: WHERE and WHEN two definitions part company, with the disagreeing county-dates listed explicitly.

**Unit of analysis.** (county, date) heatwave day; mapped per county and summarised per calendar month

**Input file(s).** tables/support_pair_disagreement_<pair>.csv, tables/support_pair_disagreement_by_month_<pair>.csv, the county boundary shapefile

**Transformation.** Outer join of the two definitions' heatwave county-date sets, classified A-only / B-only / shared; per-county disagreement rate mapped; monthly counts plotted; both one-sided county-date lists written to CSV.

**Visual encoding.** Choropleth on the one-hue sequential ramp with a fixed 0-100% scale; counties above the imputation cut outlined in brown; monthly panel uses two contrasting bar colours for the two one-sided sets and a dark line for the shared set.

**Result supported.** That disagreement is spatially and seasonally structured rather than random, and - via the exported lists - exactly which county-dates each definition claims alone. Pair Jaccards: metric 0.250; metric 0.383; percentile 0.351; duration 0.745; percentile 0.309; window 0.641.

**Result NOT supported.** Which member of a pair is right, and any generalisation to pairs not shown. The pairs were fixed in advance to isolate one axis each; they are not the most or least agreeing pairs.

**Draft publication caption.**

> Disagreement between <A> and <B>, Texas, 2015-2025, isolating the <axis> axis. (A) percentage of each county's classified county-dates that only one of the two definitions flags; counties above the 10% imputation cut are outlined. (B) the same disagreement by calendar month, with days claimed by only one definition shown separately from days both definitions classify. The complete A-only and B-only county-date lists accompany the figure as CSVs.

**Known limitation.** A per-county RATE hides absolute volume: a county with 20 classified days and a 50% disagreement rate looks identical to one with 600 days at 50%. The map inherits the county-boundary and IDW caveats and, for the window contrast, both panels come from the same underlying metric so the disagreement is purely a baseline-pooling effect.

---

