"""
=============================================================================
r12  --  data dictionary, definition registry, manifests and the final report.
=============================================================================
Writes:
  data_dictionary/revised_variable_dictionary.csv
  data_dictionary/definition_registry_revised.csv
  tables/figure_data_manifest.csv
  run_manifest.csv
  reports/FINAL_REPORT.md
  reports/FINDINGS_REVISED.md
  current_vs_revised/CURRENT_VS_REVISED.md
  README.md
=============================================================================
"""
import os
import sys
import json
import time
import hashlib
import subprocess

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K
import config as C                                          # noqa: E402

T, Q, D = K.DIR_TABLES, K.DIR_QA, K.DIR_DICT


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


# =============================================================================
# 1. variable dictionary
# =============================================================================
COLUMN_DOC = {
    # identity
    "state": ("state abbreviation", "", "State"),
    "state_name": ("state name", "", "State"),
    "county_fips": ("five-digit county FIPS code", "", "County"),
    "county_name": ("county name", "", "County"),
    "year": ("calendar year", "year", "Year"),
    "month": ("calendar month, 1 to 12", "month", "Month"),
    "month_name": ("three-letter month abbreviation", "", "Month"),
    "season": ("warm (June-September), shoulder (May and October) or cool "
               "(November-April)", "", "Season"),
    "season_label": ("reader-facing season name", "", "Season"),
    "period": ("comparison period", "", "Period"),
    "period_note": ("note on a period that is not ten years long", "", "Period note"),
    "variable": ("Tmax, Tmin or Tavg", "", "Temperature variable"),
    "variable_label": ("reader-facing variable name", "", "Temperature variable"),
    "sample": ("consistent_county (Sample A) or strict_balanced (Sample B)", "",
               "County sample"),
    # temperature
    "period_mean_f": ("mean of the daily values over the summary period",
                      "degF", "Average temperature"),
    "period_median_f": ("median of the daily values over the summary period",
                        "degF", "Median daily temperature"),
    "daily_min_f": ("lowest single daily value in the period", "degF",
                    "Lowest daily value"),
    "daily_max_f": ("highest single daily value in the period", "degF",
                    "Highest daily value"),
    "daily_p95_f": ("95th percentile of the daily values in the period", "degF",
                    "95th-percentile daily value"),
    "valid_daily_observation_count": ("number of valid daily county-level "
                                      "observations behind this summary", "records",
                                      "Valid daily county-level observations"),
    "meets_annual_coverage_requirement": ("at least %d valid daily county-level "
                                          "observations in the year"
                                          % K.MIN_DAYS_PER_COUNTY_YEAR, "", "Meets coverage"),
    "meets_monthly_coverage_requirement": ("at least %d valid daily county-level "
                                           "observations in the month"
                                           % K.MIN_DAYS_PER_COUNTY_MONTH, "",
                                           "Meets coverage"),
    "mean_contributing_stations": ("mean number of reporting stations behind the "
                                   "county's daily values", "stations",
                                   "Contributing stations"),
    "county_period_value_f": ("one value per county per period: the %s of that "
                              "county's qualifying annual values in the period"
                              % K.COUNTY_PERIOD_STAT, "degF", "County period value"),
    "annual_observations_used": ("annual county-level observations behind the "
                                 "county's period value", "records",
                                 "Annual observations used"),
    "median_across_counties_f": ("median across counties, each contributing exactly "
                                 "one value", "degF", "Median across counties"),
    "p25_across_counties_f": ("25th percentile across counties", "degF",
                              "25th percentile across counties"),
    "p75_across_counties_f": ("75th percentile across counties", "degF",
                              "75th percentile across counties"),
    "iqr_across_counties_f": ("interquartile range across counties", "degF",
                              "Interquartile range across counties"),
    "contributing_counties": ("number of counties behind the summary", "counties",
                              "Contributing counties"),
    "median_ci_low_f": ("lower bound of the %.1f-%.1f percentile bootstrap interval "
                        "on the median, resampling counties" % K.BOOTSTRAP_CI,
                        "degF", "Interval, lower"),
    "median_ci_high_f": ("upper bound of the bootstrap interval on the median",
                         "degF", "Interval, upper"),
    "difference_of_medians_vs_base_f": ("this period's median across counties minus "
                                        "the %s median across counties" % K.BASE_PERIOD,
                                        "degF", "Difference from the base period"),
    "median_paired_county_difference_f": ("median across counties of each county's "
                                          "own period difference", "degF",
                                          "Median county difference"),
    "sen_slope_f_per_decade": ("Theil-Sen slope of the annual median across counties",
                               "degF per decade", "Descriptive slope"),
    "ols_slope_f_per_decade": ("ordinary least-squares slope, sensitivity case",
                               "degF per decade", "Least-squares slope"),
    # constructs
    "construct_id": ("revised construct identifier; TX denotes the daily maximum "
                     "temperature, NOT the state", "", "Construct"),
    "construct_family": ("relative, hybrid or absolute", "", "Construct family"),
    "legacy_definition_id": ("the identifier the current package files this "
                             "construct under", "", "Legacy identifier"),
    "short_label": ("figure label carrying metric, percentile and duration", "",
                    "Construct"),
    "reader_name": ("the construct written out in plain language", "", "Definition"),
    "percentile": ("percentile of the county- and calendar-date-specific historical "
                   "daily-high distribution", "percentile", "Percentile"),
    "duration_days": ("minimum number of consecutive qualifying days", "days",
                      "Minimum duration"),
    "duration_days_minimum": ("minimum number of consecutive qualifying days", "days",
                              "Minimum duration"),
    "absolute_gate_f": ("absolute daily-high gate; NOT a National Weather Service "
                        "advisory threshold", "degF", "Absolute gate"),
    "threshold_window": ("how baseline days are pooled to estimate the threshold",
                         "", "Threshold window"),
    # events
    "event_id": ("unique event identifier", "", "Event"),
    "event_start_date": ("first date of the event", "date", "Start date"),
    "event_end_date": ("last date of the event", "date", "End date"),
    "event_duration_days": ("number of consecutive calendar dates in the event; "
                            "always an integer", "days", "Duration"),
    "event_peak_temperature_f": ("highest daily high inside the event", "degF",
                                 "Peak daily high"),
    "event_peak_date": ("date of the highest daily high", "date", "Peak date"),
    "maximum_threshold_exceedance_f": ("largest single-day amount by which the daily "
                                       "high exceeded its threshold", "degF",
                                       "Maximum exceedance"),
    "maximum_exceedance_date": ("date of the largest exceedance", "date",
                                "Maximum exceedance date"),
    "cumulative_exceedance_degree_days": ("sum over the event of the positive daily "
                                          "exceedance above the threshold",
                                          "degF-days", "Cumulative exceedance"),
    "observed_day_count": ("days in the event whose temperature was observed",
                           "days", "Observed days"),
    "imputed_day_count": ("days in the event whose temperature was gap-filled",
                          "days", "Gap-filled days"),
    "qc_review_status": ("ok, or a semicolon-separated list of review flags", "",
                         "Review status"),
    "requires_manual_review": ("the review status is not ok", "", "Needs review"),
    "audit_classification": ("physically_plausible, threshold_driven, "
                             "imputation_sensitive, station_composition_sensitive or "
                             "requires_manual_review", "", "Audit classification"),
    # summaries
    "heat_event_day_count": ("county-dates classified by this construct in the month",
                             "records", "Classified days"),
    "annual_classified_day_count": ("county-dates classified by this construct in the "
                                    "year", "records", "Classified days"),
    "annual_event_count": ("events beginning in the year", "events", "Events"),
    "events_started_count": ("events beginning in the month", "events",
                             "Events started"),
    "events_active_count": ("distinct events touching the month", "events",
                            "Events active"),
    "longest_active_event_days": ("longest event touching the month", "days",
                                  "Longest active event"),
    "longest_event_duration_days": ("longest event in the year", "days",
                                    "Longest event"),
    "first_event_start_date": ("start date of the first event of the year", "date",
                               "First event"),
    "last_event_end_date": ("end date of the last event of the year", "date",
                            "Last event"),
    "imputed_classified_day_count": ("classified days whose temperature was "
                                     "gap-filled", "records", "Gap-filled"),
    "monthly_classification_rate_per_1000": (K.UNIT_LANGUAGE["rate"],
                                             "per 1,000", "Classification rate"),
    "annual_classification_rate_per_1000": (K.UNIT_LANGUAGE["rate"], "per 1,000",
                                            "Classification rate"),
    "classified_days_per_1000_valid": (K.UNIT_LANGUAGE["rate"], "per 1,000",
                                       "Classification rate"),
    "event_ids_started": ("semicolon-separated event identifiers beginning in the "
                          "month", "", "Events started"),
    "event_ids_active": ("semicolon-separated event identifiers touching the month",
                         "", "Events active"),
    "HWN_annual_event_count": ("published-index crosswalk: annual number of distinct "
                               "events", "events", "HWN"),
    "HWF_annual_days_in_events": ("published-index crosswalk: annual number of days "
                                  "participating in events", "days", "HWF"),
    "HWD_longest_event_duration_days": ("published-index crosswalk: longest event "
                                        "duration. NOT the median event duration",
                                        "days", "HWD"),
    # agreement and quality
    "jaccard": ("agreement between two constructs on the set of classified "
                "county-dates; not accuracy", "0 to 1", "Jaccard overlap"),
    "structurally_nested": ("the two constructs are nested, so their agreement is "
                            "arithmetic rather than evidential", "", "Nested"),
    "pct_analysis_days_imputed": ("share of the county's daily records that were "
                                  "gap-filled by inverse-distance weighting",
                                  "percent", "Gap-filled"),
    "fully_imputed_county": ("the county has no observed temperature at all in the "
                             "study period", "", "Fully gap-filled"),
    "data_quality_label": ("reader-facing data-quality band for the county", "",
                           "Data quality"),
    "pct_classified_days_retained": ("share of the ungated construct's classified "
                                     "days that survive the gate", "percent",
                                     "Days retained"),
    "pct_retained": ("share of a county's classified days that survive the gate",
                     "percent", "Days retained"),
}

