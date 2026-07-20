# HDL21 To OpenAccess Tooling

## Command

```sh
hdl21-to-virtuoso --top DESIGN.py:Top --out-dir OUT_DIR --library scratch --pdk analogLib
```

## Expected Output

One or more `*.json` files in `OUT_DIR`. Each file is OA-style schematic JSON with `cellName`, `libName`, and `views`.

## Dependencies

- `ndt-sch-bridge`
- `hdl21`
- `spice-to-schematic`

Use `pip install "ndt-sch-bridge[full]"` for normal installation.

## Notes

- The command name is compatibility-only. It does not start Virtuoso.
- The conversion path is HDL21 -> SPICE -> schematic JSON.
- Use `--pdk analogLib` unless the user explicitly needs a registered PDK map.
- If `file.py` contains several HDL21 modules, prefer `file.py:Symbol` for deterministic output.

## Common Failures

- `spice_to_schematic not installed`: install the `full` extra.
- `file not found`: resolve the top path relative to the user's working directory.
- Generator requires parameters: instantiate the generator in the HDL21 file and point `--top` at the resulting module.
