## core_h10_analog_class_ab

First direct attempt at a true analog class-AB output stage.

Topology:
- keep the original first stage and second-stage `vdrv` node
- keep `vdrv -> vbuf` only as a sign-probe node
- remove the previous asymmetric quasi-digital gate-law stage
- drive the output NMOS gate from `vgn`
- drive the output PMOS gate from `vgp`
- generate the gates with complementary analog biases:
  - `vgn` from a PMOS branch plus weak pull-down
  - `vgp` from an NMOS branch plus weak pull-up

Goal:
- create non-zero quiescent overlap current
- avoid `both_off` floating behavior around nominal
- make the output pair operate as an analog class-AB block instead of rail-switching

Diagnostics:
- `driver_metrics.json`
  - `vbuf`, `vgn`, `vgp`
  - `ab_spread_V = vgn - vgp`
  - `gate_cm_V`
  - driver currents
- `output_subckt_metrics.json`
  - same gate metrics plus `i_out_p`, `i_out_n`, `quiescent_overlap_A`
- `forced_output_pair_metrics.json`
  - direct gate-force map of the unchanged output pair
- `metrics.json`
  - full-core follower, swing, load and AC probes

Current result:
- this first `h10` cut is not promotable
- the probes show the driver law is still wrong:
  - `vgn` stays near `0 V`
  - `vgp` stays near `VDD`
  - the output block falls back to the same low-side state across most of the `vdrv` sweep
- the probe suite is kept because it cleanly separates:
  - driver failure
  - output-pair behavior
  - full-core integration behavior
