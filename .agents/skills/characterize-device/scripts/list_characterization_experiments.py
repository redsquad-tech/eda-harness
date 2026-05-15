#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
from pathlib import Path
from typing import Any


def git_output(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def list_char_tags(device: str, repo: Path) -> list[str]:
    out = git_output(["tag", "-l", f"char/{device}/*"], repo)
    return sorted([line.strip() for line in out.splitlines() if line.strip()])


def git_file_text(ref: str, rel_path: str, repo: Path) -> str | None:
    proc = subprocess.run(["git", "show", f"{ref}:{rel_path}"], cwd=str(repo), capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return proc.stdout


def parse_csv_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    if not rows:
        return {"csv_exists": True, "rows": 0}
    sample = rows[0]
    pass_cols = [k for k in sample.keys() if k.startswith("pass_")]
    pass_summary: dict[str, str] = {}
    for col in pass_cols:
        vals = sorted({(r.get(col) or "").strip() for r in rows})
        pass_summary[col] = ",".join(vals)
    metric_preview: dict[str, Any] = {}
    for k, v in sample.items():
        if k.startswith("metric_"):
            metric_preview[k] = v
            if len(metric_preview) >= 8:
                break
    return {
        "csv_exists": True,
        "rows": len(rows),
        "corners": sorted({(r.get("corner") or "").strip() for r in rows if (r.get("corner") or "").strip()}),
        "description": sample.get("description", ""),
        "measure_fn": sample.get("measure_fn", ""),
        "pass_summary": pass_summary,
        "metric_preview": metric_preview,
    }


def parse_csv_summary(csv_path: Path, *, repo: Path, ref: str | None = None) -> dict[str, Any]:
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        out = parse_csv_rows(rows)
        out["csv_source"] = "working_tree"
        return out

    if ref is not None:
        rel_path = csv_path.relative_to(repo).as_posix()
        text = git_file_text(ref=ref, rel_path=rel_path, repo=repo)
        if text is not None:
            rows = list(csv.DictReader(io.StringIO(text)))
            out = parse_csv_rows(rows)
            out["csv_source"] = f"git:{ref}"
            return out

    return {"csv_exists": False}


def main() -> int:
    ap = argparse.ArgumentParser(description="List characterization experiments for device")
    ap.add_argument("--device", required=True)
    args = ap.parse_args()

    repo = Path.cwd()
    tags = list_char_tags(args.device, repo)
    out: dict[str, Any] = {"device": args.device, "count": len(tags), "experiments": []}
    for tag in tags:
        exp_id = tag.split("/")[-1]
        commit = git_output(["rev-list", "-n", "1", tag], repo)
        experiment_dir = repo / "devices" / args.device / "characterizations" / exp_id
        csv_path = experiment_dir / f"char_{exp_id}.csv"
        summary = parse_csv_summary(csv_path, repo=repo, ref=tag)
        zip_path = experiment_dir / f"artifacts_{exp_id}.zip"
        manifest_path = experiment_dir / "manifest.json"
        out["experiments"].append(
            {
                "tag": tag,
                "experiment_id": exp_id,
                "commit": commit,
                "csv_path": str(csv_path),
                "manifest_path": str(manifest_path),
                "archive_path": str(zip_path),
                **summary,
            }
        )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
