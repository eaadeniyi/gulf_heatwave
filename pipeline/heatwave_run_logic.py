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

TWO IMPLEMENTATIONS LIVE HERE, and they must always agree:

  build_runs_and_events()        the REFERENCE implementation. An explicit,
                                readable per-day loop for ONE county. It is the
                                oracle the unit tests assert against, and it is
                                the code the published Definition 01 / 02 results
                                were produced with. Do not optimise it.

  build_runs_and_events_panel()  a VECTORISED implementation that processes a
                                whole multi-county panel at once. Needed because
                                the definition grid classifies ~1M county-days
                                x 56 runs, which the per-day loop cannot carry.
                                tests/test_run_logic.py proves it returns
                                identical output to the reference on the mandated
                                sequences and on randomised sequences.
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


# =============================================================================
# VECTORISED PANEL IMPLEMENTATION
# =============================================================================
def build_runs_and_events_panel(df, min_duration=2, year_boundary_breaks_run=False,
                                definition_id="HW", state_fips="00",
                                county_col="county_fips", flag_col="candidate_day_flag",
                                date_col="date", with_event_columns=True):
    """Vectorised equivalent of build_runs_and_events() for a MULTI-COUNTY panel.

    Parameters
    ----------
    df : DataFrame sorted ascending by [county_col, date_col], one row per
         county-day. Missing calendar days may be either explicit NaN-flag rows
         OR simply absent -- both break a run, because a break is triggered by
         'previous row is not exactly one day earlier' as well as by a NaN flag.
         (So, unlike the reference path, no per-county calendar reindex is needed.)
    min_duration : minimum consecutive-day run length to qualify as an event.
    year_boundary_breaks_run : if True, a Dec-31 -> Jan-1 transition breaks the run.
    with_event_columns : if False, skip the per-day event_* columns and return only
         run_id / run_length / heatwave_day_flag (cheaper when only the flags and
         the separate event table are wanted).

    Returns
    -------
    (df, events) where df has the same added columns as the reference function and
    'events' is a one-row-per-event DataFrame (run_id, county_fips, start/end date,
    duration, event_id) -- the event table the reporting layer aggregates onto.
    """
    df = df.reset_index(drop=True).copy()
    n = len(df)
    if n == 0:
        empty_cols = ["run_id", "run_length", "heatwave_day_flag", "event_id",
                      "event_start_date", "event_end_date", "event_duration_days",
                      "event_day_number", "event_onset_flag", "event_continuation_flag",
                      "event_final_day_flag"]
        for c in empty_cols:
            df[c] = pd.Series(dtype="float64")
        return df, pd.DataFrame(columns=["run_id", county_col, "start_date", "end_date",
                                         "event_duration_days", "event_id"])

    cand = pd.to_numeric(df[flag_col], errors="coerce").to_numpy(dtype="float64")
    is_cand = (cand == 1.0)                       # NaN and 0 both -> False
    dates = df[date_col].to_numpy(dtype="datetime64[D]")
    cty = df[county_col].to_numpy()

    # ---- 1. is this row a CONTINUATION of the previous row's run? -----------
    cont = np.zeros(n, dtype=bool)
    if n > 1:
        same_county = cty[1:] == cty[:-1]
        one_day_gap = (dates[1:] - dates[:-1]) == np.timedelta64(1, "D")
        prev_is_cand = is_cand[:-1]
        c = same_county & one_day_gap & prev_is_cand
        if year_boundary_breaks_run:
            yrs = dates.astype("datetime64[Y]")
            c &= (yrs[1:] == yrs[:-1])
        cont[1:] = c

    # ---- 2. run ids: a new run starts at every candidate day that is not a
    #         continuation. Numbering matches the reference (1..K over ALL
    #         candidate runs, including those shorter than min_duration).
    new_run = is_cand & ~cont
    run_no = np.cumsum(new_run)                   # 1-based, only meaningful where is_cand
    run_id_int = np.where(is_cand, run_no, 0)     # 0 = "not in any run"

    # ---- 3. run length, then the persistence rule ---------------------------
    counts = np.bincount(run_id_int, minlength=int(run_id_int.max()) + 1)
    counts[0] = 0
    run_len = counts[run_id_int].astype("float64")
    hw = is_cand & (run_len >= min_duration)

    df["run_id"] = np.where(is_cand, run_id_int, np.nan).astype("float64")
    df["run_length"] = np.where(is_cand, run_len, np.nan)
    df["heatwave_day_flag"] = hw.astype(int)

    # ---- 4. the event table (one row per QUALIFYING run) --------------------
    hw_pos = np.flatnonzero(hw)
    if hw_pos.size == 0:
        if with_event_columns:
            df["event_id"] = None
            df["event_start_date"] = pd.NaT
            df["event_end_date"] = pd.NaT
            for c in ["event_duration_days", "event_day_number"]:
                df[c] = np.nan
            for c in ["event_onset_flag", "event_continuation_flag", "event_final_day_flag"]:
                df[c] = 0
        return df, pd.DataFrame(columns=["run_id", county_col, "start_date", "end_date",
                                         "event_duration_days", "event_id"])

    rid_hw = run_id_int[hw_pos]
    starts = np.r_[True, rid_hw[1:] != rid_hw[:-1]]      # runs are contiguous in a sorted panel
    start_pos = hw_pos[starts]                            # panel index of each event's first day
    grp = np.cumsum(starts) - 1                           # 0-based event index per heatwave row

    # last panel index of each event = the row before the next event's first row,
    # among heatwave rows only
    last_of_event = np.empty(start_pos.size, dtype=np.int64)
    last_of_event[:-1] = hw_pos[np.flatnonzero(starts)[1:] - 1]
    last_of_event[-1] = hw_pos[-1]

    ev = pd.DataFrame({
        "run_id": rid_hw[starts].astype("float64"),
        county_col: cty[start_pos],
        "start_date": pd.to_datetime(dates[start_pos]),
        "end_date": pd.to_datetime(dates[last_of_event]),
        "event_duration_days": run_len[start_pos].astype(int),
    })
    # sequential event number within county-year, then the readable event id
    ev["onset_year"] = ev["start_date"].dt.year
    ev["seq"] = ev.groupby([county_col, "onset_year"]).cumcount() + 1
    county_code = pd.Series(ev[county_col].astype(str)).str[-3:]
    ev["event_id"] = (state_fips + "_" + county_code + "_" + ev["onset_year"].astype(str)
                      + "_" + ev["seq"].map(lambda s: "%03d" % s) + "_" + definition_id)

    # ---- 5. broadcast the event fields back onto the daily rows ------------
    if with_event_columns:
        df["event_id"] = None
        df["event_start_date"] = pd.NaT
        df["event_end_date"] = pd.NaT
        df["event_duration_days"] = np.nan
        df["event_day_number"] = np.nan
        df["event_onset_flag"] = 0
        df["event_continuation_flag"] = 0
        df["event_final_day_flag"] = 0

        day_number = np.arange(hw_pos.size) - np.flatnonzero(starts)[grp] + 1
        dur_per_row = ev["event_duration_days"].to_numpy()[grp]
        df.loc[hw_pos, "event_id"] = ev["event_id"].to_numpy()[grp]
        df.loc[hw_pos, "event_start_date"] = ev["start_date"].to_numpy()[grp]
        df.loc[hw_pos, "event_end_date"] = ev["end_date"].to_numpy()[grp]
        df.loc[hw_pos, "event_duration_days"] = dur_per_row.astype("float64")
        df.loc[hw_pos, "event_day_number"] = day_number.astype("float64")
        df.loc[hw_pos, "event_onset_flag"] = (day_number == 1).astype(int)
        df.loc[hw_pos, "event_continuation_flag"] = (day_number > 1).astype(int)
        df.loc[hw_pos, "event_final_day_flag"] = (day_number == dur_per_row).astype(int)

    return df, ev[["run_id", county_col, "start_date", "end_date",
                   "event_duration_days", "event_id", "onset_year", "seq"]]
