# EDA Harness Acceptance Flow

This repository is used with Codex to turn an analog block specification into ngspice acceptance testbenches and a reusable Cadence/Virtuoso Maestro setup.

The workflow is interactive. Codex completes one stage, or one testbench group, reports the result, and waits before continuing.

## Requirements

- Python environment with the project dependencies, including HDL21 and VLSIR tools;
- `ngspice`;
- `pandoc` and a LaTeX engine when a PDF report is requested;
- Cadence Virtuoso, Spectre/ADE/Maestro APIs, a valid license, and an interactive shell that loads the Cadence environment for the Cadence stages.

## Start a Run

Create one workspace directory per block, place the specification in it, and ask Codex from the repository root:

```text
Я положил спеку в папку <workspace>, сделай тестбенчи.
```

The real DUT netlist is not required for ngspice testbench development. The workflow creates an HDL21/SPICE mock DUT first.

## Workflow

1. Create `verification_plan.md`.
2. Create and smoke-test `mock_device.py` and `mock_device.sp`.
3. Obtain the target existing-or-new Cadence cell name and create `testbench_implementation_plan.md`.
4. Implement and run one ngspice testbench group per turn.
5. Optionally create `test_report.md` and `test_report.pdf`.
6. Create and validate one Maestro setup block per turn.
7. Assemble the final `cadence_export/generate.il`.

## Main Artifacts

```text
<workspace>/
  verification_plan.md
  testbench_implementation_plan.md
  mock_device.py
  mock_device.sp
  tests/
    <group>.py
    <group>.sp
    <group>.control
  results/
    <group>.log
    <group>_metrics.csv
    <group>_samples.csv       # when needed
    <group>_waveforms.csv     # when needed
  test_report.md              # optional
  test_report.pdf             # optional
  cadence_export/
    model_bindings.toml
    model_bindings.il         # generated; do not edit
    dut_placeholder.scs
    generate.il
    maestro_setup/<group>.il
    spectre_wrappers/<group>.scs
```

The generated `.sp` fixture contains topology and stable `TB_*` parameters. Its `.control` file binds the mock DUT, executes ngspice, evaluates acceptance limits, and writes results.

## Cadence Model Bindings

When process coverage is required, Codex creates `cadence_export/model_bindings.toml`. The user supplies:

- `common.models` for models required by every logical process corner;
- `corners.<name>.models` for each configured logical corner;
- absolute model-file paths and optional section names.

Do not select process-corner models inside the real DUT netlist. Maestro applies the configured model bindings per corner.

## Final Cadence Export

The generator uses one shared Cadence cell for all groups. Each group receives namespaced `spectre_<group>` and `config_<group>` views, while all tests are stored in one selected Maestro view.

By default, `dut_placeholder.scs` includes the generated mock. To use the real DUT, replace the entire placeholder contents with a Spectre or SPICE include. The included netlist must expose the public subckt name and pin order recorded in the plans; add a local adapter subckt when necessary.

`generate.il` never deletes or clears `cds.lib`. Run it from the directory containing the user's existing `cds.lib`; when a new library is requested, Cadence registers it through the active library list.

Codex generates this file but does not run it; the user launches it in the intended Cadence environment.

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

For a new library registered through that `cds.lib`:

```bash
cd /path/containing/cds.lib
export CADENCE_EXPORT_DIR=/absolute/path/to/<workspace>/cadence_export
export CADENCE_LIBRARY_NAME=<new_library_name>
export CADENCE_LIBRARY_PATH=/absolute/path/to/<new_library_directory>
export CADENCE_VIEW_PREFIX=acceptance_
export CADENCE_MAESTRO_VIEW_NAME=acceptance_maestro
virtuoso -nograph -restore "$CADENCE_EXPORT_DIR/generate.il"
```

The existing library and cell are reused; missing ones are created. Generated Spectre/config views use the required prefix. The selected Maestro view is opened in append mode, so use a new Maestro view name or remove the previous generated view when intentionally replacing an older test/corner matrix.

A successful run ends with:

```text
cadence generate PASS
```
