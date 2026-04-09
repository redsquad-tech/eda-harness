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

Three concrete layers exist:

1. `v3` research core
- source: `opamp/v3/opamp_core.py`
- this is the static-core experiment track

2. `v3/prod` RC integration layer
- source: `opamp/v3/prod`
- this is the current release-candidate source of truth for:
  - integrated DUT
  - acceptance tests
  - customer bundle

3. `v1` legacy product path
- kept only as the source of the proven AZ frontend while `v3` frontend is still not implemented
- not the RC source of truth anymore

## Active RC Baseline

### Core

Current promoted default in [`opamp/v3/opamp_core.py`](/home/vadim/work/eda-harness/opamp/v3/opamp_core.py):
- helper-link isolation in shutdown enabled
- `w_tail = 4.0 um`
- `r_stage1_bias = 2.5e6 ohm`
- `l_in = 3.0 um`
- `w_stage2_n = 20.0 um`
- `l_stage2_n = 6.0 um`
- `l_stage2_p = 10.0 um`
- `c_comp = 220 fF`
- `w_out_n = 1.2 um`

### Integrated DUT

Current RC DUT in [`opamp/v3/prod/opamp_az_top.py`](/home/vadim/work/eda-harness/opamp/v3/prod/opamp_az_top.py):
- real AZ frontend from `components/frontend_az.py`
- `v3` core from `opamp/v3/opamp_core.py`
- default promoted frontend params:
  - `c_az = 200 fF`
  - `r_vcm_top = 700 ohm`
  - `r_vcm_bot = 5 ohm`
  - `c_out_p = 10 fF`
  - `w_sw_n = 1.1`
  - `w_sw_p = 1.6`
  - `nf_sw = 2`
  - `period = 5 us`
  - `dead_time = 0.5 us`

Current measured metrics:

Nominal `TT / 1.8 V / 27 C`
- direct gain `≈ 64.31 dB`
- `IQ ≈ 21.17 uA`
- `VOUT_low ≈ 0.1063 V`
- disabled leakage `≈ 0.54 nA`
- raw offset `≈ 1303 uV`

Hard corner `SS / 1.6 V / 125 C`
- `AOL ≈ 65.90 dB`
- `GBW ≈ 217.7 kHz`
- `PM ≈ 38.12 deg`
- `GM ≈ 23.19 dB`
- `IQ ≈ 15.91 uA`

Interpretation:
- shutdown: closed
- worst-corner stability: closed
- nominal gain/current: materially improved
- low-side swing: still misses by about `1 to 2 mV`
- raw offset: still requires `AZ`
- current blockers for maximum-spec closure:
  - gain still too low
  - current still too high
  - slow-corner GBW still too low
  - low-side swing still slightly high

### Current Patch Candidates

1. Core promoted RC patch
- `K1_stage2p10`
- change:
  - `l_stage2_p = 10 um`
- decision:
  - promoted into `opamp/v3/opamp_core.py`

2. AZ mismatch-hardening frontier
- current best deep-valid leads:
  - `m3r1_cap200_wswn1p1_wswp1p6_rtop600`
  - `m3r2_cap200_wswn1p1_wswp1p6_rtop700`
- decision:
  - not yet promoted into RC defaults
  - still under experiment because reduced-PVT residual and MC residual remain far from spec

## Current Priorities

1. Keep `opamp/v3/prod` as the only RC promotion target.
2. Close AZ reduced-PVT residual offset and mismatch MC on top of the current RC DUT.
3. Keep the customer bundle aligned with the same bench families as `prod_release`.
4. Avoid adding new promoted defaults unless they are reflected in:
   - `opamp/v3/prod`
   - `track.md`
   - bundle contents
   - acceptance targets

## Autonomous Batch Findings In Progress

### Core `gain_ro` batch

1. `J2_load10` is a strong nominal-gain branch, but not promotable as-is
- Hypothesis:
  - longer first-stage load may raise first-stage `ro` without weakening the current backbone
- Change:
  - `l_load = 10 um`
- Result:
  - `TT`: `AOL ≈ 81.11 dB`, `IQ ≈ 23.36 uA`, `VOUT_low ≈ 0.1063 V`
  - `FF`: `AOL ≈ 65.99 dB`, `GBW ≈ 1.253 MHz`
  - `SS`: `AOL ≈ 71.77 dB`, `GBW ≈ 200.0 kHz`, `GM ≈ -12.02 dB`
- Decision:
  - do not promote directly
  - keep as evidence that first-stage load length is a real gain lever
  - any follow-up must repair `SS` loop robustness

2. `J3_lin4p0_load10` is also not promotable
- Change:
  - `l_in = 4 um`, `l_load = 10 um`
- Result:
  - `TT`: `AOL ≈ 75.33 dB`, `IQ ≈ 23.03 uA`
  - `FF`: `GBW ≈ 945.2 kHz`
  - `SS`: `GBW ≈ 151.6 kHz`, `GM ≈ -12.79 dB`
