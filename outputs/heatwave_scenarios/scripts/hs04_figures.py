"""
=============================================================================
hs04_figures.py  --  figures for the heatwave-definition scenario package.
=============================================================================
Every caption states what the figure does and does NOT support, following the
plan's reporting-language table. In particular: EHF appears only in its own
figures or clearly separated panels (its assessment dates summarise a trailing
3-day thermal period, not a single day), the Tmax+RHmax construct is always
labelled a synthetic nonconcurrent envelope, and pooled cross-county quantities
are labelled QA.
=============================================================================
"""
import os, sys
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hs00_config as H

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FAM_COLOR = {"ehf": "#8172B3", "tmax": "#C44E52", "hiproxy": "#4C72B0", "hixenv": "#DD8452"}


def log(*a):
    print(*a, flush=True)


def save(fig, name, note=None):
    if note:
        # reserve space below the axes first, then place the note in it -- writing at
        # y=0.005 without doing this overlaps the x-axis label
        fig.subplots_adjust(bottom=0.20)
        fig.text(0.01, 0.012, note, fontsize=7, color="#555", wrap=True, va="bottom")
    p = os.path.join(H.FIGURES_DIR, name)
    fig.savefig(p, bbox_inches="tight", facecolor="white", dpi=120)
    plt.close(fig)
    log("   [fig] %s" % name)


# =============================================================================
# fig01 -- EHF component time series, the 3 PRESELECTED counties
# =============================================================================
def fig01_ehf_components(dv):
    counties = H.EXAMPLE_COUNTIES
    year = 2023
    fig, axes = plt.subplots(len(counties), 1, figsize=(13, 3.3 * len(counties)), sharex=False)
    for ax, c in zip(np.atleast_1d(axes), counties):
        g = dv[(dv["county_fips"] == c["county_fips"]) & (dv["year"] == year)].sort_values("date")
        ax.plot(g["date"], g["dmt_c"], lw=0.7, color="#999", label="daily mean temp (DMT, °C)")
        ax.plot(g["date"], g["dmt_3day_mean_c"], lw=1.6, color="#C44E52", label="3-day mean DMT")
        ax.plot(g["date"], g["dmt_prior30_mean_c"], lw=1.4, color="#4C72B0",
                label="prior 30-day mean (disjoint)")
        if g["t95_c_fixed"].notna().any():
            ax.axhline(g["t95_c_fixed"].iloc[0], ls="--", lw=1.1, color="k",
                       label="T95 (fixed 1979-2014)")
        ax2 = ax.twinx()
        ax2.fill_between(g["date"], 0, g["ehf_c2_fixed"].clip(lower=0), color="#8172B3", alpha=0.35,
                        label="EHF (°C², positive only)")
        ax2.set_ylabel("EHF (°C²)", color="#8172B3", fontsize=8)
        ax2.tick_params(axis="y", labelcolor="#8172B3", labelsize=7)
        ax.set_title("%s County (%s) — %d" % (c["county_name"], c["region"], year),
                     fontsize=10, fontweight="bold")
        ax.set_ylabel("°C", fontsize=8)
        ax.tick_params(labelsize=7)
        if c is counties[0]:
            h1, l1 = ax.get_legend_handles_labels()
            h2, l2 = ax2.get_legend_handles_labels()
            ax.legend(h1 + h2, l1 + l2, fontsize=7, ncol=5, loc="upper left")
    fig.suptitle("Figure 1  EHF components, fixed-baseline (1979–2014), %d" % year,
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig01_ehf_component_timeseries.png",
         "Counties preselected on geographic/climate criteria BEFORE any result was computed "
         "(one Gulf Coast humid, one north-central urban, one far-west arid) — not chosen for a "
         "dramatic episode. EHF>0 occurs exactly when EHIsig>0; the acclimatisation term scales "
         "magnitude, not occurrence. A positive value on date d summarises the 3-day period [d-2, d].")


