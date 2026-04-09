# v3 Experiments

Each experiment lives in its own directory:

- `opamp/v3/experiments/<exp-name>/`

Rules:

- experiments are independent
- each experiment may define its own generator modules
- if a hypothesis needs a modified generator, create a new generator file instead of editing the baseline generator in place
- generator files are identified by the component they implement
- each experiment directory keeps everything it needs locally:
  - hypothesis notes
  - test files
  - experiment-specific generators
  - helper scripts if needed
  - `metrics.json`

Allowed imports:

- reusable low-level blocks from `components/`
- promoted production generators from `opamp/v3/prod/components/`

Promotion rule:

- if an experiment beats the current baseline on its intended metrics, copy the winning generator logic into `opamp/v3/prod/components/` and update `opamp/v3/prod/rc/`

