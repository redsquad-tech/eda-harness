from __future__ import annotations

import argparse
import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from .assemble_bundle import build_bundle


ROOT = Path(__file__).resolve().parents[3]
PRODUCTION_ROOT = ROOT / "opamp" / "v3" / "production"
DEFAULT_BASE_BUNDLE = PRODUCTION_ROOT / "opamp_v3_prod_bundle"
DEFAULT_REPORT_DIR = PRODUCTION_ROOT / "release_report"


METRIC_DISPLAY_NAMES = {
    "core.aol_db": "Open-loop gain",
    "core.gbw_hz": "GBW",
    "core.phase_margin_deg": "Phase margin",
    "core.gain_margin_db": "Gain margin",
    "core.iq_uA": "Quiescent current, enabled",
    "core.vout_low_actual": "Output compliant swing low",
    "core.vout_high_actual": "Output compliant swing high",
    "core.vout_source": "Output voltage while sourcing 25 uA",
    "core.vout_sink": "Output voltage while sinking 25 uA",
    "core.disabled_leakage_nA": "Disabled leakage current",
    "top.residual_offset_uV": "Residual input-referred offset after AZ",
    "top.pedestal_mid50_uV": "Pedestal-equivalent input error at nominal",
    "top.settling_mid50_uV": "Hold droop contribution per AZ cycle",
    "top.offset_mean_uV": "MC residual offset mean",
    "top.offset_stddev_uV": "MC residual offset stddev",
    "top.residual_offset_pass_rate": "MC residual offset pass rate",
    "top.residual_offset_p99_uV": "MC residual offset p99",
    "top.pedestal_mid50_p99_uV": "MC pedestal-equivalent input error p99",
    "top.settling_mid50_p99_uV": "MC hold droop contribution p99",
}


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_reduced_report(report_dir: Path) -> dict:
    path = report_dir / "reduced.json"
    if not path.exists():
        raise FileNotFoundError(
            f"required report not found: {path}. "
            "Run `python3 -m opamp.v3.prod.release_report reduced` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _need_have_rows(report: dict) -> list[dict[str, str]]:
    priority = [
        "core.aol_db",
        "core.gbw_hz",
        "core.phase_margin_deg",
        "core.gain_margin_db",
        "core.iq_uA",
        "core.vout_low_actual",
        "core.vout_high_actual",
        "core.vout_source",
        "core.vout_sink",
        "core.disabled_leakage_nA",
        "top.residual_offset_uV",
        "top.pedestal_mid50_uV",
        "top.settling_mid50_uV",
        "top.offset_mean_uV",
        "top.offset_stddev_uV",
        "top.residual_offset_pass_rate",
        "top.residual_offset_p99_uV",
        "top.pedestal_mid50_p99_uV",
        "top.settling_mid50_p99_uV",
    ]
    chosen: list[dict[str, str]] = []
    used = set()
    for metric in priority:
        for row in report["rows"]:
            if row["metric"] == metric and row["metric"] not in used:
                chosen.append(
                    {
                        "name": row.get("metric_name", METRIC_DISPLAY_NAMES.get(row["metric"], row["metric"])),
                        "need": row["requirement"],
                        "have": row["measured"],
                    }
                )
                used.add(row["metric"])
                break
    return chosen


def _rows_md(rows: list[dict[str, str]]) -> str:
    lines = [
        "| Name | Need | Have |",
        "|---|---|---:|",
    ]
    for row in rows:
        lines.append(f"| {row['name']} | `{row['need']}` | `{row['have']}` |")
    return "\n".join(lines)


def _readme(rows: list[dict[str, str]], spice_only: bool) -> str:
    extra_files = ""
    if spice_only:
        extra_files += "- `reports/reduced.md`: latest reduced acceptance report\n"
        extra_files += "- `reports/reduced.json`: machine-readable reduced acceptance report\n"
    else:
        extra_files += "- `tests/`: acceptance tests used for release gating\n"
        extra_files += "- `source/`: source files for the current production DUT and RC config\n"
        extra_files += "- `reports/reduced.md`: latest reduced acceptance report\n"
        extra_files += "- `reports/reduced.json`: machine-readable reduced acceptance report\n"
    return f"""# v3 Product Customer Archive

Generated: `{_utc_ts()}`

This archive contains the current `v3/prod` integrated device, SPICE benches,
the latest reduced acceptance report, and {"SPICE-only collateral" if spice_only else "acceptance collateral"}.

## Architecture

- native AZ frontend: `opamp/v3/frontend_az.py`
- static core: `opamp/v3/opamp_core.py`
- integrated production DUT: `opamp/v3/prod/components/opamp_az_top.py`
- promoted RC configuration: `opamp/v3/prod/rc/`

## Files

- `spice/dut/opamp_az_top_v3_prod.sp`: main DUT netlist
- `spice/testbenches/core/`: full-PVT core benches, load sweep, drive, leakage
- `spice/testbenches/top/`: top-level AZ nominal/PVT/timing/MC benches
{extra_files}- `MAXIMUM_SPEC.md`: maximum requirement subset used for acceptance
- `manifest.json`: bundle manifest

## Current Need / Have Table

{_rows_md(rows)}

## Notes

- SPICE netlists use `__SKY130_LIB_SPICE__` placeholder for the SKY130 model path.
- Replace it with your local SKY130 library path before running `ngspice`.
"""


def build_customer_archive(outdir: str, report_dir: str | None = None, spice_only: bool = False) -> tuple[Path, Path]:
    outroot = Path(outdir).resolve()
    report_root = Path(report_dir).resolve() if report_dir else DEFAULT_REPORT_DIR.resolve()

    base_bundle, _ = build_bundle(str(DEFAULT_BASE_BUNDLE))
    report = _load_reduced_report(report_root)
    rows = _need_have_rows(report)

    if outroot.exists():
        shutil.rmtree(outroot)
    shutil.copytree(base_bundle, outroot)

    if not spice_only:
        tests_dst = outroot / "tests"
        tests_dst.mkdir(parents=True, exist_ok=True)
        for src in sorted((ROOT / "opamp" / "v3" / "prod" / "tests").glob("*.py")):
            shutil.copy2(src, tests_dst / src.name)

        src_dst = outroot / "source"
        src_dst.mkdir(parents=True, exist_ok=True)
        for src in [
            ROOT / "opamp" / "v3" / "frontend_az.py",
            ROOT / "opamp" / "v3" / "opamp_core.py",
            ROOT / "opamp" / "v3" / "prod" / "opamp_az_top.py",
            ROOT / "opamp" / "v3" / "prod" / "rc.py",
        ]:
            shutil.copy2(src, src_dst / src.name)

    reports_dst = outroot / "reports"
    reports_dst.mkdir(parents=True, exist_ok=True)
    for name in ("reduced.md", "reduced.json"):
        shutil.copy2(report_root / name, reports_dst / name)

    manifest_path = outroot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["customer_archive"] = {"spice_only": spice_only}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    (outroot / "README.md").write_text(_readme(rows, spice_only), encoding="utf-8")
    archive = outroot.with_suffix(".tar.gz")
    if archive.exists():
        archive.unlink()
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(outroot, arcname=outroot.name)
    return outroot, archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default=str(PRODUCTION_ROOT / "customer_archive"))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--spice-only", action="store_true")
    args = parser.parse_args(argv)
    outroot, archive = build_customer_archive(args.outdir, args.report_dir, args.spice_only)
    print(outroot)
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
