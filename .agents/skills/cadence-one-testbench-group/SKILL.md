---
name: cadence-one-testbench-group
description: Export one completed ngspice testbench group into Cadence/Virtuoso Spectre/config/ADEXL/Maestro.
---

# Skill: Cadence One Testbench Group

## Goal

Export one completed ngspice acceptance group into Cadence/Virtuoso.

One iteration = one group:

```text
tests/<group>.sp
tests/<group>.control
→ Cadence wrapper deck including the completed SPICE fixture
→ cdsTextTo5x imported view spectre_<group>
→ config view
→ ADEXL/Maestro setup
→ Maestro netlist-create verification
→ <group>_cadence_status.txt
```

After one group reaches:

```text
overall_status: PASS
```

stop, report briefly, and ask whether to continue with the next group.

Write a final status file only after PASS. If generation, import, setup, launch, or structural verification is blocked, keep diagnostic logs, report the blocker, and do not write a fake PASS or partial final status.

## Inputs

```text
verification_plan.md
testbench_implementation_plan.md
tests/<group>.sp
tests/<group>.control
original Spectre DUT netlist
```

If the group is not explicitly specified, choose the first group in `testbench_implementation_plan.md` without successful Cadence status.

Source of truth for the current group:

```text
tests/<group>.sp
tests/<group>.control
verification_plan.md
testbench_implementation_plan.md
original Spectre DUT netlist
```

Do not modify source inputs.

## Outputs

Create/update only current group artifacts:

```text
cadence_export/groups/<group>/generate.il
cadence_export/groups/<group>/verify.il
cadence_export/groups/<group>/generate.log
cadence_export/groups/<group>/verify.log
cadence_export/groups/<group>/generate.launch.log
cadence_export/groups/<group>/verify.launch.log
cadence_export/groups/<group>/<group>_cadence_status.txt
cadence_export/generated_support/cadence_dut.scs
cadence_export/generated_support/<group>.scs
cadence_export/<generated_library_name>/
```

Cadence library structure:

```text
cadence_export/<generated_library_name>/<group>_top/
  spectre_<group>/
  config/
  adexl/
  maestro/
```

Use one generated Cadence library for the suite. Use one cell per group. Do not create one library per testbench.

## Hard rules

* One group per iteration.
* Use real Cadence/OA objects and public SKILL/ADE/MAE/ASI APIs.
* Do not hand-edit `maestro.sdb`, `active.state`, `data.sdb`, or generated `input.scs`.
* Do not create fake `.oalib`, fake config, fake status, dummy PASS, or placeholder project.
* Do not use schematic/symbol/CDF/analogLib flow unless explicitly requested.
* Use the user-provided original Spectre DUT netlist as the Cadence DUT.
* Do not use mock/dev DUT as the Cadence DUT.
* Do not use generic one-size decks.
* Analysis, measurements, checks, cases/corners, and simulator options belong in ADEXL/Maestro.
* The imported Spectre view must contain a Cadence wrapper that includes the completed `tests/<group>.sp` fixture in SPICE mode.
* Do not manually translate fixture topology into Spectre unless direct SPICE-mode inclusion is proven impossible; if impossible, stop and report the blocker.
* Do not transfer `tests/<group>.control`, ngspice runner logic, CSV writing, `RESULT`, `FAIL`, `SUMMARY`, `wrdata`, `quit`, or mock includes into Cadence.
* Do not run full Spectre simulation unless explicitly requested.
* Local PASS means structural/Maestro export success, not proof that customer PDK model files exist locally or that full Spectre simulation passes.
* PASS requires Maestro netlist-create to produce `input.scs` that includes or contains the real testbench fixture and original Spectre DUT circuit.

## Primary Cadence backend

Use this no-schematic backend:

```text
1. Generate Cadence wrapper deck:
   cadence_export/generated_support/<group>.scs

2. The wrapper deck must include:
   - original Spectre DUT support in Spectre mode;
   - exact completed fixture tests/<group>.sp in SPICE mode.

3. Import the wrapper deck with cdsTextTo5x:
   view = spectre_<group>

4. Create config pointing to spectre_<group>.

5. Create ADEXL/Maestro setup pointing to that config.

6. Run Maestro netlist-create verification with maeCreateNetlistForCorner or equivalent saved-Maestro-test API.

7. Verify generated input.scs includes spectre_<group>/spectre.scs or contains equivalent imported circuit, reaches tests/<group>.sp fixture intent, and reaches the original Spectre DUT support.
```

