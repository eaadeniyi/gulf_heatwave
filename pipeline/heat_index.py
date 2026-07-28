"""
NWS Rothfusz heat index (deg F). Self-contained copy so this pipeline does not
depend on files outside the repository.

Valid for T >= 80F; below that, apparent temperature ~= actual temperature, so we
use the simpler NWS averaging fallback. Includes the official NWS low-humidity
(RH<13%, 80<=T<=112) and high-humidity (RH>85%, 80<=T<=87) correction terms,
verified against wpc.ncep.noaa.gov/html/heatindex_equationbody.html.
"""
import numpy as np


def heat_index_f(t_f, rh_pct):
    t = np.asarray(t_f, dtype=float)
    rh = np.asarray(rh_pct, dtype=float)
    simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    full = (-42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh
            - 0.00683783 * t * t - 0.05481717 * rh * rh + 0.00122874 * t * t * rh
            + 0.00085282 * t * rh * rh - 0.00000199 * t * t * rh * rh)
    adj_lo = np.where((rh < 13) & (t >= 80) & (t <= 112),
                       -((13 - rh) / 4) * np.sqrt(np.clip((17 - np.abs(t - 95.0)) / 17, 0, None)),
                       0.0)
    adj_hi = np.where((rh > 85) & (t >= 80) & (t <= 87),
                       ((rh - 85) / 10) * ((87 - t) / 5), 0.0)
    return np.where(t >= 80, full + adj_lo + adj_hi, simple)
