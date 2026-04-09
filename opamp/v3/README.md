# Opamp V3

`v3` is the main active opamp architecture.

Structure:

- `experiments/` — independent experiment directories
- `prod/components/` — promoted HDL21 generators
- `prod/rc/` — current RC assembly and selected parameters
- `prod/tests/` — acceptance gates for the current RC

Experiment rule:

- every experiment gets its own directory under `experiments/`
- if a hypothesis needs a modified generator, create a new generator file inside that experiment
- do not edit the baseline generator in place for a hypothesis
- store experiment results in `metrics.json`
- record the short outcome in [track.md](/home/vadim/work/eda-harness/track.md)

Promotion rule:

- if an experiment beats the baseline on the intended metrics, promote the winning generator logic into `prod/components/`
- update `prod/rc/` to build the new release candidate from promoted blocks

Recommended entry points:

```bash
python3 -m opamp.v3.run_tests quick_tt
python3 -m opamp.v3.run_tests prod_reduced_acceptance
python3 -m opamp.v3.run_tests prod_release
```
