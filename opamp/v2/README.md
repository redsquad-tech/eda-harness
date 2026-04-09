# Opamp V2

Isolated workspace for the `v2` opamp architecture.

Rules:
- do not modify the baseline in `components/` unless needed
- new opamp architecture work starts here
- local tests live next to the code in `opamp/v2/tests`
- `components/*` is only for low-level reusable blocks

Recommended test targets:

```bash
python3 -m opamp.v2.run_tests quick_tt
python3 -m opamp.v2.run_tests full_tt_nominal
python3 -m opamp.v2.run_tests reduced_pvt
python3 -m opamp.v2.run_tests full_pvt
```

Target intent:
- `quick_tt`: package and architecture smoke, fast core TT screen, top-level AZ TT precision
- `full_tt_nominal`: full core TT nominal budget plus top-level AZ TT precision
- `reduced_pvt`: core load sweep plus top-level reduced-PVT AZ characterization
- `full_pvt`: full core PVT characterization plus top-level reduced-PVT AZ characterization

`unittest discover` still works, but the named targets above are the preferred workflow because they avoid duplicated nominal checks.
