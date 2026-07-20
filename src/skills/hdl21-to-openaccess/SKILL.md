---
name: hdl21-to-openaccess
description: Convert HDL21 Python modules into OpenAccess-style schematic JSON files using the file-only ndt-sch-bridge toolchain. Use when the user asks for HDL21 to OA JSON, HDL21 to OpenAccess, HDL21 to Virtuoso-compatible JSON, schematic JSON generation, or the hdl21-to-virtuoso command without requiring Cadence.
---

# HDL21 To OpenAccess

## Workflow

Use the file-only command:

```sh
hdl21-to-virtuoso --top path/to/design.py:Top --out-dir build/oa-json --library scratch --pdk analogLib
```

Despite the command name, it writes OA-style JSON files and does not contact Virtuoso.

## Inputs

- `--top`: HDL21 module spec, either `file.py:Symbol` or `file.py`.
- `--out-dir`: directory for generated JSON files.
- `--library`: target OA library name stored in JSON, default `scratch`.
- `--pdk`: PDK map name, default `analogLib`.

## Procedure

1. Check that `ndt-sch-bridge[full]` is installed when conversion is expected to run.
2. Resolve the user's HDL21 top module path and symbol.
3. Run `hdl21-to-virtuoso`.
4. Inspect generated files and report their paths.
5. If conversion fails because `spice_to_schematic` is missing, tell the user to install `ndt-sch-bridge[full]`.

## Resources

- Read `references/tooling.md` for command details and failure modes.
- Use `scripts/hdl21_to_openaccess.py` when a deterministic wrapper is useful.
- Use `prompts/default.md` as the task prompt template for another agent.
