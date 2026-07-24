"""
=============================================================================
SHARED RUN / EVENT CONSTRUCTION LOGIC
=============================================================================
This module turns a per-county time series of daily "candidate" flags into
HEATWAVE DAYS and HEATWAVE EVENTS, and is deliberately kept separate so that
the SAME code is exercised by both the real-data pipeline and the unit tests
(so the tested logic is exactly the logic that runs on data).

Vocabulary (used consistently everywhere in this project):
  candidate day  : a day that meets the threshold rule on its own (e.g. mean HI
                   above the county's percentile threshold).
  heatwave day   : a candidate day that is part of a run of >= MIN_DURATION
                   CONSECUTIVE calendar days -- i.e. it survives the persistence
                   rule. One county on one date.
  heatwave event : one uninterrupted run of heatwave days within one county.
  event duration : the integer number of consecutive calendar dates in the event
                   (= end_date - start_date + 1).

A run is BROKEN (so a new event can only start after) when:
  - the previous calendar day is missing (candidate flag is NaN), OR
  - the previous day was not itself a candidate, OR
  - the gap to the previous row is not exactly 1 day (non-consecutive dates), OR
  - (optionally) a calendar-year boundary is crossed.
This matches the specification's Step-14 pseudo-logic exactly.
=============================================================================
"""
import numpy as np
import pandas as pd


def build_runs_and_events(df, min_duration=2, year_boundary_breaks_run=False,
                          definition_id="HW", state_fips="00"):
    """
    Parameters
    ----------
    df : DataFrame with one row per CALENDAR day for ONE county, sorted ascending
         by 'date', fully reindexed so missing calendar days are explicit rows.
         Must contain columns: date (Timestamp), county_fips, candidate_day_flag
         (1.0 = candidate, 0.0 = not, NaN = missing day).
    min_duration : minimum consecutive-day run length to qualify as an event.
    year_boundary_breaks_run : if True, a Dec-31 -> Jan-1 transition breaks the run.
    definition_id, state_fips : used only to compose readable event IDs.

    Returns
    -------
    The same df with added columns: run_id, run_length, heatwave_day_flag,
    event_id, event_start_date, event_end_date, event_duration_days,
    event_day_number, event_onset_flag, event_continuation_flag, event_final_day_flag.
    """
    df = df.reset_index(drop=True).copy()
    n = len(df)
    run_id = np.full(n, np.nan)
    cur_run = 0
    dates = df["date"].values
    cand = df["candidate_day_flag"].values

    # ---- 1. assign a run id to every candidate day; start a new run on a break ----
    for i in range(n):
        c = cand[i]
        if pd.isna(c) or c != 1:            # not a candidate -> not in any run
            continue
        start_new = False
        if i == 0:
            start_new = True
        else:
            prev_c = cand[i - 1]
            gap_days = (pd.Timestamp(dates[i]) - pd.Timestamp(dates[i - 1])).days
            prev_year = pd.Timestamp(dates[i - 1]).year
            this_year = pd.Timestamp(dates[i]).year
            if pd.isna(prev_c):                       # previous day missing
                start_new = True
            elif prev_c != 1:                         # previous day not a candidate
                start_new = True
            elif gap_days != 1:                       # non-consecutive dates
                start_new = True
            elif year_boundary_breaks_run and (this_year != prev_year):
                start_new = True                      # prohibited year-boundary crossing
        if start_new:
            cur_run += 1
        run_id[i] = cur_run

    df["run_id"] = run_id

    # ---- 2. run length = number of days sharing a run id; heatwave day if run>=min ----
    run_len_map = pd.Series(run_id).value_counts(dropna=True)
    df["run_length"] = pd.Series(run_id).map(run_len_map).values
    df["heatwave_day_flag"] = ((df["candidate_day_flag"] == 1) & (df["run_length"] >= min_duration)).astype(int)

    # ---- 3. build one event record per qualifying run, with onset/continuation flags ----
    df["event_id"] = None
    df["event_start_date"] = pd.NaT
    df["event_end_date"] = pd.NaT
    df["event_duration_days"] = np.nan
    df["event_day_number"] = np.nan
    df["event_onset_flag"] = 0
    df["event_continuation_flag"] = 0
    df["event_final_day_flag"] = 0

    qualifying_runs = df.loc[df["heatwave_day_flag"] == 1, "run_id"].unique()
    seq_by_county_year = {}                            # sequential event number per county-year
    for rid in sorted(qualifying_runs):
        idx = df.index[df["run_id"] == rid]
        start_date = df.loc[idx[0], "date"]
        end_date = df.loc[idx[-1], "date"]
        duration = len(idx)
        county_fips = df.loc[idx[0], "county_fips"]
        county_code = str(county_fips)[-3:]
        start_year = pd.Timestamp(start_date).year
        key = (county_fips, start_year)
        seq_by_county_year[key] = seq_by_county_year.get(key, 0) + 1
        eid = "%s_%s_%d_%03d_%s" % (state_fips, county_code, start_year,
                                    seq_by_county_year[key], definition_id)
        for day_num, ridx in enumerate(idx, start=1):
            df.loc[ridx, "event_id"] = eid
            df.loc[ridx, "event_start_date"] = start_date
            df.loc[ridx, "event_end_date"] = end_date
            df.loc[ridx, "event_duration_days"] = duration
            df.loc[ridx, "event_day_number"] = day_num
            df.loc[ridx, "event_onset_flag"] = 1 if day_num == 1 else 0
            df.loc[ridx, "event_continuation_flag"] = 1 if day_num > 1 else 0
            df.loc[ridx, "event_final_day_flag"] = 1 if day_num == duration else 0

    return df
