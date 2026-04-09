# v3 Product Layer

This package contains the production-facing `v3` RC integration layer:

- integrated hybrid DUT generator
- customer bundle assembly
- production acceptance tests
- local copy of the maximum requirement set

Current integration strategy:

- native AZ frontend from `opamp/v3/frontend_az.py`
- `v3` core from `opamp/v3/opamp_core.py`

This package is the current release-candidate source of truth for the
integrated `v3` product path.

Current promoted RC cases:

- core: `K1_stage2p10`
- az: `m4r1_cap300_wswn1p1_wswp1p6_nf2`

Process:

1. run autonomous research in `opamp/v3`
2. promote the best completed branch into `opamp/v3/prod/rc.py`
3. run `prod_release`
4. export the production bundle from `opamp/v3/prod`

Important files:

- `MAXIMUM_SPEC.md`: copied maximum requirements used by acceptance tests
- `rc.py`: current promoted RC configuration and metadata
- `opamp_az_top.py`: integrated production DUT generator
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
