Use $openaccess-to-hdl21.

Task: convert OpenAccess-style schematic JSON under `{in_dir}` to HDL21 source.

Constraints:
- Do not require Cadence or SKILL.
- Use `virtuoso-to-hdl21`.
- Write HDL21 source to `{out}`.
- Use top `{top}` and PDK `{pdk}` unless the user overrides them.
- Report generated file paths and any command failure.
