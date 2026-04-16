# v3 Experiments

`v3/experiments` now keeps only the current output-stage line of work.

Current active experiment:

- `opamp/v3/experiments/core_h10_analog_class_ab/`

Scope:

- standalone gate-driver probes
- standalone output-stage probes
- full-core probe and AC checks for the current class-AB idea

Work rule:

- new output-stage changes should be made directly in `opamp/v3/opamp_core.py`
- use `core_h10_analog_class_ab/` to keep the focused probe and metrics history for the current line
