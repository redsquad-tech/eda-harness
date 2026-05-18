# AGENTS Guide

This repository is an EDA development harness for creating and evolving analog devices (HDL21 + SKY130 + ngspice).

This document is the repository-level contract for agents creating a **new** device or updating an existing one.

## 1. Scope and Source of Truth

- Devices live in `devices/<device_name>/`.
- Each device directory should be self-contained: spec, implementation, measurements, and tests; reports are required for mature/sign-off-ready devices.
- Before coding, read the device spec and existing tests.
- If the target device is ambiguous, ask the user to select one.

## 2. Mandatory Workflow

Use this order:

1. Specification and goals
2. Verification plan and tests
3. HDL21 implementation
4. Simulation runs
5. Metrics and pass/fail summary

Do not skip verification-first workflow.

Prototype mode may use a reduced verification plan (`quick` + `char`) if explicitly labeled as prototype and accompanied by assumptions/limitations.

## 3. New Device: Required Layout

For a new device `devices/<device_name>/`, create at least:

- `README.md` — device overview, intent, pins, run commands
- `__init__.py` — exports
- `opamp.py` or `device.py` — top-level HDL21 DUT generator and params
- `measure.py` — measurement/testbench builders and characterization functions
- `measure.py` must implement characterization artifact exporter:
  - `export_characterization_artifacts(corner, out_dir, dut_out_path, ...) -> {dut_spice_path, bench_spice_path}`
  - `dut_spice_path` must equal provided `dut_out_path` (single DUT netlist per experiment)
- `run_tests.py` — entry point for quick/char suites
- `tests/__init__.py`
- `tests/test_smoke_*.py` — import/elaborate/compile/netlist checks
- `tests/test_char_*.py` — basic measurable behavior checks
- `characterization_spec.json` — per-metric targets used for characterization CSV `target_*` / `pass_*` columns

When requirements are mature, also add:

- `tests/acceptance/` — spec-level pass/fail tests
- `tests/budget/matrix.csv` — system/block/local budget matrix
- `tests/budget/test_*.py` — budget checks

## 3.1 Required User Input for New Device

For a production-intent new device, user input must include a usable specification.

Minimum required fields:

- device purpose
- target PDK/process (SKY130 in this repository)
- top-level pin/interface definition
- operating conditions (supply, load, corner/temperature intent)
- measurable target metrics with numeric criteria (for example gain/current/bandwidth/stability)

If these are missing, the agent must not present output as final design closure.

Allowed fallback:

- build a clearly labeled prototype with explicit assumptions,
- provide smoke+char tests,
- return a missing-spec list required for acceptance/budget closure.

## 4. HDL21 Implementation Contract

- DUT must be a `@h.generator`.
- DUT generator takes exactly one DUT `@h.paramclass`.
- Keep DUT params separate from testbench/stimulus params.
- DUT generator builds DUT only (no simulation, no file I/O).
- Prefer SKY130 mapped devices for DUT circuitry.
- Keep top-level compilation helper (`compile_for_sky130`) in device module.

## 5. Testbench and Measurement Contract

- Build simulations in `measure.py` and/or dedicated test files.
- Tests must verify finite, physically meaningful metrics, not only run completion.
- Keep at least two test targets:
  - `quick`: smoke checks
  - `char`: smoke + characterization
- Every code change affecting behavior must be followed by test updates and reruns.
- Metrics persistence rule:
  - `quick` may remain pass/fail only.
  - `char` and all longer validation suites (`acceptance`, `budget`, `probe`, etc.) must save measured metrics to machine-readable files (JSON) inside the device directory (typically under `tests/`).
  - Freeze/version workflow relies on these JSON metric artifacts to populate `versions/<version>/metrics/`.

## 6. Environment and PDK Contract

- Target PDK is SKY130.
- Repository expects PDK rooted under `./pdks/sky130A`.
- Simulations must fail fast with a clear message when PDK install is missing.
- Use repository ngspice integration helpers where applicable.
- Agent must run environment preflight before major simulation work:
  - Python interpreter is from project virtual environment (expected: `venv`)
  - required Python packages are importable
  - ngspice is callable
  - SKY130 PDK path is available
- If preflight fails, stop and return exact setup commands to user.

## 6.1 Virtual Environment Policy

- Preferred interpreter is project-local virtual environment.
- Use `python`/`pip` from active venv for all device scripts, tests, and tooling.
- Do not rely on system Python for reproducible device development.

