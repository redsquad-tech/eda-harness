from __future__ import annotations

import argparse
import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from .common import sky130_root
from .export_spice import export_spice


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_ROOT = ROOT / "opamp" / "v4" / "customer_archive_current"
SKY130_LIB_PLACEHOLDER = "__SKY130_LIB_SPICE__"


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_spice_text(text: str) -> str:
    pdk_root = sky130_root()
    lib_path = pdk_root / "libs.tech/ngspice/sky130.lib.spice"
    for src, dst in (
        (str(lib_path), SKY130_LIB_PLACEHOLDER),
        (str(lib_path.resolve()), SKY130_LIB_PLACEHOLDER),
        (str(ROOT), "__EDA_HARNESS_ROOT__"),
        (str(ROOT.resolve()), "__EDA_HARNESS_ROOT__"),
    ):
        text = text.replace(src, dst)
    return text


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _subckt_name_from_netlist(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(".SUBCKT "):
            return line.split()[1]
    raise RuntimeError(f"No .SUBCKT found in {path}")


def _tb_header(title: str, dut_relpath: str, corner: str = "tt") -> str:
    return (
        f"* {title}\n"
        f".include \"{dut_relpath}\"\n"
        f".lib {SKY130_LIB_PLACEHOLDER} {corner}\n"
        ".temp 27\n\n"
    )


def _tb_footer(op: bool = True, ac: tuple[float, float, int] | None = None) -> str:
    parts = []
    if op:
        parts.append(".op")
    if ac is not None:
        fstart, fstop, npts = ac
        parts.append(f".ac dec {npts} {fstart} {fstop}")
    parts.append(".end")
    return "\n".join(parts) + "\n"


def _instantiate_dut(subckt: str) -> str:
    return (
        f"XDUT avdd1p2 agnd vinp vinn vout in0u25_oa vbase vfeed "
        f"d_en_oa d_az_oa d_inf_oa vtest d_treset_oa d_tcki d_tcko d_tdi d_tdo {subckt}\n"
    )


def _common_sources(vdd: float = 1.8, vin: float = 0.9, iref_uA: float = 0.25) -> str:
    return (
        f"VVDD avdd1p2 0 DC {vdd}\n"
        f"VVIP vinp 0 DC {vin}\n"
        f"VIREF in0u25_oa 0 DC 0\n"
        f"IIREF in0u25_oa 0 DC {iref_uA}u\n"
        "VDEN d_en_oa 0 DC 1.8\n"
        "VDAZ d_az_oa 0 DC 0\n"
        "VDINF d_inf_oa 0 DC 1.8\n"
        "VDTR d_treset_oa 0 DC 0\n"
        "VDTCKI d_tcki 0 DC 0\n"
        "VDTDI d_tdi 0 DC 0\n"
        "RVBASE vbase 0 1e12\n"
        "RVFEED vfeed 0 1e12\n"
        "RVTEST vtest 0 1e12\n"
        "RDTCKO d_tcko 0 1e12\n"
        "RDTDO d_tdo 0 1e12\n"
    )


def _open_loop_tb(subckt: str, dut_relpath: str, *, vdd: float, temp_c: float, corner: str) -> str:
    return (
        _tb_header(f"v4 open-loop follower AC {corner} vdd={vdd} temp={temp_c}", dut_relpath, corner)
        + _common_sources(vdd=vdd)
        + "VVINN vinn 0 DC 0\n"
        + "EFB vinn 0 vout 0 1\n"
        + "CLOAD vout 0 1p\n"
        + "RLOAD vout 0 1e9\n"
        + _instantiate_dut(subckt)
        + ".save v(vout) v(vinp) i(VVDD)\n"
        + f".temp {temp_c}\n"
        + _tb_footer(op=True, ac=(1.0, 1e8, 20))
    )


def _supply_tb(subckt: str, dut_relpath: str, *, en_v: float, inf_v: float, label: str) -> str:
    return (
        _tb_header(f"v4 supply current {label}", dut_relpath)
        + (
            f"VVDD avdd1p2 0 DC 1.8\n"
            "VVIP vinp 0 DC 0.9\n"
            "VIREF in0u25_oa 0 DC 0\n"
            "IIREF in0u25_oa 0 DC 0.25u\n"
            f"VDEN d_en_oa 0 DC {en_v}\n"
            "VDAZ d_az_oa 0 DC 0\n"
            f"VDINF d_inf_oa 0 DC {inf_v}\n"
            "VDTR d_treset_oa 0 DC 0\n"
            "VDTCKI d_tcki 0 DC 0\n"
            "VDTDI d_tdi 0 DC 0\n"
            "RVINN vinn 0 1\n"
            "CLOAD vout 0 1p\n"
            "RLOAD vout 0 1e9\n"
            "RVBASE vbase 0 1e12\n"
            "RVFEED vfeed 0 1e12\n"
            "RVTEST vtest 0 1e12\n"
            "RDTCKO d_tcko 0 1e12\n"
            "RDTDO d_tdo 0 1e12\n"
        )
        + _instantiate_dut(subckt)
        + ".save i(VVDD) v(vout)\n"
        + _tb_footer(op=True)
    )


def _drive_tb(subckt: str, dut_relpath: str, *, direction: str, load_uA: float) -> str:
    if direction == "source":
        iload = f"ILOAD vout 0 DC {load_uA}u\n"
    elif direction == "sink":
        iload = f"ILOAD avdd1p2 vout DC {load_uA}u\n"
    else:
        raise ValueError(direction)
    return (
        _tb_header(f"v4 output drive {direction} {load_uA}uA", dut_relpath)
        + _common_sources(vdd=1.8, vin=0.9)
        + "VVINN vinn 0 DC 0\n"
        + "EFB vinn 0 vout 0 1\n"
        + "CLOAD vout 0 1p\n"
        + "RLOAD vout 0 1e9\n"
        + iload
        + _instantiate_dut(subckt)
        + ".save i(VVDD) v(vout)\n"
        + _tb_footer(op=True)
    )


def _readme() -> str:
    return f"""# v4 Customer SPICE Archive

Generated: `{_utc_ts()}`

This archive contains the current `v4` DUT SPICE netlist and ngspice benches for
customer-facing product metrics.

Contents:
- `spice/dut/neuron_core_oa_sky130.sp`: current top-level DUT
- `spice/testbenches/core/open_loop_*.sp`: open-loop follower benches, including PVT
- `spice/testbenches/core/supply_enabled_tt_v1p80_t27.sp`
- `spice/testbenches/core/supply_disabled_tt_v1p80_t27.sp`
- `spice/testbenches/core/drive_source_25uA_tt_v1p80_t27.sp`
- `spice/testbenches/core/drive_sink_25uA_tt_v1p80_t27.sp`

Notes:
- Replace `{SKY130_LIB_PLACEHOLDER}` with your local SKY130 ngspice library path.
- DUT netlist is exported from the current HDL21 source before archiving.
"""


def build_archive(outdir: str | None = None) -> tuple[Path, Path]:
    outroot = Path(outdir).resolve() if outdir else ARCHIVE_ROOT.resolve()
    if outroot.exists():
        shutil.rmtree(outroot)
    outroot.mkdir(parents=True, exist_ok=True)

    dut_dir = outroot / "spice" / "dut"
    tb_dir = outroot / "spice" / "testbenches" / "core"
    reports_dir = outroot / "reports"
    dut_dir.mkdir(parents=True, exist_ok=True)
    tb_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    dut_path = export_spice(dut_dir / "neuron_core_oa_sky130.sp")
    dut_path.write_text(_normalize_spice_text(dut_path.read_text(encoding="utf-8")), encoding="utf-8")
    subckt = _subckt_name_from_netlist(dut_path)
    dut_rel = "../../dut/neuron_core_oa_sky130.sp"

    _write_text(tb_dir / "open_loop_tt_v1p80_t27.sp", _open_loop_tb(subckt, dut_rel, vdd=1.8, temp_c=27.0, corner="tt"))
    _write_text(tb_dir / "supply_enabled_tt_v1p80_t27.sp", _supply_tb(subckt, dut_rel, en_v=1.8, inf_v=1.8, label="enabled"))
    _write_text(tb_dir / "supply_disabled_tt_v1p80_t27.sp", _supply_tb(subckt, dut_rel, en_v=0.0, inf_v=0.0, label="disabled"))
    _write_text(tb_dir / "drive_source_25uA_tt_v1p80_t27.sp", _drive_tb(subckt, dut_rel, direction="source", load_uA=25.0))
    _write_text(tb_dir / "drive_sink_25uA_tt_v1p80_t27.sp", _drive_tb(subckt, dut_rel, direction="sink", load_uA=25.0))

    corners = {"tt": 1.8, "ff": 1.8, "ss": 1.8}
    temps = (-40.0, 27.0, 125.0)
    vdds = (1.6, 1.8, 1.98)
    for corner, _ in corners.items():
        for vdd in vdds:
            for temp_c in temps:
                name = f"open_loop_{corner}_v{vdd:0.2f}".replace(".", "p") + f"_t{int(temp_c):+d}".replace("+", "")
                _write_text(
                    tb_dir / f"{name}.sp",
                    _open_loop_tb(subckt, dut_rel, vdd=vdd, temp_c=temp_c, corner=corner),
                )

    spec_json = ROOT / "opamp" / "v4" / "tests" / "v4_accept_spec_snapshot_metrics.json"
    if spec_json.exists():
        shutil.copy2(spec_json, reports_dir / spec_json.name)

    manifest = {
        "generated_at": _utc_ts(),
        "dut": "neuron_core_oa_sky130",
        "subckt": subckt,
        "contains": [
            {"path": "spice/dut/neuron_core_oa_sky130.sp", "kind": "dut"},
            {"path": "spice/testbenches/core/open_loop_tt_v1p80_t27.sp", "kind": "testbench"},
            {"path": "spice/testbenches/core/supply_enabled_tt_v1p80_t27.sp", "kind": "testbench"},
            {"path": "spice/testbenches/core/supply_disabled_tt_v1p80_t27.sp", "kind": "testbench"},
            {"path": "spice/testbenches/core/drive_source_25uA_tt_v1p80_t27.sp", "kind": "testbench"},
            {"path": "spice/testbenches/core/drive_sink_25uA_tt_v1p80_t27.sp", "kind": "testbench"},
            {"path": "reports/v4_accept_spec_snapshot_metrics.json", "kind": "metrics"},
        ],
    }
    _write_text(outroot / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    _write_text(outroot / "README.md", _readme())

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