# =============================================================================
# fig02 -- seasonality: the headline contrast
# =============================================================================
def fig02_seasonality(qa):
    d = qa.sort_values(["family", "jun_sep_classified_date_share_QA"])
    fig, ax = plt.subplots(figsize=(11, 9))
    y = np.arange(len(d))
    ax.barh(y, d["jun_sep_classified_date_share_QA"], color=[FAM_COLOR[f] for f in d["family"]],
            label="Jun–Sep")
    ax.barh(y, d["may_oct_classified_date_share_QA"],
            left=d["jun_sep_classified_date_share_QA"], color="#BBBBBB", label="May + Oct")
    ax.barh(y, d["nov_apr_classified_date_share_QA"],
            left=d["jun_sep_classified_date_share_QA"] + d["may_oct_classified_date_share_QA"],
            color="#5A5A5A", label="Nov–Apr")
    ax.set_yticks(y)
    ax.set_yticklabels(d["construct_id"], fontsize=7.5)
    ax.set_xlabel("% of classified dates (QA: pooled across counties and years)")
    ax.set_xlim(0, 100)
    ax.legend(fontsize=8, loc="lower right")
    ax.set_title("Figure 2  When do classified dates fall?\nEHF concentrates in Jun–Sep; the "
                 "year-round relative-percentile constructs do not", fontsize=12, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig02_seasonality_by_construct.png",
         "Shares are QA quantities pooled across counties and years, not per-county averages. "
         "EHF uses an ALL-CALENDAR-DAY T95, so only genuinely hot days clear it; the percentile "
         "constructs use a day-of-year-specific threshold, which a warm winter day can exceed. "
         "The Tmax+RHmax envelope is a synthetic nonconcurrent construct, not observed exposure.")


# =============================================================================
# fig03 -- percentile sweeps, by family
# =============================================================================
def fig03_percentile_sweeps(qa, reg):
    r = reg[["construct_id", "family", "percentile", "qc_tier", "season_rule"]]
    d = qa.merge(r, on=["construct_id", "family"], how="left", suffixes=("", "_r"))
    d = d[(d["season_rule"] == "year_round") & d["percentile"].notna()]
    fams = [("tmax", "Tmax (dry-bulb)"), ("hiproxy", "Tmax+RHmin proxy"),
            ("hixenv", "Tmax+RHmax synthetic envelope")]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    for ax, (fam, title) in zip(axes, fams):
        sub = d[d["family"] == fam]
        for tier, style in (("n/a", "-o"), ("RAW", "-o"), ("CONFEXCL", "--s"), ("PROBEXCL", ":^")):
            s = sub[sub["qc_tier"] == tier].sort_values("percentile")
            if not len(s):
                continue
            ax.plot(s["percentile"], s["classified_date_count_QA"], style,
                    color=FAM_COLOR[fam], alpha=0.85 if tier in ("n/a", "RAW") else 0.55,
                    label=("no QC tier" if tier == "n/a" else tier))
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.set_xlabel("percentile")
        ax.set_ylabel("classified dates (QA pooled)")
        ax.legend(fontsize=7.5)
        ax.grid(alpha=0.25)
    fig.suptitle("Figure 3  Percentile sweep by construct family (year-round runs only)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig03_percentile_sweeps.png",
         "Pooled counts are QA quantities. Duration is held at its family's value (Tmax ≥3 days; "
         "the two humidity families ≥2 days), so the three panels are NOT matched to each other — "
         "for the metric contrast at matched settings see Figure 5.")


# =============================================================================
# fig04 -- the 21x21 year-round agreement matrix (EHF deliberately absent)
# =============================================================================
def fig04_agreement_matrix():
    p = os.path.join(H.TABLES_DIR, "agreement_jaccard_yearround_21x21.csv")
    M = pd.read_csv(p, index_col=0)
    fig, ax = plt.subplots(figsize=(12, 10))
    im = ax.imshow(M.to_numpy(), cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(len(M)))
    ax.set_xticklabels(M.columns, rotation=90, fontsize=6.5)
    ax.set_yticks(range(len(M)))
    ax.set_yticklabels(M.index, fontsize=6.5)
    fig.colorbar(im, ax=ax, shrink=0.75, label="Jaccard (common-eligibility)")
    ax.set_title("Figure 4  Day-level agreement, 21 year-round ordinary constructs\n"
                 "EHF is NOT in this matrix (its dates represent 3-day periods)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig04_agreement_jaccard_yearround_21x21.png",
         "Each cell uses ITS OWN pair's common-eligible date universe; the Jaccard denominator is "
         "the union of positive classifications within that universe, not the universe size. "
         "Agreement is not accuracy — nothing here observes a true heat day. Season-restricted "
         "and PROBEXCL sensitivity runs are excluded (differing eligibility would masquerade as "
         "disagreement); EHF is reported separately in ehf_cross_family_overlap.csv.")


