# Opamp V3

Clean-sheet workspace for the next opamp architecture after the `v2`
exploration plateau.

Rules:
- do not modify the baseline in `components/` unless needed
- do not reuse `v2` architectural hacks by default
- local tests live next to the code in `opamp/v3/tests`
- `components/*` is only for low-level reusable blocks

Design intent:
- PMOS-input first stage remains the baseline assumption
- the final output path must be non-inverting by construction
- disable behavior is a first-class requirement, not a later patch
- sampled-data `AZ` remains separate from the static core

Current status:
- simulation-backed core verification is active
- current `v3` baseline closes minimum nominal `TT` goals for:
  - `AOL`
  - `GBW`
  - `PM`
  - `GM`
  - `IQ`
- current main open issues:
  - shutdown leakage
  - source drive across corners
  - low-VDD / cold loop robustness
- shutdown-clamp experiments on the existing loop have been exhausted and are tracked in `track.md`
- next `v3` work should be a shutdown-aware topology revision, not more local clamp patches

Recommended test target:

```bash
python3 -m opamp.v3.run_tests quick_tt
```
