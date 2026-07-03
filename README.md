# EDA Harness Acceptance Flow

This repository is used with a Codex agent to generate analog acceptance testbenches from a block specification and then export the completed suite to Cadence/Virtuoso.

The flow is staged and interactive: the agent creates one artifact stage or one testbench group at a time, reports the result, and waits for confirmation before continuing.

## Requirements

For planning and ngspice testbench development:

- Python environment with the project dependencies installed;
- `hdl21` and `vlsirtools`;
- `ngspice`;
- a runnable ngspice DUT netlist, or enough information for the agent to create a development mock.

For optional report generation:

- `pandoc`;
- `xelatex` or `lualatex`;
- Python plotting dependencies such as `matplotlib`.

For Cadence/Virtuoso export:

- Cadence Virtuoso available on `PATH`, including `virtuoso` and `cdsTextTo5x`;
- a valid Cadence license and working batch launch environment;
- Spectre/ADE/Maestro APIs available in the installed Virtuoso version;
- PDK/model files available through the model convention used by the generated corners, usually `$LIB_PATH/<process>.scs section <process>`.

The Cadence export stage can create Maestro setup and symbolic `$LIB_PATH` model references without local model files existing in the workspace, but real Spectre simulation later requires those model files to resolve in the Cadence environment.

## Inputs

Create one workspace directory per block/device. Put the specification and available netlists there:

```text
<workspace>/
  specification.pdf / specification.md / specification.txt
  original_spectre_netlist
  optional_runnable_ngspice_dut.sp
```

The original Spectre netlist is treated as the primary DUT source. If it is not directly runnable in ngspice, the agent may create a minimal development mock only for ngspice testbench development. Cadence export must use the original Spectre DUT, not the mock.

## Starting A Run

Ask the agent from the repository root, for example:

```text
Я положил спеку и нетлист в папку <workspace>, сделай тестбенчи.
```

The agent should first identify the workspace, describe the plan briefly, and wait for confirmation before creating artifacts.

## Workflow

The standard flow is:

1. Create `<workspace>/verification_plan.md`.
2. Prepare the DUT for ngspice development.
3. Create `<workspace>/testbench_implementation_plan.md`.
4. Implement ngspice testbench groups one by one.
5. Optionally generate `test_report.md` and `test_report.pdf`.
6. Export Cadence/Virtuoso setup one testbench group at a time.

After each stage, and after each testbench group, the agent should stop and ask whether to continue.

## Ngspice Artifacts

Each implemented testbench group normally creates:

```text
<workspace>/
  tests/
    <group>.py
    <group>.sp
    <group>.control
  results/
    <group>.log
    <group>_metrics.csv
    <group>_samples.csv      # when planned
    <group>_waveforms.csv    # when planned
```

`tests/<group>.py` generates the reusable fixture through HDL21. `tests/<group>.sp` contains the testbench topology, public DUT instance, sources, loads, stimuli, and stable `TB_*` parameters.

The selected ngspice DUT binding belongs in `tests/<group>.control`, not in the fixture. For mock-based development, `.control` includes `mock_device.sp`; the fixture itself must not include mock files, real DUT files, PDK models, or `$LIB_PATH`.

Metrics and pass/fail decisions are produced by ngspice `.control` logic, not by Python.

## Optional Report

After all ngspice groups pass, the agent can generate:

```text
<workspace>/test_report.md
<workspace>/test_report.pdf
```

The PDF requires local report tooling such as `pandoc` and a LaTeX engine. If the report is not needed, skip it and continue to Cadence export.

## Cadence/Virtuoso Export

Cadence export is generated after the ngspice suite is complete. Run it one group at a time.

Typical artifacts:

```text
<workspace>/
  cadence_export/
    groups/
      <group>/
        generate.il
    generated_support/
      cadence_dut.scs
      <group>.scs
    <workspace>_acceptance_lib/
```

`cadence_dut.scs` is generated from the original Spectre DUT netlist. If the original netlist is a flat Spectre/ADE point netlist, the export creates a clean public `subckt` wrapper and leaves PDK/process models to Maestro corners.

`generated_support/<group>.scs` embeds `tests/<group>.sp` so the ngspice fixture remains the source of truth for Cadence fixture topology.

Each Cadence group creates:

```text
<library>/<cell>/spectre_<group>
<library>/<cell>/config
<library>/<cell>/maestro
```

The Maestro setup contains one test for the group, `TB_*` design variables, the analysis, outputs/specs, native corner temperature, and PVT/case corners. Process models are symbolic references such as:

```text
$LIB_PATH/<process>.scs section <process>
```

Cadence export should not include `mock_device.sp`, ngspice `.control` files, `RESULT`/`SUMMARY` logic, or full Spectre simulation unless explicitly requested.

## Expected Final Layout

```text
<workspace>/
  verification_plan.md
  testbench_implementation_plan.md
  mock_device.py              # only if needed for ngspice development
  mock_device.sp              # only if needed for ngspice development
  tests/
    <group>.py
    <group>.sp
    <group>.control
  results/
    <group>.log
    <group>_metrics.csv
    <group>_samples.csv
    <group>_waveforms.csv
    all_metrics.csv           # when report generation merges results
  test_report.md              # optional
  test_report.pdf             # optional
  cadence_export/
    groups/<group>/generate.il
    generated_support/cadence_dut.scs
    generated_support/<group>.scs
    <workspace>_acceptance_lib/
```

Cadence may also create local runtime files such as `.cadence/`, `.tmp_*`, `logs_*`, or `libManager.log`. These are tool-side runtime artifacts, not acceptance outputs.
