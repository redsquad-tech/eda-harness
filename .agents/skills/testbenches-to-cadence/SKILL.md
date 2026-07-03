---
name: testbenches-to-cadence
description: Generate a compact Cadence/Virtuoso SKILL export file for one completed ngspice testbench group. Use when converting the current tests group SPICE and control files into a Cadence library cell, Spectre text view, config view, and Maestro setup with TB_* variables, analyses, outputs, specs, PVT corners, native temperature, and $LIB_PATH model files.
---

# Testbenches To Cadence

## Goal

Generate a compact Cadence/Virtuoso `generate.il` for completed ngspice testbench groups.

Work on one group at a time. After generating one group, briefly report back to the user and ask whether to proceed to the next one.

One iteration = one group. Do not proceed to the next group without the user's confirmation.

Main principle: use `assets/generate.il.template` as the skeleton, filling it in for the specific `tests/<group>.sp`, DUT netlist, and test intent, without building unnecessary framework around a simple task.

## Input

Expected sources in the workspace:

```text
tests/<group>.sp
tests/<group>.control
verification_plan.md
testbench_implementation_plan.md
original Spectre DUT netlist
```

The workspace is the directory containing these files. Create all Cadence artifacts inside this workspace.

## Output

Create or update only the artifacts for the current group:

```text
cadence_export/groups/<group>/generate.il
cadence_export/generated_support/cadence_dut.scs
cadence_export/generated_support/<group>.scs
cadence_export/<library_name>/
```

`generate.il` must create Cadence cell views:

```text
<library>/<cell>/spectre_<group>
<library>/<cell>/config
<library>/<cell>/maestro
```

Default names:

```text
library = <workspace_name>_acceptance_lib or the already accepted project library name
cell = fixture .SUBCKT name imported through cdsTextTo5x
test name = <group>
spectre view = spectre_<group>
config view = config
maestro view = maestro
```

## Required Flow

1. Identify the workspace.
2. Select one group. If the group is not explicitly specified, select the first group from `testbench_implementation_plan.md` that does not yet have a Cadence export.
3. Find the source files:
   - `tests/<group>.sp`
   - `tests/<group>.control`
   - the original Spectre DUT netlist.
4. From `tests/<group>.sp`, identify the fixture `.SUBCKT`, its parameters, sources, loads, DUT instance, and observed nodes/branches.
5. From `.control`, `verification_plan.md`, and `testbench_implementation_plan.md`, extract:
   - `TB_*` parameters and nominal values;
   - analysis intent: `dc`, `op`, `tran`, `ac`;
   - measurements/outputs;
   - specs/checks;
   - run cases;
   - process corners;
   - temperature cases.
6. Copy `assets/generate.il.template` to `cadence_export/groups/<group>/generate.il`.
7. Replace placeholders with real values.
8. Run the generator from the workspace:

```bash
virtuoso -nograph -restore cadence_export/groups/<group>/generate.il
```

If only another known local launch mode works, for example `-nographE`, use it.

## Rules for `generator.il`

Keep `generate.il` short and understandable. Do not add unnecessary logs, helper functions, diagnostics, `verify.il`, or status files.

Comments should appear above meaningful blocks:

```text
Block 1: names and source files
Block 2: Cadence library
Block 3: Cadence DUT support deck
Block 4: importable Spectre/SPICE wrapper
Block 5: Spectre text view import
Block 6: config view
Block 7: Maestro test
Block 8: nominal fixture variables
Block 9: analysis, outputs, and limits
Block 10: corners matrix
Block 11: save the Maestro setup
```

Blocks may be combined if that makes the result simpler and cleaner. Do not change the template structure unless necessary; change it only if a specific testbench otherwise cannot be imported or opened in the current Virtuoso version.

## DUT Support

The Cadence DUT must always be the original Spectre DUT netlist, not a mock/dev DUT.

If the original DUT already has a reusable subckt with public pins, use it directly through `cadence_dut.scs`.

If the original DUT is a top-level Spectre netlist without the required public subckt, create a minimal Spectre wrapper in `cadence_dut.scs`:

```spectre
subckt <dut_subckt_name> <public pins>
<original DUT body>
ends <dut_subckt_name>
```

For a flat Spectre/ADE point netlist, `cadence_dut.scs` must be a clean support deck:

```text
simulator lang=spectre
subckt <dut_subckt_name> <public pins>
<device/subckt instance lines only>
ends <dut_subckt_name>
```

Do not copy the following into the clean DUT subckt/support deck:

