#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


def skill_str(value: Path | str) -> str:
    return '"' + str(value).replace('"', '\\"') + '"'


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fixture_cell(spice: str, group: str) -> str:
    match = re.search(r"(?im)^\s*\.SUBCKT\s+(\S+)", spice)
    return match.group(1) if match else f"{group}_fixture"


def main() -> int:
    p = argparse.ArgumentParser(description="Create one Cadence generate.il from Maestro setup blocks.")
    p.add_argument("--workspace", default=".")
    args = p.parse_args()

    workspace = Path(args.workspace).resolve()
    export = workspace / "cadence_export"
    setup_dir = export / "maestro_setup"
    wrapper_dir = export / "spectre_wrappers"
    lib = f"{workspace.name}_acceptance"
    cds_lib = workspace / "cds.lib"
    generate = export / "generate.il"
    mock = workspace / "mock_device.sp"
    dut_placeholder = export / "dut_placeholder.scs"
    rel_lib_path = Path("cadence_export") / lib
    rel_cds_lib = Path("cds.lib")

    if not mock.exists():
        raise SystemExit(f"missing mock device: {mock}")
    blocks = sorted(set(p.stem for p in setup_dir.glob("*.il")))
    if not blocks:
        raise SystemExit(f"no Maestro setup files in {setup_dir}")

    write(cds_lib, "\n")
    write(dut_placeholder, "simulator lang=spice\n.include \"../mock_device.sp\"\n")
    body = [
        "let((cfg status lib libPath cdsLib)",
        f"  lib = {skill_str(lib)}",
        f"  libPath = {skill_str(rel_lib_path)}",
        f"  cdsLib = {skill_str(rel_cds_lib)}",
        "  unless(ddGetObj(lib) ddCreateLib(lib libPath))",
        "  unless(ddGetObj(lib) error(\"failed to create library\\n\"))",
        "",
    ]

    for group in blocks:
        tb = workspace / "tests" / f"{group}.sp"
        maestro = setup_dir / f"{group}.il"
        if not tb.exists():
            raise SystemExit(f"missing testbench SPICE: {tb}")
        spice = tb.read_text(encoding="utf-8", errors="replace").rstrip()
        cell = fixture_cell(spice, group)
        wrapper = wrapper_dir / f"{group}.scs"
        rel_wrapper = Path("cadence_export") / "spectre_wrappers" / f"{group}.scs"
        write(wrapper, "\n".join(['.include "../dut_placeholder.scs"', "", "simulator lang=spice", "", spice, ""]))
        block = maestro.read_text(encoding="utf-8", errors="replace").strip()
        body.append(
            f"""  let((cell spectreView configView maestroView testName)
    cell = {skill_str(cell)}
    spectreView = "spectre"
    configView = "config"
    maestroView = "maestro"
    testName = {skill_str(group)}

    when(ddGetObj(lib cell spectreView) ddDeleteObj(ddGetObj(lib cell spectreView)))
    status = system(strcat("cdsTextTo5x -CDSLIB " cdsLib " -LIB " lib " -CELL " cell " -VIEW " spectreView " -LANG spectre " {skill_str(rel_wrapper)}))
    unless(status == 0 error("cdsTextTo5x failed for {group}\\n"))

    when(ddGetObj(lib cell configView) ddDeleteObj(ddGetObj(lib cell configView)))
    cfg = hdbOpen(lib cell configView "w" "CDBA")
    unless(cfg error("failed to open config view for {group}\\n"))
    hdbSetTopCellViewName(cfg lib cell spectreView)
    hdbSetDefaultViewListString(cfg strcat(spectreView " spectre schematic veriloga ahdl"))
    hdbSetDefaultStopListString(cfg strcat(spectreView " spectre"))
    hdbSave(cfg)
    hdbClose(cfg)

{block}
  )
"""
        )

    body.extend(['  printf("cadence generate PASS\\n")', ")", "exit()", ""])
    write(generate, "\n".join(body))
    print(generate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
