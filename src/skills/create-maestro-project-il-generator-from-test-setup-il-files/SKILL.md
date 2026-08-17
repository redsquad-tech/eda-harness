---
name: create-maestro-project-il-generator-from-test-setup-il-files
description: Assemble per-group Maestro setup IL fragments and completed SPICE fixtures into one portable Cadence deployment bundle. Generate one Makefile and generate.il that import unique group views, create every declared Maestro test in one session, apply group-scoped corners, and verify the exact runtime test set; do not launch Cadence while authoring.
---

# Assemble Maestro Project Generator

## Purpose

Build the final portable Cadence/Virtuoso source bundle after every selected ngspice group has a Maestro setup fragment. Generate files only. Let the user run Make later from an already configured Cadence shell. Do not describe structural fragment checks as validation of SKILL or Cadence correctness.

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

Use the bundled assets as the stable starting point. Fill every placeholder before delivery. Keep the `model_bindings.toml` version `1` schema unchanged.

## Suite Shape

Create one managed Maestro view and one or more declared tests per selected group. Create one unique `spectre_<group>` and `config_<group>` view pair per group and share that config view between the group's tests. Delete the managed Maestro view once before opening the suite, never inside a group block, and save once after all tests and corners are configured.

Open exactly one Maestro session. This avoids older `maeSetAnalysis` behavior that could target only the latest open session despite `?session`.

Read exact test names from each fragment's comma-separated `EDA_HARNESS_TESTS` metadata. Preserve manifest group order and metadata order. Require a nonempty list and reject duplicate test names within a fragment or across groups.

Perform only technical fragment checks before assembly:

* Require the fragment file.
* Require one matching `EDA_HARNESS_GROUP` and one nonempty `EDA_HARNESS_TESTS` list.
* Reject duplicate metadata and test names.
* Reject unresolved `{{...}}` placeholders.
* Reject `exit`, `maeOpenSetup`, `maeSaveSetup`, and `ddDeleteObj` in fragments.
* Reject direct `mae*` and `axl*` calls; require the bundled `eh*` adapter.
* Reject obsolete `EDA_HARNESS_OUTPUTS`, `EDA_HARNESS_CORNERS`, and `EDA_HARNESS_ANALYSIS` metadata.

Do not statically judge analysis compatibility, node validity, Calculator expressions, outputs, specs, corners, or required helper-call counts.

Embed every structurally checked group fragment into `generate.il`. Reject missing, stale, or extra fragments relative to the selected manifest groups. Require the shared fixture `.SUBCKT` from the implementation plan in every fixture.

## Runtime Contract

Expose:

```bash
make -C cadence_export help
make -C cadence_export preflight
make -C cadence_export import
make -C cadence_export verify
```

Require the configured Cadence shell to supply exactly:

```bash
PDK_PATH=/path/to/pdk \
CADENCE_LIB=<logical_library> \
CADENCE_WORKDIR=/writable/workdir \
make -C cadence_export import
```

Resolve `virtuoso`, `cdsTextTo5x`, Make, and Python from `PATH`. Do not embed `vs55`, module commands, site scripts, user/group names, absolute PDK paths, ACLs, or permission repair.

Check all variables, commands, input decks, model files relative to `PDK_PATH`, and the writable target during `preflight`, before Cadence mutation. Preserve caller ownership and umask; never run `chmod`, `chown`, `setfacl`, or `sudo`.

## Runtime Test And Corner Checks

Initialize `generatedCornerAssignments` before group fragments. Require each fragment to register every created group-prefixed corner with the exact tests to which it applies. After all fragments, compute the complement of each applicable-test list and pass it to `maeSetCorner` as `?disableTests`.

Generate `expectedTests` as an explicit SKILL list. Obtain the persisted names with `maeGetSetup(?typeName "tests" ?session sess)` and reject both missing expected tests and unexpected actual tests.

Write `validation.json` only after the exact runtime test-set check succeeds:

```json
{
  "status": "ok",
  "expected_tests": 4,
  "actual_tests": 4
}
```

Save the setup once, print `EDA_HARNESS_EXPORT_OK` with the actual count, and close the Maestro session before terminating the batch process. Do not claim static or runtime validation of analyses, outputs, metrics, specs, or corners beyond successful API execution.

Require `make import` to invoke `make verify`. Treat Virtuoso exit `0`, an exact minimal validation record, the sentinel, equal positive test counts, and no error or unexpected warning text as success. Allow only the known infrastructure warnings encoded by `verify_export.py`; treat every other warning or a partial test set as failure.

## Completion

Report generated files, group count, exact declared test names, and the three-variable Make invocation. State that import remains pending until the user runs it successfully.
