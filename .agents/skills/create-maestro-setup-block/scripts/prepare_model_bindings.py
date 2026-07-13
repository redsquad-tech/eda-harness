#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CORNER_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


@dataclass(frozen=True)
class ProcessCoverage:
    source: str
    corners: tuple[str, ...]


def markdown_table_value(text: str, label: str) -> str:
    match = re.search(
        rf"(?im)^\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|\s*$",
        text,
    )
    if not match:
        raise ValueError(f"missing {label!r} row in process-coverage table")
    return match.group(1).strip().strip("`").strip()


def read_process_coverage(path: Path) -> ProcessCoverage:
    if not path.is_file():
        raise ValueError(f"missing verification plan: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    source = markdown_table_value(text, "Corner Source")
    logical = markdown_table_value(text, "Logical Corners")

    if source not in {"specification", "configuration", "none"}:
        raise ValueError(
            f"invalid Corner Source {source!r}; expected specification, configuration, or none"
        )

    if source == "specification":
        corners = tuple(part.strip().strip("`").strip() for part in logical.split(","))
        if not corners or any(not corner for corner in corners):
            raise ValueError("Logical Corners must contain comma-separated names")
        if len(set(corners)) != len(corners):
            raise ValueError("Logical Corners contains duplicate names")
        for corner in corners:
            validate_corner_name(corner, "verification plan")
        return ProcessCoverage(source=source, corners=corners)

    if source == "configuration":
        if logical != "configured_process_corners":
            raise ValueError(
                "Corner Source configuration requires Logical Corners configured_process_corners"
            )
        return ProcessCoverage(source=source, corners=())

    if logical != "none":
        raise ValueError("Corner Source none requires Logical Corners none")
    return ProcessCoverage(source=source, corners=())


def validate_corner_name(name: str, context: str) -> None:
    if not CORNER_NAME_RE.fullmatch(name):
        raise ValueError(
            f"invalid logical corner name {name!r} in {context}; "
            "use letters, digits, underscore, hyphen, or dot"
        )


def toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def render_template(coverage: ProcessCoverage) -> str:
    lines = [
        "# Cadence process-model configuration.",
        "# Use absolute file paths. Replace every placeholder before validation.",
    ]
    if coverage.source == "none":
        lines.append("# No model entries are required because process-corner coverage is disabled.")
    else:
        lines.extend(
            [
                "# Uncomment the example entries you need, then copy lines or corner blocks as needed.",
                "# An entry without section includes the whole file.",
            ]
        )
    lines.extend(
        [
            "",
            "version = 1",
            "",
        "# common.models contains model entries used by every logical process corner.",
        "# Leave it empty when no model entry is shared by all corners.",
        "[common]",
        "models = [",
        '  # { file = "/absolute/path/to/common_model_file.scs", section = "common_section_name" },',
        '  # { file = "/absolute/path/to/sectionless_common_model_file.scs" },',
        "]",
        "",
        "# corners contains one table per logical process corner.",
        "# Each selected corner must contain at least one corner-specific model entry.",
        "[corners]",
        ]
    )
    if coverage.source == "specification":
        lines.extend(
            [
                "",
                "# The corner tables below come from the verification specification.",
                "# For every table, uncomment and fill at least one entry in models.",
            ]
        )
        for corner in coverage.corners:
            lines.extend(
                [
                    "",
                    f"[corners.{toml_string(corner)}]",
                    "models = [",
                    '  # { file = "/absolute/path/to/corner_model_file.scs", section = "corner_section_name" },',
                    '  # { file = "/absolute/path/to/additional_corner_model_file.scs", section = "additional_section_name" },',
                    "]",
                ]
            )
    elif coverage.source == "configuration":
        lines.extend(
            [
                "",
                "# The specification does not define logical process corners.",
                "# Copy the complete commented block once per desired corner.",
                "# Uncomment each copied block, replace logical_corner_name, and fill its models.",
                "#",
                '# [corners."logical_corner_name"]',
                "# models = [",
                '#   { file = "/absolute/path/to/corner_model_file.scs", section = "corner_section_name" },',
                '#   { file = "/absolute/path/to/additional_corner_model_file.scs", section = "additional_section_name" },',
                "# ]",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "# Process-corner coverage is not required by the verification plan.",
                "# Keep common.models and corners empty.",
            ]
        )
    return "\n".join(lines) + "\n"


def require_exact_keys(value: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"unknown keys in {context}: {', '.join(sorted(unknown))}")


def validate_models(value: Any, context: str) -> list[tuple[str, str | None]]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be an array")

    result: list[tuple[str, str | None]] = []
    for index, entry in enumerate(value, start=1):
        item_context = f"{context}[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{item_context} must be an object")
        require_exact_keys(entry, {"file", "section"}, item_context)

        file_value = entry.get("file")
        if not isinstance(file_value, str) or not file_value.strip():
            raise ValueError(f"{item_context}.file must be a non-empty string")
        model_path = Path(file_value)
        if not model_path.is_absolute():
            raise ValueError(f"{item_context}.file must be an absolute path: {file_value!r}")
        if not model_path.is_file():
            raise ValueError(f"{item_context}.file does not exist or is not a file: {file_value}")

        section = entry.get("section")
        if section is not None and (not isinstance(section, str) or not section.strip()):
            raise ValueError(f"{item_context}.section must be a non-empty string when present")
        result.append((file_value, section))
    return result


