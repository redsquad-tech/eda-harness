---
name: maestro-to-cadence
description: Use this skill alone, after all Maestro setup blocks are validated, to assemble the final reusable Cadence/Virtuoso generator with the mock DUT placeholder. Treat it as one isolated final workflow stage.
---

# Maestro To Cadence

## Execution Boundary

Execute only this skill in the current turn. If the skill pauses for user input, the answer authorizes only completion of this final assembly stage. After reporting the result, stop.

Use this skill after all groups have validated Maestro setup files in:

```text
<workspace>/cadence_export/maestro_setup/<group>.il
```

This stage generates a reusable `generate.il` for importing all testbench groups into the shared cell named by `Shared Top-Level Fixture Subckt` in `testbench_implementation_plan.md`. Each group gets namespaced Spectre and config views. One user-selected Maestro view contains all Maestro tests from all group setup blocks.

## Inputs

Expected files in the workspace:

```text
mock_device.sp
tests/<group>.sp
cadence_export/maestro_setup/<group>.il
testbench_implementation_plan.md
cadence_export/model_bindings.toml
cadence_export/model_bindings.il
```

## Output

```text
<workspace>/cadence_export/dut_placeholder.scs
<workspace>/cadence_export/generate.il
<workspace>/cadence_export/spectre_wrappers/<group>.scs
```

## Workflow

1. Identify the workspace.
2. From this skill directory, create the final generator:

```bash
python3 scripts/create_generate_il.py \
  --workspace /absolute/path/to/<workspace>
```

The script first verifies that `model_bindings.il` was compiled from the current `model_bindings.toml`. If the TOML changed after the Maestro groups were validated, stop and regenerate the bindings and group setups before assembling the final export. The script then writes `cadence_export/dut_placeholder.scs`, Spectre wrapper files, and one `cadence_export/generate.il`. The generated file loads `model_bindings.il` once before applying any group setup blocks. After all blocks are applied, it uses their `generatedCornerAssignments` registry to enable each generated corner only for its exact applicable tests, disables all other tests on that corner, and disables the Nominal corner before saving. It does not parse TOML in Virtuoso, create or modify `cds.lib`, or run Virtuoso.

By default, `dut_placeholder.scs` points to the generated mock:

```spice
simulator lang=spice
* DUT implementation only; process-corner models are configured in model_bindings.toml.
.include "../mock_device.sp"
```

Each generated wrapper includes the placeholder first and then switches back to SPICE for the fixture:

```spice
.include "../dut_placeholder.scs"

simulator lang=spice
```

3. Do not run `generate.il`. Give the user the applicable command below.

For an existing library:

```bash
cd /path/containing/cds.lib
export CADENCE_LIBRARY_NAME=<existing_library_name>
unset CADENCE_LIBRARY_PATH
export CADENCE_VIEW_PREFIX=acceptance_
export CADENCE_MAESTRO_VIEW_NAME=acceptance_maestro
virtuoso -nograph -restore /absolute/path/to/<workspace>/cadence_export/generate.il
```

For a new library:

```bash
cd /path/containing/cds.lib
export CADENCE_LIBRARY_NAME=<new_library_name>
export CADENCE_LIBRARY_PATH=/absolute/path/to/<new_library>
export CADENCE_VIEW_PREFIX=acceptance_
export CADENCE_MAESTRO_VIEW_NAME=acceptance_maestro
virtuoso -nograph -restore /absolute/path/to/<workspace>/cadence_export/generate.il
```

`CADENCE_LIBRARY_NAME`, `CADENCE_VIEW_PREFIX`, and `CADENCE_MAESTRO_VIEW_NAME` are always required. `CADENCE_LIBRARY_PATH` is required only when that library name is not already registered. Successful execution ends with:

```text
cadence generate PASS
```

The shared cell will contain:

```text
<shared_cell>/<CADENCE_VIEW_PREFIX>spectre_<group>/netlist.oa
<shared_cell>/<CADENCE_VIEW_PREFIX>config_<group>/expand.cfg
<shared_cell>/<CADENCE_MAESTRO_VIEW_NAME>/active.state
<shared_cell>/<CADENCE_MAESTRO_VIEW_NAME>/maestro.sdb
```

## Rules

* Do not modify the validated per-group Maestro setup blocks during this stage.
* Do not run `generate.il`, Virtuoso, or Spectre.
* Tell the user to select the DUT only through `cadence_export/dut_placeholder.scs`.
* Keep process-corner model files and sections in `cadence_export/model_bindings.toml`. The real DUT selected by `dut_placeholder.scs` must not select process corners internally.
* Provide the `generate.il` launch command from the directory containing the user's `cds.lib`.

## Final Response

Report briefly:

* generated `generate.il`;
* generated `dut_placeholder.scs`;
* the shared cell name and the `CADENCE_VIEW_PREFIX` / `CADENCE_MAESTRO_VIEW_NAME` naming convention;
* that `generate.il` uses the mock DUT placeholder by default;
* that the DUT implementation is selected only by `<workspace>/cadence_export/dut_placeholder.scs`;
* show the current mock placeholder contents:

```spice
simulator lang=spice
* DUT implementation only; process-corner models are configured in model_bindings.toml.
.include "../mock_device.sp"
```

* explain that to use a real DUT, the user replaces the entire contents of `cadence_export/dut_placeholder.scs`; do not tell the user to edit `generate.il`, `spectre_wrappers/*.scs`, or generated Cadence database files;
* warn that the selected real DUT netlist must not include or select process-corner models. Put those model files and sections in `model_bindings.toml` so Maestro owns process selection. Ordinary DUT implementation includes that do not select process models may remain in the DUT netlist;
* for a real Spectre DUT, use this placeholder shape:

```spice
simulator lang=spectre
// DUT implementation only; process-corner models are configured in model_bindings.toml.
include "/private/path/to/real_dut.scs"
```

* for a real SPICE DUT, use this placeholder shape:

```spice
simulator lang=spice
* DUT implementation only; process-corner models are configured in model_bindings.toml.
.include "/private/path/to/real_dut.sp"
```

* print the exact public DUT subckt contract from `verification_plan.md`, cross-checking the `xdut` instance in generated fixtures when needed. Include the required subckt name and pin order, for example:

```spice
.SUBCKT <DUT_SUBCKT> <pin1> <pin2> ... <pinN>
...
.ENDS <DUT_SUBCKT>
```

* explain that the file included by `dut_placeholder.scs` must define that exact subckt name and pin order. If the private DUT uses a different name or pin order, the user should make `dut_placeholder.scs` include the private netlist and define a local adapter wrapper with the required public subckt contract around the private DUT;
* provide both launch commands from the directory containing the user's `cds.lib`;
* state that Codex generated but did not execute `generate.il`;
* any blockers or warnings.

## Stage Boundary

After completing this skill, stop and report the result to the user. Do not invoke another workflow skill in the same turn.
