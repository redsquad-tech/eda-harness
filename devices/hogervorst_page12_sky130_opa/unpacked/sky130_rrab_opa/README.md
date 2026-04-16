# Sky130 HDL21 rail-to-rail / class-AB op-amp

This package contains a **Sky130-oriented HDL21 architectural implementation** of the
high-gain two-stage CMOS op-amp discussed from the Hogervorst / Monticelli-style topology:

- complementary input pairs,
- high-resistance first-stage nodes,
- Monticelli-inspired class-AB gate-drive cell,
- push-pull output stage,
- dual RC-C compensation,
- product wrapper with NASP-style pins.

## What is in here

- `generators.py`
  - small inverter
  - transmission gate
  - NMOS / PMOS rail switch
  - NMOS / PMOS differential pair
  - NMOS / PMOS current source
  - PMOS / NMOS cascode branch
  - bias generator
- `opamp.py`
  - complementary cascode first stage
  - simplified Monticelli cell
  - class-AB output stage
  - top wrapper `neuron_core_oa_sky130`
  - helper `compile_for_sky130`

## Design intent

This is an **architectural first cut**, not a signoff-ready clone of the original paper.
The goals are:

1. keep the same high-level analog structure,
2. preserve the requested external pinout,
3. keep disabled / inference mode behavior structurally visible,
4. leave calibration and scan-chain insertion points obvious.

## Main deviations from a final production design

- The auto-zero / offset-calibration loop is only a **hook**:
  `d_az_oa` currently shorts the first-stage differential nodes.
  A real design would add storage capacitors, trim injection, sequencing, and verification.
- The daisy-chain test controller is only a **stub**:
  `d_tcki -> d_tcko` and `d_tdi -> d_tdo` are simple pass-through connections.
- Compensation uses generic HDL21 `Res` and `Cap` elements.
  For a full physical Sky130 implementation, these should be replaced or wrapped by the
  chosen resistor / MiM-cap technology cells.
- Pin name `avdd1p2` is preserved for compatibility with the uploaded requirement document,
  even though this Sky130 implementation is intended as a **1.8 V-class** first pass.

## Recommended starting point for simulation

Use the top generator directly:

```python
import hdl21 as h
from sky130_rrab_opa.opamp import NeuronOaParams, neuron_core_oa_sky130, compile_for_sky130


dut = neuron_core_oa_sky130(NeuronOaParams())
compile_for_sky130(dut)
```

## Rough Sky130-oriented target envelope

These are **design targets**, not guaranteed post-layout numbers:

- Supply: 1.8 V nominal
- Load capacitance: up to 1 pF
- Open-loop gain: ~70 dB to 85 dB at TT
- GBW: ~0.8 MHz to 2 MHz
- Phase margin: ~50 deg to 70 deg in unity gain
- Output drive: at least +/-25 uA, with class-AB headroom for transient peaks
- Inference-mode quiescent current: ~8 uA to 15 uA
- Disabled-mode leakage: targeted below ~50 nA before full optimization
- Input common-mode range: substantially wider than the original half-supply-limited spec
- Offset: millivolt-class before a real AZ / trim loop is added

## Where to tighten next

1. replace the simplified Monticelli bridge with a paper-accurate floating-bias cell,
2. add true auto-zero storage and latching,
3. size compensation from AC simulations instead of rules of thumb,
4. replace ideal passives with physical PDK cells,
5. close disabled-mode leakage with explicit state-dependent bias collapse,
6. add the actual scan / test latch chain.