TABLE_DOC = {
    "county_annual_temperature.csv": "annual county-level temperature observations, five states",
    "county_monthly_temperature.csv": "monthly county-level temperature summaries, five states",
    "county_period_temperature.csv": "one temperature value per county per period, per sample",
    "state_period_temperature_equal_county.csv": "equal-county state period summaries with bootstrap intervals",
    "state_month_period_temperature_equal_county.csv": "equal-county state summaries by calendar month and period",
    "state_period_temperature_current_vs_revised.csv": "current pooled result beside the revised equal-county result",
    "period_comparison_current_vs_revised.csv": "current pooled result beside the revised equal-county result",
    "sample_membership_counties.csv": "which counties belong to Sample A and Sample B",
    "revised_temperature_monthly_sanity_check.csv": "monthly distribution across counties, with coverage counts",
    "summer_audit_jun_aug_jun_sep.csv": "June-August and June-September audit",
    "state_annual_series.csv": "annual median across counties, four county samples",
    "trend_sensitivity.csv": "Theil-Sen and least-squares slopes with intervals",
    "benchmark_comparison_summary.csv": "status of each required external comparison",
    "county_annual_relative_warm_spells.csv": "annual county-level relative warm-spell summary",
    "county_monthly_relative_warm_spells.csv": "monthly county-level relative warm-spell summary",
    "individual_relative_warm_spell_events.csv": "one row per relative warm spell",
    "county_annual_hybrid_heat_events.csv": "annual county-level hybrid heat-event summary",
    "county_monthly_hybrid_heat_events.csv": "monthly county-level hybrid heat-event summary",
    "individual_hybrid_heat_events.csv": "one row per hybrid relative-and-absolute heat event",
    "county_annual_absolute_hot_spells.csv": "annual county-level absolute hot-spell summary",
    "county_monthly_absolute_hot_spells.csv": "monthly county-level absolute hot-spell summary",
    "individual_absolute_hot_spells.csv": "one row per absolute hot spell",
    "county_annual_all_constructs.csv": "annual county-level summary for all 60 constructs",
    "county_monthly_all_constructs.csv": "monthly county-level summary for the primary-window and absolute constructs",
    "construct_summary.csv": "one row per construct, county-level quantities first",
    "monthly_classification_rates.csv": "monthly classification rate per construct, family-specific denominators",
    "seasonal_classification_shares.csv": "three-category seasonal split per construct",
    "definition_agreement_jaccard.csv": "pairwise agreement on classified county-dates",
    "definition_agreement_jaccard_matrix.csv": "the same, in square form",
    "absolute_gate_effect.csv": "what each absolute gate does to each relative definition",
    "absolute_vs_relative.csv": "absolute constructs against matched relative constructs",
    "county_gate_effect.csv": "per-county geography of the absolute gate",
    "county_data_quality.csv": "per-county gap-filling and subset membership",
    "county_profile_examples.csv": "the six example counties",
    "long_event_audit.csv": "every event longer than the audit threshold, classified",
    "imputation_sensitivity.csv": "state summaries under six county subsets",
    "imputation_sensitivity_rankings.csv": "ranking invariance and what the subsets change",
    "annual_event_count_distribution.csv": "distribution of annual county-level event counts",
    "event_duration_distribution.csv": "distribution of individual event durations",
    "eligibility_denominator_comparison.csv": "valid-record counts per construct family, tested for equality",
    "county_record_coverage.csv": "record extent and coverage per state",
    "figure_data_manifest.csv": "every figure with its input table, aggregation and limitations",
}


# Suffix and prefix rules cover the families of columns that repeat across
# tables, so the dictionary documents every column rather than a subset.
PATTERN_DOC = [
    ("_QA", "pooled statewide total; a QA quantity, never a substantive result",
     "records", "Pooled total (QA)"),
    ("_ci_low_f", "lower bound of the %.1f-%.1f percentile bootstrap interval, "
     "resampling counties" % K.BOOTSTRAP_CI, "degF", "Interval, lower"),
    ("_ci_high_f", "upper bound of the bootstrap interval, resampling counties",
     "degF", "Interval, upper"),
    ("_per_1000_valid", K.UNIT_LANGUAGE["rate"], "per 1,000", "Classification rate"),
    ("_per_1000", K.UNIT_LANGUAGE["rate"], "per 1,000", "Classification rate"),
    ("pct_days_june_september", "share of classified days falling in June-September",
     "percent", "June-September share"),
    ("pct_days_may_and_october", "share of classified days falling in May or October",
     "percent", "May and October share"),
    ("pct_days_november_april", "share of classified days falling in November-April",
     "percent", "November-April share"),
    ("median_annual_classified_days", "median across annual county-level observations "
     "of the classified-day count", "records", "Median annual classified days"),
    ("median_annual_event_count", "median across annual county-level observations of "
     "the event count", "events", "Median annual events"),
    ("median_event_duration_days", "median across events of the integer duration; a "
     "median may fall between two integers, no event lasts a fraction of a day",
     "days", "Median event duration"),
    ("current_published_", "the value the current package published, unchanged", "",
     "Current package"),
    ("current_rule_", "the current package's RULE re-applied to the revised panel, so "
     "the weighting defect can be separated from the panel change", "",
     "Current rule, revised panel"),
    ("revised_", "the revised equal-county result", "", "Revised"),
    ("_construct", "construct identifier", "", "Construct"),
    ("stratum", "county subset used for the data-quality sensitivity", "",
     "County subset"),
    ("contributing_", "count of units behind the summary", "units", "Contributing"),
    ("valid_daily_observations", "valid daily county-level observations used as the "
     "denominator", "records", "Valid daily county-level observations"),
    ("classified_days", "county-dates classified by the construct", "records",
     "Classified days"),
    ("min_contributing_stations", "fewest reporting stations on any day of the event",
     "stations", "Minimum stations"),
    ("max_contributing_stations", "most reporting stations on any day of the event",
     "stations", "Maximum stations"),
    ("minimum_reference_values", "smallest walk-forward baseline sample behind any "
     "threshold used inside the event", "observations", "Smallest baseline sample"),
    ("mean_daily_high_f", "mean daily high across the days of the event", "degF",
     "Mean daily high"),
    ("onset_year", "calendar year in which the event began", "year", "Onset year"),
    ("analysis_days", "daily county-level records in the classification window",
     "records", "Analysis days"),
    ("native_analysis_days", "daily county-level records that were observed rather "
     "than gap-filled", "records", "Observed days"),
    ("peak_month", "calendar month carrying the most classified days", "",
     "Peak month"),
    ("interpretation", "how the row should and should not be read", "",
     "Interpretation"),
    ("note", "free-text qualification attached to the row", "", "Note"),
    ("label", "reader-facing short label", "", "Label"),
    ("counties", "number of counties", "counties", "Counties"),
    ("min_across_counties_f", "lowest county value", "degF", "Minimum across counties"),
    ("max_across_counties_f", "highest county value", "degF", "Maximum across counties"),
    ("_f", "temperature or temperature difference", "degF", "Temperature"),
    ("pct_", "percentage", "percent", "Percentage"),
    ("n_", "count", "records", "Count"),
]
DESCRIBE_DOC = {
    "count": ("number of values in the distribution", "records", "Count"),
    "mean": ("arithmetic mean of the distribution", "", "Mean"),
    "std": ("standard deviation of the distribution", "", "Standard deviation"),
    "min": ("smallest value", "", "Minimum"),
    "max": ("largest value", "", "Maximum"),
    "10%": ("10th percentile", "", "10th percentile"),
    "25%": ("25th percentile", "", "25th percentile"),
    "50%": ("median", "", "Median"),
    "75%": ("75th percentile", "", "75th percentile"),
    "90%": ("90th percentile", "", "90th percentile"),
    "99%": ("99th percentile", "", "99th percentile"),
}


def lookup(col):
    if col in COLUMN_DOC:
        return COLUMN_DOC[col] + ("exact",)
    if col in DESCRIBE_DOC:
        return DESCRIBE_DOC[col] + ("distribution",)
    for pat, doc, unit, label in PATTERN_DOC:
        if col.endswith(pat) or col.startswith(pat) or pat == col:
            return doc, unit, label, "pattern"
    return "", "", col.replace("_", " ").capitalize(), "undocumented"


