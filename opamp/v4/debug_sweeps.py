import json
import math
from pathlib import Path

from .measure import run_debug_sweeps, run_stage_gain_partition_sweep


ROOT = Path(__file__).resolve().parent


def _fmt(value):
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if abs(value) >= 1e3 or (abs(value) > 0 and abs(value) < 1e-3):
            return f"{value:.4e}"
        return f"{value:.6f}"
    return str(value)


def _render_sweep_section(title: str, sweep: dict) -> list[str]:
    rows = [
        f"## {title}",
        "",
        "| Input | VOUT | VOUT_INT | DRV_P | DRV_N | VGP | VGN | IQ uA |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    input_key = "vinp_V" if sweep["sweep_input"] == "vinp" else "vinn_V"
    for row in sweep["rows"]:
        rows.append(
            f"| `{_fmt(row[input_key])}` | `{_fmt(row['vout_V'])}` | `{_fmt(row['vout_int_V'])}` | "
            f"`{_fmt(row['drv_p_V'])}` | `{_fmt(row['drv_n_V'])}` | `{_fmt(row['vgp_V'])}` | "
            f"`{_fmt(row['vgn_V'])}` | `{_fmt(row['iq_uA'])}` |"
        )
    rows += ["", "Summary:"]
    for key, value in sweep["summary"].items():
        rows.append(f"- `{key}`: `{_fmt(value)}`")
    rows.append("")
    return rows


def _render_feedback_section(metrics: list[dict]) -> list[str]:
    rows = [
        "## Unity Feedback Sense Check",
        "",
    ]
    for topo in metrics:
        rows += [
            f"### {topo['name']}",
            "",
            f"- `feedback_to`: `{topo['feedback_to']}`",
            f"- `drive_input`: `{topo['drive_input']}`",
        ]
        for key, value in topo["summary"].items():
            rows.append(f"- `{key}`: `{_fmt(value)}`")
        rows += [
            "",
            "| Drive | VOUT | VOUT_INT | Tracking Error | DRV_P | DRV_N | VGP | VGN |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        drive_key = "vinp_V" if topo["drive_input"] == "vinp" else "vinn_V"
        for row in topo["rows"]:
            rows.append(
                f"| `{_fmt(row[drive_key])}` | `{_fmt(row['vout_V'])}` | `{_fmt(row['vout_int_V'])}` | "
                f"`{_fmt(row['tracking_error_V'])}` | `{_fmt(row['drv_p_V'])}` | `{_fmt(row['drv_n_V'])}` | "
                f"`{_fmt(row['vgp_V'])}` | `{_fmt(row['vgn_V'])}` |"
            )
        rows.append("")
    return rows


def _render_md(payload: dict) -> str:
    lines = [
        "# opamp/v4 Debug Sweeps",
        "",
        "Named sweep set for fast bring-up debugging of polarity, internal node response, and unity-feedback sense.",
        "",
    ]
    lines += _render_sweep_section("Input To Output Polarity: sweep VINP", payload["input_to_output_polarity_vinp"])
    lines += _render_sweep_section("Input To Output Polarity: sweep VINN", payload["input_to_output_polarity_vinn"])
    lines += _render_feedback_section(payload["unity_feedback_sense_check"])
    part = payload["stage_gain_partition_sweep"]
    lines += [
        "## Stage Gain Partition",
        "",
        "### Frontend To DRV",
        "",
        "| VINP | DRV_P | DRV_N | VOUT_INT | VOUT |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in part["frontend_to_drv"]["rows"]:
        lines.append(
            f"| `{_fmt(row['vinp_V'])}` | `{_fmt(row['drv_p_V'])}` | `{_fmt(row['drv_n_V'])}` | "
            f"`{_fmt(row['vout_int_V'])}` | `{_fmt(row['vout_V'])}` |"
        )
    lines += ["", "Summary:"]
    for key, value in part["frontend_to_drv"]["summary"].items():
        lines.append(f"- `{key}`: `{_fmt(value)}`")

    lines += [
        "",
        "### DRV To Gate",
        "",
        "| VINP | DRV_P | DRV_N | VGP | VGN |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in part["drv_to_gate"]["rows"]:
        lines.append(
            f"| `{_fmt(row['vinp_V'])}` | `{_fmt(row['drv_p_V'])}` | `{_fmt(row['drv_n_V'])}` | "
            f"`{_fmt(row['vgp_V'])}` | `{_fmt(row['vgn_V'])}` |"
        )
    lines += ["", "Summary:"]
    for key, value in part["drv_to_gate"]["summary"].items():
        lines.append(f"- `{key}`: `{_fmt(value)}`")

    lines += [
        "",
        "### Output Stage Only: sweep VGP",
        "",
        "| VGP | VGN | VOUT | PSRC | NSRC | IQ uA |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in part["gate_to_output_stage_vgp_sweep"]["rows"]:
        lines.append(
            f"| `{_fmt(row['vgp_V'])}` | `{_fmt(row['vgn_V'])}` | `{_fmt(row['vout_V'])}` | "
            f"`{_fmt(row['psrc_V'])}` | `{_fmt(row['nsrc_V'])}` | `{_fmt(row['iq_uA'])}` |"
        )
    lines += ["", "Summary:"]
    for key, value in part["gate_to_output_stage_vgp_sweep"]["summary"].items():
        lines.append(f"- `{key}`: `{_fmt(value)}`")

    lines += [
        "",
        "### Output Stage Only: sweep VGN",
        "",
        "| VGP | VGN | VOUT | PSRC | NSRC | IQ uA |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in part["gate_to_output_stage_vgn_sweep"]["rows"]:
        lines.append(
            f"| `{_fmt(row['vgp_V'])}` | `{_fmt(row['vgn_V'])}` | `{_fmt(row['vout_V'])}` | "
            f"`{_fmt(row['psrc_V'])}` | `{_fmt(row['nsrc_V'])}` | `{_fmt(row['iq_uA'])}` |"
        )
    lines += ["", "Summary:"]
    for key, value in part["gate_to_output_stage_vgn_sweep"]["summary"].items():
        lines.append(f"- `{key}`: `{_fmt(value)}`")
    lines += [
        "",
        "### Raw Push-Pull Only: sweep VGP",
        "",
        "| VGP | VGN | VOUT | IQ uA |",
        "|---:|---:|---:|---:|",
    ]
    for row in part["raw_push_pull_vgp_sweep"]["rows"]:
        lines.append(
            f"| `{_fmt(row['vgp_V'])}` | `{_fmt(row['vgn_V'])}` | `{_fmt(row['vout_V'])}` | `{_fmt(row['iq_uA'])}` |"
        )
    lines += ["", "Summary:"]
    for key, value in part["raw_push_pull_vgp_sweep"]["summary"].items():
        lines.append(f"- `{key}`: `{_fmt(value)}`")

    lines += [
        "",
        "### Raw Push-Pull Only: sweep VGN",
        "",
        "| VGP | VGN | VOUT | IQ uA |",
        "|---:|---:|---:|---:|",
    ]
    for row in part["raw_push_pull_vgn_sweep"]["rows"]:
        lines.append(
            f"| `{_fmt(row['vgp_V'])}` | `{_fmt(row['vgn_V'])}` | `{_fmt(row['vout_V'])}` | `{_fmt(row['iq_uA'])}` |"
        )
    lines += ["", "Summary:"]
    for key, value in part["raw_push_pull_vgn_sweep"]["summary"].items():
        lines.append(f"- `{key}`: `{_fmt(value)}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    payload = run_debug_sweeps(output_dir=ROOT)
    payload["stage_gain_partition_sweep"] = run_stage_gain_partition_sweep()["metrics"]
    (ROOT / "debug_sweeps_v4.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path = ROOT / "debug_sweeps_v4.md"
    md_path.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps({"json": str(ROOT / "debug_sweeps_v4.json"), "md": str(md_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