def load_and_resolve_config(
    path: Path, coverage: ProcessCoverage
) -> tuple[tuple[str, ...], dict[str, list[tuple[str, str | None]]]]:
    if not path.is_file():
        raise ValueError(f"missing model config: {path}; create it with --init")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("model config root must be an object")
    require_exact_keys(data, {"version", "common", "corners"}, "model config")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("model config version must be integer 1")

    common = data.get("common")
    if not isinstance(common, dict):
        raise ValueError("common must be an object")
    require_exact_keys(common, {"models"}, "common")
    common_models = validate_models(common.get("models"), "common.models")

    corners_value = data.get("corners")
    if not isinstance(corners_value, dict):
        raise ValueError("corners must be an object")

    corner_models: dict[str, list[tuple[str, str | None]]] = {}
    for corner, corner_value in corners_value.items():
        if not isinstance(corner, str):
            raise ValueError("corner names must be strings")
        validate_corner_name(corner, "model config")
        if not isinstance(corner_value, dict):
            raise ValueError(f"corners.{corner} must be an object")
        require_exact_keys(corner_value, {"models"}, f"corners.{corner}")
        corner_models[corner] = validate_models(
            corner_value.get("models"), f"corners.{corner}.models"
        )

    if coverage.source == "specification":
        missing = [corner for corner in coverage.corners if corner not in corner_models]
        if missing:
            raise ValueError(
                "required process corners missing from model config: " + ", ".join(missing)
            )
        selected = coverage.corners
    elif coverage.source == "configuration":
        if not corner_models:
            raise ValueError("corners must not be empty for configured_process_corners")
        selected = tuple(corner_models)
    else:
        if corner_models:
            raise ValueError("model config must not define corners when Corner Source is none")
        selected = ()

    resolved: dict[str, list[tuple[str, str | None]]] = {}
    for corner in selected:
        if not corner_models[corner]:
            raise ValueError(f"corners.{corner}.models must contain at least one model entry")
        resolved[corner] = [*common_models, *corner_models[corner]]
    return selected, resolved


def skill_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def render_skill(
    config_path: Path,
    source_sha256: str,
    corners: tuple[str, ...],
    resolved: dict[str, list[tuple[str, str | None]]],
) -> str:
    lines = [
        "; Generated from model_bindings.toml. Do not edit.",
        f"; Source: {config_path}",
        f"; Source SHA-256: {source_sha256}",
    ]
    if corners:
        lines.append(
            "edaHarnessProcessCorners = list(" + " ".join(skill_string(c) for c in corners) + ")"
        )
    else:
        lines.append("edaHarnessProcessCorners = nil")
    lines.extend(["", "procedure(edaHarnessModelsForCorner(cornerName)", "  case(cornerName"])
    for corner in corners:
        lines.append(f"    ({skill_string(corner)}")
        lines.append("      list(")
        for file_value, section in resolved[corner]:
            section_value = "nil" if section is None else skill_string(section)
            lines.append(f"        list({skill_string(file_value)} {section_value})")
        lines.extend(["      )", "    )"])
    lines.extend(
        [
            '    (t error("No model bindings for logical corner %s\\n" cornerName))',
            "  )",
            ")",
            "",
        ]
    )
    return "\n".join(lines)


def write_template(path: Path, coverage: ProcessCoverage) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_template(coverage), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create, validate, and compile Cadence process-model bindings."
    )
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--init", action="store_true", help="create model_bindings.toml if absent")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    verification_plan = workspace / "verification_plan.md"
    export = workspace / "cadence_export"
    config = export / "model_bindings.toml"
    output = export / "model_bindings.il"

    try:
        coverage = read_process_coverage(verification_plan)
        if args.init:
            if config.exists():
                print(f"model config already exists: {config}")
            else:
                write_template(config, coverage)
                print(f"created model config template: {config}")
            return 0

        corners, resolved = load_and_resolve_config(config, coverage)
        output.parent.mkdir(parents=True, exist_ok=True)
        source_sha256 = hashlib.sha256(config.read_bytes()).hexdigest()
        output.write_text(
            render_skill(config, source_sha256, corners, resolved), encoding="utf-8"
        )
    except ValueError as exc:
        raise SystemExit(f"model bindings error: {exc}") from exc

    print(f"validated model config: {config}")
    print(f"selected logical corners: {', '.join(corners) if corners else 'none'}")
    print(f"generated SKILL bindings: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
