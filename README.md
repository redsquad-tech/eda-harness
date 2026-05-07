# EDA Harness

Repository for HDL21 + SKY130 + ngspice device development.

Primary workflow:

1. User asks Codex to create/update a device in `devices/<device_name>/`
2. Codex implements HDL21 DUT (Device Under Test) and tests
3. Codex runs simulations/tests
4. Codex returns measured metrics and pass/fail status

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
Создай операционный усилитель.
```

Codex should:

- create a new folder under `devices/`
- implement DUT + measurement + tests
- run quick/char checks
- report metrics and limitations

If full specification is not provided, Codex should produce a clearly labeled prototype with explicit assumptions.

Expected result format from Codex:

- files created/updated
- commands executed
- test status
- measured metrics
- known limitations / assumptions

Behavior rules are defined in:

- `AGENTS.md` (repository contract for agents)
- `.agents/skills/code-test-or-component-hdl21/SKILL.md` (preferred implementation standard)

## 5) Troubleshooting

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
