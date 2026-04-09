from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import hdl21 as h

from opamp.v1.frontend_az import (
    FrontendAzParams,
    FrontendAzPedestalZeroInputTbParams,
    FrontendAzSettlingInPhaseWindowTbParams,
    run_pedestal_zero_input_test,
    run_settling_in_phase_window_test,
)
from opamp.v1.opamp_az_top import (
    OpampAzTopNoiseAndOffsetTbParams,
    OpampAzTopParams,
    run_noise_and_offset_test,
)
from opamp.v1.tests.structural._helpers import init_sky130_install
from .specs import OpampAzV3MaximumSpec, OpampAzV3TargetSpec


@dataclass(frozen=True)
class AzBatchCase:
    name: str
    hypothesis: str
    frontend_params: FrontendAzParams
    timing: dict[str, float]


REDUCED_PVT_CASES = {
    "TT_V1.80_T27C": (h.pdk.Corner.TYP, 1.8, 27.0),
    "SS_V1.60_T125C": (h.pdk.Corner.SLOW, 1.6, 125.0),
    "FF_V1.98_T-40C": (h.pdk.Corner.FAST, 1.98, -40.0),
    "SS_V1.60_T-40C": (h.pdk.Corner.SLOW, 1.6, -40.0),
    "FF_V1.98_T125C": (h.pdk.Corner.FAST, 1.98, 125.0),
}


def utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{utc_ts()}] {msg}", flush=True)


def _frontend_params(**updates) -> FrontendAzParams:
    base = FrontendAzParams()
    payload = {
        "c_az": float(base.c_az),
        "w_sw_n": float(base.w_sw_n),
        "w_sw_p": float(base.w_sw_p),
        "l_sw": float(base.l_sw),
        "nf_sw": int(base.nf_sw),
        "m_sw": int(base.m_sw),
        "use_dummy_switch": bool(base.use_dummy_switch),
        "r_vcm_top": float(base.r_vcm_top),
        "r_vcm_bot": float(base.r_vcm_bot),
        "r_out_p": float(base.r_out_p),
        "r_out_n": float(base.r_out_n),
        "c_out_p": float(base.c_out_p),
        "c_out_n": float(base.c_out_n),
        "c_corr_n_scale": float(base.c_corr_n_scale),
    }
    payload.update(updates)
    return FrontendAzParams(**payload)


def _default_timing() -> dict[str, float]:
    return {
        "period": 20e-6,
        "dead_time": 2e-6,
        "phi1_share": 0.4,
        "phi2_share": 0.2,
        "phi3_share": 0.4,
        "tstop": 200e-6,
        "tstep": 100e-9,
    }


def _timing(**updates) -> dict[str, float]:
    payload = _default_timing()
    payload.update(updates)
    return payload


def _serialize_frontend_params(params: FrontendAzParams) -> dict[str, float | int | bool]:
    return {
        "c_az": float(params.c_az),
        "w_sw_n": float(params.w_sw_n),
        "w_sw_p": float(params.w_sw_p),
        "l_sw": float(params.l_sw),
        "nf_sw": int(params.nf_sw),
        "m_sw": int(params.m_sw),
        "use_dummy_switch": bool(params.use_dummy_switch),
        "r_vcm_top": float(params.r_vcm_top),
        "r_vcm_bot": float(params.r_vcm_bot),
        "r_out_p": float(params.r_out_p),
        "r_out_n": float(params.r_out_n),
        "c_out_p": float(params.c_out_p),
        "c_out_n": float(params.c_out_n),
        "c_corr_n_scale": float(params.c_corr_n_scale),
    }


