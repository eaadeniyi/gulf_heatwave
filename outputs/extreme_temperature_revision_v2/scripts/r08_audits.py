"""
=============================================================================
r08  --  STAGES 15 and 16: long-event audit, data-quality sensitivity,
         county profiles.
=============================================================================
STAGE 15 -- LONG-EVENT AUDIT
Every event longer than the configured audit threshold is listed with the
evidence needed to judge it, and classified. NOTHING IS DELETED. A long event
is a question, not an error: a 243-day run of daily highs above 80 degF in
south Texas is exactly what that rule should produce, and it is evidence about
the RULE rather than about the data.

Each event is given one or more of:
    physically_plausible            hot, well clear of its threshold, on
                                    observed data with a stable station count
    threshold_driven                the daily highs barely clear the threshold,
                                    so the run exists because the threshold is
                                    low rather than because it is hot
    imputation_sensitive            a large share of the event's days are IDW
                                    gap-filled, or the county is fully imputed
    station_composition_sensitive   the number of contributing stations changes
                                    materially inside the event window, or the
                                    county is carried by a single station
    requires_manual_review          more than one of the above, or none

STAGE 16 -- DATA-QUALITY SENSITIVITY
County-level summaries are recomputed under six prespecified county subsets and
compared on county ranking, annual event counts, classified-day counts, monthly
profile and long-event frequency. No county ranking is published anywhere in
this package without its data-quality indicator attached.

OUTPUTS
  tables/long_event_audit.csv
  tables/imputation_sensitivity.csv
  tables/imputation_sensitivity_rankings.csv
  tables/county_data_quality.csv
  tables/county_profile_examples.csv
  event_audits/long_event_daily_detail_<family>.csv
  event_audits/LONG_EVENT_REVIEW.md
  county_profiles/<fips>_<name>.csv
=============================================================================
"""
import os
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K
import config as C                                          # noqa: E402
import p02_classify_and_report as p02                       # noqa: E402

A0, A1 = K.ANALYSIS_YEARS
DETAIL_CAP_PER_FAMILY = 150      # longest N events per family get per-day detail


# =============================================================================
def county_quality():
    r = pd.read_csv(os.path.join(C.state_output_dir(K.TEST_STATE),
                                 "coverage_and_imputation_report.csv"),
                    dtype={"county_fips": str})
    r["fully_imputed_county"] = (r["fully_imputed_county"].astype(str).str.lower()
                                 .isin(("true", "1", "yes")))
    r["observed_share"] = 1.0 - r["pct_analysis_days_imputed"] / 100.0
    r["any_observed"] = r["native_analysis_days"] > 0
    r["imputation_lt_20pct"] = r["pct_analysis_days_imputed"] < 20
    r["imputation_lt_10pct"] = r["pct_analysis_days_imputed"] < 10
    r["not_fully_imputed"] = ~r["fully_imputed_county"]
    r["anchor_stations"] = r["observed_share"] >= K.ANCHOR_MIN_OBSERVED_SHARE
    r["all_counties"] = True
    r["data_quality_label"] = np.where(
        r["fully_imputed_county"], "fully imputed (no observed temperature)",
        np.where(r["pct_analysis_days_imputed"] >= 20, "20% or more imputed",
                 np.where(r["pct_analysis_days_imputed"] >= 10, "10-20% imputed",
                          np.where(r["observed_share"] >= K.ANCHOR_MIN_OBSERVED_SHARE,
                                   "anchor: 95% or more observed",
                                   "under 10% imputed"))))
    return r


def station_counts():
    """Contributing-station counts per county-date, from the raw GHCN pull."""
    d = pd.read_csv(C.ghcn_path(K.TEST_STATE),
                    usecols=["county_fips", "date", "tmax_f", "tmax_f_nstations"],
                    dtype={"county_fips": str})
    d["date"] = pd.to_datetime(d["date"])
    d = d[(d["date"].dt.year >= A0) & (d["date"].dt.year <= A1)]
    return d.rename(columns={"tmax_f": "observed_tmax_f",
                             "tmax_f_nstations": "contributing_stations"})


