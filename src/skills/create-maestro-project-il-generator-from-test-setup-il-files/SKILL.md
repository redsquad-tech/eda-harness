---
name: create-maestro-project-il-generator-from-test-setup-il-files
description: Assemble all validated per-group Maestro setup IL fragments and completed SPICE fixtures into one portable Cadence deployment bundle. Generate one Makefile and generate.il that import unique group views into one Maestro suite at runtime, with strict environment preflight and persisted-state verification; do not launch Cadence while authoring.
---

# Assemble Maestro Project Generator

## Purpose

Build the final portable Cadence/Virtuoso source bundle after every selected ngspice group has a validated Maestro setup fragment. Generate files only. The user runs Make later from an already configured Cadence shell.

## Inputs

```text
verification_plan.md
testbench_implementation_plan.md
tests/testbench_manifest.json
tests/<group>.sp
cadence_export/maestro_setup/<group>.il
cadence_export/model_bindings.toml
original Spectre DUT netlist
```

Use the original Spectre DUT, never the ngspice mock. Preserve its public subckt interface. Remove service includes, analyses, simulator options, and process-model binding from a flat wrapper when necessary; process models belong to the generated corners.

## Outputs

Create inside the DUT workspace:

```text
cadence_export/
  Makefile
  generate.il
  eda_harness_api.il
  verify_export.py
  model_bindings.toml
  maestro_setup/<group>.il
  generated_support/cadence_dut.scs
  generated_support/<group>.scs
```

Use the bundled assets as the stable starting point. Fill every placeholder before delivery.

## Suite Shape

Create one managed Maestro view with one test per selected group. For each group create unique `spectre_<group>` and `config_<group>` views. Delete the managed Maestro view once before adding group tests, never inside a group block, and save once after all tests and corners are configured.

Embed every validated group fragment into `generate.il`. Reject missing, duplicate, stale, or extra fragments relative to the selected manifest groups. Require the shared fixture `.SUBCKT` from the implementation plan in every fixture.

## Runtime Contract

Expose:

```bash
make -C cadence_export help
make -C cadence_export preflight
make -C cadence_export import
make -C cadence_export verify
```

The configured Cadence shell supplies exactly:

```bash
PDK_PATH=/path/to/pdk \
CADENCE_LIB=<logical_library> \
CADENCE_WORKDIR=/writable/workdir \
make -C cadence_export import
```

Resolve `virtuoso`, `cdsTextTo5x`, Make, and Python from `PATH`. Do not embed `vs55`, module commands, site scripts, user/group names, absolute PDK paths, ACLs, or permission repair.

`preflight` must check all variables, commands, input decks, model files relative to `PDK_PATH`, and the writable target before Cadence mutation. Preserve caller ownership and umask; never run `chmod`, `chown`, `setfacl`, or `sudo`.

## Analysis And Validation

Use the bundled API adapter. OP and DC map to Cadence `dc`; transient maps to `tran`; AC maps to `ac`. Never emit `dcOp` or guess alternate API signatures.

Print `EDA_HARNESS_EXPORT_OK` only after checking persisted test names/counts, unique views, enabled normalized analyses, output/spec counts, corners, native temperatures, model files/sections, and real DUT inclusion.

`make import` must invoke `make verify`. Success requires Virtuoso exit `0`, the sentinel, a valid `validation.json`, exact counts, and no warning/error text. Exit `0` with a warning or partial setup is failure.

## Completion

Report generated files and test/view/corner counts, plus the exact three-variable Make invocation. State that import is pending until the user runs it successfully.