def build_batches() -> dict[str, list[AzBatchCase]]:
    baseline = AzBatchCase(
        name="baseline",
        hypothesis="Current best known baseline AZ point from the ledger.",
        frontend_params=_frontend_params(c_az=70e-15, r_vcm_top=8e2, r_vcm_bot=5.0),
        timing=_default_timing(),
    )
    return {
        "path_topology": [
            baseline,
            AzBatchCase("path_p_soft_2", "Slightly weaker non-inverting live-path coupling may reduce corner pedestal kick.", _frontend_params(c_az=70e-15, r_vcm_top=8e2, r_vcm_bot=5.0, r_out_p=2.0), _default_timing()),
            AzBatchCase("path_p_soft_5", "More isolated non-inverting live path tests whether FF/hot pedestal is correction-kick dominated.", _frontend_params(c_az=70e-15, r_vcm_top=8e2, r_vcm_bot=5.0, r_out_p=5.0), _default_timing()),
            AzBatchCase("path_both_soft_2", "Slightly weaker coupling on both live paths may reduce switching kick symmetry errors.", _frontend_params(c_az=70e-15, r_vcm_top=8e2, r_vcm_bot=5.0, r_out_p=2.0, r_out_n=2.0), _default_timing()),
            AzBatchCase("shunt_p_10f", "A tiny shunt on the positive core-facing node may absorb edge feedthrough without killing the live path.", _frontend_params(c_az=70e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15), _default_timing()),
            AzBatchCase("shunt_both_10f", "Tiny symmetric shunts may reduce pedestal if edge-feedthrough dominates both sides.", _frontend_params(c_az=70e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15, c_out_n=10e-15), _default_timing()),
            AzBatchCase("dummy_switches", "Dummy switches may reduce charge injection asymmetry without topology changes.", _frontend_params(c_az=70e-15, r_vcm_top=8e2, r_vcm_bot=5.0, use_dummy_switch=True), _default_timing()),
        ],
        "cap_bank": [
            baseline,
            AzBatchCase("cap100", "Larger AZ cap may reduce pedestal and mismatch sensitivity.", _frontend_params(c_az=100e-15, r_vcm_top=8e2, r_vcm_bot=5.0), _default_timing()),
            AzBatchCase("cap150", "More aggressive AZ cap increase.", _frontend_params(c_az=150e-15, r_vcm_top=8e2, r_vcm_bot=5.0), _default_timing()),
            AzBatchCase("cap200", "Largest AZ cap in the first exploration band.", _frontend_params(c_az=200e-15, r_vcm_top=8e2, r_vcm_bot=5.0), _default_timing()),
            AzBatchCase("cap100_path2", "Cap increase plus mild positive live-path isolation.", _frontend_params(c_az=100e-15, r_vcm_top=8e2, r_vcm_bot=5.0, r_out_p=2.0), _default_timing()),
            AzBatchCase("cap150_path2", "Cap increase plus mild positive live-path isolation.", _frontend_params(c_az=150e-15, r_vcm_top=8e2, r_vcm_bot=5.0, r_out_p=2.0), _default_timing()),
            AzBatchCase("cap200_shuntp10", "Large cap plus tiny positive shunt to test pedestal filtering.", _frontend_params(c_az=200e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15), _default_timing()),
        ],
        "timing_profiles": [
            baseline,
            AzBatchCase("freq10k", "Lower AZ frequency may reduce fast-corner dynamic error if current topology is edge dominated.", baseline.frontend_params, _timing(period=100e-6, tstop=600e-6, dead_time=2e-6)),
            AzBatchCase("freq100k", "Higher AZ frequency tests dynamic robustness.", baseline.frontend_params, _timing(period=10e-6, tstop=100e-6, dead_time=1e-6)),
            AzBatchCase("freq200k", "Upper timing-band stress point.", baseline.frontend_params, _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)),
            AzBatchCase("dead10ns", "Minimal non-overlap may reduce dead-time hold error if overlap is still avoided.", baseline.frontend_params, _timing(dead_time=10e-9, tstop=120e-6)),
            AzBatchCase("dead50ns", "Spec-allowed wider non-overlap with much smaller dead time than the current baseline.", baseline.frontend_params, _timing(dead_time=50e-9, tstop=120e-6)),
            AzBatchCase("duty_live50", "Longer PHI3 live window may improve usable interior settling.", baseline.frontend_params, _timing(phi1_share=0.35, phi2_share=0.15, phi3_share=0.50)),
            AzBatchCase("duty_apply25", "Slightly stronger apply window tests whether correction underdrive is the corner problem.", baseline.frontend_params, _timing(phi1_share=0.35, phi2_share=0.25, phi3_share=0.40)),
        ],
        "finish_rc": [
            baseline,
            AzBatchCase("rbot10", "Slightly larger bottom attenuator resistor may soften correction kick.", _frontend_params(c_az=70e-15, r_vcm_top=8e2, r_vcm_bot=10.0), _default_timing()),
            AzBatchCase("rtop600", "Slightly smaller top resistor strengthens sensed correction.", _frontend_params(c_az=70e-15, r_vcm_top=6e2, r_vcm_bot=5.0), _default_timing()),
            AzBatchCase("rtop1000", "Slightly larger top resistor weakens sensed correction.", _frontend_params(c_az=70e-15, r_vcm_top=1e3, r_vcm_bot=5.0), _default_timing()),
            AzBatchCase("rtop1000_rbot10", "Weaker attenuation path in both directions.", _frontend_params(c_az=70e-15, r_vcm_top=1e3, r_vcm_bot=10.0), _default_timing()),
            AzBatchCase("rtop600_rbot10", "Stronger top path plus softer bottom return.", _frontend_params(c_az=70e-15, r_vcm_top=6e2, r_vcm_bot=10.0), _default_timing()),
            AzBatchCase("cap150_rtop1000", "One cap winner candidate plus weaker sensed correction.", _frontend_params(c_az=150e-15, r_vcm_top=1e3, r_vcm_bot=5.0), _default_timing()),
            AzBatchCase("cap150_rbot10", "One cap winner candidate plus softer bottom return.", _frontend_params(c_az=150e-15, r_vcm_top=8e2, r_vcm_bot=10.0), _default_timing()),
        ],
    }


