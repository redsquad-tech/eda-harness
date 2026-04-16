# v3 Customer SPICE Archive

Generated: `2026-04-14T06:51:00.026326+00:00`

This archive contains the current `v3` DUT netlists and the exact SPICE benches
used for quick customer-facing characterization.

## DUT

- `spice/dut/opamp_az_top_v3.sp`: full current auto-zero top-level DUT
- `spice/dut/opamp_core_v3.sp`: current static core used inside the top-level DUT

## Included SPICE Benches

- `spice/testbenches/core/core_open_loop_tt_v1p80_t27.sp`
  Current `TT` biased open-loop AC bench for `AOL / GBW / PM / GM / IQ`
- `spice/testbenches/top/top_az_residual_offset_tt_v1p80_t27.sp`
  Current residual-offset-after-AZ bench
- `spice/testbenches/top/top_az_hold_200us_tt_v1p80_t27.sp`
  Current 200 us hold bench
- `spice/testbenches/top/top_az_mc_tt_mm.sp`
  Current mismatch-only top-level MC bench

## Quick Metrics

### Core `TT`, `VDD=1.8 V`, `27 C`, `CL=1 pF`

| Metric | Value | Status |
|---|---:|---|
| Open-loop gain | `88.48 dB` | pass vs `>= 65 dB` |
| GBW | `186479.2 Hz` | fail vs `>= 300 kHz` |
| Phase margin | `13.04 deg` | fail vs `>= 30 deg` |
| Gain margin | `2.79 dB` | fail vs `>= 5 dB` |
| Enabled current | `2.997 uA` | pass vs `<= 20 uA` |

### Full DUT `TT`, `VDD=1.8 V`, `27 C`

| Metric | Value | Status |
|---|---:|---|
| Residual offset after AZ | `-1899.81 uV` | fail vs `<= 250 uV` |
| Hold drift over 200 us | `0.040037 V` | fail vs `<= 50 uV eq.` |

## Notes

- All SPICE netlists use `__SKY130_LIB_SPICE__` as the SKY130 model-path placeholder.
- Replace it with your local SKY130 ngspice library path before running.
- `top_az_mc_tt_mm.sp` is the mismatch-only Monte Carlo bench collateral requested for customer review.