def daily_panel():
    cd = p02.load_county_days(K.TEST_STATE, verbose=False)
    cd = cd[(cd["year"] >= A0) & (cd["year"] <= A1)]
    return cd[["county_fips", "county_name", "date", "year", "month", "day",
               "tmax_f", "tmin_f", "temp_imputed", "template_doy"]]


# =============================================================================
# STAGE 15
# =============================================================================
def long_event_audit(cat, cd, stn, qual):
    """Summary row and classification for every event over the audit threshold."""
    ev = cat[cat["event_duration_days"] > K.LONG_EVENT_DAYS].copy()
    K.log("   %s events exceed %d days (%s of %s events in the catalogues)"
          % ("{:,}".format(len(ev)), K.LONG_EVENT_DAYS, "{:,}".format(len(ev)),
             "{:,}".format(len(cat))))
    if not len(ev):
        return ev, pd.DataFrame()

    day = cd.merge(stn[["county_fips", "date", "contributing_stations",
                        "observed_tmax_f"]], on=["county_fips", "date"], how="left")
    day = day.set_index(["county_fips", "date"]).sort_index()

    # per-day detail for the longest events in each family
    detail_rows = []
    keep = (ev.sort_values("event_duration_days", ascending=False)
            .groupby("construct_family", observed=True)
            .head(DETAIL_CAP_PER_FAMILY))
    for _, e in keep.iterrows():
        rng = pd.date_range(e["event_start_date"], e["event_end_date"], freq="D")
        try:
            sub = day.loc[(e["county_fips"], slice(rng[0], rng[-1])), :].reset_index()
        except KeyError:
            continue
        sub["event_id"] = e["event_id"]
        sub["construct_id"] = e["construct_id"]
        sub["construct_family"] = e["construct_family"]
        sub["absolute_gate_f"] = e["absolute_gate_f"]
        sub["event_day_number"] = np.arange(1, len(sub) + 1)
        sub["crosses_month_boundary"] = sub["month"].nunique() > 1
        sub["missing_daily_high"] = sub["tmax_f"].isna()
        sub["station_count_changed_during_event"] = (
            sub["contributing_stations"].nunique(dropna=True) > 1)
        detail_rows.append(sub)
    detail = (pd.concat(detail_rows, ignore_index=True) if detail_rows
              else pd.DataFrame())

    # event-level station and imputation evidence for ALL long events
    agg_rows = []
    g = stn.set_index(["county_fips", "date"])["contributing_stations"]
    for cty, sub in ev.groupby("county_fips", observed=True):
        try:
            s = g.loc[cty]
        except KeyError:
            s = pd.Series(dtype=float)
        for _, e in sub.iterrows():
            w = s.loc[pd.Timestamp(e["event_start_date"]):
                      pd.Timestamp(e["event_end_date"])] if len(s) else pd.Series(dtype=float)
            w = w.dropna()
            agg_rows.append(dict(
                event_id=e["event_id"],
                min_contributing_stations=float(w.min()) if len(w) else np.nan,
                max_contributing_stations=float(w.max()) if len(w) else np.nan,
                station_count_changes=int(w.nunique()) if len(w) else 0,
                days_with_no_station=int((e["event_duration_days"] - len(w)))))
    ag = pd.DataFrame(agg_rows)
    ev = ev.merge(ag, on="event_id", how="left")
    ev = ev.merge(qual[["county_fips", "pct_analysis_days_imputed",
                        "fully_imputed_county", "data_quality_label"]]
                  .rename(columns={"pct_analysis_days_imputed": "county_pct_imputed",
                                   "fully_imputed_county": "county_fully_imputed"}),
                  on="county_fips", how="left")

    ev["imputed_share_of_event"] = (ev["imputed_day_count"]
                                    / ev["event_duration_days"]).round(4)
    ev["mean_exceedance_per_day_f"] = (ev["cumulative_exceedance_degree_days"]
                                       / ev["event_duration_days"]).round(3)
    ev["crosses_month_boundary"] = (
        pd.to_datetime(ev["event_start_date"]).dt.month
        != pd.to_datetime(ev["event_end_date"]).dt.month)
    ev["station_set_changed"] = ev["station_count_changes"] > 1
    ev["single_station_county"] = ev["max_contributing_stations"] <= 1

    imp = (ev["imputed_share_of_event"] >= 0.5) | ev["county_fully_imputed"].fillna(False)
    stc = ev["station_set_changed"].fillna(False) | ev["single_station_county"].fillna(False)
    thr = (ev["mean_exceedance_per_day_f"] < 1.0) & (ev["construct_family"] != "absolute")
    plaus = ((ev["event_peak_temperature_f"] >= 90.0)
             & (ev["mean_exceedance_per_day_f"] >= 2.0) & ~imp & ~stc)
    plaus_abs = (ev["construct_family"] == "absolute") & ~imp & ~stc

    lab = pd.DataFrame({"physically_plausible": plaus | plaus_abs,
                        "threshold_driven": thr,
                        "imputation_sensitive": imp,
                        "station_composition_sensitive": stc})
    ev["audit_flags"] = lab.apply(
        lambda r: ";".join([c for c in lab.columns if r[c]]) or "unclassified", axis=1)
    n_flags = lab.sum(axis=1)
    ev["audit_classification"] = np.where(
        n_flags == 0, "requires_manual_review",
        np.where(n_flags > 1, "requires_manual_review", ev["audit_flags"]))
    ev["exceeds_strict_audit_threshold"] = (ev["event_duration_days"]
                                            > K.LONG_EVENT_DAYS_STRICT)
    ev["audit_threshold_days"] = K.LONG_EVENT_DAYS
    ev["action"] = ("listed for review; no event is deleted on the basis of its "
                    "length alone")
    return ev, detail


