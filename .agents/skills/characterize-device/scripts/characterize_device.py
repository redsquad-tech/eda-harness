#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib
import inspect
import json
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import hdl21 as h


CORNER_MAP = {
    "TT": h.pdk.Corner.TYP,
    "FF": h.pdk.Corner.FAST,
    "SS": h.pdk.Corner.SLOW,
    # Cross corners are passed as canonical string labels.
    # Device measurement functions are expected to normalize and handle them.
    "FS": "FS",
    "SF": "SF",
}

# Ensure repository root is importable even when script is executed by path.
# (e.g. `python .agents/skills/.../characterize_device.py`)
REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    return value


def load_spec_targets(device: str) -> dict[str, dict[str, Any]]:
    """
    Optional per-device characterization targets.
    Expected file: devices/<device>/characterization_spec.json
    Format:
    {
      "metrics": {
        "metric_name": {"min": <num>, "max": <num>, "typ": <num>, "exact": <num>}
      }
    }
    """
    path = Path("devices") / device / "characterization_spec.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics", {})
    if not isinstance(metrics, dict):
        raise RuntimeError(f"Invalid characterization spec format in {path}: 'metrics' must be object")
    return metrics


def eval_target(value: Any, target: dict[str, Any]) -> str:
    # Pass/fail as string for CSV readability: PASS/FAIL/N/A
    if not isinstance(value, (int, float)):
        return "N/A"
    if "exact" in target and value != float(target["exact"]):
        return "FAIL"
    if "min" in target and value < float(target["min"]):
        return "FAIL"
    if "max" in target and value > float(target["max"]):
        return "FAIL"
    return "PASS"


def _invoke_measurement(fn: Any, fn_name: str, corner_code: str, num_points: int | None = None) -> dict[str, Any]:
    sig = inspect.signature(fn)
    if "corner" not in sig.parameters:
        raise RuntimeError(
            f"Measurement function {fn_name} is not PVT-compatible: missing required 'corner' argument"
        )
    kwargs: dict[str, Any] = {}
    kwargs["corner"] = CORNER_MAP[corner_code]
    if num_points is not None and "num_points" in sig.parameters:
        kwargs["num_points"] = num_points

    result = fn(**kwargs)
    if not isinstance(result, dict):
        raise RuntimeError(f"Measurement function must return dict, got: {type(result)!r}")

    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        raise RuntimeError("Measurement result must include dict key 'metrics'")
    for key in ("component", "category", "purpose"):
        if not result.get(key):
            raise RuntimeError(
                f"Measurement function {fn_name} must return non-empty '{key}' for characterization"
            )

    out = {
        "component": result.get("component"),
        "category": result.get("category"),
        "purpose": result.get("purpose"),
        "metrics": to_plain(metrics),
    }
    return out


def resolve_measure_fn(mod: Any, explicit_fn_name: str | None, num_points: int | None) -> tuple[str, Any]:
    if explicit_fn_name:
        fn = getattr(mod, explicit_fn_name, None)
        if fn is None or not callable(fn):
            raise RuntimeError(f"Measurement function not found: {mod.__name__}.{explicit_fn_name}")
        return explicit_fn_name, fn

    candidates: list[tuple[str, Any]] = []
    for name in dir(mod):
        if name.startswith("_"):
            continue
        obj = getattr(mod, name)
        if not callable(obj):
            continue
        try:
            sig = inspect.signature(obj)
        except (TypeError, ValueError):
            continue
        if "corner" in sig.parameters:
            candidates.append((name, obj))
    if not candidates:
        raise RuntimeError(
            f"No suitable measurement function found in {mod.__name__}: "
            "expected a public callable with `corner` argument"
        )

    def score(name: str) -> tuple[int, str]:
        lowered = name.lower()
        if lowered.startswith("run_"):
            return (0, lowered)
        if "char" in lowered:
            return (1, lowered)
        return (2, lowered)

    for name, fn in sorted(candidates, key=lambda x: score(x[0])):
        try:
            _ = _invoke_measurement(fn, name, "TT", num_points=num_points)
            return name, fn
        except Exception:
            continue
    raise RuntimeError(
        f"Could not auto-select measurement function in {mod.__name__}: "
        "corner-aware candidates exist, but none passed output contract probe"
    )


