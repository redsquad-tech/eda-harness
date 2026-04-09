# v1 Legacy Opamp Track

This directory contains the legacy integrated opamp implementation that
previously lived partly in `components/` and in the root `tests/` tree.

It is kept for:

- baseline comparison
- legacy characterization
- old customer-facing reference benches
- migration support while `v3` keeps evolving

Main legacy blocks:

- [frontend_az.py](/home/vadim/work/eda-harness/opamp/v1/frontend_az.py)
- [opamp_core.py](/home/vadim/work/eda-harness/opamp/v1/opamp_core.py)
- [opamp_az_top.py](/home/vadim/work/eda-harness/opamp/v1/opamp_az_top.py)

Legacy tests:

- [tests](/home/vadim/work/eda-harness/opamp/v1/tests)

This is not the main branch for new work.

New development and release-candidate work should target:

- [opamp/v3](/home/vadim/work/eda-harness/opamp/v3)
- especially [opamp/v3/prod](/home/vadim/work/eda-harness/opamp/v3/prod)
