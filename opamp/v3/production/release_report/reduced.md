# reduced

- total_checks: 32
- failed_checks: 22
- passed: False

| Metric | Condition | Requirement | Measured | Pass | Details |
|---|---|---|---:|:---:|---|
| core.aol_db | TT / 1.80 V / 27 C | >= 75.000 dB | 86.186 dB | PASS |  |
| core.gbw_hz | TT / 1.80 V / 27 C | 500000.00 Hz .. 1000000.00 Hz | 422555.06 Hz | FAIL |  |
| core.phase_margin_deg | TT / 1.80 V / 27 C | >= 30.000 deg | 40.872 deg | PASS |  |
| core.gain_margin_db | TT / 1.80 V / 27 C | >= 5.000 dB | 21.462 dB | PASS |  |
| core.iq_uA | TT / 1.80 V / 27 C | <= 15.00 uA | 21.10 uA | FAIL |  |
| core.vout_low_actual | TT / 1.80 V / 27 C | <= 0.100 V | 0.105 V | FAIL |  |
| core.vout_high_actual | TT / 1.80 V / 27 C | >= 1.700 V | 1.800 V | PASS |  |
| core.vout_source | TT / 1.80 V / 27 C / +25 uA | <= 0.100 V | 0.440 V | FAIL |  |
| core.vout_sink | TT / 1.80 V / 27 C / -25 uA | >= 1.700 V | 0.902 V | FAIL |  |
| core.disabled_leakage_nA | FF / 1.98 V / -40 C | <= 15.00 nA | 0.54 nA | PASS |  |
| top.residual_offset_uV | TT / 1.80 V / 27 C | <= 150.00 uV | 28748.47 uV | FAIL |  |
| top.pedestal_mid50_uV | TT / 1.80 V / 27 C | <= 50.00 uV | 1438.24 uV | FAIL |  |
| top.settling_mid50_uV | TT / 1.80 V / 27 C | <= 30.00 uV | 17.44 uV | PASS |  |
| top.residual_offset_uV | TT / 1.80 V / 27 C | <= 150.00 uV | 28748.47 uV | FAIL |  |
| top.pedestal_mid50_uV | TT / 1.80 V / 27 C | <= 50.00 uV | 1438.24 uV | FAIL |  |
| top.settling_mid50_uV | TT / 1.80 V / 27 C | <= 30.00 uV | 17.44 uV | PASS |  |
| top.residual_offset_uV | SS_HOT / 1.60 V / 125 C | <= 150.00 uV | 23304.10 uV | FAIL |  |
| top.pedestal_mid50_uV | SS_HOT / 1.60 V / 125 C | <= 50.00 uV | 66.61 uV | FAIL |  |
| top.settling_mid50_uV | SS_HOT / 1.60 V / 125 C | <= 30.00 uV | 25.07 uV | PASS |  |
| top.residual_offset_uV | FF_COLD / 1.98 V / -40 C | <= 150.00 uV | 38590.95 uV | FAIL |  |
| top.pedestal_mid50_uV | FF_COLD / 1.98 V / -40 C | <= 50.00 uV | 2654.68 uV | FAIL |  |
| top.settling_mid50_uV | FF_COLD / 1.98 V / -40 C | <= 30.00 uV | 15.32 uV | PASS |  |
| top.residual_offset_uV | SS_COLD / 1.60 V / -40 C | <= 150.00 uV | 11331.40 uV | FAIL |  |
| top.pedestal_mid50_uV | SS_COLD / 1.60 V / -40 C | <= 50.00 uV | 375.06 uV | FAIL |  |
| top.settling_mid50_uV | SS_COLD / 1.60 V / -40 C | <= 30.00 uV | 50.54 uV | FAIL |  |
| top.residual_offset_uV | FF_HOT / 1.98 V / 125 C | <= 150.00 uV | 60571.37 uV | FAIL |  |
| top.pedestal_mid50_uV | FF_HOT / 1.98 V / 125 C | <= 50.00 uV | 113.63 uV | FAIL |  |
| top.settling_mid50_uV | FF_HOT / 1.98 V / 125 C | <= 30.00 uV | 10.64 uV | PASS |  |
| top.residual_offset_pass_rate | TT mismatch-only MC / 50 samples | >= 0.9900 | 0.0000 | FAIL |  |
| top.residual_offset_p99_uV | TT mismatch-only MC / 50 samples | <= 150.00 uV | 29625.07 uV | FAIL |  |
| top.pedestal_mid50_p99_uV | TT mismatch-only MC / 50 samples | <= 50.00 uV | 3128.59 uV | FAIL |  |
| top.settling_mid50_p99_uV | TT mismatch-only MC / 50 samples | <= 30.00 uV | 409.19 uV | FAIL |  |