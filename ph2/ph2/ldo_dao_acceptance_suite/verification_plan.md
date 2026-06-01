# LDO_DAO Verification Plan

## 1. Purpose and Scope

This document defines the acceptance-level verification plan for the LDO_DAO (Always-on Digital Domain Linear Regulator) block against the provided specification.

The planned verification is black-box at the DUT boundary. Testbenches drive only the documented public pins and observe only the documented output, public feedback/interface pins, and supply-source currents. Internal DUT nodes, internal instances, and implementation-specific subcircuits are outside the verification scope.

The verification plan covers the externally observable LDO behavior: output voltage regulation, quiescent supply current, static-load operation, dynamic-load transient response, loop stability, PSRR, and output-voltage statistical variation.

Process-corner, voltage, temperature, and Monte Carlo coverage are included according to the specification requirements, operating conditions, simulated-condition references, and customer guidance. The exact coverage conditions are defined explicitly in the acceptance test matrix.

### 1.1 In Scope

This plan is scoped to schematic/netlist-level acceptance testing of the LDO_DAO block through its public interface. In-scope checks are:

- black-box SPICE testbenches that instantiate the DUT through the documented pin contract;
- operating-point, AC, transient, PVT, and Monte Carlo simulations defined by this plan;
- numeric acceptance checks for the metrics listed in the acceptance test matrix;
- machine-readable pass/fail results and measured metric reporting for each acceptance run.

Passing this plan means the DUT satisfies the defined pre-layout or netlist-level acceptance criteria for the modeled conditions.

### 1.2 Out of Scope

This plan is not a tapeout sign-off plan and does not by itself authorize mask release or production tapeout. The following items are explicitly out of scope:

- physical layout creation or review;
- DRC, LVS, ERC, antenna, density, latch-up, or other physical verification;
- parasitic extraction and PEX/post-layout simulation;
- EM/IR, reliability, aging, ESD, or package/board-level analysis;
- final tapeout sign-off, release qualification, or foundry deliverables.

Those activities must be covered by separate physical sign-off and tapeout-readiness plans. If an extracted netlist is available, this acceptance plan may be reused as a simulation stimulus and metric framework, but PEX execution and physical sign-off remain outside the scope of this document.

## 2. DUT Interface and Signal Interpretation

The DUT is verified through the documented public interface.

| Pin | Role | Verification Usage |
|---|---|---|
| `vdd_3v3` | Main LDO supply input | Driven by the testbench. Used as the LDO input supply, PSRR injection source, and supply-current measurement source. |
| `vout_1v2` | Regulated 1.2 V output supply | Observed by the testbench. Used for output-voltage, static-load, dynamic-load, PSRR, and statistical-variation measurements. `COUT = 449 pF` is connected from this pin to `vss` in all acceptance testbenches. Static and dynamic loads are applied only in the testbenches that explicitly define those load conditions. |
| `vref_0v8` | External voltage reference input | Driven by the testbench. Nominal value is `0.80 V`; min/max values of `0.72 V` and `0.88 V` are covered according to the acceptance test matrix. |
| `ibiasn_0u5` | External current reference / bias input | Driven by the testbench as a current reference. Nominal value is `400 nA`; min/max values of `300 nA` and `500 nA` are covered according to the acceptance test matrix. The testbench drives current into this pin. |
| `vfb_i` | Error-amplifier feedback input | Connected by the testbench to `vfb_o` for normal closed-loop operation. Used with `vfb_o` as the public loop-break / injection interface for loop-stability measurements. |
| `vfb_o` | Feedback-divider output | Connected by the testbench to `vfb_i` for normal closed-loop operation. Used with `vfb_i` as the public loop-break / injection interface for loop-stability measurements. |
| `vss` | Analog ground | Tied by the testbench to simulator ground and used as the common reference for supplies, references, loads, and measurements. |

The intended reusable DUT wrapper or mock-DUT instance contract is:

```spice
XDUT vdd_3v3 vout_1v2 vref_0v8 ibiasn_0u5 vfb_i vfb_o vss ldo_dao
```

For normal closed-loop operating tests, the testbench connects `vfb_o` to `vfb_i`.

For loop-stability tests, `vfb_i` and `vfb_o` may be separated by the testbench injection network. No internal DUT nodes are required.

## 3. Specification Interpretation Notes

The following notes define how ambiguous or implementation-dependent specification details are handled in the acceptance testbenches.

