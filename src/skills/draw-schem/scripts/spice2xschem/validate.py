#!/usr/bin/env python3
"""
CLI validation for generated xschem files.

This validator intentionally checks only file loading / symbol resolution.
The installed xschem 2.8.1 in this environment crashes in CLI netlisting
mode (`-x -n`) even on bundled example schematics, so netlisting is not
used as a pass/fail criterion here.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


def _runner() -> list[str]:
    if shutil.which("xvfb-run"):
        return ["xvfb-run", "-a", "xschem"]
    return ["xschem", "-x"]


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr)


def validate_dir(path: Path) -> int:
    if not shutil.which("xschem"):
        print("xschem not found in PATH")
        return 2

    root = path.resolve()
    files = sorted(root.glob("*.sch")) + sorted(root.glob("*.sym"))
    if not files:
        print(f"no .sch/.sym files found in {root}")
        return 2

    base_runner = _runner()
    open_failures: list[tuple[str, int, str]] = []
    unresolved: list[tuple[str, str]] = []

    for file in files:
        code, output = _run([*base_runner, "-q", file.name], root)
        lowered = output.lower()
        if code != 0 or "unable to open file" in lowered or "fatal:" in lowered:
            open_failures.append((file.name, code, output.strip()))
            continue

        if file.suffix == ".sch":
            with tempfile.NamedTemporaryFile(prefix="xschem_validate_", suffix=".log", delete=True) as tmp:
                code, output = _run([*base_runner, "-q", "-d", "2", "--log", tmp.name, file.name], root)
                log_text = Path(tmp.name).read_text(encoding="utf-8", errors="replace")
                issues = []
                if "unable to open file" in log_text.lower():
                    issues.append("unable to open file")
                if "missing=1" in log_text or "missing=2" in log_text or "missing=3" in log_text:
                    issues.append("missing symbols")
                if code != 0 or "fatal:" in output.lower():
                    issues.append("xschem returned non-zero during debug open")
                if issues:
                    unresolved.append((file.name, ", ".join(issues)))

    print(f"checked files: {len(files)}")
    print(f"open failures: {len(open_failures)}")
    print(f"resolution issues: {len(unresolved)}")

    for name, code, output in open_failures[:20]:
        print(f"FAIL open {name} exit={code}")
        if output:
            print(output[:500])

    for name, issue in unresolved[:20]:
        print(f"FAIL resolve {name}: {issue}")

    if open_failures or unresolved:
        return 1

    print("all files opened successfully and no unresolved symbols were reported")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated xschem files through xschem CLI")
    parser.add_argument("directory", help="Directory with generated .sch/.sym files")
    args = parser.parse_args()
    raise SystemExit(validate_dir(Path(args.directory)))


if __name__ == "__main__":
    main()