Use `cdsTextTo5x` from SKILL via `system(...)`:

```bash
cdsTextTo5x -LIB <lib> -CELL <group>_top -VIEW spectre_<group> -LANG spectre <generated_group_deck.scs>
```

Check return status and import log. Do not continue if import failed.

Final verification must netlist the saved Maestro setup/config/test. A standalone raw OCEAN netlist is not enough as final proof.

## DUT handling

Cadence DUT = user-provided original Spectre DUT netlist.

If original DUT already has the required public subckt and pin order, use it directly through `cadence_export/generated_support/cadence_dut.scs`.

If original DUT is a top-level Spectre netlist without public reusable subckt, create:

```text
cadence_export/generated_support/cadence_dut.scs
```

The support file must:

```text
preserve original DUT lines and continuation "\"
create public subckt with pin order from verification plan
close wrapper before non-DUT tail sections, for example:
  simulatorOptions, modelParameter, element, outputParameter,
  designParamVals, primitives, subckts, saveOptions
not modify original DUT file
```

When copying lines read by SKILL `gets(line port)`, write raw lines as:

```lisp
fprintf(outPort "%s" line)
```

Do not write `"%s\n"` for already-read lines.

Reject:

```spectre
... \
    
    continued_parameter=...
```

DUT support sanity must verify:

```text
public DUT subckt exists
no tail sections leaked into public subckt
no blank line after continuation "\"
original file unchanged
mock/dev DUT not used as Cadence DUT
```

## Generated Cadence wrapper deck

Generate:

```text
cadence_export/generated_support/<group>.scs
```

The wrapper deck preserves the completed fixture by including exact `tests/<group>.sp` in SPICE mode.

Required shape:

```spectre
simulator lang=spectre
include "<absolute_or_valid_path_to/cadence_dut.scs>"

simulator lang=spice
.include "<absolute_or_valid_path_to/tests/<group>.sp>"
simulator lang=spectre
```

Rules:

* Do not include `mock_device.sp`.
* Do not include `tests/<group>.control`.
* Do not include ngspice `.control` / `.endc` logic.
* Do not manually rewrite source/load/stimulus topology from `tests/<group>.sp` into Spectre.
* Do not create an empty `subckt <group>_top ... ends <group>_top` as the only imported design.
* If `cdsTextTo5x` requires a top design wrapper, the wrapper must be reachable and must include or instantiate the real fixture circuit; it must not be an empty placeholder.
* Do not insert `global 0` unconditionally. Preserve global statements from the original DUT/support netlist. If a generated wrapper truly needs a global statement, emit it once near the beginning and verify it is required.
* Do not put case-variable defaults in the imported deck when Maestro sets those variables.

The group deck must not contain:

```text
.control
.endc
ngspice RESULT/SUMMARY echo logic
quit
wrdata/write raw
op/tran/ac commands
saveOptions
mock_device.sp
```

`save` lines are optional; Maestro outputs/checks own observability.

## Imported Spectre view

Import with `cdsTextTo5x` into:

```text
<lib>/<group>_top/spectre_<group>
```

Verify:

```text
view directory exists
netlist.oa exists
spectre.scs exists or valid symlink exists
cdsTextTo5x log shows success
view is visible in Library Manager
imported view includes or preserves the Cadence wrapper deck
wrapper reaches cadence_dut.scs
wrapper reaches tests/<group>.sp in SPICE mode
mock_device.sp is not included
```

If `spectre.scs` is a symlink, verify target exists. Avoid broken symlinks.

## Config view

Create:

```text
<lib>/<group>_top/config
```

It must point to imported view:

```text
design <lib>.<group>_top:spectre_<group>
viewlist spectre_<group> spectre schematic veriloga ahdl
stoplist spectre_<group> spectre
```

Equivalent SKILL intent:

```lisp
cfg = hdbOpen(lib cell "config" "w" "CDBA")
hdbSetTopCellViewName(cfg lib cell "spectre_<group>")
hdbSetDefaultViewListString(cfg "spectre_<group> spectre schematic veriloga ahdl")
hdbSetDefaultStopListString(cfg "spectre_<group> spectre")
hdbSave(cfg)
hdbClose(cfg)
```

