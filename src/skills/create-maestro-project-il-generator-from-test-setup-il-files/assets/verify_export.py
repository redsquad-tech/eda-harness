#!/usr/bin/env python3
"""Validate a generated Cadence import log and structural validation record."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


HARD_FAILURE_RE = re.compile(
    r"(?:\*error\*|\berror\b|doesn't exist|undefined function|unbound variable|failed)",
    re.IGNORECASE,
)
WARNING_RE = re.compile(r"\bwarning\b", re.IGNORECASE)
ALLOWED_WARNING_RES = (
    re.compile(r"WARNING This OS does not appear to be a Cadence supported Linux configuration", re.IGNORECASE),
    re.compile(r"\*WARNING\* could not load font .+ using font .+", re.IGNORECASE),
    re.compile(r"\*WARNING\* Font name .+ is invalid", re.IGNORECASE),
    re.compile(
        r"\*WARNING\* The Virtuoso Analog Design Environment \(ADE\) creates a user interface \(UI\)",
        re.IGNORECASE,
    ),
)


def is_allowed_warning(line: str) -> bool:
    return any(pattern.search(line) for pattern in ALLOWED_WARNING_RES)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a generated EDA Harness Cadence import.")
    parser.add_argument("log")
    parser.add_argument("validation")
    args = parser.parse_args()

    log_path = Path(args.log)
    validation_path = Path(args.validation)
    if not log_path.is_file():
        raise SystemExit(f"missing Cadence log: {log_path}")
    text = log_path.read_text(encoding="utf-8", errors="replace")
    failures = [
        line
        for line in text.splitlines()
        if HARD_FAILURE_RE.search(line)
        or (WARNING_RE.search(line) and not is_allowed_warning(line))
    ]
    if failures:
        raise SystemExit("Cadence emitted warning/error output:\n" + "\n".join(failures[:20]))
    if "EDA_HARNESS_EXPORT_OK" not in text:
        raise SystemExit("missing EDA_HARNESS_EXPORT_OK sentinel")

    try:
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid validation record: {exc}") from exc
    expected_fields = {"status", "expected_tests", "actual_tests"}
    if not isinstance(validation, dict) or set(validation) != expected_fields:
        actual_fields = sorted(validation) if isinstance(validation, dict) else type(validation).__name__
        raise SystemExit(
            f"invalid validation fields: expected={sorted(expected_fields)}, actual={actual_fields}"
        )
    if validation.get("status") != "ok":
        raise SystemExit("Cadence validation status is not ok")
    expected = validation.get("expected_tests")
    actual = validation.get("actual_tests")
    if not isinstance(expected, int) or expected < 1 or actual != expected:
        raise SystemExit(f"Cadence test count mismatch: expected={expected}, actual={actual}")
    print(f"Cadence export verified: tests={actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
