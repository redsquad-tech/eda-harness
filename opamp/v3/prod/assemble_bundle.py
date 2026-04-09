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
from opamp.v3.measure_core import OpampCoreDisabledTbParams, OpampCoreFollowerTbParams, OpampCoreOpenLoopTbParams, _build_follower_op_tb, run_open_loop_test
from opamp.v3.opamp_core import OpampCoreParams

from opamp.v1.tests.structural._helpers import init_sky130_install

from .opamp_az_top import (
    OpampAzTopProdClosedLoopStepTbParams,
    OpampAzTopProdNoiseAndOffsetTbParams,
    OpampAzTopProdParams,
    build_closed_loop_step_test,
    build_noise_and_offset_mc_test,
    build_noise_and_offset_test,
    export_spice as export_top_spice,
)
from .rc import CURRENT_AZ_RC_CASE, CURRENT_CORE_RC_CASE, current_rc_summary


ROOT = Path(__file__).resolve().parents[3]
PRODUCTION_ROOT = ROOT / "opamp" / "v3" / "production"
PVT_CASES = (
    ("tt_v1p60_tm40", h.pdk.Corner.TYP, 1.6, -40.0),
    ("tt_v1p60_t27", h.pdk.Corner.TYP, 1.6, 27.0),
    ("tt_v1p60_t125", h.pdk.Corner.TYP, 1.6, 125.0),
    ("tt_v1p80_tm40", h.pdk.Corner.TYP, 1.8, -40.0),
    ("tt_v1p80_t27", h.pdk.Corner.TYP, 1.8, 27.0),
    ("tt_v1p80_t125", h.pdk.Corner.TYP, 1.8, 125.0),
    ("tt_v1p98_tm40", h.pdk.Corner.TYP, 1.98, -40.0),
    ("tt_v1p98_t27", h.pdk.Corner.TYP, 1.98, 27.0),
    ("tt_v1p98_t125", h.pdk.Corner.TYP, 1.98, 125.0),
    ("ss_v1p60_tm40", h.pdk.Corner.SLOW, 1.6, -40.0),
    ("ss_v1p60_t27", h.pdk.Corner.SLOW, 1.6, 27.0),
    ("ss_v1p60_t125", h.pdk.Corner.SLOW, 1.6, 125.0),
    ("ss_v1p80_tm40", h.pdk.Corner.SLOW, 1.8, -40.0),
    ("ss_v1p80_t27", h.pdk.Corner.SLOW, 1.8, 27.0),
    ("ss_v1p80_t125", h.pdk.Corner.SLOW, 1.8, 125.0),
    ("ss_v1p98_tm40", h.pdk.Corner.SLOW, 1.98, -40.0),
    ("ss_v1p98_t27", h.pdk.Corner.SLOW, 1.98, 27.0),
    ("ss_v1p98_t125", h.pdk.Corner.SLOW, 1.98, 125.0),
    ("ff_v1p60_tm40", h.pdk.Corner.FAST, 1.6, -40.0),
    ("ff_v1p60_t27", h.pdk.Corner.FAST, 1.6, 27.0),
    ("ff_v1p60_t125", h.pdk.Corner.FAST, 1.6, 125.0),
    ("ff_v1p80_tm40", h.pdk.Corner.FAST, 1.8, -40.0),
    ("ff_v1p80_t27", h.pdk.Corner.FAST, 1.8, 27.0),
    ("ff_v1p80_t125", h.pdk.Corner.FAST, 1.8, 125.0),
    ("ff_v1p98_tm40", h.pdk.Corner.FAST, 1.98, -40.0),
    ("ff_v1p98_t27", h.pdk.Corner.FAST, 1.98, 27.0),
    ("ff_v1p98_t125", h.pdk.Corner.FAST, 1.98, 125.0),
)
LOAD_SWEEP = (
    ("cl_0p0pf", 0.0),
    ("cl_0p5pf", 0.5e-12),
    ("cl_1p0pf", 1.0e-12),
    ("cl_2p0pf", 2.0e-12),
)
LOAD_SWEEP_CASES = (
    ("tt", h.pdk.Corner.TYP, 1.8, 27.0),
    ("ss", h.pdk.Corner.SLOW, 1.6, 125.0),
    ("ff", h.pdk.Corner.FAST, 1.98, -40.0),
)
TIMING_SWEEP = (
    ("freq10k", 100e-6, 0.5e-6),
    ("freq50k", 20e-6, 0.5e-6),
    ("freq100k", 10e-6, 0.5e-6),
    ("freq200k", 5e-6, 0.5e-6),
    ("dead10ns", 20e-6, 10e-9),
    ("dead20ns", 20e-6, 20e-9),
    ("dead50ns", 20e-6, 50e-9),
)


def utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_spice_text(text: str) -> str:
    install = require_sky130_install()
    lib_path = install.pdk_path / install.lib_path
    for src in (str(lib_path), str(lib_path.resolve()), str(ROOT)):
        text = text.replace(src, "__SKY130_LIB_SPICE__" if "sky130" in src.lower() else "__EDA_HARNESS_ROOT__")
    return text


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _export_sim_netlist(path: Path, sim) -> None:
    sim_proto.export_save = _export_save_compat
    write_compatible_netlist(to_proto(sim), path)
    path.write_text(_normalize_spice_text(path.read_text(encoding="utf-8")), encoding="utf-8")


def _export_dut_netlist(path: Path, params: OpampAzTopProdParams) -> None:
    export_top_spice(path, params)
    path.write_text(_normalize_spice_text(path.read_text(encoding="utf-8")), encoding="utf-8")


def _manifest_entry(path: Path, purpose: str, kind: str) -> dict[str, str]:
    return {"path": str(path), "purpose": purpose, "kind": kind}


def _readme(manifest: dict) -> str:
    return f"""# v3 Product Tapeout Bundle

Generated: `{manifest["generated_at"]}`

This bundle exports the current `v3` product candidate:

- native auto-zero frontend from `opamp/v3/frontend_az.py`
- `v3` static core from `opamp/v3/opamp_core.py`

Current promoted RC cases:

- core: `{CURRENT_CORE_RC_CASE}`
- az: `{CURRENT_AZ_RC_CASE}`

## Main DUT

- `spice/dut/opamp_az_top_v3_prod.sp`
- `MAXIMUM_SPEC.md`

## Included Benches

- nominal top-level AZ noise/offset
- full-PVT top-level AZ noise/offset
- mismatch-only top-level MC bench
- top-level timing sweep benches
- top-level closed-loop step bench
- core full-PVT open-loop benches
- core full-PVT swing / drive / leakage benches
- core load sweep benches

## Running

All generated netlists use the placeholder:

`__SKY130_LIB_SPICE__`

Replace it with your local SKY130 model-library path before running `ngspice`.
"""


