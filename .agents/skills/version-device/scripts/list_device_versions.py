#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def git_output(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def list_line_branches(device: str, repo: Path) -> list[str]:
    out = git_output(["for-each-ref", "--format=%(refname:short)", f"refs/heads/device/{device}/"], repo)
    return [line.strip() for line in out.splitlines() if line.strip()]


def list_freeze_tags(device: str, repo: Path) -> list[str]:
    out = git_output(["tag", "-l", f"device/{device}/*/v*"], repo)
    return sorted([line.strip() for line in out.splitlines() if line.strip()])


def list_release_tags(device: str, repo: Path) -> list[str]:
    out = git_output(["tag", "-l", f"release/{device}/v*"], repo)
    return sorted([line.strip() for line in out.splitlines() if line.strip()])


def load_index(device: str, repo: Path) -> tuple[dict | None, str | None]:
    p = repo / "devices" / device / "VERSION_INDEX.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")), "current_branch"
        except json.JSONDecodeError:
            return None, None
    if not p.exists():
        # Canonical catalog lives on main. If current branch does not have it,
        # read it from main directly.
        try:
            out = git_output(["show", f"main:devices/{device}/VERSION_INDEX.json"], repo)
            return json.loads(out), "main"
        except Exception:
            return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description="List branches/tags/catalog for a device")
    ap.add_argument("--device", required=True)
    args = ap.parse_args()

    repo = Path.cwd()
    version_index, version_index_source = load_index(args.device, repo)
    payload = {
        "device": args.device,
        "line_branches": list_line_branches(args.device, repo),
        "freeze_tags": list_freeze_tags(args.device, repo),
        "release_tags": list_release_tags(args.device, repo),
        "version_index": version_index,
        "version_index_source": version_index_source,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
