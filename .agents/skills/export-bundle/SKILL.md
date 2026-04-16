---
name: export-bundle
description: Use this skill when user wants to share a device with someone else. This skill will export the device and testbenches netlists, README, metrics and all its dependencies into a tar.gz file. This file can be shared with someone to analysis and usage.
---


# Export Bundle Skill

The bundle should be a tar.gz file containing the following files:

- `README.md` with the device description, pinout, and usage instructions
- `device.sp` toplevel netlist of the device
- `testbenches/` directory with netlists (`.sp`) of all testbenches
- `metrics.md` with the product metrics table for the device: specification metrics with all corners, PVT and Monte Carlo results.

## How to export

You can export only one device at a time. Determinate device user wants to export (usually you already work with it). Go to the device directory, for example `devices/neuron_core_oa_sky130/`, and:

1. Choose the main device module to export. 
2. Create `export_spice.py` (if not exists):
  - Initialize SKY130 install with `init_sky130_install()`.
  - dut = h.elaborate(<DeviceName>(<DeviceParams>())). This elaborates the generators, parametrization and obtains the final HDL21 DUT graph.
  - call compile_for_sky130(dut). This step prepares the DUT for netlisting as a SKY130 circuit. It ensures that MOSFETs are instantiated using the correct SKY130 library cells (e.g., `sky130_fd_pr__nfet_01v8` and `sky130_fd_pr__pfet_01v8`) instead of generic MOSFETs.
  - call h.netlist(dut, stream, fmt="spice")
  - HDL21 exports .SUBCKT ... SPICE netlist to the memory.
  - write this netlist to file `device.sp` in the tmp/<device_name>/dist/device.sp directory.
3. Export all testbenches netlists in the same way, for example to `devices/<device_name>/devices/testbenches/test1.sp`, `devices/<device_name>/dist/testbenches/test2.sp`, etc.
4. Create `metrics.md` with the product metrics table for the device: specification metrics with all corners, PVT and Monte Carlo results.
5. Create `README.md` with the device description, pinout, and usage instructions.
6. Create tar.gz bundle by packaging `devices/<device_name>/dist/` directory. Put result ti the `.` directory with the name `<device_name>_bundle.tar.gz`.
