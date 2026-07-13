---
name: control-to-maestro
description: Use this skill alone, after an ngspice testbench group is complete, to create and validate its Maestro/ADE setup block. Process exactly one group per turn and stop before another group or final Cadence assembly.
---

# Control To Maestro

## Execution Boundary

Execute only this skill in the current turn and process only one group. A broad request for the whole workflow or all groups does not authorize another group or final assembly. If the skill pauses for user input, including model bindings, the answer authorizes only completion of the current group. After reporting the result, wait for a new user message explicitly requesting continuation.

Work on exactly one group per iteration. If the user did not name a group, select the first group from `testbench_implementation_plan.md` that does not yet have a completed Maestro setup file. Stop after that group and ask whether to continue.

## Inputs

Expected files in the workspace:

```text
mock_device.sp
tests/<group>.sp
tests/<group>.control
verification_plan.md
testbench_implementation_plan.md
cadence_export/model_bindings.toml
```

`model_bindings.toml` is required only when process coverage is enabled. The workflow below creates its template at the start of this stage.

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
2. Prepare process-model bindings before creating the first Maestro group:

```bash
python3 scripts/prepare_model_bindings.py \
  --workspace /absolute/path/to/<workspace> \
  --init
```

If this creates `cadence_export/model_bindings.toml` and process coverage is enabled, stop and ask the user to fill the commented template. Explain that `common.models` is applied to every logical corner, `corners.<name>.models` is specific to that logical corner, paths must be absolute, and every selected corner needs at least one corner-specific entry. Warn the user not to include process-corner models inside the real DUT netlist because they would conflict with Maestro corner selection. Do not continue until the user says the file is filled.

If `Corner Source` is `none`, no user input is needed; keep the generated model lists empty and continue.

Validate and compile the completed configuration:

```bash
python3 scripts/prepare_model_bindings.py \
  --workspace /absolute/path/to/<workspace>
```

Do not continue on any validation error. Successful compilation creates:

```text
<workspace>/cadence_export/model_bindings.il
```

Do not edit `model_bindings.il`; it is generated from the TOML file.

3. Run the temporary-foundation helper. Pass `--workspace` as an absolute path; `--mock-device` and `--testbench-sp` are relative to that workspace.

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

The helper first uses `virtuoso` from the current `PATH`. If it is absent there, it automatically launches the same command through `bash -ic` so the user's interactive shell can load Cadence paths, license variables, and compatibility libraries. Do not report missing Virtuoso as a blocker until this fallback has also failed.

`wrapper.scs` embeds `mock_device.sp` and `tests/<group>.sp`. `setup_tmp.il` loads `cadence_export/model_bindings.il`, reads `Shared Top-Level Fixture Subckt` from `testbench_implementation_plan.md`, uses it as the common cell name, imports `spectre_<group>`, creates `config_<group>`, opens a clean temporary `maestro` session, and defines `lib`, `cell`, `spectreView`, `configView`, `maestroView`, `testName`, `sess`, and `generatedCornerAssignments` before the `MAESTRO_SETUP` block.

4. Edit only the block in `setup_tmp.il` marked:

```lisp
; BEGIN MAESTRO_SETUP
...
; END MAESTRO_SETUP
```

5. Translate `tests/<group>.control` into Maestro/ADE code inside that block:

* add only this group's Maestro test or tests to the already-open `sess`; do not delete, open, or save the Maestro view inside the group block;
* split the `.control` file into logical analysis cases before writing Maestro tests. One testbench group may contain one analysis case or several analysis cases;
* identify derived metrics before splitting too aggressively. If a metric is computed from earlier measurements or outputs in the `.control` file, keep the source measurements and the derived metric in the same Maestro test whenever possible;
* create one Maestro test per incompatible analysis case or dependency group. Incompatible cases are cases that need different Maestro analysis definitions, such as different analysis types, different DC sweep sources, different transient stop/maxstep settings, or other analysis options that cannot live in one Maestro test without losing the required measurements;
* if a group contains one Maestro test, use the group name as the test name with no suffix;
* if a group contains multiple Maestro tests, name each test `<group>__<purpose>`, deriving a concise stable `snake_case` purpose from its analysis case in the implementation plan or `.control`; use numeric suffixes only when no meaningful stable purpose can be determined;
* set `TB_*` variables from the fixture defaults and `.control` run values;
* set each Maestro test analysis (`dc`, `tran`, `ac`, etc.) to match its `.control` analysis case;
* add outputs for each metric/result from the `.control` to the Maestro test for the analysis case that produces it;
* add specs/checks from the same limits as the `.control` to the corresponding Maestro test;
* create corners/cases for the run matrix; name every corner `<group_name>__<corner_name>` by prefixing its local corner name with `testName`;
* immediately after creating each corner, prepend `list(cornerName applicableTests)` to `generatedCornerAssignments`, where `applicableTests` is the exact list passed through `?enableTests`; the final Cadence stage uses this registry to disable every non-applicable test on that corner after all groups have been added;
* set simulator temperature as native corner temperature when temperature is swept;
* resolve the process set separately for each Maestro test from that test's run matrix: use its exact explicit logical corners, expand `configured_process_corners` to `edaHarnessProcessCorners`, or use no process dimension when process coverage is not applicable;
* use `edaHarnessModelsForCorner(proc)` only for the process corners selected for that test.