def run_measurement(
    device: str, fn_name: str | None, corner_code: str, num_points: int | None = None
) -> tuple[str, dict[str, Any]]:
    mod = importlib.import_module(f"devices.{device}.measure")
    resolved_name, fn = resolve_measure_fn(mod, explicit_fn_name=fn_name, num_points=num_points)
    out = _invoke_measurement(fn, resolved_name, corner_code, num_points=num_points)
    return resolved_name, out


def build_rows(
    device: str,
    description: str,
    fn_name: str | None,
    num_points: int | None,
    min_points: int,
    spec_targets: dict[str, dict[str, Any]],
    corners: tuple[str, ...] = ("TT", "FF", "SS", "FS", "SF"),
) -> tuple[list[dict[str, Any]], str]:
    experiment_id = utc_stamp()
    rows: list[dict[str, Any]] = []

    for corner_code in corners:
        resolved_name, res = run_measurement(
            device=device,
            fn_name=fn_name,
            corner_code=corner_code,
            num_points=num_points,
        )
        num_points = res["metrics"].get("num_points")
        if isinstance(num_points, (int, float)) and int(num_points) < min_points:
            raise RuntimeError(
                f"Characterization rejected: metric num_points={num_points} is below minimum {min_points}. "
                "Use a fuller measurement sweep."
            )
        row: dict[str, Any] = {
            "experiment_id": experiment_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "device": device,
            "description": description,
            "corner": corner_code,
            "measure_fn": resolved_name,
            "component": res.get("component"),
            "category": res.get("category"),
            "purpose": res.get("purpose"),
        }
        for key, value in res["metrics"].items():
            # Avoid duplicating the corner value both as top-level `corner`
            # and as `metric_corner` when measurement returns identical info.
            if key == "corner" and str(value).upper() == corner_code:
                continue
            metric_col = f"metric_{key}"
            row[metric_col] = value
            target = spec_targets.get(key)
            if isinstance(target, dict):
                if "min" in target:
                    row[f"target_{key}_min"] = target["min"]
                if "typ" in target:
                    row[f"target_{key}_typ"] = target["typ"]
                if "max" in target:
                    row[f"target_{key}_max"] = target["max"]
                if "exact" in target:
                    row[f"target_{key}_exact"] = target["exact"]
                row[f"pass_{key}"] = eval_target(value, target)
        rows.append(row)

    return rows, experiment_id


def _corner_sensitivity_contract(rows: list[dict[str, Any]], corners: tuple[str, ...]) -> None:
    """
    Generic PVT sanity check:
    for multi-corner runs, require at least one numeric metric to differ across corners.
    Prevents "corner label changes only" outputs.
    """
    if len(corners) <= 1 or len(rows) <= 1:
        return
    metric_cols = sorted({k for r in rows for k in r.keys() if k.startswith("metric_")})
    if not metric_cols:
        return
    numeric_cols = []
    for col in metric_cols:
        vals = [r.get(col) for r in rows]
        if all(isinstance(v, (int, float)) for v in vals):
            numeric_cols.append(col)
    if not numeric_cols:
        return
    any_varies = False
    for col in numeric_cols:
        vals = [float(r.get(col)) for r in rows]
        if max(vals) - min(vals) > 1e-15:
            any_varies = True
            break
    if not any_varies:
        raise RuntimeError(
            "Characterization contract failed: multi-corner run produced identical numeric metrics "
            "across corners. Ensure corner input changes model/conditions, not only corner label."
        )


def write_csv(device: str, rows: list[dict[str, Any]], experiment_id: str) -> Path:
    out_dir = Path("devices") / device / "characterizations"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"char_{experiment_id}.csv"

    fieldnames: list[str] = []
    seen = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return out_path


