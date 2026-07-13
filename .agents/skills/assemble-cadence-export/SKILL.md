---
name: assemble-cadence-export
description: Assemble, update, or regenerate the final Cadence/Virtuoso export, including cadence_export/generate.il, dut_placeholder.scs, and Spectre wrappers, from validated per-group Maestro setup blocks. Use when all required Maestro blocks are valid and the final export is missing or stale, or when the user explicitly requests final Cadence assembly or reassembly. Treat this as one isolated workflow stage; stop and report after completion.
---

# Assemble Cadence Export

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

The script first verifies that `model_bindings.il` was compiled from the current `model_bindings.toml`. If the TOML changed after the Maestro groups were validated, stop and regenerate the bindings and group setups before assembling the final export. The script then writes `cadence_export/dut_placeholder.scs`, Spectre wrapper files, and one `cadence_export/generate.il`. At run time, the generated file resolves `model_bindings.il` and all Spectre wrappers from the required `CADENCE_EXPORT_DIR` instead of embedding the workspace's absolute path. After all blocks are applied, it uses their `generatedCornerAssignments` registry to enable each generated corner only for its exact applicable tests, disables all other tests on that corner, and disables the Nominal corner before saving. It does not parse TOML in Virtuoso, create or modify `cds.lib`, or run Virtuoso.

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
export CADENCE_EXPORT_DIR=/absolute/path/to/<workspace>/cadence_export
export CADENCE_LIBRARY_NAME=<existing_library_name>
unset CADENCE_LIBRARY_PATH
export CADENCE_VIEW_PREFIX=acceptance_
export CADENCE_MAESTRO_VIEW_NAME=acceptance_maestro
virtuoso -nograph -restore "$CADENCE_EXPORT_DIR/generate.il"
```

For a new library:

```bash
cd /path/containing/cds.lib
export CADENCE_EXPORT_DIR=/absolute/path/to/<workspace>/cadence_export
export CADENCE_LIBRARY_NAME=<new_library_name>
export CADENCE_LIBRARY_PATH=/absolute/path/to/<new_library>
export CADENCE_VIEW_PREFIX=acceptance_
export CADENCE_MAESTRO_VIEW_NAME=acceptance_maestro
virtuoso -nograph -restore "$CADENCE_EXPORT_DIR/generate.il"
```

`CADENCE_EXPORT_DIR`, `CADENCE_LIBRARY_NAME`, `CADENCE_VIEW_PREFIX`, and `CADENCE_MAESTRO_VIEW_NAME` are always required. `CADENCE_EXPORT_DIR` must be the absolute path to the directory containing `generate.il`. `CADENCE_LIBRARY_PATH` is required only when that library name is not already registered.

When presenting the launch command, explain every environment variable:

* `CADENCE_EXPORT_DIR` is the absolute path to the generated `cadence_export` directory containing `generate.il`, `model_bindings.il`, and `spectre_wrappers/`.
* `CADENCE_LIBRARY_NAME` is the target Cadence library name. It names either an already registered library to reuse or the new library to create.
* `CADENCE_LIBRARY_PATH` is the absolute filesystem path where a new library is created. It must be unset when reusing an existing registered library.
* `CADENCE_VIEW_PREFIX` is the namespace prefix added to every generated Spectre and config view so generated views do not collide with unrelated user views.
* `CADENCE_MAESTRO_VIEW_NAME` is the exact name of the shared Maestro view that receives all generated tests.

Explain that an absolute path shown in `CADENCE_EXPORT_DIR` is the value for the workspace's current location, not a path embedded in `generate.il`; if the workspace is moved, the user updates this variable.

Successful execution ends with:

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
* explain the purpose of every environment variable in those commands and which variables differ between an existing and a new library;
* state that Codex generated but did not execute `generate.il`;
* any blockers or warnings.

## Stage Boundary

After completing this skill, stop and report the result to the user. Do not invoke another workflow skill in the same turn.
