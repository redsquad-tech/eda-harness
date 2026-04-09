# Auto-Zero Opamp Specification for SKY130

## 1. Scope

This document defines a specification-first implementation target for a low-offset auto-zero operational amplifier in `sky130`.

The target block is a reusable analog amplifier for low-bandwidth inference / sensor front-end use, where low residual DC offset is more important than high-speed settling.

This specification targets the `sky130` equivalent implementation, derived from the provided GF55 goal table and adjusted to realistic 1.8 V SKY130 operating limits.

## 2. Intended Use

- inference-mode analog front-end
- low-frequency sampled signal chain
- low-offset closed-loop amplification
- moderate capacitive loads
- low quiescent current operation

The amplifier is intended to operate with an auto-zero clocked front-end and two-phase non-overlap timing.

## 3. Top-Level Block Name

Recommended top-level reusable block name:

`opamp_az_top`

Recommended major sub-blocks:

- `frontend_az`
- `gain_stage`
- `second_stage`
- `output_stage`
- `bias_gen`
- `freq_comp`
- `cmfb_ct` or `cmfb_sc` if fully differential
- `nonoverlap_clk` if on-chip timing is required

## 4. Architectural Recommendation

Recommended starting architecture:

- PMOS-input first stage
- auto-zero switched-capacitor input front-end
- low-current second gain stage
- Miller compensation
- single-ended output for the first implementation pass
- external non-overlap clock for the first implementation pass

Rationale:

- PMOS input helps satisfy the required low-end input common-mode range
- single-ended implementation reduces risk and area for the first revision
- external AZ timing isolates analog validation from clock-generator issues

Second-step architecture option:

- fully differential two-stage amplifier
- common-mode feedback
- on-chip non-overlap clock generation

## 5. Operating Modes

The amplifier shall support the following modes:

1. `sample_zero`  
   The front-end samples its own offset and stores the error on AZ memory capacitors.
2. `amplify`  
   The stored offset is subtracted from the signal path while the amplifier drives the load.
3. `disabled`  
   Internal bias is off or strongly reduced and leakage is minimized.

## 6. Top-Level Interface

### 6.1 Required Pins for the First Implementation

- `VINP`: non-inverting analog input
- `VINN`: inverting analog input
- `VOUT`: analog output
- `VDD`: positive supply
- `VSS`: ground
- `EN`: enable
- `PHI1`: auto-zero phase 1 control
- `PHI2`: auto-zero phase 2 control

### 6.2 Optional Pins for the Differential Variant

- `VOUTP`
- `VOUTN`
- `VOCM`

### 6.3 Optional Pins for On-Chip Clocking

- `CLK_AZ`

## 7. Electrical Specification

Unless stated otherwise, the specification is now split into two levels:

- `Minimum requirement`: realistic first-closure requirement for the initial `sky130` implementation
- `Maximum requirement`: stricter target carried over as the upper product goal for the same architecture

The implementation goal is to close the minimum requirements first and then push toward the maximum requirements.

### 7.1 Supply and Environment

| Parameter | SKY130 Spec |
|---|---|
| Process | `sky130` 1.8 V core devices |
| Supply range | `1.6 V ... 1.98 V` |
| Nominal supply | `1.8 V` |
| Temperature range | `-40 C ... 125 C` |
| Nominal temperature | `27 C` |

### 7.2 Load and Output

| Parameter | Minimum SKY130 Requirement | Maximum SKY130 Requirement |
|---|---:|---:|
| Load range | `0 pF ... 2 pF` | `0 pF ... 2 pF` |
| Nominal load | `1 pF` | `1 pF` |
| Output compliant swing | `0.1 V ... VDD - 0.2 V` | `0.1 V ... VDD - 0.1 V` |
| Relaxed output swing | `0.02 V ... VDD - 0.02 V` | `0.02 V ... VDD - 0.02 V` |
| Output current | `+/-20 uA` | `+/-25 uA` |

### 7.3 Input Operating Range

| Parameter | SKY130 Spec |
|---|---|
| Input common-mode range | `0 ... 0.5 * VDD` |
| Nominal differential test amplitude | `20 mV` for linear characterization |

