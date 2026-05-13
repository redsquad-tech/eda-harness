---
name: characterize-device
description: Use when user explicitly asks to run characterization/PVT sweep, save tagged CSV results, or report past characterization experiments and outcomes.
---

# Characterize Device Skill

This skill standardizes characterization execution, artifact capture (CSV + commit + tag), and experiment-history reporting for a device.

## Trigger Guidance

Use this skill for requests like:

- "характеризуй устройство"
- "прогони PVT"
- "сделай CSV с результатами по углам"

## Current Scope

- 5-corner characterization: `TT`, `FF`, `SS`, `FS`, `SF`
- one CSV per characterization run
- create one git commit + one git tag for each successful full characterization:
  - commit message: `characterization(<device>): <experiment_id>`
  - commit scope: all changes under `devices/<device>/` (device code + tests + artifacts including CSV)
  - `char/<device>/<experiment_id>`
- support listing past characterization experiments and results from tags + CSV files
- measurement function must be PVT-compatible (accept `corner` argument)
- measurement function must return:
  - `component`
  - `category`
  - `purpose`
  - `metrics` (dictionary)

Safety rule:

- characterization request is run/report only
- do not edit device implementation files during characterization
- if contract checks fail, return a structured failure report with exact missing contract items
- only modify device code if user explicitly asks to fix contract and rerun

## Workflow

1. Identify target device under `devices/<device>`.
2. Get free-form experiment description from user request.
3. Run characterization script for full characterization:

```bash
python .agents/skills/characterize-device/scripts/characterize_device.py \
  --device <device_name> \
  --description "<free-form description>"
```

Tagging rule:

- full characterization creates a git commit for full device state under `devices/<device>/`, then creates a git tag (`char/<device>/<experiment_id>`)
- use `--no-commit` and/or `--no-tag` only when user explicitly requests a no-git dry run

Default guard:

- default run uses `num_points=3` when measurement function supports it (prototype-friendly fast mode)
- script enforces minimum `metric_num_points` of 3 when metric is present
- increase minimum when user asks for denser characterization:

```bash
python .agents/skills/characterize-device/scripts/characterize_device.py \
  --device <device_name> \
  --description "<free-form description>" \
  --num-points 16 \
  --min-points 16
```

Optional measurement function override:

```bash
python .agents/skills/characterize-device/scripts/characterize_device.py \
  --device <device_name> \
  --description "<free-form description>" \
  --measure-fn <measure_function_name>
```

If `--measure-fn` is omitted, the script auto-discovers a public corner-aware function in `devices/<device>/measure.py` that passes output-contract probing.

Selection rule:

- do not use a measurement function that does not accept `corner`
- do not use a measurement function that omits `component/category/purpose`
- treat corner-normalization as mandatory contract:
  - measurement must correctly map both enum aliases (`TYP/FAST/SLOW`) and string labels (`TT/FF/SS/FS/SF`)
  - corner argument must influence selected model/conditions according to declared PVT mapping
- for multi-corner runs, the resulting numeric metric set must not be fully identical across all corners
- for sweep-based characterization metrics, treat 3 points as a smoke-only minimum; use denser sweeps for meaningful characterization

Note:

- create/update completion gates (validate-only contract check and multi-corner no-artifact precheck) are defined in `AGENTS.md` and `.agents/skills/code-test-or-component-hdl21/SKILL.md`

4. Return:
- output CSV path
- corners used (`TT/FF/SS/FS/SF`)
- experiment id
- short metric summary
- or structured failure report (without code edits)

## List Past Experiments

When user asks "какие были эксперименты" / "show characterization history":

```bash
python .agents/skills/characterize-device/scripts/list_characterization_experiments.py \
  --device <device_name>
```

Return:

- experiment tags
- related commits
- CSV paths
- short per-experiment summary (corners, pass_* status, metric preview)
- if CSV is not present in working tree, history reader falls back to CSV content from git tag/commit

## Output Location

- `devices/<device>/characterizations/char_<experiment_id>.csv`

## Spec Targets In CSV

If `devices/<device>/characterization_spec.json` exists, script adds:

- `target_<metric>_min|typ|max|exact`
- `pass_<metric>` (`PASS`/`FAIL`/`N/A`)

Minimal expected structure:

```json
{
  "metrics": {
    "example_metric": {
      "min": 0.0,
      "typ": 1.0,
      "max": 2.0
    },
    "exact_metric_example": {
      "exact": 0
    }
  }
}
```
