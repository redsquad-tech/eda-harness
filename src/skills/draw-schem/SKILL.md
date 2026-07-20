---
name: draw-schem
description: Use this skill when you need to visualize a circuit of your hdl21 device or a testbench.
---

# Draw Schematic

Generate an xschem schematic from an HDL21 device or testbench through a SPICE netlist.

## Workflow

1. Identify the user's task workspace and the HDL21 top-level module.
2. Export the elaborated circuit with `hdl21.netlist(..., fmt="spice")`. Keep the generated netlist in the task workspace.
3. Run the converter bundled with this skill:

```bash
PYTHONPATH=<skill-root>/scripts \
  python -m spice2xschem input.sp --output schematic
```

4. Validate the generated schematic with the same bundled module:

```bash
PYTHONPATH=<skill-root>/scripts \
  python -m spice2xschem.validate schematic
```

5. If xschem is installed, render or open the generated top-level `.sch`; otherwise return the portable `schematic/` directory and state that rendering requires xschem.

Do not require KiCad, LTspice, a repository-local PDK, or an agent-specific installation path. Resolve `<skill-root>` as the directory containing this `SKILL.md`.