Then verify:

```lisp
simCheckViewConfig(lib cell "config")
```

## ADEXL/Maestro setup

Create ADEXL and migrate to Maestro:

```text
<lib>/<group>_top/adexl
<lib>/<group>_top/maestro
```

Create tests, variables, analyses, outputs, specs/checks through public APIs.

## Run cases and Corners

Represent the ngspice run matrix and deferred PVT intent in Maestro.

For small named explicit cases with different requirements, different outputs, or clearly separate operating modes, explicit per-case tests are acceptable.

For `loop_matrix`, PVT-like matrices, temperature/reference/ramp matrices, or any large Cartesian parameter matrix, use:

```text
one Maestro test
N Maestro corners
unique outputs/checks created once
```

Do not create one Maestro test per matrix point for large matrices.

Expected GUI shape for a matrix group:

```text
Tests:   1
Corners: N
Outputs: one row per metric, not N duplicates
```

Example shape:

```text
1 test
N corners
M outputs
M checks/specs
N × M metric evaluations at run time
```

Corner names must be deterministic and readable, for example:

```text
<group>__run_<index>_<short_parameter_summary>
```

Create corner variable overrides through public APIs, for example:

```text
maeSetCorner(...)
maeSetVar(... ?typeName "corner" ?typeValue list(cornerName) ...)
```

or equivalent AXL/MAE APIs.

A review CSV such as `corners_matrix.csv` may be generated, but the saved Maestro setup must contain real corners; a CSV alone is not enough.

For process/model corners:

* Use process-corner intent from `verification_plan.md` / `testbench_implementation_plan.md`.
* Default process corner identifiers are `tt`, `ff`, `ss`, `fs`, `sf`.
* Use runtime environment variable reference `$LIB_PATH` as the model root.
* Default per-corner model reference is `$LIB_PATH/<corner>.scs` unless the specification or project files define another concrete convention.
* Create real Maestro corners/model references for each required process corner.
* Do not require `LIB_PATH` to be defined locally during structural export.
* Do not require `$LIB_PATH/<corner>.scs` files to exist locally during structural export.
* Do not call `fileExists` or equivalent local path validation on unresolved `$LIB_PATH` model references.
* Do not fake process model sections and do not silently drop process coverage.
* If Cadence APIs cannot store the `$LIB_PATH/<corner>.scs` references or cannot create the required corners, do not write PASS status; keep logs and report the blocker.

Cadence PVT matrix must include real process-corner entries where the verification plan preserves process coverage. For example:

```text
process × simulator_temperature × public-pin/reference/supply/ramp dimensions
```

## Test intent extraction

Extract from `.sp`, `.control`, and plans:

```text
fixture topology and stimulus from tests/<group>.sp
DUT connections
run cases / loop matrix from tests/<group>.control and plans
variables and bindings
analysis: op/dc/tran/ac
AC sweep shape and point density
temperature / simulator options
measurements
derived metrics
checks / limits
saved signal intent
```

Do not transfer ngspice runner wrapper as Cadence logic:

```text
echo
RESULT/SUMMARY
CSV writing
quit
wrdata/write raw
```

Transfer only test intent.

## Analysis

Map ngspice analysis into Maestro/ADE:

```text
op     → operating point / dc operating point
dc     → DC analysis
tran   → transient analysis
ac     → AC analysis
```

Do not put analysis commands into imported Spectre deck.

For transient groups, set step/stop through Maestro analysis fields, not only as design variables.

If source intent has:

```spice
tran <step_expr> <stop_expr>
```

then saved Maestro state and generated `input.scs` must contain equivalent transient analysis fields, for example:

```spectre
tran tran stop=<stop_var_or_expr> step=<step_var_or_expr> ...
```

or equivalent local Spectre syntax.

It is not enough for `<step_var>` and `<stop_var>` to exist as parameters if the `tran` line does not use them.

For AC groups, set sweep type and point density in saved AC analysis, not only as design variables.

Example:

```spice
ac dec <points_per_decade> <start_freq> <stop_freq>
```

must become saved AC intent equivalent to:

