from __future__ import annotations

import argparse
import json
from pathlib import Path

import hdl21 as h
import sky130_hdl21 as sky130

from .measure_core import (
    OpampCoreDisabledTbParams,
    OpampCoreFollowerTbParams,
    OpampCoreOpenLoopTbParams,
    render_full_characterization_report,
    run_disabled_leakage_shutdown_fixture_test,
    run_input_referred_offset_test,
    run_open_loop_test,
    run_output_drive_test,
    run_output_swing_test,
    summarize_full_characterization,
)
from .opamp_core import OpampCoreParams
from .specs import (
    OpampAzV3MaximumSpec,
    OpampAzV3TargetSpec,
    max_required_output_high,
    min_required_output_high,
)


CORNERS = {
    "TT": h.pdk.Corner.TYP,
    "FF": h.pdk.Corner.FAST,
    "SS": h.pdk.Corner.SLOW,
}
VDDS = (1.6, 1.8, 1.98)
TEMPS = (-40.0, 27.0, 125.0)


def init_sky130_install() -> None:
    if sky130.install is not None:
        return
    sky130.install = sky130.Install(
        pdk_path=Path("pdks/sky130A/sky130A").resolve(),
        lib_path=Path("libs.tech/ngspice/sky130.lib.spice"),
        model_ref=Path("libs.ref/sky130_fd_pr/spice"),
    )


def build_case_labels() -> list[str]:
    labels: list[str] = []
    for cname in CORNERS:
        for vdd in VDDS:
            for temp_c in TEMPS:
                labels.append(f"{cname}_V{vdd:.2f}_T{temp_c:.0f}C")
    return labels


def parse_case_label(label: str) -> tuple[str, float, float]:
    cname, vpart, tpart = label.split("_")
    vdd = float(vpart[1:])
    temp_c = float(tpart[1:-1])
    return cname, vdd, temp_c


def serialize_dut_params(dut: OpampCoreParams) -> dict[str, object]:
    return {
        "architecture_name": str(dut.architecture_name),
        "w_in": float(dut.w_in),
        "l_in": float(dut.l_in),
        "w_load": float(dut.w_load),
        "l_load": float(dut.l_load),
        "w_tail_ref": float(dut.w_tail_ref),
        "l_tail_ref": float(dut.l_tail_ref),
        "w_tail": float(dut.w_tail),
        "l_tail": float(dut.l_tail),
        "r_stage1_bias": float(dut.r_stage1_bias),
        "w_tail_sw": float(dut.w_tail_sw),
        "l_tail_sw": float(dut.l_tail_sw),
        "tail_switch_stack": int(dut.tail_switch_stack),
        "w_stage2_n": float(dut.w_stage2_n),
        "l_stage2_n": float(dut.l_stage2_n),
        "w_stage2_p": float(dut.w_stage2_p),
        "l_stage2_p": float(dut.l_stage2_p),
        "w_stage2_bias_ref": float(dut.w_stage2_bias_ref),
        "l_stage2_bias_ref": float(dut.l_stage2_bias_ref),
        "r_stage2_bias": float(dut.r_stage2_bias),
        "w_out_n": float(dut.w_out_n),
        "l_out_n": float(dut.l_out_n),
        "w_out_boost": float(dut.w_out_boost),
        "l_out_boost": float(dut.l_out_boost),
        "w_out_pd": float(dut.w_out_pd),
        "l_out_pd": float(dut.l_out_pd),
        "r_vdrv_out": float(dut.r_vdrv_out),
        "r_gp": float(dut.r_gp),
        "r_gp_pullup": float(dut.r_gp_pullup),
        "r_gp_boost": float(dut.r_gp_boost),
        "r_gp_boost_pullup": float(dut.r_gp_boost_pullup),
        "isolate_gp_link_in_shutdown": bool(dut.isolate_gp_link_in_shutdown),
        "w_gp_sw": float(dut.w_gp_sw),
        "l_gp_sw": float(dut.l_gp_sw),
        "c_comp": float(dut.c_comp),
        "debug_current_probes": bool(dut.debug_current_probes),
    }


