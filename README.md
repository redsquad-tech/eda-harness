# EDA Harness

Repository for developing, testing, and incrementally closing analog blocks in `hdl21`, primarily an `auto-zero` opamp in `sky130`.

This document explains:
- what is in the project
- how to work in the repo
- which development rules are mandatory
- how to test changes
- where to find current status and target requirements

## Project

Branch layout:

- `opamp/v3` is the main active branch
- `opamp/v3/prod` is the release-candidate integration, acceptance, and bundle path
- `opamp/v1` contains the legacy baseline opamp and legacy tests
- `components/` now keeps only reusable low-level blocks and shared utilities

Current primary target block:
- a low-residual-offset `auto-zero` opamp in `sky130`

Base specification:
- [opamp_az_spec.md](/home/vadim/work/eda-harness/opamp_az_spec.md)

Current engineering status:
- [track.md](/home/vadim/work/eda-harness/track.md)

Rules for components, generators, and test structure:
- [hdl21.md](/home/vadim/work/eda-harness/hdl21.md)
- [tesing_guide.md](/home/vadim/work/eda-harness/tesing_guide.md)

Additional utility document:
- [spice2xschem/README.md](/home/vadim/work/eda-harness/spice2xschem/README.md)

## Core Working Principle

The project is run **through tests**.

Mandatory organizational rule:
- every new opamp architecture lives in its own folder: `opamp/<amp_arch_name>`
- tests for that architecture live alongside it in `opamp/<amp_arch_name>/tests`
- `components/` is used only for low-level reusable blocks that are unlikely to change often
- top-level opamp pieces (`opamp_core`, `opamp_az_top`, `frontend_az`, stage composition, and related test logic) should live in versioned architecture folders, not in `components/`

Main rule:
- **everything must be covered by tests**

The practical process is always:
1. express the requirement as a test
2. run the test and get a real red metric
3. localize the bottleneck from the metrics
4. refine or fix the test if needed
5. only then propose a circuit hypothesis
6. validate that hypothesis with automated tests
7. repeat until the metric turns green

## Mandatory Development Rules

### 1. Test First, Then Circuit

Before any substantial circuit change, it must be clear:
- which metric is bad
- which test measures it
- what improvement is expected after the change

If there is no test:
- add the test first

If the test exists but does not give an unambiguous signal:
- improve the test first

### 2. Bottlenecks Are Identified Only Through Metrics

Do not tune sizes or topology by intuition alone.

You must:
- measure the current state
- record real numbers
- understand where quality is being lost:
  - gain
  - swing
  - drive
  - offset
  - pedestal
  - settling
  - leakage
  - corner robustness

Only after that should you choose the next hypothesis.

### 3. Tests Can Be Wrong

This is a key repository rule.

Always remember:
- the test can be formulated incorrectly
- the measurement window can be wrong
- the bench can distort the operating point
- the loop-break setup can measure something other than what it seems
- a top-level budget test can accidentally count edge feedthrough artifacts as useful error

If a problem is not getting solved:
- **first look for an error in the test**

This is not an exception. It is a mandatory check.

### 4. If the Result Does Not Match Physical Intuition, Check Measurement First

Typical examples:
- suspiciously large gain
- very strange phase margin
- an unexpected collapse after a "reasonable" change
- nominal looks good but a standalone block produces nonsense

In such cases, first check:
- fixture correctness
- meaning of the metric being measured
- measurement window
- bias point
- sign convention

Only after that should you redesign the circuit.

### 5. Separate the Primitive Library from the Opamp Architecture

`components/`:
- library of low-level reusable generators
- leaf / primitive analog blocks
- shared simulation helpers

`opamp/<amp_arch_name>/`:
- the entire concrete opamp architecture
- its top-level blocks
- its local `specs`, `tb`, `run_*`, and `tests`

`opamp/v1/tests/...`:
- legacy baseline tests
- kept for comparison and migration only

`opamp/v3/prod/...`:
- release-candidate integrated DUT
- acceptance tests
- bundle generation

Do not mix:
- low-level reusable primitives
- frequently changing top-level opamp architecture
- generic component characterization
- product-specific spec assertions

Details:
- [tesing_guide.md](/home/vadim/work/eda-harness/tesing_guide.md)

