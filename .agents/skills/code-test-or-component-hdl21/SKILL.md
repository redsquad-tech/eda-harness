---
name: code-test-or-component-hdl21
description: Use this skill when you need to describe a circuit or a test in hdl21. Before run this skill you should describe the circuit or test in natural language (have a clear PRD). This skill will convert this description into hdl21 code.
---

# HDL21 Component Standard

This document defines the mandatory repository standard for reusable HDL21 components and opamp-architecture workspaces.

## 0. Mandatory Line Selection (Before Any Coding)

For any user request `create/update/modify device`, the agent **MUST** do line selection first and only once for the session:

1. Identify target `device_name`.
2. Discover existing lines and versions:
   - `python ../version-device/scripts/list_device_versions.py --device <device_name>`
   - In the user-facing message, explicitly include:
     - available line branches,
     - available freeze tags,
     - available release tags,
     - promoted/not-promoted status from `VERSION_INDEX.json` (if present).
   - Treat script JSON output as source of truth. Do not infer or override its `version_index` / `version_index_source` fields.
   - If `version_index` is present, agent MUST NOT say "VERSION_INDEX.json not found".
3. Ask user to choose one mode:
   - create new line `device/<device>/<line>` from base (`main` or explicit freeze tag), or
   - continue existing line.
   - For `create new line`, always ask user for explicit `<base_ref>`; do not assume defaults silently.
4. If discovery returns no lines/versions:
   - explicitly state that no prior versions exist,
   - suggest `new line mainline from main`,
   - still ask user to confirm explicit base-ref.
5. Create/switch branch:
   - `python ../version-device/scripts/start_device_line.py --device <device_name> --line <line_name> --base-ref <base_ref>`
6. Only after branch is selected, start implementation/tests.

The agent **MUST NOT** start coding before this line-selection gate is resolved.

## 0.1 Create/Update Completion Gate (Mandatory)

Before reporting create/update as successful, agent **MUST** run characterization contract check:

```bash
python ../characterize-device/scripts/characterize_device.py \
  --device <device_name> \
  --description "creation characterization contract check" \
  --validate-only
```

And **MUST** run corner-sensitivity precheck (no artifacts):

```bash
python ../characterize-device/scripts/characterize_device.py \
  --device <device_name> \
  --description "creation corner-sensitivity precheck" \
  --no-csv \
  --no-tag \
  --no-commit \
  --corners TT,FF,SS,FS,SF
```

Rules:

- this is a hard gate for create/update completion
- if either command fails, task is not complete
- agent must not claim success until the gate passes
- for new devices, create `devices/<device>/characterization_spec.json` with device-relevant target metrics for characterization CSV pass/fail columns
- full characterization CSV/tag run is not part of create/update unless user explicitly requested characterization
- run these gate commands using `python` from active project venv
- during create/update, any direct call to `characterize_device.py` must be either:
  - `--validate-only`, or
  - `--no-csv` (for corner-sensitivity precheck)
- running `characterize_device.py` in create/update without `--validate-only` and without `--no-csv` is not allowed
- `--no-tag` and `--no-commit` are allowed in this section only for the mandatory no-artifact precheck command above

## 1. Repository Structure

- common patterns and subblocks (hdl21 library, e.g. diffpair, current mirror, etc.) SHOULD live in: `components/<component_name>.py`
- your devices SHOULD live in: `devices/<device_name>/`, this is wd for your devices
- `devices/<device_name>/tests` **MUST** contain: hdl21 budget test, hdl21 specification corner tests, PVT sweep tests, and Monte Carlo tests when required by the specification
- Shared repository helpers lives in `components/__init__.py`, use them when need initialize sky130 pdk, ngspice integration.
- When you need to create a netlist from hdl21 instance, use `components/ngspice_netlister.py`.

Repository-standard metric reporting helpers:

- `flatten_metrics(...)`
- `format_metrics_table(...)`
- `print_metrics_table(...)`

## 2. Public API Contract

We use TDD process. Each component **MUST** export:

- one DUT parameter class (`<ComponentName>Params`) snd DUT generator function (`<component_name>(...)`) in the `<ComponentName>.py` module
- zero or more testbench parameter classes, keep test suites files decomposed by test purpose (budget, spec, dev tests go in separate files)

## 3. Specification-First Requirement

We use TDD process. Implementation **MUST NOT** begin until a usable component specification has been provided.

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

After specification is provided, tests **MUST** be implemented to cover all specified requirements. Do not repeat tests, check existing ones. Edit existing tests as needed. Implementation MUST NOT start until the full verification plan is defined.

## 4. Generator Rules

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

## 5. Parameter Rules

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

## 6. Module Rules

DUTs and testbenches **MUST** use `h.Module`.

For non-trivial generators, procedural `h.Module(...)` construction is the repository-default style.

`@h.module` class syntax **MAY** be used only for simple static modules without loops, conditional structure, or local alias variables that could be captured as HDL objects.

Analog or SPICE-style terminals **MUST** use `h.Port` or `h.Ports` unless directional intent is required.

`h.Input`, `h.Output`, and `h.Inout` **SHOULD** be used only when explicit direction is part of the interface contract.

## 7. Testbench Contract

Each simulation testbench **MUST** expose exactly one port:

- `VSS = h.Port()`

All other testbench nodes **MUST** be internal `Signal`s.

Simulation testbenches **MUST NOT** have zero ports or multiple ports.

The DUT ground terminal **MUST** connect to testbench `VSS`.

DUT MUST use PDK components, ideal devices **MUST NOT** be used in DUT. Testbenches SHOULD use ideal devices.

## 8. Corner Coverage

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

## 9. Monte Carlo Policy

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

## 10. Analysis Selection

The simplest analysis that directly tests the claim **SHOULD** be used.

Recommended mapping:

- `Op` or `Dc` for operating point, bias, ratio, compliance
- `Dc` sweep for transfer curves, headroom, common-mode range
- `Ac` for gain, bandwidth, phase margin, impedance
- `Tran` for startup, settling, switching, sampled, or clocked behavior
- `Noise` for noise metrics
- `MonteCarlo` for yield or mismatch-sensitive metrics

## 11. Simulation Environment

If a DUT requires PDK model includes or libraries, the test builder **MUST** add them.

Component modules **MUST NOT** auto-initialize the PDK.

If `sky130_hdl21.install` is missing, component code **MUST** fail fast via `require_sky130_install()`.

All simulation artifacts **MUST** be written under `tmp/`.

Component simulations **MUST NOT** run in the repository root or in ad hoc scratch directories.

## 12. Export Rules

`export_spice(...)` **MUST** export the DUT only.

`export_spice(...)` **MUST** use the same DUT generator and DUT parameter class used by tests.

DUT export **MUST** use the repository-standard elaboration pattern.

SPICE export **MUST** use `h.netlist(..., fmt="spice")`.

## 13. SKY130 Rules

This repository targets SKY130.

Leaf-level generators **MUST** instantiate SKY130 devices or passives directly unless a documented abstraction layer is required.

Higher-level generators inside `opamp/<amp_arch_name>/` **MAY** compose low-level registered components from `components/`.

Higher-level generators inside `opamp/<amp_arch_name>/` **SHOULD** prefer local imports from the same architecture workspace for all opamp-specific blocks.

Unregistered reusable local components **MUST NOT** be used as dependencies.

The repository PDK root **MUST** be `./pdks/sky130A`.

The execution environment **MUST** initialize `sky130_hdl21.install` before simulations run.

Generic HDL21 primitives **MAY** be used only when their mapping to SKY130 is intentional and unambiguous.

## 14. Canonical Generator Pattern

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
