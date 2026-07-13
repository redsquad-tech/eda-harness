---
name: spec-to-verification-plan
description: Use this skill alone to create verification_plan.md from a specification. Treat it as one isolated workflow stage and stop before any mock-DUT, implementation-plan, testbench, report, or Cadence work.
---

# Skill: Spec to Verification Plan

## Execution Boundary

Execute only this skill in the current turn. A broad request for the whole workflow does not authorize later stages. If the skill pauses for user input, the answer authorizes only completion of this skill. After reporting the result, wait for a new user message explicitly requesting continuation.

## Inputs

* Specification: PDF, Markdown, plain text, or another document format.

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
* Do not invent requirements, numeric limits, statistical assumptions, DUT behavior, project-specific PDK model files, or proprietary model-section names. Default logical PVT/corner presets may be created only by the policy below.
* Requirements and operating conditions have priority over historical, simulated, or reference results.
* Historical, simulated, or reference results may be used to understand intent, but not as acceptance limits unless the specification explicitly defines them as requirements.
* If a requirement is ambiguous, choose the most consistent engineering interpretation and document it in the notes.
* If an ambiguity blocks creation of the plan, ask the user a question.
* The plan must be concise, deterministic, and sufficient for later implementation of acceptance testbenches.

## DUT Interface and Signal Interpretation

Extract the expected public DUT interface from the specification.

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

If the specification does not define a SPICE subckt name or pin order, choose a stable expected contract from the documented pins and document the assumption.

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
* unclear public pin list, pin direction, pin naming, or pin order;
* unclear nominal condition;
* unclear current sign convention;
* unclear requirement scope;
* unclear distinction between requirement and reference/simulated data;
* whether process corners come explicitly from the specification or are deferred as `configured_process_corners`;
* assumptions for Monte Carlo or statistical coverage when explicitly required.

## Operating Conditions and Coverage Presets

Extract explicit operating conditions from the specification first.

Use this table:

```markdown
| Condition | Nominal Value | Acceptance Coverage Values |
|---|---:|---|
| `<condition>` | `<nominal>` | `<values to cover>` |
```

Define reusable presets for nominal conditions, sweeps, PVT sets, transient stimuli, and statistical conditions when they are needed to verify requirements.

Always record process coverage in this machine-readable table:

```markdown
| Process Coverage Item | Value |
|---|---|
| Corner Source | `<specification / configuration / none>` |
| Logical Corners | `<comma-separated exact names / configured_process_corners / none>` |
```

Use `specification` with the exact required logical corner names when the specification defines them. Use `configuration` with `configured_process_corners` when process variation is applicable but the specification does not define the required set. Use `none` for both values only when process variation is not applicable or meaningful anywhere in the plan; do not use `none` merely because the specification omits corner names.

Coverage strategy must follow the specification, the default PVT/corner policy, and engineering judgment:

* Include coverage for conditions that can affect the requirement being verified.
* Coverage must be concrete: do not use `optional`, `if required`, `if requested`, or `TBD` as runnable coverage in the matrix. `configured_process_corners` is the defined late-binding policy below, not a `TBD` value.
* If a value depends on the specific test, write `test-dependent`, not `TBD`.
* If required non-PVT numeric coverage cannot be defined because data is missing, move it to assumptions/blockers; do not create fake runnable values.
* Apply PVT coverage to analog/performance requirements, DC/OP currents, thresholds, timing, AC metrics, transient metrics, regulation, startup, and mode behavior where operating conditions can affect pass/fail.
* Do not apply PVT expansion where it is not physically or logically meaningful; document the reason in notes or condition coverage.
* Use full-combination coverage for PVT according to the policy below. For non-PVT sweeps, use full combinations only when explicitly required or engineering-necessary.
* Include Monte Carlo/statistical verification only when the specification defines a statistical acceptance requirement, yield requirement, sigma limit, mismatch requirement, or explicitly requires Monte Carlo/statistical verification.
* Do not create Monte Carlo/statistical acceptance testbench rows from simulated, historical, characterization, or reference-result tables alone. If statistical values are listed only as simulated/reference results, document them in notes but do not add runnable statistical coverage.
* Do not add Monte Carlo runs as future placeholders if the specification does not require statistical verification. Process corners must follow the PVT/corner policy below.
* For one-dimensional non-PVT sweeps, explicitly state that only one group of conditions changes and all other conditions remain nominal.