## 6.2 ngspice Parser Compatibility Fallback

If simulation runs but Python-side raw parsing fails (for example, ngspice output format mismatch):

1. Keep DUT and test intent unchanged.
2. Switch measurement flow to robust ngspice batch mode (`ngspice -b`).
3. Parse required scalar/traces from generated log/text outputs (`.op`, `.ac`, etc.).
4. Document this fallback in device README or measurement notes.

## 6.3 PDK Path Compatibility (Minimal Rule)

If SKY130 PDK is reported missing, first check canonical path:

- `./pdks/sky130A`

Some legacy code expects:

- `./pdks/sky130A/sky130A`

In that case, create compatibility symlink:

```bash
mkdir -p pdks/sky130A
ln -sfn /absolute/path/to/pdks/volare/sky130/versions/0fe599b2afb6708d281543108caf8310912f54af/sky130A pdks/sky130A/sky130A
```

Validation rule:

- Do not report `char` as successful if simulation is skipped due to missing PDK/environment setup.

## 7. Output and Reporting Contract

For each development task, report:

- files created/updated
- commands executed
- test status (`quick`, `char`, and others if run)
- key measured metrics (gain, currents, operating points, and relevant AC/transient metrics)
- known limitations and next steps

## 8. Definition of Done (New Device, Minimum)

A new device is minimally ready when:

1. Device folder exists under `devices/<device_name>/` with required files.
2. `run_tests.py quick` passes.
3. `run_tests.py char` passes.
4. Characterization returns numeric metrics and tests assert them.
5. README explains what was built and how to run tests.
6. Characterization contract-check passes via validate-only mode:

```bash
python .agents/skills/characterize-device/scripts/characterize_device.py \
  --device <device_name> \
  --description "creation characterization contract check" \
  --validate-only
```

`--validate-only` must validate both measurement-output contract and exporter contract (dry-run, no CSV artifacts).

7. If step 6 fails, create/update task is not complete and must be reported as failed (do not present device as ready).
8. Run steps 6 and 9 using `python` from active project venv.
9. Corner-sensitivity precheck passes before declaring create/update ready:

```bash
python .agents/skills/characterize-device/scripts/characterize_device.py \
  --device <device_name> \
  --description "creation corner-sensitivity precheck" \
  --no-csv \
  --no-tag \
  --no-commit \
  --corners TT,FF,SS,FS,SF
```

10. If step 9 fails, create/update task is not complete; fix implementation before reporting create/update success.
11. During create/update, `characterize_device.py` is allowed only in non-artifact modes:
    - `--validate-only`, or
    - `--no-csv` (for corner-sensitivity precheck).
    Full CSV-producing characterize runs in create/update are not allowed unless user explicitly requested characterization.
12. For new devices, `measure.py` must include callable `export_characterization_artifacts(...)` compatible with characterize workflow.

## 9. Definition of Done (Mature Device)

A mature device additionally has:

- acceptance tests mapped to specification requirements
- budget matrix and budget tests
- corner/PVT coverage according to spec
- Monte Carlo tests when required by mismatch/offset/yield requirements

## 10. Practical Rule for Agents

If spec is incomplete:

- stop guessing,
- produce a missing-spec report,
- propose exact missing fields required to proceed.

If user asks for quick exploration/prototype:

- deliver a clearly labeled prototype with smoke+char tests,
- state that acceptance/budget closure is pending.

## 11. Preferred Skill Usage

When creating or substantially updating a device, the agent should first use the repository skill:

- `.agents/skills/code-test-or-component-hdl21/SKILL.md`

When user requests to capture a stable device state as a named version (freeze/snapshot/release baseline), the agent should use:

- `.agents/skills/version-device/SKILL.md`

Expected behavior:

1. Convert user PRD/spec into HDL21-oriented implementation and test plan.
2. Apply repository standards from that skill during code and test creation.
3. Verify final outputs still satisfy this `AGENTS.md` contract.

Skill usage is preferred workflow for consistency; if skill execution is not possible, the agent must still meet all requirements in this document.

## 12. Versioning and Branching Contract

This repository supports parallel device R&D. Use line-based development:

- branch format: `device/<device_name>/<line_name>`
- freeze tag format: `device/<device_name>/<line_name>/vX.Y.Z`
- release tag format (main only): `release/<device_name>/vA.B.C`

Rules:

