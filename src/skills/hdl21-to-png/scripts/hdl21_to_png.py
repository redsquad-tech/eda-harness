#!/usr/bin/env python3
"""Run HDL21 -> schematic PNG conversion."""
from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--json-dir")
    parser.add_argument("--library", default="scratch")
    parser.add_argument("--pdk", default="analogLib")
    parser.add_argument("--view", default="schematic")
    parser.add_argument("--scale", default="2.0")
    parser.add_argument("--hierarchy-dir")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cmd = [
        "hdl21-to-png",
        "--top", args.top,
        "--out-dir", args.out_dir,
        "--library", args.library,
        "--pdk", args.pdk,
        "--view", args.view,
        "--scale", args.scale,
    ]
    if args.json_dir:
        cmd.extend(["--json-dir", args.json_dir])
    if args.hierarchy_dir:
        cmd.extend(["--hierarchy-dir", args.hierarchy_dir])
    if args.verbose:
        cmd.append("--verbose")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
