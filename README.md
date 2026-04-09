# EDA Harness

Repository for iterative analog development in `hdl21`, primarily the `auto-zero` opamp in `sky130`.

## Main Links

- Specification: [opamp_az_spec.md](/home/vadim/work/eda-harness/opamp_az_spec.md)
- Experiment ledger: [track.md](/home/vadim/work/eda-harness/track.md)
- HDL21 rules: [hdl21.md](/home/vadim/work/eda-harness/hdl21.md)
- Testing guide: [tesing_guide.md](/home/vadim/work/eda-harness/tesing_guide.md)

## Project Layout

- `opamp/<arch>/` — one architecture per directory
- `opamp/v3` — main active branch
- `opamp/v3/experiments/<exp-name>/` — independent experiment directories
- `opamp/v3/prod/components/` — promoted HDL21 generators used in the best known versions
- `opamp/v3/prod/rc/` — RC assembly and promoted parameter set
- `opamp/v3/prod/tests/` — acceptance gates for the promoted RC
- `opamp/v1` — legacy baseline
- `components/` — reusable low-level blocks only

## Development Process

The project is run through independent experiments.

Working loop:

1. Read the specification in [opamp_az_spec.md](/home/vadim/work/eda-harness/opamp_az_spec.md).
2. Formulate a hypothesis and explicit metrics.
3. Create a new experiment directory:
   `opamp/<arch>/experiments/<exp-name>/`
4. Put everything needed for the experiment into that directory:
   - hypothesis test files
   - experiment-specific generators
   - experiment helpers
   - `metrics.json`
5. If the hypothesis needs a modified generator, create a new generator file for that experiment.
   Do not edit the baseline generator in place.
6. Run the experiment tests.
7. Compare the result against the current baseline.
8. If the result is better than the baseline on the intended metrics:
   - copy the winning generator logic into `opamp/<arch>/prod/components/`
   - update `opamp/<arch>/prod/rc/` so the current RC is built from the promoted blocks and parameters
9. Record the experiment and short result in [track.md](/home/vadim/work/eda-harness/track.md).
10. Repeat.

Experiments are independent. They may import:

- reusable low-level blocks from `components/`
- promoted opamp blocks from `opamp/<arch>/prod/components/`

## Development Rules

- Use a TDD approach.
- Keep a clear separation between DUT modules and tests.
- Prefer small resistors and capacitors inside the DUT.
- Prefer moving heavy elements out of the DUT and into surrounding circuitry when possible.
- Do not change the circuit without a measurable test.
- Do not modify a baseline generator for an experiment; create a new generator local to the experiment.
- Identify generator files by the component they implement.
- Do not promote a result into `prod` unless it is better than the current baseline on the intended metric.

## Promotion Roles

- `v3` is the main research branch.
- `v3/experiments` is where independent hypotheses are executed.
- `v3/prod/components` contains only promoted generators.
- `v3/prod/rc` binds promoted generators and parameters into the current release candidate.
- `v1` is for legacy comparison only.

## Typical Commands

Main active branch:

```bash
python3 -m opamp.v3.run_tests quick_tt
python3 -m opamp.v3.run_tests prod_reduced_acceptance
python3 -m opamp.v3.run_tests prod_release
```

Legacy:

```bash
python3 -m unittest discover -s opamp/v1/tests -v
```
