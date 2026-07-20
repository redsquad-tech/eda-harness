#!/usr/bin/env python3
"""Run OA-style schematic JSON -> HDL21 conversion."""
from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--top")
    parser.add_argument("--pdk", default="analogLib")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cmd = [
        "virtuoso-to-hdl21",
        "--in-dir", args.in_dir,
        "--out", args.out,
        "--pdk", args.pdk,
    ]
    if args.top:
        cmd.extend(["--top", args.top])
    if args.verbose:
        cmd.append("--verbose")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