Do not change acceptance limits. Do not use internal DUT nodes. Use paths that exist in the imported fixture.

`cdsTextTo5x -CELL <shared_fixture_name>` imports the `.SUBCKT` whose name matches that cell directly as the cell body. Therefore nodes and instances inside the matching fixture subckt are normally at the root of the Maestro test hierarchy. A top-level ngspice activation instance written after `.ENDS` is not an additional Maestro hierarchy level. Do not add a wrapper prefix derived from an activation instance outside the imported subckt.

Build voltage paths from the exact root node names inside the matching fixture subckt. For source current, use the exact imported source-instance name and its actual branch-terminal name. Derive all three from the current group's artifact; do not reuse node, instance, terminal, or hierarchy names from examples or previous groups.

Useful Maestro/ADE forms:

```lisp
let((db cornerHandle model)
  maeCreateTest(testName ?lib lib ?cell cell ?view configView ?simulator "spectre" ?session sess)
  maeSetVar("TB_NAME" "value" ?typeName "test" ?typeValue list(testName) ?session sess)
  maeSetAnalysis(testName "dc" ?enable t ?session sess)
  maeAddOutput("metric" testName ?outputType "point" ?expr "VT(\"/<fixture_node>\")" ?session sess)
  maeSetSpec("metric" testName ?range list("min" "max") ?session sess)
)
```

For transient analyses, pass stop/max step through `?options`, for example `list(list("stop" "TB_TSTOP") list("maxstep" "TB_TSTEP"))`; do not rely on variables alone if the analysis fields are empty.

Use one composable Maestro setup block per testbench group. The final Cadence stage applies all group blocks to one shared Maestro session. Inside each block, use one Maestro test when the group has one compatible analysis/dependency case, or multiple Maestro tests when the `.control` file has multiple incompatible cases. Do not create separate Maestro tests merely for process, temperature, supply, reference, load, or corner dimensions when the analysis definition is the same; represent those dimensions as corners with corner-level `TB_*` overrides.

For any analysis type, split by the smallest set of Maestro analysis definitions needed to preserve the `.control` behavior. Keep dependent measurements together when a derived metric uses them. Different analysis option sets that cannot coexist in one Maestro test need separate tests, but do not split dependent measurements into separate tests unless cross-test derived expressions are verified in `active.state`.

For DC sweeps specifically, use the swept source as the primary split boundary. Different swept sources need different Maestro tests. Opposite sweep directions of the same source may remain in one Maestro test when outputs/specs combine both directions into one derived metric, such as a difference between rising and falling crossings.

For corner setup, build only the dimensions required by the applicable test rows in `verification_plan.md` and `tests/<group>.control`. Resolve process coverage per Maestro test, not once for the whole suite or group. An explicit process subset applies exactly as recorded for that test. `configured_process_corners` expands to every name in `edaHarnessProcessCorners`. If process coverage is not applicable to a test, do not add a process dimension or process model files to that test's corners. When several compatible Maestro tests share a corner, enable it only for the tests whose run matrices contain that condition.

Corner names must use the exact group-scoped format `<group_name>__<condition_key>`. `testName` is the group name supplied by the foundation. Derive `conditionKey` from the applicable condition combination in the current test's run matrix, including process, supply, temperature, and other swept dimensions when present, then prefix it with `testName`. Preserve explicit logical process identifiers exactly; for `configured_process_corners`, preserve the names from `edaHarnessProcessCorners`. Before using an explicit process name, verify that it exists in `edaHarnessProcessCorners`; otherwise stop with a clear configuration mismatch instead of silently substituting another corner. Do not create unscoped Maestro corner names. When one group has multiple Maestro tests, enable each group-scoped corner only for its applicable test names.

`model_bindings.il` defines:

```lisp
edaHarnessProcessCorners
edaHarnessModelsForCorner(cornerName)
```

