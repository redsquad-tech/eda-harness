from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import hdl21 as h

from .measure_core import (
    OpampCoreDisabledTbParams,
    OpampCoreFollowerTbParams,
    OpampCoreOpenLoopTbParams,
    run_disable_nodes_test,
    run_input_referred_offset_test,
    run_open_loop_test,
    run_output_drive_test,
    run_output_swing_test,
)
from .opamp_core import OpampCoreParams
from .tests._helpers import init_sky130_install


@dataclass(frozen=True)
class HypothesisCase:
    name: str
    hypothesis: str
    params: OpampCoreParams


def _serialize_params(params: OpampCoreParams) -> dict[str, float | int | bool | str]:
    return {
        "architecture_name": str(params.architecture_name),
        "w_in": float(params.w_in),
        "l_in": float(params.l_in),
        "w_load": float(params.w_load),
        "l_load": float(params.l_load),
        "w_tail_ref": float(params.w_tail_ref),
        "l_tail_ref": float(params.l_tail_ref),
        "w_tail": float(params.w_tail),
        "l_tail": float(params.l_tail),
        "r_stage1_bias": float(params.r_stage1_bias),
        "w_tail_sw": float(params.w_tail_sw),
        "l_tail_sw": float(params.l_tail_sw),
        "tail_switch_stack": int(params.tail_switch_stack),
        "w_stage2_n": float(params.w_stage2_n),
        "l_stage2_n": float(params.l_stage2_n),
        "w_stage2_p": float(params.w_stage2_p),
        "l_stage2_p": float(params.l_stage2_p),
        "w_stage2_bias_ref": float(params.w_stage2_bias_ref),
        "l_stage2_bias_ref": float(params.l_stage2_bias_ref),
        "r_stage2_bias": float(params.r_stage2_bias),
        "w_out_n": float(params.w_out_n),
        "l_out_n": float(params.l_out_n),
        "w_out_boost": float(params.w_out_boost),
        "l_out_boost": float(params.l_out_boost),
        "w_out_pd": float(params.w_out_pd),
        "l_out_pd": float(params.l_out_pd),
        "r_vdrv_out": float(params.r_vdrv_out),
        "r_gp": float(params.r_gp),
        "r_gp_pullup": float(params.r_gp_pullup),
        "r_gp_boost": float(params.r_gp_boost),
        "r_gp_boost_pullup": float(params.r_gp_boost_pullup),
        "isolate_gp_link_in_shutdown": bool(params.isolate_gp_link_in_shutdown),
        "w_gp_sw": float(params.w_gp_sw),
        "l_gp_sw": float(params.l_gp_sw),
        "c_comp": float(params.c_comp),
        "debug_current_probes": bool(params.debug_current_probes),
    }


def build_batch_cases() -> list[HypothesisCase]:
    baseline = OpampCoreParams()
    return [
        HypothesisCase(
            name="baseline",
            hypothesis="Reference promoted v3 baseline for comparison.",
            params=baseline,
        ),
        HypothesisCase(
            name="J2_load10",
            hypothesis="Longer first-stage NMOS mirror load may raise first-stage output resistance without weakening the current backbone.",
            params=OpampCoreParams(l_load=10.0),
        ),
        HypothesisCase(
            name="J3_lin4p0_load10",
            hypothesis="Longer PMOS input pair plus longer first-stage load may build gain together if either knob alone is too weak.",
            params=OpampCoreParams(l_in=4.0, l_load=10.0),
        ),
        HypothesisCase(
            name="J4_lin4p0_stage2p10",
            hypothesis="Longer PMOS input pair plus longer stage-2 PMOS load may raise gain while keeping stage-2 NMOS drive intact.",
            params=OpampCoreParams(l_in=4.0, l_stage2_p=10.0),
        ),
        HypothesisCase(
            name="K1_stage2p10",
            hypothesis="Longer stage-2 PMOS load alone may add gain without the slow-corner penalty seen from longer input PMOS.",
            params=OpampCoreParams(l_stage2_p=10.0),
        ),
        HypothesisCase(
            name="K2_load10_stage2p10",
            hypothesis="Longer first-stage load plus longer stage-2 PMOS load may be the cleanest ro-building combination with the baseline current backbone.",
            params=OpampCoreParams(l_load=10.0, l_stage2_p=10.0),
        ),
        HypothesisCase(
            name="K3_load12",
            hypothesis="A slightly stronger first-stage load-length move may be needed before gain starts improving materially.",
            params=OpampCoreParams(l_load=12.0),
        ),
        HypothesisCase(
            name="K4_stage2p12",
            hypothesis="A slightly stronger stage-2 PMOS load-length move may raise gain while keeping stage-2 NMOS unchanged.",
            params=OpampCoreParams(l_stage2_p=12.0),
        ),
        HypothesisCase(
            name="K5_load10_stage2p12",
            hypothesis="If gain needs both stages to contribute more ro, load10 plus stage2p12 is the next reasonable narrow combination.",
            params=OpampCoreParams(l_load=10.0, l_stage2_p=12.0),
        ),
    ]