### 7.4 Gain, Bandwidth, and Stability

All nominal AC specs apply at:

- `TT`
- `VDD = 1.8 V`
- `T = 27 C`
- `CL = 1 pF`

| Parameter | Minimum SKY130 Requirement | Maximum SKY130 Requirement | Internal Design Target |
|---|---:|---:|---:|
| Open-loop gain | `>= 65 dB` | `>= 75 dB` | `80 ... 85 dB` |
| GBW | `0.3 ... 1 MHz` | `0.5 ... 1 MHz` | `0.8 ... 1.2 MHz` |
| Phase margin | `>= 30 deg` | `>= 30 deg` | `50 ... 60 deg` |
| Gain margin | `>= 5 dB` | `>= 5 dB` | `>= 8 dB` |

### 7.5 Offset and Error Budget

The guaranteed offset metric is the input-referred residual offset after auto-zero correction.

| Parameter | Minimum SKY130 Requirement | Maximum SKY130 Requirement |
|---|---:|---:|
| Residual input-referred offset after AZ | `<= 250 uV` | `<= 150 uV` |
| Stretch-goal residual offset | `<= 150 uV` | `<= 100 uV` |
| Pedestal-equivalent input error at nominal | `<= 100 uV` | `<= 50 uV` |
| Hold droop contribution per AZ cycle | `<= 50 uV` | `<= 30 uV` |

Raw pre-AZ offset is characterization only and is not a production pass/fail spec.

### 7.6 Power and Leakage

| Parameter | Minimum SKY130 Requirement | Maximum SKY130 Requirement |
|---|---:|---:|
| Quiescent current, enabled | `<= 20 uA` | `<= 15 uA` |
| Disabled leakage current | `<= 250 nA` | `<= 15 nA` |

If on-chip clock generation is added, the implementation shall clearly separate:

- analog core current
- timing generation current

### 7.7 Area

| Parameter | Minimum SKY130 Requirement | Maximum SKY130 Requirement |
|---|---:|---:|
| Active area | `3000 ... 7000 um^2` | `3000 ... 5000 um^2` |

This area budget includes:

- input pair
- active loads / mirrors
- second stage
- biasing
- compensation
- AZ switches
- AZ capacitors
- CMFB if present

## 8. Auto-Zero Timing Specification

The amplifier shall operate with a two-phase non-overlap clock.

### 8.1 Required Timing Rules

- `PHI1` and `PHI2` shall never overlap during normal operation
- break-before-make timing is required
- AZ memory nodes shall not be shorted simultaneously to both the sampling and amplification paths

### 8.2 Recommended Starting Timing

| Parameter | Initial Recommendation |
|---|---:|
| Auto-zero frequency | `50 kHz` |
| Allowed exploration range | `10 kHz ... 200 kHz` |
| Non-overlap dead time | `10 ns ... 50 ns` |
| Per-phase duty target | `~45%` |

### 8.3 AZ Capacitor Recommendation

| Parameter | Initial Recommendation |
|---|---:|
| Per-side AZ capacitor exploration range | `100 fF ... 500 fF` |
| Starting value | `200 fF` |

## 9. Functional Requirements

The block shall satisfy the following functional requirements:

1. The amplifier shall start reliably over the full supply and temperature range.
2. The auto-zero mechanism shall reduce the effective DC input offset to at least the minimum guaranteed residual-offset target, with the maximum target as the second-step closure goal.
3. The amplifier shall remain stable for `CL = 0 ... 2 pF`.
4. The output shall meet at least the minimum compliant swing target while sourcing or sinking the minimum guaranteed output current, with the maximum target as the second-step closure goal.
5. The disabled state shall meet at least the minimum leakage requirement, with the maximum leakage target as the second-step closure goal.
6. The AZ timing interface shall tolerate non-overlap control without destructive charge-sharing failures.

## 10. Design Constraints

1. Only SKY130-supported device types may be used.
2. The first implementation shall prefer 1.8 V core devices unless a specific reliability case requires otherwise.
3. The first implementation shall avoid unnecessary cascode depth that would reduce low-end ICMR margin.
4. All measurable performance claims shall map to tests.
5. If a claimed metric cannot be tested, it shall not be presented as a guaranteed spec.

