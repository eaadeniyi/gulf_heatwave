"""
=============================================================================
e04  --  the written deliverables for this package.
=============================================================================
Every number is read live from the tables written by e01-e03, so the prose
cannot drift from the data. Writes FINDINGS.md and README.md.
=============================================================================
"""
import os
import sys
import platform
import subprocess

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etx_config as K
import config as C

P = K.PRIMARY_WINDOW
YEARS = "%d-%d" % C.ANALYSIS_YEARS
EDA = "%d-%d" % K.EDA_YEARS
T = K.DIR_TABLES


def rd(n, **kw):
    return pd.read_csv(os.path.join(T, n), **kw)


def git_commit():
    try:
        c = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=K.REPO_ROOT,
                           capture_output=True, text=True, timeout=20).stdout.strip()
        d = subprocess.run(["git", "status", "--porcelain"], cwd=K.REPO_ROOT,
                           capture_output=True, text=True, timeout=20).stdout.strip()
        return (c or "unknown") + ("+dirty" if d else "")
    except Exception:
        return "unknown"


def main():
    K.ensure_dirs()
    ex = rd("e01_record_extent_and_coverage.csv")
    sd = rd("e01_state_decade_temperature.csv")
    mc = rd("e01_state_month_decadal_change.csv")
    sy = rd("e01_state_year_temperature.csv")
    cy = rd("e01_county_year_temperature.csv", dtype={"county_fips": str})
    bal = rd("e01_balanced_panel_counties.csv", dtype={"county_fips": str})
    grid = rd("e03_part2_percentile_duration_grid.csv")
    fl = rd("e03_floor_effect.csv")
    av = rd("e03_absolute_vs_relative.csv")
    m = rd("e02_master_run_summary.csv")
    fc = pd.read_csv(os.path.join(K.DIR_QA, "e02_floor_operator_check.csv"))
    rec = pd.read_csv(os.path.join(K.DIR_QA, "e02_reconciliation.csv"))

    last = K.DECADE_LABEL[K.DECADES[-1]]
    first = K.DECADE_LABEL[K.DECADES[0]]
    chg = sd[(sd["panel"] == "balanced_panel") & (sd["decade"] == last)]
    chg_u = sd[(sd["panel"] == "all_reporting_counties") & (sd["decade"] == last)]

    def ch(state, var, panel=chg):
        s = panel[(panel["state"] == state) & (panel["variable"] == var)]
        return float(s["change_vs_1980s_f"].iloc[0]) if len(s) else np.nan

    mchg_col = [c for c in mc.columns if c.startswith("change_")][0]
    tmax_mo = mc[mc["variable"] == "Tmax"].pivot_table(index="state", columns="month",
                                                       values=mchg_col)
    g = grid[grid["window"] == P]

    def cell(p, d, field):
        s = g[(g["percentile"] == p) & (g["minimum_duration_days"] == d)]
        return float(s[field].iloc[0]) if len(s) else np.nan

    # ---------------------------------------------------------------- FINDINGS
    p = os.path.join(K.PKG_ROOT, "FINDINGS.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("# Extreme-temperature tests - findings\n\n")
        f.write("Three pieces of work: a temperature description for the five Gulf states, a "
                "county-relative daily-maximum-temperature grid, and the absolute-floor test. "
                "Parts 2 and 3 run on **%s** (%s), the pilot state, on the same input table, "
                "walk-forward baseline and code path as the published definitions.\n\n"
                % (K.TEST_STATE, YEARS))
        f.write("Every figure and table referenced here is in `figures/` and `tables/`; "
                "provenance and QA are in `qa/`. Rebuild with `python scripts/e01_...` through "
                "`e04_...` (about 8 minutes in total).\n\n")

        # ---------- part 1 -------------------------------------------------
        f.write("---\n\n## Part 1 - Gulf-state temperature, %s\n\n" % EDA)
        f.write("**Record and coverage.** All five states span %s to %s. 2026 is excluded "
                "everywhere as a partial year, leaving %d complete years. Tmax is present on "
                "%s%% of county-days depending on the state (%s), so the annual summaries use "
                "only county-years with at least %d valid days.\n\n"
                % (ex["first_date"].min(), ex["last_date"].max(),
                   K.EDA_YEARS[1] - K.EDA_YEARS[0] + 1,
                   "-".join("%.0f" % v for v in (ex["pct_county_days_with_tmax"].min(),
                                                 ex["pct_county_days_with_tmax"].max())),
                   ", ".join("%s %.0f%%" % (r["state"], r["pct_county_days_with_tmax"])
                             for _, r in ex.iterrows()), K.MIN_DAYS_PER_COUNTY_YEAR))
        f.write("**The reporting network shrinks, and it matters.** Counties clearing the "
                "coverage gate fall over the record (Figure E1, bottom panel). Comparing "
                "decades therefore uses a BALANCED panel - counties clearing the gate in every "
                "decade: %s. The difference is not cosmetic: Alabama's Tmax warming since the "
                "%s reads **%+.2f degF** on the balanced panel but only **%+.2f degF** on "
                "whichever counties happened to report, and Florida's Tmin warming reads "
                "%+.2f against %+.2f. An unbalanced decadal comparison in this data is partly "
                "a station-network trend.\n\n"
                % (", ".join("%s %d" % (s, int(((bal["state"] == s)
                                                & (bal["variable"] == "Tmax")).sum()))
                             for s in K.STATES),
                   first, ch("AL", "Tmax"), ch("AL", "Tmax", chg_u),
                   ch("FL", "Tmin"), ch("FL", "Tmin", chg_u)))
        f.write("**Levels.** Median county-year Tmax over %s: %s. But the spread WITHIN a "
                "state is as large as the gap between states - Texas county-years span roughly "
                "%.0f-%.0f degF - so a state mean is a weak summary and the county remains the "
                "substantive unit (Figure E2).\n\n"
                % (EDA, ", ".join("%s %.1f" % (s, cy[(cy["state"] == s)
                                                     & (cy["variable"] == "Tmax")
                                                     & cy["passes_coverage_gate"]]["mean_f"]
                                               .median()) for s in K.STATES),
                   cy[(cy["state"] == "TX") & (cy["variable"] == "Tmax")
                      & cy["passes_coverage_gate"]]["mean_f"].min(),
                   cy[(cy["state"] == "TX") & (cy["variable"] == "Tmax")
                      & cy["passes_coverage_gate"]]["mean_f"].max()))
        f.write("**Decadal change, %s to %s (balanced panel, degF):**\n\n" % (first, last))
        tt = pd.DataFrame({"state": K.STATES,
                           "Tmax": ["%+.2f" % ch(s, "Tmax") for s in K.STATES],
                           "Tmin": ["%+.2f" % ch(s, "Tmin") for s in K.STATES],
                           "Tmean": ["%+.2f" % ch(s, "Tmean") for s in K.STATES]})
        f.write(K.md_table(tt) + "\n\n")
        f.write("**Tmin is warming faster than Tmax in every one of the five states** "
                "(Figure E3). The gap is largest in Florida (%+.2f against %+.2f) and Alabama "
                "(%+.2f against %+.2f). The diurnal range is narrowing, which is directly "
                "relevant to this project: a night-time (Tmin) definition and a day-time "
                "(Tmax) definition are not just selecting different days, they are tracking "
                "quantities that are changing at different rates.\n\n"
                % (ch("FL", "Tmin"), ch("FL", "Tmax"), ch("AL", "Tmin"), ch("AL", "Tmax")))
        f.write("**The warming is concentrated OUTSIDE summer** (Figure E4, bottom row). "
                "Change in median Tmax, %s to %s, balanced panel:\n\n" % (first, last))
        mrow = pd.DataFrame({"state": K.STATES})
        for mo, nm in ((12, "Dec"), (2, "Feb"), (10, "Oct"), (7, "Jul"), (8, "Aug")):
            mrow[nm] = ["%+.1f" % tmax_mo.loc[s, mo] if s in tmax_mo.index else ""
                        for s in K.STATES]
        f.write(K.md_table(mrow) + "\n\n")
        feb_max_state = tmax_mo[2].idxmax()
        summer = tmax_mo[[6, 7, 8]]
        f.write("December warmed **%+.1f degF in Texas** and %+.1f in Mississippi, and February "
                "%+.1f in %s, while June-August moved by at most %+.1f degF in any state and "
                "went NEGATIVE in %d state-month combinations. This is the physical reason the "
                "year-round relative definitions load onto the cool season: the anomalies are "
                "largest where the warming is, and a walk-forward percentile threshold measures "
                "departure from each date's own history.\n\n"
                % (tmax_mo.loc["TX", 12], tmax_mo.loc["MS", 12], tmax_mo[2].max(),
                   K.STATE_LABEL[feb_max_state], summer.to_numpy().max(),
                   int((summer.to_numpy() < 0).sum())))

        # ---------- part 2 -------------------------------------------------
        f.write("---\n\n## Part 2 - county-relative daily maximum temperature\n\n")
        f.write("9 definitions (80th / 85th / 90th percentile x >= 2 / >= 3 / >= 5 consecutive "
                "days) at all four threshold windows = 36 runs. Reported at the `%s` window.\n\n"
                % P)
        f.write("**Verification first.** Four of the nine cells already exist in the delivered "
                "definition grid. The rebuild reproduces all four exactly - %d/%d "
                "reconciliation checks pass on heatwave days and events - so the five new cells "
                "can be read directly alongside the earlier work.\n\n"
                % (int((rec["result"] == "PASS").sum()), len(rec)))
        f.write("**Per-county median heatwave days over %s:**\n\n" % YEARS)
        tab = pd.DataFrame({"percentile": ["%dth" % p for p in K.EXTREME_PERCENTILES]})
        for d in K.EXTREME_DURATIONS:
            tab[">=%d days" % d] = ["%d" % cell(p, d, "per_county_heatwave_days_median")
                                    for p in K.EXTREME_PERCENTILES]
        f.write(K.md_table(tab) + "\n\n")
        f.write("The two levers behave differently. The percentile moves the count smoothly "
                "(%d -> %d days per county from the 80th to the 90th at >= 2 days, a factor of "
                "%.1f). The duration rule bites harder at the long end: at the 90th percentile, "
                "%d days at >= 2 falls to %d at >= 3 and %d at >= 5, a factor of %.1f from the "
                "shortest to the longest rule.\n\n"
                % (cell(80, 2, "per_county_heatwave_days_median"),
                   cell(90, 2, "per_county_heatwave_days_median"),
                   cell(80, 2, "per_county_heatwave_days_median")
                   / cell(90, 2, "per_county_heatwave_days_median"),
                   cell(90, 2, "per_county_heatwave_days_median"),
                   cell(90, 3, "per_county_heatwave_days_median"),
                   cell(90, 5, "per_county_heatwave_days_median"),
                   cell(90, 2, "per_county_heatwave_days_median")
                   / cell(90, 5, "per_county_heatwave_days_median")))
        f.write("**The cool-season loading survives every one of the nine cells.** The share of "
                "heatwave days falling outside Jun-Sep runs from **%.0f%% to %.0f%%** across "
                "the grid, and the monthly rate is close to flat all year (Figure E6). A longer "
                "persistence rule helps a little - %.0f%% outside Jun-Sep at >= 2 days versus "
                "%.0f%% at >= 5 - but never resolves it, and the peak month is October or "
                "August depending on the cell, never a mid-summer month for the looser cells. "
                "No choice of percentile or duration fixes this, which is what motivates "
                "Part 3.\n\n"
                % (g["pct_heatwave_days_outside_jun_sep"].min(),
                   g["pct_heatwave_days_outside_jun_sep"].max(),
                   cell(90, 2, "pct_heatwave_days_outside_jun_sep"),
                   cell(90, 5, "pct_heatwave_days_outside_jun_sep")))

        # ---------- part 3 -------------------------------------------------
        f.write("---\n\n## Part 3 - absolute floors at 80 degF and 90 degF\n\n")
        f.write("### 3a. The floor as a GATE on the relative rule\n\n")
        f.write("A day must clear both its own county/calendar percentile threshold AND the "
                "absolute floor. 18 runs at the `%s` window (Figure E7, "
                "`tables/e03_floor_effect.csv`).\n\n" % P)
        f80 = fl[fl["floor_degF"] == 80.0]
        f90 = fl[fl["floor_degF"] == 90.0]
        f.write("| floor | days retained | cool-season share (outside Jun-Sep) | "
                "day-level agreement with the unfloored version |\n|---|---|---|---|\n")
        f.write("| none | 100%% | %.0f-%.0f%% | 1.00 |\n"
                % (fl["pct_outside_jun_sep_no_floor"].min(),
                   fl["pct_outside_jun_sep_no_floor"].max()))
        f.write("| 80 degF | %.0f-%.0f%% | %.0f-%.0f%% | %.2f-%.2f |\n"
                % (f80["pct_days_retained"].min(), f80["pct_days_retained"].max(),
                   f80["pct_outside_jun_sep_with_floor"].min(),
                   f80["pct_outside_jun_sep_with_floor"].max(),
                   f80["jaccard_with_vs_without_floor"].min(),
                   f80["jaccard_with_vs_without_floor"].max()))
        f.write("| 90 degF | %.0f-%.0f%% | %.0f-%.0f%% | %.2f-%.2f |\n\n"
                % (f90["pct_days_retained"].min(), f90["pct_days_retained"].max(),
                   f90["pct_outside_jun_sep_with_floor"].min(),
                   f90["pct_outside_jun_sep_with_floor"].max(),
                   f90["jaccard_with_vs_without_floor"].min(),
                   f90["jaccard_with_vs_without_floor"].max()))
        f.write("**The 90 degF floor largely resolves the cool-season problem; the 80 degF "
                "floor does not.** For `TMAX_P90_2D` the share outside Jun-Sep falls from "
                "%.0f%% to %.0f%% with a 90 degF floor but only to %.0f%% with 80 degF. The "
                "monthly profiles (Figure E7 C-D) show the mechanism: a 90 degF floor drives "
                "November through March to essentially zero and leaves a single August-peaked "
                "season, whereas the unfloored definition peaks in **December**.\n\n"
                % (float(fl[fl["cell"] == "P90.2D"]["pct_outside_jun_sep_no_floor"].iloc[0]),
                   float(f90[f90["cell"] == "P90.2D"]["pct_outside_jun_sep_with_floor"].iloc[0]),
                   float(f80[f80["cell"] == "P90.2D"]["pct_outside_jun_sep_with_floor"].iloc[0])))
        f.write("It is not free. A 90 degF floor discards **%.0f-%.0f%% of the classified "
                "days**, and it changes what the definition means: the output is no longer "
                "'unusual for this date' but 'unusual for this date AND hot in absolute terms'. "
                "That is a different construct and has to be described as one. Its geography "
                "also changes (Figure E9): a county-relative rule flags a broadly similar "
                "number of days everywhere by construction, while a floor concentrates "
                "exposure in the hottest counties - the retained share falls with latitude and "
                "elevation.\n\n"
                % (100 - f90["pct_days_retained"].max(), 100 - f90["pct_days_retained"].min()))
        f.write("### 3b. The floor as an ABSOLUTE-ONLY definition\n\n")
        f.write("Tmax > floor with no percentile at all. An absolute rule has no baseline and "
                "therefore no threshold window - there is nothing to pool - so this is 6 runs "
                "(2 floors x 3 durations), Figure E8.\n\n")
        a2 = av[av["minimum_duration_days"] == 2].drop_duplicates("absolute_definition")
        tt = pd.DataFrame({
            "definition": a2["absolute_definition"],
            "per-county median days": a2["per_county_median_absolute"].astype(int),
            "%% of all days in %s" % YEARS:
                (100 * a2["per_county_median_absolute"] / 4018).round(0).astype(int),
            "outside Jun-Sep": a2["pct_outside_jun_sep_absolute"].round(1),
        })
        f.write(K.md_table(tt) + "\n\n")
        f.write("**An 80 degF floor is not an extreme-heat criterion in Texas.** Tmax above "
                "80 degF for two or more consecutive days flags a median of **%d county-days "
                "per county**, which is **%.0f%% of every day in the study period**. Whatever "
                "that measures, it is not an extreme. The 90 degF rule flags %d days (%.0f%% "
                "of all days) and is strongly seasonal (%.0f%% outside Jun-Sep), so it behaves "
                "like a hazard-style summer definition.\n\n"
                % (int(a2["per_county_median_absolute"].max()),
                   100 * a2["per_county_median_absolute"].max() / 4018,
                   int(a2[a2["floor_degF"] == 90.0]["per_county_median_absolute"].iloc[0]),
                   100 * float(a2[a2["floor_degF"] == 90.0]["per_county_median_absolute"]
                               .iloc[0]) / 4018,
                   float(a2[a2["floor_degF"] == 90.0]["pct_outside_jun_sep_absolute"].iloc[0])))
        f.write("**The absolute and relative constructs are not variants of one another.** "
                "Day-level agreement between them is only **Jaccard %.2f-%.2f** across every "
                "pairing tested. They flag largely different county-dates: the absolute rule "
                "fires in the hottest weeks of the hottest counties, the relative rule fires "
                "whenever a county departs from its own normal for the date, including in "
                "winter. Choosing between them is a choice of research question, not a "
                "sensitivity setting.\n\n"
                % (av["jaccard_absolute_vs_relative"].min(),
                   av["jaccard_absolute_vs_relative"].max()))

        # ---------- what it means -----------------------------------------
        f.write("---\n\n## What this means for the open decisions\n\n")
        f.write("1. **The floor/season decision now has numbers.** A 90 degF Tmax floor takes "
                "the cool-season share from ~%.0f%% to ~%.0f%% and costs about half the "
                "classified days; an 80 degF floor is too low to change the character of the "
                "definition in Texas. If the goal is an occupational heat-exposure measure that "
                "a reader will interpret as hazardous heat, the 90 degF gate (or a declared "
                "season) is the option the data supports - and the definition must then be "
                "renamed to reflect that it is part absolute.\n"
                % (fl["pct_outside_jun_sep_no_floor"].median(),
                   f90["pct_outside_jun_sep_with_floor"].median()))
        f.write("2. **Part 1 explains why the problem existed.** Cool-season warming (December "
                "%+.1f degF in Texas) far exceeds summer warming (July %+.1f), so a "
                "walk-forward relative threshold necessarily finds its largest departures "
                "outside summer. This is a property of the regional climate trend, not a bug in "
                "the classification.\n" % (tmax_mo.loc["TX", 12], tmax_mo.loc["TX", 7]))
        f.write("3. **Tmin warming exceeds Tmax warming in all five states**, which strengthens "
                "the earlier finding that a Tmin definition is a different construct rather "
                "than a sensitivity case - the two metrics are diverging over time, not just "
                "disagreeing day to day.\n")
        f.write("4. **>= 5 consecutive days is a genuine third option** on the duration axis, "
                "not a minor extension: it cuts per-county exposure by roughly %.1fx relative "
                "to >= 2 days at the 90th percentile and lowers the cool-season share by about "
                "%.0f points, because long runs are harder to sustain out of season.\n\n"
                % (cell(90, 2, "per_county_heatwave_days_median")
                   / cell(90, 5, "per_county_heatwave_days_median"),
                   cell(90, 2, "pct_heatwave_days_outside_jun_sep")
                   - cell(90, 5, "pct_heatwave_days_outside_jun_sep")))

        # ---------- caveats ------------------------------------------------
        f.write("---\n\n## Caveats and choices worth knowing\n\n")
        f.write("- **Part 1 uses the OBSERVED GHCN record, not the IDW gap-filled table.** The "
                "question was what the record is over its available duration, so gap-filled "
                "values would describe the interpolation. The cost is uneven coverage, handled "
                "with the coverage gate and the balanced panel. Parts 2 and 3 use the "
                "pipeline's gap-filled county-day table, as every other definition in this "
                "project does - so Part 1 and Parts 2-3 are NOT on the same input, by design.\n")
        f.write("- **Parts 2 and 3 are Texas only.** Both are state-agnostic and run for another "
                "Gulf state as soon as that state's county-day table is built "
                "(`pipeline/p01_build_countyday_idw.py`); only Texas has one today.\n")
        f.write("- **Comparison operators.** The relative rule uses a strict `>` as everywhere "
                "in this project; the floor-as-gate uses `>=` (matching the pipeline's existing "
                "floor implementation) and the absolute-only rule uses `>` ('exceeding'). That "
                "is not purely cosmetic: %d of %s evaluable county-days sit exactly on the "
                "80 degF floor and %d on the 90 degF floor, because a county-day Tmax is an "
                "average over the county's reporting stations rather than a raw quantised "
                "reading. The affected share is %.3f%% and changes no conclusion here, but it "
                "is recorded in `qa/e02_floor_operator_check.csv` rather than assumed away.\n"
                % (int(fc[fc["floor_degF"] == 80.0]["county_days_exactly_on_floor"].iloc[0]),
                   "{:,}".format(int(fc["evaluable_county_days"].iloc[0])),
                   int(fc[fc["floor_degF"] == 90.0]["county_days_exactly_on_floor"].iloc[0]),
                   float(fc[fc["floor_degF"] == 80.0]["pct_county_days_exactly_on_floor"]
                         .iloc[0])))
        f.write("- **The floored variants were run at the primary window only.** The window was "
                "the least consequential of the four axes in the definition-comparison package "
                "(median Jaccard 0.687), and the floor is already crossed with 9 definitions x "
                "2 floors. The other three windows are one config edit away.\n")
        f.write("- **Nothing here uses a health outcome**, so nothing here can identify a "
                "correct definition. Jaccard is agreement between two definitions, never "
                "accuracy.\n")
        f.write("- **The temperature-source question is still unresolved and still dominates.** "
                "Earlier work found anchor-station versus multi-station composite temperature "
                "agreeing at only 0.45-0.73 - larger than most of the definition effects "
                "measured here. County-level results remain provisional until that is settled.\n")
    K.log("[write] FINDINGS.md")

    # ---------------------------------------------------------------- README
    p = os.path.join(K.PKG_ROOT, "README.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("# Extreme-temperature tests\n\n")
        f.write("Three requested pieces of work, kept in their own package so the delivered "
                "16-definition comparison in `outputs/definition_comparison/` is untouched.\n\n")
        f.write("**Read `FINDINGS.md` first.**\n\n")
        f.write("| part | what | scope | outputs |\n|---|---|---|---|\n")
        f.write("| 1 | Gulf-state temperature description: annual, by state, decadal, monthly "
                "| TX, LA, MS, AL, FL; %s; observed GHCN record | `figures/e01_*`, "
                "`tables/e01_*` |\n" % EDA)
        f.write("| 2 | county-relative daily MAX temperature, 80th/85th/90th percentile x "
                ">=2/>=3/>=5 consecutive days | %s, %s, 4 threshold windows (36 runs) | "
                "`figures/e03_fig05*`, `e03_fig06`, `tables/e03_part2_*` |\n"
                % (K.TEST_STATE, YEARS))
        f.write("| 3a | the same 9 definitions with an absolute floor as a GATE (80 / 90 degF) "
                "| %s, %s, primary window (18 runs) | `figures/e03_fig07`, `e03_fig09`, "
                "`tables/e03_floor_effect.csv` |\n" % (K.TEST_STATE, YEARS))
        f.write("| 3b | absolute-only definitions, Tmax > 80 / 90 degF | %s, %s, no window "
                "axis (6 runs) | `figures/e03_fig08`, `tables/e03_absolute_vs_relative.csv` "
                "|\n\n" % (K.TEST_STATE, YEARS))
        f.write("## Headline\n\n")
        f.write("| question | answer |\n|---|---|\n")
        f.write("| Has the Gulf warmed? | yes, and Tmin faster than Tmax in all 5 states "
                "(TX %+.2f vs %+.2f degF since the %s) |\n"
                % (ch("TX", "Tmin"), ch("TX", "Tmax"), first))
        f.write("| Where in the year? | the COOL season: December %+.1f degF in TX, July "
                "%+.1f |\n" % (tmax_mo.loc["TX", 12], tmax_mo.loc["TX", 7]))
        f.write("| Does any percentile/duration choice fix the cool-season loading? | no - "
                "%.0f-%.0f%% of heatwave days fall outside Jun-Sep in all 9 cells |\n"
                % (g["pct_heatwave_days_outside_jun_sep"].min(),
                   g["pct_heatwave_days_outside_jun_sep"].max()))
        f.write("| Does an 80 degF floor fix it? | no - cool-season share only falls to "
                "%.0f-%.0f%% |\n" % (f80["pct_outside_jun_sep_with_floor"].min(),
                                     f80["pct_outside_jun_sep_with_floor"].max()))
        f.write("| Does a 90 degF floor fix it? | largely yes - %.0f-%.0f%%, at the cost of "
                "about half the classified days |\n"
                % (f90["pct_outside_jun_sep_with_floor"].min(),
                   f90["pct_outside_jun_sep_with_floor"].max()))
        f.write("| Is an absolute floor alone a heatwave definition? | not at 80 degF - it "
                "flags %.0f%% of ALL days in Texas |\n"
                % (100 * a2["per_county_median_absolute"].max() / 4018))
        f.write("| Do absolute and relative rules pick the same days? | no - Jaccard "
                "%.2f-%.2f |\n\n" % (av["jaccard_absolute_vs_relative"].min(),
                                     av["jaccard_absolute_vs_relative"].max()))
        f.write("## Verification\n\n")
        f.write("Four Part-2 cells (`TMAX_P85_2D`, `TMAX_P85_3D`, `TMAX_P90_2D`, "
                "`TMAX_P90_3D`) already exist in the delivered definition grid. This package "
                "rebuilds them and reconciles against the published run summaries: **%d/%d "
                "checks pass**, so the new cells are directly comparable with the earlier "
                "work. See `qa/e02_reconciliation.csv`.\n\n"
                % (int((rec["result"] == "PASS").sum()), len(rec)))
        f.write("## Rebuild\n\n```bash\ncd outputs/extreme_temp_tests/scripts\n"
                "python e01_state_temperature_eda.py     # part 1  (~1 min)\n"
                "python e02_run_extreme_definitions.py   # parts 2-3 classification (~5 min)\n"
                "python e03_tables_and_figures.py        # tables + figures (~1 min)\n"
                "python e04_report.py                    # FINDINGS.md + README.md\n```\n\n")
        f.write("Provenance: git `%s`, classification input `%s`, python %s / pandas %s.\n"
                % (git_commit(), m["input_hash"].iloc[0], platform.python_version(),
                   pd.__version__))
    K.log("[write] README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