```text
start = <start_freq>
stop = <stop_freq>
sweep = logarithmic/decade
points per decade = <points_per_decade>
```

Do not mark analysis semantics PASS if saved state or generated `input.scs` loses required step/stop/sweep settings from source intent.

## Variables and bindings

Design variables must exist in Maestro/ADEXL.

Examples:

```text
supply/reference/control values
ramp time
analysis step/stop
AC sweep values
temperature trace variables
limits
```

Bindings such as:

```text
tstep = ramp_time / 400
tstop = 2 * ramp_time
```

must become Maestro variables or valid analysis expressions, and analysis fields must actually use them.

Do not leave analysis fields referring to undefined names.

If included `tests/<group>.sp` uses nominal source defaults, the Maestro setup must override the corresponding source/stimulus parameters or otherwise prove that each case value reaches generated `input.scs`. Do not report PASS for case variables that exist only as unused Maestro variables.

## Temperature

If `.control` or plan has temperature cases, do not store temperature only as a design variable.

Recognize temperature-like names such as:

```text
temp
tempval
temp_c
temperature
```

For each test or corner, set actual Spectre simulator option `temp`.

Examples:

```text
case temp=<T> → simulator option temp=<T>
```

A traceability variable may also exist, but it is not sufficient unless netlist-create proves it drives `simulatorOptions temp`.

Do not use only `tnom`.

Verification must prove generated `input.scs` has correct simulator `temp` for each tested case/corner, or for representative temperature values in very large matrices.

## Measurements and outputs

Every measurement becomes a real Maestro output.

Rules:

```text
output name matches metric name
no placeholder 0
no comment-only measurement
current metrics reference real supply/source branch
max/min/avg metrics preserve source signal and window
threshold/crossing metrics preserve observed signal, threshold expression, edge, occurrence, reported swept signal
derived metrics reference existing outputs
checks/specs reference real outputs
```

Examples:

```text
I_<supply> = current through the corresponding source, with sign matching source intent
V_<signal> = voltage of a public observed signal
<derived_metric> = expression over existing outputs
```

## Threshold/crossing measurements

For ngspice measurements like:

```spice
meas tran <metric> FIND v(<swept>) WHEN v(<observed>)=<threshold> FALL=<n>
meas tran <metric> FIND v(<swept>) WHEN v(<observed>)=<threshold> RISE=<n>
```

preserve:

```text
observed waveform/relation
threshold expression
edge = falling/rising
occurrence = FALL/RISE number
reported value = swept signal value at crossing
```

Do not assume one fixed `cross(...)` argument order for all Cadence installations.

Valid implementations include:

```text
cross(waveform occurrence edge ...)
cross(waveform threshold occurrence edge ...)
helper function with explicit threshold/edge/occurrence
```

Use local Cadence calculator syntax that opens correctly in ADE/Maestro and preserves source meaning.

For dynamic thresholds, use waveform expressions, for example:

```text
<scale> * VT("/<signal>")
```

or `VF(...)` if that is the local expression convention.

Do not reject an expression only because it omits explicit zero threshold if local Cadence `cross()` syntax uses nth-crossing form.

Verification must check:

```text
outputs exist
edge and occurrence are preserved
threshold expression is present
reported swept signal is correct
derived metrics exist
checks reference outputs
```

## Maestro netlist-create verification

`verify.il` must do more than open Maestro.

It must run Maestro/ADE netlist-create for the saved setup:

```lisp
maeCreateNetlistForCorner(...)
```

or the closest public API that netlists the saved Maestro test/config.

For explicit-test mode, netlist each test.

For corner-matrix mode:

```text
netlist all corners when practical
for very large matrices, netlist deterministic representative corners covering:
  all process corners when process coverage is present, or a documented representative subset only when netlisting all is impractical
  min/nom/max temperature when present
  endpoints of each sweep dimension
  at least one nominal/central point
always verify all corner metadata exists
```

Verification steps:

```text
open saved Maestro setup
trigger Maestro netlist-create
find generated netlist/input.scs
verify input.scs is not options-only
verify input.scs includes spectre_<group>/spectre.scs or contains equivalent imported circuit inline
inspect included spectre.scs too
verify wrapper includes or preserves tests/<group>.sp fixture intent
verify mock_device.sp is not included
verify original Spectre DUT support is included
verify group-specific design markers exist
verify top-level design circuit is reachable
verify case/corner variables and simulator temp appear in input.scs when applicable
verify process corner names and `$LIB_PATH/<corner>.scs` model references are encoded when process coverage is applicable
do not require local expansion of `LIB_PATH`
do not require local model files to exist
verify required analysis settings appear in input.scs
```

