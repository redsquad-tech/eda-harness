# Agent Instructions

Your task is to generate acceptance testbenches from a block/circuit specification and then export the completed testbench suite to Cadence/Virtuoso.

When the user asks you to create testbenches from a specification, first briefly describe the work plan and wait for confirmation. Do not mention skill names in the user-facing plan.

Working directory rule:  
Before creating any artifacts, identify the task workspace directory: the directory that contains the user-provided specification, DUT netlist, and/or existing testbench files. Create all generated artifacts inside that workspace directory unless the user explicitly asks for another location.

Work in stages:

1. Create `<workspace>/verification_plan.md`  
   Use the `spec-to-verification-plan` skill.

2. Prepare the DUT for testbench development  
   Treat the user-provided Spectre DUT netlist as the primary DUT source and preserve its public interface.  
   For ngspice development, use a provided runnable ngspice-compatible DUT netlist when available.  
   If no runnable ngspice-compatible DUT is available, create only the minimal development DUT/mock needed to run ngspice tests using the `spec-to-hdl21-mock-dut` skill.

3. Create `<workspace>/testbench_implementation_plan.md`  
   Use the `verification-plan-to-implementation-plan` skill.  
   The plan must define the minimum set of testbench groups, future files, stable output paths, and implementation order.

4. Implement ngspice testbench groups sequentially  
   Use the `implementation-plan-to-testbenches` skill.  
   Implement one group per iteration: HDL21 fixture → exported SPICE → `.control` → ngspice run → CSV/log outputs → cleanup.  
   After each group, report the result and ask the user whether to continue with the next group.

5. Optionally create the ngspice report after all testbench groups are complete  
   Use the `test2report` skill only if the user wants the report.  
   Generate:

```text
<workspace>/test_report.md
<workspace>/test_report.pdf
```

   If the user skips the report, continue to the Cadence export stage.

6. Export the completed suite to Cadence/Virtuoso  
   Use the `cadence-one-testbench-group` skill.  
   Export one testbench group per iteration. For each group, create or update:

```text
<workspace>/cadence_export/groups/<group>/generate.il
<workspace>/cadence_export/groups/<group>/verify.il
<workspace>/cadence_export/groups/<group>/<group>_cadence_status.txt
<workspace>/cadence_export/groups/<group>/generate.log
<workspace>/cadence_export/groups/<group>/verify.log
<workspace>/cadence_export/<generated_library_name>/
```

   Each Cadence group must create a real Cadence/Virtuoso library cell with `Spectre`, `config`, `adexl`, and `maestro` views.  
   After each Cadence group reaches `overall_status: PASS`, report the result and ask the user whether to continue with the next Cadence group.

After each stage, stop, briefly report the result, and ask the user whether to continue to the next stage. Do not move to the next skill/stage without user confirmation.

General rules:

* HDL21 is used to generate circuit fixtures; do not replace it with handwritten SPICE templates.
* The primary DUT is the user-provided Spectre netlist; it does not need to be rewritten in HDL21.
* For ngspice, use a provided runnable ngspice-compatible DUT netlist when available. Create a mock/development DUT only if ngspice has no runnable DUT.
* PVT/corner coverage is defined in the verification plan: use specification-defined conditions when present; otherwise apply the default PVT/corner policy from the verification-planning instructions to every test where it is applicable and meaningful.
* `.control` files are responsible for including the selected DUT netlist/model files, sweeps, measurements, pass/fail, `RESULT`/`FAIL`/`SUMMARY`, and CSV outputs.
* Python must not compute physical metrics or pass/fail.
* Use only public DUT pins.
* Do not use internal DUT nodes as acceptance observability points.
* Do not weaken limits from the specification.
* Keep the file structure minimal and stable for downstream report and Cadence export generation.
* If input documents or the netlist contradict each other, document the assumption/blocker and do not guess silently.

Cadence export rules:

* Cadence export starts only after the ngspice testbench groups are implemented and passing.
* Cadence export is not optional.
* Use the user-provided original Spectre DUT netlist as the primary Cadence DUT.
* Do not use ngspice mock/dev DUT as the primary Cadence DUT.
* Cadence export must be done one testbench group at a time.
* Each Cadence group must preserve the same test intent as the corresponding ngspice `.sp` and `.control`: stimulus, variables, run cases, analysis, measurements, derived metrics, and checks.
* Cadence `Spectre` views must be design/cell views, not standalone simulation decks.
* Analysis, measurements, checks, simulator options, and run cases belong in ADEXL/Maestro, not in the `Spectre` text view.
* If a group has temperature sweep, the generated Maestro/ADEXL tests must set simulator temperature per case, not only a design variable.
* If a group has threshold/crossing measurements, the generated Maestro/ADEXL outputs must preserve the crossing waveform, edge, occurrence, and reported swept signal value.
* Do not run full Spectre simulation unless the user explicitly asks.
* The required local Cadence acceptance for each group is structural/Maestro export success: library/cell/views exist, config opens, Maestro opens, tests/cases exist, variables/analysis/outputs/checks exist, and fresh-open verification passes.
* Each Cadence group status file must end with:

```text
overall_status: PASS
```

* Do not finish a Cadence group with `FAIL`, `BLOCKED`, `NOT_RUN`, `SKIP`, `WARN`, or partial result.