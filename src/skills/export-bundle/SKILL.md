---
name: export-bundle
description: Export one circuit device and its testbenches, documentation, metrics, and declared dependencies into a portable tar.gz archive for review or reuse.
---

# Export Bundle

Create one self-contained archive for one device at a time. Work inside the user's task workspace and preserve the public DUT interface.

## Bundle layout

```text
<device-name>/
  README.md
  device.sp
  testbenches/
    <group>.sp
  metrics.md
  dependencies/
  manifest.json
```

Include only dependencies required to interpret or simulate the exported files and whose redistribution is permitted. Do not include PDK installations, credentials, raw tool caches, unrelated results, or proprietary model files without explicit authorization.

## Workflow

1. Identify the device, its public pins, its source netlist or HDL21 top level, completed testbench netlists, and result metrics.
2. Prefer an existing authoritative device netlist. If the source is HDL21, elaborate it and export SPICE with `hdl21.netlist(..., fmt="spice")`.
3. Apply a project-provided PDK compilation adapter only when the project already defines one. Do not assume a particular PDK or invent project-specific preparation helpers.
4. Copy the completed testbench `.sp` files without changing their DUT interface. Document model-file requirements instead of bundling restricted PDK content.
5. Create `metrics.md` from the existing result artifacts. Preserve PVT and Monte Carlo context; do not recompute physical metrics or pass/fail during packaging.
6. Write `README.md` with the device description, pinout, simulator requirements, model dependencies, and example commands.
7. Write `manifest.json` listing every bundled file, its SHA-256 digest, the source revision when available, and any omitted external dependencies.
8. Create `<device-name>_bundle.tar.gz` with relative paths rooted at `<device-name>/`. Inspect the archive listing and verify every recorded checksum before returning it.

Generate temporary staging content inside the task workspace and remove it after the archive is verified. Never follow symlinks outside the workspace.