```text
ADE/service includes such as ade_e.scs
PDK/model includes from the original point netlist
simulatorOptions
analysis statements
info statements
saveOptions
```

PDK/process models must come from Maestro corner Model Files through `$LIB_PATH/<proc>.scs section <proc>`, not from `cadence_dut.scs`.

When copying lines read through SKILL `gets`, write them without an additional newline:

```lisp
fprintf(out "%s" line)
```

Do not use:

```lisp
fprintf(out "%s\n" line)
```

## Wrapper Deck

Generated wrapper:

```text
cadence_export/generated_support/<group>.scs
```

Wrapper form:

```spectre
simulator lang=spectre
include "<absolute path>/cadence_export/generated_support/cadence_dut.scs"

simulator lang=spice
<embedded tests/<group>.sp>
simulator lang=spectre
```

Embed the contents of `tests/<group>.sp` in the wrapper by reading the file and using `fprintf(out "%s" line)`. This keeps `tests/<group>.sp` as the source of truth while making the `.SUBCKT` visible to `cdsTextTo5x`.

Preferred path: first try importing with the clean `cadence_dut.scs` included in the wrapper, as shown above. This preserves a simple structure: the fixture and DUT support are visible in the imported Spectre view, while process models remain corner-level Model Files.

Fallback path: if `cdsTextTo5x` fails specifically because of the DUT support include, do not rebuild the fixture manually and do not place the DUT in Model Files. Leave the wrapper fixture-only:

```spectre
simulator lang=spectre
simulator lang=spice
<embedded tests/<group>.sp>
simulator lang=spectre
```

and attach `cadence_dut.scs` as a Maestro test-level Definition File:

```lisp
maeSetEnvOption(
  testName
  ?options list(list("definitionFiles" list(strcat(cwd "/" dutSupport))))
  ?session sess
)
```

This way, `cadence_dut.scs` will appear in the generated simulator input as a regular include, but it will not become a corner Model File.

Do not include the following in the Cadence wrapper:

```text
mock_device.sp
tests/<group>.control
.control
.endc
RESULT/SUMMARY echo logic
wrdata/write raw
quit
```

## Maestro Setup

Create one Maestro test per fixture group if the analysis/setup is truly single.

Before recreating the generated Maestro view, delete the old generated view so repeated runs do not accumulate duplicate tests/outputs:

```lisp
when(ddGetObj(lib cell maestroView)
  ddDeleteObj(ddGetObj(lib cell maestroView))
)
```

Create the following in Maestro:

```text
TB_* design variables at test level
analysis
outputs once per metric
specs/checks once per metric
corners for run cases and PVT matrix
```

Do not create separate tests for the process, temperature, supply/reference/ramp/case matrix. These measurements must be corners.

## Analysis Setup

Transfer analysis intent from `tests/<group>.control`, `verification_plan.md`, and `testbench_implementation_plan.md` into Maestro analysis fields. It is not enough to simply create `TB_*` variables if the analysis itself does not use them.

For transient groups, set stop/max step through `maeSetAnalysis` `?options`, because `maeSetAnalysis` accepts analysis fields through `options`, not as separate keyword arguments:

```lisp
maeSetAnalysis(
  testName "tran"
  ?enable t
  ?options list(
    list("stop" "<stop_time_expr>")
    list("maxstep" "<max_step_expr>")
  )
  ?session sess
)
```

`<stop_time_expr>` and `<max_step_expr>` must be derived from the original ngspice transient intent. If stop/step vary by case, define them through corner-level `TB_*` variables and use those variables in the analysis options.

Example form:

```lisp
maeSetVar("TB_TRAN_STOP" "<nominal_stop>" ?typeName "test" ?typeValue list(testName) ?session sess)
maeSetVar("TB_TRAN_MAXSTEP" "<nominal_step>" ?typeName "test" ?typeValue list(testName) ?session sess)
maeSetAnalysis(
  testName "tran"
  ?enable t
  ?options list(
    list("stop" "TB_TRAN_STOP")
    list("maxstep" "TB_TRAN_MAXSTEP")
  )
  ?session sess
)
```

If the fixture already has meaningful timing variables, they may be used directly instead of adding new generic names, for example as an expression over existing `TB_*` variables. The key requirement is that the saved Maestro state and generated simulator input contain non-empty transient stop/maxstep intent.

## Corners

Build the corner matrix once as a `corners` list, then use this list for:

```text
maeSetCorner
corner-level TB_* overrides
AXL native temperature
AXL model files
```

