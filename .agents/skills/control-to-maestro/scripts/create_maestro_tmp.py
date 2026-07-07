#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def skill_str(value: Path | str) -> str:
    return '"' + str(value).replace('"', '\\"') + '"'


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Create a minimal temporary Cadence setup for one SPICE testbench.")
    p.add_argument("--workspace", default=".")
    p.add_argument("--group", required=True)
    p.add_argument("--mock-device", required=True)
    p.add_argument("--testbench-sp", required=True)
    args = p.parse_args()

    workspace = Path(args.workspace).resolve()
    group = args.group
    mock = (workspace / args.mock_device).resolve() if not Path(args.mock_device).is_absolute() else Path(args.mock_device)
    tb = (workspace / args.testbench_sp).resolve() if not Path(args.testbench_sp).is_absolute() else Path(args.testbench_sp)
    out = workspace / f"maestro_tmp_{group}"
    lib = f"tmp_{group}_lib"
    cell = f"{group}_fixture"
    view = f"spectre_{group}"

    if not mock.exists():
        raise SystemExit(f"missing mock device: {mock}")
    if not tb.exists():
        raise SystemExit(f"missing testbench SPICE: {tb}")
    shutil.rmtree(out, ignore_errors=True)

    wrapper = out / "wrapper.scs"
    cds_lib = out / "cds.lib"
    il = out / "setup_tmp.il"
    lib_path = out / lib

    write(
        wrapper,
        "\n".join(
            [
                "simulator lang=spice",
                f"* BEGIN mock {mock}",
                mock.read_text(encoding="utf-8", errors="replace").rstrip(),
                f"* END mock {mock}",
                "",
                f"* BEGIN testbench {tb}",
                tb.read_text(encoding="utf-8", errors="replace").rstrip(),
                f"* END testbench {tb}",
                "",
            ]
        ),
    )
    write(cds_lib, "\n")
    write(
        il,
        f"""let((cfg status lib cell spectreView configView maestroView testName)
  lib = {skill_str(lib)}
  cell = {skill_str(cell)}
  spectreView = {skill_str(view)}
  configView = "config"
  maestroView = "maestro"
  testName = {skill_str(group)}

  unless(ddGetObj(lib)
    ddCreateLib(lib {skill_str(lib_path)})
  )
  unless(ddGetObj(lib) error("failed to create library\\n"))

  when(ddGetObj(lib cell spectreView)
    ddDeleteObj(ddGetObj(lib cell spectreView))
  )
  status = system(strcat(
    "cdsTextTo5x -CDSLIB " {skill_str(cds_lib)}
    " -LIB " lib
    " -CELL " cell
    " -VIEW " spectreView
    " -LANG spectre " {skill_str(wrapper)}
  ))
  unless(status == 0 error("cdsTextTo5x failed\\n"))

  when(ddGetObj(lib cell configView)
    ddDeleteObj(ddGetObj(lib cell configView))
  )
  cfg = hdbOpen(lib cell configView "w" "CDBA")
  unless(cfg error("failed to open config view\\n"))
  hdbSetTopCellViewName(cfg lib cell spectreView)
  hdbSetDefaultViewListString(cfg strcat(spectreView " spectre schematic veriloga ahdl"))
  hdbSetDefaultStopListString(cfg strcat(spectreView " spectre"))
  hdbSave(cfg)
  hdbClose(cfg)

  ; BEGIN MAESTRO_SETUP
  ; Add only Maestro/ADE setup code here. A later script will extract exactly
  ; the code between BEGIN MAESTRO_SETUP and END MAESTRO_SETUP.
  ; Use variables already in scope: lib, cell, configView, maestroView, testName.
  ; END MAESTRO_SETUP

  printf("maestro tmp PASS\\n")
)
exit()
""",
    )

    result = subprocess.run(["virtuoso", "-nograph", "-restore", il.name], cwd=out)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print(il)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