def build_bundle(outdir: str) -> tuple[Path, Path]:
    init_sky130_install()
    require_sky130_install()
    outroot = Path(outdir).resolve()
    if outroot.exists():
        shutil.rmtree(outroot)
    outroot.mkdir(parents=True, exist_ok=True)

    top_params = OpampAzTopProdParams()
    core_params = OpampCoreParams()
    spice_dut = outroot / "spice" / "dut"
    spice_core = outroot / "spice" / "testbenches" / "core"
    spice_top = outroot / "spice" / "testbenches" / "top"
    manifest_entries: list[dict[str, str]] = []

    spec_src = Path(__file__).with_name("MAXIMUM_SPEC.md")
    spec_dst = outroot / "MAXIMUM_SPEC.md"
    shutil.copy2(spec_src, spec_dst)
    manifest_entries.append(_manifest_entry(spec_dst.relative_to(outroot), "Maximum requirement subset used by acceptance tests", "spec"))

    dut_path = spice_dut / "opamp_az_top_v3_prod.sp"
    _export_dut_netlist(dut_path, top_params)
    manifest_entries.append(_manifest_entry(dut_path.relative_to(outroot), "Integrated v3 hybrid DUT", "dut"))

    nominal_tb = OpampAzTopProdNoiseAndOffsetTbParams(vdd=1.8, temp_c=27.0)
    top_nom = spice_top / "top_noise_offset_tt_v1p80_t27.sp"
    _export_sim_netlist(top_nom, build_noise_and_offset_test(top_params, nominal_tb, corner=h.pdk.Corner.TYP))
    manifest_entries.append(_manifest_entry(top_nom.relative_to(outroot), "Top-level nominal noise/offset bench", "testbench"))

    top_mc = spice_top / "top_noise_offset_mc_tt_mm.sp"
    _export_sim_netlist(top_mc, build_noise_and_offset_mc_test(top_params, nominal_tb, model_section="tt_mm"))
    manifest_entries.append(_manifest_entry(top_mc.relative_to(outroot), "Top-level mismatch-only MC bench", "testbench"))

    top_step = spice_top / "top_closed_loop_step_tt_v1p80_t27.sp"
    _export_sim_netlist(top_step, build_closed_loop_step_test(top_params, OpampAzTopProdClosedLoopStepTbParams(), corner=h.pdk.Corner.TYP))
    manifest_entries.append(_manifest_entry(top_step.relative_to(outroot), "Top-level closed-loop step bench", "testbench"))

    for label, corner, vdd, temp_c in PVT_CASES:
        tb = OpampAzTopProdNoiseAndOffsetTbParams(vdd=vdd, temp_c=temp_c)
        path = spice_top / f"top_noise_offset_{label}.sp"
        _export_sim_netlist(path, build_noise_and_offset_test(top_params, tb, corner=corner))
        manifest_entries.append(_manifest_entry(path.relative_to(outroot), f"Top-level full-PVT bench {label}", "testbench"))

    for label, period, dead_time in TIMING_SWEEP:
        tb = OpampAzTopProdNoiseAndOffsetTbParams(vdd=1.8, temp_c=27.0, period=period, dead_time=dead_time)
        path = spice_top / f"top_noise_offset_timing_{label}.sp"
        _export_sim_netlist(path, build_noise_and_offset_test(top_params, tb, corner=h.pdk.Corner.TYP))
        manifest_entries.append(_manifest_entry(path.relative_to(outroot), f"Top-level timing sweep bench {label}", "testbench"))

    from opamp.v3.measure_core import _build_follower_ac_tb

    for label, corner, vdd, temp_c in PVT_CASES:
        tb = OpampCoreOpenLoopTbParams(vdd=vdd, c_load=1e-12, temp_c=temp_c)
        sim = run_open_loop_test  # keep import used for smoke/ API continuity
        del sim
        path = spice_core / f"core_open_loop_{label}.sp"
        _export_sim_netlist(path, _build_follower_ac_tb(core_params, vdd=vdd, vin=0.9, c_load=1e-12, r_probe=1e12, en_voltage=vdd, f_start=1.0, f_stop=1e9, npts=40, temp_c=temp_c, corner=corner))
        manifest_entries.append(_manifest_entry(path.relative_to(outroot), f"v3 core full-PVT AC bench {label}", "testbench"))

        swing_follower = OpampCoreFollowerTbParams(vdd=vdd, c_load=1e-12, temp_c=temp_c, drive_current_uA=25.0)
        swing_low = spice_core / f"core_output_low_{label}.sp"
        swing_high = spice_core / f"core_output_high_{label}.sp"
        drive_source = spice_core / f"core_drive_source_25uA_{label}.sp"
        drive_sink = spice_core / f"core_drive_sink_25uA_{label}.sp"
        leakage = spice_core / f"core_disabled_leakage_{label}.sp"
        _export_sim_netlist(swing_low, _build_follower_op_tb(core_params, vdd=vdd, vin=float(swing_follower.vout_low_target), c_load=1e-12, r_probe=1e12, en_voltage=vdd, temp_c=temp_c, corner=corner))
        _export_sim_netlist(swing_high, _build_follower_op_tb(core_params, vdd=vdd, vin=float(swing_follower.vout_high_target), c_load=1e-12, r_probe=1e12, en_voltage=vdd, temp_c=temp_c, corner=corner))
        _export_sim_netlist(drive_source, _build_follower_op_tb(core_params, vdd=vdd, vin=float(swing_follower.vout_mid_target), c_load=1e-12, r_probe=1e12, en_voltage=vdd, temp_c=temp_c, corner=corner, current_load_uA=25.0, load_mode="source"))
        _export_sim_netlist(drive_sink, _build_follower_op_tb(core_params, vdd=vdd, vin=float(swing_follower.vout_mid_target), c_load=1e-12, r_probe=1e12, en_voltage=vdd, temp_c=temp_c, corner=corner, current_load_uA=25.0, load_mode="sink"))
        _export_sim_netlist(leakage, _build_follower_op_tb(core_params, vdd=vdd, vin=0.4, c_load=1e-12, r_probe=1e12, en_voltage=0.0, temp_c=temp_c, corner=corner))
        manifest_entries.append(_manifest_entry(swing_low.relative_to(outroot), f"v3 core full-PVT low-swing bench {label}", "testbench"))
        manifest_entries.append(_manifest_entry(swing_high.relative_to(outroot), f"v3 core full-PVT high-swing bench {label}", "testbench"))
        manifest_entries.append(_manifest_entry(drive_source.relative_to(outroot), f"v3 core full-PVT source-drive bench {label}", "testbench"))
        manifest_entries.append(_manifest_entry(drive_sink.relative_to(outroot), f"v3 core full-PVT sink-drive bench {label}", "testbench"))
        manifest_entries.append(_manifest_entry(leakage.relative_to(outroot), f"v3 core full-PVT disabled-leakage bench {label}", "testbench"))

    for prefix, corner, vdd, temp_c in LOAD_SWEEP_CASES:
        follower = OpampCoreFollowerTbParams(vdd=vdd, c_load=1e-12, temp_c=temp_c, drive_current_uA=25.0)
        for load_label, c_load in LOAD_SWEEP:
            ac_path = spice_core / f"core_open_loop_{prefix}_{load_label}.sp"
            swing_path = spice_core / f"core_output_swing_{prefix}_{load_label}.sp"
            _export_sim_netlist(ac_path, _build_follower_ac_tb(core_params, vdd=vdd, vin=0.9, c_load=c_load, r_probe=1e12, en_voltage=vdd, f_start=1.0, f_stop=1e9, npts=40, temp_c=temp_c, corner=corner))
            _export_sim_netlist(swing_path, _build_follower_op_tb(core_params, vdd=vdd, vin=float(follower.vout_low_target), c_load=c_load, r_probe=1e12, en_voltage=vdd, temp_c=temp_c, corner=corner))
            manifest_entries.append(_manifest_entry(ac_path.relative_to(outroot), f"v3 core load-sweep AC bench {prefix} {load_label}", "testbench"))
            manifest_entries.append(_manifest_entry(swing_path.relative_to(outroot), f"v3 core load-sweep swing bench {prefix} {load_label}", "testbench"))

    manifest = {
        "generated_at": utc_ts(),
        "bundle_name": outroot.name,
        "dut": "opamp_az_top_v3_prod",
        "rc_summary": current_rc_summary(),
        "contains": manifest_entries,
    }
    _write_text(outroot / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write_text(outroot / "README.md", _readme(manifest))

    archive = outroot.with_suffix(".tar.gz")
    if archive.exists():
        archive.unlink()
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(outroot, arcname=outroot.name)
    return outroot, archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default=str(PRODUCTION_ROOT / "opamp_v3_prod_bundle"))
    args = parser.parse_args(argv)
    outdir, archive = build_bundle(args.outdir)
    print(outdir)
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
