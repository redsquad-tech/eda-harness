# opamp/v4

`v4` uses its own local primitives and generators.

Current source of truth:
- [opamp.py](/home/vadim/work/eda-harness/opamp/v4/opamp.py)
- [generators.py](/home/vadim/work/eda-harness/opamp/v4/generators.py)

Notes:
- The schematic is compiled for `sky130`.
- The `v4` design is not assembled from reusable analog building blocks in `components/`.
- Instead, `v4` uses local HDL21 generators for its wrapper/support circuitry and local HDL21 device composition for the core schematic.
- `components/` is still used infrastructurally, for example through simulation/ netlisting helpers, but not as the schematic source for the `v4` op-amp core.
