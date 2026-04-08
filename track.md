# Opamp Experiment Ledger

## Goal

This file is the compact experiment memory for the `sky130` opamp work.

Use it to:
- track good and bad hypotheses with metrics
- avoid repeating dead branches
- keep the current active baseline explicit

Keep entries short:
- `Hypothesis`
- `Change`
- `Result`
- `Decision`

## Current Status

Two tracks exist:

1. Baseline `AZ` product track
- nominal `AZ` precision works
- reduced-PVT `AZ` precision still fails badly, especially hot/fast pedestal and settling
- not tapeout-ready

2. `v3` static-core track
- shutdown leakage is now essentially solved
- enabled-core closure is still open
- current main blocker: worst-corner stability

## Active `v3` Baseline

Current promoted default in `opamp/v3/opamp_core.py`:
- helper-link isolation in shutdown enabled
- `w_tail = 4.0 um`
- `r_stage1_bias = 2.5e6 ohm`
- `l_in = 3.0 um`

Current measured metrics:

Nominal `TT / 1.8 V / 27 C`
- direct gain `≈ 62.68 dB`
- `IQ ≈ 27.79 uA`
- `VOUT_low ≈ 0.1146 V`
- disabled leakage `≈ 0.97 nA`
- raw offset `≈ 1044 uV`

Hard corner `SS / 1.6 V / 125 C`
- `AOL ≈ 60.43 dB`
- `GBW ≈ 230.7 kHz`
- `PM ≈ 36.71 deg`
- `GM ≈ -22.73 dB`
- `IQ ≈ 20.96 uA`

Interpretation:
- shutdown: closed
- nominal gain/current: improved but still not at target
- low-side swing: still misses
- raw offset: still requires `AZ`
- worst-corner stability: main blocker

## Current Priorities

1. Fix worst-corner `GM` and loop robustness.
2. Improve nominal `AOL / IQ` further.
3. Recover low-side swing.
4. Only then revisit broader PVT/ MC and full `AZ` integration for `v3`.

## Baseline `AZ` Track

### Current Best Known Baseline `AZ` Point

Default:
- `FrontendAzParams(c_az=70 fF, r_vcm_top=8e2, r_vcm_bot=5)`

Nominal `TT`
- residual offset `≈ 7.91 uV`
- pedestal `mid50 ≈ 23.56 uV`
- settling `mid50 ≈ 7.70 uV`

Reduced PVT
- `SS / 1.6 V / -40 C`: acceptable
- `SS / 1.6 V / 125 C`: fails
- `FF / 1.98 V / -40 C`: fails
- `FF / 1.98 V / 125 C`: fails badly

Conclusion:
- nominal `AZ` is good
- reduced-PVT `AZ` is still not signoff-ready

### Baseline `AZ` Hypothesis Ledger

#### Promoted

1. `PHI3` must carry the live signal path
- Hypothesis:
  - `PHI3` should be the real signal-transfer phase, not only a measurement window
- Change:
  - moved live `VINP`/ `VINN` signal transfer into `PHI3`
- Result:
  - nominal residual offset improved `≈ 131.5 uV -> 7.91 uV`
  - worst reduced-PVT residual offset improved `≈ 16326 uV -> 2675 uV`
- Decision:
  - keep

2. Interior-window (`mid50`) metrics are the correct product metrics
- Hypothesis:
  - full-window metrics were over-counting switching feedthrough
- Change:
  - moved `AZ` product evaluation to interior-window measurement
- Result:
  - nominal product metrics became honest and stable
- Decision:
  - keep

#### Rejected

1. Simple three-phase split alone fixes corner sensitivity
- Result:
  - nominal improved
  - reduced-PVT became worse in `FF`
- Decision:
  - do not repeat without topology change

2. Mirrored correction on `VXN`
- Result:
  - worsened pedestal and settling
  - even very weak variants broke nominal behavior
- Decision:
  - dead branch

3. Floating or isolated `hold -> apply` path on `VXP`
- Result:
  - nominal collapsed
  - `FF` corners became catastrophic
- Decision:
  - dead branch

4. Separate correction path plus direct live `VINP` path
- Result:
  - better than some dead branches
  - still unacceptable hot-`FF` pedestal
- Decision:
  - not enough by itself

5. Small `R/C` retuning
- Result:
  - no robust closure
- Decision:
  - do not spend more time here without a topology change

## `v3` Core Track

### `v3` Core Design Rules

Keep:
- PMOS-input first stage
- explicit `VX` and `VDRV` nodes
- non-inverting output path
- sampled-data `AZ` separate from the static core

Do not repeat:
- clamp-only shutdown tuning
- direct PMOS input-gate forcing without isolation
- scalar `r_stage2_bias` tuning as the main lever
- `r_gp` tuning as the main lever
- pure helper-strength sweeps as a substitute for output-path redesign

## `v3` Hypothesis Ledger

### Promoted

1. Split-tail first stage plus isolated internal input gates helps shutdown
- Hypothesis:
  - shutdown must be structural, not just stronger clamps
- Change:
  - split first-stage tail
  - isolate internal gates with TGs
  - clamp only the internal gates in shutdown
- Result:
  - worst disable corner improved from catastrophic-clamp regimes to `≈ 1977.6 nA`
- Decision:
  - keep as the structural basis

2. Shutdown current is not in the first-stage tail path
- Hypothesis:
  - remaining leakage may still come from the first stage
- Change:
  - added debug current probes to shutdown diagnostics
- Result:
  - at `FF / 1.98 V / -40 C`:
    - total disable current `≈ 16037.8 nA`
    - tail current `≈ 0.0008 nA`
    - `VX` current `≈ 0.0025 nA`
    - `VREF` current `≈ 0.0025 nA`
    - `VDRV` current `≈ -16037.7 nA`