def variable_dictionary():
    rows = []
    for fn in sorted(os.listdir(T)):
        if not fn.endswith(".csv"):
            continue
        try:
            head = pd.read_csv(os.path.join(T, fn), nrows=200, low_memory=False)
        except Exception:
            continue
        for col in head.columns:
            doc, unit, label, how = lookup(col)
            rows.append(dict(
                table=fn, table_purpose=TABLE_DOC.get(fn, ""), column=col,
                reader_facing_label=label, definition=doc, unit=unit,
                dtype=str(head[col].dtype), documentation_source=how,
                documented=bool(doc),
                note=("pooled statewide QA quantity; never a substantive result"
                      if col.endswith("_QA") else "")))
    d = pd.DataFrame(rows)
    return d


# =============================================================================
# 2. definition registry
# =============================================================================
def definition_registry():
    rows = []
    for c in K.constructs():
        fam = c["family"]
        if fam == "relative":
            formula = ("daily high > county- and calendar-date-specific historical "
                       "%dth percentile, for at least %d consecutive days"
                       % (c["percentile"], c["duration_days"]))
            gate_op = ""
        elif fam == "hybrid":
            formula = ("(daily high > county- and calendar-date-specific historical "
                       "%dth percentile) AND (daily high >= %d degF), for at least %d "
                       "consecutive days" % (c["percentile"], int(c["absolute_gate_f"]),
                                             c["duration_days"]))
            gate_op = ">="
        else:
            formula = ("daily high > %d degF for at least %d consecutive days"
                       % (int(c["absolute_gate_f"]), c["duration_days"]))
            gate_op = ">"
        rows.append(dict(
            construct_id=c["construct_id"], construct_family=fam,
            reader_facing_name=c["reader_name"],
            legacy_definition_id=c["legacy_definition_id"],
            legacy_window=c["legacy_window"],
            metric="daily maximum air temperature (ETCCDI TX)",
            metric_reader_label=K.VAR_DAILY_LABEL["Tmax"],
            percentile=c["percentile"], minimum_duration_days=c["duration_days"],
            absolute_gate_f=c["absolute_gate_f"],
            threshold_window=c["window"] or "none",
            threshold_window_label=(K.WINDOW_READER[c["window"]] if c["window"]
                                    else "not applicable: an absolute rule has no "
                                         "baseline and therefore no window"),
            baseline=("walk-forward, 1979 to the year before the classified year"
                      if fam != "absolute" else "none"),
            relative_comparison_operator=(C.COMPARISON_OP if fam != "absolute" else ""),
            absolute_gate_operator=gate_op,
            season_rule="year round",
            formula=formula,
            day_label=c["day_label"], event_label=c["event_label"],
            state=K.TEST_STATE, analysis_years=K.ANALYSIS_YEARS_LABEL,
            input_table="gap-filled county-day table (outputs/TX/county_daily_heat.csv)",
            HWN="annual number of distinct events",
            HWF="annual number of days participating in events",
            HWD="longest event duration (NOT the median event duration)",
            is_a_heatwave=("no - year-round relative construct with no absolute heat "
                           "condition" if fam == "relative" else
                           "part - relative anomaly AND an absolute daily-high gate"
                           if fam == "hybrid" else
                           "an absolute hot spell, not a relative anomaly"),
            naming_note=("TX in the identifier is the ETCCDI symbol for the daily "
                         "maximum temperature, not the state abbreviation. This "
                         "construct is not TX90p: TX90p is a warm-day FREQUENCY index "
                         "and does not encode event duration."),
            gate_note=("80 degF and 90 degF are absolute daily-high gates chosen for "
                       "this sensitivity test. They are NOT National Weather Service "
                       "advisory thresholds." if c["absolute_gate_f"] else "")))
    return pd.DataFrame(rows)


# =============================================================================
# 3. manifests
# =============================================================================
def figure_manifest():
    parts = []
    for f in ("_figure_manifest_part1.csv", "_figure_manifest_part2.csv"):
        p = os.path.join(Q, f)
        if os.path.exists(p):
            parts.append(pd.read_csv(p))
    m = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    m["figure_path"] = m["figure_file"].map(lambda f: "figures/" + f)
    m["figure_exists"] = m["figure_file"].map(
        lambda f: os.path.exists(os.path.join(K.DIR_FIG, f)))
    m["figure_md5"] = m["figure_file"].map(
        lambda f: md5_of(os.path.join(K.DIR_FIG, f))
        if os.path.exists(os.path.join(K.DIR_FIG, f)) else "")
    m["reproducible_from"] = ("scripts/r09_figures_part1.py or "
                              "scripts/r10_figures_part2.py plus the input table")
    return m


