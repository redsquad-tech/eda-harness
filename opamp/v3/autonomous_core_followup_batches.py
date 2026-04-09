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
class BatchCase:
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


def _screen_case(case: BatchCase) -> dict:
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


def _penalty(case: dict) -> tuple[int, int, int]:
    ss = case["open_loop_ss_1p6_125"]
    tt = case["open_loop_tt_1p8_27"]
    swing = case["swing_tt_1p8_27"]
    bad_gm = int(float(ss["gain_margin_db"]) < 5.0)
    bad_pm = int(float(ss["phase_margin_deg"]) < 30.0 or float(tt["phase_margin_deg"]) < 30.0)
    bad_swing = int(float(swing["vout_low_actual"]) > 0.11)
    return bad_gm, bad_pm, bad_swing


def _rank_key(case: dict) -> tuple[int, int, int, float, float, float, float, float]:
    tt = case["open_loop_tt_1p8_27"]
    ss = case["open_loop_ss_1p6_125"]
    ff = case["open_loop_ff_1p98_m40"]
    swing = case["swing_tt_1p8_27"]
    penalty = _penalty(case)
    return (
        penalty[0],
        penalty[1],
        penalty[2],
        -float(tt["aol_db"]),
        float(tt["iq_uA"]),
        -float(ss["gain_margin_db"]),
        abs(float(ff["gbw_hz"]) - 1e6),
        float(swing["vout_low_actual"]),
    )


def build_batches() -> dict[str, list[BatchCase]]:
    baseline = BatchCase("baseline", "Reference promoted v3 baseline.", OpampCoreParams())
    return {
        "stability_repair": [
            baseline,
            BatchCase("K1_stage2p10", "Longer stage-2 PMOS load gives strong gain; verify as the reference follow-up branch.", OpampCoreParams(l_stage2_p=10.0)),
            BatchCase("K1_c240", "More compensation may recover SS margin on K1 without giving back too much gain.", OpampCoreParams(l_stage2_p=10.0, c_comp=240e-15)),
            BatchCase("K1_c260", "Stronger compensation on K1 for SS margin repair.", OpampCoreParams(l_stage2_p=10.0, c_comp=260e-15)),
            BatchCase("J2_c240", "More compensation on J2 tests whether the first-stage load branch can be stabilized.", OpampCoreParams(l_load=10.0, c_comp=240e-15)),
            BatchCase("J2_c260", "Stronger compensation on J2.", OpampCoreParams(l_load=10.0, c_comp=260e-15)),
            BatchCase("K1_c240_wout0p9", "K1 with compensation repair and smaller helper PMOS to avoid low-swing regression.", OpampCoreParams(l_stage2_p=10.0, c_comp=240e-15, w_out_n=0.9)),
            BatchCase("K4_stage2p12_c240", "Longer stage-2 PMOS load with compensation repair as a lower-current high-gain alternative.", OpampCoreParams(l_stage2_p=12.0, c_comp=240e-15)),
        ],
        "mixed_repair": [
            baseline,
            BatchCase("K1_load10_c240", "Combine both gain levers with compensation repair to see if TT gain can stay high while SS margin recovers.", OpampCoreParams(l_load=10.0, l_stage2_p=10.0, c_comp=240e-15)),
            BatchCase("K1_load10_c260", "Stronger compensation on the combined gain branch.", OpampCoreParams(l_load=10.0, l_stage2_p=10.0, c_comp=260e-15)),
            BatchCase("K1_stage2p10_wout0p9", "Keep the K1 gain branch but trim the helper PMOS for low swing.", OpampCoreParams(l_stage2_p=10.0, w_out_n=0.9)),
            BatchCase("K1_stage2p10_wout0p6", "Aggressive low-swing trim on K1.", OpampCoreParams(l_stage2_p=10.0, w_out_n=0.6)),
            BatchCase("K4_stage2p12_wout0p9", "Stage2p12 branch with lower helper PMOS as another balanced candidate.", OpampCoreParams(l_stage2_p=12.0, w_out_n=0.9)),
            BatchCase("K4_stage2p12_c240_wout0p9", "Stage2p12 with mild compensation repair and lower helper PMOS.", OpampCoreParams(l_stage2_p=12.0, c_comp=240e-15, w_out_n=0.9)),
        ],
    }