### 6. Every Important Change Needs a Quick Run

Minimum:
- a fast nominal screen
- the affected budget tests

Do not make a long series of circuit changes without intermediate runs.

### 7. After Nominal Closure, Go to Corners

Do not treat the design as ready just because it passes `TT nominal`.

Minimum before saying the circuit is "almost ready":
- nominal tests
- reduced `PVT`

Minimum before tape-out:
- full `PVT`
- `MC`
- `PEX`
- post-layout verification

## Recommended Work Cycle

For any problem:

1. Find the current test or add a new one.
2. Get a numerical red metric.
3. Check that the test is measuring the intended behavior.
4. Capture debug metrics and raw waveforms if there is doubt.
5. Formulate one hypothesis.
6. Validate the hypothesis with automated tests.
7. If the hypothesis fails, record that in [track.md](/home/vadim/work/eda-harness/track.md).
8. If several hypotheses fail, return to the test and look for a measurement problem.

## How to Read the Project

Recommended order:
1. [README.md](/home/vadim/work/eda-harness/README.md)
2. [opamp_az_spec.md](/home/vadim/work/eda-harness/opamp_az_spec.md)
3. [track.md](/home/vadim/work/eda-harness/track.md)
4. [tesing_guide.md](/home/vadim/work/eda-harness/tesing_guide.md)
5. [hdl21.md](/home/vadim/work/eda-harness/hdl21.md)
6. [opamp/v3](/home/vadim/work/eda-harness/opamp/v3) for active research
7. [opamp/v3/prod](/home/vadim/work/eda-harness/opamp/v3/prod) for RC, acceptance, and bundle flow
8. [opamp/v1](/home/vadim/work/eda-harness/opamp/v1) only if legacy comparison is needed

## How to Test

For a new opamp architecture:

```bash
python3 -m unittest discover -s opamp/<amp_arch_name>/tests -v
```

Legacy baseline examples:

### Fast Checks

```bash
python3 -m unittest -v opamp.v1.tests.structural.opamp_core.test_opamp_core__screen__fast_nominal
python3 -m unittest -v opamp.v1.tests.structural.opamp_az_top.test_opamp_az_top__budget__precision_ppa
```

### Long but Useful Checks

```bash
python3 -m unittest -v opamp.v1.tests.structural.opamp_core.test_opamp_core__char__pvt
python3 -m unittest -v opamp.v1.tests.structural.opamp_az_top.test_opamp_az_top__char__reduced_pvt
```

### Main Active Branch

For the main branch:

```bash
python3 -m opamp.v3.run_tests quick_tt
python3 -m opamp.v3.run_tests prod_reduced_acceptance
python3 -m opamp.v3.run_tests prod_release
```

### Legacy Full Run

```bash
python3 -m unittest discover -s opamp/v1/tests -v
```

For active work, the default path is no longer the legacy root test tree. Use `opamp/v3` and `opamp/v3/prod`.

## What Matters Right Now

At the moment:
- `v3` is the main active branch
- `opamp/v3/prod` is the RC path for integrated DUT, acceptance, SPICE export, and bundle generation
- `v1` is legacy baseline only
- the main blocker before tape-out is still `AZ` reduced-PVT and MC closure

Current metrics and experiment history:
- [track.md](/home/vadim/work/eda-harness/track.md)

## What Is Needed Before Tape-Out

Minimum path:
1. close the schematics across reduced/full `PVT`
2. run `MC`
3. do layout
4. run `PEX`
5. repeat signoff checks post-layout

As of now, tape-out readiness is not there yet.

## Markdown Document Index

- [README.md](/home/vadim/work/eda-harness/README.md)
- [hdl21.md](/home/vadim/work/eda-harness/hdl21.md)
- [opamp_az_spec.md](/home/vadim/work/eda-harness/opamp_az_spec.md)
- [track.md](/home/vadim/work/eda-harness/track.md)
- [tesing_guide.md](/home/vadim/work/eda-harness/tesing_guide.md)
- [opamp/v1/README.md](/home/vadim/work/eda-harness/opamp/v1/README.md)
- [spice2xschem/README.md](/home/vadim/work/eda-harness/spice2xschem/README.md)
