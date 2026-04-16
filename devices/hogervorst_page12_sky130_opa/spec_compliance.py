import json
import math
from pathlib import Path

from .measure import run_spec_compliance


ROOT = Path(__file__).resolve().parent


def _fmt(value):
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if abs(value) >= 1e3 or (abs(value) > 0 and abs(value) < 1e-3):
            return f"{value:.4e}"
        return f"{value:.6f}"
    return str(value)


def _render_md(payload: dict) -> str:
    lines = [
        "# opamp/v4 Spec Compliance",
        "",
        "## Nominal Open-Loop",
        "",
    ]
    for key, value in payload["nominal_open_loop"].items():
        lines.append(f"- `{key}`: `{_fmt(value)}`")

    lines += [
        "",
        "## Supply Current",
        "",
        "Enabled:",
    ]
    for key, value in payload["enabled_current"].items():
        lines.append(f"- `{key}`: `{_fmt(value)}`")
    lines += [
        "",
        "Disabled:",
    ]
    for key, value in payload["disabled_current"].items():
        lines.append(f"- `{key}`: `{_fmt(value)}`")

    lines += [
        "",
        "## Output Drive",
        "",
        "High / source 20 uA:",
    ]
    for key, value in payload["output_drive_high"].items():
        lines.append(f"- `{key}`: `{_fmt(value)}`")
    lines += [
        "",
        "Low / sink 20 uA:",
    ]
    for key, value in payload["output_drive_low"].items():
        lines.append(f"- `{key}`: `{_fmt(value)}`")

    lines += [
        "",
        "## CL Sweep",
        "",
        "| CL (F) | AOL (dB) | GBW (Hz) | PM (deg) | GM (dB) | IQ (uA) | Vout (V) |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["cl_sweep"]:
        lines.append(
            f"| `{_fmt(row['c_load_f'])}` | `{_fmt(row['aol_db'])}` | `{_fmt(row['gbw_hz'])}` | "
            f"`{_fmt(row['phase_margin_deg'])}` | `{_fmt(row['gain_margin_db'])}` | "
            f"`{_fmt(row['iq_uA'])}` | `{_fmt(row['vout_dc'])}` |"
        )

    lines += [
        "",
        "## PVT Open-Loop",
        "",
        "Reduced compliance subset: full `TT` grid over `VDD x Temp`, plus nominal `FF` and `SS`.",
        "",
        "| Corner | VDD | Temp C | AOL dB | GBW Hz | PM deg | GM dB | IQ uA | Vout V |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["pvt_open_loop"]:
        lines.append(
            f"| `{row['corner']}` | `{_fmt(row['vdd'])}` | `{_fmt(row['temp_c'])}` | `{_fmt(row['aol_db'])}` | "
            f"`{_fmt(row['gbw_hz'])}` | `{_fmt(row['phase_margin_deg'])}` | `{_fmt(row['gain_margin_db'])}` | "
            f"`{_fmt(row['iq_uA'])}` | `{_fmt(row['vout_dc'])}` |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    payload = run_spec_compliance(output_dir=ROOT)
    md_path = ROOT / "spec_compliance_v4.md"
    md_path.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps({"json": str(ROOT / "spec_compliance_v4.json"), "md": str(md_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
