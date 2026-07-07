---
name: verification-plan-to-implementation-plan
description: Use this skill to create a concise testbench_implementation_plan.md from verification_plan.md.
---

# Skill: Verification Plan to Testbench Implementation Plan

## Purpose

Create a concise `testbench_implementation_plan.md` for implementing testbenches from `verification_plan.md`.

The implementation plan must define the minimum set of future testbench groups, their names, future files, stable fixture parameters, and stable CSV outputs.

Always write `testbench_implementation_plan.md` in English.

## Inputs

* `verification_plan.md` — the primary source for requirements, test matrix, DUT contract, metrics, and acceptance criteria.
* Specification — only if needed to clarify requirement meaning.

## Output

Create or update:

```text
testbench_implementation_plan.md
```

## `testbench_implementation_plan.md` Structure

Use this short structure:

```markdown
# <BLOCK_NAME> Testbench Implementation Plan

## 1. Fixture Groups
## 2. Planned Files and Outputs
## 3. Implementation Order
## 4. Assumptions / Blockers
```

## Fixture Groups

The main task is to group checks from `verification_plan.md` into the minimum number of future testbench groups.

Use this table:

```markdown
| Fixture Group | Covers Verification Plan Items | Analysis Type | Grouping Reason |
|---|---|---|---|
| `<group_name>` | `<requirement names / test matrix rows>` | `<OP/DC/TRAN/AC/MC/...>` | `<why these checks belong together>` |
```

Grouping rules:

* Do not create a separate group for every requirement row.
* One group must cover all checks with the same circuit setup, stimulus, analysis type, and observability.
* Derived metrics do not get a separate group if they are computed from the same waveform/run/analysis.
* Split groups only when setup, stimulus, analysis type, or measured public outputs/currents actually differ.
* Group name must be a short `snake_case` name and must be used as the stable base for future file names.
* Refer to requirement names and test matrix rows from `verification_plan.md`; do not duplicate the whole verification plan.

## Planned Files and Outputs

For each group, specify the future files.

Use this table:

```markdown
| Fixture Group | HDL21 Source | Exported SPICE Fixture | Ngspice Control | Metrics CSV | Samples / Waveform CSV |
|---|---|---|---|---|---|
| `<group_name>` | `tests/<group_name>.py` | `tests/<group_name>.sp` | `tests/<group_name>.control` | `results/<group_name>_metrics.csv` | `<planned sample/waveform outputs or none>` |
```

Also include a compact fixture-parameter table:

```markdown
| Fixture Group | Stable Fixture Parameters | Non-Parameter Run Dimensions |
|---|---|---|
| `<group_name>` | `<TB_* parameters>` | `<temperature, process, labels, or none>` |
```

Rules:

* Each testbench group is implemented by a separate HDL21 Python file.
* The SPICE fixture is exported to the stable path `tests/<group_name>.sp`.
* The SPICE fixture owns testbench topology and the public DUT instance only.
* The SPICE fixture must not include/source `mock_device.sp`, DUT implementation netlists, `$LIB_PATH`, PDK/foundry model files, process-corner models, or Cadence/Spectre hookup comments.
* The ngspice `.control` owns mock binding: it must include/source `mock_device.sp` and the generated SPICE fixture.
* Run matrix, measurements, derived metrics, and pass/fail checks must be in `tests/<group_name>.control`.
* Do not plan separate SPICE decks for each corner/run/condition.
* Sweep/run logic must live in `.control` using simulator-side loops, `alterparam`, `reset`, and analysis commands.
* The Python file is used to generate the circuit fixture, not to compute physical metrics.
* Plan stable fixture parameters for public-pin source, stimulus, control, load, and timing values that appear in run matrices or Cadence-export cases, so they can later become Cadence/Maestro design variables.
* Stable fixture parameter names must use uppercase `TB_*` names, for example `TB_<PIN>`, `TB_<PIN>_DC`, `TB_<STIM>_START`, `TB_<STIM>_STOP`, `TB_<STIM>_TIME`, `TB_TSTEP`, or `TB_TSTOP`.
* Do not plan lowercase ad-hoc fixture parameter names such as `vdd_value`, `temp_c`, `sweep_target`, or `ramp_direction`.
* Do not plan simulator temperature as a fixture parameter. Temperature must be represented as simulator temperature in ngspice and as corner-level simulator temperature in Cadence/Maestro.
* Do not plan process corner, run ID, case name, requirement name, sweep target, or ramp direction as fixture parameters. They are run/corner labels or metadata.
* If a ramp direction or sweep target affects the waveform, plan numeric `TB_*` parameters for the actual source values and timing; keep direction/target as run metadata.
* Preserve PVT/corner coverage from `verification_plan.md` as verification intent and downstream Cadence/Spectre export coverage.
* For ngspice runs with the generated mock, do not require `$LIB_PATH`, PDK/foundry model files, or active process-corner model includes.
* For ngspice runs with the generated mock, do not plan active process-corner model sweeps; keep process corners for Cadence/Spectre export using the model convention and corner identifiers from `verification_plan.md`.
* Public-pin voltage/reference/control/stimulus sweeps and simulator temperature sweeps should remain planned where meaningful.
* Plan any deferred process-model note only in the future `.control`; do not put `$LIB_PATH` or process-corner TODO comments into generated SPICE fixtures.
* If the group does not require waveform/sample export, write `none` in the last column.
* If the group has analysis type `TRAN`, `AC`, `noise`, `stability`, `PSRR`, transient response, frequency response, or another waveform-like/probe-based analysis, always plan the waveform/probe artifact: `results/<group_name>_waveforms.csv`.
* `results/<group_name>_samples.csv` may only be an additional artifact for compact sample/crossing/sweep/debug points. Do not use samples CSV as a replacement for waveform/probe CSV for TRAN/AC/waveform-like groups.
* If the group requires both compact sample points and waveform/probe evidence, list both files separated by `;`, for example `results/<group_name>_samples.csv; results/<group_name>_waveforms.csv`.
* If a waveform/probe CSV cannot be saved for a TRAN/AC/waveform-like group, state this as a blocker. Do not plan only samples CSV instead of waveform CSV.
* Waveform/probe artifacts must be planned as normal outputs of the corresponding testbench group, so the next implementation step creates them together with metrics/log outputs.

