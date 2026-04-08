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
    run_direct_dc_gain_test,
    run_disable_nodes_test,
    run_input_referred_offset_test,
    run_open_loop_test,
    run_output_swing_test,
)
from .opamp_core import OpampCoreParams
from .tests._helpers import init_sky130_install


@dataclass(frozen=True)
class ExperimentCase:
    name: str
    description: str
    params: OpampCoreParams


def family_a_cases() -> list[ExperimentCase]:
    baseline = OpampCoreParams()
    return [
        ExperimentCase(
            name="baseline",
            description="Current v3 baseline for comparison.",
            params=baseline,
        ),
        ExperimentCase(
            name="A1_tail_switch_weaker_longer",
            description="Reduce tail-switch width and lengthen it to cut off-state leakage.",
            params=OpampCoreParams(w_tail_sw=4.0, l_tail_sw=1.0),
        ),
        ExperimentCase(
            name="A2_tail_switch_stack2",
            description="Use a 2-stack PMOS tail enable path to reduce residual off-state conduction.",
            params=OpampCoreParams(w_tail_sw=8.0, l_tail_sw=0.5, tail_switch_stack=2),
        ),
        ExperimentCase(
            name="A3_tail_switch_stack3",
            description="Use a 3-stack PMOS tail enable path as a stronger isolation experiment.",
            params=OpampCoreParams(w_tail_sw=8.0, l_tail_sw=0.5, tail_switch_stack=3),
        ),
    ]


def family_b_cases() -> list[ExperimentCase]:
    baseline = OpampCoreParams()
    return [
        ExperimentCase(
            name="baseline",
            description="Current v3 baseline with shutdown fix and lighter stage-1 bias promoted.",
            params=baseline,
        ),
        ExperimentCase(
            name="B2_input_longer",
            description="Increase PMOS input-pair length on top of the lighter-bias baseline.",
            params=OpampCoreParams(l_in=3.0),
        ),
        ExperimentCase(
            name="B5_tail_lighter_input_longer",
            description="Focused combo: lighter first-stage bias plus longer PMOS input pair.",
            params=OpampCoreParams(l_in=3.0, w_tail=4.0, r_stage1_bias=2.5e6),
        ),
        ExperimentCase(
            name="B6_tail_lighter_input_longer_load_longer",
            description="Focused combo extension: B5 plus longer first-stage NMOS mirror load.",
            params=OpampCoreParams(l_in=3.0, l_load=10.0, w_tail=4.0, r_stage1_bias=2.5e6),
        ),
        ExperimentCase(
            name="B7_tail_lighter_input_longer_stage2_smaller",
            description="Focused combo extension: B5 plus slightly smaller second-stage NMOS.",
            params=OpampCoreParams(l_in=3.0, w_tail=4.0, r_stage1_bias=2.5e6, w_stage2_n=20.0),
        ),
    ]


def _serialize_params(params: OpampCoreParams) -> dict[str, float | int | str]:
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
        "r_vdrv_out": float(params.r_vdrv_out),
        "r_gp": float(params.r_gp),
        "isolate_gp_link_in_shutdown": bool(params.isolate_gp_link_in_shutdown),
        "w_gp_sw": float(params.w_gp_sw),
        "l_gp_sw": float(params.l_gp_sw),
        "c_comp": float(params.c_comp),
    }


def _screen_metrics(case: ExperimentCase) -> dict:
    disable_tb = OpampCoreDisabledTbParams(vdd=1.98, v_cm=0.4, temp_c=-40.0)
    disable = run_disable_nodes_test(case.params, disable_tb, corner=h.pdk.Corner.FAST)
    return {
        "case": case.name,
        "description": case.description,
        "params": _serialize_params(case.params),
        "disable_ff_1p98_m40": disable["metrics"],
    }


