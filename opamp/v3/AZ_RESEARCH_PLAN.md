# AZ Research Plan

This file captures the current AZ improvement plan as explicit hypotheses, device variants, and validation tests.

## Hypotheses

### az_h1: Fast timing plus positive shunt plus larger cap is the main reduced-PVT closure axis

- Problem: Current AZ top passes nominal but still fails reduced-PVT by a large margin.
- Hypothesis: The dominant remaining AZ error is dynamic and edge-related; positive-side shunt filtering with larger sampling capacitance and faster timing should cut worst hot/fast pedestal and settling without breaking nominal precision.
- Success metrics:
  - TT residual <= 100 uV
  - TT pedestal_mid50 <= 25 uV
  - TT settling_mid50 <= 10 uV
  - RPVT worst pedestal_mid50 < 350 uV
  - RPVT worst settling_mid50 < 100 uV
- Variants:
  - `az_h1_v1_cap200_shuntp10_freq200k`
    - frontend: c_az = 200 fF, c_out_p = 10 fF
    - timing: period = 5 us, dead_time = 0.5 us, phi1/phi2/phi3 = 0.4/0.2/0.4
    - rationale: Current best balanced corner-reduction branch from the autonomous batches.
    - expect: reduce worst reduced-PVT residual toward < 1000 uV, reduce worst reduced-PVT pedestal_mid50 toward < 150 uV, reduce worst reduced-PVT settling_mid50 toward <= 50 uV
    - kill if: TT residual > 150 uV, TT pedestal_mid50 > 50 uV, TT settling_mid50 > 30 uV
  - `az_h1_v2_cap150_shuntp10_freq200k`
    - frontend: c_az = 150 fF, c_out_p = 10 fF
    - timing: period = 5 us, dead_time = 0.5 us, phi1/phi2/phi3 = 0.4/0.2/0.4
    - rationale: Lower-cap version to test whether 200 fF is over-driving hot/fast residual.
    - expect: same nominal class as v1, slightly better hot/fast residual or pedestal tradeoff
    - kill if: corners worse than v1 in all three reduced-PVT metrics
  - `az_h1_v3_shunt_both10_freq200k`
    - frontend: c_az = 70 fF, c_out_p = 10 fF, c_out_n = 10 fF
    - timing: period = 5 us, dead_time = 0.5 us
    - rationale: Tests whether symmetric edge filtering helps reduced-PVT more than cap increase.
    - expect: rule out or confirm symmetric shunt as a real topology direction
    - kill if: TT settling_mid50 > 10 uV with no corner benefit over v1
- Tests: az_tt_precision, az_reduced_pvt, az_timing_sanity

### az_h2: RC finish can make a safe baseline patch if aggressive timing is too risky

- Problem: The aggressive timing branch improves corners strongly, but may be harder to productize.
- Hypothesis: A weaker but more nominal-safe branch may exist by combining the best cap/shunt topology with modest attenuation-path retuning.
- Success metrics:
  - TT residual <= 25 uV
  - TT pedestal_mid50 <= 20 uV
  - RPVT worst pedestal_mid50 < 1000 uV
  - RPVT worst settling_mid50 < 250 uV
- Variants:
  - `az_h2_v1_cap200_shuntp10_rtop600`
    - frontend: c_az = 200 fF, c_out_p = 10 fF, r_vcm_top = 600 ohm
    - timing: legacy timing
    - rationale: Current best conservative baseline patch that preserves nominal behavior strongly.
    - expect: keep nominal almost baseline-clean, improve reduced-PVT without aggressive timing
    - kill if: TT residual > 20 uV, TT pedestal_mid50 > 25 uV
  - `az_h2_v2_cap200_shuntp10_rtop600_freq200k`
    - frontend: c_az = 200 fF, c_out_p = 10 fF, r_vcm_top = 600 ohm
    - timing: period = 5 us, dead_time = 0.5 us
    - rationale: Combines the best nominal-safe RC trim with the strongest timing lever.
    - expect: bridge the gap between conservative and aggressive branches, target reduced-PVT pedestal_mid50 < 250 uV while keeping TT residual < 75 uV
    - kill if: TT residual > 100 uV, TT pedestal_mid50 > 25 uV
  - `az_h2_v3_cap150_shuntp10_rtop600_freq200k`
    - frontend: c_az = 150 fF, c_out_p = 10 fF, r_vcm_top = 600 ohm
    - timing: period = 5 us, dead_time = 0.5 us
    - rationale: Intermediate-cap fallback if 200 fF is too aggressive in nominal or MC.
    - expect: same corner direction with potentially lower residual sigma
    - kill if: worse than h2_v2 on both nominal and corners
- Tests: az_tt_precision, az_reduced_pvt, az_nominal_frontend

### az_h3: A narrower dead-time window may outperform both legacy and freq200k branches

- Problem: `dead10ns` improved corners strongly but damaged nominal residual too much.
- Hypothesis: There may be an intermediate dead-time region that keeps most corner benefit while recovering nominal residual and pedestal.
- Success metrics:
  - TT residual <= 150 uV
  - TT pedestal_mid50 <= 50 uV
  - RPVT worst residual < 1800 uV
  - RPVT worst pedestal_mid50 < 1200 uV
