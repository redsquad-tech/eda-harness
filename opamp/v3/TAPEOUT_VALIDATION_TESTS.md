# Opamp V3 Tapeout Validation Test Plan

This is the customer-facing validation list for tapeout readiness.

Planned cases: `25`
Implementation status summary: `{"legacy_available": 2, "planned": 21, "v3_available": 2}`

| Test File | Component | Category | Level | Status | Key Metrics | Corners | Pass Rule |
|---|---|---|---|---|---|---|---|
| `test_opamp_az_top__contract__startup.py` | `opamp_az_top` | `contract` | `top` | `planned` | `startup_success, startup_time_us` | `SS/TT/FF x VDDmin/VDDnom/VDDmax x Tmin/Tnom/Tmax` | must start reliably and recover from enable cycling at all PVT corners |
| `test_opamp_az_top__contract__disable_enable_recovery.py` | `opamp_az_top` | `contract` | `top` | `planned` | `recovery_success, recovery_time_us, post_reenable_offset_uV` | `SS/TT/FF x VDDmin/VDDnom/VDDmax x Tmin/Tnom/Tmax` | must re-enable cleanly with no latched or wrong operating point |
| `test_opamp_az_top__contract__az_phase_function.py` | `opamp_az_top` | `contract` | `top` | `planned` | `phase_order_ok, no_overlap_violation, no_destructive_charge_sharing` | `TT nominal plus reduced PVT decision corners` | must tolerate PHI1/PHI2 non-overlap timing without destructive switching behavior |
| `test_opamp_az_top__budget__nominal_open_loop.py` | `opamp_az_top` | `budget` | `top` | `planned` | `aol_db, gbw_hz, phase_margin_deg, gain_margin_db` | `TT / 1.8 V / 27 C / CL=1 pF` | AOL >= 65 dB, GBW in 0.3..1 MHz, PM >= 30 deg, GM >= 5 dB |
| `test_opamp_az_top__budget__nominal_swing_drive.py` | `opamp_az_top` | `budget` | `top` | `planned` | `vout_low_actual, vout_high_actual, source_drive_v, sink_drive_v` | `TT / 1.8 V / 27 C` | must meet low/high swing and +/-20 uA drive requirements at nominal |
| `test_opamp_az_top__budget__nominal_power_leakage.py` | `opamp_az_top` | `budget` | `top` | `planned` | `iq_uA, disabled_leakage_nA` | `TT / 1.8 V / 27 C` | enabled IQ <= 20 uA and disabled leakage <= 250 nA |
| `test_opamp_az_top__pvt__open_loop.py` | `opamp_az_top` | `pvt` | `top` | `planned` | `worst_aol_db, worst_gbw_hz, worst_phase_margin_deg, worst_gain_margin_db` | `SS/TT/FF x 1.6/1.8/1.98 V x -40/27/125 C` | must satisfy all open-loop spec minima and GBW bounds across full PVT |
| `test_opamp_az_top__pvt__swing_drive.py` | `opamp_az_top` | `pvt` | `top` | `planned` | `worst_vout_low, worst_vout_high, worst_source_drive_v, worst_sink_drive_v` | `SS/TT/FF x 1.6/1.8/1.98 V x -40/27/125 C` | must meet compliant swing and +/-20 uA drive across full PVT |
| `test_opamp_az_top__pvt__power_leakage.py` | `opamp_az_top` | `pvt` | `top` | `planned` | `worst_iq_uA, worst_disabled_leakage_nA` | `SS/TT/FF x 1.6/1.8/1.98 V x -40/27/125 C` | enabled IQ and disabled leakage must meet full-PVT limits |
| `test_opamp_az_top__pvt__load_stability.py` | `opamp_az_top` | `pvt` | `top` | `planned` | `phase_margin_deg, gain_margin_db, gbw_hz` | `TT/1.8/27, SS/1.6/125, FF/1.98/-40 with CL=0/0.5/1/2 pF` | must remain stable for CL = 0..2 pF |
| `test_opamp_az_top__budget__residual_offset.py` | `opamp_az_top` | `budget` | `top` | `planned` | `residual_offset_uV` | `TT / 1.8 V / 27 C` | residual offset after AZ <= 250 uV minimum requirement |
| `test_opamp_az_top__budget__pedestal.py` | `opamp_az_top` | `budget` | `top` | `planned` | `pedestal_mid50_uV` | `TT / 1.8 V / 27 C` | pedestal-equivalent input error <= 100 uV minimum requirement |
| `test_opamp_az_top__budget__hold_droop.py` | `opamp_az_top` | `budget` | `top` | `planned` | `settling_mid50_uV` | `TT / 1.8 V / 27 C` | hold droop contribution per AZ cycle <= 50 uV minimum requirement |
| `test_opamp_az_top__pvt__residual_offset_pedestal_settling.py` | `opamp_az_top` | `pvt` | `top` | `legacy_available` | `worst_residual_offset_uV, worst_pedestal_mid50_uV, worst_settling_mid50_uV` | `reduced decision corners; extend to full PVT for signoff` | worst reduced/full PVT AZ metrics must meet spec limits |
| `test_opamp_az_top__pvt__az_frequency_sweep.py` | `opamp_az_top` | `pvt` | `top` | `planned` | `residual_offset_uV, pedestal_mid50_uV, settling_mid50_uV` | `TT plus reduced PVT; faz=10/50/100/200 kHz` | must meet AZ error metrics across timing frequency sweep |
| `test_opamp_az_top__pvt__nonoverlap_sweep.py` | `opamp_az_top` | `pvt` | `top` | `planned` | `residual_offset_uV, pedestal_mid50_uV, settling_mid50_uV` | `TT plus reduced PVT; deadtime=10/20/50 ns` | must tolerate required non-overlap timing range |
| `test_opamp_az_top__mc__residual_offset.py` | `opamp_az_top` | `mc` | `top` | `planned` | `mean_uV, sigma_uV, p99_uV, max_uV, yield` | `TT mismatch-only, no process variation, 200 samples minimum` | MC residual offset yield must satisfy customer acceptance criteria |
| `test_opamp_az_top__mc__pedestal.py` | `opamp_az_top` | `mc` | `top` | `planned` | `mean_uV, sigma_uV, p99_uV, max_uV, yield` | `TT mismatch-only, no process variation, 200 samples minimum` | MC pedestal distribution must remain inside customer acceptance criteria |
| `test_opamp_az_top__mc__hold_droop.py` | `opamp_az_top` | `mc` | `top` | `planned` | `mean_uV, sigma_uV, p99_uV, max_uV, yield` | `TT mismatch-only, no process variation, 200 samples minimum` | MC hold droop distribution must remain inside customer acceptance criteria |
| `test_opamp_az_top__mc__startup_yield.py` | `opamp_az_top` | `mc` | `top` | `planned` | `startup_yield, worst_startup_time_us` | `TT mismatch-only, 100 samples minimum` | must show no unacceptable startup failures under mismatch |
| `test_opamp_core_v3__char__tt_nominal.py` | `opamp_core_v3` | `char` | `core` | `v3_available` | `aol_db, gbw_hz, phase_margin_deg, gain_margin_db, iq_uA, vout_low_actual, disabled_leakage_nA` | `TT / 1.8 V / 27 C` | characterization only; appendix data for customer |
| `test_opamp_core_v3__screen__fast_nominal.py` | `opamp_core_v3` | `char` | `core` | `v3_available` | `smoke_nominal_ok` | `TT / 1.8 V / 27 C` | characterization/screen only |
| `test_opamp_az_top__budget__precision_ppa.py` | `opamp_az_top` | `budget` | `top` | `legacy_available` | `residual_offset_uV, pedestal_mid50_uV, settling_mid50_uV` | `TT / 1.8 V / 27 C` | legacy baseline nominal precision budget |
| `test_opamp_az_top__pex__open_loop.py` | `opamp_az_top` | `pex` | `top` | `planned` | `schematic_vs_pex_delta_aol_db, schematic_vs_pex_delta_gbw_pct, schematic_vs_pex_delta_pm_deg` | `TT plus reduced decision corners` | PEX deltas must stay within agreed signoff envelope |
| `test_opamp_az_top__pex__residual_offset_pedestal_settling.py` | `opamp_az_top` | `pex` | `top` | `planned` | `schematic_vs_pex_delta_residual_offset_uV, schematic_vs_pex_delta_pedestal_uV, schematic_vs_pex_delta_settling_uV` | `TT plus reduced decision corners` | PEX precision deltas must remain inside agreed signoff envelope |