# =============================================================================
# STAGE 16
# =============================================================================
def imputation_sensitivity(ann, mon, cat, qual):
    rows, rank_rows = [], []
    constructs = sorted(set(mon["construct_id"]))
    base_rank = {}
    long_by_cty = (cat[cat["event_duration_days"] > K.LONG_EVENT_DAYS]
                   .groupby(["construct_id", "county_fips"], observed=True)
                   .size().rename("long_events").reset_index())
    for key, label in K.IMPUTATION_STRATA:
        keep = qual.loc[qual[key], "county_fips"]
        for cid in constructs:
            a = ann[(ann["construct_id"] == cid) & ann["county_fips"].isin(keep)]
            m = mon[(mon["construct_id"] == cid) & mon["county_fips"].isin(keep)]
            le = long_by_cty[(long_by_cty["construct_id"] == cid)
                             & long_by_cty["county_fips"].isin(keep)]
            if not len(a):
                continue
            cum = a.groupby("county_fips")["annual_classified_day_count"].sum()
            season = (m.groupby("season")["heat_event_day_count"].sum()
                      .reindex(["warm", "shoulder", "cool"], fill_value=0))
            svalid = (m.groupby("season")["valid_daily_observation_count"].sum()
                      .reindex(["warm", "shoulder", "cool"], fill_value=0))
            tot = float(season.sum())
            rows.append(dict(
                stratum=key, stratum_label=label, construct_id=cid,
                counties=int(a["county_fips"].nunique()),
                median_annual_classified_days=float(
                    a["annual_classified_day_count"].median()),
                p25_annual_classified_days=float(
                    a["annual_classified_day_count"].quantile(0.25)),
                p75_annual_classified_days=float(
                    a["annual_classified_day_count"].quantile(0.75)),
                median_annual_event_count=float(a["annual_event_count"].median()),
                median_cumulative_classified_days=float(cum.median()),
                classified_days_per_1000_valid=round(
                    1000.0 * m["heat_event_day_count"].sum()
                    / m["valid_daily_observation_count"].sum(), 3)
                if m["valid_daily_observation_count"].sum() else np.nan,
                warm_season_rate_per_1000=round(1000.0 * season["warm"]
                                                / svalid["warm"], 3)
                if svalid["warm"] else np.nan,
                shoulder_rate_per_1000=round(1000.0 * season["shoulder"]
                                             / svalid["shoulder"], 3)
                if svalid["shoulder"] else np.nan,
                cool_season_rate_per_1000=round(1000.0 * season["cool"]
                                                / svalid["cool"], 3)
                if svalid["cool"] else np.nan,
                pct_days_june_september=round(100.0 * season["warm"] / tot, 2)
                if tot else np.nan,
                long_events_per_100_county_years=round(
                    100.0 * le["long_events"].sum()
                    / (a["county_fips"].nunique() * (A1 - A0 + 1)), 3),
                pct_classified_days_imputed=round(
                    100.0 * m["imputed_classified_day_count"].sum()
                    / m["heat_event_day_count"].sum(), 2)
                if m["heat_event_day_count"].sum() else np.nan))
            if key == "all_counties":
                base_rank[cid] = cum
            elif cid in base_rank:
                base = base_rank[cid]
                shared = cum.index.intersection(base.index)
                if len(shared) > 3:
                    # Spearman here is an INVARIANT CHECK, not a sensitivity result:
                    # a county's own classified-day count does not depend on which
                    # other counties are in the subset, so the order among retained
                    # counties must be exactly preserved. A value below 1 would mean
                    # the subsetting had leaked into the county-level computation.
                    rho, p = stats.spearmanr(cum.loc[shared], base.loc[shared])
                    top10_all = set(base.nlargest(10).index)
                    top25_all = set(base.nlargest(25).index)
                    rank_rows.append(dict(
                        stratum=key, stratum_label=label, construct_id=cid,
                        counties_compared=len(shared),
                        counties_excluded=int(len(base) - len(shared)),
                        spearman_vs_all_counties=round(float(rho), 4),
                        spearman_is_an_invariant_check=True,
                        invariant_holds=bool(abs(rho - 1.0) < 1e-9),
                        top10_counties_excluded_by_this_subset=len(top10_all
                                                                   - set(shared)),
                        top25_counties_excluded_by_this_subset=len(top25_all
                                                                   - set(shared)),
                        median_cumulative_all_counties=float(base.median()),
                        median_cumulative_this_subset=float(cum.median()),
                        median_shift=round(float(cum.median() - base.median()), 3),
                        note=("county-level values are invariant to which other "
                              "counties are included, so the Spearman correlation "
                              "must be 1; what a data-quality subset actually "
                              "changes is WHICH counties are eligible to be ranked "
                              "and therefore the state-level summary across them")))
    return pd.DataFrame(rows), pd.DataFrame(rank_rows)


