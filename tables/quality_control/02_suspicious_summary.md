# Suspicious meteorological values -- audit summary (revised 2026-07-16)

Renamed from '02_invalid...' because these records are IMPLAUSIBLE, not
strictly impossible. They are retained (`suspicious_retain`) and flagged,
never silently dropped. Downstream, step03 also produces a sensitivity
event table with these set to missing, so their influence is quantified.

## RH=100 pin row-level disposition (review R3 Issue 4)

Each pinned record now carries rh_pin_class / verification_basis / recommended_action columns in the CSV. Of 31 total pins in the 5 pilot counties:

- **3 confirmed_artifact** (warm + rain-free): recommended set_missing/correct. These are the 2023-03-01 records that inflate the proxy 15-24F.
- **19 likely_real_wet** (measurable precip): genuine saturation, recommended retain.
- **9 indeterminate**: pinned but neither warm-dry nor wet -- i.e. cold/cool dry days or days with precip missing. These do NOT sit in warm-season events and are flagged for manual_review rather than auto-dropped, since fog/moisture can pin RH without measurable precipitation.

Note: only the 3 confirmed_artifact records are removed from the PRIMARY analysis (step03); the retain-all sensitivity keeps them.

    ======================================================================
    Weather-value fact-check audit (consumes step01 qc_status; review Issue 2)
    ======================================================================
    
[qc_status distribution across all 86770 county-days]
      valid              86709 (99.9297%)
      suspicious_retain  50 (0.0576%)
      missing_input      11 (0.0127%)
    
[soft-QC flag frequencies -- implausible but not physically impossible]
      qc_zero_diurnal_rh_range         31
      qc_rh_pinned_at_100              31
      qc_tiny_diurnal_temp_range       11
      qc_hi_jump_unexplained_by_tmax   10
    
[RH=100 pin sub-classification via independent GHCN precipitation cross-check]
      likely_artifact (warm+dry, PRCP~=0, Tmax>=80F): 3 -- these SPURIOUSLY inflate the HI proxy
      likely_real_wet (PRCP>=0.01in):                 19 -- genuine saturation, physically defensible
      confirmed-artifact days (all pinned RH=100 on rain-free warm days):
        Cameron (Brownsville)  2023-03-01  Tmax=87.5  proxy_HI=118.6 (inflated)
        Harris (Houston)       2023-03-01  Tmax=85.3  proxy_HI=109.0 (inflated)
        Travis (Austin)        2023-03-01  Tmax=83.7  proxy_HI=102.2 (inflated)
    [hard-QC flag frequencies -- physically impossible, field set to NaN]
      qc_tmax_lt_tmin                  0
      qc_rh_oob                        0
      qc_rmin_gt_rmax                  0
    
[rh_pinned_at_100 dates affecting >1 county simultaneously]
    date
2023-03-01    3
2017-01-14    2
    
[RH=100 pin row-level disposition] confirmed_artifact=3  likely_real_wet=19  indeterminate=9  (total pins=31)
    [done] wrote C:\Users\eadeni1\OneDrive - Louisiana State University\Documents\doc\heatWaveUS\texas_heatwave_pilot\tables\quality_control\02_suspicious_meteorological_values.csv rows=61
