from __future__ import annotations

import argparse
import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import hdl21 as h
import hdl21.sim.proto as sim_proto
from hdl21.sim import Save, Sim, Tran
from hdl21.sim.proto import to_proto

from components.ngspice_netlister import _export_save_compat, write_compatible_netlist
from opamp.v1.tests.structural._helpers import init_sky130_install
from opamp.v3.measure_core import (
    OpampCoreOpenLoopTbParams,
    _build_open_loop_biased_ac_tb,
)
from opamp.v3.opamp_az_top import (
    OpampAzHoldTbParams,
    OpampAzTopParams,
    export_spice as export_top_spice,
    opamp_az_top,
)
from opamp.v3.opamp_core import OpampCoreParams, opamp_core
from opamp.v3.prod.rc import current_core_params
from opamp.v3.tests.test_rc_probe_az_residual_offset import _build_follower_hold_test
from opamp.v3.common import require_sky130_install


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_ROOT = ROOT / "opamp" / "v3" / "customer_archive_current"


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_spice_text(text: str) -> str:
    install = require_sky130_install()
    lib_path = install.pdk_path / install.lib_path
    for src in (str(lib_path), str(lib_path.resolve()), str(ROOT), str(ROOT.resolve())):
        text = text.replace(src, "__SKY130_LIB_SPICE__" if "sky130" in src.lower() else "__EDA_HARNESS_ROOT__")
    return text


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _export_sim_netlist(path: Path, sim: Sim) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sim_proto.export_save = _export_save_compat
    write_compatible_netlist(to_proto(sim), path)
    path.write_text(_normalize_spice_text(path.read_text(encoding="utf-8")), encoding="utf-8")


def _export_dut_netlist(path: Path, mod: h.Module) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        h.netlist(h.elaborate(mod), f, fmt="spice")
    path.write_text(_normalize_spice_text(path.read_text(encoding="utf-8")), encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _current_top_params() -> OpampAzTopParams:
    return OpampAzTopParams(opamp_core_params=current_core_params())


def _build_az_mc_test(
    dut_params: OpampAzTopParams,
    tb_params: OpampAzHoldTbParams,
    *,
    model_section: str = "tt_mm",
) -> Sim:
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)
    t_az = float(tb_params.t_az)
    t_lat = float(tb_params.t_lat)
    t_inf = float(tb_params.t_inf)
    tstop = t_az + t_lat + t_inf

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, den, daz, dinf, vdd = h.Signals(7)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        vden = h.Vdc(dc=tb_params.vdd)(p=den, n=VSS)
        vdaz = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=t_az, rise=20e-9, fall=20e-9, width=tstop, period=2 * tstop)(p=daz, n=VSS)
        vdinf = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=t_az + t_lat, rise=20e-9, fall=20e-9, width=t_inf, period=2 * tstop)(p=dinf, n=VSS)
        vvin = h.Vdc(dc=tb_params.vin)(p=vinp, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, D_EN_OA=den, D_AZ_OA=daz, D_INF_OA=dinf, VDD=vdd, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=tstop, tstep=float(tb_params.tstep)),
            Save("time, v(xtop.vout), v(xtop.vinn), v(xtop.dinf)"),
            h.sim.Lib(install.pdk_path / install.lib_path, model_section),
        ],
    )


def _readme(open_loop: dict, residual: dict, hold: dict) -> str:
    return f"""# v3 Customer SPICE Archive

Generated: `{_utc_ts()}`

This archive contains the current `v3` DUT netlists and the exact SPICE benches
used for quick customer-facing characterization.

## DUT

- `spice/dut/opamp_az_top_v3.sp`: full current auto-zero top-level DUT
- `spice/dut/opamp_core_v3.sp`: current static core used inside the top-level DUT

## Included SPICE Benches

- `spice/testbenches/core/core_open_loop_tt_v1p80_t27.sp`
  Current `TT` biased open-loop AC bench for `AOL / GBW / PM / GM / IQ`
- `spice/testbenches/top/top_az_residual_offset_tt_v1p80_t27.sp`
  Current residual-offset-after-AZ bench
- `spice/testbenches/top/top_az_hold_200us_tt_v1p80_t27.sp`
  Current 200 us hold bench
- `spice/testbenches/top/top_az_mc_tt_mm.sp`
  Current mismatch-only top-level MC bench

## Quick Metrics

### Core `TT`, `VDD=1.8 V`, `27 C`, `CL=1 pF`

| Metric | Value | Status |
|---|---:|---|
| Open-loop gain | `{open_loop["aol_db"]:.2f} dB` | pass vs `>= 65 dB` |
| GBW | `{open_loop["gbw_hz"]:.1f} Hz` | fail vs `>= 300 kHz` |
| Phase margin | `{open_loop["phase_margin_deg"]:.2f} deg` | fail vs `>= 30 deg` |
| Gain margin | `{open_loop["gain_margin_db"]:.2f} dB` | fail vs `>= 5 dB` |
| Enabled current | `{open_loop["iq_uA"]:.3f} uA` | pass vs `<= 20 uA` |

### Full DUT `TT`, `VDD=1.8 V`, `27 C`

| Metric | Value | Status |
|---|---:|---|
| Residual offset after AZ | `{residual["residual_offset_uV"]:.2f} uV` | fail vs `<= 250 uV` |
| Hold drift over 200 us | `{hold["vout_drift_V"]:.6f} V` | fail vs `<= 50 uV eq.` |

## Notes

- All SPICE netlists use `__SKY130_LIB_SPICE__` as the SKY130 model-path placeholder.
- Replace it with your local SKY130 ngspice library path before running.
- `top_az_mc_tt_mm.sp` is the mismatch-only Monte Carlo bench collateral requested for customer review.
"""