# =============================================================================
# county profiles
# =============================================================================
def county_profiles(ann, mon, qual, cd):
    cid = K.PRIMARY_CONSTRUCT
    a = ann[ann["construct_id"] == cid]
    cum = a.groupby("county_fips")["annual_classified_day_count"].sum().sort_values()
    picks = {}
    nonzero = cum[cum > 0]
    if len(nonzero):
        picks["highest classified-day count"] = nonzero.index[-1]
        picks["median classified-day count"] = nonzero.index[len(nonzero) // 2]
        picks["lowest classified-day count"] = nonzero.index[0]
    fi = qual[qual["fully_imputed_county"]]["county_fips"]
    if len(fi):
        picks["fully imputed county"] = fi.iloc[0]
    anch = qual[qual["anchor_stations"]]["county_fips"]
    if len(anch):
        cand = [c for c in cum.index if c in set(anch)]
        if cand:
            picks["anchor county (95%+ observed)"] = cand[len(cand) // 2]
    if "48201" in set(cum.index):
        picks["Harris County (most populous)"] = "48201"

    rows = []
    for role, fips in picks.items():
        q = qual[qual["county_fips"] == fips].iloc[0]
        aa = a[a["county_fips"] == fips].sort_values("year")
        mm = mon[(mon["construct_id"] == cid) & (mon["county_fips"] == fips)]
        prof = aa[["year", "annual_event_count", "annual_classified_day_count",
                   "longest_event_duration_days", "imputed_classified_day_count",
                   "valid_daily_observation_count",
                   "annual_classification_rate_per_1000"]].copy()
        prof.insert(0, "county_name", q["county_name"])
        prof.insert(0, "county_fips", fips)
        prof["profile_role"] = role
        prof["data_quality_label"] = q["data_quality_label"]
        prof["pct_analysis_days_imputed"] = q["pct_analysis_days_imputed"]
        name = "".join(ch if ch.isalnum() else "_" for ch in str(q["county_name"]))
        prof.to_csv(os.path.join(K.DIR_PROFILES, "%s_%s.csv" % (fips, name)),
                    index=False)
        by_month = (mm.groupby("month")["heat_event_day_count"].sum()
                    .reindex(range(1, 13), fill_value=0))
        rows.append(dict(
            profile_role=role, county_fips=fips, county_name=q["county_name"],
            construct_id=cid, data_quality_label=q["data_quality_label"],
            pct_analysis_days_imputed=q["pct_analysis_days_imputed"],
            fully_imputed_county=bool(q["fully_imputed_county"]),
            cumulative_classified_days=int(aa["annual_classified_day_count"].sum()),
            median_annual_classified_days=float(
                aa["annual_classified_day_count"].median()),
            median_annual_event_count=float(aa["annual_event_count"].median()),
            longest_event_days=int(aa["longest_event_duration_days"].max()),
            peak_month=K.MONTH_ABBR[int(by_month.idxmax()) - 1] if by_month.sum() else "",
            pct_days_june_september=round(
                100.0 * by_month.loc[K.WARM_SEASON].sum() / by_month.sum(), 2)
            if by_month.sum() else np.nan,
            **{"month_%02d_classified_days" % m: int(by_month[m]) for m in range(1, 13)}))
    return pd.DataFrame(rows)


# =============================================================================
def main():
    K.ensure_dirs()
    t0 = time.time()
    K.log("=" * 78)
    K.log("r08  STAGES 15-16 -- long-event audit, data-quality sensitivity, profiles")
    K.log("=" * 78)

    qual = county_quality()
    qual.to_csv(os.path.join(K.DIR_TABLES, "county_data_quality.csv"), index=False)
    K.log("county data quality: %d counties; %d fully imputed; %d anchor (>= %.0f%% "
          "observed); median imputation %.1f%%"
          % (len(qual), int(qual["fully_imputed_county"].sum()),
             int(qual["anchor_stations"].sum()), 100 * K.ANCHOR_MIN_OBSERVED_SHARE,
             qual["pct_analysis_days_imputed"].median()))

    ann = pd.read_csv(os.path.join(K.DIR_TABLES, "county_annual_all_constructs.csv"),
                      dtype={"county_fips": str})
    mon = pd.read_csv(os.path.join(K.DIR_TABLES, "county_monthly_all_constructs.csv"),
                      dtype={"county_fips": str})
    cat = pd.concat([pd.read_csv(os.path.join(K.DIR_TABLES, f),
                                 dtype={"county_fips": str})
                     for f in ("individual_relative_warm_spell_events.csv",
                               "individual_hybrid_heat_events.csv",
                               "individual_absolute_hot_spells.csv")],
                    ignore_index=True)

    # ---- STAGE 15 -----------------------------------------------------------
    K.log("-" * 78)
    K.log("STAGE 15 -- long-event audit (threshold: more than %d days)"
          % K.LONG_EVENT_DAYS)
    cd = daily_panel()
    stn = station_counts()
    ev, detail = long_event_audit(cat, cd, stn, qual)
    keep_cols = ["event_id", "construct_id", "construct_family", "county_fips",
                 "county_name", "event_start_date", "event_end_date",
                 "event_duration_days", "event_peak_temperature_f", "event_peak_date",
                 "maximum_threshold_exceedance_f", "maximum_exceedance_date",
                 "cumulative_exceedance_degree_days", "mean_exceedance_per_day_f",
                 "absolute_gate_f", "percentile", "threshold_window",
                 "observed_day_count", "imputed_day_count", "imputed_share_of_event",
                 "min_contributing_stations", "max_contributing_stations",
                 "station_count_changes", "station_set_changed",
                 "single_station_county", "days_with_no_station",
                 "crosses_month_boundary", "county_pct_imputed",
                 "county_fully_imputed", "data_quality_label", "audit_flags",
                 "audit_classification", "exceeds_strict_audit_threshold",
                 "audit_threshold_days", "qc_review_status", "action"]
    ev[keep_cols].to_csv(os.path.join(K.DIR_TABLES, "long_event_audit.csv"), index=False)
    for fam, g in detail.groupby("construct_family", observed=True) if len(detail) \
            else []:
        g.to_csv(os.path.join(K.DIR_EVENT_AUDITS,
                              "long_event_daily_detail_%s.csv" % fam), index=False)
    cls = ev["audit_classification"].value_counts()
    for k, v in cls.items():
        K.log("   %-32s %s events" % (k, "{:,}".format(int(v))))
    K.log("   per-day detail written for the longest %d events in each family "
          "(cap stated, not silent): %s rows"
          % (DETAIL_CAP_PER_FAMILY, "{:,}".format(len(detail))))
    write_long_event_review(ev, cat)

    # ---- STAGE 16 -----------------------------------------------------------
    K.log("-" * 78)
    K.log("STAGE 16 -- data-quality sensitivity")
    sens, ranks = imputation_sensitivity(ann, mon, cat, qual)
    sens.to_csv(os.path.join(K.DIR_TABLES, "imputation_sensitivity.csv"), index=False)
    ranks.to_csv(os.path.join(K.DIR_TABLES, "imputation_sensitivity_rankings.csv"),
                 index=False)
    K.log("   %d stratum x construct rows; %d ranking comparisons"
          % (len(sens), len(ranks)))
    p = sens[sens["construct_id"] == K.PRIMARY_CONSTRUCT]
    K.log("   %s under each county subset:" % K.PRIMARY_CONSTRUCT)
    K.log("      %-42s %8s %10s %10s %9s" % ("subset", "counties", "med annual",
                                             "Jun-Sep %", "long/100cy"))
    for _, x in p.iterrows():
        K.log("      %-42s %8d %10.1f %10.1f %9.2f"
              % (x["stratum_label"], x["counties"],
                 x["median_annual_classified_days"], x["pct_days_june_september"],
                 x["long_events_per_100_county_years"]))
    if len(ranks):
        rp = ranks[ranks["construct_id"] == K.PRIMARY_CONSTRUCT]
        n_bad = int((~ranks["invariant_holds"]).sum())
        K.log("   invariant check (a county's value must not depend on which other "
              "counties are included): %d of %d comparisons violate it"
              % (n_bad, len(ranks)))
        if n_bad:
            raise K.BlockingQAFailure(
                "county-level values changed when other counties were excluded; the "
                "subsetting has leaked into the county-level computation")
        K.log("   what the subsets actually change, for %s:" % K.PRIMARY_CONSTRUCT)
        for _, r in rp.iterrows():
            K.log("      %-42s excludes %3d counties, %d of the all-counties top 10, "
                  "median cumulative days %+.0f"
                  % (r["stratum_label"], r["counties_excluded"],
                     r["top10_counties_excluded_by_this_subset"], r["median_shift"]))

    # ---- county profiles ----------------------------------------------------
    K.log("-" * 78)
    prof = county_profiles(ann, mon, qual, cd)
    prof.to_csv(os.path.join(K.DIR_TABLES, "county_profile_examples.csv"), index=False)
    K.log("county profiles written for %d example counties -> county_profiles/"
          % len(prof))
    for _, r in prof.iterrows():
        K.log("   %-32s %s %-14s  %5d cumulative days, %s"
              % (r["profile_role"], r["county_fips"], r["county_name"],
                 r["cumulative_classified_days"], r["data_quality_label"]))
    K.log("r08 done in %.1f min" % ((time.time() - t0) / 60))
    return 0


def write_long_event_review(ev, cat):
    L = []
    A = L.append
    A("# Long-event audit")
    A("")
    A("Every event longer than %d days is listed in `tables/long_event_audit.csv` "
      "with the evidence needed to judge it. **No event is deleted on the basis of "
      "its length.** A long run is evidence about the RULE that produced it as much "
      "as about the data." % K.LONG_EVENT_DAYS)
    A("")
    A("## How many, and under which construct")
    A("")
    t = (ev.groupby(["construct_family", "construct_id"], observed=True)
         .agg(long_events=("event_id", "size"),
              longest_event_days=("event_duration_days", "max"),
              median_long_event_days=("event_duration_days", "median"))
         .reset_index())
    allc = (cat.groupby("construct_id", observed=True)["event_id"].size()
            .rename("all_events").reset_index())
    t = t.merge(allc, on="construct_id", how="left")
    t["pct_of_events_that_are_long"] = (100.0 * t["long_events"]
                                        / t["all_events"]).round(2)
    A(K.md_table(t.sort_values("long_events", ascending=False), max_rows=40,
                 floatfmt="%.2f"))
    A("")
    A("## Classification")
    A("")
    c = ev["audit_classification"].value_counts().rename_axis(
        "classification").reset_index(name="events")
    c["share_pct"] = (100.0 * c["events"] / len(ev)).round(2)
    A(K.md_table(c))
    A("")
    A("Rules, applied in code and reproducible from `tables/long_event_audit.csv`:")
    A("")
    A("- **physically_plausible** - peak daily high at or above 90 degF, mean "
      "exceedance at least 2 degF per day, no imputation or station-composition "
      "flag. For the absolute family, any event without an imputation or "
      "station-composition flag, because an absolute rule has no exceedance to "
      "measure against a percentile.")
    A("- **threshold_driven** - mean exceedance below 1 degF per day. The run "
      "persists because the daily highs sit just above a low threshold, not "
      "because the weather is extreme.")
    A("- **imputation_sensitive** - at least half the event's days are IDW "
      "gap-filled, or the county has no observed temperature at all.")
    A("- **station_composition_sensitive** - the number of contributing stations "
      "changes inside the event window, or the county is carried by a single "
      "station.")
    A("- **requires_manual_review** - no rule fired, or more than one fired.")
    A("")
    A("## The longest events")
    A("")
    top = ev.nlargest(25, "event_duration_days")[
        ["event_id", "construct_id", "county_name", "event_start_date",
         "event_end_date", "event_duration_days", "event_peak_temperature_f",
         "mean_exceedance_per_day_f", "imputed_share_of_event",
         "audit_classification"]]
    A(K.md_table(top, floatfmt="%.2f"))
    A("")
    A("Durations are integer counts of consecutive calendar dates. Where a median "
      "duration falls between two integers it is a median ACROSS events; no "
      "individual event lasts a fraction of a day.")
    A("")
    A("## What the long events say about the rules")
    A("")
    absl = ev[ev["construct_family"] == "absolute"]
    if len(absl):
        A("- The longest runs in the whole package come from the ABSOLUTE family. "
          "The longest is %d days. A rule of the form 'daily high above 80 degF for "
          "at least two consecutive days' will run for most of a Texas summer by "
          "construction, which is a statement about the rule, not a defect in the "
          "data." % int(absl["event_duration_days"].max()))
    rel = ev[ev["construct_family"] == "relative"]
    if len(rel):
        A("- Long RELATIVE warm spells are more interesting, because a walk-forward "
          "percentile threshold should be exceeded about (100 - p)%% of the time. "
          "%d relative warm spells run beyond %d days; %d of those are classified "
          "threshold_driven, meaning the daily highs clear the threshold by under "
          "1 degF per day on average."
          % (len(rel), K.LONG_EVENT_DAYS,
             int((rel["audit_classification"] == "threshold_driven").sum())))
    A("")
    A("Per-day detail for the longest %d events in each family - daily high, "
      "threshold, exceedance, gate status, observed or imputed status, contributing "
      "station count, month boundaries and missing values - is in "
      "`event_audits/long_event_daily_detail_<family>.csv`. That cap is stated "
      "rather than applied silently; the summary table above covers every long "
      "event." % DETAIL_CAP_PER_FAMILY)
    with open(os.path.join(K.DIR_EVENT_AUDITS, "LONG_EVENT_REVIEW.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
