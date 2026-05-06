# Running The SPICE Bundle

## 1. Point ngspice to SKY130 models

All benches use the placeholder:

`__SKY130_LIB_SPICE__`

Replace it in the `.sp` files with your local SKY130 ngspice library path, for example:

`/path/to/sky130A/libs.tech/ngspice/sky130.lib.spice`

## 2. Run an acceptance bench

Example:

```bash
cd spice/testbenches/acceptance
ngspice -b accept_open_loop_tt_v1p80_t27.sp -o accept_open_loop_tt_v1p80_t27.log
```

Other acceptance benches:

- `accept_supply_enabled_tt_v1p80_t27.sp`
- `accept_supply_disabled_tt_v1p80_t27.sp`
- `accept_drive_source_25uA_tt_v1p80_t27.sp`
- `accept_drive_sink_25uA_tt_v1p80_t27.sp`

## 3. Run a core PVT bench

Example:

```bash
cd spice/testbenches/core
ngspice -b open_loop_tt_v1p80_t27.sp -o open_loop_tt_v1p80_t27.log
```

## 4. Files

- `spice/dut/neuron_core_oa_sky130.sp`: DUT netlist
- `spice/testbenches/core/`: characterization and PVT benches
- `spice/testbenches/acceptance/`: nominal acceptance benches
- `reports/`: exported JSON metrics from repository acceptance runs
