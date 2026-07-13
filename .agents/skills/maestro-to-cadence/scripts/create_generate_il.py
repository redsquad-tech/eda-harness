#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import textwrap
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


def verify_model_bindings(config: Path, bindings: Path) -> None:
    if not config.is_file():
        raise SystemExit(f"missing model configuration: {config}")
    if not bindings.is_file():
        raise SystemExit(
            f"missing generated model bindings: {bindings}; "
            "complete the control-to-maestro model-binding step first"
        )
    text = bindings.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"(?m)^; Source SHA-256: ([0-9a-f]{64})$", text)
    if not match:
        raise SystemExit(
            f"model bindings do not contain a source hash: {bindings}; "
            "regenerate and revalidate the Maestro setup blocks"
        )
    current_hash = hashlib.sha256(config.read_bytes()).hexdigest()
    if match.group(1) != current_hash:
        raise SystemExit(
            f"model configuration changed after bindings were generated: {config}; "
            "regenerate the bindings and revalidate the Maestro setup blocks"
        )


def main() -> int:
    p = argparse.ArgumentParser(description="Create one Cadence generate.il from Maestro setup blocks.")
    p.add_argument("--workspace", default=".")
    args = p.parse_args()

    workspace = Path(args.workspace).resolve()
    export = workspace / "cadence_export"
    setup_dir = export / "maestro_setup"
    wrapper_dir = export / "spectre_wrappers"
    generate = export / "generate.il"
    mock = workspace / "mock_device.sp"
    dut_placeholder = export / "dut_placeholder.scs"
    model_config = export / "model_bindings.toml"
    model_bindings = export / "model_bindings.il"
    cell = shared_fixture_name(workspace / "testbench_implementation_plan.md")

    if not mock.exists():
        raise SystemExit(f"missing mock device: {mock}")
    verify_model_bindings(model_config, model_bindings)
    blocks = sorted(set(p.stem for p in setup_dir.glob("*.il")))
    if not blocks:
        raise SystemExit(f"no Maestro setup files in {setup_dir}")

    write(
        dut_placeholder,
        "simulator lang=spice\n"
        "* DUT implementation only; process-corner models are configured in model_bindings.toml.\n"
        ".include \"../mock_device.sp\"\n",
    )
    body = [
        f"load({skill_str(model_bindings)})",
        "",
        "let((cfg status sess lib libPath libObj cdsLib cell viewPrefix maestroView",
        "      generatedCornerAssignments allTests assignment cornerName desiredTests",
        "      disabledTests existingTest)",
        '  lib = getShellEnvVar("CADENCE_LIBRARY_NAME")',
        '  libPath = getShellEnvVar("CADENCE_LIBRARY_PATH")',
        '  viewPrefix = getShellEnvVar("CADENCE_VIEW_PREFIX")',
        '  maestroView = getShellEnvVar("CADENCE_MAESTRO_VIEW_NAME")',
        '  cdsLib = "cds.lib"',
        f"  cell = {skill_str(cell)}",
        '  unless(lib && strlen(lib) > 0 error("CADENCE_LIBRARY_NAME is not set\\n"))',
        '  unless(viewPrefix && strlen(viewPrefix) > 0 error("CADENCE_VIEW_PREFIX is not set\\n"))',
        '  unless(maestroView && strlen(maestroView) > 0 error("CADENCE_MAESTRO_VIEW_NAME is not set\\n"))',
        "  libObj = ddGetObj(lib)",
        "  if(libObj then",
        '    printf("Using existing library %s\\n" lib)',
        "  else",
        '    unless(libPath && strlen(libPath) > 0 error("Library %s does not exist and CADENCE_LIBRARY_PATH is not set\\n" lib))',
        "    libObj = ddCreateLib(lib libPath)",
        '    unless(libObj error("Failed to create library %s at %s\\n" lib libPath))',
        '    printf("Created library %s at %s\\n" lib libPath)',
        "  )",
        "",
    ]

    group_data: list[tuple[str, Path, str]] = []
    for group in blocks:
        tb = workspace / "tests" / f"{group}.sp"
        maestro = setup_dir / f"{group}.il"
        if not tb.exists():
            raise SystemExit(f"missing testbench SPICE: {tb}")
        spice = tb.read_text(encoding="utf-8", errors="replace").rstrip()
        if not re.search(rf"(?im)^\s*\.SUBCKT\s+{re.escape(cell)}(?:\s|$)", spice):
            raise SystemExit(f"testbench {tb} does not define shared fixture .SUBCKT {cell}")
        wrapper = wrapper_dir / f"{group}.scs"
        write(wrapper, "\n".join(['.include "../dut_placeholder.scs"', "", "simulator lang=spice", "", spice, ""]))
        block = maestro.read_text(encoding="utf-8", errors="replace").strip()
        if "generatedCornerAssignments" not in block:
            raise SystemExit(
                f"Maestro setup does not register corner-to-test assignments: {maestro}; "
                "regenerate this group with control-to-maestro"
            )
        group_data.append((group, wrapper, block))

    for group, wrapper, _ in group_data:
        body.append(
            f"""  let((spectreView configView)
    spectreView = strcat(viewPrefix {skill_str(f"spectre_{group}")})
    configView = strcat(viewPrefix {skill_str(f"config_{group}")})

    when(ddGetObj(lib cell spectreView) ddDeleteObj(ddGetObj(lib cell spectreView)))
    status = system(strcat("cdsTextTo5x -CDSLIB " cdsLib " -LIB " lib " -CELL " cell " -VIEW " spectreView " -LANG spectre " {skill_str(wrapper)}))
    unless(status == 0 error("cdsTextTo5x failed for {group}\\n"))

    when(ddGetObj(lib cell configView) ddDeleteObj(ddGetObj(lib cell configView)))
    cfg = hdbOpen(lib cell configView "w" "CDBA")
    unless(cfg error("failed to open config view for {group}\\n"))
    hdbSetTopCellViewName(cfg lib cell spectreView)
    hdbSetDefaultViewListString(cfg strcat(spectreView " spectre schematic veriloga ahdl"))
    hdbSetDefaultStopListString(cfg strcat(spectreView " spectre"))
    hdbSave(cfg)
    hdbClose(cfg)
  )
"""
        )

    body.extend(
        [
            "  sess = maeOpenSetup(lib cell maestroView ?mode \"a\" ?allowADEXL t)",
            '  unless(sess error("failed to open shared Maestro setup\\n"))',
            "  generatedCornerAssignments = nil",
            "",
        ]
    )

    for group, _, block in group_data:
        # The group wrapper is indented one level inside the top-level let;
        # indent its inserted setup block one additional two-space level.
        indented_block = textwrap.indent(block, "    ")
        body.append(
            f"""  let((spectreView configView testName)
    spectreView = strcat(viewPrefix {skill_str(f"spectre_{group}")})
    configView = strcat(viewPrefix {skill_str(f"config_{group}")})
    testName = {skill_str(group)}

{indented_block}
  )
"""
        )

    body.extend(
        [
            "  when(generatedCornerAssignments",
            '    allTests = maeGetSetup(?typeName "tests" ?enabled \'all ?session sess)',
            "    foreach(assignment generatedCornerAssignments",
            "      cornerName = car(assignment)",
            "      desiredTests = cadr(assignment)",
            "      disabledTests = nil",
            "      foreach(existingTest allTests",
            "        unless(member(existingTest desiredTests)",
            "          disabledTests = cons(existingTest disabledTests)",
            "        )",
            "      )",
            "      unless(maeSetCorner(cornerName ?enableTests desiredTests",
            "          ?disableTests disabledTests ?enabled t ?session sess)",
            '        error("failed to normalize tests for corner %s\\n" cornerName)',
            "      )",
            "    )",
            '    unless(maeSetSetup(?corners list("Nominal") ?enabled nil ?session sess)',
            '      error("failed to disable Nominal corner\\n")',
            "    )",
            "  )",
            "",
            "  unless(maeSaveSetup(?lib lib ?cell cell ?view maestroView ?session sess)",
            '    error("failed to save shared Maestro setup\\n")',
            "  )",
            '  printf("cadence generate PASS\\n")',
            ")",
            "exit()",
            "",
        ]
    )
    write(generate, "\n".join(body))
    print(generate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
