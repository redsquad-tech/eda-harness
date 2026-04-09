# v3 Product Layer

This package contains the promoted `v3` release-candidate layer.

Structure:

- `components/` — HDL21 generators taken from the best completed experiments
- `rc/` — script-level selection of promoted generators and their parameters
- `tests/` — acceptance gates for the current RC
- bundle/report scripts — export the current RC and its test collateral

Process:

1. run independent experiments in `opamp/v3/experiments/`
2. if a result is better than the baseline, copy its generator logic into `prod/components/`
3. update `prod/rc/` to select the winning blocks and parameter values
4. run acceptance in `prod/tests/`
5. export bundle/report from the promoted RC

Current promoted RC cases:

- core: `K1_stage2p10`
- az: `m4r1_cap300_wswn1p1_wswp1p6_nf2`

Important files:

- `MAXIMUM_SPEC.md`: copied maximum requirements used by acceptance tests
- `rc/`: current promoted RC configuration and metadata
- `components/opamp_az_top.py`: integrated production DUT generator
- `tests/test_prod__acceptance__maximum_spec.py`: reduced release gate
- `tests/test_prod__acceptance__full_pvt_core.py`: full-PVT core acceptance
- `tests/test_prod__acceptance__full_pvt_top.py`: full-PVT top-level AZ acceptance
- `tests/test_prod__acceptance__load_sweep.py`: load sweep acceptance
- `tests/test_prod__acceptance__timing_and_mc.py`: timing sweep and MC acceptance

Recommended commands:

- reduced release gate:
  - `python3 -m opamp.v3.run_tests prod_reduced_acceptance`
- full release gate:
  - `python3 -m opamp.v3.run_tests prod_release`
- structured reduced report:
  - `python3 -m opamp.v3.prod.release_report reduced`
- rebuild customer bundle:
  - `python3 -m opamp.v3.prod.assemble_bundle`
- rebuild SPICE-only customer archive:
  - `python3 -m opamp.v3.prod.assemble_customer_archive --spice-only`
