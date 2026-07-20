Use $hdl21-to-png.

Task: render the HDL21 module at `{top}` as a schematic PNG.

Constraints:
- Do not require Cadence or SKILL.
- Use `hdl21-to-png`.
- Write PNG output under `{out_dir}`.
- Write intermediate JSON under `{json_dir}` only if requested.
- Use view `{view}`, library `{library}`, and PDK `{pdk}` unless the user overrides them.
- Report generated file paths and any command failure.