| Item | Interpretation |
|---|---|
| `vref_0v8` voltage range | The `vref_0v8` pin-list voltage range shows `2.0-3.6`, but the operating-conditions table defines the external voltage reference as `0.72 V`, `0.8 V`, and `0.88 V`. Acceptance testbenches drive `vref_0v8` using `0.72 V / 0.80 V / 0.88 V`. |
| `ibiasn_0u5` current reference | `ibiasn_0u5` is driven as a current-reference input. Acceptance testbenches use the operating-condition values `300 nA`, `400 nA`, and `500 nA`. The testbench injects the specified current into this pin. |
| Feedback connection | For normal closed-loop operation, `vfb_o` is connected to `vfb_i` in the testbench. For loop-stability measurements, `vfb_i` and `vfb_o` may be separated by the public loop-injection network. |
| `vfb_0` typo normalization | The pin-list note `shorted with vfb_0` is interpreted as `shorted with vfb_o`, matching the documented `vfb_o` feedback-divider output pin. |
| Output capacitance | All acceptance testbenches connect `COUT = 449 pF` from `vout_1v2` to `vss`, corresponding to `840 × 535 fF`. |
| Dynamic-load frequency | The operating-conditions table defines the dynamic-load clock frequency as `10 MHz`. Acceptance dynamic-load tests use `10 MHz`. The `12 MHz` text in the simulated-parameters table is treated as reference/simulation-history text, not the acceptance stimulus. |
| Dynamic-load waveform | The dynamic-load testbench uses a pulsed load waveform consistent with the specification: average dynamic-load current target `60 µA`, pulse amplitude up to `30 mA`, pulse width `200 ps`, repeated at the clock rate or grouped into bursts. |
| Quiescent-current limit | The acceptance limit for quiescent supply current is `3 µA` from the requirements table. Simulated-parameter values are used only as reference data. |
| PVT temperature set | Acceptance PVT temperature coverage uses the block operating-condition junction temperatures `-40 °C`, `27 °C`, and `150 °C`. The `-40 °C`, `0 °C`, `27 °C`, and `125 °C` values in the simulated-parameters section are treated as historical/reference simulation conditions, not as the acceptance temperature set. |
| PVT coverage | Process-corner, voltage, and temperature coverage is included for metrics that require PVT coverage. The process-corner names are `typical`, `fff`, `ssf`, `fsf`, and `sff`. |
| Monte Carlo coverage | `Vout variation 1σ` is treated as a Monte Carlo/statistical metric for the isolated LDO. The `LDO+PRIM_REF` variation value is not part of the isolated LDO_DAO acceptance scope. Monte Carlo sample count is set to `50` samples according to customer guidance. |
| DUT netlist form | The provided implementation netlist is treated as an implementation reference. Runnable testbenches may use a compatible DUT wrapper or mock DUT, but the public pin contract must remain unchanged. |

## 4. Operating Conditions and Coverage Presets

Unless a specific test defines different conditions, the acceptance testbenches use the nominal operating conditions from the specification.

| Condition | Nominal Value | Acceptance Coverage Values |
|---|---:|---|
| Process corner | `typical` | `typical`, `fff`, `ssf`, `fsf`, `sff` |
| Junction temperature | `27 °C` | `-40 °C`, `27 °C`, `150 °C` |
| `vdd_3v3` block supply | `3.3 V` | `2.0 V`, `3.3 V`, `3.6 V` |
| `vref_0v8` voltage reference | `0.80 V` | `0.72 V`, `0.80 V`, `0.88 V` |
| `ibiasn_0u5` current reference | `400 nA` | `300 nA`, `400 nA`, `500 nA` |
| Static load current | `15 µA` | `15 µA` |
| Dynamic-load clock frequency | `10 MHz` | `10 MHz` |
| Dynamic-load average current | `60 µA` | `60 µA` |
| Dynamic-load pulse amplitude | up to `30 mA` | up to `30 mA` |
| Dynamic-load pulse width | `200 ps` | `200 ps` |
| Output capacitance | approximately `449 pF` | approximately `449 pF` |

The nominal operating point is:

```text
process = typical
temperature = 27 °C
vdd_3v3 = 3.3 V
vref_0v8 = 0.80 V
ibiasn_0u5 = 400 nA
vfb_o shorted to vfb_i
COUT = 449 pF
```

Monte Carlo output-voltage variation is evaluated separately at the specified statistical condition:

```text
process = typical
temperature = 27 °C
vdd_3v3 = 2.8 V
vref_0v8 = 0.80 V
ibiasn_0u5 = 400 nA
COUT = 449 pF
samples = 50
```

## 5. Acceptance Test Matrix

The acceptance verification is organized into reusable black-box testbenches. Each testbench drives only the documented public DUT pins and extracts the required acceptance metrics from `vout_1v2`, public feedback pins, and supply-source currents.

All acceptance testbenches connect the output capacitance explicitly:

```spice
COUT vout_1v2 vss 449p
```

### 5.1 Presets