def _disable_rank_case(metrics: dict) -> tuple[float, float, float]:
    disable = float(metrics["disable_ff_1p98_m40"]["disabled_leakage_nA"])
    tail1 = abs(float(metrics["disable_ff_1p98_m40"]["tail1_dc"]) - 1.98)
    vdrv = abs(float(metrics["disable_ff_1p98_m40"]["vdrv_dc"]))
    return (disable, tail1, vdrv)


def _nominal_rank_case(metrics: dict) -> tuple[float, float, float, float]:
    disable = float(metrics["disable_ff_1p98_m40"]["disabled_leakage_nA"])
    open_loop = metrics["open_loop_tt_1p8_27"]
    aol = float(open_loop.get("aol_db", open_loop.get("direct_gain_db")))
    iq = float(metrics["open_loop_tt_1p8_27"]["iq_uA"])
    low = float(metrics["swing_tt_1p8_27"]["vout_low_actual"])
    return (disable, -aol, iq, low)


def _nominal_check(case_metrics: dict) -> dict:
    params = OpampCoreParams(**case_metrics["params"])
    nominal_open_tb = OpampCoreOpenLoopTbParams(vdd=1.8, temp_c=27.0)
    nominal_follow_tb = OpampCoreFollowerTbParams(vdd=1.8, vout_high_target=1.6, vout_mid_target=0.9, temp_c=27.0)
    case_metrics["open_loop_tt_1p8_27"] = run_direct_dc_gain_test(params, nominal_open_tb, corner=h.pdk.Corner.TYP)["metrics"]
    case_metrics["swing_tt_1p8_27"] = run_output_swing_test(params, nominal_follow_tb, corner=h.pdk.Corner.TYP)["metrics"]
    return case_metrics


def _full_check(case_metrics: dict) -> dict:
    params = OpampCoreParams(**case_metrics["params"])
    hard_open_tb = OpampCoreOpenLoopTbParams(vdd=1.6, v_cm=0.4, temp_c=125.0, f_stop=1e8, npts=20)
    offset_tb = OpampCoreFollowerTbParams(vdd=1.8, vout_mid_target=0.9, temp_c=27.0)
    case_metrics["open_loop_ss_1p6_125"] = run_open_loop_test(params, hard_open_tb, corner=h.pdk.Corner.SLOW)["metrics"]
    case_metrics["offset_tt_1p8_27"] = run_input_referred_offset_test(params, offset_tb, corner=h.pdk.Corner.TYP)["metrics"]
    return case_metrics


def _family_b_screen_metrics(case: ExperimentCase) -> dict:
    disable_tb = OpampCoreDisabledTbParams(vdd=1.98, v_cm=0.4, temp_c=-40.0)
    nominal_open_tb = OpampCoreOpenLoopTbParams(vdd=1.8, temp_c=27.0)
    nominal_follow_tb = OpampCoreFollowerTbParams(vdd=1.8, vout_high_target=1.6, vout_mid_target=0.9, temp_c=27.0)
    disable = run_disable_nodes_test(case.params, disable_tb, corner=h.pdk.Corner.FAST)
    nominal_open = run_direct_dc_gain_test(case.params, nominal_open_tb, corner=h.pdk.Corner.TYP)
    nominal_swing = run_output_swing_test(case.params, nominal_follow_tb, corner=h.pdk.Corner.TYP)
    return {
        "case": case.name,
        "description": case.description,
        "params": _serialize_params(case.params),
        "disable_ff_1p98_m40": disable["metrics"],
        "open_loop_tt_1p8_27": nominal_open["metrics"],
        "swing_tt_1p8_27": nominal_swing["metrics"],
    }


def _family_b_rank_case(metrics: dict) -> tuple[float, float, float, float]:
    open_loop = metrics["open_loop_tt_1p8_27"]
    aol = float(open_loop.get("aol_db", open_loop.get("direct_gain_db")))
    iq = float(open_loop["iq_uA"])
    low = float(metrics["swing_tt_1p8_27"]["vout_low_actual"])
    disable = float(metrics["disable_ff_1p98_m40"]["disabled_leakage_nA"])
    return (-aol, iq, low, disable)


