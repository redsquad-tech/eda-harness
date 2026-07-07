# Agent Instructions

Your task is to generate acceptance testbenches from a block/circuit specification and then prepare the completed testbench suite for Cadence/Virtuoso.

When the user asks you to create testbenches from a specification, first briefly describe the full work plan through ngspice testbench generation and Cadence/Virtuoso preparation, then wait for confirmation. Do not mention skill names in the user-facing plan.

Working directory rule:  
Before creating any artifacts, identify the task workspace directory: the directory that contains the user-provided specification. Create all generated artifacts inside that workspace directory unless the user explicitly asks for another location.

Work in stages:

1. Create `<workspace>/verification_plan.md`  
   Use the `spec-to-verification-plan` skill.

2. Create the mock DUT for testbench development  
   Use the `spec-to-hdl21-mock-dut` skill to create the generated HDL21 mock and SPICE mock netlist used by the testbench flow.

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

   If the user skips the report, continue to the Cadence/Maestro stages.

6. Create Cadence/Maestro setup blocks for the completed suite  
   Use the `control-to-maestro` skill.  
   Create and verify one temporary Maestro setup per testbench group per iteration.  
   Extract the reusable Maestro setup file for the group and remove the temporary folder.  
   After each group, report the result and ask the user whether to continue with the next group.

7. Assemble the final Cadence/Virtuoso library  
   Use the `maestro-to-cadence` skill.  
   Generate one `cadence_export/generate.il`, run it with Virtuoso, and verify the final library with one cell per testbench group.

After each stage, stop, briefly report the result, and ask the user whether to continue to the next stage. Do not move to the next skill/stage without user confirmation.

General rules:

* HDL21 is used to generate circuit fixtures; do not replace it with handwritten SPICE templates.
* The generated mock DUT is used as the executable DUT for ngspice development and as the placeholder DUT for Cadence/Maestro export.
* The final Cadence/Virtuoso export must keep DUT replacement localized to `<workspace>/cadence_export/dut_placeholder.scs`; users can edit that file locally to point to their real Spectre/SPICE DUT and rerun `cadence_export/generate.il`.
* PVT/corner coverage is defined in the verification plan: use specification-defined conditions when present; otherwise apply the default PVT/corner policy from the verification-planning instructions to every test where it is applicable and meaningful.
* `.control` files are responsible for including the generated mock DUT netlist and fixture netlist, sweeps, measurements, pass/fail, `RESULT`/`FAIL`/`SUMMARY`, and CSV outputs.
* Python must not compute physical metrics or pass/fail.
* Use only public DUT pins.
* Do not use internal DUT nodes as acceptance observability points.
* Do not weaken limits from the specification.
* Keep the file structure minimal and stable for downstream report generation and Cadence/Maestro assembly.
* If the specification or generated artifacts contradict each other, document the assumption/blocker and do not guess silently.