def render_batch_markdown(batch_name: str, payload: dict) -> str:
    lines = [
        f"# Core Follow-up Batch {batch_name}",
        "",
        payload["purpose"],
        "",
        "| Case | TT AOL | TT IQ | TT PM | TT Vlow | SS GM | SS GBW kHz | FF AOL | FF GBW kHz | Leak nA | Raw Vos uV |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case in payload["cases"]:
        tt = case["open_loop_tt_1p8_27"]
        ss = case["open_loop_ss_1p6_125"]
        ff = case["open_loop_ff_1p98_m40"]
        swing = case["swing_tt_1p8_27"]
        disable = case["disable_ff_1p98_m40"]
        offset = case["offset_tt_1p8_27"]
        lines.append(
            f"| {case['case']} | {float(tt['aol_db']):.2f} | {float(tt['iq_uA']):.2f} | {float(tt['phase_margin_deg']):.2f} | "
            f"{float(swing['vout_low_actual']):.4f} | {float(ss['gain_margin_db']):.2f} | {float(ss['gbw_hz'])/1e3:.1f} | "
            f"{float(ff['aol_db']):.2f} | {float(ff['gbw_hz'])/1e3:.1f} | {float(disable['disabled_leakage_nA']):.2f} | "
            f"{float(offset['input_referred_offset_abs_uV']):.1f} |"
        )
    lines.extend(["", f"Best case by follow-up priority: `{payload['best_case_by_priority']}`", ""])
    if payload["failures"]:
        lines.append("## Failures")
        lines.append("")
        for failure in payload["failures"]:
            lines.append(f"- `{failure['case']}`: `{failure['error']}`")
        lines.append("")
    lines.append("## Hypotheses")
    lines.append("")
    for case in payload["cases"]:
        lines.append(f"- `{case['case']}`: {case['hypothesis']}")
    return "\n".join(lines)


def write_index(outroot: Path, results: dict[str, dict]) -> None:
    lines = [
        "# Autonomous Core Follow-up Batches",
        "",
        "Second-generation core follow-up batches built from current autonomous winners.",
        "",
        "| Batch | Cases Done | Failures | Best Case | Artifact |",
        "|---|---:|---:|---|---|",
    ]
    for batch_name, payload in sorted(results.items()):
        lines.append(
            f"| {batch_name} | {len(payload['cases'])} | {len(payload['failures'])} | "
            f"`{payload['best_case_by_priority']}` | [`{batch_name}.md`](./{batch_name}.md) |"
        )
    (outroot / "index.md").write_text("\n".join(lines), encoding="utf-8")


def run_batch(batch_name: str, cases: list[BatchCase], outroot: Path) -> dict:
    json_path = outroot / f"{batch_name}.json"
    if json_path.exists():
        payload = json.loads(json_path.read_text())
        completed = {case["case"]: case for case in payload.get("cases", [])}
        failures = payload.get("failures", [])
    else:
        completed = {}
        failures = []
    for case in cases:
        if case.name in completed:
            print(f"[{batch_name}] skip {case.name}", flush=True)
            continue
        print(f"[{batch_name}] running {case.name}", flush=True)
        try:
            completed[case.name] = _screen_case(case)
        except Exception as err:
            failures.append({"case": case.name, "error": f"{type(err).__name__}: {err}"})
            print(f"[{batch_name}] failed {case.name}: {type(err).__name__}: {err}", flush=True)
        payload = {
            "purpose": f"Autonomous follow-up batch `{batch_name}` for perspective core solutions.",
            "cases": sorted(completed.values(), key=_rank_key),
            "failures": failures,
            "best_case_by_priority": sorted(completed.values(), key=_rank_key)[0]["case"] if completed else None,
        }
        outroot.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        (outroot / f"{batch_name}.md").write_text(render_batch_markdown(batch_name, payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="append", dest="batches")
    parser.add_argument("--outdir", default="tmp/opamp_v3_autonomous_core_followup")
    args = parser.parse_args(argv)
    init_sky130_install()
    outroot = Path(args.outdir)
    batches = build_batches()
    selected = args.batches or list(batches.keys())
    results: dict[str, dict] = {}
    for batch_name in selected:
        if batch_name not in batches:
            raise SystemExit(f"Unknown batch: {batch_name}")
        results[batch_name] = run_batch(batch_name, batches[batch_name], outroot)
        write_index(outroot, results)
    print(outroot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