| Preset | Definition |
|---|---|
| `NOM` | `typical`, `27 °C`, `vdd_3v3 = 3.3 V`, `vref_0v8 = 0.80 V`, `ibiasn_0u5 = 400 nA`, `vfb_o` shorted to `vfb_i`, `COUT = 449 pF` |
| `PVT` | Full process/voltage/temperature coverage using all combinations of process corners `typical`, `fff`, `ssf`, `fsf`, `sff`; temperatures `-40 °C`, `27 °C`, `150 °C`; supplies `2.0 V`, `3.3 V`, `3.6 V`; with nominal `vref_0v8 = 0.80 V` and nominal `ibiasn_0u5 = 400 nA` |
| `REF_IBIAS_SWEEP` | One-dimensional sweeps from `NOM`: `vref_0v8 = 0.72 V / 0.80 V / 0.88 V` with nominal `ibiasn_0u5`, and `ibiasn_0u5 = 300 nA / 400 nA / 500 nA` with nominal `vref_0v8` |
| `DYNAMIC_LOAD` | Dynamic load applied at `vout_1v2`: `10 MHz` clock frequency, average load current target `60 µA`, pulse amplitude up to `30 mA`, pulse width `200 ps` |
| `MC_VOUT` | Monte Carlo run for isolated LDO output-voltage variation at `typical`, `27 °C`, `vdd_3v3 = 2.8 V`, `vref_0v8 = 0.80 V`, `ibiasn_0u5 = 400 nA`, `COUT = 449 pF`; `50` samples |

One-dimensional sweeps mean that one preset group is varied while all other preset groups remain nominal. The nominal case is shared and does not need to be duplicated.

### 5.2 Test Matrix

| Testbench | Specification Coverage | Test Condition / Stimulus | Condition Coverage | Measurement Method | Acceptance Criteria |
|---|---|---|---|---|---|
| `output_voltage_op` | Output voltage regulation | Drive `vdd_3v3`, `vref_0v8`, and `ibiasn_0u5`. Short `vfb_o` to `vfb_i`. Connect `COUT = 449 pF` from `vout_1v2` to `vss`. No intentional output load is applied. | `NOM`, `PVT`, `REF_IBIAS_SWEEP` | Measure DC `vout_1v2` after the operating point converges. | `1.08 V <= Vout_dc <= 1.32 V` |
| `static_load_op` | Output voltage regulation under static load | Same as `output_voltage_op`, with `15 µA` DC load applied at `vout_1v2`. `COUT = 449 pF` remains connected. | `NOM`, `PVT`, `REF_IBIAS_SWEEP` | Measure DC `vout_1v2` under the static-load condition. | `1.08 V <= Vout_static_load <= 1.32 V` |
| `quiescent_current_op` | Quiescent supply current | Closed-loop operation with `COUT = 449 pF` connected and no intentional output load. Drive `vdd_3v3`, `vref_0v8`, and `ibiasn_0u5` according to the run condition. Short `vfb_o` to `vfb_i`. | `NOM`, `PVT`, `REF_IBIAS_SWEEP` | Measure current drawn from the `vdd_3v3` supply source and report positive current consumption into the DUT. | `Iq <= 3 µA` |
| `dynamic_load_tran` | Dynamic-load transient response: output drop, overshoot, and average drop | Closed-loop operation with `COUT = 449 pF` connected. Apply `15 µA` DC load at `vout_1v2`. Apply `DYNAMIC_LOAD` at `vout_1v2` after the static-load operating point is established. | `NOM`, `PVT` | Measure steady-state output before dynamic load, minimum output during transient, maximum output during transient, and average output during periodic dynamic-load operation. Calculate `Vout_drop_abs`, `Vout_overshoot_abs`, and `Vout_avg_drop`. | `Vout_drop_abs <= 50 mV`; `Vout_overshoot_abs <= 20 mV`; `Vout_avg_drop <= 25 mV` |
| `loop_stability_ac` | Gain-bandwidth, phase margin, and gain margin | Use `vfb_i` and `vfb_o` as the public loop-break / AC injection interface. Connect `COUT = 449 pF` from `vout_1v2` to `vss`. Apply `15 µA` DC load at `vout_1v2`. | `NOM`, `PVT` | Extract loop response, gain-bandwidth, phase margin, and gain margin from the AC/stability analysis. | `GBW >= 100 kHz`; `PM >= 40 deg`; `GM >= 20 dB` |
| `psrr_ac` | Power-supply rejection | Closed-loop operation with `COUT = 449 pF` connected. Apply `15 µA` DC load at `vout_1v2`. Inject AC ripple at `vdd_3v3` and measure AC response at `vout_1v2`. | `NOM`, `PVT` | Sweep frequency, compute PSRR, and report the minimum PSRR across the sweep. | `PSRR_min >= 40 dB` |
| `vout_variation_mc` | Output-voltage 1σ statistical variation of the isolated LDO | Closed-loop operation at the `MC_VOUT` condition with `COUT = 449 pF` connected. No intentional output load is applied. Run Monte Carlo samples for device mismatch/statistical variation. | `MC_VOUT` | Measure `vout_1v2` for each sample and compute the standard deviation. | `Vout_sigma <= 20 mV` |
