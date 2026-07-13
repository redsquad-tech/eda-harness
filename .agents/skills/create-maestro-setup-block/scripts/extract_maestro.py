#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


BEGIN = "; BEGIN MAESTRO_SETUP"
END = "; END MAESTRO_SETUP"


def main() -> int:
    p = argparse.ArgumentParser(description="Extract the Maestro setup block and remove the temporary Cadence folder.")
    p.add_argument("--workspace", default=".")
    p.add_argument("--group", required=True)
    args = p.parse_args()

    workspace = Path(args.workspace).resolve()
    tmp = workspace / f"maestro_tmp_{args.group}"
    setup = tmp / "setup_tmp.il"
    out = workspace / "cadence_export" / "maestro_setup" / f"{args.group}.il"

    if not setup.exists():
        raise SystemExit(f"missing temporary setup file: {setup}")

    text = setup.read_text(encoding="utf-8", errors="replace")
    match = re.search(rf"^[ \t]*{re.escape(BEGIN)}[ \t]*\n(.*?)^[ \t]*{re.escape(END)}[ \t]*$", text, re.M | re.S)
    if not match:
        raise SystemExit(f"could not find MAESTRO_SETUP block in {setup}")

    block = match.group(1).strip() + "\n"
    if not block.strip():
        raise SystemExit(f"empty MAESTRO_SETUP block in {setup}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(block, encoding="utf-8")
    shutil.rmtree(tmp)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