## CSV Outputs

The implementation plan must define only the data needed for future reporting and analysis.

Minimum metrics CSV schema:

```csv
test_name,requirement,run_id,parameters,metric,value,unit,limit_min,limit_max,pass,fail_reason,source_log
```

Purpose:

* `results/<group_name>_metrics.csv` — one or more rows with final measured metrics and pass/fail.
* `results/<group_name>_samples.csv` — sweep/MC/sample/crossing points, if needed for analysis or debugging.
* `results/<group_name>_waveforms.csv` — the standard waveform/probe output for TRAN/AC/waveform-like groups. Plan this exact stable path regardless of whether the user explicitly requested plots.

Rules for sample/waveform outputs:

* Metrics CSV is required for every group.
* For OP/DC-only groups, metrics CSV is usually sufficient; samples/waveforms may be `none`.
* For TRAN groups, always plan `results/<group_name>_waveforms.csv` as the standard output with time axis and measured public/probe signals.
* For AC/frequency-response groups, always plan `results/<group_name>_waveforms.csv` with frequency axis and measured signals.
* `results/<group_name>_samples.csv` does not replace waveform CSV. It is only an additional compact evidence/debug artifact.
* Waveform CSV must include a run/case identifier if one file contains data from multiple runs, for example `run_id`, `case`, or `sweep_target`.
* Sample CSV must include a run/case identifier if it contains data from multiple runs.
* Do not mix metrics, samples, and waveforms in one file.
* Do not add PDF/report-specific aggregation to the implementation plan. Downstream report generation can read the stable CSV files.

## Implementation Order

Specify the future implementation order of groups.

Preferred order:

1. OP/DC groups;
2. transient groups;
3. AC/stability groups;
4. statistical/Monte Carlo groups, if any.

For each iteration, the next skill must implement only one group and must not change already selected group names, file paths, or CSV schema without a clear reason.

## Assumptions / Blockers

Briefly state only items that may block implementation:

* unknown DUT subckt/module contract;
* simulator feature limitations;
* unclear required waveform/sample export;
* ambiguous requirements that were not resolved in `verification_plan.md`.

Missing local PDK files or missing `$LIB_PATH` is not a blocker for ngspice implementation. Preserve the Cadence/Spectre model convention from `verification_plan.md`.

State explicitly that generated SPICE fixtures must stay DUT-implementation independent: `mock_device.sp` belongs in `.control`, not in `tests/<group_name>.sp`.

State explicitly that simulator temperature is not a fixture parameter; it must be handled as simulator temperature in ngspice and as corner-level simulator temperature in Cadence/Maestro.

If the group is TRAN/AC/waveform-like but it is unclear which signals to save, do not leave this silent: plan `results/<group_name>_waveforms.csv` with the main public/probe signals or state a blocker.

## Final Checklist

Before finishing, verify that:

* all requirements from `verification_plan.md` are included in fixture groups;
* groups are not split without reason;
* each group has future `.py`, `.sp`, `.control`, and CSV paths;
* no per-run SPICE decks are planned;
* fixtures are planned as topology plus public DUT instance only, without `mock_device.sp` includes;
* `mock_device.sp` and fixture binding is planned in `.control`;
* swept/corner-controlled source, stimulus, control, load, and timing values are planned as stable uppercase `TB_*` fixture parameters for later Cadence/Maestro reuse;
* simulator temperature, process corner, run ID, case name, sweep target, and ramp direction are not planned as fixture parameters;
* measurements/pass-fail are planned in `.control`;
* CSV outputs have stable paths;
* PVT/corner intent from `verification_plan.md` is preserved for Cadence/Spectre export;
* ngspice planning with the generated mock does not require `$LIB_PATH`, PDK/foundry models, or active process-corner model sweeps;
* deferred process-model notes are planned only in `.control`, not in generated SPICE fixtures;
* TRAN/AC/waveform-like groups have planned waveform/probe CSV; if it cannot be created, this is listed as a blocker;
* sample/waveform CSVs are not mixed with metrics CSV;
* multiple sample/waveform outputs in one table cell are separated with `;`;
* implementation order is specified;
* assumptions/blockers are brief.

## Final Response to the User

Respond briefly with:

* `testbench_implementation_plan.md` created/updated;
* how many fixture groups were defined;
* which future files and CSV outputs are planned;
* which groups plan waveform/sample artifacts;
* how fixture/DUT binding is split between `.sp` and `.control`;
* which `TB_*` fixture parameters are planned and which run dimensions are not fixture parameters;
* how PVT/process-corner intent is preserved for Cadence/Spectre export;
* whether there are assumptions/blockers.
