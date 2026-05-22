# HDL21 To PNG Tooling

## Command

```sh
hdl21-to-png --top DESIGN.py:Top --out-dir PNG_DIR --json-dir JSON_DIR --library scratch --pdk analogLib
```

## Expected Output

- `PNG_DIR/<cell>.schematic.png` by default.
- Optional `JSON_DIR/<cell>.json` when `--json-dir` is supplied.

## Dependencies

- `ndt-sch-bridge`
- `hdl21`
- `spice-to-schematic`
- `cairosvg`

Use `pip install "ndt-sch-bridge[full]"`. CairoSVG is a normal package dependency for PNG rendering.

## Options

- `--view schematic`: render schematic view.
- `--view symbol`: render symbol view.
- `--scale 2.0`: adjust PNG size.
- `--hierarchy-dir DIR`: load additional cell JSONs for expanded hierarchy rendering.

## Common Failures

- `cairosvg is required for PNG output`: install package dependencies normally instead of `--no-deps`.
- `schematic_svg renderer not found`: install `spice-to-schematic` or run from the monorepo with `../core/src`.
- `no 'schematic' views rendered`: use `--view symbol` or inspect the JSON view names.
