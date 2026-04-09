from __future__ import annotations

import argparse
import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import hdl21 as h
import hdl21.sim.proto as sim_proto
from hdl21.sim.proto import to_proto

from components import require_sky130_install
from components.ngspice_netlister import _export_save_compat, write_compatible_netlist
from opamp.v1.opamp_az_top import (
    OpampAzTopClosedLoopStepTbParams,
    OpampAzTopNoiseAndOffsetTbParams,
    OpampAzTopOpenLoopTbParams,
    OpampAzTopParams,
    build_closed_loop_step_test as build_top_closed_loop_step_test,
    build_noise_and_offset_mc_test as build_top_noise_offset_mc_test,
    build_noise_and_offset_test as build_top_noise_offset_test,
    build_open_loop_test as build_top_open_loop_test,
    export_spice as export_top_spice,
)
from opamp.v1.opamp_core import (
    OpampCoreClosedLoopStepTbParams,
    OpampCoreDisabledTbParams,
    OpampCoreFollowerTbParams,
    OpampCoreOpenLoopTbParams,
    OpampCoreParams,
    _build_follower_op_tb,
    build_closed_loop_step_test as build_core_closed_loop_step_test,
    build_open_loop_test as build_core_open_loop_test,
    export_spice as export_core_spice,
)
from opamp.v1.tests.structural._helpers import init_sky130_install


ROOT = Path(__file__).resolve().parents[2]
PVT_CASES = {
    "tt_v1p80_t27": (h.pdk.Corner.TYP, 1.8, 27.0),
    "ss_v1p60_t125": (h.pdk.Corner.SLOW, 1.6, 125.0),
    "ff_v1p98_tm40": (h.pdk.Corner.FAST, 1.98, -40.0),
    "ss_v1p60_tm40": (h.pdk.Corner.SLOW, 1.6, -40.0),
    "ff_v1p98_t125": (h.pdk.Corner.FAST, 1.98, 125.0),
}


def utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_spice_text(text: str) -> str:
    install = require_sky130_install()
    lib_path = install.pdk_path / install.lib_path
    replacements = {
        str(lib_path): "__SKY130_LIB_SPICE__",
        str(lib_path.resolve()): "__SKY130_LIB_SPICE__",
        str(ROOT): "__EDA_HARNESS_ROOT__",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _export_sim_netlist(path: Path, sim) -> None:
    sim_proto.export_save = _export_save_compat
    write_compatible_netlist(to_proto(sim), path)
    path.write_text(_normalize_spice_text(path.read_text(encoding="utf-8")), encoding="utf-8")


def _export_dut_netlist(path: Path, exporter, params) -> None:
    exporter(path, params)
    path.write_text(_normalize_spice_text(path.read_text(encoding="utf-8")), encoding="utf-8")


def _bundle_readme(manifest: dict) -> str:
    return f"""# Tapeout Bundle

Generated: `{manifest["generated_at"]}`

This archive contains customer-facing SPICE netlists for the current `opamp_az_top`
design point and the supporting `opamp_core` characterization benches.

## Contents

- `spice/dut/opamp_az_top.sp`: top-level DUT netlist
- `spice/dut/opamp_core.sp`: core DUT netlist
- `spice/testbenches/core/`: core AC, swing, drive, leakage benches
- `spice/testbenches/top/`: top-level AZ nominal, reduced-PVT, and MC benches
- `manifest.json`: machine-readable file inventory

## PDK Include Placeholder

Generated netlists replace the local SKY130 model-library path with:

`__SKY130_LIB_SPICE__`

Before running `ngspice`, replace this token with your local SKY130 library file,
for example:

`/path/to/sky130.lib.spice`

## Recommended Customer Questions Covered

- Nominal core gain / GBW / PM / GM
- Core output swing and ±25 uA drive
- Core disabled leakage
- Top-level residual offset / pedestal / settling at nominal
- Top-level reduced-PVT AZ behavior
- Top-level mismatch-only MC bench template

## Notes

- The MC bench uses the `tt_mm` model section and is intended to be rerun multiple
  times to build statistics.
- Reduced-PVT benches are exported as separate SPICE files for the decision corners.
- The bundled netlists are generated from the current repository DUT defaults.
"""


def _manifest_entry(path: Path, purpose: str, kind: str) -> dict[str, str]:
    return {
        "path": str(path),
        "purpose": purpose,
        "kind": kind,
    }


def build_bundle(outdir: str) -> tuple[Path, Path]:
    init_sky130_install()
    outroot = Path(outdir).resolve()
    if outroot.exists():
        shutil.rmtree(outroot)
    outroot.mkdir(parents=True, exist_ok=True)

    spice_dut = outroot / "spice" / "dut"
    spice_core = outroot / "spice" / "testbenches" / "core"
    spice_top = outroot / "spice" / "testbenches" / "top"
    manifest_entries: list[dict[str, str]] = []

    top_params = OpampAzTopParams()
    core_params = OpampCoreParams()

    top_dut_path = spice_dut / "opamp_az_top.sp"
    core_dut_path = spice_dut / "opamp_core.sp"
    _export_dut_netlist(top_dut_path, export_top_spice, top_params)
    _export_dut_netlist(core_dut_path, export_core_spice, core_params)
    manifest_entries.append(_manifest_entry(top_dut_path.relative_to(outroot), "Top-level DUT subckt", "dut"))
    manifest_entries.append(_manifest_entry(core_dut_path.relative_to(outroot), "Core DUT subckt", "dut"))

    # Core nominal and corner benches
    core_open_nom = spice_core / "core_open_loop_tt_v1p80_t27.sp"
    _export_sim_netlist(
        core_open_nom,
        build_core_open_loop_test(
            core_params,
            OpampCoreOpenLoopTbParams(vdd=1.8, c_load=1e-12, temp_c=27.0),
            corner=h.pdk.Corner.TYP,
        ),
    )
    manifest_entries.append(_manifest_entry(core_open_nom.relative_to(outroot), "Core nominal AC bench", "testbench"))

    for name, (corner, vdd, temp_c) in {
        "core_open_loop_ss_v1p60_t125.sp": (h.pdk.Corner.SLOW, 1.6, 125.0),
        "core_open_loop_ff_v1p98_tm40.sp": (h.pdk.Corner.FAST, 1.98, -40.0),
    }.items():
        path = spice_core / name
        _export_sim_netlist(
            path,
            build_core_open_loop_test(
                core_params,
                OpampCoreOpenLoopTbParams(vdd=vdd, c_load=1e-12, temp_c=temp_c),
                corner=corner,
            ),
        )
        manifest_entries.append(_manifest_entry(path.relative_to(outroot), f"Core corner AC bench {name}", "testbench"))

    core_step = spice_core / "core_closed_loop_step_tt_v1p80_t27.sp"
    _export_sim_netlist(
        core_step,
        build_core_closed_loop_step_test(
            core_params,
            OpampCoreClosedLoopStepTbParams(vdd=1.8, c_load=1e-12, temp_c=27.0),
            corner=h.pdk.Corner.TYP,
        ),
    )
    manifest_entries.append(_manifest_entry(core_step.relative_to(outroot), "Core nominal closed-loop step bench", "testbench"))

    follower = OpampCoreFollowerTbParams(vdd=1.8, c_load=1e-12, temp_c=27.0, drive_current_uA=25.0)
    for name, sim in {
        "core_output_low_tt_v1p80_t27.sp": _build_follower_op_tb(core_params, vdd=1.8, vin=float(follower.vout_low_target), c_load=1e-12, r_probe=1e12, en_voltage=1.8, temp_c=27.0, corner=h.pdk.Corner.TYP),
        "core_output_high_tt_v1p80_t27.sp": _build_follower_op_tb(core_params, vdd=1.8, vin=float(follower.vout_high_target), c_load=1e-12, r_probe=1e12, en_voltage=1.8, temp_c=27.0, corner=h.pdk.Corner.TYP),
        "core_drive_source_25uA_tt_v1p80_t27.sp": _build_follower_op_tb(core_params, vdd=1.8, vin=float(follower.vout_mid_target), c_load=1e-12, r_probe=1e12, en_voltage=1.8, temp_c=27.0, corner=h.pdk.Corner.TYP, current_load_uA=25.0, load_mode="source"),
        "core_drive_sink_25uA_tt_v1p80_t27.sp": _build_follower_op_tb(core_params, vdd=1.8, vin=float(follower.vout_mid_target), c_load=1e-12, r_probe=1e12, en_voltage=1.8, temp_c=27.0, corner=h.pdk.Corner.TYP, current_load_uA=25.0, load_mode="sink"),
        "core_disabled_leakage_ff_v1p98_tm40.sp": _build_follower_op_tb(core_params, vdd=1.98, vin=0.4, c_load=1e-12, r_probe=1e12, en_voltage=0.0, temp_c=-40.0, corner=h.pdk.Corner.FAST),
    }.items():
        path = spice_core / name
        _export_sim_netlist(path, sim)
        manifest_entries.append(_manifest_entry(path.relative_to(outroot), f"Core operating-point bench {name}", "testbench"))

    # Top-level benches
    top_open = spice_top / "top_open_loop_proxy_tt_v1p80_t27.sp"
    _export_sim_netlist(
        top_open,
        build_top_open_loop_test(
            top_params,
            OpampAzTopOpenLoopTbParams(vdd=1.8, c_load=1e-12),
            corner=h.pdk.Corner.TYP,
        ),
    )
    manifest_entries.append(_manifest_entry(top_open.relative_to(outroot), "Top-level smoke/open-loop proxy bench", "testbench"))

    top_step = spice_top / "top_closed_loop_step_tt_v1p80_t27.sp"
    _export_sim_netlist(
        top_step,
        build_top_closed_loop_step_test(
            top_params,
            OpampAzTopClosedLoopStepTbParams(vdd=1.8, c_load=1e-12, v_step=10e-3),
            corner=h.pdk.Corner.TYP,
        ),
    )
    manifest_entries.append(_manifest_entry(top_step.relative_to(outroot), "Top-level closed-loop step bench", "testbench"))

    nominal_tb = OpampAzTopNoiseAndOffsetTbParams(vdd=1.8, temp_c=27.0)
    top_nom = spice_top / "top_noise_offset_tt_v1p80_t27.sp"
    _export_sim_netlist(top_nom, build_top_noise_offset_test(top_params, nominal_tb, corner=h.pdk.Corner.TYP))
    manifest_entries.append(_manifest_entry(top_nom.relative_to(outroot), "Top-level nominal noise/offset bench", "testbench"))

    top_mc = spice_top / "top_noise_offset_mc_tt_mm.sp"
    _export_sim_netlist(top_mc, build_top_noise_offset_mc_test(top_params, nominal_tb, model_section="tt_mm"))
    manifest_entries.append(_manifest_entry(top_mc.relative_to(outroot), "Top-level mismatch-only MC bench", "testbench"))

    for label, (corner, vdd, temp_c) in PVT_CASES.items():
        tb = OpampAzTopNoiseAndOffsetTbParams(vdd=vdd, temp_c=temp_c)
        path = spice_top / f"top_noise_offset_{label}.sp"
        _export_sim_netlist(path, build_top_noise_offset_test(top_params, tb, corner=corner))
        manifest_entries.append(_manifest_entry(path.relative_to(outroot), f"Top-level reduced-PVT noise/offset bench {label}", "testbench"))

    manifest = {
        "generated_at": utc_ts(),
        "bundle_name": outroot.name,
        "dut": "opamp_az_top",
        "contains": manifest_entries,
        "notes": {
            "sky130_lib_placeholder": "__SKY130_LIB_SPICE__",
            "mc_model_section": "tt_mm",
            "reduced_pvt_cases": list(PVT_CASES.keys()),
        },
    }
    _write_text(outroot / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write_text(outroot / "README.md", _bundle_readme(manifest))

    archive_path = outroot.with_suffix(".tar.gz")
    if archive_path.exists():
        archive_path.unlink()
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(outroot, arcname=outroot.name)
    return outroot, archive_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="tmp/opamp_v3_tapeout_bundle")
    args = parser.parse_args(argv)
    bundle_dir, archive_path = build_bundle(args.outdir)
    print(bundle_dir)
    print(archive_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
