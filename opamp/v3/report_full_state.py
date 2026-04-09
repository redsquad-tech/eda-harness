from __future__ import annotations

import json
from pathlib import Path

from opamp.v3.measure_core import render_full_characterization_report, run_full_characterization, summarize_full_characterization
from opamp.v3.tests._helpers import init_sky130_install


def main() -> int:
    init_sky130_install()
    result = run_full_characterization()
    summary = summarize_full_characterization(result)
    report_md = render_full_characterization_report(result, summary)

    outdir = Path("tmp/opamp_v3_full_characterization")
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "full_characterization.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (outdir / "report.md").write_text(report_md, encoding="utf-8")

    print(outdir / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
