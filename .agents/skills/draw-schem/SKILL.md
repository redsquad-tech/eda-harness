---
name: draw-schem
description: Use this skill when you need to visualize a circuit of your hdl21 device or a testbench.
---

## Draw Schematic Skill

This skill will generate a schematic visualization of the circuit described by the HDL21 code. Export the circuit to a SPICE netlist using `h.netlist(..., fmt="spice")`, then tell user to use a SPICE schematic viewer (e.g., KiCad, LTspice) to visualize the circuit.