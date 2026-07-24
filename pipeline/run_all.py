"""
Run the whole heatwave pipeline for every state/percentile in config.py, in order:

  p01  build county-day table + IDW gap-fill        (once per state)
  p03  NWS advisory-threshold proxy                 (once per state; skipped if no office table)
  p02  classify heatwave days/events + reporting    (once per state x percentile)
  p04  figures                                      (once per state x percentile)

To run for a different state or definition, edit config.py (STATES, PERCENTILES)
and re-run this file:   python run_all.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import p01_build_countyday_idw as p01
import p02_classify_and_report as p02
import p03_nws_proxy as p03
import p04_figures as p04


def main():
    for st in C.STATES:
        p01.build_state(st)          # county-day table + IDW (percentile-independent)
        p03.run_state(st)            # NWS proxy (percentile-independent)
        for pctl in C.PERCENTILES:
            p02.run_state_percentile(st, pctl)
            p04.run_state_percentile(st, pctl)
    print("\n[run_all] complete for states=%s percentiles=%s" % (C.STATES, C.PERCENTILES), flush=True)


if __name__ == "__main__":
    main()