- Variants:
  - `az_h3_v1_cap200_shuntp10_dead50ns`
    - frontend: c_az = 200 fF, c_out_p = 10 fF
    - timing: dead_time = 50 ns, period = 20 us
    - rationale: Current strongest corner winner, but nominal residual regressed too much.
    - expect: establish upper bound of dead-time leverage
    - kill if: TT residual > 250 uV
  - `az_h3_v2_cap200_shuntp10_dead100ns`
    - frontend: c_az = 200 fF, c_out_p = 10 fF
    - timing: dead_time = 100 ns, period = 20 us
    - rationale: Test whether a slightly less aggressive dead-time cut keeps corner benefit but repairs nominal residual.
    - expect: TT residual < 150 uV with corner metrics still better than freq200k baseline
    - kill if: corners degrade back toward baseline while TT residual remains > 150 uV
  - `az_h3_v3_cap200_shuntp10_dead200ns`
    - frontend: c_az = 200 fF, c_out_p = 10 fF
    - timing: dead_time = 200 ns, period = 20 us
    - rationale: Bridges between the safe legacy timing and aggressive short-dead-time branch.
    - expect: recover a balanced dead-time operating point if it exists
    - kill if: TT pedestal_mid50 > 50 uV and corners not better than freq200k branch
- Tests: az_tt_precision, az_reduced_pvt, az_deadtime_sweep

### az_h4: Only finalists should enter mismatch screening

- Problem: Nominal and reduced-PVT do not tell whether a branch is manufacturable.
- Hypothesis: Mismatch-only Monte Carlo is the gate between a promising AZ branch and a real baseline candidate.
- Success metrics:
  - MC residual mean near nominal expectation
  - MC residual sigma small enough that 3-sigma is near or below minimum spec
  - MC pedestal and settling spread do not reopen spec catastrophically
- Variants:
  - `az_h4_v1_mc_cap200_shuntp10_freq200k`
    - frontend: same as aggressive patch candidate
    - timing: same as aggressive patch candidate
    - rationale: Mismatch-only gate for the strongest current candidate.
    - expect: quantify mean/sigma on residual/pedestal/settling, decide if this branch is viable for tapeout-facing closure
    - kill if: MC sigma makes 3-sigma exceed minimum spec limits badly
  - `az_h4_v2_mc_cap200_shuntp10_rtop600`
    - frontend: same as conservative fallback
    - timing: legacy timing
    - rationale: Mismatch-only gate for the safer nominal fallback.
    - expect: check whether conservative branch has materially better mismatch robustness
    - kill if: MC result is not better than aggressive branch while corners remain much worse
- Tests: az_mc_offset, az_mc_pedestal_settling

## Test Matrix

### az_tt_precision

- Purpose: Nominal top-level AZ precision check
- Fixture: noise_and_offset
- Corners: TT / 1.8 V / 27 C
- Metrics: residual_offset_uV, pedestal_mid50_uV, settling_mid50_uV
- Rule: Use as nominal gate before spending reduced-PVT time.
- Applies to: combo_corner_balance, nominal_safe_finish, deadtime_window

### az_reduced_pvt

- Purpose: Reduced-PVT corner closure check
- Fixture: noise_and_offset
- Corners: TT/SS/FF reduced decision corners
- Metrics: worst_residual_offset_uV, worst_pedestal_mid50_uV, worst_settling_mid50_uV
- Rule: Primary ranking test for all pre-MC AZ branches.
- Applies to: combo_corner_balance, nominal_safe_finish, deadtime_window

### az_timing_sanity

- Purpose: Confirm timing-dependent winner is not a single-point accident
- Fixture: noise_and_offset
- Corners: TT nominal, FF / 1.98 V / 125 C
- Metrics: residual_offset_uV, pedestal_mid50_uV, settling_mid50_uV
- Rule: Small timing perturbation should not cause catastrophic metric jumps.
- Applies to: combo_corner_balance

### az_nominal_frontend

- Purpose: Frontend-only nominal pedestal/settling sanity
- Fixture: frontend_az transient
- Corners: TT nominal
- Metrics: pedestal_uV, settling_mid50_uV
- Rule: Use to catch pathological frontend changes before top-level ranking.
- Applies to: nominal_safe_finish

### az_deadtime_sweep

- Purpose: Short dead-time exploration around promising branches
- Fixture: noise_and_offset
- Corners: TT nominal, FF / 1.98 V / 125 C
- Metrics: residual_offset_uV, pedestal_mid50_uV, settling_mid50_uV
- Rule: Identify the narrowest viable dead-time band before MC.
- Applies to: deadtime_window

### az_mc_offset

- Purpose: Mismatch-only residual-offset MC gate
- Fixture: mismatch-only Monte Carlo
- Corners: TT mismatch-only
- Metrics: mean_uV, sigma_uV, p99_uV
- Rule: Finalists only. Use to decide baseline promotion order.
- Applies to: mc_gate

### az_mc_pedestal_settling

- Purpose: Mismatch-only pedestal and settling MC gate
- Fixture: mismatch-only Monte Carlo
- Corners: TT mismatch-only
- Metrics: pedestal_mean_uV, pedestal_sigma_uV, settling_mean_uV, settling_sigma_uV
- Rule: Finalists only. Reject branches with excessive dynamic spread.
- Applies to: mc_gate

