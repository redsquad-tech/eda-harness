# v4 Customer SPICE Archive

Generated: `2026-04-16T05:54:32.981755+00:00`

This archive contains the current `v4` DUT SPICE netlist and ngspice benches for
customer-facing product metrics.

Contents:
- `spice/dut/neuron_core_oa_sky130.sp`: current top-level DUT
- `spice/testbenches/core/open_loop_*.sp`: open-loop follower benches, including PVT
- `spice/testbenches/core/supply_enabled_tt_v1p80_t27.sp`
- `spice/testbenches/core/supply_disabled_tt_v1p80_t27.sp`
- `spice/testbenches/core/drive_source_25uA_tt_v1p80_t27.sp`
- `spice/testbenches/core/drive_sink_25uA_tt_v1p80_t27.sp`

Notes:
- Replace `__SKY130_LIB_SPICE__` with your local SKY130 ngspice library path.
- DUT netlist is exported from the current HDL21 source before archiving.
