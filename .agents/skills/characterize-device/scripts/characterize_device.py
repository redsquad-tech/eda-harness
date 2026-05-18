#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import inspect
import json
import subprocess
import sys
import zipfile
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


def write_csv(experiment_dir: Path, rows: list[dict[str, Any]], experiment_id: str) -> Path:
    experiment_dir.mkdir(parents=True, exist_ok=True)
    out_path = experiment_dir / f"char_{experiment_id}.csv"

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


def export_artifacts_from_measure(
    device: str,
    experiment_dir: Path,
    corners: tuple[str, ...],
    num_points: int | None,
    measure_fn_name: str | None,
) -> dict[str, Any]:
    mod = importlib.import_module(f"devices.{device}.measure")
    exporter = getattr(mod, "export_characterization_artifacts", None)
    if exporter is None or not callable(exporter):
        raise RuntimeError(
            "Artifact export contract missing: define callable "
            f"devices.{device}.measure.export_characterization_artifacts(...)"
        )

    out: dict[str, Any] = {"bench_by_corner": {}, "files": []}
    spice_root = experiment_dir / "spice"
    expected_dut_path = (spice_root / f"{device}_dut.sp").resolve()
    canonical_dut_src: Path | None = None
    canonical_dut_hash: str | None = None
    for corner in corners:
        corner_dir = experiment_dir / "spice" / corner
        corner_dir.mkdir(parents=True, exist_ok=True)
        kwargs: dict[str, Any] = {
            "corner": corner,
            "out_dir": corner_dir,
            "dut_out_path": expected_dut_path,
        }
        if num_points is not None:
            kwargs["num_points"] = num_points
        if measure_fn_name:
            kwargs["measure_fn_name"] = measure_fn_name
        payload = exporter(**kwargs)
        if not isinstance(payload, dict):
            raise RuntimeError(
                "export_characterization_artifacts must return dict with keys "
                "'dut_spice_path' and 'bench_spice_path'"
            )
        dut_path = payload.get("dut_spice_path")
        bench_path = payload.get("bench_spice_path")
        if not dut_path or not bench_path:
            raise RuntimeError(
                "export_characterization_artifacts must return non-empty "
                "'dut_spice_path' and 'bench_spice_path'"
            )
        dut_abs = Path(str(dut_path)).resolve()
        bench_abs = Path(str(bench_path))
        if not dut_abs.exists() or not bench_abs.exists():
            raise RuntimeError(
                "export_characterization_artifacts returned missing files: "
                f"dut={dut_abs} bench={bench_abs}"
            )
        if dut_abs != expected_dut_path:
            raise RuntimeError(
                "Artifact export contract failed: DUT must be exported once to "
                f"{expected_dut_path}, got {dut_abs}"
            )
        dut_hash = hashlib.sha256(dut_abs.read_bytes()).hexdigest()
        if canonical_dut_hash is None:
            canonical_dut_hash = dut_hash
            canonical_dut_src = dut_abs
        elif dut_hash != canonical_dut_hash:
            raise RuntimeError(
                "DUT SPICE differs across corners for one characterization run. "
                "Current report format expects one DUT netlist per experiment."
            )
        out["bench_by_corner"][corner] = {
            "bench_spice_path": str(bench_abs),
        }
        out["files"].append(str(bench_abs))

    if canonical_dut_src is None:
        raise RuntimeError("Artifact export failed: no DUT SPICE generated")

    out["dut_spice_path"] = str(expected_dut_path)
    out["files"].insert(0, str(expected_dut_path))
    return out


def require_artifact_exporter(device: str) -> None:
    mod = importlib.import_module(f"devices.{device}.measure")
    exporter = getattr(mod, "export_characterization_artifacts", None)
    if exporter is None or not callable(exporter):
        raise RuntimeError(
            "Artifact export contract missing: define callable "
            f"devices.{device}.measure.export_characterization_artifacts(...)"
        )


def write_manifest(
    experiment_dir: Path,
    *,
    device: str,
    experiment_id: str,
    description: str,
    corners: tuple[str, ...],
    measure_fn_name: str,
    csv_path: Path,
    spice_exports: dict[str, Any],
) -> Path:
    manifest = {
        "device": device,
        "experiment_id": experiment_id,
        "description": description,
        "corners": list(corners),
        "measure_fn": measure_fn_name,
        "csv_path": str(csv_path),
        "spice": spice_exports,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    out = experiment_dir / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


def build_zip(experiment_dir: Path, experiment_id: str, include_files: list[Path]) -> Path:
    experiment_dir = experiment_dir.resolve()
    zip_path = experiment_dir / f"artifacts_{experiment_id}.zip"
    include_set = {p.resolve() for p in include_files}
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(include_set):
            if p == zip_path.resolve() or not p.is_file():
                continue
            zf.write(p, arcname=p.relative_to(experiment_dir))
    return zip_path


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

    # Fail fast before creating any full-characterization artifacts.
    require_artifact_exporter(args.device)

    experiment_dir = Path("devices") / args.device / "characterizations" / experiment_id
    out_path = write_csv(experiment_dir, rows, experiment_id)
    commit_hash = ""
    tag_name = ""
    used_measure_fn_name = str(rows[0].get("measure_fn")) if rows else (args.measure_fn or "")
    spice_exports = export_artifacts_from_measure(
        device=args.device,
        experiment_dir=experiment_dir,
        corners=corners,
        num_points=args.num_points,
        measure_fn_name=used_measure_fn_name if used_measure_fn_name else None,
    )
    manifest_path = write_manifest(
        experiment_dir,
        device=args.device,
        experiment_id=experiment_id,
        description=args.description,
        corners=corners,
        measure_fn_name=used_measure_fn_name,
        csv_path=out_path,
        spice_exports=spice_exports,
    )
    zip_inputs: list[Path] = [Path(out_path), Path(manifest_path)]
    zip_inputs.extend(Path(str(p)) for p in spice_exports.get("files", []))
    zip_path = build_zip(experiment_dir, experiment_id, zip_inputs)

    # Commit newly created artifacts (csv + spice + manifest + zip) on top of
    # existing device state if commit mode is enabled.
    if not args.no_commit:
        commit_hash = commit_characterization_device_state(
            repo=Path.cwd(),
            device=args.device,
            experiment_id=experiment_id,
        )
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
    print(f"Experiment dir: {experiment_dir}")
    print(f"Manifest: {manifest_path}")
    print(f"Archive: {zip_path}")
    print(f"Corners: {', '.join(corners)}")
    print(f"Experiment ID: {experiment_id}")
    if commit_hash:
        print(f"Commit: {commit_hash}")
    if tag_name:
        print(f"Tag: {tag_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