Set up process models through a model object:

```lisp
model = axlPutModel(cornerHandle proc)
axlSetModelFile(model strcat("$LIB_PATH/" proc ".scs"))
axlSetModelSection(model proc)
axlSetModelTest(model testName)
axlSetEnabled(model t)
```

Do not check whether `$LIB_PATH/<proc>.scs` exists locally. This is a symbolic model reference for the Cadence/Spectre environment.

Do not add `cadence_dut.scs` as a corner model object. Corner Model Files must contain only process model references.

Set temperature as native corner temperature:

```lisp
axlPutVar(cornerHandle "temperature" temp)
```

Do not rely only on the design variable `temp` if a Temperature row is required in Corners Setup and the simulator option `temp`.

## Outputs And Paths

Create outputs using the `maeAddOutput` form:

```lisp
maeAddOutput("<name>" testName ?outputType "point" ?expr "<calculator_expr>" ?session sess)
```

If the current Virtuoso version does not accept `?outputType "point"`, you may omit `?outputType`, but keep `?expr`.

Do not use `?outputType "expr"` until you have verified in this Cadence version that the output is actually saved in `active.state` as `outputsCommon/outputList`. A successful `maeAddOutput` call or the presence of `maeSetSpec` does not prove that the output appeared in the Maestro GUI.

Output expressions must reference only nodes/branches that are actually reachable from the imported Cadence top cell.

Derive paths from the current `tests/<group>.sp` and the actual Spectre deck created after `cdsTextTo5x`.

Mandatory rule for our HDL21/ngspice fixtures:

1. Find the fixture `.SUBCKT <fixture_name> ... .ENDS`.
2. Check whether there is a top-level instance after `.ENDS` of the form:

```spice
X<top_instance_name> <connections...> <fixture_name>
```

3. If such an instance exists, it is the active simulation top instance. All output paths to elements or nodes inside the fixture must include its name:

```lisp
<calculator_function>("/<top_instance_name>/<element_or_node_path>")
```

4. Do not use shortened paths such as:

```lisp
<calculator_function>("/<element_or_node_path>")
```

if these elements/nodes are inside the fixture `.SUBCKT`, not at the deck top level.

General selection rule:

```text
if the imported/generated Spectre deck contains a top-level XTB instance:
  output paths must include this XTB instance

if the imported Cadence cell is a wrapper/top subckt with a fixture instance:
  output paths must include this fixture instance

if fixture sources/nodes are truly at the deck top level:
  output paths may start directly from these sources/nodes
```

For currents through sources, use the branch path of the source that actually exists in the fixture. Do not hardcode a terminal suffix (`/PLUS`, `/MINUS`, or another suffix): add a suffix only if it is visible in the imported/generated design or required by the local ADE calculator for that branch.

For voltages, use a public or fixture-level node path that actually exists in the imported design.

When in doubt, open the generated/imported Spectre view or generated input netlist and choose the path based on the actual hierarchy. If `input.scs` only includes the imported `spectre.scs`, open the imported `spectre.scs` itself and check whether it contains an active top-level `X... <fixture_name>` instance after `.ENDS`. Do not invent a path from the group name.

## What Not To Do

Do not do the following:

```text
manually edit maestro.sdb, active.state, or similar Cadence state files
create a mock DUT for Cadence
use a schematic workaround unless requested by the user
run a full Spectre simulation unless requested by the user
create verify.il
create status files
create fake PASS status
```

## Resource

Main skeleton:

```text
assets/generate.il.template
```

Use it as the starting point. Modify placeholder sections and group-specific intent. Do not invent an alternative Cadence flow if the template fits.

If a method from the template is unavailable in the current Virtuoso version, find the closest public API equivalent and preserve the same architecture: Spectre text import, config, one Maestro test, `TB_*` variables, Maestro analyses/outputs/specs, PVT corners, native temperature, and model objects.

Minimum check after running the current group:

```text
generated_support/<group>.scs embeds tests/<group>.sp verbatim or line-for-line
one Maestro test exists
corner count matches expected matrix
Temperature is native corner temperature
corner Model Files contain only $LIB_PATH/<proc>.scs section <proc>
active.state contains outputsCommon/outputList entries for all expected outputs
cadence_dut.scs is included either by wrapper preferred path or definitionFiles fallback
mock_device.sp is absent from Cadence export/netlist
netlist-only input.scs contains cadence_dut.scs and imported fixture view
```

After generating the current group, stop. Do not create the next group in the same response.