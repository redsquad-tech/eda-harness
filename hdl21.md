# HDL21 Component Standard

This document defines the mandatory repository standard for reusable HDL21 components.

## 1. Keywords

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.

## 2. Repository Structure

Each reusable component **MUST** have:

- one module file: `components/<component_name>.py`
- one registry entry in `components.csv`

Shared repository helpers **MUST** live in `components/__init__.py`.

Repository-local ngspice compatibility code **MUST**, when needed, live in `components/ngspice_netlister.py`.

Component-level verification code **MUST** live in the same module as the component generator.

A separate `tests/` package for component verification code **MUST NOT** be created by default.

## 3. Registry Contract

Each reusable component **MUST** be registered in `components.csv`.

Each registry entry **MUST** include:

- `name`
- `description`
- `parameters`

`name` **MUST** match the public component name used by the module and generator.

## 4. Public API Contract

Each component module **MUST** export:

- one DUT parameter class
- one DUT generator
- zero or more testbench parameter classes
- one or more `build_*_test(...)` functions
- one or more `run_*_test(...)` functions
- `run_all_tests(...)`
- `print_test_report(...)`
- `elaborate_dut(...)`
- `export_spice(...)`

A component module **MAY** export private or structural helpers, but those helpers **MUST** remain in the same module.

## 5. Naming

The public component name **MUST** be used consistently across:

- file name
- generator name
- registry entry

Naming conventions:

- DUT parameter classes **MUST** use `<ComponentName>Params`
- testbench parameter classes **MUST** use `<ComponentName><TestName>TbParams`

## 6. Specification-First Requirement

Implementation **MUST NOT** begin until a usable component specification has been provided.

If required specification data is missing, implementation **MUST** stop and return a missing-spec report.

Implementation **MUST NOT** guess missing requirements.

A usable specification **MUST** define:

- component name
- purpose
- component class: leaf, reusable block, or top-level composition
- full pin list and pin meaning
- DUT parameters: names, types, units, defaults, legal ranges
- implementation constraints
- required operating conditions
- required measurable behaviors
- numeric pass/fail criteria
- measurement conditions
- required process-corner coverage
- whether statistical verification is required

If Monte Carlo is required, the specification **MUST** also define:

- statistical variation scope
- measured metric
- required statistic
- acceptance criterion
- sample count, if not default

## 7. Generator Rules

A DUT generator:

- **MUST** be decorated with `@h.generator`
- **MUST** take exactly one DUT parameter-class argument
- **MUST** build the DUT only

A DUT generator **MUST NOT**:

- build testbenches
- run simulations
- perform file I/O
- use random behavior
- depend on mutable global state

For generators with loops, conditional topology, programmatic naming, or `setattr(...)`, DUT construction **SHOULD** use procedural assembly:

- `mod = h.Module(...)`
- explicit `mod.<port> = h.Port()` or `mod.<port_a>, mod.<port_b> = h.Ports(...)`
- explicit `setattr(mod, ...)` only on the constructed module object

Class-body `@h.module` construction **SHOULD** be limited to simple static leaf cells.

## 8. Parameter Rules

Generator inputs **MUST** use `@h.paramclass`.

DUT parameters and testbench parameters **MUST** be separate classes.

Stimulus values **MUST NOT** be placed in the DUT parameter class.

Physical values passed to devices, passives, or simulator sources **MUST** use `h.Scalar`.

Geometry-bearing parameters **MUST** include explicit units in both the specification and parameter descriptions.

Recommended naming:

- `w_*`, `l_*`, `nf_*`, `m_*`
- `r_*`, `c_*`, `i_*`, `v_*`
- `dev_*`
- `style`
- `use_*`

## 9. Module Rules

DUTs and testbenches **MUST** use `h.Module`.

For non-trivial generators, procedural `h.Module(...)` construction is the repository-default style.

`@h.module` class syntax **MAY** be used only for simple static modules without loops, conditional structure, or local alias variables that could be captured as HDL objects.

Analog or SPICE-style terminals **MUST** use `h.Port` or `h.Ports` unless directional intent is required.

`h.Input`, `h.Output`, and `h.Inout` **SHOULD** be used only when explicit direction is part of the interface contract.

## 10. Shared Helpers

Shared repository helpers **MUST** be imported from `components`.

Component modules **MUST NOT** import ngspice compatibility internals directly from `components/ngspice_netlister.py` unless repository maintenance requires it.