def run_case(dut: OpampCoreParams, label: str) -> dict:
    cname, vdd, temp_c = parse_case_label(label)
    corner = CORNERS[cname]
    open_tb = OpampCoreOpenLoopTbParams(
        vdd=vdd,
        c_load=1e-12,
        r_probe=1e12,
        v_cm=min(0.4, 0.5 * vdd),
        dc_v_diff=100e-6,
        f_start=1.0,
        f_stop=1e9,
        npts=40,
        temp_c=temp_c,
    )
    follower20 = OpampCoreFollowerTbParams(
        vdd=vdd,
        c_load=1e-12,
        r_probe=1e12,
        vout_low_target=0.1,
        vout_high_target=min_required_output_high(vdd),
        vout_mid_target=0.5 * vdd,
        drive_current_uA=20.0,
        f_start=1.0,
        f_stop=1e9,
        npts=40,
        temp_c=temp_c,
    )
    follower25 = OpampCoreFollowerTbParams(
        vdd=vdd,
        c_load=1e-12,
        r_probe=1e12,
        vout_low_target=0.1,
        vout_high_target=max_required_output_high(vdd),
        vout_mid_target=0.5 * vdd,
        drive_current_uA=25.0,
        f_start=1.0,
        f_stop=1e9,
        npts=40,
        temp_c=temp_c,
    )
    disabled_tb = OpampCoreDisabledTbParams(
        vdd=vdd,
        c_load=1e-12,
        r_probe=1e12,
        v_cm=min(0.4, 0.5 * vdd),
        temp_c=temp_c,
    )
    return {
        "open_loop": run_open_loop_test(dut, open_tb, corner=corner)["metrics"],
        "swing_min": run_output_swing_test(dut, follower20, corner=corner)["metrics"],
        "drive_20uA": run_output_drive_test(dut, follower20, corner=corner)["metrics"],
        "drive_25uA": run_output_drive_test(dut, follower25, corner=corner)["metrics"],
        "leakage": run_disabled_leakage_shutdown_fixture_test(dut, disabled_tb, corner=corner)["metrics"],
        "raw_offset": run_input_referred_offset_test(dut, follower20, corner=corner)["metrics"],
    }


def summarize_extended(cases: dict[str, dict]) -> dict:
    target = OpampAzV3TargetSpec()
    maximum = OpampAzV3MaximumSpec()
    items = list(cases.items())

    def min_item(keyfn):
        return min(((label, keyfn(case)) for label, case in items), key=lambda x: x[1])

    def max_item(keyfn):
        return max(((label, keyfn(case)) for label, case in items), key=lambda x: x[1])

    return {
        "worst_raw_offset_abs_uV": max_item(lambda c: float(c["raw_offset"]["input_referred_offset_abs_uV"])),
        "best_raw_offset_abs_uV": min_item(lambda c: float(c["raw_offset"]["input_referred_offset_abs_uV"])),
        "worst_vout_source_25uA": min_item(lambda c: float(c["drive_25uA"]["vout_source"])),
        "worst_vout_sink_25uA": min_item(lambda c: float(c["drive_25uA"]["vout_sink"])),
        "worst_vout_high_maxspec_margin": min(
            (
                (
                    label,
                    float(case["swing_min"]["vout_high_actual"])
                    - max_required_output_high(parse_case_label(label)[1]),
                )
                for label, case in items
            ),
            key=lambda x: x[1],
        ),
        "pass_counts": {
            "minimum_aol": sum(float(c["open_loop"]["aol_db"]) >= target.aol_db_min for _, c in items),
            "maximum_aol": sum(float(c["open_loop"]["aol_db"]) >= maximum.aol_db_min for _, c in items),
            "minimum_iq": sum(float(c["open_loop"]["iq_uA"]) <= target.iq_uA_max for _, c in items),
            "maximum_iq": sum(float(c["open_loop"]["iq_uA"]) <= maximum.iq_uA_max for _, c in items),
            "minimum_vlow": sum(float(c["swing_min"]["vout_low_actual"]) <= target.output_swing_low_max_v for _, c in items),
            "maximum_vlow": sum(float(c["swing_min"]["vout_low_actual"]) <= maximum.output_swing_low_max_v for _, c in items),
            "minimum_vhigh": sum(
                float(c["swing_min"]["vout_high_actual"]) >= min_required_output_high(parse_case_label(label)[1])
                for label, c in items
            ),
            "maximum_vhigh": sum(
                float(c["swing_min"]["vout_high_actual"]) >= max_required_output_high(parse_case_label(label)[1])
                for label, c in items
            ),
            "minimum_pm": sum(float(c["open_loop"]["phase_margin_deg"]) >= target.phase_margin_deg_min for _, c in items),
            "minimum_gm": sum(float(c["open_loop"]["gain_margin_db"]) >= target.gain_margin_db_min for _, c in items),
            "minimum_gbw_low": sum(float(c["open_loop"]["gbw_hz"]) >= target.gbw_hz_min for _, c in items),
            "maximum_gbw_low": sum(float(c["open_loop"]["gbw_hz"]) >= maximum.gbw_hz_min for _, c in items),
            "minimum_leak": sum(float(c["leakage"]["disabled_leakage_nA"]) <= target.disabled_leakage_nA_max for _, c in items),
            "maximum_leak": sum(float(c["leakage"]["disabled_leakage_nA"]) <= maximum.disabled_leakage_nA_max for _, c in items),
        },
    }


