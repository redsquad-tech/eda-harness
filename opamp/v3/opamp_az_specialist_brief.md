## Context

This is a SKY130 prototype of a foreground auto-zero op-amp wrapper around a working continuous-time core.

Relevant netlist:
- [opamp_az_top.spice](/home/vadim/work/eda-harness/opamp/v3/opamp_az_top.spice)

Main implementation file:
- [opamp_az_top.py](/home/vadim/work/eda-harness/opamp/v3/opamp_az_top.py)

Target behavior is closer to the separate product spec (`opamp_az_spec.md`) than to the exact prototype process/ supply. This prototype runs on SKY130 and ~1.8 V style devices.

## What Already Works

The underlying core is not the main problem anymore.

Nominal core operating point without relying on AZ is healthy:
- `VIN = 0.9 V`
- `VOUT ≈ 0.8996 V`
- `VX ≈ 0.5542 V`
- `VDRV ≈ 0.5331 V`
- `I_stage2_n / I_stage2_p ≈ 1.02`

`VDRV_QREF` has been checked against the measured core quiescent point:
- divider target in AZ top: `VDRV_QREF ≈ 0.5294 V`
- measured core nominal: `VDRV ≈ 0.5331 V`
- mismatch: about `3.7 mV`

So the current evidence says:
- the core is usable
- the selected `VDRV_QREF` is reasonable
- the remaining problem is in the AZ calibration law, not basic core bias

## Current AZ Architecture

The AZ wrapper currently has:
- input mux:
  - `AZ`: both internal core inputs tied to `VCM_AZ`
  - `INF`: external inputs drive core
- weak PMOS auxiliary trim pair injected into stage1 drains (`VX / VREF`)
- differential storage nodes:
  - `VTRP`
  - `VTRN`
- `CazP/CazN` referenced to fixed `VTR_CM = VCM_AZ`
- explicit internal `AZ_RESET` pulse:
  - `VTRP <- VCM_AZ`
  - `VTRN <- VCM_AZ`
- then `AZ_NULL`
- analog servo during `AZ_NULL`:
  - `Vsense = VDRV`
  - `Vtarget = VDRV_QREF`
  - opposite current injection into `VTRP / VTRN` through `VCCS`
- output isolated from external `VOUT` pin outside inference

This means the old direct-track storage has already been removed. The current loop is no longer storing raw `VDRV` or `QREF` on the trim nodes.

## What Does Not Work

The AZ wrapper modes run, but the calibration does not produce a useful offset correction.

Residual after calibration is still huge:
- [rc_probe_az_residual_offset_metrics.json](/home/vadim/work/eda-harness/opamp/v3/tests/rc_probe_az_residual_offset_metrics.json)
- `VIN_CM = 0.9 V`
- `inference_vout ≈ 1.238 V`
- `residual_offset ≈ +0.338 V`

That is many orders of magnitude away from any serious auto-zero target.

## Diagnostic Evidence

### 1. Sign / trim sensitivity

From:
- [rc_probe_az_trim_sign_metrics.json](/home/vadim/work/eda-harness/opamp/v3/tests/rc_probe_az_trim_sign_metrics.json)

Two calibration targets were compared:
- low target:
  - `VDRV_QREF ≈ 0.4521 V`
  - settled `VDRV ≈ 0.4521 V`
  - `u = VTRN - VTRP ≈ 4.100 mV`
  - `VX ≈ 0.5552 V`
- high target:
  - `VDRV_QREF ≈ 0.6444 V`
  - settled `VDRV ≈ 0.6444 V`
  - `u ≈ 3.977 mV`
  - `VX ≈ 0.5531 V`

Observed deltas:
- `ΔQREF ≈ +192.3 mV`
- `ΔVDRV ≈ +192.3 mV`
- `Δu ≈ -122.6 uV`
- `ΔVX ≈ -2.12 mV`

Interpretation:
- the servo strongly forces `VDRV` to the chosen target
- but the stored trim `u = VTRN - VTRP` hardly moves
- and `VX` hardly moves
- so the trim actuator appears too weak or poorly coupled to generate meaningful correction at the signal path level