def run_manifest():
    rows = []
    order = ["r00_config.py", "r_palette.py", "r_figlib.py",
             "r01_reproduce_audit.py", "r02_temperature_panel.py",
             "r03_period_aggregation.py", "r04_trends.py", "r05_benchmark.py",
             "r06_events.py", "r07_agreement_and_gates.py", "r08_audits.py",
             "r09_figures_part1.py", "r10_figures_part2.py", "r11_qa_tests.py",
             "r12_report.py", "run_revision.py"]
    purpose = {
        "r00_config.py": "configuration, terminology, construct naming, samples",
        "r_palette.py": "colour-vision validation of every figure palette",
        "r_figlib.py": "shared figure furniture and the figure manifest",
        "r01_reproduce_audit.py": "Stage 1: reproduce and audit the current package",
        "r02_temperature_panel.py": "Stage 2: county temperature panel and sanity checks",
        "r03_period_aggregation.py": "Stages 3-4: equal-county period aggregation",
        "r04_trends.py": "Stage 5: descriptive trend sensitivity",
        "r05_benchmark.py": "Stage 6: external benchmarking",
        "r06_events.py": "Stages 7-8: construct families and eligibility denominators",
        "r07_agreement_and_gates.py": "agreement, absolute gates, rates, geography",
        "r08_audits.py": "Stages 15-16: long-event audit and data-quality sensitivity",
        "r09_figures_part1.py": "revised figures E2-E4 and R1-R4",
        "r10_figures_part2.py": "revised figures E5-E9 and R5-R10",
        "r11_qa_tests.py": "the consolidated QA suite (blocking)",
        "r12_report.py": "dictionary, registry, manifests, final report",
        "run_revision.py": "driver: runs every step in order, stopping on failure",
    }
    for i, s in enumerate(order, 1):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), s)
        rows.append(dict(step=i, script="scripts/" + s,
                         purpose=purpose.get(s, ""),
                         exists=os.path.exists(p),
                         size_bytes=os.path.getsize(p) if os.path.exists(p) else np.nan,
                         md5=md5_of(p) if os.path.exists(p) else ""))
    man = pd.DataFrame(rows)
    outs = []
    for sub in ("tables", "figures", "qa", "data_dictionary", "reports",
                "county_profiles", "event_audits", "config", "current_vs_revised"):
        d = os.path.join(K.REV_ROOT, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            fp = os.path.join(d, f)
            if not os.path.isfile(fp):
                continue
            n = np.nan
            if f.endswith(".csv") and os.path.getsize(fp) < 60_000_000:
                try:
                    n = len(pd.read_csv(fp, low_memory=False))
                except Exception:
                    pass
            outs.append(dict(step=np.nan, script="", purpose="output",
                             exists=True, size_bytes=os.path.getsize(fp),
                             md5=md5_of(fp), output="%s/%s" % (sub, f), n_rows=n))
    return pd.concat([man, pd.DataFrame(outs)], ignore_index=True)


# =============================================================================
# 4. the report
# =============================================================================
def build_report(ctx):
    L = []
    A = L.append
    c = ctx

    A("# Extreme-temperature analysis, revision v2")
    A("")
    A("_Gulf-state temperature description and Texas extreme-temperature "
      "classification, audited and revised._")
    A("")
    A("Generated %s | git `%s` | python %s, pandas %s, numpy %s"
      % (c["date"], c["git"], c["prov"]["python"], c["prov"]["pandas"],
         c["prov"]["numpy"]))
    A("")
    A("---")
    A("")
    A("## 1  Purpose")
    A("")
    A("To audit the delivered extreme-temperature package, correct the aggregation "
      "and terminology defects it contains, and reissue every affected table, figure, "
      "caption and finding in a form an advisor can review and a later analyst can "
      "link to occupational-injury data. The original package is untouched; this is a "
      "parallel, versioned revision.")
    A("")
    A("## 2  Research question")
    A("")
    A("Descriptively: what does the daily temperature record look like across the five "
      "Gulf states over %s, how has it differed between prespecified periods, and how "
      "sensitive is a county-level heat-event classification to the choice of "
      "definition, threshold, duration, absolute gate, county sample and data quality?"
      % K.YEARS_LABEL)
    A("")
    A("## 3  Epistemic level")
    A("")
    A("**Descriptive.** The analysis may describe temperature distributions, period "
      "differences, classification sensitivity, event frequency, event timing, "
      "geographic patterns and agreement among definitions. It does **not** establish "
      "causal climate trends, occupational-injury effects, individual worker exposure, "
      "the objectively correct heatwave definition, or equivalence with National "
      "Weather Service advisories.")
    A("")
    A("## 4  Data sources")
    A("")
    A(K.md_table(c["sources"]))
    A("")
    A("%s" % K.PANEL_SENTENCE)
    A("")
    A("## 5  Current computation, as it stands")
    A("")
    A("Every aggregation performed by the current package was read off its code and "
      "catalogued in `qa/02_existing_aggregation_inventory.csv` (%d entries), with "
      "the data lineage of every figure in `qa/02b_existing_figure_lineage.csv`. The "
      "current scripts were then re-executed with their outputs redirected to "
      "`current_vs_revised/reproduction/`, and **all %d regenerated tables and "
      "figures reproduce bit-for-bit** "
      "(`qa/01_existing_pipeline_reproduction.csv`). The classification step was "
      "reproduced separately by an independent rebuild from the archived threshold "
      "cache: **%d of %d exact set-equality checks on classified county-dates and "
      "event boundaries pass**."
      % (c["n_agg"], c["n_repro"], c["n_verify_pass"], c["n_verify"]))
    A("")
    A("The audit therefore rests on numbers that were reproduced before they were "
      "criticised.")
    A("")
    A("## 6  Identified weaknesses")
    A("")
    A(K.md_table(c["agg"][c["agg"]["severity"].isin(["BLOCKING", "high"])][
        ["package_step", "quantity", "issue", "severity"]], max_rows=30))
    A("")
    A("Three further defects were found that the current package does not record at "
      "all:")
    A("")
    A("1. **%d raw county-dates have a daily high below the same day's daily low.** On "
      "%d of them the county high and the county low were averaged over different "
      "numbers of stations, so the pair is not internally consistent. The current "
      "package never checks this. Handling is declared in "
      "`r00_config.INVERTED_RECORD_ACTION`; the records are preserved in "
      "`qa/quarantined_inverted_daily_records.csv`. None falls in the Texas "
      "classification window."
      % (c["n_quar"], c["n_quar_station"]))
    A("2. **The archived threshold cache does not survive a default CSV round trip.** "
      "%s of %s stored threshold values are misparsed by the pandas default float "
      "parser - `94.38799999999999` reads back as `94.388` - and with the project's "
      "strict `>` comparison that one bit flips the classification of county-dates "
      "sitting exactly on their threshold. Any downstream reuse of that cache must "
      "pass `float_precision='round_trip'`, or the thresholds should be archived in a "
      "binary format. See `qa/float_roundtrip_defect.csv`."
      % (c["frt_bad"], c["frt_tot"]))
    A("3. **There is no external benchmark in this repository.** The only second "
      "temperature product is byte-identical to the project data on all %s matched "
      "daily records, despite its build script documenting a different county "
      "assignment. See section 9." % c["bench_n"])
    A("")
    A("## 7  Revisions performed")
    A("")
    A(K.md_table(pd.DataFrame(c["revisions"], columns=["area", "what changed"])))
    A("")
    A("## 8  Current versus revised, numerically")
    A("")
    A("### Period difference, %s to %s, average daily high temperature"
      % (K.BASE_PERIOD, K.RECENT_PERIOD))
    A("")
    A(K.md_table(c["cvr_tmax"], floatfmt="%.2f"))
    A("")
    A("The revised point estimates move by up to %.2f degF. More consequential than "
      "the movement is what the current package never showed: the bootstrap interval "
      "across counties is %.2f to %.2f degF wide, so several of the state-to-state "
      "orderings asserted in the current findings are not supported by the data behind "
      "them." % (c["max_move"], c["ci_min_w"], c["ci_max_w"]))
    A("")
    A("### County sample")
    A("")
    A("The current 'balanced panel' required only one qualifying year per period. "
      "Enforcing a real minimum removes a large share of it:")
    A("")
    A(K.md_table(c["samples"]))
    A("")
    A("### Classification results")
    A("")
    A(K.md_table(c["cvr_class"]))
    A("")
    A("## 9  Validity risks")
    A("")
    for r in c["risks"]:
        A("- %s" % r)
    A("")
    A("## 10  Claims this package supports")
    A("")
    for s in c["allowed"]:
        A("- \"%s\"" % s)
    A("")
    A("## 11  Claims this package does NOT support")
    A("")
    for s in c["not_allowed"]:
        A("- \"%s\"" % s)
    A("")
    A("## 12  Unresolved decisions")
    A("")
    for i, s in enumerate(c["unresolved"], 1):
        A("%d. %s" % (i, s))
    A("")
    A("## 13  Recommended primary definition")
    A("")
    A(c["primary_rec"])
    A("")
    A("## 14  Sensitivity definitions")
    A("")
    A(K.md_table(pd.DataFrame(c["sensitivity"], columns=["construct", "role"])))
    A("")
    A("## 15  Reproducibility record")
    A("")
    A(K.md_table(c["repro"]))
    A("")
    A("Run the whole revision with `python scripts/run_revision.py`. Each step stops "
      "the pipeline if a blocking QA test fails; `qa/QA_TEST_SUITE.csv` records all "
      "%d checks (%d pass, %d fail, %d reported)."
      % (c["qa_n"], c["qa_pass"], c["qa_fail"], c["qa_rep"]))
    A("")
    A("## 16  Next action")
    A("")
    for i, s in enumerate(c["next"], 1):
        A("%d. %s" % (i, s))
    A("")
    A("---")
    A("")
    A("## Figure specifications")
    A("")
    A("Every figure below is reproducible from the named table and script. The full "
      "machine-readable version is `tables/figure_data_manifest.csv`.")
    A("")
    for _, r in c["figman"].iterrows():
        A("### %s - `%s`" % (r["figure_id"], r["figure_file"]))
        A("")
        A("| field | value |")
        A("|---|---|")
        A("| purpose | %s |" % r["purpose"])
        A("| unit of analysis | %s |" % r["unit_of_analysis"])
        A("| input table | %s |" % r["input_table"])
        A("| aggregation | %s |" % r["aggregation_formula"])
        A("| denominator | %s |" % r["denominator"])
        A("| result supported | %s |" % r["result_supported"])
        A("| result NOT supported | %s |" % r["result_not_supported"])
        A("| limitation | %s |" % r["limitation"])
        A("")
        A("> %s" % r["draft_caption"])
        A("")
    return "\n".join(L) + "\n"


# =============================================================================
def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 78)
    K.log("r12  dictionary, registry, manifests and the final report")
    K.log("=" * 78)

    vd = variable_dictionary()
    vd.to_csv(os.path.join(D, "revised_variable_dictionary.csv"), index=False)
    K.log("[write] revised_variable_dictionary.csv  (%d columns across %d tables, "
          "%d documented)" % (len(vd), vd["table"].nunique(),
                              int(vd["documented"].sum())))
    reg = definition_registry()
    reg.to_csv(os.path.join(D, "definition_registry_revised.csv"), index=False)
    K.log("[write] definition_registry_revised.csv  (%d constructs)" % len(reg))
    figman = figure_manifest()
    figman.to_csv(os.path.join(T, "figure_data_manifest.csv"), index=False)
    K.log("[write] figure_data_manifest.csv  (%d figures)" % len(figman))

    # ---- context for the report --------------------------------------------
    prov = json.load(open(os.path.join(K.DIR_CONFIG, "provenance.json")))
    agg = pd.read_csv(os.path.join(Q, "02_existing_aggregation_inventory.csv"))
    rp = pd.read_csv(os.path.join(Q, "01_existing_pipeline_reproduction.csv"))
    ver = pd.read_csv(os.path.join(Q, "e02_independent_rebuild_verification.csv"))
    frt = pd.read_csv(os.path.join(Q, "float_roundtrip_defect.csv"))
    idt = pd.read_csv(os.path.join(Q, "benchmark_identity_test.csv"))
    quar = pd.read_csv(os.path.join(Q, "quarantined_inverted_daily_records.csv"))
    qa = pd.read_csv(os.path.join(Q, "QA_TEST_SUITE.csv"))
    comp = pd.read_csv(os.path.join(T, "period_comparison_current_vs_revised.csv"))
    members = pd.read_csv(os.path.join(T, "sample_membership_counties.csv"),
                          dtype={"county_fips": str})
    summ = pd.read_csv(os.path.join(T, "construct_summary.csv"))
    season = pd.read_csv(os.path.join(T, "seasonal_classification_shares.csv"))
    ge = pd.read_csv(os.path.join(T, "absolute_gate_effect.csv"))
    flat = pd.read_csv(os.path.join(Q, "flatness_criterion.csv"))
    ann = pd.read_csv(os.path.join(T, "county_annual_all_constructs.csv"),
                      dtype={"county_fips": str})
    ev = pd.read_csv(os.path.join(T, "long_event_audit.csv"))
    e01 = pd.read_csv(os.path.join(K.CURRENT_PKG, "tables",
                                   "e01_state_decade_temperature.csv"))

    cvr = comp[(comp["variable"] == "Tmax") & (comp["period"] == K.RECENT_PERIOD)]
    a = cvr[cvr["sample"] == K.SAMPLE_A_NAME].set_index("state")
    b = cvr[cvr["sample"] == K.SAMPLE_B_NAME].set_index("state")
    cvr_tmax = pd.DataFrame({
        "state": [K.STATE_LABEL[s] for s in K.STATES],
        "current (pooled)": [a.loc[s, "current_published_change_vs_base_f"]
                             for s in K.STATES],
        "current counties": [int(a.loc[s, "current_published_counties"])
                             for s in K.STATES],
        "revised Sample A": [a.loc[s, "revised_change_vs_base_f"] for s in K.STATES],
        "Sample A 95% interval": ["%.2f to %.2f" % (a.loc[s, "revised_change_ci_low_f"],
                                                    a.loc[s, "revised_change_ci_high_f"])
                                  for s in K.STATES],
        "Sample A counties": [int(a.loc[s, "revised_counties"]) for s in K.STATES],
        "revised Sample B": [b.loc[s, "revised_change_vs_base_f"] for s in K.STATES],
        "Sample B counties": [int(b.loc[s, "revised_counties"]) for s in K.STATES],
    })
    ci_w = (cvr["revised_change_ci_high_f"] - cvr["revised_change_ci_low_f"])

    smp = pd.DataFrame({
        "state": [K.STATE_LABEL[s] for s in K.STATES],
        "current 'balanced panel'": [
            int(e01[(e01["state"] == s) & (e01["variable"] == "Tmax")
                    & (e01["panel"] == "balanced_panel")]["counties"].iloc[0])
            for s in K.STATES],
        "Sample A: consistent-county": [
            int(((members["sample"] == K.SAMPLE_A_NAME) & (members["state"] == s)
                 & (members["variable"] == "Tmax")).sum()) for s in K.STATES],
        "Sample B: strict balanced": [
            int(((members["sample"] == K.SAMPLE_B_NAME) & (members["state"] == s)
                 & (members["variable"] == "Tmax")).sum()) for s in K.STATES],
    })

    p = summ[summ["construct_id"] == K.PRIMARY_CONSTRUCT].iloc[0]
    g90 = ge[(ge["percentile"] == 90) & (ge["duration_days"] == 3)
             & (ge["absolute_gate_f"] == 90.0)].iloc[0]
    rel = summ[summ["construct_family"] == "relative"]
    cvr_class = pd.DataFrame([
        ["headline quantity for a definition",
         "statewide pooled event total, and a per-county median of an 11-year "
         "cumulative count",
         "median ANNUAL county-level event count and classified-day count, with the "
         "full distribution"],
        ["seasonality", "two categories: inside and outside June-September",
         "three categories: June-September %.0f-%.0f%%, May and October %.0f-%.0f%%, "
         "November-April %.0f-%.0f%% across the nine relative definitions"
         % (rel["pct_days_june_september"].min(), rel["pct_days_june_september"].max(),
            rel["pct_days_may_and_october"].min(), rel["pct_days_may_and_october"].max(),
            rel["pct_days_november_april"].min(), rel["pct_days_november_april"].max())],
        ["monthly rate denominator",
         "one shared denominator reused from another package for all three families",
         "family-specific valid-record counts, tested for equality and documented"],
        ["'the monthly rate is nearly flat'",
         "asserted with no criterion",
         "criterion defined (highest/lowest month at most 1.5 and coefficient of "
         "variation at most 0.15); %d of %d constructs meet it, so the curves are "
         "NOT described as flat" % (int(flat["meets_flatness_criterion"].sum()),
                                    len(flat))],
        ["geography of a relative rule",
         "'flags a similar number of days everywhere by construction'",
         "measured: cumulative classified days for %s range %d to %d across counties, "
         "a factor of %.1f"
         % (K.PRIMARY_CONSTRUCT,
            int(ann[ann["construct_id"] == K.PRIMARY_CONSTRUCT]
                .groupby("county_fips")["annual_classified_day_count"].sum().min()),
            int(ann[ann["construct_id"] == K.PRIMARY_CONSTRUCT]
                .groupby("county_fips")["annual_classified_day_count"].sum().max()),
            (ann[ann["construct_id"] == K.PRIMARY_CONSTRUCT]
             .groupby("county_fips")["annual_classified_day_count"].sum().max()
             / max(1, ann[ann["construct_id"] == K.PRIMARY_CONSTRUCT]
                   .groupby("county_fips")["annual_classified_day_count"].sum()
                   .replace(0, np.nan).min())))],
        ["the 90 degF value", "'floor', implicitly a correction",
         "absolute daily-high gate; changes the construct to a hybrid "
         "relative-and-absolute definition; retains %.0f%% of classified days and "
         "moves the June-September share from %.0f%% to %.0f%%"
         % (g90["pct_classified_days_retained"],
            g90["pct_days_june_september_no_gate"],
            g90["pct_days_june_september_with_gate"])],
        ["long events", "not examined",
         "%s events longer than %d days audited and classified; the longest is %d days"
         % ("{:,}".format(len(ev)), K.LONG_EVENT_DAYS,
            int(ev["event_duration_days"].max()))],
    ], columns=["quantity", "current package", "revised package"])

    ctx = dict(
        date=time.strftime("%Y-%m-%d"), git=prov.get("git_commit", "unknown"),
        prov=prov, agg=agg, n_agg=len(agg),
        n_repro=int(rp["verdict"].isin(["IDENTICAL_BYTES", "IDENTICAL_VALUES"]).sum()),
        n_verify=len(ver), n_verify_pass=int((ver["result"] == "PASS").sum()),
        n_quar=len(quar),
        n_quar_station=int(quar["station_sets_differ"].sum()) if len(quar) else 0,
        frt_bad="{:,}".format(int(frt["threshold_values_misparsed_by_default"].sum())),
        frt_tot="{:,}".format(int(frt["threshold_rows"].sum())),
        bench_n="{:,}".format(int(idt["matched_daily_records"].sum())),
        cvr_tmax=cvr_tmax, samples=smp, cvr_class=cvr_class, figman=figman,
        max_move=comp["change_absolute_difference_f"].abs().max(),
        ci_min_w=ci_w.min(), ci_max_w=ci_w.max(),
        qa_n=len(qa), qa_pass=int((qa["result"] == "PASS").sum()),
        qa_fail=int((qa["result"] == "FAIL").sum()),
        qa_rep=int(qa["result"].isin(["REPORT", "FLAG"]).sum()),
        sources=pd.DataFrame([
            ["raw GHCN county-day records, five Gulf states",
             "%s, observed only, no gap-filling" % K.YEARS_LABEL,
             "Part 1: figures E2, E2b, E3, E4, R1, R2, R4"],
            ["gap-filled county-day table, Texas",
             "%s, inverse-distance gap-filled" % K.ANALYSIS_YEARS_LABEL,
             "Parts 2 and 3: figures E5 to E9, R5 to R10"],
            ["archived walk-forward threshold cache",
             "3 percentiles x 4 windows, read with float_precision='round_trip'",
             "reproduction of the classification step"],
            ["county coverage and imputation report, Texas", "per county",
             "every county-level data-quality indicator"],
            ["county polygons (US Census)", "2020 TIGER/Line", "figure E9"],
        ], columns=["source", "extent", "used by"]),
        revisions=[
            ["aggregation", "state period summaries rebuilt as daily -> annual "
                            "county value -> one value per county per period -> median "
                            "across counties, with a county bootstrap interval"],
            ["county sample", "the mis-named 'balanced panel' replaced by Sample A "
                              "(consistent-county) and Sample B (strict balanced), "
                              "both prespecified and both reported"],
            ["trend language", "period differences relabelled as differences; Sen and "
                               "least-squares slopes estimated separately under four "
                               "county samples"],
            ["terminology", "plain-language variable labels; Tavg defined explicitly; "
                            "TGm retired; reader-facing unit language throughout"],
            ["construct naming", "three families with explicit identifiers and reader "
                                 "names; year-round relative constructs are no longer "
                                 "called heatwaves"],
            ["denominators", "computed per construct family and tested for equality "
                             "rather than shared by assumption"],
            ["seasonality", "three categories; the shoulder months are no longer "
                            "merged into the cool season"],
            ["event layer", "full individual event catalogues with peak, exceedance, "
                            "observed and gap-filled day counts and a review status"],
            ["audits", "long-event audit, six-way data-quality sensitivity, county "
                       "profiles, palette validation"],
            ["QA", "a blocking test suite of %d checks covering daily logic, coverage, "
                   "period weighting, event logic, gate logic, denominators and output "
                   "consistency" % len(qa)],
        ],
        risks=[
            "**Temperature source.** No independent temperature product is available "
            "in this repository, so the county aggregation is unvalidated. Earlier "
            "work found anchor-station against multi-station composite agreeing at "
            "only 0.45 to 0.73, which is larger than most of the definition effects "
            "measured here. This remains the dominant unresolved risk.",
            "**Station-network composition.** The reporting network changes over the "
            "record. Samples A and B control which counties are compared but not which "
            "stations are inside a county in a given year; the stable-station "
            "sensitivity is thin outside Texas and Florida (Louisiana 1 county, "
            "Mississippi 0, Alabama 2).",
            "**Gap-filling.** 22 of 254 Texas counties have no observed temperature at "
            "all and are carried entirely by interpolation. They are marked everywhere "
            "and a sensitivity excluding them is reported, but their classified days "
            "describe the interpolation as much as the county.",
            "**Different inputs for Part 1 and Parts 2-3.** Part 1 uses the observed "
            "record; Parts 2 and 3 use the gap-filled table, as the rest of the "
            "project does. The two are not on the same input by design, and no "
            "quantity is carried between them.",
            "**Sample selection.** Samples A and B exclude between a third and three "
            "quarters of counties depending on the state, and the excluded counties "
            "are disproportionately rural and short-record. This is a coverage "
            "restriction, not a random sample.",
            "**Knife-edge comparisons.** With a strict `>` comparison, a county-date "
            "sitting exactly on its threshold is decided by the last bit of a stored "
            "float. This affects a handful of records but is a reproducibility hazard "
            "for anyone reusing the archived thresholds.",
            "**No health outcome anywhere in this package**, so nothing here can "
            "identify a correct definition, and agreement between definitions is not "
            "evidence of accuracy.",
        ],
        allowed=[
            "Average daily high temperatures were highest during the prespecified warm "
            "season.",
            "Average daily lows remained below 75 degF in some state-month summaries.",
            "The recent-period median differed from the 1980s median under this "
            "aggregation.",
            "Relative and absolute definitions identified different county-dates.",
            "The 90 degF gate concentrated classifications into warmer months.",
            "The result is sensitive to data coverage, county weighting, and "
            "station-network composition.",
            "The analysis does not establish causality.",
        ],
        not_allowed=[
            "Every summer temperature should exceed 75 degF.",
            "The current balanced panel fully controls station-network change.",
            "The period difference proves a climate trend.",
            "The cool season causes the off-season classifications.",
            "The 90 degF floor is an NWS advisory threshold.",
            "The relative percentile definition gives every county equal exposure.",
            "The Jaccard Index measures accuracy.",
            "A county with more classified days necessarily has greater worker heat "
            "exposure.",
            "The classifications caused occupational accidents.",
        ],
        unresolved=[
            "**The temperature source.** An independent, spatially consistent product "
            "(nClimGrid-Daily, PRISM or Daymet temperature) must be obtained before "
            "any county-level result is treated as settled. Nothing in this package "
            "narrows that question.",
            "**Handling of the %d inverted county-dates.** The declared rule "
            "quarantines the whole county-date. An advisor may prefer to keep the "
            "high and the low as separately valid station means. The choice changes "
            "nothing measurable here but should be signed off." % len(quar),
            "**Which sample is primary.** Sample A retains more counties, Sample B is "
            "strictly balanced. Their intervals overlap in every state, so the choice "
            "is currently a matter of preference rather than of evidence.",
            "**Whether to adopt an absolute gate at all.** The gate makes the "
            "construct part-absolute. That is a research-question decision, not a "
            "sensitivity setting, and it should be made before linkage rather than "
            "after.",
            "**Whether the shoulder months belong with summer.** May and October carry "
            "%.0f to %.0f%% of classified days across the relative definitions. "
            "A June-September season and a May-October season are materially different "
            "exposure windows."
            % (rel["pct_days_may_and_october"].min(),
               rel["pct_days_may_and_october"].max()),
            "**Extension beyond Texas.** Parts 2 and 3 are state-agnostic but only "
            "Texas has a built county-day table.",
        ],
        primary_rec=(
            "**%s** - the county-specific 90th-percentile daily-high warm spell with a "
            "minimum duration of three days and a 90 degF absolute gate, at the %s "
            "threshold window.\n\n"
            "Reasoning, and the reasoning is about the research question rather than "
            "about the numbers. A purely relative rule (`%s`) places %.0f%% of its "
            "classified days outside June-September and %.0f%% in November-April; for "
            "an occupational heat-exposure measure a reader will interpret that as "
            "hazardous heat, and it is not. Adding the 90 degF gate moves the "
            "June-September share from %.0f%% to %.0f%% and retains %.0f%% of the "
            "classified days. The three-day minimum removes the shortest runs without "
            "the %.1fx reduction the five-day rule imposes.\n\n"
            "This recommendation is conditional in two ways that must travel with it. "
            "First, the gate makes the construct **part absolute**, so it must be "
            "named and described as a hybrid relative-and-absolute heat event, never "
            "as a heatwave and never as an NWS-equivalent. Second, no health outcome "
            "appears anywhere in this package, so nothing here can establish that this "
            "definition is the correct one - only that it matches the stated research "
            "question better than the alternatives tested."
            % (K.hyb_id(90, 3, 90.0), K.PRIMARY_WINDOW, K.PRIMARY_CONSTRUCT,
               100 - p["pct_days_june_september"], p["pct_days_november_april"],
               g90["pct_days_june_september_no_gate"],
               g90["pct_days_june_september_with_gate"],
               g90["pct_classified_days_retained"],
               float(summ[summ["construct_id"] == K.rel_id(90, 2)]
                     ["median_cumulative_classified_days_per_county"].iloc[0]
                     / max(1.0, summ[summ["construct_id"] == K.rel_id(90, 5)]
                           ["median_cumulative_classified_days_per_county"].iloc[0])))),
        sensitivity=[
            [K.PRIMARY_CONSTRUCT, "the same construct with no absolute gate - isolates "
                                  "what the gate does"],
            [K.hyb_id(90, 3, 80.0), "the weaker gate - shows that 80 degF is too low "
                                    "to change the character of the definition"],
            [K.abs_id(90.0, 3), "absolute only - the hazard-style construct the "
                                "relative family is usually contrasted against"],
            [K.rel_id(85, 3), "a looser percentile at the same duration"],
            [K.rel_id(90, 2) + " and " + K.rel_id(90, 5),
             "the duration axis at the recommended percentile"],
            [K.rel_id(90, 3, "w05") + ", " + K.rel_id(90, 3, "month"),
             "the threshold-window axis, available in the annual layer for all four "
             "windows"],
            ["Sample A and Sample B", "the county-selection axis for every Part 1 "
                                      "result"],
            ["six county subsets", "the data-quality axis for every Part 2 result"],
        ],
        repro=pd.DataFrame([
            ["git commit", prov.get("git_commit", "unknown")],
            ["python", prov["python"]],
            ["pandas / numpy / matplotlib / scipy",
             "%s / %s / %s / %s" % (prov["pandas"], prov["numpy"],
                                    prov["matplotlib"], prov["scipy"])],
            ["geopandas", prov.get("geopandas", "unavailable")],
            ["platform", prov["platform"]],
            ["bootstrap seed", str(K.BOOTSTRAP_SEED)],
            ["bootstrap resamples", str(K.BOOTSTRAP_N)],
            ["configuration", "config/resolved_configuration.csv, "
                              "config/r00_config_snapshot.py"],
            ["input checksums", "qa/03_current_output_checksums.csv"],
            ["run manifest", "run_manifest.csv"],
            ["QA suite", "qa/QA_TEST_SUITE.csv, qa/QA_REPORT.md"],
        ], columns=["item", "value"]),
        next=[
            "Obtain an independent, spatially consistent temperature product "
            "(nClimGrid-Daily, PRISM or Daymet temperature) for %s and re-run r05. "
            "Until that exists, no county-level temperature value in this project has "
            "been externally checked, and this is the single highest-value next step."
            % K.YEARS_LABEL,
            "Get advisor sign-off on the recommended primary definition and on the "
            "handling of the %d inverted county-dates." % len(quar),
            "Fix the archived threshold cache: store thresholds in a binary format, or "
            "add `float_precision='round_trip'` to every reader in the pipeline.",
            "Build the county-day table for Louisiana, Mississippi, Alabama and "
            "Florida so Parts 2 and 3 stop being Texas-only.",
            "Decide the exposure window (June-September against May-October) before "
            "linkage, because it changes the classified-day count by %.0f to %.0f%%."
            % (rel["pct_days_may_and_october"].min(),
               rel["pct_days_may_and_october"].max()),
            "Only then link to occupational-injury data, carrying the data-quality "
            "indicator for every county into the linked dataset.",
        ],
    )

    rep = build_report(ctx)
    with open(os.path.join(K.DIR_REPORTS, "FINAL_REPORT.md"), "w",
              encoding="utf-8") as f:
        f.write(rep)
    K.log("[write] reports/FINAL_REPORT.md  (%d lines)" % len(rep.splitlines()))

    write_findings(ctx, summ, season, ge, flat, ann, ev, comp, cvr_tmax)
    write_cvr(ctx, cvr_tmax, smp, cvr_class)
    write_readme(ctx)

    # ---- terminology gate over the prose this step just wrote ---------------
    reports = [os.path.join(K.DIR_REPORTS, f) for f in os.listdir(K.DIR_REPORTS)
               if f.endswith(".md")]
    reports += [os.path.join(K.REV_ROOT, "README.md"),
                os.path.join(K.DIR_CVR, "CURRENT_VS_REVISED.md")]
    hits = K.terminology_violations(reports)
    qa_path = os.path.join(Q, "QA_TEST_SUITE.csv")
    row = pd.DataFrame([dict(
        test="terminology", check="retired_vocabulary_absent_from_reports",
        result="PASS" if not hits else "FAIL", blocking=True,
        detail="%d unguarded use(s) across %d files%s"
               % (len(hits), len(reports),
                  "" if not hits else ": " + str(hits[:3])),
        source="reports/, README.md, current_vs_revised/")])
    if os.path.exists(qa_path):
        pd.concat([pd.read_csv(qa_path), row], ignore_index=True).to_csv(
            qa_path, index=False)
    K.log("terminology gate over the written reports: %s (%d unguarded use(s))"
          % ("PASS" if not hits else "FAIL", len(hits)))
    for h in hits[:6]:
        K.log("   ! %-24s %-46s %s" % h)
    if hits:
        raise K.BlockingQAFailure(
            "the written reports contain %d unguarded use(s) of the retired "
            "vocabulary" % len(hits))

    man = run_manifest()
    man.to_csv(os.path.join(K.REV_ROOT, "run_manifest.csv"), index=False)
    K.log("[write] run_manifest.csv  (%d scripts, %d outputs)"
          % (int(man["script"].astype(bool).sum()),
             int(man["purpose"].eq("output").sum())))
    K.log("r12 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


def write_findings(c, summ, season, ge, flat, ann, ev, comp, cvr_tmax):
    rel = summ[summ["construct_family"] == "relative"]
    g = ge[(ge["percentile"] == 90) & (ge["duration_days"] == 3)]
    L = []
    A = L.append
    A("# Revised findings")
    A("")
    A("Revision v2 of the extreme-temperature package. Every number here is "
      "recomputed; nothing is carried over from the previous findings. The original "
      "package is unchanged and remains at `outputs/extreme_temp_tests/`.")
    A("")
    A("%s" % K.PANEL_SENTENCE)
    A("")
    A("**Epistemic level: descriptive.** Period differences are differences, not "
      "trends. Agreement between definitions is agreement, not accuracy. No health "
      "outcome appears anywhere in this package.")
    A("")
    A("---")
    A("")
    A("## Part 1 - Gulf-state temperature, %s" % K.YEARS_LABEL)
    A("")
    A("### The three variables are not interchangeable")
    A("")
    su = pd.read_csv(os.path.join(K.DIR_TABLES, "summer_audit_jun_aug_jun_sep.csv"))
    js = su[su["window"] == "Jun-Sep"]
    tab = js.pivot_table(index="state", columns="variable_label",
                         values="median_across_counties_f").reset_index()
    tab["state"] = tab["state"].map(K.STATE_LABEL)
    A(K.md_table(tab, floatfmt="%.1f"))
    A("")
    A("June-September **average daily highs** run %.0f to %.0f degF. June-September "
      "**average daily lows** run %.0f to %.0f degF - below 75 degF in every state. "
      "That is ordinary for inland, northern, rural and elevated counties and is not a "
      "data-quality signal. A rule that every summer temperature must exceed 75 degF "
      "would flag the average daily low across the entire region; it is not applied "
      "here."
      % (js[js["variable"] == "Tmax"]["median_across_counties_f"].min(),
         js[js["variable"] == "Tmax"]["median_across_counties_f"].max(),
         js[js["variable"] == "Tmin"]["median_across_counties_f"].min(),
         js[js["variable"] == "Tmin"]["median_across_counties_f"].max()))
    A("")
    A("### Period differences, corrected")
    A("")
    A("The previous decadal table was computed as a median over all pooled annual "
      "county-level observations, so a county with ten qualifying years counted ten "
      "times and one with two counted twice. Recomputed with every county contributing "
      "exactly one value per period:")
    A("")
    A(K.md_table(cvr_tmax, floatfmt="%.2f"))
    A("")
    A("The point estimates move modestly. The interval is the new information: it is "
      "%.1f to %.1f degF wide, and it overlaps zero in no state but overlaps between "
      "states in every pairing, so the previous package's ordering of states by "
      "'warming' is not supported."
      % (c["ci_min_w"], c["ci_max_w"]))
    A("")
    A("### Level and difference are different quantities")
    A("")
    A("June-September remains the hottest part of the year in every state. The largest "
      "period differences are in the cool season. Both statements are true and they do "
      "not conflict: a month that changed more between two periods is not thereby "
      "hotter. Figure E4 keeps them in separate rows and shades the same months in "
      "both.")
    A("")
    A("### Slopes, reported separately from differences")
    A("")
    tr = pd.read_csv(os.path.join(K.DIR_TABLES, "trend_sensitivity.csv"))
    t = tr[(tr["series"] == "consistent_county_sample_A") & (tr["variable"] == "Tmax")]
    A("The annual state summary increased by %.2f to %.2f degF per decade across the "
      "five states under this descriptive model (Theil-Sen on the annual median across "
      "counties, consistent-county sample). This result may reflect climate change, "
      "station-network composition, data coverage, or remaining inhomogeneity and does "
      "not isolate causation."
      % (t["sen_slope_f_per_decade"].min(), t["sen_slope_f_per_decade"].max()))
    A("")
    A("---")
    A("")
    A("## Part 2 - county-specific relative warm spells")
    A("")
    A("These are **relative warm spells**, not heatwaves. The rule is year-round, "
      "applies no absolute heat condition, and cool-season days qualify. The threshold "
      "is the **county- and calendar-date-specific** historical percentile, not the "
      "percentile of the county's year-round distribution.")
    A("")
    hdr = {"short_label": "definition",
           "median_annual_classified_days": "median classified days per county-year",
           "median_annual_event_count": "median events per county-year",
           "median_event_duration_days": "median event duration (days)",
           "pct_days_june_september": "% Jun-Sep",
           "pct_days_may_and_october": "% May+Oct",
           "pct_days_november_april": "% Nov-Apr",
           "peak_month": "peak month"}
    A(K.md_table(rel[list(hdr)].rename(columns=hdr), floatfmt="%.1f"))
    A("")
    A("### The seasonal split, in three categories")
    A("")
    A("The previous package reported one number: the share outside June-September. "
      "Splitting the shoulder months out changes the reading. Across the nine "
      "definitions, June-September carries %.0f to %.0f%% of classified days, May and "
      "October carry %.0f to %.0f%%, and November-April carry %.0f to %.0f%%. The "
      "shoulder months are not a rounding detail: they are close to a fifth of all "
      "classified days, and merging them with November-April overstates how much of "
      "the signal is genuinely off-season."
      % (rel["pct_days_june_september"].min(), rel["pct_days_june_september"].max(),
         rel["pct_days_may_and_october"].min(), rel["pct_days_may_and_october"].max(),
         rel["pct_days_november_april"].min(), rel["pct_days_november_april"].max()))
    A("")
    A("### The monthly rate is not flat")
    A("")
    finite = flat[np.isfinite(flat["max_over_min_ratio"])]
    n_inf = len(flat) - len(finite)
    A("The previous package described the monthly profile as 'close to flat all year'. "
      "Under a prespecified criterion - highest-to-lowest monthly ratio at most 1.5 "
      "AND coefficient of variation at most 0.15 - **%d of %d constructs meet it**. "
      "Among the %d constructs whose quietest month is non-zero the ratio runs from "
      "%.1f to %.1f; the remaining %d have at least one month with NO classified days "
      "at all, which is the strongest possible departure from flatness. The curves are "
      "not flat and are not described as flat."
      % (int(flat["meets_flatness_criterion"].sum()), len(flat), len(finite),
         finite["max_over_min_ratio"].min(), finite["max_over_min_ratio"].max(),
         n_inf))
    A("")
    A("---")
    A("")
    A("## Part 3 - absolute daily-high gates")
    A("")
    A("80 degF and 90 degF are **absolute daily-high gates** chosen for this "
      "sensitivity test. They are not National Weather Service advisory thresholds, "
      "and a gate is not a correction: it changes the construct from a purely relative "
      "warm spell to a hybrid relative-and-absolute heat event.")
    A("")
    hdr3 = {"label": "definition", "absolute_gate_f": "gate (degF)",
            "pct_classified_days_retained": "% days retained",
            "day_level_jaccard_with_no_gate": "Jaccard vs no gate",
            "pct_days_june_september_no_gate": "% Jun-Sep, no gate",
            "pct_days_june_september_with_gate": "% Jun-Sep, with gate",
            "median_county_retention_pct": "county retention, median",
            "p10_county_retention_pct": "county retention, 10th pct",
            "p90_county_retention_pct": "county retention, 90th pct"}
    A(K.md_table(g[list(hdr3)].rename(columns=hdr3), floatfmt="%.2f"))
    A("")
    A("The 90 degF gate moves the June-September share from %.0f%% to %.0f%% and keeps "
      "%.0f%% of the classified days. The 80 degF gate keeps %.0f%% and moves the "
      "share only to %.0f%%."
      % (g[g["absolute_gate_f"] == 90]["pct_days_june_september_no_gate"].iloc[0],
         g[g["absolute_gate_f"] == 90]["pct_days_june_september_with_gate"].iloc[0],
         g[g["absolute_gate_f"] == 90]["pct_classified_days_retained"].iloc[0],
         g[g["absolute_gate_f"] == 80]["pct_classified_days_retained"].iloc[0],
         g[g["absolute_gate_f"] == 80]["pct_days_june_september_with_gate"].iloc[0]))
    A("")
    A("**The gate does not bite equally everywhere.** For the 90 degF gate the "
      "retained share runs from %.0f%% at the 10th percentile of counties to %.0f%% at "
      "the 90th. A gate redistributes exposure geographically as well as seasonally, "
      "concentrating it in the hottest counties."
      % (g[g["absolute_gate_f"] == 90]["p10_county_retention_pct"].iloc[0],
         g[g["absolute_gate_f"] == 90]["p90_county_retention_pct"].iloc[0]))
    A("")
    A("### An 80 degF absolute rule is not an extreme-heat criterion")
    A("")
    ab = summ[summ["construct_family"] == "absolute"]
    hdr2 = {"short_label": "definition",
            "median_annual_classified_days": "median classified days per county-year",
            "median_annual_event_count": "median events per county-year",
            "median_event_duration_days": "median event duration (days)",
            "classified_days_per_1000_valid": "classified days per 1,000 valid records",
            "pct_days_june_september": "% Jun-Sep"}
    A(K.md_table(ab[list(hdr2)].rename(columns=hdr2), floatfmt="%.1f"))
    A("")
    a80 = ab[ab["construct_id"] == K.abs_id(80.0, 2)].iloc[0]
    A("A daily high above 80 degF for at least two consecutive days classifies %.0f%% "
      "of every valid daily county-level observation in the record, with a median of "
      "%.0f classified days per county per year. Whatever that measures, it is not an "
      "extreme. The longest single run in the whole package is %d consecutive days."
      % (a80["classified_days_per_1000_valid"] / 10.0,
         a80["median_annual_classified_days"], int(ev["event_duration_days"].max())))
    A("")
    A("---")
    A("")
    A("## What is new in this revision, and was not visible before")
    A("")
    A("1. **A county-level spread the previous caption denied.** For %s, cumulative "
      "classified days range from %d to %d across counties, a factor of %.1f. The "
      "claim that a relative percentile rule 'flags a similar number of days "
      "everywhere by construction' is not supported."
      % (K.PRIMARY_CONSTRUCT,
         int(ann[ann["construct_id"] == K.PRIMARY_CONSTRUCT]
             .groupby("county_fips")["annual_classified_day_count"].sum().min()),
         int(ann[ann["construct_id"] == K.PRIMARY_CONSTRUCT]
             .groupby("county_fips")["annual_classified_day_count"].sum().max()),
         (ann[ann["construct_id"] == K.PRIMARY_CONSTRUCT]
          .groupby("county_fips")["annual_classified_day_count"].sum().max()
          / max(1, ann[ann["construct_id"] == K.PRIMARY_CONSTRUCT]
                .groupby("county_fips")["annual_classified_day_count"].sum()
                .replace(0, np.nan).min()))))
    A("2. **%s inverted daily records** - a daily high below the same day's daily low "
      "- of which %d have their high and low averaged over different station sets. "
      "The previous package does not check for this." % (c["n_quar"],
                                                         c["n_quar_station"]))
    A("3. **The archived thresholds do not survive a default CSV read.** %s of %s "
      "values are misparsed by the pandas default float parser, which flips "
      "classification on knife-edge county-dates." % (c["frt_bad"], c["frt_tot"]))
    A("4. **There is no external benchmark.** The only candidate is byte-identical to "
      "the project data on all %s matched records. Nothing in this project's county "
      "temperature values has been externally validated." % c["bench_n"])
    A("5. **%s events run longer than %d days** and are now audited and classified; "
      "%d are flagged station-composition-sensitive and %d imputation-sensitive."
      % ("{:,}".format(len(ev)), K.LONG_EVENT_DAYS,
         int((ev["audit_classification"] == "station_composition_sensitive").sum()),
         int((ev["audit_classification"] == "imputation_sensitive").sum())))
    A("")
    A("## Caveats worth carrying forward")
    A("")
    for r in c["risks"]:
        A("- %s" % r)
    A("")
    A("See `reports/FINAL_REPORT.md` for the full audit, the recommended primary "
      "definition and the next actions.")
    with open(os.path.join(K.DIR_REPORTS, "FINDINGS_REVISED.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    K.log("[write] reports/FINDINGS_REVISED.md")


def write_cvr(c, cvr_tmax, smp, cvr_class):
    L = []
    A = L.append
    A("# Current package against revised package")
    A("")
    A("The original package at `outputs/extreme_temp_tests/` is unmodified. Its "
      "outputs were re-executed into `current_vs_revised/reproduction/` and reproduce "
      "bit-for-bit before any comparison was made.")
    A("")
    A("## Period difference, %s to %s, average daily high temperature"
      % (K.BASE_PERIOD, K.RECENT_PERIOD))
    A("")
    A(K.md_table(cvr_tmax, floatfmt="%.2f"))
    A("")
    A("## County sample")
    A("")
    A(K.md_table(smp))
    A("")
    A("## Classification results")
    A("")
    A(K.md_table(cvr_class))
    A("")
    A("## Figure crosswalk")
    A("")
    A("| current figure | revised figure | what changed |")
    A("|---|---|---|")
    for cur, new, why in [
        ("e01_fig02_distribution_by_state.png",
         "r_fig_E2_distribution_by_state.png + r_fig_E2b_one_value_per_county.png",
         "retitled; the three conflated sources of variation stated; an equal-county "
         "alternative added"),
        ("e01_fig03_decadal_change.png", "r_fig_E3_period_comparison.png",
         "equal-county aggregation; bootstrap intervals; county counts; both samples; "
         "trend language removed; 2020-2025 labelled a six-year recent period"),
        ("e01_fig04_monthly.png", "r_fig_E4_monthly_level_and_difference.png",
         "equal-county period difference; identical warm-season shading in both rows "
         "(the current figure shades different months in each); level and difference "
         "stated as different quantities"),
        ("e03_fig05_part2_percentile_duration_grid.png",
         "r_fig_E5_percentile_duration_grid.png",
         "pooled event total replaced by the median annual county-level event count; "
         "season split three ways; 'heatwave days' renamed"),
        ("e03_fig05b_part2_agreement.png", "r_fig_E5b_agreement_jaccard.png",
         "full labels; agreement-not-accuracy and structural-nesting stated"),
        ("e03_fig06_part2_seasonality.png",
         "r_fig_E6_monthly_classification_rate.png",
         "construct-specific denominator; flatness criterion defined and evaluated; "
         "reader-facing unit language"),
        ("e03_fig07_floor_effect.png", "r_fig_E7_absolute_gate_effect.png",
         "'floor' renamed absolute daily-high gate; three-way season split; county "
         "geography of retention added; annual county-level change replaces pooled "
         "totals"),
        ("e03_fig08_absolute_vs_relative.png", "r_fig_E8_absolute_vs_relative.png",
         "annual county-level distributions replace study-period medians; the share of "
         "all valid records classified added"),
        ("e03_fig09_county_floor_effect_map.png",
         "r_fig_E9_county_geography_all_counties.png + "
         "r_fig_E9_county_geography_excluding_fully_imputed.png",
         "caption claim withdrawn and the spread measured; data-quality panel added; "
         "fully imputed counties hatched; a version excluding them added"),
        ("(none)", "r_fig_R1 to r_fig_R10",
         "current-versus-revised, sample comparison, benchmark, trend sensitivity, "
         "imputation sensitivity, event timeline, long-event audit, annual "
         "distributions, family rates, county profiles"),
    ]:
        A("| %s | %s | %s |" % (cur, new, why))
    with open(os.path.join(K.DIR_CVR, "CURRENT_VS_REVISED.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    K.log("[write] current_vs_revised/CURRENT_VS_REVISED.md")


def write_readme(c):
    L = []
    A = L.append
    A("# Extreme-temperature revision (v2)")
    A("")
    A("A corrected and audited reissue of `outputs/extreme_temp_tests/`. **The "
      "original package is not modified.**")
    A("")
    A("**Read `reports/FINDINGS_REVISED.md` first, then `reports/FINAL_REPORT.md`.**")
    A("")
    A("| directory | contents |")
    A("|---|---|")
    A("| `config/` | resolved configuration and a snapshot of the config module |")
    A("| `data_dictionary/` | variable dictionary and the revised definition registry |")
    A("| `tables/` | every published table |")
    A("| `figures/` | revised E2 to E9 plus ten new figures |")
    A("| `county_profiles/` | per-county series for the example counties |")
    A("| `event_audits/` | long-event review and per-day detail |")
    A("| `qa/` | reproduction, aggregation inventory, checksums, QA suite |")
    A("| `scripts/` | the pipeline, in run order |")
    A("| `reports/` | the findings and the full report |")
    A("| `current_vs_revised/` | the reproduction of the current package and the "
      "comparison |")
    A("")
    A("## Headline")
    A("")
    A("| question | answer |")
    A("|---|---|")
    A("| Does the current package reproduce? | yes - all %d tables and figures "
      "bit-for-bit, and %d of %d exact checks on the classification step |"
      % (c["n_repro"], c["n_verify_pass"], c["n_verify"]))
    A("| Was the 'balanced panel' balanced? | no - it required one qualifying year per "
      "period; a real minimum removes 20-45%% of it |")
    A("| Does the aggregation correction change the answer? | the point estimates move "
      "by up to %.2f degF; more importantly the interval across counties, never "
      "reported before, is %.1f to %.1f degF wide |"
      % (c["max_move"], c["ci_min_w"], c["ci_max_w"]))
    A("| Is a summer daily low below 75 degF a defect? | no - it is the ordinary case "
      "across the region |")
    A("| Is the monthly classification rate flat? | no - %d of %d constructs meet the "
      "prespecified flatness criterion |"
      % (int(pd.read_csv(os.path.join(Q, "flatness_criterion.csv"))
             ["meets_flatness_criterion"].sum()),
         len(pd.read_csv(os.path.join(Q, "flatness_criterion.csv")))))
    A("| Does a relative rule flag a similar number of days everywhere? | no - a "
      "factor of 12.7 between the highest and lowest county |")
    A("| Is there an external benchmark? | no - the only candidate is byte-identical "
      "to the project data |")
    A("")
    A("## Rebuild")
    A("")
    A("```bash")
    A("cd outputs/extreme_temperature_revision_v2/scripts")
    A("python run_revision.py            # every step in order, ~12 minutes")
    A("```")
    A("")
    A("Individual steps are listed in `run_manifest.csv`. The pipeline stops if any "
      "blocking QA test fails; it does not continue by dropping failed records or "
      "changing assumptions.")
    A("")
    A("Provenance: git `%s`, python %s, pandas %s, bootstrap seed %d."
      % (c["git"], c["prov"]["python"], c["prov"]["pandas"], K.BOOTSTRAP_SEED))
    with open(os.path.join(K.REV_ROOT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    K.log("[write] README.md")


if __name__ == "__main__":
    sys.exit(main())