def render_report(dut: OpampCoreParams, cases: dict[str, dict]) -> str:
    base_result = {
        "metrics": {
            "cases": {
                k: {
                    "open_loop": v["open_loop"],
                    "swing": v["swing_min"],
                    "drive": v["drive_20uA"],
                    "leakage": v["leakage"],
                }
                for k, v in cases.items()
            }
        }
    }
    summary = summarize_full_characterization(base_result)
    extended = summarize_extended(cases)
    report = render_full_characterization_report(base_result, summary)
    report += "\n\n## Extended Checks\n\n"
    report += f"- Worst raw-offset abs: `{extended['worst_raw_offset_abs_uV'][1]:.3f} uV` @ `{extended['worst_raw_offset_abs_uV'][0]}`\n"
    report += f"- Best raw-offset abs: `{extended['best_raw_offset_abs_uV'][1]:.3f} uV` @ `{extended['best_raw_offset_abs_uV'][0]}`\n"
    report += f"- Worst +25 uA source-load VOUT: `{extended['worst_vout_source_25uA'][1]:.6f} V` @ `{extended['worst_vout_source_25uA'][0]}`\n"
    report += f"- Worst -25 uA sink-load VOUT: `{extended['worst_vout_sink_25uA'][1]:.6f} V` @ `{extended['worst_vout_sink_25uA'][0]}`\n"
    report += f"- Worst max-spec high-swing margin: `{extended['worst_vout_high_maxspec_margin'][1]:.6f} V` @ `{extended['worst_vout_high_maxspec_margin'][0]}`\n"
    report += "\n### Pass Counts\n\n"
    for key, value in extended["pass_counts"].items():
        report += f"- `{key}`: `{value}/{len(cases)}`\n"
    report += "\n## Active DUT Params\n\n"
    for key, value in serialize_dut_params(dut).items():
        report += f"- `{key}`: `{value}`\n"
    return report


def save_outputs(outdir: Path, dut: OpampCoreParams, cases: dict[str, dict]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    base_result = {
        "metrics": {
            "cases": {
                k: {
                    "open_loop": v["open_loop"],
                    "swing": v["swing_min"],
                    "drive": v["drive_20uA"],
                    "leakage": v["leakage"],
                }
                for k, v in cases.items()
            }
        }
    }
    payload = {
        "dut_params": serialize_dut_params(dut),
        "summary": summarize_full_characterization(base_result) if cases else None,
        "extended_summary": summarize_extended(cases) if cases else None,
        "cases": cases,
        "completed_case_count": len(cases),
        "expected_case_count": len(build_case_labels()),
    }
    (outdir / "current_baseline_27p.json").write_text(json.dumps(payload, indent=2, sort_keys=True))
    (outdir / "current_baseline_27p.md").write_text(render_report(dut, cases) if cases else "# opamp/v3 Long Characterization\n\nNo cases completed yet.\n")


def load_cases(json_path: Path) -> dict[str, dict]:
    if not json_path.exists():
        return {}
    payload = json.loads(json_path.read_text())
    return payload.get("cases", {})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="tmp/opamp_v3_extended_pvt")
    parser.add_argument("--case", action="append", dest="cases")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)

    init_sky130_install()
    outdir = Path(args.outdir)
    json_path = outdir / "current_baseline_27p.json"
    dut = OpampCoreParams()
    cases = load_cases(json_path) if args.resume else {}

    requested = args.cases or build_case_labels()
    for label in requested:
        if label in cases:
            print(f"{label} skip")
            continue
        cases[label] = run_case(dut, label)
        save_outputs(outdir, dut, cases)
        print(f"{label} done")

    save_outputs(outdir, dut, cases)
    print(outdir / "current_baseline_27p.json")
    print(outdir / "current_baseline_27p.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
