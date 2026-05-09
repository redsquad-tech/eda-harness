# EDA Harness

Repository for HDL21 + SKY130 + ngspice device development.

Primary workflow:

1. User asks Codex to create/update a device.
2. Codex discovers existing lines/versions and asks user to choose:
   - continue an existing line, or
   - create a new line with explicit base-ref (`main` or freeze tag/commit).
3. Codex creates/switches `device/<device>/<line>` and performs implementation in that line.
4. Codex runs development checks/simulations and reports metrics and pass/fail status.
5. User asks Codex to freeze a stable line state.
6. Codex runs freeze pipeline (`quick` + `char` by default), saves artifacts, updates `VERSION/CHANGELOG`, creates freeze commit/tag, and updates `devices/<device>/VERSION_INDEX.json` on `main` with `promoted_to_main=false`.
7. Codex asks whether to promote this frozen version to `main`.
8. If approved, Codex runs promote pipeline: merge to `main` (`--no-ff`), assign release version, create release tag, and update `VERSION_INDEX.json` (`promoted_to_main=true`).

## 1) System Requirements

- Linux environment
- Python 3.11
- `ngspice`

Install ngspice (Debian/Ubuntu):

```bash
sudo apt update
sudo apt install -y ngspice
```

## 2) Python Environment

From repository root:

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3) Install SKY130 PDK

```bash
mkdir -p pdks
PDK_ROOT=pdks volare enable --pdk sky130 0fe599b2afb6708d281543108caf8310912f54af
```

## 4) How To Work With Codex

Minimal prompt:

```text
Создай операционный усилитель
```

Codex should:

- create a new folder under `devices/`
- implement DUT + measurement + tests
- run quick/char checks
- report metrics and limitations

If full specification is not provided, Codex should produce a clearly labeled prototype with explicit assumptions.

For a production-intent (fully qualified) device, user must provide a usable specification to Codex.  
Minimum required spec fields:

- device purpose
- top-level pins/interface
- operating conditions (supply, load, corners, temperature intent)
- numeric target metrics and pass/fail criteria (for example gain, bandwidth, phase margin, current, swing)

Without this spec, output should be treated as prototype only (not acceptance/budget closure).

Expected result format from Codex:

- files created/updated
- commands executed
- test status
- measured metrics
- known limitations / assumptions

Behavior rules are defined in:

- `AGENTS.md` (repository contract for agents)
- `.agents/skills/code-test-or-component-hdl21/SKILL.md` (preferred implementation standard)
- `.agents/skills/version-device/SKILL.md` (freeze/version workflow)

## 5) Versioning Workflow (Line / Freeze / Promote)

This repository uses line-based device development.

Branch model:

- line branch: `device/<device>/<line>`

Tag model:

- freeze tag: `device/<device>/<line>/vX.Y.Z`
- release tag (main only): `release/<device>/vA.B.C`

Global catalog:

- `devices/<device>/VERSION_INDEX.json` (maintained on `main`)

### 5.1 Start Or Continue A Line

Primary path: when user asks Codex to create/update a device, Codex performs line selection before any edits.

Recommended interaction:

1. Ask Codex to modify a specific device.
2. Codex discovers existing lines/versions for that device.
3. Codex asks you to choose:
   - continue an existing line, or
   - create a new line with explicit base-ref.
4. Codex creates/switches the selected line branch and only then starts implementation.

Manual/debug fallback:

Discover existing lines/versions:

```bash
python .agents/skills/version-device/scripts/list_device_versions.py --device <device>
```

Create or switch line:

```bash
python .agents/skills/version-device/scripts/start_device_line.py \
  --device <device> \
  --line <line> \
  --base-ref <main_or_freeze_tag_or_commit>
```

### 5.2 Freeze A Stable Line State

Primary path: when user asks Codex to freeze/snapshot/version a stable line state, Codex runs the freeze workflow automatically.

What happens:

- run validation targets (`quick` + `char` by default)
- save artifacts under `devices/<device>/versions/<line>/<version>/`
- update `devices/<device>/VERSION` and `devices/<device>/CHANGELOG.md`
- create freeze commit on line branch
- create freeze tag `device/<device>/<line>/vX.Y.Z`
- update `devices/<device>/VERSION_INDEX.json` on `main` (`promoted_to_main=false`)
- after freeze completion, Codex asks whether to promote this frozen version to `main`

Optional:

- explicit line version may be provided by user (`vX.Y.Z`)
- otherwise Codex auto-bumps from `devices/<device>/VERSION`

Manual/debug fallback:

```bash
python .agents/skills/version-device/scripts/freeze_device_version.py \
  --device <device> \
  --line <line>
```

### 5.3 Promote To Main

Primary path: after freeze, if user confirms promote, Codex runs promote workflow automatically.

What happens:

- merge `device/<device>/<line>` into `main` (`--no-ff`)
- assign release version (auto-bump or explicit)
- create release tag `release/<device>/vA.B.C`
- update matching entry in `VERSION_INDEX.json` (`promoted_to_main=true`)

Manual/debug fallback:

```bash
python .agents/skills/version-device/scripts/promote_device_version.py \
  --device <device> \
  --line <line> \
  --version <vX.Y.Z>
```

## 6) Troubleshooting

### A) `ModuleNotFoundError` for HDL21/related packages

Virtual environment is not active or dependencies are not installed.

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### B) Missing SKY130 PDK root

Check Volare install (`pdks/sky130A`). If legacy code expects `pdks/sky130A/sky130A`, add compatibility link:

```bash
mkdir -p pdks/sky130A
ln -sfn /absolute/path/to/pdks/volare/sky130/versions/0fe599b2afb6708d281543108caf8310912f54af/sky130A pdks/sky130A/sky130A
```

### C) ngspice/vlsirtools raw parse error

Example:

`ValueError: Invalid flags ['Plotname:', 'Operating', 'Point']`

This is a compatibility issue between some ngspice outputs and Python raw parser stack.

Preferred fallback in measurement code:

- run ngspice in batch mode (`ngspice -b`)
- parse text `.op` / `.ac` logs directly for required metrics

If needed, pin compatible ngspice/vlsirtools versions for your environment.