`edaHarnessProcessCorners` is the catalog of process corners available from the model configuration; it is not an instruction to apply every corner to every test. The function returns an ordered list of `list(modelFile modelSection)` entries for one selected process corner. `modelSection` is `nil` for a sectionless include. Preserve this order and create a separate Maestro model object for every entry.

Useful corner APIs:

```lisp
cornerName = strcat(testName "__" conditionKey)
applicableTests = list(testName)
maeSetCorner(cornerName ?enableTests applicableTests ?enabled t ?session sess)
generatedCornerAssignments = cons(
  list(cornerName applicableTests)
  generatedCornerAssignments
)
maeSetVar("TB_NAME" value ?typeName "corner" ?typeValue list(cornerName) ?session sess)
db = axlGetMainSetupDB(sess)
cornerHandle = axlGetCorner(db cornerName)
axlPutVar(cornerHandle "temperature" temp)
modelIndex = 0
foreach(binding edaHarnessModelsForCorner(proc)
  modelIndex = modelIndex + 1
  model = axlPutModel(cornerHandle sprintf(nil "%s_%d" proc modelIndex))
  axlSetModelFile(model car(binding))
  when(cadr(binding) axlSetModelSection(model cadr(binding)))
  axlSetModelTest(model testName)
  axlSetEnabled(model t)
)
```

Use `maeSetCorner` to create/enable each corner, register the same exact test list in `generatedCornerAssignments`, use `maeSetVar` for corner-level `TB_*` overrides, `axlPutVar(... "temperature" ...)` for native simulator temperature, and model objects only for process corners applicable to each test. The Python helper has already validated absolute paths and file existence; do not repeat filesystem validation in the generated SKILL block.

Use `maeAddOutput(... ?outputType "point" ?expr ... )` first. If this Virtuoso build rejects `?outputType "point"`, omit `?outputType` but keep `?expr`. Do not use `?outputType "expr"` unless you verify the output appears in `active.state`.

Before extracting the reusable block, compare every output path with the matching fixture `.SUBCKT` and the imported cellview. Confirm root node names, imported instance names, and current branch terminals. Seeing the expression in `active.state` or receiving `maestro tmp PASS` proves only that the setup was saved; it does not prove that the referenced signal exists. Fix every guessed or nonexistent hierarchy component before extraction.

For AC waveform outputs, use `?outputType "all"` for traces and `?outputType "point"` for scalar metrics. Working calculator-expression patterns include `db20(...)`, `phase(...)`, `cross(...)`, `value(...)`, `ymin(...)`, and `ymax(...)` around `VF(...)`/`VT(...)` paths.

6. Re-run the temporary setup until it succeeds:

```bash
cd /absolute/path/to/<workspace>/maestro_tmp_<group>
virtuoso -nograph -restore setup_tmp.il
```

If `virtuoso` is absent from the non-interactive `PATH`, use the interactive-shell fallback instead:

```bash
bash -ic 'cd /absolute/path/to/<workspace>/maestro_tmp_<group> && virtuoso -nograph -restore setup_tmp.il'
```

The script is intended to be rerunnable. It recreates `spectre_<group>`, `config_<group>`, and the isolated temporary Maestro view each time. Deleting the temporary Maestro view here does not become part of the extracted group block.

7. Check the result:

```bash
find /absolute/path/to/<workspace>/maestro_tmp_<group>/tmp_<group>_lib -type f | sort
```

Also inspect the Maestro state when needed:

```text
<workspace>/maestro_tmp_<group>/tmp_<group>_lib/<shared_fixture_name>/maestro/
```

Verify that expected analyses, outputs, specs, variables, and corners are present. If a group has multiple Maestro tests, verify each test has the correct analysis options and only the outputs/specs produced by that analysis case. If an output does not appear in `active.state`, fix `maeAddOutput` usage and rerun.

8. Extract the final reusable Maestro block and remove the temporary folder:

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
* Treat `model_bindings.toml` as the user-edited source and `model_bindings.il` as generated output; never edit the generated IL manually.
* Inside `MAESTRO_SETUP`, use the existing variables `lib`, `cell`, `spectreView`, `configView`, `maestroView`, `testName`, `sess`, and `generatedCornerAssignments`; do not hardcode temporary library/cell/view names.
* Format generated SKILL with two spaces per nesting level so the extracted block and final assembled `generate.il` remain readable.
* The extracted block must only add and configure the current group's tests, outputs, specs, variables, and group-scoped corners. It must not delete, open, or save the shared Maestro view.
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

## Stage Boundary

After completing the current group or the complete suite, stop, report the result to the user, and wait for explicit confirmation before invoking any downstream skill.