- Decision:
  - dead as a direct max-spec branch
  - confirms that longer `l_in` can tame `FF` GBW, but at too much `SS` cost

### AZ `path_topology` batch

1. `path_p_soft_2` is effectively identical to baseline
- Hypothesis:
  - slightly weaker non-inverting live-path coupling may reduce corner pedestal kick
- Change:
  - `r_out_p = 2`
- Result:
  - `TT` stayed the same within noise: residual `≈ 7.91 uV`, pedestal `mid50 ≈ 23.56 uV`, settling `mid50 ≈ 7.70 uV`
  - reduced-PVT worst metrics also stayed the same:
    - worst residual `≈ 2674.81 uV`
    - worst pedestal `mid50 ≈ 8399.73 uV`
    - worst settling `mid50 ≈ 670.45 uV`
- Decision:
  - dead branch
  - small positive live-path weakening is not the `FF/hot` fix

## `v1` Legacy `AZ` Track

### Current Best Known `v1` Baseline `AZ` Point

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

### `v1` Baseline `AZ` Hypothesis Ledger

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

6. `cap200_shuntp10_freq200k` is the best balanced AZ patch candidate so far
- Change:
  - `c_az = 200 fF`
  - `c_out_p = 10 fF`
  - `period = 5 us`
  - `dead_time = 0.5 us`
- Result:
  - `TT`: residual `≈ 38.40 uV`, pedestal `mid50 ≈ 5.25 uV`, settling `mid50 ≈ 3.86 uV`
  - reduced-PVT worst:
    - residual `≈ 1977.66 uV`
    - pedestal `mid50 ≈ 316.32 uV`
    - settling `mid50 ≈ 78.13 uV`
- Decision:
  - superseded by `cap200_shuntp10_rtop600_freq200k`

7. `cap200_shuntp10_rtop600` is the conservative AZ fallback
- Change:
  - `c_az = 200 fF`
  - `c_out_p = 10 fF`
  - `r_vcm_top = 600 ohm`
- Result:
  - `TT`: residual `≈ 8.14 uV`, pedestal `mid50 ≈ 13.40 uV`, settling `mid50 ≈ 4.81 uV`
  - reduced-PVT worst:
    - residual `≈ 2372.18 uV`
    - pedestal `mid50 ≈ 5147.88 uV`
    - settling `mid50 ≈ 522.14 uV`
- Decision:
  - keep as fallback if fast timing is too aggressive for product use

8. `cap200_shuntp10_rtop600_freq200k` is now the best balanced AZ patch candidate
- Change:
  - `c_az = 200 fF`
  - `r_vcm_top = 600 ohm`
  - `c_out_p = 10 fF`
  - `period = 5 us`
  - `dead_time = 0.5 us`
- Result:
  - `TT`: residual `≈ 31.77 uV`, pedestal `mid50 ≈ 4.84 uV`, settling `mid50 ≈ 3.71 uV`
  - reduced-PVT worst:
    - residual `≈ 1799.66 uV`
    - pedestal `mid50 ≈ 251.93 uV`
    - settling `mid50 ≈ 63.71 uV`
- Decision:
  - promote as the current AZ default candidate

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

7. Smaller and longer stage-2 NMOS plus slightly higher compensation closes hard-corner stability
- Hypothesis:
  - the hard-corner problem is in stage-2 / output-path loop shape, not in shutdown or first-stage bias
- Change:
  - `w_stage2_n = 20.0 um`
  - `l_stage2_n = 6.0 um`
  - `c_comp = 220 fF`
- Result:
  - `SS GM ≈ -22.73 dB -> 23.19 dB`
  - `SS PM ≈ 36.71 deg -> 38.12 deg`
  - `TT gain ≈ 64.31 dB`
  - `TT IQ ≈ 21.17 uA`
- Decision:
  - promoted

8. PMOS helper width reduction is the only scalar low-swing lever that materially works
- Hypothesis:
  - the always-available PMOS helper is setting most of the residual low-side floor
- Change:
  - reduced `w_out_n` from the old larger helper down to the current small-helper regime
- Result:
  - `VOUT_low` improved from `≈ 0.168 V` in the stability-closure branch to `≈ 0.106 V` at the promoted default
  - hard-corner stability remained healthy
- Decision:
  - promoted

9. Longer stage-2 PMOS load is the first real high-gain baseline patch
- Hypothesis:
  - stage-2 PMOS load length can raise gain strongly without the stability damage seen in the dead branches
- Change:
  - `l_stage2_p = 10 um`
- Result:
  - `TT`: `AOL ≈ 86.19 dB`, `IQ ≈ 21.10 uA`, `PM ≈ 40.87 deg`
  - `SS`: `GM ≈ 23.14 dB`, `GBW ≈ 215.8 kHz`
  - `FF`: `AOL ≈ 66.45 dB`, `GBW ≈ 1313.9 kHz`
  - `VOUT_low ≈ 0.1046 V`
