---
name: control-to-maestro
description: Use this skill to create the Maestro/ADE setup block for one completed ngspice testbench group using the generated mock DUT for validation.
---

# Control To Maestro

Work on exactly one group per iteration. If the user did not name a group, select the first group from `testbench_implementation_plan.md` that does not yet have a completed Maestro setup file. Stop after that group and ask whether to continue.

## Inputs

Expected files in the workspace:

```text
mock_device.sp
tests/<group>.sp
tests/<group>.control
verification_plan.md
testbench_implementation_plan.md
```

## Output

During this stage, work temporarily in:

```text
<workspace>/maestro_tmp_<group>/
```

After validation, extract the reusable Maestro block to:

```text
<workspace>/cadence_export/maestro_setup/<group>.il
```

The extraction script deletes the temporary folder after the output file is written.

## Workflow

1. Identify the workspace and group.
2. From this skill directory, run the helper script. Pass `--workspace` as an absolute path; `--mock-device` and `--testbench-sp` are relative to that workspace.

```bash
python3 scripts/create_maestro_tmp.py \
  --workspace /absolute/path/to/<workspace> \
  --group <group> \
  --mock-device mock_device.sp \
  --testbench-sp tests/<group>.sp
```

The script creates and runs:

```text
<workspace>/maestro_tmp_<group>/cds.lib
<workspace>/maestro_tmp_<group>/wrapper.scs
<workspace>/maestro_tmp_<group>/setup_tmp.il
```

`wrapper.scs` embeds `mock_device.sp` and `tests/<group>.sp`. `setup_tmp.il` creates the temporary library, imports the Spectre view, creates the config view, and defines `lib`, `cell`, `configView`, `maestroView`, and `testName` before the `MAESTRO_SETUP` block.

3. Edit only the block in `setup_tmp.il` marked:

```lisp
; BEGIN MAESTRO_SETUP
...
; END MAESTRO_SETUP
```

4. Translate `tests/<group>.control` into Maestro/ADE code inside that block:

* delete and recreate one Maestro view for this group;
* split the `.control` file into logical analysis cases before writing Maestro tests. One testbench group may contain one analysis case or several analysis cases;
* identify derived metrics before splitting too aggressively. If a metric is computed from earlier measurements or outputs in the `.control` file, keep the source measurements and the derived metric in the same Maestro test whenever possible;
* create one Maestro test per incompatible analysis case or dependency group. Incompatible cases are cases that need different Maestro analysis definitions, such as different analysis types, different DC sweep sources, different transient stop/maxstep settings, or other analysis options that cannot live in one Maestro test without losing the required measurements;
* when multiple Maestro tests are needed, name them neutrally and stably, for example `case1 = strcat(testName "__case_1")`, `case2 = strcat(testName "__case_2")`; do not encode specification-specific signal names into the naming rule;
* set `TB_*` variables from the fixture defaults and `.control` run values;
* set each Maestro test analysis (`dc`, `tran`, `ac`, etc.) to match its `.control` analysis case;
* add outputs for each metric/result from the `.control` to the Maestro test for the analysis case that produces it;
* add specs/checks from the same limits as the `.control` to the corresponding Maestro test;
* create corners/cases for the run matrix;
* set simulator temperature as native corner temperature when temperature is swept;
* preserve process coverage through `$LIB_PATH/<process>.scs` model files when the verification plan requires process corners.

Do not change acceptance limits. Do not use internal DUT nodes. Use paths that exist in the imported fixture, usually through the top-level `XTB` instance.

Useful Maestro/ADE forms:

```lisp
let((sess db cornerHandle model)
  when(ddGetObj(lib cell maestroView) ddDeleteObj(ddGetObj(lib cell maestroView)))
  sess = maeOpenSetup(lib cell maestroView ?mode "a" ?allowADEXL t)
  maeCreateTest(testName ?lib lib ?cell cell ?view configView ?simulator "spectre" ?session sess)
  maeSetVar("TB_NAME" "value" ?typeName "test" ?typeValue list(testName) ?session sess)
  maeSetAnalysis(testName "dc" ?enable t ?session sess)
  maeAddOutput("metric" testName ?outputType "point" ?expr "VT(\"/XTB/node\")" ?session sess)
  maeSetSpec("metric" testName ?range list("min" "max") ?session sess)
  maeSaveSetup(?lib lib ?cell cell ?view maestroView ?session sess)
)
```

For transient analyses, pass stop/max step through `?options`, for example `list(list("stop" "TB_TSTOP") list("maxstep" "TB_TSTEP"))`; do not rely on variables alone if the analysis fields are empty.

Use one Maestro setup block per testbench group. Inside that block, use one Maestro test when the group has one compatible analysis/dependency case, or multiple Maestro tests when the `.control` file has multiple incompatible cases. Do not create separate Maestro tests merely for process, temperature, supply, reference, load, or corner dimensions when the analysis definition is the same; represent those dimensions as corners with corner-level `TB_*` overrides.