def run_family_b_sweep(*, include_cases: set[str] | None = None) -> dict:
    init_sky130_install()
    cases: list[dict] = []
    failures: list[dict[str, str]] = []
    for case in family_b_cases():
        if include_cases is not None and case.name not in include_cases:
            continue
        print(f"[family_b] running {case.name}", flush=True)
        try:
            cases.append(_family_b_screen_metrics(case))
        except Exception as err:
            failures.append({"case": case.name, "error": f"{type(err).__name__}: {err}"})
            print(f"[family_b] failed {case.name}: {type(err).__name__}: {err}", flush=True)
    ranked = sorted(cases, key=_family_b_rank_case)
    return {
        "family": "B",
        "purpose": "nominal AOL and IQ screen from the shutdown-fixed baseline",
        "cases": cases,
        "failures": failures,
        "best_case_by_priority": ranked[0]["case"] if ranked else None,
    }


def render_family_b_markdown(result: dict) -> str:
    lines = [
        "# Family B Sweep",
        "",
        "Priority order: higher nominal gain, lower nominal current, better low-side swing, then preserved shutdown leakage.",
        "",
        "| Case | Direct Gain dB | IQ uA | Vlow V | Disable nA |",
        "|---|---:|---:|---:|---:|",
    ]
    for case in result["cases"]:
        ol = case["open_loop_tt_1p8_27"]
        sw = case["swing_tt_1p8_27"]
        disable = case["disable_ff_1p98_m40"]
        lines.append(
            f"| {case['case']} | "
            f"{float(ol['direct_gain_db']):.2f} | {float(ol['iq_uA']):.2f} | "
            f"{float(sw['vout_low_actual']):.4f} | {float(disable['disabled_leakage_nA']):.2f} |"
        )
    lines.extend(["", f"Best case by current priority: `{result['best_case_by_priority']}`", ""])
    if result["failures"]:
        lines.append("## Failures")
        lines.append("")
        for failure in result["failures"]:
            lines.append(f"- `{failure['case']}`: `{failure['error']}`")
        lines.append("")
    return "\n".join(lines)


def run_family_a_sweep(*, include_cases: set[str] | None = None, survivor_count: int = 2, full_check_best: bool = False) -> dict:
    init_sky130_install()
    cases: list[dict] = []
    failures: list[dict[str, str]] = []
    for case in family_a_cases():
        if include_cases is not None and case.name not in include_cases:
            continue
        print(f"[family_a] running {case.name}", flush=True)
        try:
            cases.append(_screen_metrics(case))
        except Exception as err:
            failures.append({"case": case.name, "error": f"{type(err).__name__}: {err}"})
            print(f"[family_a] failed {case.name}: {type(err).__name__}: {err}", flush=True)
    disable_ranked = sorted(cases, key=_disable_rank_case)
    survivor_names: list[str] = []
    for case in disable_ranked:
        if len(survivor_names) >= max(int(survivor_count), 1):
            break
        survivor_names.append(case["case"])
    if "baseline" in {case["case"] for case in cases} and "baseline" not in survivor_names:
        survivor_names.append("baseline")
    survivor_set = set(survivor_names)
    for idx, case in enumerate(cases):
        if case["case"] not in survivor_set:
            continue
        print(f"[family_a] nominal-check {case['case']}", flush=True)
        try:
            cases[idx] = _nominal_check(case)
        except Exception as err:
            failures.append({"case": case["case"], "error": f"{type(err).__name__}: {err}"})
            print(f"[family_a] failed nominal-check {case['case']}: {type(err).__name__}: {err}", flush=True)
    nominal_ranked = sorted(
        [case for case in cases if "open_loop_tt_1p8_27" in case and "swing_tt_1p8_27" in case],
        key=_nominal_rank_case,
    )
    if nominal_ranked and full_check_best:
        best_name = nominal_ranked[0]["case"]
        print(f"[family_a] full-check {best_name}", flush=True)
        best_full = _full_check(nominal_ranked[0])
        for idx, case in enumerate(cases):
            if case["case"] == best_name:
                cases[idx] = best_full
                break
    return {
        "family": "A",
        "purpose": "tail-side shutdown topology screen with disable-first survivor flow",
        "cases": cases,
        "failures": failures,
        "survivor_cases": survivor_names,
        "best_case_by_priority": nominal_ranked[0]["case"] if nominal_ranked else (disable_ranked[0]["case"] if disable_ranked else None),
    }


