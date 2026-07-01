---
name: implementation-plan-to-testbenches
description: Use this skill to sequentially implement all testbench groups from testbench_implementation_plan.md.
---

# Skill: Implementation Plan to Testbenches

## Purpose

Sequentially implement all testbench groups from `testbench_implementation_plan.md`.

In one iteration, implement only one current group, bring it to a working state in ngspice, report back to the user, and ask whether to continue with the next group.

## Inputs

* `verification_plan.md` — DUT contract, requirements, conditions, metrics, and pass/fail limits.
* `testbench_implementation_plan.md` — fixture groups, planned files, CSV outputs, and implementation order.
* DUT netlist for development/run — user-provided runnable SPICE netlist or generated mock netlist selected in the previous stage.
* Optional model files/includes — use only when the selected real ngspice DUT requires them. Do not require `$LIB_PATH` or PDK/foundry process models for mock/development ngspice runs.

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

## HDL21 Fixture Requirement

`tests/<group_name>.py` must actually use HDL21 to generate a reusable electrical fixture and export `tests/<group_name>.sp`.

Main rule: the exported `tests/<group_name>.sp` must be a complete testbench fixture, not a thin DUT wrapper and not a DUT-binding wrapper.

Rules:

* `tests/<group_name>.py` must generate the circuit fixture through HDL21 modules/instances/primitives/helpers.
* The exported `tests/<group_name>.sp` must contain the DUT instance by public contract and the electrical setup required for this group: supply/reference/control sources, loads, capacitors, feedback connections, stimulus elements, named nodes, and probe points where applicable.
* The exported fixture must instantiate the DUT, but must not include/source the selected DUT implementation netlist.
* Do not put `.include`, `.lib`, or `source` statements for `mock_device.sp`, real DUT netlists, selected DUT netlists, `$LIB_PATH`, PDK/foundry models, or process corners into `tests/<group_name>.sp`.
* For OP/DC/static groups, the fixture should usually contain all static sources, loads, feedback connections, and the DUT instance.
* For TRAN/AC/waveform-like groups, the fixture must contain the stimulus/source elements required for the analysis, for example parameterized PULSE/PWL/AC/DC sources, loads/caps, and stable probe nodes.
* `.control` must not be the primary place where the testbench circuit topology is created. Do not move supply/reference/control/stimulus sources into `.control` just because it is easier.
* `.control` must control the already-created fixture: include/source files, `alterparam`/`alter`, `reset`, analysis commands, measurements, derived metrics, pass/fail, `RESULT`/`FAIL`/`SUMMARY`, and CSV/waveform exports.
* Export the SPICE fixture through the HDL21 netlisting/export flow.
* Do not replace HDL21 generation with full handwritten SPICE text generation.
* Do not use HDL21 only as a decorative port-list declaration on top of a handwritten fixture.
* Do not edit generated SPICE manually.
* Do not insert `$LIB_PATH`, process-corner TODOs, or Cadence/Spectre hookup comments into generated `tests/<group_name>.sp`; exported SPICE fixtures must stay clean and reusable.

Raw-SPICE exception:

* If a required simulator-specific element is not expressed well by pure HDL21 primitives, for example a PULSE/PWL source, behavioral helper, or special probe/helper element, the Python generator may add a small documented raw-SPICE fragment to the generated `tests/<group_name>.sp`.
* This raw-SPICE fragment must be minimal, local to the fixture, and added by `tests/<group_name>.py` when generating `.sp`.
* The raw-SPICE fragment must not include/source the selected DUT implementation netlist, mock netlist, real DUT netlist, `$LIB_PATH`, or PDK/foundry models.
* The final `tests/<group_name>.sp` must still contain a complete reusable fixture with stimulus/source elements.
* Do not use raw-SPICE fragments in `.control` as a way to describe the main circuit topology.

Before finishing the fixture, check that:

* the group electrical setup can be understood by opening `tests/<group_name>.sp`, without reading measurement loops in `.control`;
* `.sp` contains sources/stimulus/load/probe elements if the group needs them;
* `.sp` contains the DUT instance by public contract;
* `.sp` does not contain selected DUT/mock netlist includes, real DUT netlist includes, `$LIB_PATH`, PDK/foundry model includes, process-corner TODOs, or Cadence/Spectre hookup comments;
* `.control` does not contain the main set of V/I source declarations that should be part of the reusable fixture;
* `.control` changes parameters of existing fixture elements instead of recreating fixture topology.

## Ngspice Control Requirement

`tests/<group_name>.control` contains simulator-side logic:

* include/source the selected ngspice DUT/mock netlist for this stage;
* include/source the generated SPICE fixture `tests/<group_name>.sp`;
* include/source required model/includes only when the selected real ngspice DUT requires them;
* for mock/development ngspice runs, do not add active `.include` or `.lib` lines for `$LIB_PATH` or process-corner models;
* for mock/development ngspice runs, add the deferred Cadence/Spectre process-model note only in `tests/<group_name>.control`, as a comment, using `$LIB_PATH` and corner identifiers `tt`, `ff`, `ss`, `fs`, `sf`;
* run matrix, loops, `alterparam`/`alter`, `reset`;
* analysis commands: OP/DC/TRAN/AC/MC;
* measurements and derived metrics;
* pass/fail checks;
* `RESULT` / `FAIL` / `SUMMARY` lines;
* writing metrics CSV and planned samples/waveform CSV.

Python must not compute physical metrics or pass/fail.

For metrics CSV, simulator-side text output may be used. For waveform/sample data, prefer `wrdata` or another simulator-native export.

Do not create separate SPICE decks for each run/corner/condition.

## Run Matrix and Coverage Rules

The executable ngspice run matrix must match the current group coverage from `testbench_implementation_plan.md` and the corresponding rows in the `Acceptance Test Matrix` in `verification_plan.md`, except for deferred process-corner coverage on mock/development ngspice runs.

Rules:

* first identify the concrete verification-plan items covered by the current group;
* for each item, use its `Test Condition / Stimulus`, `Condition Coverage`, measurement method, and acceptance criteria from `verification_plan.md`;
* use `Operating Conditions` and `Presets` from `verification_plan.md` as the source of values for the presets/runs specified in the test matrix;
* do not add coverage beyond what is specified in the test matrix;
* do not remove executable public-pin, supply, reference, control, stimulus, or simulator-temperature coverage;
* for mock/development ngspice runs, exclude process-corner dimensions from the executable ngspice run matrix and preserve them as downstream Cadence/Spectre coverage intent;
* do not require `$LIB_PATH`, PDK/foundry model files, or active process-corner model includes for mock/development ngspice runs;
* do not emit per-process-corner `RESULT` or CSV rows in mock/development ngspice unless real process models were actually included and swept;
* if the verification plan specifies a nominal-only run, run nominal only;
* if the verification plan specifies a sweep over one executable group of conditions, change only that group and keep all other executable conditions nominal/fixed;
* if the verification plan specifies full-combination coverage, run the full combination of executable ngspice dimensions for this stage;
* if the implementation plan and verification plan disagree on executable coverage, use the verification plan as the source of truth and state an assumption/blocker;
* expected run count must be calculated before writing `.control` and must match `SUMMARY runs=<n>`;
* for mock/development ngspice runs, expected run count is calculated after excluding deferred process-corner dimensions.

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
* for mock/development ngspice runs with deferred process coverage, do not list a specific process corner as an executed parameter;
* if two requirements need the same fixture but different bias cases, use one fixture and several cases/loops in `.control`.

Before the final run of the current group, check:

