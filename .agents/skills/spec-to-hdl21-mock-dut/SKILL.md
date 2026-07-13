---
name: spec-to-hdl21-mock-dut
description: Use this skill alone, after verification_plan.md exists, to create an HDL21 mock DUT and generated SPICE mock netlist. Treat it as one isolated workflow stage and stop before implementation-plan or testbench work.
---

# Skill: Spec to HDL21 Mock DUT

## Execution Boundary

Execute only this skill in the current turn. A broad request for the whole workflow does not authorize later stages. If the skill pauses for user input, the answer authorizes only completion of this skill. After reporting the result, wait for a new user message explicitly requesting continuation.

## Purpose

Create the mock DUT used by the generated testbench flow.

The mock DUT is not a real device implementation. It must match the public DUT contract from `verification_plan.md` and reproduce the external behavior needed for the measurements in the Acceptance Test Matrix in a simplified way.

## Inputs

* Specification.
* `verification_plan.md`.

## Output

Create or update:

```text
mock_device.py
mock_device.sp
```

`mock_device.sp` must be generated from `mock_device.py`. Do not edit generated SPICE manually.

## Main Rules

* The DUT contract is more important than the internal mock implementation.
* Generated SPICE must contain a `.subckt`/top wrapper with the same name, public pins, and pin order expected by the testbenches.
* Use the DUT contract from `verification_plan.md` as the source of truth for the mock public wrapper.
* Do not use internal nodes of the real DUT as the public interface of the mock.
* Keep the mock independent of PDK/foundry models and Cadence model configuration.
* The mock must be deterministic, fast, and simulator-friendly.
* Mock values must be inside acceptance limits with reasonable margin, not on the boundary.

## HDL21 Requirement

`mock_device.py` must actually use HDL21 to describe the circuit and export SPICE.

Rules:

* describe public ports/top wrapper as an HDL21 module;
* describe ordinary mock elements using HDL21 instances/primitives/helpers;
* export SPICE through the HDL21 netlisting/export flow;
* do not replace HDL21 generation with full handwritten SPICE text generation;
* do not use HDL21 only as a port-list declaration on top of fully handwritten SPICE;
* if the required behavioral behavior cannot be expressed cleanly with HDL21, a small raw-SPICE behavioral helper may be used;
* if a raw-SPICE behavioral helper is used, the public top wrapper must still be generated through HDL21. The raw helper may only be an internal subckt/model/include connected from the HDL21-generated wrapper;
* the raw-SPICE helper must be isolated, documented, and used only for the simulator-specific behavioral core;
* the top wrapper, public contract, and all wrapper circuitry expressible in HDL21 must still be generated through HDL21.

## Mock DUT Behavior

Read the `Acceptance Test Matrix` from `verification_plan.md` and implement the minimum external behavior needed for all planned checks.

For each test matrix row, check:

* which public pins will be driven;
* which public outputs or supply currents will be measured;
* which modes, sweeps, ramps, OP/DC/TRAN/AC/statistical runs are needed;
* which metrics must be measurable.

If several metrics are extracted from the same waveform/analysis, the mock must support them consistently. For example, rising/falling thresholds and hysteresis must come from one hysteretic response, and transient drop/overshoot/average drop must come from one transient response.

## Mock Parameters

Move the main constants to the beginning of `mock_device.py`:

* nominal output/reference/current values;
* thresholds and hysteresis values;
* current consumption values;
* delay/time-constant/settling parameters;
* AC/PSRR/stability surrogate parameters, if such checks exist;
* statistical surrogate parameters, if the verification plan requires statistical checks.

## Coverage Awareness

The mock must work correctly across public-pin conditions/runs listed in `verification_plan.md`.

* If a supply/reference/control pin is swept, the mock must respond to that public pin or preserve valid measurable behavior across the full sweep range.
* If temperature is swept, the mock must remain runnable and measurable across the temperature range, but it does not need to model real temperature physics.
* If there is a mode control, bypass, enable, reset, or test mode, the mock must explicitly implement this public-pin logic.
* If there are supply-current checks, the mock must create measurable current through the corresponding supply pins with the correct magnitude and stable sign convention.
* If there are AC tests, the mock must have an AC-observable path sufficient for metric extraction.
* If there are statistical/Monte Carlo checks, the mock must allow the pipeline to run, but must not pretend to validate real device statistics.

## Ngspice Smoke Check

Create a temporary smoke deck:

```text
mock_device_smoke.sp
```

The smoke deck is only used to check that `mock_device.sp` parses, instantiates, and runs in ngspice.

The smoke deck must:

* include `mock_device.sp`;
* not include PDK/foundry models;
* instantiate the mock DUT with the exact public DUT contract and pin order;
* drive all supply, ground, analog input, digital/control, reference, bias, enable/reset pins to safe nominal values from `verification_plan.md`;
* connect required public feedback pins according to the nominal operating setup, if such pins exist;
* add simple loads or high-value resistors where needed to avoid floating nodes;
* run at least `.op` and a short `.tran`.

Run:

```bash
ngspice -b -o mock_device_smoke.log mock_device_smoke.sp
```

If there are errors, fix `mock_device.py`, regenerate `mock_device.sp`, rerun the smoke check, and repeat until it succeeds.

After a successful smoke check, delete the temporary files:

```text
mock_device_smoke.sp
mock_device_smoke.log
```

If the smoke check fails because of a blocker, keep the log for diagnostics and clearly report the blocker.

## Final Checklist

Before finishing, verify that:

* `mock_device.py` actually uses HDL21 generation and is not manually generating the entire SPICE netlist;
* generated SPICE contains the expected `.subckt`/top wrapper and pin order;
* `mock_device.sp` is generated from `mock_device.py`;
* planned checks from the Acceptance Test Matrix have supported mock behavior;
* measured outputs/currents will be measurable where needed;
* swept public-pin supplies/references/controls are supported or remain measurable over their ranges;
* the mock does not require PDK/foundry includes;
* no internal DUT nodes are used;
* the ngspice smoke check passed;
* temporary smoke files were deleted after a successful check.

## Final Response to the User

Respond briefly with:

* which files were created/updated;
* which DUT contract was implemented;
* which planned checks are supported by the mock behavior;
* whether SPICE was generated through the HDL21 flow;
* whether the ngspice smoke check passed;
* remaining limitations/blockers, if any.

## Stage Boundary

After completing this skill, stop, report the result to the user, and wait for explicit confirmation before invoking any downstream skill.