# =============================================================================
# fig05 -- the matched metric comparison (the metric-isolating result)
# =============================================================================
def fig05_matched_metric():
    m = pd.read_csv(os.path.join(H.TABLES_DIR, "matched_metric_comparison.csv"))
    pct = [85, 90, 95]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    axes[0].plot(pct, m["jaccard_common_eligibility"], "-o", color="#4C72B0", lw=2)
    axes[0].set_xticks(pct)
    axes[0].set_xlabel("percentile (duration and window matched at ≥2 days, w15)")
    axes[0].set_ylabel("Jaccard (common-eligibility)")
    axes[0].set_ylim(0, 1)
    axes[0].grid(alpha=0.25)
    axes[0].set_title("Metric agreement falls as the threshold rises", fontsize=10, fontweight="bold")
    for x, y in zip(pct, m["jaccard_common_eligibility"]):
        axes[0].annotate("%.3f" % y, (x, y), textcoords="offset points", xytext=(0, 8), fontsize=8)

    w = 0.35
    x = np.arange(len(pct))
    axes[1].bar(x - w / 2, m["n_A_only_positive"], w, label="Tmax only", color="#C44E52")
    axes[1].bar(x + w / 2, m["n_B_only_positive"], w, label="Tmax+RHmin proxy only", color="#4C72B0")
    axes[1].bar(x, m["n_classified_by_both"], w * 0.5, label="both", color="#55A868")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(["P%d" % p for p in pct])
    axes[1].set_ylabel("classified dates")
    axes[1].legend(fontsize=8)
    axes[1].set_title("Where they disagree", fontsize=10, fontweight="bold")
    fig.suptitle("Figure 5  Metric-isolating comparison: Tmax vs Tmax+RHmin proxy\n"
                 "percentile, duration and window matched — metric is the only axis that differs",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig05_matched_metric_comparison.png",
         "Computed on the pairwise-common eligible calendar (the proxy excludes confirmed humidity "
         "artifacts that Tmax legitimately retains). The metric-isolating claim applies to DAILY "
         "classification only; event-level differences are not claimed to isolate metric choice. "
         "The proxy pairs two daily extrema that often occur in the warmer part of the day but are "
         "NOT verified as concurrent.")


# =============================================================================
# fig06 -- EHF: fixed vs walk-forward, and cross-family overlap
# =============================================================================
def fig06_ehf(dv, ehf_summary):
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))

    an = dv[(dv["year"] >= H.ANALYSIS_YEARS[0]) & (dv["year"] <= H.ANALYSIS_YEARS[1])]
    for col, lab, color in (("ehf_c2_fixed", "fixed 1979–2014 (benchmark)", "#8172B3"),
                            ("ehf_c2_wf", "walk-forward (candidate)", "#DD8452")):
        pos = an.loc[an[col] > 0, col]
        axes[0].hist(pos, bins=60, range=(0, 60), histtype="step", lw=1.8, color=color, label=lab)
    axes[0].set_xlabel("EHF (°C²) on positive days")
    axes[0].set_ylabel("county-days")
    axes[0].set_yscale("log")
    axes[0].legend(fontsize=8)
    axes[0].set_title("EHF magnitude, both baselines", fontsize=10, fontweight="bold")

    counts = an.groupby("month")[["ehf_c2_fixed", "ehf_c2_wf"]].apply(lambda g: (g > 0).sum())
    idx = np.arange(1, 13)
    axes[1].bar(idx - 0.2, counts["ehf_c2_fixed"].reindex(idx).fillna(0), 0.4,
                color="#8172B3", label="fixed")
    axes[1].bar(idx + 0.2, counts["ehf_c2_wf"].reindex(idx).fillna(0), 0.4,
                color="#DD8452", label="walk-forward")
    axes[1].set_xticks(idx)
    axes[1].set_xticklabels(MONTHS, fontsize=7.5)
    axes[1].set_ylabel("positive-EHF assessment dates")
    axes[1].legend(fontsize=8)
    axes[1].set_title("Positive-EHF dates by month", fontsize=10, fontweight="bold")

    e = pd.read_csv(os.path.join(H.TABLES_DIR, "ehf_cross_family_overlap.csv"))
    for i, (eid, g) in enumerate(e.groupby("ehf_construct")):
        g = g.sort_values("jaccard_common_eligibility")
        axes[2].barh(np.arange(len(g)) + i * 0.4, g["jaccard_common_eligibility"], 0.38,
                     label=eid, alpha=0.85)
    axes[2].set_yticks([])
    axes[2].set_xlabel("assessment-date Jaccard vs each ordinary construct")
    axes[2].legend(fontsize=7)
    axes[2].set_title("EHF vs ordinary definitions\n(reported separately, never in the 21×21)",
                      fontsize=10, fontweight="bold")

    fig.suptitle("Figure 6  Excess Heat Factor: magnitude, seasonality, and overlap with ordinary constructs",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig06_ehf_overview.png",
         "EHF units are °C² (the clamp's 1 is 1°C), never a Fahrenheit temperature. Occurrence is "
         "determined by EHIsig; the acclimatisation term affects magnitude and accumulated severity "
         "only. The fixed-baseline variant is an ADAPTED benchmark (BoM specifications use 1971–2000 "
         "or 1985–2014; neither matches this project's 1979–2014). Panel 3's Jaccard compares an "
         "assessment-date label against ordinary single-day classifications — not an equivalent unit.")