Default PVT/corner policy:

* Use specification-defined voltage, temperature, and other numeric PVT conditions when present.
* If the specification explicitly requires process corners, use their exact logical names and exact required subset.
* If the specification does not explicitly define required process corners, use `configured_process_corners` wherever process variation is applicable and meaningful. This means every logical corner later defined in `cadence_export/model_bindings.toml`.
* Do not infer required process coverage from historical, simulated, characterization, or reference-result tables alone.
* If it is ambiguous whether names in the specification are required process coverage or reference data, document the blocker and ask the user instead of guessing.
* Keep logical process-corner names separate from project-specific model-section names.
* If the specification names model files or sections, document them as reference information only; model binding is configured at the later Cadence stage.
* If the specification defines only part of the non-process PVT coverage, use the specification-defined dimensions and apply default coverage to the missing voltage and temperature dimensions.
* If the specification does not define PVT/corner coverage, create default PVT coverage for every test where PVT variation is applicable and meaningful.
* Local access to PDK model files is not required for `verification_plan.md`. Do not mark missing local model files as a blocker at this stage.
* Logical process coverage must not be conditional on local model access. Keep the specification-required set when it is explicit; otherwise keep `configured_process_corners`.
* Default supply-voltage coverage is low/nominal/high. Use specified operating min/nom/max values when available. If only a range is specified, use min/mid/max. If only nominal supply is specified, use `0.9 * Vnom`, `Vnom`, and `1.1 * Vnom`. If no supply value is available, document a blocker instead of inventing a voltage.
* Default temperature coverage is cold/nominal/hot. Use specified temperature min/nom/max values when available. If only a range is specified, use min/nominal-within-range/max. If no temperature values are specified, use `-40 °C`, `27 °C`, and `125 °C`.
* For multiple supplies, vary relevant supplies coherently as low/nominal/high unless the specification requires independent supply combinations.
* PVT coverage means the full combination of applicable process, supply-voltage, temperature, and specification-defined PVT dimensions for that test.
* Do not invent project-specific model paths or model-section names.

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
* `Condition Coverage`: specify concrete presets/runs. For PVT rows, explicitly state the full combination of dimensions. Use `explicit_spec_pvt` when all applicable numeric voltage and temperature values come from the specification, `mixed_spec_default_pvt` when some applicable numeric values come from the specification and others use defaults, and `default_pvt` when all applicable numeric voltage and temperature values use defaults. The selected logical process set does not change this classification. Use `nominal_only_with_reason` only when PVT is not meaningful, and `statistical_by_spec` only for specification-defined statistical coverage.
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
* the process-coverage table has exactly one valid source and matching logical-corner value;
* every specification requirement appears in the test matrix;
* every testbench row has stimulus, coverage, measurement method, and acceptance criteria;
* related metrics are grouped into the minimum number of reusable testbenches;
* coverage in the test matrix is concrete, with no optional/future/TBD runnable runs;
* voltage, temperature, and other numeric PVT coverage follows the specification when defined, while process coverage uses the explicit specification-required set or `configured_process_corners`;
* PVT rows explicitly state the full combination of applicable dimensions;
* explicit process-corner names are preserved exactly, while absent specification coverage is represented as `configured_process_corners`;
* missing local PDK model files are not treated as a blocker for the verification plan;
* nominal-only rows have a clear reason;
* statistical coverage is included only when required by the specification;
* no fake project-specific PDK paths or proprietary model sections are invented;
* no internal DUT nodes are used as acceptance observability points;
* no requirements or numeric limits are invented;
* the plan is concise and ready for testbench implementation.

## Final Response to the User

After creating or updating `verification_plan.md`, respond briefly with:

* created/updated file name;
* expected DUT contract;
* main requirement groups covered;
* PVT/corner decisions, including whether process corners are explicit or deferred to configuration;
* when using `configured_process_corners`, explain plainly in the user's language: the concrete process corners are not known yet; the user will list them later in `cadence_export/model_bindings.toml`, and tests with this condition will run on every corner listed there;
* Monte Carlo/statistical decision and why;
* blockers or assumptions, if any.

## Stage Boundary

After completing this skill, stop, report the result to the user, and wait for explicit confirmation before invoking any downstream skill.
