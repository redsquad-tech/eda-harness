# Structural Component Testing Guide

## 1. Scope

This guide defines tests for structural Hdl21 generators built from verified SKY130 leaf cells.

Covered components:

- `frontend_az`
- `gain_stage`
- `second_stage`
- `output_stage`
- `cmfb_ct`
- `cmfb_sc`
- `bias_gen`
- `freq_comp`
- `sw_bank_az`
- `input_mux`
- `offset_trim`
- `ripple_filter`
- `opamp_az_top`
- `opamp_diff_top`

Out of scope: leaf generators such as `tg_switch`, `sample_hold_cap`, `nonoverlap_clk`, `diffpair_n`, `diffpair_p`, `tail_bias`, `current_mirror`, `active_load`, `cascode_block`.

## 2. Test Categories

| Category | Meaning | Pass/Fail |
|---|---|---:|
| `smoke` | Instantiate, connect, converge | yes |
| `contract` | Basic functional correctness | yes |
| `char` | Characterization only | no |
| `pvt` | Worst case across process, voltage, temperature | yes |
| `mc` | Monte Carlo / mismatch | yes |
| `pex` | Schematic vs extracted delta | yes |
| `budget` | Fit against a block or system spec | yes |

Rules:

- `contract` proves the block is usable.
- `char` measures behavior.
- `budget` is instance-specific, not generic.

## 3. Naming

### Test files and functions

```text
test_<component>__<category>__<purpose>.py
```

```python
def test_<component>__<category>__<purpose>():
    ...
```

Examples:

```text
test_frontend_az__contract__pedestal_zero_input.py
test_gain_stage__char__gain_gmro.py
test_opamp_az_top__budget__precision_ppa.py
```

### Testbench files

```text
tb_<component>__<purpose>__<fixture>.py
```

### Spec classes

```text
<ComponentPascalCase>Spec
```

### Result files

```text
<component>__<category>__<purpose>.json
```

Optional artifacts:

```text
<component>__<metric>__vs_<sweep>.csv
<component>__<metric>__vs_<sweep>.png
```

### Naming rules

Do not put any of these in a file name:

- process corner
- temperature
- VDD
- Monte Carlo seed
- sweep values

Those belong in test configuration.

## 4. Purpose Names

Use short `snake_case` names. Reuse existing names when possible.

Common purpose names:

- `basic`
- `polarity`
- `phase_polarity`
- `bias_headroom`
- `pedestal_zero_input`
- `settling_in_phase_window`
- `gain_gmro`
- `icmr`
- `swing`
- `load_drive`
- `vocm_lock`
- `diff_transparency`
- `startup`
- `current_accuracy`
- `pole_zero_extract`
- `code_monotonicity`
- `attenuation_at_fchop`
- `open_loop`
- `closed_loop_step`
- `noise_and_offset`
- `precision_ppa`

Do not create synonyms for the same check.

## 5. Directory Layout

```text
tests/
  structural/
    <component>/
      test_<component>__smoke__basic.py
      test_<component>__contract__*.py
      test_<component>__char__*.py
      test_<component>__pvt__*.py
      test_<component>__mc__*.py
      test_<component>__pex__*.py
      test_<component>__budget__*.py
      tb_<component>__*.py
      specs_<component>.py
```

## 6. Result Format

Each test should emit one JSON result.

```json
{
  "component": "frontend_az",
  "category": "contract",
  "purpose": "pedestal_zero_input",
  "pass": true,
  "metrics": {
    "pedestal_uV": 38.2,
    "settling_residue_uV": 14.7
  },
  "corner_worst": "ss_125c_vddmin",
  "margin": {
    "pedestal_uV": 11.8
  },
  "artifacts": {
    "csv": "frontend_az__pedestal_uV__vs_vcm.csv"
  }
}
```

Required fields:

| Field | Required |
|---|---|
| `component` | always |
| `category` | always |
| `purpose` | always |
| `pass` | all except pure `char` |
| `metrics` | always |
| `corner_worst` | `pvt`, `mc`, `pex`, `budget` |
| `margin` | `contract`, `budget` |

## 7. Canonical Fixtures

Use fixed fixture names.

| Fixture | Meaning |
|---|---|
| `nominal_load` | standard load |
| `light_load` | light load |
| `heavy_load` | heavy load |
| `unity_feedback` | unity-gain feedback |
| `closed_loop_gain10` | closed-loop gain = 10 |
| `hold_cap` | hold-cap testbench |
| `sc_loop` | switched-cap loop |
| `diff_load` | differential load |
| `current_load` | current load |
| `worst_bias` | bad startup condition |

## 8. Special Rules

### Budget

Budget tests are instance-specific.

Format:

```text
test_<component>__budget__<budget_name>.py
```

Recommended budget names:

- `precision_frontend`
- `input_stage_precision`
- `drive_and_gain`
- `vocm_accuracy`
- `stability_window`
- `switch_network_precision`
- `offset_trim_range`
- `ripple_attenuation`
- `precision_ppa`

Budget result should include:

- `spec_name`
- `pass`
- `violations`
- `margin`
- `corner_worst`

### PVT

Use a purpose name that tells what is worst-cased.

Good:

```text
test_gain_stage__pvt__gain_headroom.py
test_frontend_az__pvt__residue_and_noise.py
```

Bad:

```text
test_gain_stage__pvt__all.py
test_frontend_az__pvt__corners.py
```

### MC

Use Monte Carlo only for mismatch-sensitive blocks.

Format:

```text
test_<component>__mc__<stat_metric>.py
```

### PEX

Name the test after the metric most affected by layout parasitics.

Format:

```text
test_<component>__pex__<delta_metric>.py
```

## 9. Minimum Test Set for a New Structural Generator

Start with:

1. `smoke/basic`
2. two main `contract` tests
3. one main `char` test
4. one `pvt` test
5. one `budget` test if the block is already used in a top-level design

Template:

```text
test_<component>__smoke__basic.py
test_<component>__contract__<main_contract_1>.py
test_<component>__contract__<main_contract_2>.py
test_<component>__char__<main_metric>.py
test_<component>__pvt__<main_worst_case>.py
```

For precision, auto-zero, and fully differential blocks, add `mc` and `pex` early.