def _screen_case(case: HypothesisCase) -> dict:
    disable_tb = OpampCoreDisabledTbParams(vdd=1.98, v_cm=0.4, temp_c=-40.0)
    tt_open_tb = OpampCoreOpenLoopTbParams(vdd=1.8, temp_c=27.0)
    tt_follow_tb = OpampCoreFollowerTbParams(vdd=1.8, vout_high_target=1.6, vout_mid_target=0.9, drive_current_uA=25.0, temp_c=27.0)
    ss_open_tb = OpampCoreOpenLoopTbParams(vdd=1.6, v_cm=0.4, temp_c=125.0, f_stop=1e8, npts=20)
    ff_open_tb = OpampCoreOpenLoopTbParams(vdd=1.98, v_cm=0.4, temp_c=-40.0)
    return {
        "case": case.name,
        "hypothesis": case.hypothesis,
        "params": _serialize_params(case.params),
        "disable_ff_1p98_m40": run_disable_nodes_test(case.params, disable_tb, corner=h.pdk.Corner.FAST)["metrics"],
        "open_loop_tt_1p8_27": run_open_loop_test(case.params, tt_open_tb, corner=h.pdk.Corner.TYP)["metrics"],
        "swing_tt_1p8_27": run_output_swing_test(case.params, tt_follow_tb, corner=h.pdk.Corner.TYP)["metrics"],
        "drive_tt_1p8_27_25uA": run_output_drive_test(case.params, tt_follow_tb, corner=h.pdk.Corner.TYP)["metrics"],
        "open_loop_ss_1p6_125": run_open_loop_test(case.params, ss_open_tb, corner=h.pdk.Corner.SLOW)["metrics"],
        "open_loop_ff_1p98_m40": run_open_loop_test(case.params, ff_open_tb, corner=h.pdk.Corner.FAST)["metrics"],
        "offset_tt_1p8_27": run_input_referred_offset_test(case.params, tt_follow_tb, corner=h.pdk.Corner.TYP)["metrics"],
    }


def _rank_key(metrics: dict) -> tuple[float, float, float, float, float, float, float]:
    tt = metrics["open_loop_tt_1p8_27"]
    ss = metrics["open_loop_ss_1p6_125"]
    ff = metrics["open_loop_ff_1p98_m40"]
    swing = metrics["swing_tt_1p8_27"]
    disable = metrics["disable_ff_1p98_m40"]
    tt_aol = float(tt["aol_db"])
    tt_iq = float(tt["iq_uA"])
    ff_aol = float(ff["aol_db"])
    ss_gbw = float(ss["gbw_hz"])
    ff_gbw_err = abs(float(ff["gbw_hz"]) - 1e6)
    low = float(swing["vout_low_actual"])
    leak = float(disable["disabled_leakage_nA"])
    return (-tt_aol, tt_iq, -ff_aol, -ss_gbw, ff_gbw_err, low, leak)


