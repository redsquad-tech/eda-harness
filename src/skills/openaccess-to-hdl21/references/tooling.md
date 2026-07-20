# OpenAccess To HDL21 Tooling

## Command

```sh
virtuoso-to-hdl21 --in-dir OA_JSON_DIR --out generated/design.py --top Top --pdk analogLib
```

## Expected Output

- `generated/design.py`: HDL21 source.
- `generated/design.json`: sidecar copy of the source OA-style JSON bundle.

## Dependencies

- `ndt-sch-bridge`
- `hdl21`

## Notes

- The input is a directory of JSON files, not a live OA database.
- `--top` is optional only when a single unreferenced root cell can be detected.
- Use `--pdk analogLib` unless the JSON uses a specific supported PDK map.

## Common Failures

- `no schematic JSON files found`: wrong `--in-dir` or files are not `*.json`.
- `--top ... not present`: choose a cell name listed in the error output.
- Reverse conversion failure: inspect masters in JSON and choose a PDK map that knows them.
