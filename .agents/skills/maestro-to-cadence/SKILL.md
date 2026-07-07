---
name: maestro-to-cadence
description: Use this skill to assemble validated Maestro setup blocks into a final Cadence/Virtuoso acceptance library using the generated mock DUT as the placeholder implementation.
---

# Maestro To Cadence

Use this skill after all groups have validated Maestro setup files in:

```text
<workspace>/cadence_export/maestro_setup/<group>.il
```

This stage creates one Cadence library with one cell per testbench group. Each cell gets `spectre`, `config`, and `maestro` views. The generated Spectre wrappers include `cadence_export/dut_placeholder.scs` as the placeholder DUT implementation, then switch to `simulator lang=spice` for each generated fixture.

## Inputs

Expected files in the workspace:

```text
mock_device.sp
tests/<group>.sp
cadence_export/maestro_setup/<group>.il
```

## Output

```text
<workspace>/cds.lib
<workspace>/cadence_export/dut_placeholder.scs
<workspace>/cadence_export/generate.il
<workspace>/cadence_export/spectre_wrappers/<group>.scs
<workspace>/cadence_export/<workspace_name>_acceptance/
```

## Workflow

1. Identify the workspace.
2. From this skill directory, create the final generator:

```bash
python3 scripts/create_generate_il.py \
  --workspace /absolute/path/to/<workspace>
```

The script writes `cds.lib`, `cadence_export/dut_placeholder.scs`, Spectre wrapper files, and one `cadence_export/generate.il`.

By default, `dut_placeholder.scs` points to the generated mock:

```spice
simulator lang=spice
.include "../mock_device.sp"
```

Each generated wrapper includes the placeholder first and then switches back to SPICE for the fixture:

```spice
.include "../dut_placeholder.scs"

simulator lang=spice
```

3. Run the generated Cadence script separately:

```bash
cd /absolute/path/to/<workspace>
virtuoso -nograph -restore cadence_export/generate.il
```

Successful output ends with:

```text
cadence generate PASS
```

4. Check the final library:

```bash
find /absolute/path/to/<workspace>/cadence_export/<workspace_name>_acceptance -maxdepth 3 -type f | sort
```

Each group should have a fixture cell:

```text
<fixture_cell>/spectre/netlist.oa
<fixture_cell>/config/expand.cfg
<fixture_cell>/maestro/active.state
<fixture_cell>/maestro/maestro.sdb
```

5. Inspect `active.state` when needed to confirm analyses, outputs, and specs were preserved. Inspect `maestro.sdb` when needed to confirm corner count, model files, and native simulator temperature.

## Rules

* Do not manually edit the generated Cadence database files.
* Do not regenerate or rewrite the per-group Maestro setup blocks in this stage.
* Keep one Cadence cell per testbench group.
* Keep the generated library under `cadence_export/`.
* Keep `cds.lib` at the workspace root.
* Keep real-DUT replacement localized to `cadence_export/dut_placeholder.scs`; do not tell the user to edit generated wrappers or `generate.il`.
* Run `generate.il` as a separate Virtuoso command.
* Do not run full Spectre simulations unless the user asks.

## Final Response

Report briefly:

* generated `generate.il`;
* generated `dut_placeholder.scs`;
* final library path;
* cells created;
* views present for each cell;
* analyses/outputs/corner counts if checked;
* that the library was generated with the mock DUT placeholder by default;
* that the DUT implementation is selected only by `<workspace>/cadence_export/dut_placeholder.scs`;
* show the current mock placeholder contents:

```spice
simulator lang=spice
.include "../mock_device.sp"
```

* explain that to use a real DUT, the user replaces the entire contents of `cadence_export/dut_placeholder.scs`; do not tell the user to edit `generate.il`, `spectre_wrappers/*.scs`, or generated Cadence database files;
* for a real Spectre DUT, use this placeholder shape:

```spice
simulator lang=spectre
include "/private/path/to/real_dut.scs"
```

* for a real SPICE DUT, use this placeholder shape:

```spice
simulator lang=spice
.include "/private/path/to/real_dut.sp"
```

* print the exact public DUT subckt contract from `verification_plan.md`, cross-checking the `xdut` instance in generated fixtures when needed. Include the required subckt name and pin order, for example:

```spice
.SUBCKT <DUT_SUBCKT> <pin1> <pin2> ... <pinN>
...
.ENDS <DUT_SUBCKT>
```

* explain that the file included by `dut_placeholder.scs` must define that exact subckt name and pin order. If the private DUT uses a different name or pin order, the user should make `dut_placeholder.scs` include the private netlist and define a local adapter wrapper with the required public subckt contract around the private DUT;
* after editing `cadence_export/dut_placeholder.scs` in the same generated workspace, tell the user to reopen or refresh Virtuoso/ADE;
* if the workspace was moved/copied to another path, or if the user needs to rebuild the generated Cadence export, tell them to rerun the final Cadence export stage from that workspace root. Use a portable command in the final response, not the current machine's absolute path:

```bash
cd <workspace>
virtuoso -nograph -restore cadence_export/generate.il
```

* any blockers or warnings.
