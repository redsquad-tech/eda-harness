# Agent Instructions

Your task is to generate acceptance testbenches from a block/circuit specification.

When the user asks you to create testbenches from a specification, first briefly describe the work plan and wait for confirmation. Do not mention skill names in the user-facing plan.

Work in stages:

1. Create `verification_plan.md`
   Use the `spec-to-verification-plan` skill.

2. Prepare the DUT for testbench development
   If the user already provided a runnable SPICE/ngspice netlist with the required public `.subckt` and pin order, use that netlist directly. Do not create an HDL21 DUT and do not create a mock.
   If the user already provided a suitable HDL21 DUT/mock and/or SPICE netlist, use it.
   If no runnable DUT/mock is available, create a mock DUT using the `spec-to-hdl21-mock-dut` skill.

3. Create `testbench_implementation_plan.md`
   Use the `verification-plan-to-implementation-plan` skill.
   The plan must define the minimum set of testbench groups, future files, stable output paths, and implementation order.

4. Implement testbench groups sequentially
   Use the `implementation-plan-to-testbenches` skill.
   Implement one group per iteration: HDL21 fixture → exported SPICE → `.control` → ngspice run → CSV/log outputs → cleanup.
   After each group, report the result and ask the user whether to continue with the next group.

5. Create the report after all testbench groups are complete
   Use the `test2report` skill.
   Generate `test_report.md` and `test_report.pdf`.

After each stage, stop, briefly report the result, and ask the user whether to continue to the next stage. Do not move to the next skill/stage without user confirmation.

General rules:

* HDL21 is used to generate circuit fixtures; do not replace it with handwritten SPICE templates.
* The DUT does not need to be written in HDL21 if the user already provided a runnable SPICE/ngspice netlist with the correct public contract.
* If a suitable user-provided runnable DUT netlist exists, use it. Create a mock DUT only if no runnable DUT/mock is available.
* `.control` files are responsible for including the selected DUT netlist/model files, sweeps, measurements, pass/fail, `RESULT`/`FAIL`/`SUMMARY`, and CSV outputs.
* Python must not compute physical metrics or pass/fail.
* Use only public DUT pins.
* Do not use internal DUT nodes as acceptance observability points.
* Do not weaken limits from the specification.
* Keep the file structure minimal and stable for downstream report generation.
* If input documents or the netlist contradict each other, document the assumption/blocker and do not guess silently.
