---
name: create-ngspice-testbench-group-from-implementation-plan
description: Create or revise one ngspice testbench group from a completed verification_plan.md, completed testbench_implementation_plan.md, and completed mock DUT artifacts. The completed group includes its HDL21 source, generated SPICE fixture, ngspice control file, simulation log, metrics CSV, and any planned sample or waveform CSV files, with the required run matrix executed and every metric reported as pass, fail, or explicitly unmeasurable. Use when the user requests an ngspice acceptance test, or when the plans and mock DUT are complete and a planned group is missing, incomplete, or inconsistent with them. Process exactly one group per invocation and stop after reporting it.
---

# Implement Ngspice Testbench Group

## Execution Boundary

Execute only this skill in the current turn and implement only one group. A broad request for the whole workflow or all testbenches does not authorize another group or a downstream stage. If the skill pauses for user input, the answer authorizes only completion of the current group. After reporting the result, wait for a new user message explicitly requesting continuation.

## Purpose

Sequentially implement all testbench groups from `testbench_implementation_plan.md`.

In one iteration, implement only one current group, bring it to a working state in ngspice, report back to the user, and ask whether to continue with the next group.

## Inputs

* `verification_plan.md` — DUT contract, requirements, conditions, metrics, and pass/fail limits.
* `testbench_implementation_plan.md` — shared top-level fixture subckt name, fixture groups, planned files, CSV outputs, and implementation order.
* `mock_device.sp` — generated mock DUT netlist from the previous stage.

## Selecting the Current Group

Determine the current group from `Implementation Order`.

If the user explicitly specified a group name, implement that group.

If no group is specified, choose the first group in order that does not have a successful set of planned files, ngspice log, and metrics CSV.

If all groups are already implemented and verified, report that the testbench suite is complete.

## What to Create in One Iteration

For the selected group, create or update only its planned files from `testbench_implementation_plan.md`, usually:

```text
tests/<group_name>.py
tests/<group_name>.sp
tests/<group_name>.control
results/<group_name>_metrics.csv
results/<group_name>_samples.csv / results/<group_name>_waveforms.csv, if planned
results/<group_name>.log
```

Each group has its own separate HDL21 Python file. Do not create one shared generator for all groups.

## Shared Fixture Naming Contract

Read `Shared Top-Level Fixture Subckt` from the `Fixture Naming Contract` in `testbench_implementation_plan.md` before implementing the current group. If it is missing or ambiguous, stop and report the blocker instead of deriving a name from the group.

Every group must use that exact shared name for its importable top-level fixture `.SUBCKT`. Group names still determine the `.py`, `.sp`, `.control`, log, and CSV file names. The shared fixture name does not change the DUT subckt name or public DUT contract.

## HDL21 Fixture Requirement

`tests/<group_name>.py` must actually use HDL21 to generate a reusable electrical fixture and export `tests/<group_name>.sp`.

Main rule: the exported `tests/<group_name>.sp` must be a complete testbench fixture, not a thin DUT wrapper and not a DUT-binding wrapper.

Rules:

* `tests/<group_name>.py` must generate the circuit fixture through HDL21 modules/instances/primitives/helpers.
* The exported `tests/<group_name>.sp` must contain the DUT instance by public contract and the electrical setup required for this group: supply/reference/control sources, loads, capacitors, feedback connections, stimulus elements, named nodes, and probe points where applicable.
* The exported fixture must instantiate the DUT, but must not include/source `mock_device.sp` or any DUT implementation netlist.
* Do not put `.include`, `.lib`, or `source` statements for `mock_device.sp`, PDK/foundry models, or process corners into `tests/<group_name>.sp`.
* For OP/DC/static groups, the fixture should usually contain all static sources, loads, feedback connections, and the DUT instance.
* For TRAN/AC/waveform-like groups, the fixture must contain the stimulus/source elements required for the analysis, for example parameterized PULSE/PWL/AC/DC sources, loads/caps, and stable probe nodes.
* `.control` must not be the primary place where the testbench circuit topology is created. Do not move supply/reference/control/stimulus sources into `.control` just because it is easier.
* `.control` must control the already-created fixture: include/source files, `alterparam`/`alter`, `reset`, analysis commands, measurements, derived metrics, pass/fail, `RESULT`/`FAIL`/`SUMMARY`, and CSV/waveform exports.
* Export the SPICE fixture through the HDL21 netlisting/export flow.
* Do not replace HDL21 generation with full handwritten SPICE text generation.
* Do not use HDL21 only as a decorative port-list declaration on top of a handwritten fixture.
* Do not edit generated SPICE manually.
* Do not insert process-corner model placeholders into generated `tests/<group_name>.sp`; exported SPICE fixtures must stay clean and reusable.

