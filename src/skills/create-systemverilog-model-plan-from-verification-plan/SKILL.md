---
name: create-systemverilog-model-plan-from-verification-plan
description: Create or revise systemverilog_model/plan.md from a device specification and an existing verification_plan.md, defining the exact public interface, deterministic black-box behavior, requirement classifications, and validation cases for a behavioral SystemVerilog reference model. Use when verified DUT requirements need a concrete SystemVerilog model contract and behavioral validation plan.
---

# Skill: Create SystemVerilog Model Plan

## Purpose

Create a concise plan for a simulation-only SystemVerilog behavioral model of
the DUT's externally visible behavior for digital integration.

## Inputs

Read the device specification and `verification_plan.md`.

Use `verification_plan.md` as the normalized DUT contract and coverage source.
Consult the specification for the original requirements and behavioral details.
Preserve documented interpretations and record unresolved discrepancies that
affect the model.

## Output

Create or update `systemverilog_model/plan.md`, creating the directory when
needed.

Write the plan in English and use this structure:

```markdown
# <BLOCK_NAME> SystemVerilog Model Plan

## 1. Purpose
## 2. Interface
## 3. Behavior
## 4. Coverage
## 5. Validation
```

Keep the plan concise and specific to the device.

## 1. Purpose

Summarize the model's role and behavioral scope for digital integration in one
short paragraph.

## 2. Interface

Define the exact SystemVerilog module declaration and the interpretation of each
port.

* Preserve documented public port names and preserve directions when compatible
  with the chosen SystemVerilog value types.
* Use `logic` or packed `logic` vectors for discrete signals and `real` for
  analog numeric values in the specification units.
* State the unit and interpretation of every `real` port. A `real` port carries
  only a numeric value, not electrical loading, impedance, or current flow.
* Represent an electrical `inout` port as `input real` when the model only
  observes its numeric value, and document the direction abstraction. If the
  model must drive or resolve the port, record the required abstraction or
  blocker instead of assuming a real-valued `inout` type.
* Identify preserved ports with no modeled effect.

## 3. Behavior

Describe deterministic black-box behavior using the clearest declarative form:

* use continuous assignments or equations for stateless analytical relations;
* use SystemVerilog UDP truth/state tables for small finite mappings and state
  transitions;
* for hysteresis driven by numeric inputs, use continuous threshold comparisons
  to derive discrete logic conditions, then feed those conditions into a
  SystemVerilog UDP state table for retention;
* for clocked or multi-phase behavior, define named states and an explicit
  transition table with current state, event or condition, next state, and
  externally visible action;
* express repeated fixed-length phases as a state plus a bounded counter rather
  than listing every cycle as a separate state.

Separate datapath rules from control sequencing. Write numeric transfer
functions as equations or piecewise tables and control sequencing as a state
transition table. Do not replace either with prose describing a chain of
procedural `if` statements.

For behavior that does not fit these forms, select procedural logic only when an
equation, truth table, UDP, or state transition table would be less clear, and
record the reason.

Define, where applicable, the initial state, control and mode priority, equality
boundaries, hysteresis and state retention, specified timing, out-of-range
behavior, and relationships between outputs or independent channels.

Use specified nominal or typical values for model parameters. If only an
acceptance range exists, choose a deterministic representative value, normally
the midpoint; document its derivation, keep related values consistent, and label
it as a model default rather than an acceptance requirement.

Model only dependencies supported by the specification or
`verification_plan.md`.

Do not infer clipping, saturation, limiting, or another transfer-function rule
solely from a port voltage/current range, absolute rating, operating range, or
pin-table annotation. Add such behavior only when the inputs explicitly define
it as externally visible device behavior. If a port annotation conflicts with
an explicit transfer or acceptance requirement, document and resolve the
conflict instead of silently clamping the model.

## 4. Coverage

Classify each relevant requirement in a concise table:

```markdown
| Requirement | Classification | Treatment |
|---|---|---|
```

In the generated plan, place a brief classification legend immediately before
the table using these definitions:

* `supported` — represented directly by SystemVerilog logic, equations, state, or
  timing behavior;
* `abstracted` — its public stimulus or response is represented by a simplified
  numeric or behavioral rule while physical dependence or dynamics are omitted;
* `not-modeled` — no corresponding behavior is implemented because the
  requirement describes electrical implementation rather than public behavior
  needed for digital integration.

For each requirement, state its modeled treatment or the reason for exclusion.
Group related requirements and include only requirements present in the inputs.
Classify every requirement exercised by model validation as `supported` or
`abstracted`.
Classify a preserved input whose intentional non-dependency is validated as
`abstracted`.

## 5. Validation

Define validation cases in a concise table:

```markdown
| Case | Condition | Expected Behavior |
|---|---|---|
```

Cover, where applicable, nominal behavior, equality boundaries, initial and
retained state, hysteresis, control priority and modes, representative parameter
values, independent channels, specified timing, and inputs intentionally having
no modeled effect.

For finite numeric transfer functions, validate exact transition boundaries and
values immediately on both sides. Exhaust all output codes when tractable;
otherwise choose representative transitions across the range. Expected values
must be derived independently from the model implementation so floating-point
or rounding mistakes are observable.

## Final Check

Before finishing, verify that:

* the public interface and all numeric units are complete;
* behavior, state, boundaries, and parameter conventions are unambiguous;
* every clocked or multi-phase protocol has an explicit state transition table;
* every numeric transfer has an equation or piecewise table;
* every modeled clamp or saturation rule has an explicit behavioral source and
  is not inferred only from a port or operating range;
* the coverage section explains all classification labels used in its table;
* every relevant requirement has a coverage classification;
* validation cases cover every modeled behavior;
* the plan is self-contained for implementing and validating every `supported`
  and `abstracted` behavior without rereading the source inputs.

## Final Response

Briefly report the file path, proposed module and interface, coverage summary,
and unresolved assumptions or blockers.
