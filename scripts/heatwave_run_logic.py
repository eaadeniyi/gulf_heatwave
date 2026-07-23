"""
Shared, importable run/event-construction logic (spec Steps 12-16). Used by
BOTH the real-data pipeline (step03) and the required unit tests (Part J),
so the logic under test is exactly the logic used on real data -- not a
reimplementation that could silently drift from it.
"""
import numpy as np
import pandas as pd


def build_runs_and_events(df, min_duration=2, year_boundary_breaks_run=False,
                           definition_id="HI85_2D", state_fips="48"):
    """
    df: one row per CALENDAR day (fully reindexed -- no gaps), sorted by date
        ascending, must have columns: date (pd.Timestamp), county_fips,
        candidate_day_flag (1/0/NaN; NaN = missing day).

    Implements spec Step 14's pseudo-logic exactly: a run exists only among
    candidate_day_flag==1 rows; a NEW run starts whenever the previous row is
    missing, the previous row's candidate flag != 1, the date gap to the
    previous row != 1 day, or (if configured) a year boundary is crossed.

    Returns df with added columns: run_id, run_length, heatwave_day_flag,
    event_id, event_start_date, event_end_date, event_duration_days,
    event_day_number, event_onset_flag, event_continuation_flag,
    event_final_day_flag.
    """
    df = df.reset_index(drop=True).copy()
    n = len(df)
    run_id = np.full(n, np.nan)
    cur_run = 0

    dates = df["date"].values
    cand = df["candidate_day_flag"].values

    for i in range(n):
        c = cand[i]
        if pd.isna(c) or c != 1:
            continue
        start_new = False
        if i == 0:
            start_new = True
        else:
            prev_c = cand[i - 1]
            gap_days = (pd.Timestamp(dates[i]) - pd.Timestamp(dates[i - 1])).days
            prev_year = pd.Timestamp(dates[i - 1]).year
            this_year = pd.Timestamp(dates[i]).year
            if pd.isna(prev_c):
                start_new = True                                   # previous day missing
            elif prev_c != 1:
                start_new = True                                   # previous candidate flag != 1
            elif gap_days != 1:
                start_new = True                                   # date difference != 1 day
            elif year_boundary_breaks_run and (this_year != prev_year):
                start_new = True                                   # prohibited year-boundary crossing
        if start_new:
            cur_run += 1
        run_id[i] = cur_run

    df["run_id"] = run_id
    run_len_map = pd.Series(run_id).value_counts(dropna=True)
    df["run_length"] = pd.Series(run_id).map(run_len_map).values
    df["heatwave_day_flag"] = ((df["candidate_day_flag"] == 1) & (df["run_length"] >= min_duration)).astype(int)

    # ---- event assignment (Step 16) -- only among qualifying (heatwave) runs ----
    df["event_id"] = None
    df["event_start_date"] = pd.NaT
    df["event_end_date"] = pd.NaT
    df["event_duration_days"] = np.nan
    df["event_day_number"] = np.nan
    df["event_onset_flag"] = 0
    df["event_continuation_flag"] = 0
    df["event_final_day_flag"] = 0

    qualifying_runs = df.loc[df["heatwave_day_flag"] == 1, "run_id"].unique()
    seq_by_county_year = {}
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
        seq = seq_by_county_year[key]
        eid = "%s_%s_%d_%03d_%s" % (state_fips, county_code, start_year, seq, definition_id)

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
