# Opamp Core V3: brief for external analog review

## Files

- DUT netlist: `opamp/v3/opamp_core.spice`
- Main DUT source: `opamp/v3/opamp_core.py`

## Current topology

Current core is now a direct-output two-stage op-amp.

1. `stage1`
- PMOS differential pair
- NMOS active-load / single-ended conversion
- PMOS tail-current generation and enable/disable hooks

2. `stage2`
- NMOS common-source gain device `m_stage2_n`, gate driven by `VX`
- PMOS current-source load `m_stage2_p`, gate driven by local bias node `ibias2`
- Miller compensation branch from `VX` to `VDRV`
- optional series compensation resistor `Rz` in series with `Cc`

3. `output`
- `VOUT` is tied directly to `VDRV`
- the old shared output-driver / shared gate-output-stage is intentionally removed from the main gain loop

## Why the topology was changed

Earlier diagnostics showed that the old resistively driven output path was the main bottleneck in the compensated loop.

Key evidence:
- standalone output path low-frequency transfer `VDRV -> VOUT` was only about `0.087 V/V` (`-21.19 dB`)
- bypassing that path gave much higher low-frequency gain than the full core
- therefore the previous loop was not behaving like a clean two-stage op-amp

## Current main failure

After removing the output path from the main loop, the core became much faster, but its intrinsic open-loop gain is still very low.

Current measured behavior on TT / 1.8 V / 27 C:
- `AOL ~= 29.41 dB`
- `GBW ~= 1.31 MHz` with `Cc = 2.7 pF`, `Rz = 0`
- `PM ~= 17.23 deg`
- `GM ~= 1.98 dB`
- `Iq ~= 7.50 uA`

So the problem is now no longer output-path loading. The problem is that the direct-output core itself has:
- high bandwidth
- low phase margin
- very low open-loop gain

## Key measured data

### Baseline direct-output core

From `tests/.rz_sweep/pt_00.json`:
- `Cc = 2.7 pF`
- `Rz = 0`
- `AOL = 29.412 dB`
- `GBW = 1.311 MHz`
- `PM = 17.235 deg`
- `GM = 1.984 dB`
- `Iq = 7.501 uA`

### Smaller `Cc` without `Rz`

From `tests/.rz_sweep/pt_01.json` and `pt_03.json`:
- `Cc = 1.2 pF`, `Rz = 0` -> `GBW = 2.127 MHz`, `PM = 1.755 deg`
- `Cc = 1.0 pF`, `Rz = 0` -> `GBW = 2.314 MHz`, `PM = -1.480 deg`

Interpretation:
- reducing `Cc` increases bandwidth strongly
- but phase margin quickly collapses

### `Rz` effect

From `tests/.rz_sweep/pt_10.json`:
- `Cc = 2.7 pF`, `Rz = 100k`
- `AOL = 29.412 dB`
- `GBW = 1.206 MHz`
- `PM = 29.984 deg`
- `GM = 3.952 dB`

From `tests/.rz_sweep/pt_11.json`:
- `Cc = 1.5 pF`, `Rz = 100k`
- `AOL = 29.412 dB`
- `GBW = 1.828 MHz`
- `PM = 14.834 deg`
- `GM = 2.379 dB`

Interpretation:
- `Rz` does help phase margin
- but `Rz` does not increase open-loop gain at all
- the core still sits around only `29.4 dB` gain across all tested compensation points

## Main diagnosis at this stage

The previously integrated output path was indeed a bad extra stage inside the compensated loop, and removing it was the right move.

However, after removing that output path, the direct-output core still has a serious intrinsic gain problem:
- compensation can trade bandwidth against phase margin
- but compensation does not move `AOL`
- `AOL` appears stuck around `29.4 dB`

So the current blocker is now the gain structure of the direct-output core itself, not the old output-stage dynamics.

## What would be most useful from the specialist

Please review the direct-output core and advise what structural change is most likely needed to raise `AOL` substantially while keeping `GBW` in the `>= 0.3 MHz` range and `PM >= 30 deg`.

Specifically:

1. Does the present second stage simply have too little intrinsic gain for a direct-output topology?
- `m_stage2_n` / `m_stage2_p`
- load seen at `VDRV`
- missing gain buffering or too-low `ro`

2. Is the first stage too weak relative to the direct-output second stage?
- insufficient first-stage gain
- insufficient effective transconductance into the Miller-compensated node
- poor gain partition between stage1 and stage2

3. Which change is most defensible to raise gain without throwing away the new bandwidth?
- strengthen or re-bias stage1
- increase `ro` in stage2 by device-length / current-structure changes
- change stage2 topology
- add an explicit gain-enhancing load or cascode-like structure

4. Is direct `VDRV -> VOUT` fundamentally too low-gain in this topology, meaning a proper output buffer is still needed, but outside the compensated gain path?

## Short version

The old output stage inside the loop was removed after diagnostics proved it was the wrong bottleneck.

Now the core behaves like this:
- bandwidth is already around `1.2 .. 2.3 MHz`
- phase margin can be moved with `Cc` / `Rz`
- but open-loop gain is stuck around only `29.4 dB`

So the current question for review is not compensation-first. It is:

**Why is the direct-output two-stage core itself so low-gain, and what is the cleanest structural change to raise `AOL` significantly without destroying the newly recovered bandwidth?**
