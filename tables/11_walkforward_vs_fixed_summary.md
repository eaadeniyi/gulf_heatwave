# Walk-forward vs fixed 1979-2014 baseline comparison (R2 Issue 9)

Both use the identical definition (HI proxy, 85th pctl, +-15-day window,
HI>=80 floor, >=2-day persistence, year-round, strict '>'). Only the
reference pool differs: expanding 1979..Y-1 vs fixed 1979-2014.

- Day-level Jaccard overlap: **0.9226**
- Total heatwave-days: walk-forward **3018**, fixed **3213** (fixed +195)
- County ranking by heatwave-days is IDENTICAL under both baselines.

Per-county detail in `11_walkforward_vs_fixed_comparison.csv`.

- Direction is NOT universal: the fixed baseline flags MORE days in Cameron (Brownsville), Harris (Houston), Lubbock, Travis (Austin), but FEWER in El Paso (El Paso: -6 days).

Interpretation (stated with restraint -- review R3 Issue 12): the fixed
baseline does not drift upward as recent hot years accrue, so it GENERALLY
(not universally) flags more heatwave-days in later analysis years than the
walk-forward baseline. The lower walk-forward slopes are CONSISTENT WITH
attenuation from an expanding reference pool, but are NOT yet isolated from
station-network composition changes (see 05_station_provenance) -- the
anchor-station sensitivity is required before any causal/trend claim.

These 11-year annual slopes are DESCRIPTIVE linear fits, not formal trend
estimates: only 11 bounded annual counts per county, possible autocorrelation,
a definition that itself changes with the baseline, and no uncertainty
intervals. Formal trend work needs count models, longer records, and
station-composition sensitivity.