PASS requires design markers derived from the current group deck and plan, for example:

```text
DUT instance name
DUT subckt/model name
expected source/load/stimulus instance names
expected public signal names
exact fixture path tests/<group>.sp or imported equivalent
```

The verifier must derive these markers from:

```text
cadence_export/generated_support/<group>.scs
tests/<group>.sp
tests/<group>.control
verification_plan.md
testbench_implementation_plan.md
```

For transient groups with explicit step/stop intent, verification must fail if:

```text
saved Maestro transient analysis has empty stop/step fields
generated input.scs tran line lacks stop/step
step/stop variables exist but are not used by the tran analysis
```

FAIL if `input.scs` contains only:

```text
parameters
simulatorOptions
dcOp/tran/ac
info statements
saveOptions
```

## Cadence launch preflight

Before running `generate.il` or `verify.il`, identify the working Cadence launch command for the local environment.

Rules:

* Run Virtuoso from the task workspace through `bash -lc`.
* Use the Cadence wrapper found by `command -v virtuoso`; do not call raw Cadence binaries directly.
* Do not bypass the wrapper unless the wrapper-provided runtime environment is explicitly reproduced.
* Prefer `virtuoso -nograph -restore ... -log ...`.
* Keep `DISPLAY` and `XAUTHORITY` unchanged by default.
* Use `virtuoso -nographE` only as a fallback, not as the default.
* If `-nograph` fails with Xvfb/socket/lock errors before SKILL restore starts, retry once with `CDS_XVFB_AUTOCLEAN=all CDS_XVFB_MAXTRIES=2`.
* Do not use `CDS_XVFB_OPTIONS="-nolisten tcp"` unless it is known to work in the local wrapper.
* Capture wrapper stdout/stderr separately from the Cadence `-log` file because wrapper failures can happen before Cadence creates the requested log.
* Declare a Cadence launch blocker only after trying the wrapper through `bash -lc`, default `-nograph`, the Xvfb autoclean retry when applicable, and any known project/local launcher found in the workspace.

## Validation commands

Run from the task workspace using the selected Cadence launch command.

Default command template:

```bash
bash -lc 'cd <workspace> && virtuoso -nograph -restore cadence_export/groups/<group>/generate.il -log cadence_export/groups/<group>/generate.log' > cadence_export/groups/<group>/generate.launch.log 2>&1

bash -lc 'cd <workspace> && virtuoso -nograph -restore cadence_export/groups/<group>/verify.il -log cadence_export/groups/<group>/verify.log' > cadence_export/groups/<group>/verify.launch.log 2>&1
```

Fallback for Xvfb/socket/lock failures before SKILL restore:

```bash
bash -lc 'cd <workspace> && CDS_XVFB_AUTOCLEAN=all CDS_XVFB_MAXTRIES=2 virtuoso -nograph -restore cadence_export/groups/<group>/generate.il -log cadence_export/groups/<group>/generate.log' > cadence_export/groups/<group>/generate.launch.log 2>&1

bash -lc 'cd <workspace> && CDS_XVFB_AUTOCLEAN=all CDS_XVFB_MAXTRIES=2 virtuoso -nograph -restore cadence_export/groups/<group>/verify.il -log cadence_export/groups/<group>/verify.log' > cadence_export/groups/<group>/verify.launch.log 2>&1
```

Generator must print:

```text
CBE_GROUP_START <group>
CBE_GROUP_COMPLETE_PASS <group>
```

Verifier must print a group-specific PASS marker after all structural/Maestro checks pass.

If Virtuoso stays alive after completion marker, terminate it cleanly in the runner.

Do not treat a launch as successful unless the Cadence `-log` file or captured launch log proves that SKILL restore started and reached the expected marker.

## Required checks

All must pass:

