# v3 Product Customer Archive

Generated: `2026-04-09T20:29:00.815497+00:00`

This archive contains the current `v3/prod` integrated device, SPICE benches,
the latest reduced acceptance report, and SPICE-only collateral.

## Architecture

- native AZ frontend: `opamp/v3/frontend_az.py`
- static core: `opamp/v3/opamp_core.py`
- integrated production DUT: `opamp/v3/prod/opamp_az_top.py`
- promoted RC configuration: `opamp/v3/prod/rc.py`

## Files

- `spice/dut/opamp_az_top_v3_prod.sp`: main DUT netlist
- `spice/testbenches/core/`: full-PVT core benches, load sweep, drive, leakage
- `spice/testbenches/top/`: top-level AZ nominal/PVT/timing/MC benches
- `reports/reduced.md`: latest reduced acceptance report
- `reports/reduced.json`: machine-readable reduced acceptance report
- `MAXIMUM_SPEC.md`: maximum requirement subset used for acceptance
- `manifest.json`: bundle manifest

## Current Need / Have Table

| Name | Need | Have |
|---|---|---:|
| core.aol_db | `>= 75.000 dB` | `86.186 dB` |
| core.gbw_hz | `500000.00 Hz .. 1000000.00 Hz` | `422555.06 Hz` |
| core.phase_margin_deg | `>= 30.000 deg` | `40.872 deg` |
| core.gain_margin_db | `>= 5.000 dB` | `21.462 dB` |
| core.iq_uA | `<= 15.00 uA` | `21.10 uA` |
| core.vout_low_actual | `<= 0.100 V` | `0.105 V` |
| core.vout_high_actual | `>= 1.700 V` | `1.800 V` |
| core.vout_source | `<= 0.100 V` | `0.440 V` |
| core.vout_sink | `>= 1.700 V` | `0.902 V` |
| core.disabled_leakage_nA | `<= 15.00 nA` | `0.54 nA` |
| top.residual_offset_uV | `<= 150.00 uV` | `28748.47 uV` |
| top.pedestal_mid50_uV | `<= 50.00 uV` | `1438.24 uV` |
| top.settling_mid50_uV | `<= 30.00 uV` | `17.44 uV` |
| top.residual_offset_pass_rate | `>= 0.9900` | `0.0000` |
| top.residual_offset_p99_uV | `<= 150.00 uV` | `29625.07 uV` |
| top.pedestal_mid50_p99_uV | `<= 50.00 uV` | `3128.59 uV` |
| top.settling_mid50_p99_uV | `<= 30.00 uV` | `409.19 uV` |

## Notes

- SPICE netlists use `__SKY130_LIB_SPICE__` placeholder for the SKY130 model path.
- Replace it with your local SKY130 library path before running `ngspice`.
