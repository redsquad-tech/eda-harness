#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

LINE_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def git_ref_exists(ref: str, cwd: Path) -> bool:
    proc = subprocess.run(["git", "show-ref", "--verify", "--quiet", ref], cwd=str(cwd))
    return proc.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Create or switch to device line branch")
    ap.add_argument("--device", required=True)
    ap.add_argument("--line", required=True)
    ap.add_argument("--base-ref", default="main")
    ap.add_argument("--allow-dirty", action="store_true")
    args = ap.parse_args()

    if not LINE_RE.match(args.line):
        raise SystemExit("Invalid line name. Allowed: letters, digits, dot, underscore, dash.")

    repo = Path.cwd()

    if not args.allow_dirty:
        device_prefix = f"devices/{args.device}/"
        tracked = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        tracked = [p.strip() for p in tracked if p.strip()]
        disallowed = [p for p in tracked if not p.startswith(device_prefix)]
        if disallowed:
            raise SystemExit(
                "Working tree has tracked changes outside target device. "
                "Commit/stash them first or pass --allow-dirty.\n" + "\n".join(disallowed)
            )

    branch = f"device/{args.device}/{args.line}"
    if git_ref_exists(f"refs/heads/{branch}", repo):
        subprocess.run(["git", "switch", branch], cwd=str(repo), check=True)
        print(f"Switched to existing line: {branch}")
        return 0

    subprocess.run(["git", "switch", "-c", branch, args.base_ref], cwd=str(repo), check=True)
    print(f"Created and switched to line: {branch} (base: {args.base_ref})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
