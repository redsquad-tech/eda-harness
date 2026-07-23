---
name: create-maestro-test-setup-il-from-ngspice-group
description: Convert one named or all completed ngspice testbench groups into portable Maestro setup IL fragments. Read verification and implementation plans, generated SPICE fixtures, ngspice control files, manifests, logs, and metrics; preserve analyses, TB variables, outputs, limits, cases, temperatures, and configured process corners without launching Cadence.
---

# Create Maestro Setup IL

## Purpose

Translate completed open-stack testbench intent into deterministic per-group Maestro setup fragments. Generate source artifacts only; do not launch Virtuoso, load a site environment, or create a Cadence library.

## Inputs

Read from one DUT workspace:

```text
verification_plan.md
testbench_implementation_plan.md
tests/testbench_manifest.json
tests/<group>.sp
tests/<group>.control
results/<group>.log
results/<group>_metrics.csv
```

Use the original Spectre DUT public contract for later export. Do not bind the ngspice mock as the Cadence DUT.

## Selection

* An explicit group name selects that group.
* `all`, `remaining`, or no selector processes every completed group without a confirmation gate.
* A group is completed only when its saved runner produced structurally valid current outputs.
* Continue independent groups after a group-specific conversion blocker.

## Outputs

Create or update:

```text
cadence_export/model_bindings.toml
cadence_export/maestro_setup/<group>.il
```

`model_bindings.toml` schema version is `1`. Model file names are relative to runtime `PDK_PATH`; absolute paths and `..` are forbidden. Each entry contains `file` and optional `section`. Logical corners come from the specification when explicit, otherwise from configured corner tables. Do not invent a fixed five-corner set.

```toml
version = 1

[common]
models = []

[corners.<logical_corner>]
models = [{ file = "relative/model/file.scs", section = "model_section" }]
```

## Translation Contract

Treat `.control` as the executable source for run cases, analyses, measurements, and limits. Cross-check it against both plans, the manifest counts, and current metrics. Never infer acceptance behavior from filenames alone.

Normalize analyses exactly:

```text
op   -> dc
dc   -> dc
tran -> tran
ac   -> ac
```

Never emit `dcOp`. Represent simulator temperature as native corner temperature, not as a design variable. Preserve stable fixture `TB_*` parameters as Maestro design variables. Process/case/temperature combinations are corners rather than separate Maestro tests.

Create one Maestro test per group. Add one output and one spec for every acceptance metric represented by the group. Derive signal hierarchy from the imported fixture; use only public DUT pins and fixture probe nodes.

## Fragment Interface

Each fragment is embedded inside a suite generator and may use these variables:

```text
sess lib suiteCell spectreView configView testName pdkPath
```

It may call helpers from `eda_harness_api.il`, including normalized analysis, output/spec, and corner helpers. It must not open, delete, or save the shared Maestro view and must not call `exit`, `system`, `chmod`, `chown`, `setfacl`, or `sudo`.

Start every fragment with machine-readable metadata:

```skill
; EDA_HARNESS_GROUP: <group>
; EDA_HARNESS_TESTS: 1
; EDA_HARNESS_OUTPUTS: <positive integer>
; EDA_HARNESS_CORNERS: <positive integer>
; EDA_HARNESS_ANALYSIS: dc|tran|ac
```

The fragment must create `testName`, select `configView`, configure the normalized enabled analysis, add outputs/specs, configure exact corners, and assert the expected persisted counts before returning.

## Validation

Copy `scripts/validate_group_setup.py` only when a standalone validator is useful, or run it directly from the skill:

```bash
python <skill-root>/scripts/validate_group_setup.py \
  cadence_export/maestro_setup/<group>.il --group <group>
```

Validation must reject missing metadata, wrong group identity, unsupported analysis, zero counts, `dcOp`, destructive suite operations, site setup, permission repair, and unresolved placeholders.

## Completion

Report selected groups, generated fragments, normalized analyses, test/output/corner counts, and blockers. State clearly that Cadence has not been run.
