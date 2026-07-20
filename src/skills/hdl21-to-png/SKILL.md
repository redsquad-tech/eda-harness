---
name: hdl21-to-png
description: Render HDL21 Python modules to schematic PNG images through ndt-sch-bridge's HDL21 to OA JSON conversion and SVG/PNG renderer. Use when the user asks for HDL21 to PNG, schematic image generation, rendered schematic preview, PNG output from HDL21, or hdl21-to-png.
---

# HDL21 To PNG

## Workflow

Use the file-only command:

```sh
hdl21-to-png --top path/to/design.py:Top --out-dir build/png --json-dir build/json --library scratch --pdk analogLib
```

The command first generates OA-style JSON, then renders the selected view to PNG.

## Inputs

- `--top`: HDL21 module spec, either `file.py:Symbol` or `file.py`.
- `--out-dir`: directory for PNG files.
- `--json-dir`: optional directory for intermediate JSON files.
- `--view`: view to render, usually `schematic` or `symbol`.
- `--scale`: render scale, default `2.0`.
- `--hierarchy-dir`: optional directory of cell JSONs for hierarchy expansion.
- `--library`, `--pdk`: same meaning as `hdl21-to-virtuoso`.

## Procedure

1. Check that `ndt-sch-bridge[full]` and `cairosvg` are installed.
2. Resolve the user's HDL21 top module path and symbol.
3. Run `hdl21-to-png`.
4. Report the PNG files and any intermediate JSON files.
5. If PNG conversion fails because CairoSVG is missing, install package dependencies with normal `pip install .` or `pip install ndt-sch-bridge[full]`.

## Resources

- Read `references/tooling.md` for command details and failure modes.
- Use `scripts/hdl21_to_png.py` when a deterministic wrapper is useful.
- Use `prompts/default.md` as the task prompt template for another agent.