- Decision:
  - promote as the current core patch candidate

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

8. `r_vdrv_out` sweep for low-side swing
- Result:
  - `1, 2, 5 ohm` produced no useful low-swing improvement
- Decision:
  - dead branch

9. `r_gp` scalar tuning for low-side swing
- Result:
  - essentially no movement in `VOUT_low`
- Decision:
  - dead branch

10. Shorter PMOS helper length for low-side swing
- Result:
  - made `VOUT_low` worse
- Decision:
  - dead branch

11. Follower common-mode sweep for low-side swing diagnosis
- Result:
  - `vout_mid_target = 0.8, 0.9, 1.0 V` gave identical `VOUT_low`
- Decision:
  - confirms residual floor is not common-mode dependent

12. Helper gate pull-up (`r_gp_pullup`) as structural quieting
- Result:
  - best tested point reached `VOUT_low ≈ 0.10066 V`
  - but cost too much gain to promote
- Decision:
  - useful diagnostic, not a promoted solution

13. Split-helper topology (`base + boost`) 
- Result:
  - no better Pareto point than the simple helper branch
- Decision:
  - dead branch

14. Inverter-driven NMOS pull-down assist
- Result:
  - clearly moves low-side floor
  - but either collapses output behavior or breaks gain/current / AC behavior
- Decision:
  - reject in current naive form

15. First-stage current reduction as a route to maximum-spec closure (`G1`)
- Hypothesis:
  - lighter first-stage bias plus modest geometry tweaks may raise `AOL / IQ` enough to move toward max spec
- Change:
  - `G1A/G1B/G1C/G1D`:
    - lighter `w_tail`
    - higher `r_stage1_bias`
    - optional longer `l_in`
- Result:
  - current improved:
    - `TT IQ ≈ 21.17 uA -> 17.15 ... 18.43 uA`
  - but gain fell badly:
    - `TT AOL ≈ 64.31 dB -> 58.38 ... 60.05 dB`
  - `SS` GBW also worsened:
    - `≈ 217.7 kHz -> 184.7 ... 215.8 kHz`
- Decision:
  - dead branch for max-spec closure

16. Smaller and longer stage-2 NMOS as a gain-building branch (`H2`)
- Hypothesis:
  - a smaller and longer stage-2 NMOS may increase useful gain while pulling `FF` excess back
- Change:
  - `w_stage2_n = 18.0 um`
  - `l_stage2_n = 8.0 um`
- Result:
  - `TT IQ` improved:
    - `≈ 21.17 uA -> 18.21 uA`
  - but gain collapsed:
    - `TT AOL ≈ 64.31 dB -> 57.06 dB`
    - `FF AOL ≈ 61.49 dB -> 56.00 dB`
  - low swing worsened badly:
    - `≈ 0.1063 V -> 0.1358 V`
- Decision:
  - dead branch

17. Longer input PMOS alone (`J1`)
- Hypothesis:
  - longer PMOS input devices alone may build gain without disrupting the current backbone
- Change:
  - `l_in = 4.0 um`
- Result:
  - `FF` GBW moved in the right direction:
    - `≈ 1345 kHz -> 1015 kHz`
  - but gain did not improve:
    - `TT AOL ≈ 64.31 dB -> 63.63 dB`
    - `FF AOL ≈ 61.49 dB -> 61.14 dB`
  - `SS` GBW got much worse:
    - `≈ 217.7 kHz -> 164.2 kHz`
- Decision:
  - not promotable as a primary gain branch
  - keep only as a possible later `FF`-GBW trim if a real gain branch is found elsewhere

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
- `r_vdrv_out` sweeps for low-side swing
- helper-length sweeps for low-side swing
- follower common-mode sweeps for low-side swing
- first-stage current reduction as the main route to max-spec closure
- smaller/ longer stage-2 NMOS as a max-spec gain branch

## Current Search Direction

The next credible gain branch is now narrower:
- keep the present current backbone close to baseline
- do not reduce first-stage current further
- do not weaken stage-2 NMOS further
- explore only higher-intrinsic-gain levers that keep the present drive strength:
  - longer first-stage load in a narrow region
  - longer stage-2 PMOS load
  - combinations that improve gain without reopening the `SS` GBW collapse
- split-helper variants in the current form
- naive inverter-driven NMOS pull-down assist

Do not repeat on the baseline `AZ` track:
- mirrored `VXN` correction
- floating `PHI3` signal path
- simple `hold -> apply` split without live `PHI3` input
- small `R/C` retuning without a topology change

## Next Step

Keep the current promoted `v3` baseline unless the `0.100 V` low-side limit is strictly hard.

If the limit is soft enough:
- stop here on static-core tuning
- move to real `v3` AZ integration
- then run offset and MC work

If the limit is absolutely hard:
- the only remaining worthwhile branch is a true structural direct-output-path redesign
- do not spend more time on scalar helper tuning
