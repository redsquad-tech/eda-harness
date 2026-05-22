---
name: openaccess-to-hdl21
description: Convert OpenAccess-style schematic JSON directories into HDL21 Python source using the file-only ndt-sch-bridge reverse tool. Use when the user asks for OA JSON to HDL21, OpenAccess to HDL21, Virtuoso JSON export to HDL21, or running virtuoso-to-hdl21 without Cadence.
---

# OpenAccess To HDL21

## Workflow

Use the file-only command:

```sh
virtuoso-to-hdl21 --in-dir build/oa-json --out generated/design.py --top Top --pdk analogLib
```

This reads JSON files from disk. It does not connect to Cadence or load SKILL.

## Inputs

- `--in-dir`: directory containing one or more OA-style schematic JSON files.
- `--out`: HDL21 Python output path.
- `--top`: optional top cell name; omit only when a clear top can be auto-detected.
- `--pdk`: PDK map name, default `analogLib`.

## Procedure

1. Confirm `--in-dir` exists and contains `*.json`.
2. Ask for or infer `--top` if multiple cells exist.
3. Run `virtuoso-to-hdl21`.
4. Report the generated `.py` and sibling `.json` files.
5. If a master cannot be mapped, inspect the PDK map and suggest the closest supported `--pdk`.

## Resources

- Read `references/tooling.md` for command details and failure modes.
- Use `scripts/openaccess_to_hdl21.py` when a deterministic wrapper is useful.
- Use `prompts/default.md` as the task prompt template for another agent.
