# Output Stage Spec

## Artifacts

- Current standalone output-path source: [output_path_reference.py](/home/vadim/work/eda-harness/opamp/v3/output_path_reference.py)
- Current generated SPICE netlist: [output_path_reference.spice](/home/vadim/work/eda-harness/opamp/v3/output_path_reference.spice)

## What This Block Is

Current standalone block `reference_output_path_method2` is a single-ended output path after the second stage.

External interface:

- input: `VDRV`
- output: `VOUT`
- supplies: `VDD`, `VSS`

Internal structure:

1. Helper inverter:
- `m_inv_p`, `m_inv_n`
- creates `vdrvb` from `VDRV`

2. Linked bias chain:
- `m_bias_p` diode-connected PMOS
- `r_bias`
- `m_bias_n` diode-connected NMOS
- produces two internal bias nodes:
  - `vgp_q`
  - `vgn_q`

3. Gate-forming network:
- `r_keep_n`: `vgn_q -> VGN`
- `r_keep_p`: `vgp_q -> VGP`
- `r_sig_n`: `VDRV -> VGN`
- `r_sig_p`: `vdrvb -> VGP`

4. Push-pull output pair:
- `m_out_n`: common-source NMOS pull-down
- `m_out_p`: common-source PMOS pull-up

So the block is not just the output pair. It is:

- bias generator
- weak signal injector
- common-source push-pull output stage

## Intended Topology

By intent this should behave as a biased class-AB common-source push-pull output path:

1. `keep` path sets quiescent gate window:
- `VGN_Q`
- `VGP_Q`

2. `sig` path perturbs that window with input signal:
- `VGN = VGN_Q + small_n(VDRV)`
- `VGP = VGP_Q + small_p(VDRV)`

3. Output pair converts gate modulation into output current:
- NMOS branch pulls `VOUT` down
- PMOS branch pulls `VOUT` up

## Local Branch Semantics

These statements are physically correct for the output pair itself:

- `VGN ↑ -> I_N ↑ -> VOUT ↓`
- `VGP ↓ -> I_P ↑ -> VOUT ↑`

Therefore:

- the `keep` network must place the pair in a usable quiescent operating region
- the `sig` network must change the dominance of `I_P` vs `I_N` smoothly

The right criterion is not a hardcoded sign for `VDRV -> VOUT`.
The right criterion is:

- quiescent point not rail-parked
- `I_P` and `I_N` comparable around nominal
- signal changes branch dominance without hard switching

## Expected Characteristics

The standalone output path is expected to satisfy all of the following.

### DC Quiescent Point

With only the `keep` path active:

- `VOUT_Q` should stay away from both rails
- output pair should already conduct lightly
- neither branch should dominate so strongly that `VOUT` parks high or low

In practical terms:

- `I_out_p` and `I_out_n` should both be non-negligible
- `VOUT_Q` should be in a usable middle region, not near `0 V` or `1.8 V`

### Signal Perturbation

With `keep + sig` active:

- `sig` should move `VGN/VGP` around the quiescent point
- it should not completely overwrite the quiescent bias
- it should not produce instant rail-to-rail gate split

### Transfer

For a sweep of `VDRV`:

- `VOUT(VDRV)` should have a usable analog region
- branch-current handoff should be smooth
- the block should not behave like a two-state switch over almost the whole sweep

### Load Handling

At a fixed mid-ish drive point:

- sourcing current into `VOUT` should move output in one physically sensible direction
- sinking current from `VOUT` should move output in the opposite direction
- output pair should remain the dominant current path, not the internal bias chain

## Current Implemented Parameters

Current defaults in [output_path_reference.py](/home/vadim/work/eda-harness/opamp/v3/output_path_reference.py):

- output NMOS: `w=1.2`, `l=0.5`
- output PMOS: `w=2.4`, `l=0.5`
- bias NMOS: `w=0.6`, `l=1.0`
- bias PMOS: `w=1.2`, `l=1.0`
- `r_bias = 120k`
- inverter NMOS: `w=0.5`, `l=2.0`
- inverter PMOS: `w=1.0`, `l=2.0`
- `r_keep_n = r_keep_p = 60k`
- `r_sig_n = r_sig_p = 1.2M`

## Current Measured Behavior

From [rc_probe_reference_output_path_metrics.json](/home/vadim/work/eda-harness/opamp/v3/tests/rc_probe_reference_output_path_metrics.json):

- `VDRV=0.0 -> VOUT≈0.164 V`
- `VDRV=0.8 -> VOUT≈1.749 V`
- `VDRV=1.0 -> VOUT≈1.756 V`
- `VDRV=1.2 -> VOUT≈1.696 V`
- `VDRV=1.6 -> VOUT≈0.068 V`
- `VDRV=1.8 -> VOUT≈0.040 V`

Branch currents are already in the microamp range, so the output pair is no longer off.
But transfer is still wrong:

- quiescent center is wrong
- output path is mostly rail-hopping
- usable analog mid-region is missing or too narrow

From [rc_probe_reference_output_signal_isolation_metrics.json](/home/vadim/work/eda-harness/opamp/v3/tests/rc_probe_reference_output_signal_isolation_metrics.json):

- `keep_only -> VOUT≈1.72 V`
- `sig_only -> VOUT≈1.63 V`
- `combined -> VOUT≈1.76 V` at `VDRV=1.0`

This means:

- `keep` alone already parks the output too high
- `sig` alone is too strong and not a small perturbation
- current failure is dominated by wrong gate-law, especially wrong quiescent center

From [rc_probe_reference_output_connectivity_cuts_metrics.json](/home/vadim/work/eda-harness/opamp/v3/tests/rc_probe_reference_output_connectivity_cuts_metrics.json):

- branch ownership looks physically consistent
- gross hidden short or completely wrong node hookup is unlikely

From [rc_probe_reference_output_branch_semantics_metrics.json](/home/vadim/work/eda-harness/opamp/v3/tests/rc_probe_reference_output_branch_semantics_metrics.json):

- isolated branch action is strongly cross-coupled through the shared bias network
- branches do not behave like independent local `keep_n/keep_p/sig_n/sig_p` controls

## What Must Be True Before Integration Into Core

The block should not be integrated into the full op-amp until all of the following are true:

1. `keep_only` produces a non-rail quiescent `VOUT`
2. `combined` produces a smooth analog region over a meaningful `VDRV` interval
3. `I_out_p` and `I_out_n` hand off smoothly, not by abrupt rail hopping
4. bias chain no longer dominates the interpretation of output behavior
5. branch semantics are understandable and match intended class-AB behavior

## Immediate Design Conclusion

At the moment the dominant defect is not gross wiring. The dominant defect is:

- wrong quiescent center of the gate window
- plus a signal law that is still too aggressive and too cross-coupled

So the next design work should focus on:

1. fixing quiescent gate-window center
2. then reducing and reshaping signal perturbation
3. only then reconsidering sizing or core integration
