# Anchor-station vs county-composite temperature sensitivity (R3 Issue 8)

Same definition, humidity, thresholds, and run logic; ONLY the county
temperature source differs: single full-span airport anchor vs the
changing multi-station composite. Both retain-all.

- Mean Tmax bias (anchor - composite), by county: Cameron +1.34F, El +0.40F, Harris +0.09F, Lubbock +0.42F, Travis +1.55F
- Heatwave-day Jaccard(composite, anchor): Cameron 0.603, El 0.552, Harris 0.637, Lubbock 0.725, Travis 0.453
- Total heatwave-days composite=3018 anchor=3472 (+454)

If anchor and composite disagree materially (low Jaccard or large Tmax
bias), the composite series carries station-composition signal that must
be controlled before interpreting trends or the walk-forward-vs-fixed gap.
Detail: `12b_anchor_vs_composite_comparison.csv`.