def _make_top_params(frontend_params: FrontendAzParams) -> OpampAzTopParams:
    return OpampAzTopParams(frontend_az_params=frontend_params)


def _frontend_ped_tb(timing: dict[str, float], *, vdd: float = 1.8) -> FrontendAzPedestalZeroInputTbParams:
    return FrontendAzPedestalZeroInputTbParams(
        vdd=vdd,
        period=timing["period"],
        dead_time=timing["dead_time"],
        phi1_share=timing["phi1_share"],
        phi2_share=timing["phi2_share"],
        phi3_share=timing["phi3_share"],
        tstop=timing["tstop"],
        tstep=timing["tstep"],
    )


def _frontend_settle_tb(timing: dict[str, float], *, vdd: float = 1.8) -> FrontendAzSettlingInPhaseWindowTbParams:
    return FrontendAzSettlingInPhaseWindowTbParams(
        vdd=vdd,
        period=timing["period"],
        dead_time=timing["dead_time"],
        phi1_share=timing["phi1_share"],
        phi2_share=timing["phi2_share"],
        phi3_share=timing["phi3_share"],
        tstop=timing["tstop"],
        tstep=timing["tstep"],
    )


def _top_tb(timing: dict[str, float], *, vdd: float, temp_c: float) -> OpampAzTopNoiseAndOffsetTbParams:
    return OpampAzTopNoiseAndOffsetTbParams(
        vdd=vdd,
        period=timing["period"],
        dead_time=timing["dead_time"],
        phi1_share=timing["phi1_share"],
        phi2_share=timing["phi2_share"],
        phi3_share=timing["phi3_share"],
        tstop=timing["tstop"],
        tstep=timing["tstep"],
        temp_c=temp_c,
    )


