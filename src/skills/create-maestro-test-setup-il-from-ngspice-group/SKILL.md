---
name: create-maestro-test-setup-il-from-ngspice-group
description: Convert one named or all completed ngspice testbench groups into portable Maestro setup IL fragments. Read verification and implementation plans, generated SPICE fixtures, complete ngspice control files, manifests, logs, and metrics; preserve analyses, TB variables, waveforms, calculated acceptance metrics, limits, cases, temperatures, and configured process corners without launching Cadence.
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

* Let an explicit group name select that group.
* Process every completed group for `all`, `remaining`, or no selector without a confirmation gate.
* Treat a group as completed only when its saved runner produced structurally valid current outputs.
* Continue independent groups after a group-specific conversion blocker.

## Outputs

Create or update:

```text
cadence_export/model_bindings.toml
cadence_export/maestro_setup/<group>.il
```

Keep `model_bindings.toml` at schema version `1`. Keep model file names relative to runtime `PDK_PATH`; forbid absolute paths and `..`. Give each entry `file` and optional `section`. Take logical corners from the specification when explicit, otherwise from configured corner tables. Do not invent a fixed five-corner set.

```toml
version = 1

[common]
models = []

[corners.<logical_corner>]
models = [{ file = "relative/model/file.scs", section = "model_section" }]
```

## Translate The Complete Control Program

Treat the complete `.control` as the executable source for run cases, analyses, measurements, and limits. Cross-check it against both plans, manifest counts, current logs, and current metrics. Never choose an analysis from the group name or filename.

1. Read the entire `.control` block.
2. List every independent simulation run and its options.
3. Partition incompatible runs into separate Maestro tests.
4. Transfer each test's analysis and options, stable `TB_*` values, measurements, derived metrics, limits, and applicable corners.
5. Treat the matching fixture `.SUBCKT` imported as the suite cell as the root hierarchy; ignore activation instances outside its `.ENDS` and never use them as path prefixes.
6. Derive every referenced node, source instance, and branch terminal from inside that `.SUBCKT`.
7. Use only public DUT pins and fixture probe nodes; never use internal DUT nodes.
8. Preserve each acceptance metric as a calculated metric rather than simplifying it to a waveform.
9. Do not open, save, close, or delete the shared Maestro view from a group fragment.
10. Use only `eh*` wrappers for Maestro and AXL operations.
11. Record the exact created test names in `EDA_HARNESS_TESTS`.

Create one or more Maestro tests per group.

Use one test when all measurements share one compatible analysis definition. Create separate tests for different analysis types, DC sweep sources, transient stop/maxstep settings, AC ranges, or other incompatible options. Do not create separate tests only for process, temperature, supply, or load; represent these as corners or test variables.

Use stable group-prefixed names:

```text
dac_characterization
  |-- dac_characterization__static
  |-- dac_characterization__rise
  `-- dac_characterization__fall
```

Normalize analysis kinds only through `ehSetAnalysis`:

```text
op   -> dc
dc   -> dc
tran -> tran
ac   -> ac
```

Never emit `dcOp`. Represent simulator temperature as native corner temperature rather than as a design variable. Preserve stable fixture `TB_*` parameters as test variables.

## Fragment Interface

Embed each fragment inside the suite generator. Use these supplied variables as needed:

```text
sess lib suiteCell spectreView configView testName pdkPath
generatedCornerAssignments
```

Write each `cond` clause as exactly one list containing its predicate and actions; do not wrap the clause in an additional list:

```lisp
cond(
  (somePredicate(value)
    actionForFirstCase()
  )
  (t
    fallbackAction()
  )
)
```

Assign `testName` to each declared name and call:

```lisp
ehCreateTest(sess testName lib suiteCell configView)
ehSetTestVar(sess testName "TB_VDD" "1.2")
```

Pass every analysis option as a backtick list. Preserve the exact applicable `.control` values.
Map ngspice `tran ... uic` to the Cadence option `("skipdc" "yes")`; omit
`skipdc` when `uic` is absent. Cadence enumerated option values are strings,
not SKILL booleans.

```lisp
; OP
ehSetAnalysis(
  sess testName "op"
  `(("saveOppoint" t))
)

; DC component-parameter sweep
ehSetAnalysis(
  sess testName "dc"
  `(("dev" "vsource_instance")
    ("param" "dc")
    ("start" "0")
    ("stop" "1.2")
    ("step" "1m"))
)

; TRAN
ehSetAnalysis(
  sess testName "tran"
  `(("stop" "10u") ("maxstep" "1n"))
)

; AC
ehSetAnalysis(
  sess testName "ac"
  `(("start" "1")
    ("stop" "10G")
    ("incrType" "Logarithmic")
    ("stepTypeLog" "Points Per Decade")
    ("dec" "20"))
)
```

Use `ehAddWaveform` only for a waveform requested as an output. Use `ehAddMetric` for acceptance metrics. Do not replace settling time, INL, DNL, gain, phase margin, or leakage with a raw voltage waveform.

```lisp
ehAddWaveform(sess testName "aout" "/aout")

ehAddMetric(
  sess testName
  "output_max"
  sprintf(nil "ymax(%s)" ehVT("/aout"))
)

ehSetMinimum(sess testName "gain" "60")
ehSetMaximum(sess testName "leakage" "1u")
ehSetRange(sess testName "output" "0.1" "1.1")
```

Use `ehVT`, `ehVF`, and `ehVAR` for common signal and variable expressions. Escape every quote inside an arbitrary SKILL Calculator expression string as `\"`.

Create each corner before assigning variables or models. Prefix every Maestro corner name with its group, for example `dac__tt_27`, `dac__ss_125`, or `enable__tt_27`.

```lisp
ehCreateCorner(sess cornerName)
ehSetCornerVar(sess cornerName "temperature" "27")
ehSetCornerVar(sess cornerName "TB_VDD" "1.2")
ehAddCornerModel(
  sess cornerName modelName modelFile modelSection testName
)

applicableTests = list("dac__static" "dac__rise" "dac__fall")
generatedCornerAssignments = cons(
  list(cornerName applicableTests)
  generatedCornerAssignments
)
```

Use a stable, corner-local `modelName` for every model binding and make it unique when a corner uses more than one model. Pass `nil` for a missing model section.

Do not call any `mae*` or `axl*` function directly. Do not call `exit`, `maeOpenSetup`, `maeSaveSetup`, `maeCloseSession`, `ddDeleteObj`, `system`, or permission-changing commands from a group fragment.

Start every fragment with only these machine-readable metadata fields:

```skill
; EDA_HARNESS_GROUP: dac
; EDA_HARNESS_TESTS: dac__static,dac__rise,dac__fall
```

List test names in creation order without placeholders. Do not emit `EDA_HARNESS_OUTPUTS`, `EDA_HARNESS_CORNERS`, or `EDA_HARNESS_ANALYSIS`; those claims cannot be confirmed without running Cadence.

## Completion

Report selected groups, generated fragments, and exact declared test names. Report conversion blockers separately. State clearly that Cadence has not been run and that analysis, output, metric, spec, and corner correctness has not been runtime-verified.
