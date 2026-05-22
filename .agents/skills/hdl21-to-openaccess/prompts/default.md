Use $hdl21-to-openaccess.

Task: convert the HDL21 module at `{top}` to OpenAccess-style schematic JSON.

Constraints:
- Do not require Cadence or SKILL.
- Use `hdl21-to-virtuoso`.
- Write JSON output under `{out_dir}`.
- Use library `{library}` and PDK `{pdk}` unless the user overrides them.
- Report generated file paths and any command failure.
