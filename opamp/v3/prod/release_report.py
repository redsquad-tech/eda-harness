from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .tests._acceptance_report import (
    AcceptanceRow,
    failing_rows,
    full_pvt_core_rows,
    full_pvt_top_rows,
    load_sweep_rows,
    reduced_acceptance_rows,
    rows_to_markdown,
    timing_mc_rows,
)


REPORT_BUILDERS = {
    "reduced": reduced_acceptance_rows,
    "full_pvt_core": full_pvt_core_rows,
    "full_pvt_top": full_pvt_top_rows,
    "load_sweep": load_sweep_rows,
    "timing_mc": timing_mc_rows,
}


def _rows_to_jsonable(rows: list[AcceptanceRow]) -> list[dict[str, object]]:
    return [asdict(r) for r in rows]


def build_report(section: str) -> dict[str, object]:
    rows = REPORT_BUILDERS[section]()
    failed = failing_rows(rows)
    return {
        "section": section,
        "total_checks": len(rows),
        "failed_checks": len(failed),
        "passed": len(failed) == 0,
        "rows": _rows_to_jsonable(rows),
    }


def write_report(section: str, outdir: Path) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    report = build_report(section)
    rows = [AcceptanceRow(**row) for row in report["rows"]]
    md_path = outdir / f"{section}.md"
    json_path = outdir / f"{section}.json"
    md_path.write_text(
        f"# {section}\n\n"
        f"- total_checks: {report['total_checks']}\n"
        f"- failed_checks: {report['failed_checks']}\n"
        f"- passed: {report['passed']}\n\n"
        + rows_to_markdown(rows),
        encoding="utf-8",
    )
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("section", choices=sorted(REPORT_BUILDERS))
    parser.add_argument("--outdir", default="tmp/opamp_v3_prod_release_report")
    args = parser.parse_args(argv)
    md_path, json_path = write_report(args.section, Path(args.outdir))
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