```text
source files exist
Cadence launch command selected through bash -lc
Cadence wrapper used, not raw binary
generate launch stdout/stderr captured
verify launch stdout/stderr captured
generate SKILL restore reached expected markers
verify SKILL restore reached expected markers
original Spectre DUT selected, not mock
process model references use $LIB_PATH when process corners are required
local LIB_PATH value is not required for structural export
local model file existence is not required for structural export
generated library exists
cds.lib updated without deleting unrelated DEFINE lines
cadence_dut.scs exists when needed
DUT support sanity passes
generated wrapper .scs exists
wrapper includes cadence_dut.scs
wrapper includes exact tests/<group>.sp in SPICE mode
wrapper does not include mock_device.sp or tests/<group>.control
cdsTextTo5x import passes
imported spectre_<group> view exists
config points to imported view
simCheckViewConfig passes
ADEXL setup exists
Maestro setup opens
expected tests exist
expected corners exist for matrix groups
process corners exist when required
case/corner variables applied
simulator temp applied when needed
analysis configured
transient stop/step semantics configured when needed
AC sweep semantics configured when needed
outputs exist
derived outputs exist when needed
checks reference real outputs
Maestro netlist-create passes
generated input.scs includes real testbench/DUT circuit
generated input.scs does not include mock_device.sp
top-level design circuit is reachable
fresh-open verification passes
```

Do not run full Spectre simulation unless requested.

## Status file

Write final status only after success:

```text
cadence_export/groups/<group>/<group>_cadence_status.txt
```

Required shape:

```text
group: <group>
library: <libName>
cell: <group>_top
imported_view: spectre_<group>
generated_deck: cadence_export/generated_support/<group>.scs
included_fixture: tests/<group>.sp
fixture_language_mode: spice
cadence_launch: PASS
cadence_wrapper_used: PASS
generate_restore: PASS
verify_restore: PASS
dut_support: PASS
original_spectre_dut_selected: PASS
mock_dut_not_used: PASS
cdsTextTo5x_import: PASS
config_points_to_imported_spectre_view: PASS
config_view: PASS
adexl_setup: PASS
maestro_setup: PASS
maestro_tests_expected: <N>
maestro_tests_created: <N>
run_cases_expected: <N>
run_cases_created: <N>
measurements_expected: <N_unique_outputs>
measurements_created: <N_unique_outputs>
checks_expected: <N_unique_checks>
checks_created: <N_unique_checks>
sim_check_view_config: PASS
mae_open_setup: PASS
maestro_netlist_create: PASS
netlist_contains_design: PASS
netlist_contains_fixture: PASS
netlist_contains_original_dut: PASS
netlist_excludes_mock: PASS
top_level_design_circuit: PASS
fresh_open: PASS
audit: PASS
generate_log: cadence_export/groups/<group>/generate.log
verify_log: cadence_export/groups/<group>/verify.log
generate_launch_log: cadence_export/groups/<group>/generate.launch.log
verify_launch_log: cadence_export/groups/<group>/verify.launch.log
overall_status: PASS
```

For corner-matrix groups, also include before the final `overall_status: PASS` line:

```text
corners_expected: <N>
corners_created: <N>
corner_matrix: PASS
metric_evaluations_expected: <N_corners * N_outputs>
```

If applicable, include before the final `overall_status: PASS` line:

```text
process_corners: PASS
model_env_references_created: PASS
model_paths_use_LIB_PATH: PASS
temperature_cases: PASS
threshold_crossings: PASS
tran_analysis_semantics: PASS
ac_analysis_semantics: PASS
```

Do not include unrelated status fields.

Do not include local model-file existence as a PASS field unless full simulation was explicitly requested and actually performed.

The final non-empty line of the status file must be:

```text
overall_status: PASS
```

Do not write final status with any non-PASS state.

## Cleanup

After current group passes, remove only temporary clutter for that group:

```text
*.cdslck
*.cdslck.*
failed attempt files
temporary logs
stale generated views not used by final config
```

Keep generated library/views, `.il`, logs, status, generated support decks, launch logs, and netlist-create evidence paths.

## Final response after one group

Reply briefly after PASS:

```text
group implemented
library/cell/imported view
fixture included in SPICE mode
original Spectre DUT support used
process model references encoded through $LIB_PATH when applicable
Cadence launch command used
tests/corners/cases count
outputs/checks count
status path
overall_status: PASS
next group
ask whether to continue
```

Do not continue to the next group without user confirmation.