## Fixture Parameterization for Cadence Reuse

The generated fixture must expose stable parameters for values that later become ngspice run variables or Cadence/Maestro design variables.

Rules:

* Any public-pin source value, stimulus value, load value, ramp timing, analysis timing, or control value that appears in a run matrix, sweep, corner, or Cadence-export case must be emitted as a named fixture parameter with a nominal default.
* Use stable generic parameter names with a `TB_` prefix, derived from the public pin or stimulus function, for example `TB_<PIN>`, `TB_<PIN>_DC`, `TB_<STIM>_RAMP`, `TB_TSTEP`, or `TB_TSTOP`.
* Do not hard-code swept or corner-controlled source/stimulus values directly into voltage/current/source instances.
* In the exported SPICE fixture, source/stimulus values must reference the named parameters, for example `.param TB_<NAME>=<nominal>` and `dc 'TB_<NAME>'`, or an equivalent ngspice-compatible syntax generated by `tests/<group_name>.py`.
* True fixed topology constants that are never swept, never used as run variables, and never needed as Cadence variables may remain hard-coded.
* Do not use hierarchical source instance paths as the primary variable interface for values that can be represented by fixture parameters.
* The same fixture parameter names must be used by `.control` run loops and preserved for Cadence/Maestro export.

Raw-SPICE exception:

* If a required simulator-specific element is not expressed well by pure HDL21 primitives, for example a PULSE/PWL source, behavioral helper, special probe/helper element, or fixture parameter declaration, the Python generator may add a small documented raw-SPICE fragment to the generated `tests/<group_name>.sp`.
* This raw-SPICE fragment must be minimal, local to the fixture, and added by `tests/<group_name>.py` when generating `.sp`.
* The raw-SPICE fragment must not include/source `mock_device.sp`, DUT implementation netlists, or PDK/foundry models.
* The final `tests/<group_name>.sp` must still contain a complete reusable fixture with stimulus/source elements.
* Do not use raw-SPICE fragments in `.control` as a way to describe the main circuit topology.

Cadence-importable fixture shape:

* The exported `tests/<group_name>.sp` must contain one importable top fixture `.SUBCKT` named exactly as `Shared Top-Level Fixture Subckt` in `testbench_implementation_plan.md`; it owns the complete active testbench topology needed for the current group.
* The importable top fixture `.SUBCKT` must include the DUT instance, supply/reference/control sources, transient/AC stimulus sources, loads/caps, feedback connections, behavioral/probe helper elements, and named observed nodes required by the group.
* For ngspice activation, the area outside `.SUBCKT ... .ENDS` may contain parameter defaults, comments, and one top-level `X...` instance of the importable fixture.
* Do not leave required active topology as loose top-level elements after `.ENDS`: voltage/current sources, behavioral sources, probe/helper elements, loads/caps, or fixture instances that are required for the test must be inside the importable fixture `.SUBCKT`.
* Internal reusable subfixtures are allowed, but one group-level importable fixture must assemble the complete active testbench.

Before finishing the fixture, check that:

* the group electrical setup can be understood by opening `tests/<group_name>.sp`, without reading measurement loops in `.control`;
* `.sp` contains sources/stimulus/load/probe elements if the group needs them;
* `.sp` contains the DUT instance by public contract;
* `.sp` contains one importable group-level fixture `.SUBCKT` with the complete active testbench topology;
* the importable top fixture `.SUBCKT` name exactly matches `Shared Top-Level Fixture Subckt` from `testbench_implementation_plan.md`;
* no required active topology remains loose outside `.SUBCKT ... .ENDS`, except for one top-level ngspice activation instance;
* swept and corner-controlled source/stimulus/control values are exposed as stable `TB_*` fixture parameters;
* `.sp` does not contain `mock_device.sp` includes, DUT implementation netlist includes, PDK/foundry model includes, or process-corner model placeholders;
* `.control` does not contain the main set of V/I source declarations that should be part of the reusable fixture;
* `.control` changes fixture parameters instead of recreating fixture topology.

## Ngspice Control Requirement

`tests/<group_name>.control` contains simulator-side logic:

* include/source `mock_device.sp`;
* include/source the generated SPICE fixture `tests/<group_name>.sp`;
* do not add active `.include` or `.lib` lines for process-corner models;
* add one of these inactive model placeholders near the includes, based on process coverage in `verification_plan.md`.

For explicit logical corners:

```spice
* Process-corner model placeholder (inactive for mock DUT):
* Before running with a real DUT, load the required process models here.
* Planned logical corners: <comma-separated selected logical corners>
```

For `configured_process_corners`:

```spice
* Process-corner model placeholder (inactive for mock DUT):
* Before running with a real DUT, load the required process models here.
* Logical corners are deferred to the Cadence model configuration.
```

* run matrix, loops, `alterparam`/`alter`, `reset`;
* set executable run values through named fixture parameters where available, preferably using `alterparam` plus `reset`;
* analysis commands: OP/DC/TRAN/AC/MC;
* measurements and derived metrics;
* pass/fail checks;
* `RESULT` / `FAIL` / `SUMMARY` lines;
* writing metrics CSV and planned samples/waveform CSV.

Python must not compute physical metrics or pass/fail.

Acceptance metrics must be measured by ngspice from simulated values or `meas` results. Do not replace an acceptance metric with a constant, mock-only shortcut, or assumed pass value. If the generated mock cannot make a metric measurable, emit an explicit unmeasurable result for that metric instead of a passing result; use `pass=0`, `value=unmeasurable`, and a specific metric-dependent reason in the log/CSV.

For metrics CSV, simulator-side text output may be used. For waveform/sample data, prefer `wrdata` or another simulator-native export.

Do not create separate SPICE decks for each run/corner/condition.

## Run Matrix and Coverage Rules

The executable ngspice run matrix must match the current group coverage from `testbench_implementation_plan.md` and the corresponding rows in the `Acceptance Test Matrix` in `verification_plan.md`, except for deferred process-corner coverage with the generated mock.

Rules:

* first identify the concrete verification-plan items covered by the current group;
* for each item, use its `Test Condition / Stimulus`, `Condition Coverage`, measurement method, and acceptance criteria from `verification_plan.md`;
* use `Operating Conditions` and `Presets` from `verification_plan.md` as the source of values for the presets/runs specified in the test matrix;
* map executable run values to stable fixture parameters when they drive fixture sources, controls, loads, timing, or stimulus;
* do not add coverage beyond what is specified in the test matrix;
* do not remove executable public-pin, supply, reference, control, stimulus, or simulator-temperature coverage;
* exclude process-corner dimensions from the executable ngspice run matrix and preserve them as downstream coverage intent;
* do not require PDK/foundry model files or active process-corner model includes for ngspice runs;
* do not emit per-process-corner `RESULT` or CSV rows in ngspice runs;
* if the verification plan specifies a nominal-only run, run nominal only;
* if the verification plan specifies a sweep over one executable group of conditions, change only that group and keep all other executable conditions nominal/fixed;
* if the verification plan specifies full-combination coverage, run the full combination of executable ngspice dimensions for this stage;
* if the implementation plan and verification plan disagree on executable coverage, use the verification plan as the source of truth and state an assumption/blocker;
* expected run count must be calculated before writing `.control` and must match `SUMMARY runs=<n>`;
* expected run count is calculated after excluding deferred process-corner dimensions.

## Requirement-Specific Setup Rules

A fixture group may combine several requirements, but this does not mean they are measured in the same simulator run.

Before writing `.control`, create a brief internal run table for the current group:

```text
requirement -> run condition -> measured metric -> source/probe -> limits
```

Rules:

* measure each requirement only under its own `Test Condition / Stimulus` from `verification_plan.md`;
* if two requirements have different fixed bias values, supply values, mode-control values, load values, stimulus, or measurement window, they must be different runs/cases inside one group;
* a shared run may be used only if all driven conditions for those requirements are truly identical;
* do not measure a metric for one requirement in a run configured for another requirement;
* if one OP/TRAN/AC run prints several RESULT rows, each RESULT must correspond to the conditions of its own requirement;
* `parameters="..."` in RESULT/CSV must list all requirement-relevant driven values so it is clear that the measurement condition matches the verification plan;
* include the named fixture parameter values in `parameters="..."` when those parameters control the run condition;
* with deferred process coverage, do not list a specific process corner as an executed parameter;
* if two requirements need the same fixture but different bias cases, use one fixture and several cases/loops in `.control`.

Before the final run of the current group, check:

* the list of actual `RESULT` rows;
* the list of parameters in each run;
* actual run coverage against the executable ngspice dimensions from the verification plan;
* whether the `.control` process-corner placeholder lists explicit logical corners or states that they are deferred to the Cadence model configuration;
* whether each RESULT matches its requirement-specific condition;
* whether `SUMMARY runs=<n>` matches the expected run count.

## Control-File Quality Rules

The control file must be compact, readable, and maintainable.

Rules:

* if the group has more than one similar run, use `foreach`/loops;
* do not copy large identical blocks for each run if only a parameter differs;
* identical `alter/reset/analysis/measure/RESULT/FAIL/CSV` patterns must be implemented inside a loop as much as ngspice control syntax allows;
* for different requirement cases with similar setup, use a shared template and short loops/cases, not long copy-paste blocks;
* if the measurement formula truly differs, it may be split into several short blocks;
* create the CSV header only once;
* RESULT/FAIL/log lines and CSV rows must have the same field set across all runs in one group;
* do not leave dead code, debug-only echoes, temporary comments, unused variables, or old alternative measurements;
* if a loop is impossible because of ngspice syntax limitations, explicitly state the reason in a comment in the control file.
* do not use constants such as `let metric = 100` as substitutes for acceptance measurements. Constants may be used only for limits, fixed stimulus values, or intermediate math that is not reported as a measured acceptance metric.

Shell commands inside `.control` must not be the main logic.

Allowed:

* simple initialization/cleanup of output CSV;
* simple writing of a CSV row, if this is more stable for ngspice.

Not allowed:

* computing physical metrics in shell;
* doing pass/fail checks in shell;
* creating complex file architecture from `.control`;
* using shell as a replacement for ngspice measurements.

## CSV and Waveform Output Rules

Metrics CSV, samples CSV, and waveform CSV must be suitable for automatic reading by the report/analysis pipeline.

Rules:

* every planned CSV must be a real comma-separated CSV with consistent delimiter `,`;
* header and data rows must use the same delimiter;
* do not mix a comma-separated header with whitespace-separated data;
* if ngspice `wrdata` writes whitespace-separated output, either configure/build the export so the final planned file is a valid CSV, or use `.control` text output to write comma-separated rows;
* waveform/sample CSV must contain `run_id` or another run/case identifier if one file contains data from several runs;
* if the waveform/sample file contains data from different signal modes or swept supplies, add a `run_id`/`case`/`sweep_target` column so rows can be unambiguously mapped to the run condition;
* do not append waveform samples from different runs into one file without a run identifier;
* if a full waveform is too large, save selected samples/probes or separate compact waveform CSV files for representative runs;
* metrics CSV must use the schema from `testbench_implementation_plan.md`;
* units must be consistent between log RESULT lines and CSV rows.

## Implementation Rules

* Follow `verification_plan.md` and `testbench_implementation_plan.md`.
* Do not change group names, planned paths, or CSV schema without a clear reason.
* Use only public DUT pins from the DUT contract.
* Do not use internal DUT nodes as observability points.
* Do not weaken acceptance limits to make the test pass.
* Develop and verify against `mock_device.sp` from the previous stage.
* The generated fixture owns testbench topology, DUT instantiation, and stable `TB_*` parameter declarations; `tests/<group_name>.control` owns `mock_device.sp` binding and run-time parameter values.
* Do not require real process models for mock-DUT ngspice runs; keep the inactive process-corner model placeholder in `tests/<group_name>.control` only.
* Do not place `mock_device.sp` includes, DUT implementation netlist includes, PDK/foundry model includes, or process-corner model placeholders in generated `tests/<group_name>.sp`.
* Output directories must exist before files are written. Create them in the HDL21 Python source or a pre-run step; do not make shell commands inside `.control` the main architecture.

## Ngspice Verification

After creating the files, run:

```bash
python tests/<group_name>.py
ngspice -b -o results/<group_name>.log tests/<group_name>.control
```

If the implementation plan specifies other paths, use those paths.

Iteratively fix the implementation until the current group satisfies all of the following:

* HDL21 source runs without errors;
* SPICE fixture is generated through the HDL21 flow;
* exported `.sp` is a complete reusable fixture, not a thin DUT wrapper or DUT-binding wrapper;
* fixture topology is in `tests/<group_name>.sp`, not in `.control`;
* exported `.sp` has one importable group-level fixture `.SUBCKT` containing the complete active testbench topology;
* the importable top fixture `.SUBCKT` name exactly matches the shared fixture naming contract from `testbench_implementation_plan.md`;
* exported `.sp` does not leave required active topology loose after `.ENDS`, except for one top-level ngspice activation instance;
* generated `tests/<group_name>.sp` contains the DUT instance by public contract;
* generated `tests/<group_name>.sp` exposes swept and corner-controlled source/stimulus/control values as stable `TB_*` fixture parameters with nominal defaults;
* generated `tests/<group_name>.sp` does not contain `mock_device.sp` includes, DUT implementation netlist includes, PDK/foundry model includes, or process-corner model placeholders;
* `tests/<group_name>.control` includes/sources `mock_device.sp` and generated fixture;
* ngspice finishes without fatal parse/runtime errors;
* `.control` runs the required analysis;
* `.control` applies executable run values through named fixture parameters where available;
* ngspice runs do not require PDK/foundry models or active process-corner includes;
* `tests/<group_name>.control` contains the required inactive process-corner model placeholder and matches the explicit or deferred process policy from `verification_plan.md`;
* log contains `RESULT` / `FAIL` / `SUMMARY`;
* metrics CSV is created, non-empty, and matches the schema;
* samples/waveform CSV is created if planned;
* planned CSV files have valid CSV format with consistent delimiter;
* waveform/sample CSV contains a run identifier if it includes data from more than one run;
* generated mock run gives meaningful measurements for all metrics in the current group, or explicitly marks mock-limited metrics as unmeasurable with `pass=0` and a clear reason;
* actual run count matches executable coverage from the verification plan;
* each RESULT row is measured under the requirement-specific condition from the verification plan;
* control file uses loops for repeated similar runs or contains a comment explaining why a loop is impossible.

If ngspice, HDL21, generated mock behavior, or simulator syntax blocks verification, stop and clearly state the blocker.

## Output Contract

Each `.control` must print machine-readable lines:

```text
RESULT test=<group_name> requirement=<requirement> parameters="<key=value; ...>" metric=<metric> value=<value> unit=<unit> pass=<0_or_1> limit="<limit>"
FAIL test=<group_name> reason=<reason> parameters="<key=value; ...>" metric=<metric> value=<value> unit=<unit> limit="<limit>"
SUMMARY test=<group_name> runs=<n> fail_count=<n>
```

Metrics CSV must match the schema from `testbench_implementation_plan.md`.

Do not leave empty, NaN, or missing metrics without an explicit blocker.

Do not report unmeasurable acceptance metrics as passing. If the generated mock cannot produce the needed crossing, settling point, operating point, or waveform condition, print and write the metric as `unmeasurable` with `pass=0` and a specific reason. This is acceptable for mock validation; it is not acceptable to hide it behind a passing constant.

For ngspice runs with the generated mock, do not report deferred process corners as executed run parameters or per-corner pass/fail results.

## Cleanup

After successful verification of the current group, delete temporary clutter:

* temporary decks;
* failed-attempt files;
* backup files;
* duplicate logs;
* `__pycache__`;
* unnecessary raw/binary files unless they are planned outputs.

Keep planned source files, generated SPICE fixture, control file, CSV outputs, useful log, and required samples/waveforms.

## Final Response After Each Group

Respond briefly with:

* which group was implemented;
* which files were created/updated;
* which ngspice command was run;
* which CSV/log outputs were produced;
* expected run count and actual run count;
* mock pass/fail summary;
* confirmation that executable coverage matches the verification plan;
* confirmation that swept/corner-controlled fixture values are exposed as stable `TB_*` parameters for Cadence/Maestro reuse;
* confirmation that the `.control` placeholder matches the explicit logical corners or `configured_process_corners` from `verification_plan.md`;
* confirmation that every RESULT matches the requirement-specific condition, or a list of assumptions/blockers;
* confirmation that the exported `.sp` is a complete fixture, not a thin wrapper or DUT-binding wrapper;
* confirmation that its top-level fixture `.SUBCKT` uses the shared name from `testbench_implementation_plan.md` while the DUT subckt contract remains unchanged;
* confirmation that generated `.sp` has no `mock_device.sp` includes, DUT implementation netlist includes, PDK/foundry model includes, or process-corner model placeholders;
* confirmation that `.control` includes/sources `mock_device.sp` and generated fixture;
* confirmation that planned CSV/waveform files have valid CSV format;
* blockers/limitations, if any;
* next group;
* ask the user whether to continue with the next group.

Do not move to the next group without user confirmation.

## Stage Boundary

After completing the current group or the complete suite, stop, report the result to the user, and wait for explicit confirmation before invoking any downstream skill.