- User chooses line strategy once at start of create/update session:
  - create new line from selected base (`main` or specific version),
  - or continue existing line.
- Before any code changes for create/update requests, agent must:
  - inspect existing lines/versions for that device,
  - report discovery results to user including lines, freeze tags, release tags, and promoted status from catalog (if available),
  - ask user to choose new-line or continue-line mode,
  - create/switch the selected `device/<device>/<line>` branch.
- Discovery source-of-truth rule:
  - agent must use `.agents/skills/version-device/scripts/list_device_versions.py` output as authoritative,
  - if output includes non-null `version_index`, agent must not claim index is missing.
- If no lines/versions exist for the device:
  - report that explicitly,
  - suggest creating a new line from `main`,
  - ask only for missing minimal identifiers (device name and optional line name),
  - if line name is not provided, use `mainline`.
- For `new line` mode, base-ref selection is mandatory:
  - agent must always ask user to choose base-ref explicitly (`main` or specific freeze tag/commit),
  - agent must not silently assume base-ref.
- Agent performs implementation and iterative checks only in selected line.
- On freeze request, agent must:
  - run required validation targets,
  - save artifacts and metrics under `devices/<device_name>/versions/<line_name>/<version>/`,
  - create freeze commit and freeze tag,
  - update `devices/<device_name>/VERSION_INDEX.json` on `main` with `promoted_to_main=false`.
- After freeze, agent asks whether to promote to `main`.
- On promote approval, agent must:
  - merge line branch into `main` (no-ff),
  - assign next release version for `main`,
  - create release tag,
  - update corresponding catalog entry (`promoted_to_main=true`, release tag, merge commit).

Catalog file:

- `devices/<device_name>/VERSION_INDEX.json` is the single visibility index for all known line freezes and promoted releases.

## 13. Characterization Contract

When user explicitly requests characterization/PVT/CSV:

- use `.agents/skills/characterize-device/SKILL.md`
- run repository characterization flow over defined corners
- write one experiment folder per run under `devices/<device>/characterizations/<experiment_id>/`
- save characterization CSV, DUT SPICE, benchmark/testbench SPICE, manifest, and zip archive in that folder
- create characterization commit for full device state under `devices/<device>/` (`characterization(<device>): <experiment_id>`)
- create characterization tag for each successful full run: `char/<device>/<experiment_id>`
- default mode is run/report only (no implementation edits)
- do not use `--no-tag` or `--no-commit` unless user explicitly requested a no-git dry run
- do not auto-run full characterization CSV during generic create/update requests

When user asks about past experiments/results:

- list characterization history using repository characterize-device tooling
- report tags, commits, CSV paths, and short metric/pass summaries

Measurement function used for characterization must:

- accept a `corner` argument
- return a dictionary with `component`, `category`, `purpose`, and `metrics`
- provide meaningful spec-related metrics (not smoke-only placeholder output)
- normalize incoming corner values to canonical labels (`TT`, `FF`, `SS`, `FS`, `SF`) before model selection
- support both enum-style inputs (`TYP`, `FAST`, `SLOW`) and string labels (`tt`, `ff`, `ss`)
- use explicit and deterministic corner-to-model mapping (no ambiguous fallback-only selection)
- for multi-corner characterization, numeric metric set must reflect corner influence (corner labels alone are insufficient)
- for 5-corner runs, `FS` and `SF` must be handled as distinct corners; do not silently collapse them to `FF`/`SS`
- if physical/tooling support for true `FS`/`SF` is unavailable, characterization must fail with explicit contract error (do not fake pass by remapping)

Artifact exporter implementation rule (for new/updated devices):

- implement `export_characterization_artifacts(corner, out_dir, dut_out_path, ...)` in `measure.py`
- required compatible signature:
  - `export_characterization_artifacts(corner, out_dir, dut_out_path, num_points=None, measure_fn_name=None, **kwargs)`
- write DUT SPICE exactly once to `dut_out_path` (shared for all corners in one experiment)
- write only corner-specific benchmark/testbench SPICE under `out_dir`
- return:
  - `dut_spice_path == dut_out_path`
  - `bench_spice_path` inside `out_dir`
- do not generate per-corner DUT filenames (`..._dut_TT.sp`, etc.) for characterization artifacts

If characterization contract is not satisfied:

- stop characterization run
- return exact missing contract items
- do not patch device code unless user explicitly asks to fix and rerun