Manual SPICE execution fallbacks inside component public APIs **MUST NOT** be added.

Repository-standard metric reporting helpers **SHOULD** use:

- `flatten_metrics(...)`
- `format_metrics_table(...)`
- `print_metrics_table(...)`

## 11. Testbench Contract

Each simulation testbench **MUST** expose exactly one port:

- `VSS = h.Port()`

All other testbench nodes **MUST** be internal `Signal`s.

Simulation testbenches **MUST NOT** have zero ports or multiple ports.

The DUT ground terminal **MUST** connect to testbench `VSS`.

## 12. Verification Contract

Verification **MUST** be specification-driven.

Every measurable specification aspect **MUST** be covered by at least one test.

No claimed behavior **MAY** exist without a corresponding test.

Each component **MUST** define a verification plan that maps:

- specification aspect
- test name
- analysis type
- extracted metrics
- pass/fail rule
- required corners
- required operating-condition sweeps
- Monte Carlo requirement

Each test **MUST** define:

- test purpose
- stimulus and load conditions
- analysis type
- extracted metrics
- pass/fail rule
- corners used
- additional sweeps, if any

## 13. Test Structure

Component tests **MUST** use a two-layer structure:

- `build_*_test(...)` builds and returns a `Sim`
- `run_*_test(...)` executes that simulation

`run_all_tests(...)` **MUST** execute the full mandatory verification plan.

`run_all_tests(...)` **MUST** return machine-readable results.

`print_test_report(...)` **SHOULD** call `run_all_tests(...)`, print a table via shared helpers from `components`, and return the same results.

Each testbench **MUST** be built in its own builder function.

Simulation execution **MUST** be isolated to runner functions.

Assertions **SHOULD** live in normal Python test code or explicit result checks.

## 14. Required Test Layers

Each reusable component **MUST** include all applicable layers:

1. structural tests
2. nominal functional tests
3. full-corner specification tests
4. operating-range tests
5. statistical tests, when required

### 14.1 Structural Tests

Structural tests **MUST** verify at least:

- generator call with valid DUT params
- elaboration
- SPICE export
- exported subckt name validity and stability
- parameter rejection for invalid values, when ranges are specified

Structural tests **MAY** use nominal conditions only.

### 14.2 Nominal Functional Tests

Each component **MUST** include at least one nominal functional test for its primary intended behavior.

### 14.3 Full-Corner Specification Tests

Every measurable specification aspect **MUST** be tested across all required corners.

A test run only at a typical corner **MUST NOT** be treated as a specification test.

### 14.4 Operating-Range Tests

If the specification constrains any operating range, that range **MUST** be tested.

Applicable ranges include:

- supply voltage
- temperature
- input common-mode
- output load
- output swing
- bias current
- clock frequency, duty cycle, or non-overlap
- control mode or trim code

If a required range is missing from the specification, implementation **MUST** stop and report the missing item.

### 14.5 Statistical Tests

Monte Carlo tests **MUST** be added when required by the specification or by mismatch-sensitive component behavior.

Monte Carlo **MUST NOT** replace corner testing.

Corner testing **MUST NOT** replace Monte Carlo.

## 15. Corner Coverage

This repository **MUST** use one canonical SKY130 corner vocabulary.

For CMOS DUTs, the default required corner set **MUST** be:

- `TT`
- `FF`
- `SS`
- `SF`
- `FS`

A reduced corner set **MUST NOT** be used unless explicitly justified in the component documentation.

If a specification claim depends on supply or temperature, required corner coverage **MUST** be combined with the required supply and temperature sweeps unless a reduced matrix is explicitly justified.

Generic aliases such as `TYP` **MUST NOT** be mixed with repository-standard corner names in public verification APIs.

## 16. Monte Carlo Policy

Monte Carlo **MUST** be used when the specification includes:

- offset requirements
- mismatch-sensitive accuracy requirements
- ratio accuracy requirements
- balance requirements
- yield, sigma, percentile, or distribution constraints
- trim effectiveness or residual error requirements
- mismatch-dominated bias or reference accuracy requirements

Monte Carlo is typically justified for:

- differential pair offset
- current mirror ratio accuracy
- resistor or capacitor ratio accuracy
- reference and bias generators
- comparator trip point
- startup yield
- common-mode accuracy
- residual offset in auto-zero, chopped, or trimmed circuits

If Monte Carlo is required, the test **MUST** define:

- varied quantities
- measured metric
- result summary method
- pass/fail criterion

If the specification implies Monte Carlo but does not define the statistical acceptance criterion, implementation **MUST** stop and report the missing requirement.

## 17. Analysis Selection

The simplest analysis that directly tests the claim **SHOULD** be used.

Recommended mapping:

- `Op` or `Dc` for operating point, bias, ratio, compliance
- `Dc` sweep for transfer curves, headroom, common-mode range
- `Ac` for gain, bandwidth, phase margin, impedance
- `Tran` for startup, settling, switching, sampled, or clocked behavior
- `Noise` for noise metrics
- `MonteCarlo` for yield or mismatch-sensitive metrics

## 18. Simulation Environment

If a DUT requires PDK model includes or libraries, the test builder **MUST** add them.

Component modules **MUST NOT** auto-initialize the PDK.

If `sky130_hdl21.install` is missing, component code **MUST** fail fast via `require_sky130_install()`.

All simulation artifacts **MUST** be written under `tmp/`.

Component simulations **MUST NOT** run in the repository root or in ad hoc scratch directories.

After implementation, component tests **MUST** be executed.

Test results **MUST** be printed or returned in a machine-readable form.

When printed for human review, component test results **SHOULD** use the shared table formatter from `components`.

Recommended manual entrypoint:

- `print_test_report(...)` for human-readable console output
- `run_all_tests(...)` for programmatic consumption

## 19. Export Rules

`export_spice(...)` **MUST** export the DUT only.

`export_spice(...)` **MUST** use the same DUT generator and DUT parameter class used by tests.

DUT export **MUST** use the repository-standard elaboration pattern.

SPICE export **MUST** use `h.netlist(..., fmt="spice")`.

## 20. SKY130 Rules

This repository targets SKY130.

Leaf-level generators **MUST** instantiate SKY130 devices or passives directly unless a documented abstraction layer is required.

Higher-level generators **MAY** compose registered local components from `components/`.

Unregistered reusable local components **MUST NOT** be used as dependencies.

The repository PDK root **MUST** be `./pdks/sky130A`.

The execution environment **MUST** initialize `sky130_hdl21.install` before simulations run.

Generic HDL21 primitives **MAY** be used only when their mapping to SKY130 is intentional and unambiguous.

## 21. Public Function Signatures

Each component module **SHOULD** expose this shape:

```python
def build_<test_name>_test(
    dut_params: <ComponentName>Params,
    tb_params: <ComponentName><TestName>TbParams | None = None,
    *,
    corner,
) -> Sim:
    ...


def run_<test_name>_test(
    dut_params: <ComponentName>Params | None = None,
    tb_params: <ComponentName><TestName>TbParams | None = None,
    *,
    corner,
    sim_options=None,
):
    ...


def run_<test_name>_all_corners(
    dut_params: <ComponentName>Params | None = None,
    tb_params: <ComponentName><TestName>TbParams | None = None,
    *,
    sim_options=None,
):
    ...


def run_all_tests(
    dut_params: <ComponentName>Params | None = None,
    *,
    sim_options=None,
):
    ...


def print_test_report(
    dut_params: <ComponentName>Params | None = None,
    *,
    sim_options=None,
):
    ...
````

## 22. Elaboration Rule

Repository code **MUST** use one elaboration pattern consistently.

The elaboration contract **MUST** match the installed HDL21 version.

Repository documentation **MUST NOT** claim an elaboration return convention that has not been verified against the installed version.

## 23. Canonical Generator Pattern

Repository examples for reusable generators **SHOULD** use this procedural pattern:

```python
@h.generator
def <component_name>(params: <ComponentName>Params) -> h.Module:
    mod = h.Module(name="<ComponentName>")
    mod.A, mod.B, mod.VDD, mod.VSS = h.Ports(4)
    mod.internal = h.Signal(name="internal")

    mod.stage0 = some_primitive(...)(p=mod.A, n=mod.internal)
    mod.stage1 = some_primitive(...)(p=mod.internal, n=mod.B)

    return mod
```

When body ties or optional nodes are needed, repository code **SHOULD** select them outside class bodies and connect them directly from `mod`, for example:

```python
body_node = mod.VSS if params.body_tie == "vss" else mod.TAIL
mod.m0 = nmos(...)(d=mod.OUT, g=mod.IN, s=mod.SRC, b=body_node)
```

This avoids class-body capture issues that have repeatedly caused invalid HDL21 modules.