def run_reduced_pvt_custom(dut_params: OpampAzTopParams, timing: dict[str, float]) -> dict:
    results = {}
    worst_residual = -float("inf")
    worst_ped_mid50 = -float("inf")
    worst_set_mid50 = -float("inf")
    for label, (corner, vdd, temp_c) in REDUCED_PVT_CASES.items():
        tb = _top_tb(timing, vdd=vdd, temp_c=temp_c)
        result = run_noise_and_offset_test(dut_params, tb, corner=corner)
        metrics = result["metrics"]
        results[label] = metrics
        worst_residual = max(worst_residual, float(metrics["residual_offset_uV"]))
        worst_ped_mid50 = max(worst_ped_mid50, float(metrics["pedestal_mid50_uV"]))
        worst_set_mid50 = max(worst_set_mid50, float(metrics["settling_mid50_uV"]))
    return {
        "cases": results,
        "worst_residual_offset_uV": worst_residual,
        "worst_pedestal_mid50_uV": worst_ped_mid50,
        "worst_settling_mid50_uV": worst_set_mid50,
    }


def run_case(case: AzBatchCase) -> dict:
    top_params = _make_top_params(case.frontend_params)
    nominal_tt = run_noise_and_offset_test(top_params, _top_tb(case.timing, vdd=1.8, temp_c=27.0), corner=h.pdk.Corner.TYP)["metrics"]
    frontend_ped = run_pedestal_zero_input_test(case.frontend_params, _frontend_ped_tb(case.timing), corner=h.pdk.Corner.TYP)["metrics"]
    frontend_settle = run_settling_in_phase_window_test(case.frontend_params, _frontend_settle_tb(case.timing), corner=h.pdk.Corner.TYP)["metrics"]
    reduced_pvt = run_reduced_pvt_custom(top_params, case.timing)
    return {
        "case": case.name,
        "hypothesis": case.hypothesis,
        "frontend_params": _serialize_frontend_params(case.frontend_params),
        "timing": case.timing,
        "frontend_tt": {
            "pedestal_zero_input": frontend_ped,
            "settling_in_phase_window": frontend_settle,
        },
        "top_tt": nominal_tt,
        "reduced_pvt": reduced_pvt,
    }


def _rank_key(case: dict) -> tuple[float, float, float, float, float, float]:
    reduced = case["reduced_pvt"]
    nominal = case["top_tt"]
    return (
        float(reduced["worst_residual_offset_uV"]),
        float(reduced["worst_pedestal_mid50_uV"]),
        float(reduced["worst_settling_mid50_uV"]),
        float(nominal["residual_offset_uV"]),
        float(nominal["pedestal_mid50_uV"]),
        float(nominal["settling_mid50_uV"]),
    )