def git_output(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def create_char_tag(
    repo: Path,
    device: str,
    experiment_id: str,
    csv_path: Path,
    description: str,
    corners: tuple[str, ...],
) -> str:
    tag = f"char/{device}/{experiment_id}"
    existing = git_output(["tag", "-l", tag], repo)
    if existing.strip():
        raise RuntimeError(f"Tag already exists: {tag}")
    msg = "\n".join(
        [
            f"Characterization experiment for {device}",
            "",
            f"experiment_id: {experiment_id}",
            f"csv: {csv_path.as_posix()}",
            f"corners: {','.join(corners)}",
            f"description: {description.replace(chr(10), ' ')}",
        ]
    )
    _ = git_output(["tag", "-a", tag, "-m", msg], repo)
    return tag


def commit_characterization_device_state(repo: Path, device: str, experiment_id: str) -> str:
    device_dir = f"devices/{device}"
    _ = git_output(["add", "--", device_dir], repo)
    message = f"characterization({device}): {experiment_id}"
    _ = git_output(["commit", "-m", message], repo)
    return git_output(["rev-parse", "HEAD"], repo)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run characterization and optionally save one CSV")
    ap.add_argument("--device", required=True, help="Device directory name under devices/")
    ap.add_argument(
        "--description",
        required=True,
        help="Free-form experiment description stored in CSV",
    )
    ap.add_argument(
        "--measure-fn",
        default=None,
        help="Measurement function name from devices.<device>.measure (default: auto-discover corner-aware function)",
    )
    ap.add_argument(
        "--num-points",
        type=int,
        default=3,
        help="Default characterization sweep points for measurement functions that accept num_points",
    )
    ap.add_argument(
        "--min-points",
        type=int,
        default=3,
        help="Minimum allowed metric_num_points (if metric is present)",
    )
    ap.add_argument(
        "--validate-only",
        action="store_true",
        help="Run one fast contract validation point (TT) and do not write CSV",
    )
    ap.add_argument(
        "--no-csv",
        action="store_true",
        help="Run measurements but do not write CSV",
    )
    ap.add_argument(
        "--corners",
        default="TT,FF,SS,FS,SF",
        help="Comma-separated corners from TT,FF,SS,FS,SF (default: TT,FF,SS,FS,SF)",
    )
    ap.add_argument(
        "--no-tag",
        action="store_true",
        help="Do not create git tag for full characterization",
    )
    ap.add_argument(
        "--no-commit",
        action="store_true",
        help="Do not create git commit for characterization device state",
    )
    args = ap.parse_args()

    device_dir = Path("devices") / args.device
    if not device_dir.exists():
        raise SystemExit(f"Device not found: {device_dir}")

    corners = tuple(c.strip().upper() for c in args.corners.split(",") if c.strip())
    if args.validate_only:
        corners = ("TT",)
    allowed = {"TT", "FF", "SS", "FS", "SF"}
    invalid = [c for c in corners if c not in allowed]
    if invalid:
        raise SystemExit(f"Invalid corners: {invalid}. Allowed: TT,FF,SS,FS,SF")

    rows, experiment_id = build_rows(
        device=args.device,
        description=args.description,
        fn_name=args.measure_fn,
        num_points=args.num_points,
        min_points=args.min_points,
        spec_targets=load_spec_targets(args.device),
        corners=corners,
    )
    _corner_sensitivity_contract(rows, corners)
    if args.validate_only:
        print("Characterization contract validation passed")
        print("Mode: validate-only")
        print("Corners: TT")
        print(f"Experiment ID: {experiment_id}")
        return 0

    if args.no_csv:
        print("Characterization run completed (no CSV requested)")
        print(f"Corners: {', '.join(corners)}")
        print(f"Experiment ID: {experiment_id}")
        return 0

    out_path = write_csv(args.device, rows, experiment_id)
    commit_hash = ""
    if not args.no_commit:
        commit_hash = commit_characterization_device_state(
            repo=Path.cwd(),
            device=args.device,
            experiment_id=experiment_id,
        )
    tag_name = ""
    if not args.no_tag:
        tag_name = create_char_tag(
            repo=Path.cwd(),
            device=args.device,
            experiment_id=experiment_id,
            csv_path=out_path,
            description=args.description,
            corners=corners,
        )
    print(f"Characterization done: {out_path}")
    print(f"Corners: {', '.join(corners)}")
    print(f"Experiment ID: {experiment_id}")
    if commit_hash:
        print(f"Commit: {commit_hash}")
    if tag_name:
        print(f"Tag: {tag_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
