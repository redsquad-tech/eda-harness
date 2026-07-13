#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shlex
import shutil
import subprocess
from pathlib import Path


def skill_str(value: Path | str) -> str:
    return '"' + str(value).replace('"', '\\"') + '"'


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def shared_fixture_name(implementation_plan: Path) -> str:
    if not implementation_plan.exists():
        raise SystemExit(f"missing implementation plan: {implementation_plan}")
    text = implementation_plan.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"(?im)^\|\s*Shared Top-Level Fixture Subckt\s*\|\s*([^|]+?)\s*\|\s*$",
        text,
    )
    if not match:
        raise SystemExit(f"missing Shared Top-Level Fixture Subckt in {implementation_plan}")
    name = match.group(1).strip().strip("`").strip()
    if not name or name.startswith("<"):
        raise SystemExit(f"invalid Shared Top-Level Fixture Subckt in {implementation_plan}: {name!r}")
    return name


def virtuoso_command(il_name: str) -> list[str]:
    direct = ["virtuoso", "-nograph", "-restore", il_name]
    if shutil.which("virtuoso"):
        return direct
    return ["bash", "-ic", "exec " + shlex.join(direct)]


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
    cell = shared_fixture_name(workspace / "testbench_implementation_plan.md")
    spectre_view = f"spectre_{group}"
    config_view = f"config_{group}"
    model_bindings = workspace / "cadence_export" / "model_bindings.il"

    if not mock.exists():
        raise SystemExit(f"missing mock device: {mock}")
    if not tb.exists():
        raise SystemExit(f"missing testbench SPICE: {tb}")
    if not model_bindings.is_file():
        raise SystemExit(
            f"missing generated model bindings: {model_bindings}; "
            "run prepare_model_bindings.py first"
        )
    tb_text = tb.read_text(encoding="utf-8", errors="replace")
    if not re.search(rf"(?im)^\s*\.SUBCKT\s+{re.escape(cell)}(?:\s|$)", tb_text):
        raise SystemExit(f"testbench {tb} does not define shared fixture .SUBCKT {cell}")
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
                tb_text.rstrip(),
                f"* END testbench {tb}",
                "",
            ]
        ),
    )
    write(cds_lib, "\n")
    write(
        il,
        f"""load({skill_str(model_bindings)})

let((cfg status sess lib cell spectreView configView maestroView testName
      generatedCornerAssignments)
  lib = {skill_str(lib)}
  cell = {skill_str(cell)}
  spectreView = {skill_str(spectre_view)}
  configView = {skill_str(config_view)}
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

  when(ddGetObj(lib cell maestroView)
    ddDeleteObj(ddGetObj(lib cell maestroView))
  )
  sess = maeOpenSetup(lib cell maestroView ?mode "a" ?allowADEXL t)
  unless(sess error("failed to open Maestro setup\\n"))
  generatedCornerAssignments = nil

  ; BEGIN MAESTRO_SETUP
  ; Add only Maestro/ADE setup code here. A later script will extract exactly
  ; the code between BEGIN MAESTRO_SETUP and END MAESTRO_SETUP.
  ; Add this group's tests to sess. Use variables already in scope:
  ; lib, cell, spectreView, configView, maestroView, testName, sess, and
  ; generatedCornerAssignments.
  ; Do not delete/open/save the shared Maestro view inside this block.
  ; END MAESTRO_SETUP

  unless(maeSaveSetup(?lib lib ?cell cell ?view maestroView ?session sess)
    error("failed to save Maestro setup\\n")
  )

  printf("maestro tmp PASS\\n")
)
exit()
""",
    )

    result = subprocess.run(virtuoso_command(il.name), cwd=out)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print(il)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