def build_archive(outdir: str | None = None) -> tuple[Path, Path]:
    init_sky130_install()
    require_sky130_install()

    outroot = Path(outdir).resolve() if outdir else ARCHIVE_ROOT.resolve()
    if outroot.exists():
        shutil.rmtree(outroot)
    outroot.mkdir(parents=True, exist_ok=True)

    top_params = _current_top_params()
    core_params = OpampCoreParams()

    dut_dir = outroot / "spice" / "dut"
    tb_core_dir = outroot / "spice" / "testbenches" / "core"
    tb_top_dir = outroot / "spice" / "testbenches" / "top"

    top_dut = dut_dir / "opamp_az_top_v3.sp"
    core_dut = dut_dir / "opamp_core_v3.sp"
    export_top_spice(top_dut, top_params)
    top_dut.write_text(_normalize_spice_text(top_dut.read_text(encoding="utf-8")), encoding="utf-8")
    _export_dut_netlist(core_dut, opamp_core(core_params))

    core_open_loop = _build_open_loop_biased_ac_tb(
        core_params,
        vdd=1.8,
        c_load=1e-12,
        r_probe=1e12,
        v_cm=0.9,
        f_start=1.0,
        f_stop=1e8,
        npts=20,
        temp_c=27.0,
        corner=h.pdk.Corner.TYP,
    )
    _export_sim_netlist(tb_core_dir / "core_open_loop_tt_v1p80_t27.sp", core_open_loop)

    hold_tb = OpampAzHoldTbParams(vin=0.9, t_inf=260e-6)
    _export_sim_netlist(
        tb_top_dir / "top_az_residual_offset_tt_v1p80_t27.sp",
        _build_follower_hold_test(top_params, hold_tb, corner=h.pdk.Corner.TYP),
    )
    from opamp.v3.opamp_az_top import build_hold_test

    _export_sim_netlist(
        tb_top_dir / "top_az_hold_200us_tt_v1p80_t27.sp",
        build_hold_test(top_params, hold_tb, corner=h.pdk.Corner.TYP),
    )
    _export_sim_netlist(
        tb_top_dir / "top_az_mc_tt_mm.sp",
        _build_az_mc_test(top_params, hold_tb, model_section="tt_mm"),
    )

    open_loop = _load_json(ROOT / "opamp" / "v3" / "tests" / "rc_probe_open_loop_metrics.json")
    residual = _load_json(ROOT / "opamp" / "v3" / "tests" / "rc_probe_az_residual_offset_metrics.json")
    hold = _load_json(ROOT / "opamp" / "v3" / "tests" / "rc_probe_az_hold_200us_metrics.json")

    manifest = {
        "generated_at": _utc_ts(),
        "dut": "opamp_az_top_v3",
        "contains": [
            {"path": "spice/dut/opamp_az_top_v3.sp", "kind": "dut"},
            {"path": "spice/dut/opamp_core_v3.sp", "kind": "dut"},
            {"path": "spice/testbenches/core/core_open_loop_tt_v1p80_t27.sp", "kind": "testbench"},
            {"path": "spice/testbenches/top/top_az_residual_offset_tt_v1p80_t27.sp", "kind": "testbench"},
            {"path": "spice/testbenches/top/top_az_hold_200us_tt_v1p80_t27.sp", "kind": "testbench"},
            {"path": "spice/testbenches/top/top_az_mc_tt_mm.sp", "kind": "testbench"},
            {"path": "reports/rc_probe_open_loop_metrics.json", "kind": "metrics"},
            {"path": "reports/rc_probe_az_residual_offset_metrics.json", "kind": "metrics"},
            {"path": "reports/rc_probe_az_hold_200us_metrics.json", "kind": "metrics"},
        ],
    }
    _write_text(outroot / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write_text(outroot / "README.md", _readme(open_loop, residual, hold))

    reports = outroot / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "opamp" / "v3" / "tests" / "rc_probe_open_loop_metrics.json", reports / "rc_probe_open_loop_metrics.json")
    shutil.copy2(ROOT / "opamp" / "v3" / "tests" / "rc_probe_az_residual_offset_metrics.json", reports / "rc_probe_az_residual_offset_metrics.json")
    shutil.copy2(ROOT / "opamp" / "v3" / "tests" / "rc_probe_az_hold_200us_metrics.json", reports / "rc_probe_az_hold_200us_metrics.json")

    archive = outroot.with_suffix(".tar.gz")
    if archive.exists():
        archive.unlink()
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(outroot, arcname=outroot.name)
    return outroot, archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default=str(ARCHIVE_ROOT))
    args = parser.parse_args(argv)
    outroot, archive = build_archive(args.outdir)
    print(outroot)
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
