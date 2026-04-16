# Opamp V3

`v3` is the main active opamp architecture.

Structure:

- `opamp_core.py` — current promoted core RC
- `experiments/` — current focused output-stage probe history
- `prod/components/` — promoted HDL21 generators
- `prod/rc/` — current RC assembly and selected parameters
- `prod/tests/` — acceptance gates for the current RC

Current mode:

- `opamp_core.py` is the active RC and main edit target
- `experiments/core_h10_analog_class_ab/` keeps the focused probe suite and metrics for the current output-stage topology
- older output-stage hypotheses were removed to keep one active line of work

Recommended entry points:

```bash
python3 -m opamp.v3.run_tests rc_mandatory
python3 -m opamp.v3.run_tests output_stage_experiments
python3 -m opamp.v3.run_tests prod_reduced_acceptance
python3 -m opamp.v3.run_tests prod_release
```
