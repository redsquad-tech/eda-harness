# v3 Product Maximum Requirements

This file is a production-local copy of the maximum-requirement subset from
[`opamp_az_spec.md`](/home/vadim/work/eda-harness/opamp_az_spec.md).

It exists to anchor acceptance tests and customer-facing bundle contents.

## Environment

- Process: `sky130` 1.8 V core devices
- Supply range: `1.6 V ... 1.98 V`
- Nominal supply: `1.8 V`
- Temperature range: `-40 C ... 125 C`
- Nominal temperature: `27 C`

## Load and Output

- Load range: `0 pF ... 2 pF`
- Nominal load: `1 pF`
- Output compliant swing: `0.1 V ... VDD - 0.1 V`
- Relaxed output swing: `0.02 V ... VDD - 0.02 V`
- Output current: `+/-25 uA`

## Gain, Bandwidth, and Stability

Nominal AC conditions:

- `TT`
- `VDD = 1.8 V`
- `T = 27 C`
- `CL = 1 pF`

- Open-loop gain: `>= 75 dB`
- GBW: `0.5 ... 1 MHz`
- Phase margin: `>= 30 deg`
- Gain margin: `>= 5 dB`

## Offset and AZ Error

- Residual input-referred offset after AZ: `<= 150 uV`
- Stretch-goal residual offset: `<= 100 uV`
- Pedestal-equivalent input error at nominal: `<= 50 uV`
- Hold droop contribution per AZ cycle: `<= 30 uV`

## Power and Leakage

- Quiescent current, enabled: `<= 15 uA`
- Disabled leakage current: `<= 15 nA`

## Acceptance Interpretation

The `prod` acceptance suite checks these maximum requirements directly against
the current integrated DUT and its available benches:

- core nominal AC / output / leakage
- top-level AZ nominal
- top-level AZ reduced PVT
- top-level AZ mismatch-only Monte Carlo

Any failing acceptance test means the current DUT is not yet tapeout-ready
against the maximum requirement set.