def render_batch_markdown(batch_name: str, payload: dict) -> str:
    target = OpampAzV3TargetSpec()
    maximum = OpampAzV3MaximumSpec()
    lines = [
        f"# AZ Batch {batch_name}",
        "",
        payload["purpose"],
        "",
        f"Generated: `{utc_ts()}`",
        "",
        "| Case | TT Resid uV | TT Ped50 uV | TT Set50 uV | RPVT Worst Resid uV | RPVT Worst Ped50 uV | RPVT Worst Set50 uV | FPed uV | FSet50 uV |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case in payload["cases"]:
        nominal = case["top_tt"]
        rpvt = case["reduced_pvt"]
        fped = case["frontend_tt"]["pedestal_zero_input"]
        fset = case["frontend_tt"]["settling_in_phase_window"]
        lines.append(
            f"| {case['case']} | "
            f"{float(nominal['residual_offset_uV']):.2f} | {float(nominal['pedestal_mid50_uV']):.2f} | {float(nominal['settling_mid50_uV']):.2f} | "
            f"{float(rpvt['worst_residual_offset_uV']):.2f} | {float(rpvt['worst_pedestal_mid50_uV']):.2f} | {float(rpvt['worst_settling_mid50_uV']):.2f} | "
            f"{float(fped['pedestal_uV']):.2f} | {float(fset['settling_mid50_uV']):.2f} |"
        )
    lines.extend(
        [
            "",
            f"Best case by current priority: `{payload['best_case_by_priority']}`",
            "",
            "## Spec Anchors",
            "",
            f"- minimum residual offset after AZ: `<= {target.residual_offset_uV_max} uV`",
            f"- minimum pedestal mid50: `<= {target.pedestal_mid50_uV_max} uV`",
            f"- minimum settling mid50: `<= {target.settling_mid50_uV_max} uV`",
            f"- maximum residual offset after AZ: `<= {maximum.residual_offset_uV_max} uV`",
            f"- maximum pedestal mid50: `<= {maximum.pedestal_mid50_uV_max} uV`",
            f"- maximum settling mid50: `<= {maximum.settling_mid50_uV_max} uV`",
            "",
        ]
    )
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
        "# Autonomous AZ Batches",
        "",
        "Autonomous research batches for the current `AZ` top-level path.",
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


def run_batch(batch_name: str, cases: list[AzBatchCase], outroot: Path) -> dict:
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
            log(f"[{batch_name}] skip {case.name}")
            continue
        log(f"[{batch_name}] running {case.name}")
        try:
            completed[case.name] = run_case(case)
            top_tt = completed[case.name]["top_tt"]
            rpvt = completed[case.name]["reduced_pvt"]
            log(
                f"[{batch_name}] done {case.name} "
                f"tt_resid={float(top_tt['residual_offset_uV']):.2f}uV "
                f"tt_ped50={float(top_tt['pedestal_mid50_uV']):.2f}uV "
                f"tt_set50={float(top_tt['settling_mid50_uV']):.2f}uV "
                f"rpvt_worst_resid={float(rpvt['worst_residual_offset_uV']):.2f}uV "
                f"rpvt_worst_ped50={float(rpvt['worst_pedestal_mid50_uV']):.2f}uV "
                f"rpvt_worst_set50={float(rpvt['worst_settling_mid50_uV']):.2f}uV"
            )
        except Exception as err:
            failures.append({"case": case.name, "error": f"{type(err).__name__}: {err}"})
            log(f"[{batch_name}] failed {case.name}: {type(err).__name__}: {err}")
        payload = {
            "purpose": f"Autonomous AZ batch `{batch_name}`.",
            "cases": sorted(completed.values(), key=_rank_key),
            "failures": failures,
            "best_case_by_priority": sorted(completed.values(), key=_rank_key)[0]["case"] if completed else None,
        }
        outroot.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        (outroot / f"{batch_name}.md").write_text(render_batch_markdown(batch_name, payload), encoding="utf-8")
        case_dir = outroot / "cases"
        case_dir.mkdir(parents=True, exist_ok=True)
        if case.name in completed:
            (case_dir / f"{batch_name}__{case.name}.json").write_text(
                json.dumps(completed[case.name], indent=2, sort_keys=True), encoding="utf-8"
            )

    return {
        "purpose": f"Autonomous AZ batch `{batch_name}`.",
        "cases": sorted(completed.values(), key=_rank_key),
        "failures": failures,
        "best_case_by_priority": sorted(completed.values(), key=_rank_key)[0]["case"] if completed else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="append", dest="batches")
    parser.add_argument("--outdir", default="tmp/opamp_v3_autonomous_az_batches")
    args = parser.parse_args(argv)

    init_sky130_install()
    outroot = Path(args.outdir)
    batches = build_batches()
    selected = args.batches or list(batches.keys())
    results: dict[str, dict] = {}
    log(f"starting autonomous AZ batches: {selected}")
    for batch_name in selected:
        if batch_name not in batches:
            raise SystemExit(f"Unknown batch: {batch_name}")
        results[batch_name] = run_batch(batch_name, batches[batch_name], outroot)
        write_index(outroot, results)
    log("autonomous AZ batches complete")
    print(outroot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
