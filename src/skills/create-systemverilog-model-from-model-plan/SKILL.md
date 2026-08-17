---
name: create-systemverilog-model-from-model-plan
description: Create or revise systemverilog_model/model.sv from an existing systemverilog_model/plan.md, implementing its exact public interface and deterministic black-box behavior as a self-contained behavioral SystemVerilog reference model, then validate it with Verible and Verilator. Use when a concrete SystemVerilog model plan must become a runnable model for digital integration.
---

# Skill: Create SystemVerilog Model

## Purpose

Implement and validate the behavioral reference model defined by
`systemverilog_model/plan.md`.

## Input

Read `systemverilog_model/plan.md` completely and treat it as the implementation
contract.

If the plan is incomplete or internally inconsistent in a way that prevents
deterministic implementation, report the blocker instead of inventing behavior.

## Output

Create or update `systemverilog_model/model.sv`.

The file must contain one self-contained public model and any private
SystemVerilog declarations it requires. Keep module name, ports, directions,
types, units, parameters, and defaults identical to the plan.

## Implementation

Implement every `supported` and `abstracted` behavior in the plan. Omit
`not-modeled` physical effects.

Use the behavioral form selected by the plan:

* continuous assignments or functions for stateless equations;
* UDP truth or state tables for small finite mappings and state transitions;
* continuous comparisons from numeric inputs to discrete conditions before a
  UDP when numeric hysteresis is required;
* named state types and `case`-based next-state logic that directly follows the
  planned transition table for clocked or multi-phase behavior.

Keep datapath and control separate. Implement piecewise numeric equations in
small functions or expressions and state transitions with `case`. Do not turn a
planned equation or transition table into a long nested `if`/`else` sequence.
Use procedural conditions only where they directly express reset, parameter
validation, priority guards, or piecewise equation boundaries, and keep them
minimal.

Define deterministic initialization, equality boundaries, priority, retained
state, unknown-control behavior, timing, and out-of-range behavior exactly as
planned. Preserve intentional non-dependencies.

For coupled parameters, expose only the planned independent parameters and
derive dependent values from them. Check invalid parameter relationships at
simulation start when the plan requires it.

Treat `real` ports as unit-bearing numeric values. Do not infer electrical
loading, impedance, current flow, disciplines, or resolution behavior from
them.

Keep the model simulator-independent SystemVerilog accepted by both Verible and
Verilator. Do not add test-only public ports or device-specific behavior absent
from the plan.

## Static Validation

Require `verible-verilog-format`, `verible-verilog-syntax`,
`verible-verilog-lint`, and `verilator`.

Format `model.sv`, then run:

```bash
verible-verilog-format --inplace systemverilog_model/model.sv
verible-verilog-syntax systemverilog_model/model.sv
verible-verilog-lint systemverilog_model/model.sv
verilator \
  --lint-only \
  --timing \
  --top-module <PUBLIC_MODULE> \
  systemverilog_model/model.sv
```

Resolve diagnostics in the model. Use a narrowly scoped lint waiver only when
the planned public contract or required output path necessarily violates a
style rule, and state the reason beside the waiver.

## Behavioral Validation

Create one or more temporary SystemVerilog testbenches that instantiate the
public model and cover the plan's Validation section. Prefer one testbench when
the cases share a compatible elaboration and expected exit status.

Each case must check its expected behavior and terminate unsuccessfully on a
mismatch. Include boundary equality, initialization and retained state,
parameter defaults or overrides, priority and independent channels when the
plan defines them.

For a finite numeric transfer, test exact transition boundaries and values
immediately on both sides. Exhaust all output codes when tractable. Calculate
expected results independently rather than copying the model expression into
the testbench; account for `real` rounding without allowing a value on the wrong
side of a specified boundary.

Use separate runs for incompatible elaboration-time parameter sets or expected
configuration failures. Count an expected-failure case as passed only when the
run fails for the intended diagnostic.

Compile and execute each temporary testbench with Verilator:

```bash
verilator \
  --binary \
  --timing \
  --top-module <TESTBENCH_MODULE> \
  --Mdir <TEMP_BUILD_DIR> \
  systemverilog_model/model.sv \
  <TEMP_TESTBENCH>
<TEMP_BUILD_DIR>/V<TESTBENCH_MODULE>
```

A successful compile without executing the generated binary and its checks is
insufficient.

If a representable validation case fails, compare both the model and temporary
testbench against the plan, fix the incorrect artifact, and rerun the complete
static and behavioral validation. Repeat until all representable cases pass or
a genuine plan or tool blocker is identified. Do not weaken checks or change
expected behavior merely to obtain a pass.

For planned behavior that Verilator cannot represent faithfully, such as
four-state `X` or `Z` semantics, verify the implementation structurally and
report the tool limitation instead of claiming a runtime pass.

Remove temporary testbenches, generated executables, build directories, and
tool caches after successful validation. Keep failed logs or build artifacts
only when they are needed to diagnose a blocker.

## Final Check

Before finishing, verify that:

* `model.sv` matches the planned public interface and parameter contract;
* analytical behavior remains equation-based and clocked control directly
  follows the planned state transition table;
* every supported or abstracted behavior is implemented;
* every planned validation case was executed or explicitly reported as limited
  by the validation tool;
* Verible syntax and lint checks pass;
* Verilator lint, build, and behavioral execution pass;
* no temporary validation artifacts remain after success.

## Final Response

Briefly report the model path, implemented behavioral scope, Verible and
Verilator results, any tool-limited validation cases, and unresolved blockers.