* the list of actual `RESULT` rows;
* the list of parameters in each run;
* actual run coverage against the executable ngspice dimensions from the verification plan;
* whether deferred process-corner coverage is preserved in `.control` comments and final response for Cadence/Spectre export;
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
* Develop and verify against the selected runnable DUT netlist from the previous stage. If a mock DUT was created, use the mock. If the user provided a runnable real SPICE netlist with the required public contract, use it directly.
* The generated fixture owns testbench topology and DUT instantiation; `tests/<group_name>.control` owns selected ngspice DUT/mock netlist binding.
* For mock/development ngspice runs, do not require real process models; keep process-corner hookup as a commented note in `tests/<group_name>.control` only.
* Do not place selected DUT/mock includes, real DUT netlist includes, `$LIB_PATH`, process-corner hookup notes, or Cadence/Spectre TODO comments in generated `tests/<group_name>.sp`.
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
* generated `tests/<group_name>.sp` contains the DUT instance by public contract;
* generated `tests/<group_name>.sp` does not contain selected DUT/mock includes, real DUT netlist includes, `$LIB_PATH`, PDK/foundry model includes, process-corner TODOs, or Cadence/Spectre hookup comments;
* `tests/<group_name>.control` includes/sources the selected ngspice DUT/mock netlist and generated fixture;
* ngspice finishes without fatal parse/runtime errors;
* `.control` runs the required analysis;
* mock/development ngspice runs do not require `$LIB_PATH`, PDK/foundry models, or active process-corner includes;
* if process-corner coverage is deferred, `tests/<group_name>.control` contains the commented Cadence/Spectre model-hookup note through `$LIB_PATH`;
* log contains `RESULT` / `FAIL` / `SUMMARY`;
* metrics CSV is created, non-empty, and matches the schema;
* samples/waveform CSV is created if planned;
* planned CSV files have valid CSV format with consistent delimiter;
* waveform/sample CSV contains a run identifier if it includes data from more than one run;
* DUT/mock run gives meaningful measurements for all metrics in the current group;
* actual run count matches executable coverage from the verification plan;
* each RESULT row is measured under the requirement-specific condition from the verification plan;
* control file uses loops for repeated similar runs or contains a comment explaining why a loop is impossible.

If ngspice, HDL21, DUT/mock behavior, or simulator syntax blocks verification, stop and clearly state the blocker.

## Output Contract

Each `.control` must print machine-readable lines:

```text
RESULT test=<group_name> requirement=<requirement> parameters="<key=value; ...>" metric=<metric> value=<value> unit=<unit> pass=<0_or_1> limit="<limit>"
FAIL test=<group_name> reason=<reason> parameters="<key=value; ...>" metric=<metric> value=<value> unit=<unit> limit="<limit>"
SUMMARY test=<group_name> runs=<n> fail_count=<n>
```

Metrics CSV must match the schema from `testbench_implementation_plan.md`.

Do not leave empty, NaN, or missing metrics without an explicit blocker.

For mock/development ngspice runs, do not report deferred process corners as executed run parameters or per-corner pass/fail results.

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
* DUT/mock pass/fail summary;
* confirmation that executable coverage matches the verification plan;
* confirmation that process-corner coverage, if deferred, is preserved for Cadence/Spectre export through `$LIB_PATH` with corner identifiers `tt`, `ff`, `ss`, `fs`, `sf`;
* confirmation that every RESULT matches the requirement-specific condition, or a list of assumptions/blockers;
* confirmation that the exported `.sp` is a complete fixture, not a thin wrapper or DUT-binding wrapper;
* confirmation that generated `.sp` has no selected DUT/mock includes, real DUT netlist includes, `$LIB_PATH`, PDK/foundry model includes, process-corner TODOs, or Cadence/Spectre hookup comments;
* confirmation that `.control` includes/sources the selected ngspice DUT/mock netlist and generated fixture;
* confirmation that planned CSV/waveform files have valid CSV format;
* blockers/limitations, if any;
* next group;
* ask the user whether to continue with the next group.

Do not move to the next group without user confirmation.