def render_family_a_markdown(result: dict) -> str:
    lines = [
        "# Family A Sweep",
        "",
        "Flow: disable-only prefilter for all cases, nominal open-loop plus swing for survivors, then hard-corner and offset full-check for the best survivor.",
        "",
        "| Case | Disable nA | Tail1 V | AOL dB | IQ uA | PM deg | GM dB | Vlow V | Raw Vos uV |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case in result["cases"]:
        disable = case["disable_ff_1p98_m40"]
        ol = case.get("open_loop_tt_1p8_27", {})
        sw = case.get("swing_tt_1p8_27", {})
        off = case.get("offset_tt_1p8_27", {})
        aol = ol.get("aol_db", ol.get("direct_gain_db"))
        iq = ol.get("iq_uA")
        pm = ol.get("phase_margin_deg")
        gm = ol.get("gain_margin_db")
        low = sw.get("vout_low_actual")
        vos = off.get("input_referred_offset_uV")
        aol_text = f"{aol:.2f}" if isinstance(aol, (int, float)) else "n/a"
        iq_text = f"{iq:.2f}" if isinstance(iq, (int, float)) else "n/a"
        pm_text = f"{pm:.2f}" if isinstance(pm, (int, float)) else "n/a"
        gm_text = f"{gm:.2f}" if isinstance(gm, (int, float)) else "n/a"
        low_text = f"{low:.4f}" if isinstance(low, (int, float)) else "n/a"
        vos_text = f"{vos:.1f}" if isinstance(vos, (int, float)) else "n/a"
        lines.append(
            f"| {case['case']} | "
            f"{disable['disabled_leakage_nA']:.1f} | {disable['tail1_dc']:.3f} | "
            f"{aol_text} | {iq_text} | {pm_text} | {gm_text} | "
            f"{low_text} | {vos_text} |"
        )
    lines.extend(
        [
            "",
            f"Survivor cases: `{', '.join(result.get('survivor_cases', []))}`",
            "",
            f"Best case by current priority: `{result['best_case_by_priority']}`",
            "",
        ]
    )
    if result["failures"]:
        lines.append("## Failures")
        lines.append("")
        for failure in result["failures"]:
            lines.append(f"- `{failure['case']}`: `{failure['error']}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=["A", "B"], default="A", help="Experiment family to run.")
    parser.add_argument("--case", action="append", dest="cases", help="Run only the named Family A case. Can be repeated.")
    parser.add_argument("--survivors", type=int, default=2, help="Number of disable-screen survivors to run through nominal checks.")
    parser.add_argument("--full-check-best", action="store_true", help="Run hard-corner plus raw-offset follow-up on the best nominal survivor.")
    args = parser.parse_args()
    outdir = Path("tmp/opamp_v3_current_experiment")
    outdir.mkdir(parents=True, exist_ok=True)
    include_cases = set(args.cases) if args.cases else None
    if args.family == "A":
        result = run_family_a_sweep(include_cases=include_cases, survivor_count=args.survivors, full_check_best=args.full_check_best)
        (outdir / "family_a.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        (outdir / "family_a.md").write_text(render_family_a_markdown(result), encoding="utf-8")
    else:
        result = run_family_b_sweep(include_cases=include_cases)
        (outdir / "family_b.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        (outdir / "family_b.md").write_text(render_family_b_markdown(result), encoding="utf-8")
    print(outdir)
    print(result["best_case_by_priority"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