For any analysis type, split by the smallest set of Maestro analysis definitions needed to preserve the `.control` behavior. Keep dependent measurements together when a derived metric uses them. Different analysis option sets that cannot coexist in one Maestro test need separate tests, but do not split dependent measurements into separate tests unless cross-test derived expressions are verified in `active.state`.

For DC sweeps specifically, use the swept source as the primary split boundary. Different swept sources need different Maestro tests. Opposite sweep directions of the same source may remain in one Maestro test when outputs/specs combine both directions into one derived metric, such as a difference between rising and falling crossings.

For corner setup, build only the dimensions required by `verification_plan.md` and `tests/<group>.control`. If temperature is not swept, do not add temperature corners. If process coverage is not required for the group, do not add process model files.

Useful corner APIs:

```lisp
maeSetCorner(cornerName ?enableTests list(testName) ?enabled t ?session sess)
maeSetVar("TB_NAME" value ?typeName "corner" ?typeValue list(cornerName) ?session sess)
db = axlGetMainSetupDB(sess)
cornerHandle = axlGetCorner(db cornerName)
axlPutVar(cornerHandle "temperature" temp)
model = axlPutModel(cornerHandle proc)
axlSetModelFile(model strcat("$LIB_PATH/" proc ".scs"))
axlSetModelSection(model proc)
axlSetModelTest(model testName)
axlSetEnabled(model t)
```

Use `maeSetCorner` to create/enable each corner, `maeSetVar` for corner-level `TB_*` overrides, `axlPutVar(... "temperature" ...)` for native simulator temperature, and model objects only for required process corners. `$LIB_PATH/<proc>.scs` is symbolic; do not check local file existence.

Use `maeAddOutput(... ?outputType "point" ?expr ... )` first. If this Virtuoso build rejects `?outputType "point"`, omit `?outputType` but keep `?expr`. Do not use `?outputType "expr"` unless you verify the output appears in `active.state`.

Output paths must match the imported fixture hierarchy. If `tests/<group>.sp` has a top-level `XTB ... <fixture>` instance after `.ENDS`, paths to fixture nodes/elements must include `/XTB/...`. For current outputs, use the branch path of the actual source instance; do not invent `/PLUS` or `/MINUS` suffixes.

For AC waveform outputs, use `?outputType "all"` for traces and `?outputType "point"` for scalar metrics. Working calculator-expression patterns include `db20(...)`, `phase(...)`, `cross(...)`, `value(...)`, `ymin(...)`, and `ymax(...)` around `VF(...)`/`VT(...)` paths.

5. Re-run the temporary setup until it succeeds:

```bash
cd /absolute/path/to/<workspace>/maestro_tmp_<group>
virtuoso -nograph -restore setup_tmp.il
```

The script is intended to be rerunnable. It recreates the Spectre and config views each time.

6. Check the result:

```bash
find /absolute/path/to/<workspace>/maestro_tmp_<group>/tmp_<group>_lib -type f | sort
```

Also inspect the Maestro state when needed:

```text
<workspace>/maestro_tmp_<group>/tmp_<group>_lib/<group>_fixture/maestro/
```

Verify that expected analyses, outputs, specs, variables, and corners are present. If a group has multiple Maestro tests, verify each test has the correct analysis options and only the outputs/specs produced by that analysis case. If an output does not appear in `active.state`, fix `maeAddOutput` usage and rerun.

7. Extract the final reusable Maestro block and remove the temporary folder:

```bash
python3 scripts/extract_maestro.py \
  --workspace /absolute/path/to/<workspace> \
  --group <group>
```

This writes:

```text
<workspace>/cadence_export/maestro_setup/<group>.il
```

## Rules

* The helper script creates only the temporary Cadence foundation. The LLM writes the Maestro/ADE block.
* Use `mock_device.sp` as the DUT implementation for the temporary validation wrapper.
* Inside `MAESTRO_SETUP`, use the existing variables `lib`, `cell`, `configView`, `maestroView`, and `testName`; do not hardcode temporary library/cell/view names.
* Keep edits inside the `MAESTRO_SETUP` markers unless the foundation itself is broken.
* One group per iteration: finish and report the current group before touching the next one.
* Do not create the final Cadence library/export here.
* Do not manually edit `maestro.sdb`, `active.state`, or generated Cadence database files.
* Do not run a full Spectre simulation unless the user asks; this stage only proves the Maestro setup is created correctly.

## Final Response

After the group succeeds, report briefly:

* group name;
* final Maestro setup file;
* created Maestro analyses;
* outputs/specs added;
* corner count or remaining corner assumptions;
* any blockers.
