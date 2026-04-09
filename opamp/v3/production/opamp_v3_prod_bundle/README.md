# v3 Product Tapeout Bundle

Generated: `2026-04-09T20:29:00.686322+00:00`

This bundle exports the current `v3` product candidate:

- native auto-zero frontend from `opamp/v3/frontend_az.py`
- `v3` static core from `opamp/v3/opamp_core.py`

Current promoted RC cases:

- core: `K1_stage2p10`
- az: `m4r1_cap300_wswn1p1_wswp1p6_nf2`

## Main DUT

- `spice/dut/opamp_az_top_v3_prod.sp`
- `MAXIMUM_SPEC.md`

## Included Benches

- nominal top-level AZ noise/offset
- full-PVT top-level AZ noise/offset
- mismatch-only top-level MC bench
- top-level timing sweep benches
- top-level closed-loop step bench
- core full-PVT open-loop benches
- core full-PVT swing / drive / leakage benches
- core load sweep benches

## Running

All generated netlists use the placeholder:

`__SKY130_LIB_SPICE__`

Replace it with your local SKY130 model-library path before running `ngspice`.