def render_markdown(result: dict) -> str:
    lines = [
        "# Hypothesis Batch",
        "",
        "Priority order: higher `TT` AOL, lower `TT` IQ, higher `FF` AOL, higher `SS` GBW, `FF` GBW closer to 1 MHz, then preserved `TT` low swing and shutdown leakage.",
        "",
        "| Case | TT AOL dB | TT IQ uA | TT Vlow V | TT Vsrc25 V | SS GBW kHz | FF AOL dB | FF GBW kHz | Leak nA | Raw Vos uV |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case in result["cases"]:
        tt = case["open_loop_tt_1p8_27"]
        ss = case["open_loop_ss_1p6_125"]
        ff = case["open_loop_ff_1p98_m40"]
        swing = case["swing_tt_1p8_27"]
        drive = case["drive_tt_1p8_27_25uA"]
        disable = case["disable_ff_1p98_m40"]
        offset = case["offset_tt_1p8_27"]
        lines.append(
            f"| {case['case']} | "
            f"{float(tt['aol_db']):.2f} | {float(tt['iq_uA']):.2f} | {float(swing['vout_low_actual']):.4f} | "
            f"{float(drive['vout_source']):.4f} | {float(ss['gbw_hz']) / 1e3:.1f} | {float(ff['aol_db']):.2f} | "
            f"{float(ff['gbw_hz']) / 1e3:.1f} | {float(disable['disabled_leakage_nA']):.2f} | {float(offset['input_referred_offset_abs_uV']):.1f} |"
        )
    lines.extend(["", f"Best case by current priority: `{result['best_case_by_priority']}`", ""])
    if result["failures"]:
        lines.append("## Failures")
        lines.append("")
        for failure in result["failures"]:
            lines.append(f"- `{failure['case']}`: `{failure['error']}`")
        lines.append("")
    lines.append("## Hypotheses")
    lines.append("")
    for case in result["cases"]:
        lines.append(f"- `{case['case']}`: {case['hypothesis']}")
    return "\n".join(lines)


def run_batch(*, include_cases: set[str] | None = None, outdir: Path) -> dict:
    init_sky130_install()
    json_path = outdir / "hypothesis_batch.json"
    if json_path.exists():
        payload = json.loads(json_path.read_text())
        completed = {case["case"]: case for case in payload.get("cases", [])}
        failures = payload.get("failures", [])
    else:
        completed = {}
        failures = []

    for case in build_batch_cases():
        if include_cases is not None and case.name not in include_cases:
            continue
        if case.name in completed:
            print(f"[batch] skip {case.name}", flush=True)
            continue
        print(f"[batch] running {case.name}", flush=True)
        try:
            completed[case.name] = _screen_case(case)
        except Exception as err:
            failures.append({"case": case.name, "error": f"{type(err).__name__}: {err}"})
            print(f"[batch] failed {case.name}: {type(err).__name__}: {err}", flush=True)
        result = {
            "purpose": "autonomous batch of current credible core hypotheses for maximum-spec closure",
            "cases": sorted(completed.values(), key=_rank_key),
            "failures": failures,
            "best_case_by_priority": sorted(completed.values(), key=_rank_key)[0]["case"] if completed else None,
        }
        outdir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        (outdir / "hypothesis_batch.md").write_text(render_markdown(result), encoding="utf-8")

    return {
        "purpose": "autonomous batch of current credible core hypotheses for maximum-spec closure",
        "cases": sorted(completed.values(), key=_rank_key),
        "failures": failures,
        "best_case_by_priority": sorted(completed.values(), key=_rank_key)[0]["case"] if completed else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", dest="cases")
    parser.add_argument("--outdir", default="tmp/opamp_v3_hypothesis_batch")
    args = parser.parse_args(argv)
    result = run_batch(include_cases=set(args.cases) if args.cases else None, outdir=Path(args.outdir))
    print(Path(args.outdir))
    print(result["best_case_by_priority"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
