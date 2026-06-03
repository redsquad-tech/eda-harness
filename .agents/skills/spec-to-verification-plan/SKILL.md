---
name: spec-to-verification-plan
description: Use this skill to create verification_plan.md from a specification.
---

# Skill: Spec to Verification Plan

## Inputs

* Specification: PDF, Markdown, plain text, or another document format.
* Optional DUT netlist: SPICE or HDL21.

## Output

Create or update the file:

```text
verification_plan.md
```

Always write `verification_plan.md` in English.

## `verification_plan.md` Structure

Use this structure:

```markdown
# <BLOCK_NAME> Verification Plan

## 1. Purpose and Scope
## 2. DUT Interface and Signal Interpretation
## 3. Specification Interpretation Notes
## 4. Operating Conditions and Coverage Presets
## 5. Acceptance Test Matrix
### 5.1 Presets
### 5.2 Test Matrix
```

## General Rules

* The plan must be black-box at the DUT boundary.
* Testbenches must drive only documented public pins.
* Testbenches may observe only documented public outputs, public interface pins, and supply-source currents.
* Do not use internal DUT nodes, internal instances, or implementation-specific subcircuits as acceptance observability points.
* Cover all requirements from the specification.
* Do not invent requirements, numeric limits, corner names, statistical assumptions, or DUT behavior.
* Requirements and operating conditions have priority over historical, simulated, or reference results.
* Historical, simulated, or reference results may be used to understand intent, but not as acceptance limits unless the specification explicitly defines them as requirements.
* If a requirement is ambiguous, choose the most consistent engineering interpretation and document it in the notes.
* If an ambiguity blocks creation of the plan, ask the user a question.
* The plan must be concise, deterministic, and sufficient for later implementation of acceptance testbenches.

## DUT Interface and Signal Interpretation

Extract the public DUT interface from the specification and cross-check it against the optional netlist.

Use this table:

```markdown
| Pin | Role | Verification Usage |
|---|---|---|
| `<pin>` | `<role>` | `<how testbenches drive or observe this pin>` |
```

After the table, specify the intended DUT contract.

For SPICE:

```spice
XDUT <pin1> <pin2> ... <pinN> <subckt_name>
```

For HDL21:

```python
dut = <module_name>(
    <pin1>=...,
    <pin2>=...,
)
```

If no netlist is provided, create the expected public contract from the specification pin list and state that the actual wrapper/pin order must be confirmed when the implementation netlist is connected.

## Specification Interpretation Notes

Use this table:

```markdown
| Item | Interpretation |
|---|---|
| `<ambiguity / inconsistency / assumption>` | `<chosen interpretation for acceptance verification>` |
```

Document only items that affect verification, for example:

* signal polarity contradictions;
* typos in pin names, metric names, or conditions;
* inconsistent supply/signal naming;
* mismatch between specification pin list and netlist ports;
* unclear nominal condition;
* unclear current sign convention;
* unclear requirement scope;
* unclear distinction between requirement and reference/simulated data;
* assumptions for coverage, PVT, or Monte Carlo.

## Operating Conditions and Coverage Presets

Extract operating conditions from the specification.

Use this table:

```markdown
| Condition | Nominal Value | Acceptance Coverage Values |
|---|---:|---|
| `<condition>` | `<nominal>` | `<values to cover>` |
```

Define reusable presets for nominal conditions, sweeps, PVT sets, transient stimuli, and statistical conditions when they are needed to verify requirements.

Coverage strategy must follow the specification and engineering judgment:

* Include coverage for conditions that can affect the requirement being verified.
* Coverage must be concrete: do not use `optional`, `if required`, `if requested`, or `TBD` as runnable coverage in the matrix.
* If a value depends on the specific test, write `test-dependent`, not `TBD`.
* If required coverage cannot be defined because data is missing, move it to assumptions/blockers; do not create fake presets/runs.
* Include PVT when the requirement must hold across process/voltage/temperature, when this follows from operating conditions, requirement wording, simulated-condition references, or the nature of the metric being verified.
* Include Monte Carlo/statistical verification when the specification defines variation, sigma, mismatch, yield, or another statistical requirement.
* Do not add process or Monte Carlo runs as future placeholders if the specification does not require such verification.
* For one-dimensional sweeps, explicitly state that only one group of conditions changes and all other conditions remain nominal.
* Use full-combination coverage only when it is explicitly required or engineering-necessary; otherwise prefer compact one-dimensional sweeps or meaningful grouped presets.

## Acceptance Test Matrix

Use this table:

```markdown
| Testbench | Specification Coverage | Test Condition / Stimulus | Condition Coverage | Measurement Method | Acceptance Criteria |
|---|---|---|---|---|---|
| `<testbench_name>` | `<requirements covered>` | `<stimulus and setup>` | `<presets/runs>` | `<metric extraction>` | `<pass/fail criteria>` |
```

For each row:

* `Testbench`: choose a short `snake_case` name derived from the requirement and analysis type.
* `Specification Coverage`: list exact requirement names or normalized metric names from the specification.
* `Test Condition / Stimulus`: describe driven pins, supplies, references, loads, mode controls, OP/DC/TRAN/AC/statistical stimulus, and public-pin connections.
* `Condition Coverage`: specify the concrete presets/runs that must be executed.
* `Measurement Method`: explain how the metric is extracted from simulation results.
* `Acceptance Criteria`: specify numeric pass/fail limits with units. A qualitative criterion is allowed only if no numeric requirement exists.

Testbench grouping rules:

* One testbench should cover all related metrics extracted from the same setup/stimulus/waveform/analysis.
* Do not create a separate testbench only for a derived metric if it is computed from metrics in the same run.
* Hysteresis, threshold pairs, droop/overshoot/average drop, gain/phase/gain-margin, and similar related metrics must be grouped into one reusable testbench if they use the same common stimulus or analysis.
* Split testbenches only when setup, stimulus, analysis type, or observability actually differs.

Measurement rules:

* For DC/OP metrics, measure the value after the operating point converges.
* For ramp thresholds, measure the swept input value at the relevant output transition.
* For hysteresis, define the formula from rising/falling thresholds.
* For supply currents, report positive current consumption into the DUT and document simulator sign normalization.
* For transient droop/overshoot/settling metrics, define the baseline and measurement window.
* For AC metrics, define the injection point, observed node, frequency range if specified, and extracted metric.
* For statistical metrics, define the per-sample measurement and final statistic.
* Do not use `smoke-only` for a metric that can be measured according to the specification.

## Final Checklist

Before finishing, verify that:

* all public pins are represented in the DUT interface table;
* the DUT contract is specified;
* verification-relevant ambiguities are documented;
* operating conditions and coverage presets are defined;
* every specification requirement appears in the test matrix;
* every testbench row has stimulus, coverage, measurement method, and acceptance criteria;
* related metrics are grouped into the minimum number of reusable testbenches;
* coverage in the test matrix is concrete, with no optional/future/TBD runnable runs;
* PVT/statistical coverage is included where required by the specification or engineering necessity;
* no internal DUT nodes are used as acceptance observability points;
* no requirements or numeric limits are invented;
* the plan is concise and ready for testbench implementation.

## Final Response to the User

After creating or updating `verification_plan.md`, respond briefly with:

* created/updated file name;
* selected DUT contract;
* main requirement groups covered;
* PVT/Monte Carlo decisions and why;
* blockers or assumptions, if any.
