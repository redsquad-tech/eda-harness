---
name: testbenches-to-cadence
description: Generate a portable Cadence/Virtuoso deployment bundle from completed DUT-workspace SPICE fixtures and ngspice control files. Produce one suite-level Makefile and SKILL generate.il that create all selected tests in one Maestro setup at runtime; generation itself requires no Cadence installation, while import requires PDK_PATH, CADENCE_LIB, CADENCE_WORKDIR, and Cadence commands in the user's configured PATH.
---

# Testbenches to Cadence

## Purpose

Convert completed open-stack fixture/control artifacts into a portable Cadence deployment bundle. Generate source files only. Do not activate site setup, run `vs55`, discover modules, launch Virtuoso, or create a Cadence library while authoring the bundle.

The user launches the generated Makefile later from an already configured Cadence shell and supplies machine-specific paths through environment variables.

## Inputs

Read from one DUT workspace:

```text
verification_plan.md
testbench_implementation_plan.md
tests/<group>.sp
tests/<group>.control
original Spectre DUT netlist
```

Use the original Spectre DUT for Cadence. Never use the ngspice mock as the Cadence DUT.

## Group Selection

* If the user explicitly selects groups, include those completed groups.
* Otherwise include every completed group from the implementation plan.
* Validate every selected fixture/control pair before generating the bundle.
* Generate one suite bundle for the complete selected set. Do not create or launch one isolated Cadence project per iteration.

## Output

Create inside the DUT workspace:

```text
cadence_export/
  Makefile
  generate.il
  eda_harness_api.il
  verify_export.py
  generated_support/
    cadence_dut.scs
    <group>.scs
```

Copy these resources as starting points:

```text
assets/Makefile.template
assets/generate.il.template
assets/eda_harness_api.il
assets/verify_export.py
```

Fill all placeholders in the Makefile and `generate.il`. Do not leave TODO values.

## Authoring Preflight

Before writing the bundle, check all selected inputs in one pass:

* each fixture and control file is readable;
* each fixture contains one importable group-level `.SUBCKT` and its public DUT instance;
* fixture `TB_*` parameters, sources, loads, stimulus, and observed public nodes are identifiable;
* each control file has a supported normalized analysis intent: `op`, `dc`, `tran`, or `ac`;
* outputs, limits, run cases, process corners, and temperatures are concrete;
* the original Spectre DUT is readable and its public pins agree with the verification contract;
* `cadence_export/` is writable.

Do not require local Cadence binaries, PDK files, `$LIB_PATH`, or site-specific shell setup during authoring.

## Runtime Contract

The generated bundle exposes:

```bash
make -C cadence_export help
make -C cadence_export preflight
make -C cadence_export import
make -C cadence_export verify
```

The user runs it from a configured Cadence shell:

```bash
PDK_PATH=/path/to/pdk \
CADENCE_LIB=<logical_library_name> \
CADENCE_WORKDIR=/path/to/writable/project \
make -C cadence_export import
```

Required environment variables:

* `PDK_PATH` — machine-local root for process model files;
* `CADENCE_LIB` — logical generated library name;
* `CADENCE_WORKDIR` — existing writable directory that will contain the generated Cadence project/library.

Resolve `virtuoso`, `cdsTextTo5x`, `make`, and Python from the user's configured `PATH`. Do not embed `vs55`, module commands, project setup scripts, user names, groups, ACLs, or machine paths.

The Makefile must export the three variables to `generate.il`. `preflight` must fail before library mutation if a variable, command, source file, required model file, or writable target is missing.

## Suite-Level Cadence Shape

Create one managed Maestro setup containing one test per selected group.

For each group create unique generated views:

```text
spectre_<group>
config_<group>
```

Create the shared `maestro` view once, add all group tests, and save once after the complete set is configured.

Mandatory rules:

* do not delete/recreate `maestro` inside the group loop;
* do not let a later group erase a previously added test;
* recreate only harness-managed views;
* one test owns its `TB_*` variables, normalized analysis, outputs/specs, cases, and corners;
* process/case/temperature combinations are corners, not separate tests;
* use native corner temperature;
* use model files rooted at `PDK_PATH` with filenames/sections derived from the verification artifacts.

## DUT And Wrapper Decks

Create `generated_support/cadence_dut.scs` from the original Spectre DUT.

If the DUT already provides a reusable public subckt, preserve it. If the input is a flat point netlist, create a clean public wrapper and omit ADE service includes, process-model includes, simulator options, analyses, save statements, and info statements. Process models belong to corners.

For each group create `generated_support/<group>.scs`:

```spectre
simulator lang=spectre
include "<generated cadence_dut.scs>"
simulator lang=spice
<embedded tests/<group>.sp>
simulator lang=spectre
```

Do not include mock DUT files, `.control` text, ngspice RESULT/SUMMARY logic, or raw output commands.

## Analysis Adapter

Use `eda_harness_api.il` for normalized API calls. Generate only these analysis identifiers:

```text
op   -> Cadence "dc"
dc   -> Cadence "dc"
tran -> Cadence "tran"
ac   -> Cadence "ac"
```

Never emit `dcOp`.

For transient analyses pass stop/maxstep through `maeSetAnalysis(... ?options ...)` and reference the appropriate `TB_*` variables. For DC and AC, fill the corresponding sweep/frequency options from the control/verification intent.

Use the adapter for outputs, specs, native-temperature corners, and model objects. If the local Cadence API profile does not provide a required symbol/signature, fail with `API_UNSUPPORTED`; do not try a sequence of guessed alternatives in the generated script.

## Outputs And Hierarchy

Create one Maestro output and spec for every acceptance metric represented by the selected control file.

Derive voltage/current paths from the actual imported hierarchy. If the fixture has an active top-level `X... <fixture_subckt>` instance, internal fixture paths must include that instance. Do not invent paths from group names and do not hardcode source-terminal suffixes unless present in the imported design.

After adding an output/spec, verify that it persists in the saved Maestro state. A successful API call alone is not proof of a valid output.

## Runtime Validation

`generate.il` may print `EDA_HARNESS_EXPORT_OK` only after checking:

* expected test count and test names;
* every unique Spectre/config view;
* normalized enabled analysis for every test;
* expected output and spec counts;
* exact corner counts;
* native temperatures and runtime `PDK_PATH` model files/sections;
* inclusion of the real DUT support deck;
* absence of mock DUT and ngspice control text.

Write `validation.json` only after these checks. `make import` must run `make verify`; success requires Virtuoso exit `0`, a valid `validation.json`, the success sentinel, and no warning/error matched by `verify_export.py`.

Treat exit `0` with an invalid/missing analysis, missing output, warning, or count mismatch as failure. Never report partial setup as successful.

## Permissions

Do not run `chmod`, `chown`, `setfacl`, `sudo`, or recursive permission repair. Do not modify the supplied DUT permissions.

The user chooses `CADENCE_WORKDIR` and runs Make under the identity that must own the project. Preserve the caller's umask. If the caller cannot read inputs or write the target, `preflight` must fail before Cadence objects are created.

## Completion Record

Return:

* selected groups and generated bundle files;
* generated test/view/corner counts;
* the exact three-variable Make invocation;
* confirmation that no site setup or machine path is embedded;
* confirmation that all selected groups share one Maestro setup without destructive per-group recreation;
* assumptions or authoring blockers.

Do not claim that the Cadence import itself completed until the user runs `make import` successfully in the configured Cadence environment.
