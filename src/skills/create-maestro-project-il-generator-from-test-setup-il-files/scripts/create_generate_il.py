#!/usr/bin/env python3
"""Assemble a portable suite-level Cadence bundle from validated group fragments."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tomllib
from pathlib import Path


GROUP_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
META_RE = re.compile(r"^; EDA_HARNESS_(GROUP|TESTS|OUTPUTS|CORNERS|ANALYSIS):\s*(\S+)\s*$", re.M)
FORBIDDEN_FRAGMENT = (
    "dcOp",
    "ddDeleteObj",
    "maeOpenSetup",
    "maeSaveSetup",
    "exit(",
    "system(",
    "vs55",
    "chmod",
    "chown",
    "setfacl",
    "sudo",
    "{{",
    "}}",
)


def relative_file(root: Path, raw: object, field: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{field} must be a non-empty relative path")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{field} must remain inside the workspace: {raw}")
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{field} escapes the workspace: {raw}") from exc
    if not path.is_file():
        raise ValueError(f"missing {field}: {raw}")
    return path


def manifest_groups(root: Path, selected: set[str]) -> list[tuple[str, Path, bool]]:
    manifest_path = root / "tests" / "testbench_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid testbench manifest: {exc}") from exc
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("groups"), list):
        raise ValueError("testbench manifest schema_version must be 1 with a groups array")
    result: list[tuple[str, int, Path, bool]] = []
    manifest_names: list[str] = []
    for item in manifest["groups"]:
        if not isinstance(item, dict):
            raise ValueError("manifest group must be an object")
        name = item.get("name")
        order = item.get("order")
        if not isinstance(name, str) or not GROUP_RE.fullmatch(name):
            raise ValueError(f"invalid group name: {name!r}")
        manifest_names.append(name)
        if not isinstance(order, int) or order < 1:
            raise ValueError(f"invalid order for group {name}")
        if name not in selected:
            continue
        fixture = relative_file(root, item.get("fixture"), f"{name}.fixture")
        canonical = item.get("canonical_inputs", [])
        if not isinstance(canonical, list) or not all(isinstance(path, str) for path in canonical):
            raise ValueError(f"{name}.canonical_inputs must be an array of relative paths")
        for index, path in enumerate(canonical):
            relative_file(root, path, f"{name}.canonical_inputs[{index}]")
        if canonical:
            relative_file(root, item.get("materializer"), f"{name}.materializer")
            dependencies = item.get("generated_dependencies")
            if not isinstance(dependencies, list) or not dependencies:
                raise ValueError(f"{name}.generated_dependencies must be non-empty")
            for index, path in enumerate(dependencies):
                relative_file(root, path, f"{name}.generated_dependencies[{index}]")
        result.append((name, order, fixture, bool(canonical)))
    if len(set(manifest_names)) != len(manifest_names):
        raise ValueError("duplicate manifest group name")
    missing = selected - set(manifest_names)
    if missing:
        raise ValueError(f"Maestro fragments are absent from the manifest: {sorted(missing)}")
    return [(name, fixture, file_stimulus) for name, _, fixture, file_stimulus in sorted(result, key=lambda row: row[1])]


def model_files(config: Path) -> list[str]:
    try:
        data = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid model bindings: {exc}") from exc
    if data.get("version") != 1:
        raise ValueError("model_bindings.toml version must be 1")
    common = data.get("common", {})
    corners = data.get("corners", {})
    if not isinstance(common, dict) or not isinstance(corners, dict):
        raise ValueError("model bindings common and corners must be tables")
    entries: list[object] = list(common.get("models", []))
    for corner, value in corners.items():
        if not isinstance(corner, str) or not isinstance(value, dict):
            raise ValueError("invalid corner table")
        corner_models = value.get("models")
        if not isinstance(corner_models, list) or not corner_models:
            raise ValueError(f"corner {corner} must declare at least one model")
        entries.extend(corner_models)
    paths: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) - {"file", "section"}:
            raise ValueError(f"invalid model entry {index}")
        raw = entry.get("file")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"model entry {index}.file must be non-empty")
        path = Path(raw)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"model path must be relative to PDK_PATH: {raw}")
        section = entry.get("section")
        if section is not None and (not isinstance(section, str) or not section.strip()):
            raise ValueError(f"model entry {index}.section must be non-empty when present")
        paths.append(path.as_posix())
    return sorted(set(paths))


def group_fragment(path: Path, group: str) -> str:
    if not path.is_file():
        raise ValueError(f"missing Maestro group fragment: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    metadata = dict(META_RE.findall(text))
    if metadata.get("GROUP") != group or metadata.get("TESTS") != "1":
        raise ValueError(f"invalid group metadata in {path}")
    if metadata.get("ANALYSIS") not in {"dc", "tran", "ac"}:
        raise ValueError(f"unsupported analysis in {path}")
    for field in ("OUTPUTS", "CORNERS"):
        value = metadata.get(field, "")
        if not value.isdigit() or int(value) < 1:
            raise ValueError(f"invalid {field} metadata in {path}")
    for needle in FORBIDDEN_FRAGMENT:
        if needle in text:
            raise ValueError(f"forbidden {needle!r} in {path}")
    for required in ("maeCreateTest", "ehSetAnalysis", "ehAddOutput", "ehSetSpec"):
        if required not in text:
            raise ValueError(f"missing {required} in {path}")
    return text.strip()


def skill_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def group_block(group: str, fragment: str) -> str:
    indented = "\n".join("    " + line for line in fragment.splitlines())
    return f'''  let((spectreView configView testName wrapperPath cfg status)
    spectreView = {skill_string(f"spectre_{group}")}
    configView = {skill_string(f"config_{group}")}
    testName = {skill_string(group)}
    wrapperPath = strcat(exportDir {skill_string(f"/generated_support/{group}.scs")})

    when(ddGetObj(lib suiteCell spectreView)
      ddDeleteObj(ddGetObj(lib suiteCell spectreView))
    )
    status = system(strcat(
      cdsText " -CDSLIB cds.lib -LIB " lib " -CELL " suiteCell
      " -VIEW " spectreView " -LANG spectre \\"" wrapperPath "\\""
    ))
    ehAssert(status == 0 {skill_string(f"cdsTextTo5x failed for {group}")})

    when(ddGetObj(lib suiteCell configView)
      ddDeleteObj(ddGetObj(lib suiteCell configView))
    )
    cfg = hdbOpen(lib suiteCell configView "w" "CDBA")
    ehAssert(cfg {skill_string(f"failed to open config view for {group}")})
    hdbSetTopCellViewName(cfg lib suiteCell spectreView)
    hdbSetDefaultViewListString(cfg strcat(spectreView " spectre schematic veriloga ahdl"))
    hdbSetDefaultStopListString(cfg strcat(spectreView " spectre"))
    hdbSave(cfg)
    hdbClose(cfg)

{indented}
    actualTests = actualTests + 1
    validatedAnalyses = validatedAnalyses + 1
    validatedOutputs = validatedOutputs + 1
    validatedCorners = validatedCorners + 1
  )'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Create one portable Cadence suite bundle.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--dut", required=True, help="Original Spectre DUT netlist")
    parser.add_argument("--suite-cell", required=True)
    args = parser.parse_args()

    root = Path(args.workspace).resolve()
    dut = Path(args.dut).resolve()
    if not dut.is_file():
        raise SystemExit(f"missing original Spectre DUT: {dut}")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.suite_cell):
        raise SystemExit("suite-cell must be a valid Cadence cell name")

    export = root / "cadence_export"
    setup = export / "maestro_setup"
    support = export / "generated_support"
    config = export / "model_bindings.toml"
    actual_fragments = {path.stem for path in setup.glob("*.il")}
    if not actual_fragments:
        raise SystemExit("no validated Maestro group fragments found")
    try:
        groups = manifest_groups(root, actual_fragments)
        models = model_files(config)
        fragments = {name: group_fragment(setup / f"{name}.il", name) for name, _, _ in groups}
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    expected_fragments = {name for name, _, _ in groups}
    if actual_fragments != expected_fragments:
        raise SystemExit(
            f"Maestro fragment set mismatch: expected={sorted(expected_fragments)}, "
            f"actual={sorted(actual_fragments)}"
        )

    support.mkdir(parents=True, exist_ok=True)
    dut_text = dut.read_text(encoding="utf-8", errors="replace").rstrip()
    if "simulator lang=" not in dut_text:
        dut_text = "simulator lang=spectre\n" + dut_text
    (support / "cadence_dut.scs").write_text(dut_text + "\n", encoding="utf-8")

    blocks: list[str] = []
    file_groups = [name for name, _, file_stimulus in groups if file_stimulus]
    if file_groups:
        materializer = export / "materialize_stimuli.py"
        if not materializer.is_file():
            raise SystemExit(f"missing Cadence stimulus materializer: {materializer}")
        for name in file_groups:
            template = support / f"{name}_source.scs.in"
            stimulus_dir = support / "stimuli" / name
            if not template.is_file():
                raise SystemExit(f"missing Spectre stimulus template: {template}")
            if "__EDA_HARNESS_STIMULUS_DIR__" not in template.read_text(encoding="utf-8"):
                raise SystemExit(f"missing portable stimulus token in {template}")
            if not stimulus_dir.is_dir() or not any(
                path.is_file() and path.stat().st_size > 0 for path in stimulus_dir.glob("*.pwl")
            ):
                raise SystemExit(f"missing Spectre PWL stimuli for {name}: {stimulus_dir}")
            (support / f"{name}_source.scs").unlink(missing_ok=True)

    for name, fixture, file_stimulus in groups:
        fixture_text = fixture.read_text(encoding="utf-8", errors="replace").rstrip()
        if not re.search(rf"(?im)^\s*\.subckt\s+{re.escape(args.suite_cell)}(?:\s|$)", fixture_text):
            raise SystemExit(f"fixture {fixture} does not define .SUBCKT {args.suite_cell}")
        includes = 'simulator lang=spectre\ninclude "cadence_dut.scs"\n'
        if file_stimulus:
            includes += f'include "{name}_source.scs"\n'
        wrapper = includes + "simulator lang=spice\n" + fixture_text + "\nsimulator lang=spectre\n"
        (support / f"{name}.scs").write_text(wrapper, encoding="utf-8")
        blocks.append(group_block(name, fragments[name]))

    assets = Path(__file__).resolve().parent.parent / "assets"
    for name in ("eda_harness_api.il", "verify_export.py"):
        shutil.copyfile(assets / name, export / name)
    generate = (assets / "generate.il.template").read_text(encoding="utf-8")
    generate = generate.replace("{{SUITE_CELL}}", args.suite_cell)
    generate = generate.replace("{{EXPECTED_TEST_COUNT}}", str(len(groups)))
    generate = generate.replace("{{GROUP_BLOCKS}}", "\n\n".join(blocks))
    if "{{" in generate or "}}" in generate:
        raise SystemExit("unresolved generate.il placeholder")
    (export / "generate.il").write_text(generate, encoding="utf-8")

    checks = [
        '\t@test -r "$(EXPORT_DIR)/generated_support/cadence_dut.scs" || { echo "missing Cadence DUT deck" >&2; exit 2; }'
    ]
    checks.extend(
        f'\t@test -r "$(EXPORT_DIR)/generated_support/{name}.scs" || {{ echo "missing support deck for {name}" >&2; exit 2; }}'
        for name, _, _ in groups
    )
    if file_groups:
        checks.append(
            '\t@test -r "$(EXPORT_DIR)/materialize_stimuli.py" || { echo "missing Cadence stimulus materializer" >&2; exit 2; }'
        )
        for name in file_groups:
            checks.extend(
                [
                    f'\t@test -r "$(EXPORT_DIR)/generated_support/{name}_source.scs.in" || {{ echo "missing Spectre stimulus template for {name}" >&2; exit 2; }}',
                    f'\t@test -n "$$(find "$(EXPORT_DIR)/generated_support/stimuli/{name}" -type f -name "*.pwl" -size +0c -print -quit 2>/dev/null)" || {{ echo "missing Spectre PWL stimuli for {name}" >&2; exit 2; }}',
                ]
            )
    checks.extend(
        f'\t@test -r "$(PDK_PATH)/{model}" || {{ echo "missing PDK model: {model}" >&2; exit 2; }}'
        for model in models
    )
    makefile = (assets / "Makefile.template").read_text(encoding="utf-8")
    makefile = makefile.replace("{{INPUT_AND_MODEL_CHECKS}}", "\n".join(checks))
    materialize = ""
    materialized_checks = ""
    if file_groups:
        materialize = '\t@"$(PYTHON)" "$(EXPORT_DIR)/materialize_stimuli.py" --export-dir "$(EXPORT_DIR)"'
        materialized_checks = "\n".join(
            f'\t@test -s "$(EXPORT_DIR)/generated_support/{name}_source.scs" || {{ echo "missing materialized Spectre stimulus for {name}" >&2; exit 2; }}'
            for name in file_groups
        )
    makefile = makefile.replace("{{MATERIALIZE_STIMULI}}", materialize)
    makefile = makefile.replace("{{MATERIALIZED_STIMULUS_CHECKS}}", materialized_checks)
    if "{{" in makefile or "}}" in makefile:
        raise SystemExit("unresolved Makefile placeholder")
    (export / "Makefile").write_text(makefile, encoding="utf-8")
    print(f"Cadence bundle generated: groups={len(groups)} path={export}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
