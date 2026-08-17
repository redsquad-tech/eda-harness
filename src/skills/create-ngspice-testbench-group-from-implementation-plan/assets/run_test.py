#!/usr/bin/env python3
"""Reproducible runner copied into a generated DUT workspace as tests/run_test.py."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


METRICS_HEADER = [
    "test_name",
    "requirement",
    "run_id",
    "parameters",
    "metric",
    "value",
    "unit",
    "limit_min",
    "limit_max",
    "pass",
    "fail_reason",
    "source_log",
]
SUMMARY_RE = re.compile(
    r"^SUMMARY\s+test=(\S+)\s+runs=(\d+)\s+results=(\d+)\s+fail_count=(\d+)\s*$"
)
class RunnerError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate and validate one testbench group or the complete DUT suite."
    )
    parser.add_argument("group", nargs="?", help="Group name from tests/testbench_manifest.json")
    parser.add_argument("--all", action="store_true", help="Run every group in manifest order")
    parser.add_argument(
        "--ngspice",
        default=os.environ.get("NGSPICE", "ngspice"),
        help="ngspice executable (default: NGSPICE or ngspice)",
    )
    args = parser.parse_args()
    if args.all == (args.group is not None):
        parser.error("select exactly one group or --all")
    return args


def inside(root: Path, raw: object, field: str, *, must_exist: bool = False) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise RunnerError(f"{field} must be a non-empty relative path")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise RunnerError(f"{field} must remain inside the DUT workspace: {raw}")
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RunnerError(f"{field} escapes the DUT workspace: {raw}") from exc

    current = root
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise RunnerError(f"{field} traverses a symlink: {raw}")
    if must_exist and not path.is_file():
        raise RunnerError(f"missing {field}: {raw}")
    return path


def load_manifest(root: Path) -> list[dict[str, object]]:
    path = root / "tests" / "testbench_manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunnerError(f"cannot read {path.relative_to(root)}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise RunnerError("testbench manifest schema_version must be 1")
    groups = payload.get("groups")
    if not isinstance(groups, list) or not groups:
        raise RunnerError("testbench manifest groups must be a non-empty array")

    names: set[str] = set()
    orders: set[int] = set()
    for group in groups:
        if not isinstance(group, dict):
            raise RunnerError("each manifest group must be an object")
        name = group.get("name")
        order = group.get("order")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise RunnerError(f"invalid group name: {name!r}")
        if name in names:
            raise RunnerError(f"duplicate group name: {name}")
        if not isinstance(order, int) or order < 1 or order in orders:
            raise RunnerError(f"invalid or duplicate order for {name}")
        names.add(name)
        orders.add(order)
    return sorted(groups, key=lambda item: int(item["order"]))


def declared_paths(root: Path, group: dict[str, object]) -> dict[str, object]:
    name = str(group["name"])
    paths: dict[str, object] = {
        "generator": inside(root, group.get("generator"), f"{name}.generator", must_exist=True),
        "fixture": inside(root, group.get("fixture"), f"{name}.fixture"),
        "control": inside(root, group.get("control"), f"{name}.control", must_exist=True),
        "log": inside(root, group.get("log"), f"{name}.log"),
        "metrics": inside(root, group.get("metrics"), f"{name}.metrics"),
    }
    for field in ("expected_runs", "expected_results"):
        value = group.get(field)
        if not isinstance(value, int) or value < 1:
            raise RunnerError(f"{name}.{field} must be a positive integer")

    parser = group.get("parser")
    paths["parser"] = None if parser in (None, "") else inside(
        root, parser, f"{name}.parser", must_exist=True
    )
    canonical_inputs = group.get("canonical_inputs", [])
    generated_dependencies = group.get("generated_dependencies", [])
    if not isinstance(canonical_inputs, list) or not isinstance(generated_dependencies, list):
        raise RunnerError(
            f"{name}.canonical_inputs and generated_dependencies must be arrays"
        )
    paths["canonical_inputs"] = [
        inside(root, item, f"{name}.canonical_inputs[{index}]", must_exist=True)
        for index, item in enumerate(canonical_inputs)
    ]
    paths["generated_dependencies"] = [
        inside(root, item, f"{name}.generated_dependencies[{index}]")
        for index, item in enumerate(generated_dependencies)
    ]
    materializer = group.get("materializer")
    paths["materializer"] = None if materializer in (None, "") else inside(
        root, materializer, f"{name}.materializer", must_exist=True
    )
    if any((paths["canonical_inputs"], paths["generated_dependencies"], paths["materializer"])) and not all(
        (paths["canonical_inputs"], paths["generated_dependencies"], paths["materializer"])
    ):
        raise RunnerError(
            f"{name} file-based stimulus requires canonical_inputs, materializer, "
            "and generated_dependencies"
        )
    artifacts = group.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise RunnerError(f"{name}.artifacts must be an array")
    normalized = []
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise RunnerError(f"{name}.artifacts[{index}] must be an object")
        kind = artifact.get("kind")
        columns = artifact.get("required_columns")
        if kind not in {"sample", "waveform"}:
            raise RunnerError(f"{name}.artifacts[{index}].kind is invalid")
        if not isinstance(columns, list) or not columns or not all(
            isinstance(column, str) and column for column in columns
        ):
            raise RunnerError(f"{name}.artifacts[{index}].required_columns is invalid")
        normalized.append(
            {
                "kind": kind,
                "path": inside(root, artifact.get("path"), f"{name}.artifacts[{index}].path"),
                "required_columns": columns,
            }
        )
    paths["artifacts"] = normalized
    return paths


def executable(raw: str) -> str:
    if os.sep in raw:
        path = Path(raw).resolve()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RunnerError(f"ngspice is not executable: {raw}")
        return str(path)
    found = shutil.which(raw)
    if found is None:
        raise RunnerError(f"ngspice is not available: {raw}")
    return found


def probe_writable(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(prefix=".eda-preflight-", dir=directory):
            pass
    except OSError as exc:
        raise RunnerError(f"directory is not writable: {directory}: {exc}") from exc


def preflight(root: Path, groups: list[dict[str, object]], ngspice: str) -> tuple[str, dict[str, dict[str, object]]]:
    errors: list[str] = []
    resolved: dict[str, dict[str, object]] = {}
    try:
        ngspice_bin = executable(ngspice)
    except RunnerError as exc:
        errors.append(str(exc))
        ngspice_bin = ngspice

    hdl21 = subprocess.run(
        [sys.executable, "-c", "import hdl21"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if hdl21.returncode != 0:
        errors.append(f"HDL21 import failed: {hdl21.stderr.strip() or hdl21.stdout.strip()}")
    for directory in (root, root / "results", root / "results" / ".work"):
        try:
            probe_writable(directory)
        except RunnerError as exc:
            errors.append(str(exc))
    for group in groups:
        try:
            resolved[str(group["name"])] = declared_paths(root, group)
        except RunnerError as exc:
            errors.append(str(exc))
    if errors:
        raise RunnerError("preflight failed:\n- " + "\n- ".join(errors))
    return ngspice_bin, resolved


def remove_file(path: Path) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise RunnerError(f"refusing to remove non-file output: {path}")
        path.unlink()


def remove_outputs(paths: dict[str, object], *, include_log: bool) -> None:
    remove_file(paths["fixture"])
    remove_file(paths["metrics"])
    for dependency in paths["generated_dependencies"]:
        remove_file(dependency)
    for artifact in paths["artifacts"]:
        remove_file(artifact["path"])
    if include_log:
        remove_file(paths["log"])


def publish_diagnostic(paths: dict[str, object], work: Path, messages: list[str]) -> None:
    log = paths["log"]
    log.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(messages)
    ngspice_log = work / "ngspice.log"
    if ngspice_log.is_file():
        text += "\n" + ngspice_log.read_text(encoding="utf-8", errors="replace")
    log.write_text(text.rstrip() + "\n", encoding="utf-8")


def validate_csv(path: Path, required: list[str]) -> list[dict[str, str]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise RunnerError(f"missing or empty CSV: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or any(column not in reader.fieldnames for column in required):
            raise RunnerError(f"CSV {path} is missing required columns: {required}")
        rows = list(reader)
    if not rows:
        raise RunnerError(f"CSV has no data rows: {path}")
    return rows


def validate_results(root: Path, group: dict[str, object], paths: dict[str, object], ngspice_log: Path) -> int:
    text = ngspice_log.read_text(encoding="utf-8", errors="replace")
    summaries = [match for line in text.splitlines() if (match := SUMMARY_RE.match(line.strip()))]
    if len(summaries) != 1:
        raise RunnerError(f"{group['name']} must emit exactly one canonical SUMMARY")
    match = summaries[0]
    summary_name, runs, results, fail_count = match.group(1), *map(int, match.groups()[1:])
    if summary_name != group["name"]:
        raise RunnerError(f"SUMMARY test mismatch for {group['name']}")
    if runs != group["expected_runs"] or results != group["expected_results"]:
        raise RunnerError(
            f"SUMMARY count mismatch for {group['name']}: runs={runs}, results={results}"
        )
    result_lines = [line for line in text.splitlines() if line.startswith("RESULT ")]
    if len(result_lines) != results:
        raise RunnerError(f"RESULT-row count mismatch for {group['name']}")
    declared_failures = sum(1 for line in result_lines if re.search(r"(?:^|\s)pass=0(?:\s|$)", line))
    if declared_failures != fail_count:
        raise RunnerError(f"FAIL count mismatch for {group['name']}")

    metrics_rows = validate_csv(paths["metrics"], METRICS_HEADER)
    if len(metrics_rows) != results:
        raise RunnerError(f"metrics CSV row count mismatch for {group['name']}")
    csv_failures = sum(1 for row in metrics_rows if row["pass"] == "0")
    if csv_failures != fail_count:
        raise RunnerError(f"metrics CSV pass count mismatch for {group['name']}")
    for artifact in paths["artifacts"]:
        validate_csv(artifact["path"], artifact["required_columns"])
    return 1 if fail_count else 0


def run_group(root: Path, group: dict[str, object], paths: dict[str, object], ngspice: str) -> int:
    name = str(group["name"])
    work = root / "results" / ".work" / name
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    messages: list[str] = []
    try:
        remove_outputs(paths, include_log=True)
        paths["log"].parent.mkdir(parents=True, exist_ok=True)
        paths["metrics"].parent.mkdir(parents=True, exist_ok=True)
        for dependency in paths["generated_dependencies"]:
            dependency.parent.mkdir(parents=True, exist_ok=True)
        for artifact in paths["artifacts"]:
            artifact["path"].parent.mkdir(parents=True, exist_ok=True)

        if paths["materializer"] is not None:
            materialized = subprocess.run(
                [sys.executable, str(paths["materializer"])],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            messages.append(
                f"materializer exit={materialized.returncode}\n"
                f"{materialized.stdout}{materialized.stderr}"
            )
            if materialized.returncode != 0 or any(
                not path.is_file() or path.stat().st_size == 0
                for path in paths["generated_dependencies"]
            ):
                raise RunnerError(f"stimulus materializer failed for {name}")

        generated = subprocess.run(
            [sys.executable, str(paths["generator"])],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        messages.append(f"generator exit={generated.returncode}\n{generated.stdout}{generated.stderr}")
        if generated.returncode != 0 or not paths["fixture"].is_file():
            raise RunnerError(f"HDL21 generator failed for {name}")

        ngspice_log = work / "ngspice.log"
        simulated = subprocess.run(
            [ngspice, "-b", "-o", str(ngspice_log), str(paths["control"])],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        messages.append(f"ngspice exit={simulated.returncode}\n{simulated.stdout}{simulated.stderr}")
        if simulated.returncode != 0 or not ngspice_log.is_file():
            raise RunnerError(f"ngspice failed for {name}")

        if paths["parser"] is not None:
            parsed = subprocess.run(
                [
                    sys.executable,
                    str(paths["parser"]),
                    "--log",
                    str(ngspice_log),
                    "--manifest",
                    str(root / "tests" / "testbench_manifest.json"),
                    "--group",
                    name,
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            messages.append(f"parser exit={parsed.returncode}\n{parsed.stdout}{parsed.stderr}")
            if parsed.returncode != 0:
                raise RunnerError(f"saved parser failed for {name}")

        status = validate_results(root, group, paths, ngspice_log)
        shutil.copyfile(ngspice_log, paths["log"])
        print(f"GROUP {name} status={'dut_fail' if status else 'pass'}")
        return status
    except (OSError, RunnerError) as exc:
        messages.append(f"RUNNER_ERROR {exc}")
        try:
            remove_outputs(paths, include_log=False)
            publish_diagnostic(paths, work, messages)
        except (OSError, RunnerError) as cleanup_error:
            print(f"RUNNER_ERROR cleanup failed for {name}: {cleanup_error}", file=sys.stderr)
        print(f"GROUP {name} status=infra_fail reason={exc}", file=sys.stderr)
        return 2


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    try:
        groups = load_manifest(root)
        if args.group is not None:
            groups = [group for group in groups if group["name"] == args.group]
            if not groups:
                raise RunnerError(f"unknown group: {args.group}")
        ngspice, resolved = preflight(root, groups, args.ngspice)
    except RunnerError as exc:
        print(f"RUNNER_ERROR {exc}", file=sys.stderr)
        return 2

    status = 0
    for group in groups:
        status = max(status, run_group(root, group, resolved[str(group["name"])], ngspice))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
