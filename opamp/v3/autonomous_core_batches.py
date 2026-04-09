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


def build_batches() -> dict[str, list[BatchCase]]:
    baseline = BatchCase("baseline", "Reference promoted v3 baseline for comparison.", OpampCoreParams())
    return {
        "gain_ro": [
            baseline,
            BatchCase("J2_load10", "Longer first-stage load may raise first-stage ro without weakening the current backbone.", OpampCoreParams(l_load=10.0)),
            BatchCase("J3_lin4p0_load10", "Longer input PMOS plus longer first-stage load may build gain if one lever alone is too weak.", OpampCoreParams(l_in=4.0, l_load=10.0)),
            BatchCase("J4_lin4p0_stage2p10", "Longer input PMOS plus longer stage-2 PMOS load may add gain while preserving stage-2 NMOS drive.", OpampCoreParams(l_in=4.0, l_stage2_p=10.0)),
            BatchCase("K1_stage2p10", "Longer stage-2 PMOS load alone may build gain with less slow-corner penalty than longer input PMOS.", OpampCoreParams(l_stage2_p=10.0)),
            BatchCase("K2_load10_stage2p10", "Longer first-stage load plus longer stage-2 PMOS load may be the cleanest two-stage ro-building combination.", OpampCoreParams(l_load=10.0, l_stage2_p=10.0)),
            BatchCase("K3_load12", "A stronger first-stage load-length move may be needed before gain improves materially.", OpampCoreParams(l_load=12.0)),
            BatchCase("K4_stage2p12", "A stronger stage-2 PMOS load-length move may raise gain while keeping stage-2 NMOS unchanged.", OpampCoreParams(l_stage2_p=12.0)),
            BatchCase("K5_load10_stage2p12", "If both stages need more ro, load10 plus stage2p12 is the next narrow combination.", OpampCoreParams(l_load=10.0, l_stage2_p=12.0)),
        ],
        "comp_shape": [
            baseline,
            BatchCase("C1_c200", "Lower compensation may recover GBW if the current core is overcompensated.", OpampCoreParams(c_comp=200e-15)),
            BatchCase("C2_c180", "A stronger compensation rollback tests whether GBW can move without immediate stability loss.", OpampCoreParams(c_comp=180e-15)),
            BatchCase("C3_stage2p10_c200", "Longer stage-2 PMOS load plus mild compensation rollback may improve gain/GBW balance.", OpampCoreParams(l_stage2_p=10.0, c_comp=200e-15)),
            BatchCase("C4_stage2p10_c180", "Longer stage-2 PMOS load plus stronger compensation rollback.", OpampCoreParams(l_stage2_p=10.0, c_comp=180e-15)),
            BatchCase("C5_load10_c200", "Longer first-stage load plus mild compensation rollback.", OpampCoreParams(l_load=10.0, c_comp=200e-15)),
            BatchCase("C6_load10_stage2p10_c200", "Longer first-stage load and longer stage-2 PMOS load with mild compensation rollback.", OpampCoreParams(l_load=10.0, l_stage2_p=10.0, c_comp=200e-15)),
            BatchCase("C7_load10_stage2p10_c180", "Same as C6 with stronger compensation rollback.", OpampCoreParams(l_load=10.0, l_stage2_p=10.0, c_comp=180e-15)),
        ],
        "output_finish": [
            baseline,
            BatchCase("O1_wout0p9", "Smaller helper PMOS may close the residual low swing with limited collateral damage.", OpampCoreParams(w_out_n=0.9)),
            BatchCase("O2_wout0p6", "Near-minimal helper PMOS tests whether low swing can close if helper influence is reduced further.", OpampCoreParams(w_out_n=0.6)),
            BatchCase("O3_stage2p10_wout0p9", "Longer stage-2 PMOS load plus smaller helper PMOS may improve gain and low swing together.", OpampCoreParams(l_stage2_p=10.0, w_out_n=0.9)),
            BatchCase("O4_load10_wout0p9", "Longer first-stage load plus smaller helper PMOS.", OpampCoreParams(l_load=10.0, w_out_n=0.9)),
            BatchCase("O5_load10_stage2p10_wout0p9", "Two-stage ro-building plus smaller helper PMOS.", OpampCoreParams(l_load=10.0, l_stage2_p=10.0, w_out_n=0.9)),
            BatchCase("O6_load10_stage2p10_wout0p6", "Aggressive output-finish variant on the best current credible gain-building combination.", OpampCoreParams(l_load=10.0, l_stage2_p=10.0, w_out_n=0.6)),
        ],
        "mixed_extreme": [
            baseline,
            BatchCase("M1_stage2p10_c200_wout0p9", "Longer stage-2 PMOS load, mild compensation rollback, and smaller helper PMOS as a balanced mixed branch.", OpampCoreParams(l_stage2_p=10.0, c_comp=200e-15, w_out_n=0.9)),
            BatchCase("M2_load10_stage2p10_c200_wout0p9", "Longer first-stage load and stage-2 PMOS load, mild compensation rollback, and smaller helper PMOS.", OpampCoreParams(l_load=10.0, l_stage2_p=10.0, c_comp=200e-15, w_out_n=0.9)),
            BatchCase("M3_stage2p12_c200_wout0p9", "Stronger stage-2 PMOS ro-building with mild compensation rollback and smaller helper PMOS.", OpampCoreParams(l_stage2_p=12.0, c_comp=200e-15, w_out_n=0.9)),
            BatchCase("M4_load12_stage2p12_c200_wout0p9", "Strongest currently credible ro-building mix with modest compensation rollback and reduced helper strength.", OpampCoreParams(l_load=12.0, l_stage2_p=12.0, c_comp=200e-15, w_out_n=0.9)),
        ],
    }


def render_batch_markdown(batch_name: str, payload: dict) -> str:
    lines = [
        f"# Batch {batch_name}",
        "",
        payload["purpose"],
        "",
        "| Case | TT AOL dB | TT IQ uA | TT Vlow V | TT Vsrc25 V | SS GBW kHz | FF AOL dB | FF GBW kHz | Leak nA | Raw Vos uV |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case in payload["cases"]:
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
    lines.extend(["", f"Best case by current priority: `{payload['best_case_by_priority']}`", ""])
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
        "# Autonomous Core Batches",
        "",
        "This directory contains autonomous batch screening runs for the current credible `v3` core hypotheses.",
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
            "purpose": f"Autonomous batch `{batch_name}` for current credible core hypotheses.",
            "cases": sorted(completed.values(), key=_rank_key),
            "failures": failures,
            "best_case_by_priority": sorted(completed.values(), key=_rank_key)[0]["case"] if completed else None,
        }
        outroot.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        (outroot / f"{batch_name}.md").write_text(render_batch_markdown(batch_name, payload), encoding="utf-8")

    return {
        "purpose": f"Autonomous batch `{batch_name}` for current credible core hypotheses.",
        "cases": sorted(completed.values(), key=_rank_key),
        "failures": failures,
        "best_case_by_priority": sorted(completed.values(), key=_rank_key)[0]["case"] if completed else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="append", dest="batches")
    parser.add_argument("--outdir", default="tmp/opamp_v3_autonomous_batches")
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
