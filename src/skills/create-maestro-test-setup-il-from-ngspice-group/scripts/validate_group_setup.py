#!/usr/bin/env python3
"""Static validator for one portable Maestro group setup fragment."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


META_RE = re.compile(r"^; EDA_HARNESS_(GROUP|TESTS|OUTPUTS|CORNERS|ANALYSIS):\s*(\S+)\s*$", re.M)
FORBIDDEN = (
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a generated Maestro group IL fragment.")
    parser.add_argument("fragment")
    parser.add_argument("--group", required=True)
    args = parser.parse_args()

    path = Path(args.fragment)
    if not path.is_file():
        raise SystemExit(f"missing group fragment: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    metadata = dict(META_RE.findall(text))
    expected = {"GROUP", "TESTS", "OUTPUTS", "CORNERS", "ANALYSIS"}
    if set(metadata) != expected:
        raise SystemExit(f"invalid metadata fields: expected={sorted(expected)}, actual={sorted(metadata)}")
    if metadata["GROUP"] != args.group:
        raise SystemExit(f"group mismatch: expected={args.group}, actual={metadata['GROUP']}")
    if metadata["ANALYSIS"] not in {"dc", "tran", "ac"}:
        raise SystemExit(f"unsupported analysis: {metadata['ANALYSIS']}")
    for field in ("TESTS", "OUTPUTS", "CORNERS"):
        if not metadata[field].isdigit() or int(metadata[field]) < 1:
            raise SystemExit(f"{field} must be a positive integer")
    if metadata["TESTS"] != "1":
        raise SystemExit("each group fragment must create exactly one Maestro test")
    for needle in FORBIDDEN:
        if needle in text:
            raise SystemExit(f"forbidden content in group fragment: {needle}")
    for required in ("maeCreateTest", "ehSetAnalysis", "ehAddOutput", "ehSetSpec"):
        if required not in text:
            raise SystemExit(f"group fragment is missing required call: {required}")
    print(
        f"Maestro group fragment valid: group={args.group} "
        f"analysis={metadata['ANALYSIS']} outputs={metadata['OUTPUTS']} corners={metadata['CORNERS']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