### 2. Convergence during calibration

From:
- [rc_probe_az_convergence_metrics.json](/home/vadim/work/eda-harness/opamp/v3/tests/rc_probe_az_convergence_metrics.json)

At the end of calibration:
- `|Vsense - Vtarget| ≈ 0.81 uV`
- initial measured error in the sampled window: `≈ 5.66 uV`
- `VDRV_end ≈ 0.53135 V`
- `u_trim_end ≈ 4.06 mV`

Interpretation:
- the `AZ_NULL` loop as currently built converges extremely well in terms of forcing `VDRV -> VDRV_QREF`
- so the failure is not "servo does not converge"
- the failure is "convergence of `VDRV` does not translate into useful offset correction at output"

### 3. Hold behavior over ~200 us

From:
- [rc_probe_az_hold_200us_metrics.json](/home/vadim/work/eda-harness/opamp/v3/tests/rc_probe_az_hold_200us_metrics.json)

In the measured inference window:
- `u_trim_start ≈ 4.053 mV`
- `u_trim_end ≈ 4.105 mV`
- `u_trim_drift ≈ 52 uV`
- `VOUT_start ≈ 0.865 V`
- `VOUT_end ≈ 1.212 V`
- `VOUT_drift ≈ 346 mV`

Interpretation:
- the stored trim itself holds reasonably well
- but output drifts a lot anyway
- so the dominant problem is not capacitor leakage on the trim nodes

## Short Diagnosis

The current AZ loop is good at making `VDRV` equal `VDRV_QREF`.

It is bad at producing a correction that actually nulls residual output offset.

At this point the most likely remaining issue is one of these:
- `Vsense = VDRV` is the wrong calibration observable for this architecture
- the weak trim pair is too weak, or badly scaled, to move the first-stage operating point enough
- the calibration loop is solving the wrong internal condition, even though `VDRV_QREF` itself is reasonable

## Specific Question For Review

Given this topology:
- working continuous-time core
- weak auxiliary PMOS trim pair in stage1
- differential stored trim on `VTRP / VTRN`
- explicit `AZ_RESET`
- `AZ_NULL` loop currently sensing `VDRV` and targeting `VDRV_QREF`

what is the most defensible next architecture step?

Please focus on these choices:

1. Should calibration continue to use:
- `Vsense = VDRV`
- `Vtarget = VDRV_QREF`

or should it switch to:
- `Vsense = vout_core`
- `Vtarget = VCM_AZ`

2. Is the weak auxiliary trim pair the right actuator, but simply too weak?
- If yes, what scaling or `gm_trim / gm_main` range would be reasonable?

3. Is the current analog servo fundamentally the wrong kind of calibration engine for this topology?
- Would you replace it with:
  - a small OTA/integrator,
  - a comparator + charge pump,
  - or a latched trim DAC driving trim slices / current injection?

4. Does the evidence above indicate that the loop is minimizing the wrong internal variable, even though `VDRV_QREF` is numerically close to core nominal?

## Files To Look At

- [opamp_az_top.spice](/home/vadim/work/eda-harness/opamp/v3/opamp_az_top.spice)
- [opamp_az_top.py](/home/vadim/work/eda-harness/opamp/v3/opamp_az_top.py)
- [rc_probe_az_trim_sign_metrics.json](/home/vadim/work/eda-harness/opamp/v3/tests/rc_probe_az_trim_sign_metrics.json)
- [rc_probe_az_convergence_metrics.json](/home/vadim/work/eda-harness/opamp/v3/tests/rc_probe_az_convergence_metrics.json)
- [rc_probe_az_hold_200us_metrics.json](/home/vadim/work/eda-harness/opamp/v3/tests/rc_probe_az_hold_200us_metrics.json)
- [rc_probe_az_residual_offset_metrics.json](/home/vadim/work/eda-harness/opamp/v3/tests/rc_probe_az_residual_offset_metrics.json)
