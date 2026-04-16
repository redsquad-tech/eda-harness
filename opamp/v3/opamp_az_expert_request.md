## Files

- SPICE netlist: [opamp_az_top.spice](/home/vadim/work/eda-harness/opamp/v3/opamp_az_top.spice)
- Python generator: [opamp_az_top.py](/home/vadim/work/eda-harness/opamp/v3/opamp_az_top.py)

## Current State

This is a SKY130 auto-zero op-amp prototype. The major recent bugs are already fixed:
- core DC operating point is healthy
- output-driver no longer overloads `VDRV`
- AZ servo is now truly latched off outside `AZ_NULL`
- residual post-AZ offset is essentially gone

The remaining problem is no longer basic functionality. It is **analog performance**.

## Measured Metrics

### Core / open-loop

Current compensated core is intentionally tuned for minimum stability closure:
- `w_in = 14 um`
- `c_comp = 2.7 pF`

Measured nominal open-loop metrics at `TT, 1.8 V, 27 C, CL=1 pF`:
- `AOL ≈ 57.2 dB`
- `GBW ≈ 80.6 kHz`
- `PM ≈ 32.7 deg`
- `GM ≈ 5.6 dB`
- `Iq ≈ 8.07 uA`

Spec targets:
- `AOL >= 65 dB` minimum
- `GBW >= 0.3 MHz` minimum
- `PM >= 30 deg`
- `GM >= 5 dB`
- `Iq <= 20 uA`

So right now:
- stability is barely acceptable
- current is acceptable
- **AOL is too low**
- **GBW is much too low**

### AZ

Post-fix AZ behavior:
- residual offset after AZ:
  - `≈ -0.254 uV`
- hold over about `200 us`:
  - output drift `≈ -5.96 mV`

So the dominant unresolved issue is now **core gain/bandwidth**, not AZ residual offset.

## What Was Already Tried

### Stability / compensation

Increasing `c_comp` was the only clean way found to get positive phase margin.

Observed trend:
- larger `c_comp` improves PM
- but reduces GBW

### Stage2 gain

Increasing `l_stage2_p` raises `AOL`, but strongly hurts phase margin.

Observed trend:
- `l_stage2_p = 10 -> 14 -> 18 um` improves gain
- but makes PM much worse unless `c_comp` is increased again

### Stage1 gm

Increasing `w_in` raises both `AOL` and `GBW`, but also destabilizes the loop.

Observed trend:
- `w_in = 10 -> 14 -> 18 um` increases gain and bandwidth
- but PM collapses unless `c_comp` is raised significantly

### Stage1 bias current

Reducing `r_stage1_bias` was low-yield:
- small gain change
- current increases
- PM does not improve materially

## Engineering Problem To Solve

We need a way to raise:
- `AOL` from about `57 dB` to at least `65 dB`
- `GBW` from about `80 kHz` to at least `300 kHz`

while keeping:
- `PM >= 30 deg`
- `GM >= 5 dB`
- `Iq <= 20 uA`

## Specific Question

What is the most defensible next architectural move to improve **AOL + GBW simultaneously** without breaking stability?

Please focus on concrete options for this topology:

1. Keep the same two-stage architecture and retune:
- stage1 gm
- stage2 output resistance
- Miller compensation / lead compensation

2. Change second-stage topology:
- e.g. different stage2 load / gain structure

3. Change compensation strategy:
- e.g. add nulling resistor / feedforward zero / other compensation element

4. Change output-path coupling if it is still loading the high-gain node too much in AC

## Short Version

The op-amp now works and AZ basically works.  
What does **not** meet spec is:
- `AOL`
- `GBW`

We need a path from roughly:
- `57 dB / 80 kHz / 33 deg`

to at least:
- `65 dB / 300 kHz / >=30 deg`

without blowing the current budget.