# =============================================================================
# fig07 -- leave-one-baseline-year-out threshold sensitivity
# =============================================================================
def fig07_loyo():
    l = pd.read_csv(os.path.join(H.TABLES_DIR, "threshold_loyo_sensitivity.csv"))
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8))
    for cid, g in l.groupby("construct_id"):
        axes[0].plot(g["dropped_baseline_year"], g["threshold_max_abs_diff_f"], "-o", ms=3, label=cid)
        axes[1].plot(g["dropped_baseline_year"], g["final_classified_day_change_count"], "-o", ms=3,
                     label=cid)
    axes[0].set_xlabel("dropped baseline year")
    axes[0].set_ylabel("max |threshold difference| (°F)")
    axes[0].set_title("Threshold movement", fontsize=10, fontweight="bold")
    axes[0].legend(fontsize=6.5)
    axes[0].grid(alpha=0.25)
    axes[1].set_xlabel("dropped baseline year")
    axes[1].set_ylabel("classified dates changed (in frozen windows)")
    axes[1].set_title("Downstream classification change", fontsize=10, fontweight="bold")
    axes[1].legend(fontsize=6.5)
    axes[1].grid(alpha=0.25)
    fig.suptitle("Figure 7  Leave-one-baseline-year-out sensitivity, 3 preselected counties",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig07_threshold_loyo_sensitivity.png",
         "Each point drops ONE baseline year, recomputes the threshold, reclassifies the entire "
         "annual sequence (event qualification depends on adjacent dates), then extracts the changes "
         "falling inside the four frozen date windows. Zero change is an acceptable, reported "
         "empirical result — this figure measures whether one historical year controls a threshold, "
         "and does not require that it does.")


def run(state="TX"):
    log("[hs04] loading ...")
    dv = pd.read_csv(os.path.join(H.TABLES_DIR, "_derived_variables_%s.csv.gz" % state),
                     usecols=["county_fips", "date", "year", "month", "dmt_c", "dmt_3day_mean_c",
                              "dmt_prior30_mean_c", "t95_c_fixed", "ehf_c2_fixed", "ehf_c2_wf"],
                     dtype={"county_fips": str})
    dv["date"] = pd.to_datetime(dv["date"])
    qa = pd.read_csv(os.path.join(H.TABLES_DIR, "scenario_summary_QA.csv"))
    reg = pd.read_csv(os.path.join(H.TABLES_DIR, "scenario_registry.csv"))
    ehf_summary = pd.read_csv(os.path.join(H.TABLES_DIR, "ehf_summary.csv"))

    fig01_ehf_components(dv)
    fig02_seasonality(qa)
    fig03_percentile_sweeps(qa, reg)
    fig04_agreement_matrix()
    fig05_matched_metric()
    fig06_ehf(dv, ehf_summary)
    fig07_loyo()
    log("[hs04] done")


if __name__ == "__main__":
    run()