## 11. Internal Performance Budgets

### 11.1 Offset Budget

Recommended top-down budget:

| Error Source | Budget |
|---|---:|
| Residual raw front-end mismatch after AZ | `<= 100 uV` |
| Pedestal contribution | `<= 50 uV` |
| Hold droop contribution | `<= 30 uV` |

The final guaranteed residual offset shall remain `<= 150 uV`.

### 11.2 Current Budget

Recommended current split:

| Subsystem | Budget |
|---|---:|
| Input stage + bias | `4 ... 6 uA` |
| Second stage | `4 ... 6 uA` |
| Output / auxiliary bias / CMFB | `3 ... 4 uA` |

### 11.3 Gain Budget

Recommended stage-level targets:

| Subsystem | Target |
|---|---:|
| First-stage intrinsic gain | `35 ... 45 dB` |
| Second-stage intrinsic gain | `35 ... 45 dB` |
| Loaded total gain | `>= 75 dB` |

## 12. Required Verification Coverage

### 12.1 PVT Matrix

Required process corners:

- `TT`
- `FF`
- `SS`

Required voltages:

- `1.6 V`
- `1.8 V`
- `1.98 V`

Required temperatures:

- `-40 C`
- `27 C`
- `125 C`

### 12.2 Monte Carlo

Monte Carlo is required because the design is mismatch-sensitive.

Required Monte Carlo metrics:

- residual input offset after AZ
- pedestal-equivalent error
- startup success
- unity-gain stability success

Recommended sample count:

- development: `200`
- signoff-lite: `500`

Recommended acceptance:

- `99%` of samples meet the residual-offset target

### 12.3 PEX

PEX is required early because layout parasitics strongly affect:

- switch feedthrough
- pedestal
- hold droop
- phase margin
- offset symmetry

## 13. Test Plan Naming

The following test names follow the repository structural testing guide.

### 13.1 `frontend_az`

- `test_frontend_az__smoke__basic.py`
- `test_frontend_az__contract__pedestal_zero_input.py`
- `test_frontend_az__contract__settling_in_phase_window.py`
- `test_frontend_az__char__noise_and_offset.py`
- `test_frontend_az__pvt__residue_and_noise.py`
- `test_frontend_az__mc__noise_and_offset.py`
- `test_frontend_az__pex__pedestal_zero_input.py`

### 13.2 `gain_stage`

- `test_gain_stage__smoke__basic.py`
- `test_gain_stage__contract__gain_gmro.py`
- `test_gain_stage__contract__icmr.py`
- `test_gain_stage__char__gain_gmro.py`
- `test_gain_stage__pvt__gain_headroom.py`

### 13.3 `second_stage`

- `test_second_stage__smoke__basic.py`
- `test_second_stage__contract__swing.py`
- `test_second_stage__contract__load_drive.py`
- `test_second_stage__char__gain_gmro.py`
- `test_second_stage__pvt__gain_headroom.py`

### 13.4 `output_stage`

- `test_output_stage__smoke__basic.py`
- `test_output_stage__contract__swing.py`
- `test_output_stage__contract__load_drive.py`
- `test_output_stage__pvt__load_drive.py`

### 13.5 `bias_gen`

- `test_bias_gen__smoke__basic.py`
- `test_bias_gen__contract__startup.py`
- `test_bias_gen__contract__current_accuracy.py`
- `test_bias_gen__pvt__current_accuracy.py`

### 13.6 `freq_comp`

- `test_freq_comp__smoke__basic.py`
- `test_freq_comp__contract__pole_zero_extract.py`
- `test_freq_comp__char__pole_zero_extract.py`
- `test_freq_comp__pex__pole_zero_extract.py`

### 13.7 `opamp_az_top`