- Decision:
  - stop first-stage shutdown work

3. The real shutdown path is `m_gp_off -> r_gp -> vdrv -> m_stage2_off`
- Hypothesis:
  - the `VDRV` path still hides the true leakage root cause
- Change:
  - split `VDRV` current into:
    - stage-2 PMOS load
    - stage-2 NMOS
    - stage-2 off clamp
    - direct `VDRV -> VOUT`
    - helper-gate link
- Result:
  - baseline `FF / 1.98 V / -40 C`:
    - `i_probe_stage2_off_nA ≈ -16037.7`
    - `i_probe_vdrv_gp_nA ≈ -16037.5`
    - `i_probe_vdrv_out_nA ≈ -0.21`
    - other stage-2 currents negligible
- Decision:
  - root cause confirmed

4. Helper-link isolation in shutdown closes disable leakage
- Hypothesis:
  - an `EN`-controlled series switch in the helper gate-link will break the clamp fight
- Change:
  - added `isolate_gp_link_in_shutdown`
- Result:
  - `FF / 1.98 V / -40 C` disabled leakage:
    - `≈ 16037.8 nA -> 0.54 nA`
  - nominal direct gain stayed `≈ 58.58 dB`
  - nominal `IQ` stayed `≈ 40.60 uA`
  - nominal `VOUT_low` stayed `≈ 0.1149 V`
- Decision:
  - promoted to default

5. Lighter first-stage bias is the best first `AOL / IQ` lever
- Hypothesis:
  - first-stage current is too strong for the gain being delivered
- Change:
  - `w_tail = 4.0 um`
  - `r_stage1_bias = 2.5e6 ohm`
- Result:
  - versus shutdown-fixed baseline:
    - direct gain `≈ 58.58 dB -> 62.04 dB`
    - `IQ ≈ 40.60 uA -> 28.23 uA`
    - low swing slightly worse: `≈ 0.1149 V -> 0.1161 V`
- Decision:
  - promoted

6. Adding longer PMOS input pair on top of lighter bias is the best balanced next step
- Hypothesis:
  - slightly longer PMOS input devices will improve gain-per-current without reopening shutdown
- Change:
  - promoted combo:
    - `w_tail = 4.0 um`
    - `r_stage1_bias = 2.5e6 ohm`
    - `l_in = 3.0 um`
- Result:
  - versus lighter-bias baseline:
    - direct gain `≈ 62.04 dB -> 62.68 dB`
    - `IQ ≈ 28.23 uA -> 27.79 uA`
    - `VOUT_low ≈ 0.1161 V -> 0.1146 V`
    - shutdown still `≈ 0.54 ... 0.97 nA`
- Decision:
  - promoted to current default baseline

### Rejected Or Not Promoted

1. Weaker or longer tail switch alone
- Hypothesis:
  - weaker tail switch may reduce shutdown current
- Result:
  - solver-hostile
- Decision:
  - do not repeat

2. Stacked tail switch
- Hypothesis:
  - stacked PMOS tail switch may reduce residual off-state conduction
- Result:
  - `tail1_dc` moved
  - disabled leakage stayed `≈ 16037.8 nA`
- Decision:
  - dead branch

3. Lower `r_stage2_bias`
- Hypothesis:
  - more stage-2 PMOS bias current may help
- Result:
  - entered slow/ solver-hostile regime
  - no clean improvement
- Decision:
  - do not repeat as a primary lever

4. `r_gp` as a tuning lever
- Hypothesis:
  - helper-gate coupling may be a lightweight knob
- Result:
  - too sensitive and slow
- Decision:
  - not a productive primary axis

5. Longer first-stage NMOS mirror load on the current `v3` baseline
- Result:
  - direct gain `≈ 58.58 dB -> 58.38 dB`
  - `IQ ≈ 40.60 uA -> 47.10 uA`
- Decision:
  - reject

6. Smaller stage-2 NMOS as a standalone step
- Result:
  - direct gain `≈ 58.58 dB -> 58.72 dB`
  - `IQ ≈ 40.60 uA -> 36.06 uA`
  - `VOUT_low ≈ 0.1149 V -> 0.1293 V`
- Decision:
  - reject as a balanced baseline

7. Lighter bias + longer input + longer load
- Result:
  - weaker than the simpler `B5` point
- Decision:
  - reject

### Side Branch Worth Keeping In Mind

1. Lighter bias + longer input + smaller stage-2 NMOS
- Result:
  - direct gain `≈ 68.14 dB`
  - `IQ ≈ 25.05 uA`
  - `VOUT_low ≈ 0.1291 V`
- Decision:
  - do not promote now
  - keep only as an aggressive high-gain side branch if low-side swing can later be recovered

## Summary Of What Not To Repeat

Do not repeat on the `v3` core:
- stronger local shutdown clamps
- first-stage output-node shutdown clamps
- direct PMOS input-gate forcing without isolation
- tail-switch stacking as a shutdown fix
- lower `r_stage2_bias` as the main lever
- `r_gp` scalar tuning as the main lever
- pure helper-strength sweeps as a substitute for output-path redesign

Do not repeat on the baseline `AZ` track:
- mirrored `VXN` correction
- floating `PHI3` signal path
- simple `hold -> apply` split without live `PHI3` input
- small `R/C` retuning without a topology change

## Next Step

Keep the current `v3` default baseline and focus on:
- worst-corner stability first
- then remaining `AOL / IQ / VOUT_low` closure

Most likely next branch:
- preserve the current default
- improve low-side swing and bad-corner `GM`
- do not reopen the shutdown path
