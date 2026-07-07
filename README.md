# EDA Harness Acceptance Flow

This repository is used with a Codex agent to generate analog acceptance testbenches from a block specification and prepare the completed suite for Cadence/Virtuoso.

The flow is staged and interactive: the agent creates one artifact stage or one testbench group at a time, reports the result, and waits for confirmation before continuing.

## Requirements

For planning and ngspice testbench development:

- Python environment with the project dependencies installed;
- `hdl21` and `vlsirtools`;
- `ngspice`.

For optional report generation:

- `pandoc`;
- `xelatex` or `lualatex`;
- Python plotting dependencies such as `matplotlib`.

For Cadence/Virtuoso export:

- Cadence Virtuoso available on `PATH`, including `virtuoso` and `cdsTextTo5x`;
- a valid Cadence license and working batch launch environment;
- Spectre/ADE/Maestro APIs available in Virtuoso;
- PDK/model files available through the model convention used by the generated corners, usually `$LIB_PATH/<process>.scs section <process>`.

The Cadence export stage can create Maestro setup and symbolic `$LIB_PATH` model references without local model files existing in the workspace, but real Spectre simulation later requires those model files to resolve in the Cadence environment.

## Inputs

Create one workspace directory per block/device and put the specification there:

```text
<workspace>/
  specification.pdf / specification.md / specification.txt
```

The pipeline does not require the user's real DUT netlist as an input. It creates a generated mock DUT for ngspice development and uses that mock as the default placeholder implementation in the Cadence/Virtuoso export.

## Starting A Run

Ask the agent from the repository root, for example:

```text
Я положил спеку в папку <workspace>, сделай тестбенчи.
```

The agent should first identify the workspace, describe the full plan through ngspice testbench generation and Cadence/Virtuoso preparation, and wait for confirmation before creating artifacts.

## Workflow

The standard flow is:

1. Create `<workspace>/verification_plan.md`.
2. Create the generated HDL21/SPICE mock DUT.
3. Create `<workspace>/testbench_implementation_plan.md`.
4. Implement ngspice testbench groups one by one.
5. Optionally generate `test_report.md` and `test_report.pdf`.
6. Create Cadence/Maestro setup blocks one group at a time.
7. Assemble the final Cadence/Virtuoso library.

After each stage, and after each testbench group, the agent should stop and ask whether to continue.

## Ngspice Artifacts

Each implemented testbench group normally creates:

```text
<workspace>/
  mock_device.py
  mock_device.sp
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

The ngspice DUT binding belongs in `tests/<group>.control`, not in the fixture. The `.control` file includes `mock_device.sp` and the fixture, runs sweeps/measurements, emits `RESULT`/`FAIL`/`SUMMARY`, and writes CSV outputs. The fixture itself must not include mock files, real DUT files, PDK models, or `$LIB_PATH`.

Metrics and pass/fail decisions are produced by ngspice `.control` logic, not by Python.

## Optional Report

After all ngspice groups pass, the agent can generate:

```text
<workspace>/test_report.md
<workspace>/test_report.pdf
```

The PDF requires local report tooling such as `pandoc` and a LaTeX engine. If the report is not needed, skip it and continue to Cadence/Maestro preparation.

## Cadence/Maestro Setup

After the ngspice suite is complete, the agent creates one reusable Maestro setup block per testbench group:

```text
<workspace>/cadence_export/maestro_setup/<group>.il
```

Each group is handled separately. The agent creates a temporary Cadence library for validation, writes the Maestro setup inside marked SKILL markers, runs Virtuoso to verify that the setup can be created, extracts only the reusable Maestro setup block, and removes the temporary folder.

The Maestro setup contains one test for the group, `TB_*` design variables, the analysis, outputs/specs, native simulator temperature, and PVT/case corners. Process models are symbolic references such as:

```text
$LIB_PATH/<process>.scs section <process>
```

## Final Cadence/Virtuoso Export

The final stage assembles the validated Maestro setup blocks into one Cadence library with one cell per testbench group.

Typical artifacts:

```text
<workspace>/
  cds.lib
  cadence_export/
    dut_placeholder.scs
    generate.il
    maestro_setup/
      <group>.il
    spectre_wrappers/
      <group>.scs
    <workspace>_acceptance/
```

Each Cadence cell contains:

```text
<workspace>_acceptance/<fixture_cell>/spectre/netlist.oa
<workspace>_acceptance/<fixture_cell>/config/expand.cfg
<workspace>_acceptance/<fixture_cell>/maestro/active.state
<workspace>_acceptance/<fixture_cell>/maestro/maestro.sdb
```

The generated wrappers include `cadence_export/dut_placeholder.scs` as the only DUT replacement point. By default, the placeholder points to the generated mock:

```spice
simulator lang=spice
.include "../mock_device.sp"
```

To use a real DUT locally, replace the contents of:

```text
<workspace>/cadence_export/dut_placeholder.scs
```

For a Spectre DUT:

```spice
simulator lang=spectre
include "/private/path/to/real_dut.scs"
```

For a SPICE DUT:

```spice
simulator lang=spice
.include "/private/path/to/real_dut.sp"
```

The included real DUT must define the public subckt name and pin order used by the generated fixtures. If the private DUT has a different name or pin order, define a local adapter wrapper in `dut_placeholder.scs` that exposes the expected public contract and instantiates the private DUT inside it.

After editing `dut_placeholder.scs` in the same generated workspace, reopen or refresh Virtuoso/ADE. If the workspace was copied to another path, or if the generated Cadence export needs to be rebuilt, rerun the final Cadence export stage from that workspace root:

```bash
cd <workspace>
virtuoso -nograph -restore cadence_export/generate.il
```

## Expected Final Layout

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
    <group>_samples.csv
    <group>_waveforms.csv
    all_metrics.csv           # when report generation merges results
  test_report.md              # optional
  test_report.pdf             # optional
  cds.lib
  cadence_export/
    dut_placeholder.scs
    generate.il
    maestro_setup/<group>.il
    spectre_wrappers/<group>.scs
    <workspace>_acceptance/
```

Cadence may also create local runtime files such as `.cadence/`, `.tmp_*`, `logs_*`, `libManager.log`, or simulation results under the user's Cadence simulation directory. These are tool-side runtime artifacts, not acceptance outputs.