- `test_opamp_az_top__smoke__basic.py`
- `test_opamp_az_top__contract__open_loop.py`
- `test_opamp_az_top__contract__closed_loop_step.py`
- `test_opamp_az_top__contract__noise_and_offset.py`
- `test_opamp_az_top__pvt__open_loop.py`
- `test_opamp_az_top__pvt__closed_loop_step.py`
- `test_opamp_az_top__mc__noise_and_offset.py`
- `test_opamp_az_top__pex__noise_and_offset.py`
- `test_opamp_az_top__budget__precision_ppa.py`

## 14. Required Pass/Fail Metrics

### 14.1 `frontend_az`

- pedestal-equivalent input error
- hold droop error
- switching residue
- sampled offset-cancellation effectiveness

### 14.2 `gain_stage`

- DC gain
- output resistance estimate
- ICMR
- headroom

### 14.3 `second_stage`

- gain
- output swing
- output current capability

### 14.4 `opamp_az_top`

- open-loop gain
- GBW
- phase margin
- gain margin
- residual input offset after AZ
- quiescent current
- disabled leakage
- output swing
- output current drive

## 15. Required Nominal Test Conditions

Unless stated otherwise, nominal conditions are:

- corner: `TT`
- `VDD = 1.8 V`
- `T = 27 C`
- `CL = 1 pF`
- `ICM = 0.5 * VDD` for mid-range AC tests

For low-end ICMR verification use:

- `ICM = 0 V`

## 16. Open Questions to Freeze Before Implementation

The following items must be frozen before detailed implementation:

1. Single-ended vs fully differential first tape-in target
2. External vs on-chip AZ clock generation
3. Allowed output ripple during AZ operation
4. Closed-loop gain use cases that must be guaranteed
5. Whether the `15 uA` current budget includes clock generation
6. Required noise metric and integration band

## 17. Recommended First Milestone

The first milestone should implement:

- `frontend_az`
- `gain_stage`
- `second_stage`
- `freq_comp`
- `bias_gen`
- `opamp_az_top`

The first milestone should exclude:

- on-chip non-overlap clock generation
- full PEX closure
- aggressive area optimization
- fully differential CMFB unless strictly required

## 18. SKY130 Summary Table

| Parameter | GF55 Target | SKY130 Minimum | SKY130 Maximum |
|---|---:|---:|---:|
| Mode | Inference mode | Same |
| VDD range | `1.08 ... 1.32 V` | `1.6 ... 1.98 V` | `1.6 ... 1.98 V` |
| Nominal VDD | `1.20 V` | `1.8 V` | `1.8 V` |
| Temperature range | `-40 ... 125 C` | Same | Same |
| Nominal temperature | `27 C` | Same | Same |
| Load range | `0 ... 1 pF` | `0 ... 2 pF` | `0 ... 2 pF` |
| Nominal load | `1 pF` | `1 pF` | `1 pF` |
| Input CM | `0 ... 0.5 * VDD` | Same | Same |
| Output swing compliant | `50 mV ... VDD-50 mV` | `100 mV ... VDD-200 mV` | `100 mV ... VDD-100 mV` |
| Relaxed swing | `5 mV ... VDD-5 mV` | `20 mV ... VDD-20 mV` | `20 mV ... VDD-20 mV` |
| Output current | `+/-25 uA` | `+/-20 uA` | `+/-25 uA` |
| Open-loop gain | `>= 80 dB` | `>= 65 dB` | `>= 75 dB` |
| GBW | `>= 1 MHz` | `300 kHz ... 1 MHz` | `500 kHz ... 1 MHz` |
| Phase margin | `>= 30 deg` | `>= 30 deg` | `>= 30 deg` |
| Gain margin | `>= 5 dB` | `>= 5 dB` | `>= 5 dB` |
| Input offset after AZ | `+/-60 uV` | `<= 250 uV` | `<= 150 uV` |
| Pedestal error | n/a | `<= 100 uV` | `<= 50 uV` |
| Hold droop / settling | n/a | `<= 50 uV` | `<= 30 uV` |
| Quiescent current | `<= 10 uA` | `<= 20 uA` | `<= 15 uA` |
| Disabled leakage | `<= 15 nA` | `<= 250 nA` | `<= 15 nA` |
| Area | `<= 1000 um^2` | `3000 ... 7000 um^2` | `3000 ... 5000 um^2` |
