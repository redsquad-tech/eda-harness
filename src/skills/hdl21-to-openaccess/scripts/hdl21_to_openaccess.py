#!/usr/bin/env python3
"""Run HDL21 -> OA-style schematic JSON conversion."""
from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--library", default="scratch")
    parser.add_argument("--pdk", default="analogLib")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cmd = [
        "hdl21-to-virtuoso",
        "--top", args.top,
        "--out-dir", args.out_dir,
        "--library", args.library,
        "--pdk", args.pdk,
    ]
    if args.verbose:
        cmd.append("--verbose")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
