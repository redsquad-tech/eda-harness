# SPICE to xschem converter

Generator that converts SPICE netlists to xschem schematic (.sch) and symbol (.sym) files for Sky130 PDK.

## Installation

```bash
pip install -e .
```

## Usage

```bash
python -m spice2xschem input.sp -o output/
```

Validation through xschem CLI:

```bash
python -m spice2xschem.validate output/
```

Options:
- `-o, --output` - Output directory (default: current directory)
- `-l, --local` - Local symbol search directory (default: current directory)

## Features

### Parsing
- `.subckt` / `.ends` blocks
- Instance declarations (`x*`)
- `.include` directives
- `*.PININFO` for pin directions (I=input, O=output, B=inout)

### Symbol Resolution (in priority order)
1. Local `.subckt` from input file
2. Sky130 PDK symbols (via `SKY130_PDK_PATH`)
3. Current project directory
4. Directory adjacent to `.include` files
5. Fallback: generate default square symbol

### Layout
- Grid-based auto-placement
- Input pins: left side, top
- Output pins: right side, bottom
- Power: top, Ground: bottom
- Orthogonal routing (Manhattan)
- Label-based fallback for complex nets

### Output
For each `.subckt` in input:
- `<name>.sch` - schematic with placed instances
- `<name>.sym` - hierarchical symbol

For unresolved external components:
- `<cell>.sym` - default square symbol (no .sch)

## Validation Notes

- The validator checks that xschem can open every generated `.sch` / `.sym`
- It also scans xschem debug logs for unresolved symbol loading issues
- In this environment `xschem 2.8.1` crashes in CLI netlisting mode (`-x -n`) even on bundled example schematics, so netlisting is not used as a validation criterion

## Example

```bash
python -m spice2xschem test.spice -o output/
```

## Environment

- `SKY130_PDK_PATH` - Path to Sky130 PDK (default: `/usr/local/share/pdk/sky130A`)

## File Format

Generated files follow xschem format v1.2:
- `v {xschem version=3.4.4 file_version=1.2}`
- `G {} K {} V {} S {} E {}`
- Pin declarations: `P {n <name> <direction> <x1> <y1> <x2> <y2> <name>}`
- Instances: `I {n <inst_name> <x> <y> <rotation> <mirror> <symbol>}`
- Wires: `W {n <net_name> <x1> <y1> <x2> <y2>}`
