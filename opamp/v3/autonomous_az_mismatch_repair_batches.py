from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import hdl21 as h

from components.frontend_az import FrontendAzParams
from components.opamp_az_top import OpampAzTopNoiseAndOffsetTbParams, OpampAzTopParams, run_noise_and_offset_monte_carlo, run_noise_and_offset_test
from tests.structural._helpers import init_sky130_install

from .autonomous_az_batches import _frontend_params, _timing, run_reduced_pvt_custom


@dataclass(frozen=True)
class AzMismatchRepairCase:
    name: str
    hypothesis: str
    frontend_params: FrontendAzParams
    timing: dict[str, float]


LOG_PATH: Path | None = None


def utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    line = f"[{utc_ts()}] {msg}"
    print(line, flush=True)
    if LOG_PATH is not None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")


def _top_tb_params(timing: dict[str, float], *, vdd: float = 1.8, temp_c: float = 27.0) -> OpampAzTopNoiseAndOffsetTbParams:
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


def build_cases() -> list[AzMismatchRepairCase]:
    baseline_timing = _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)
    return [
        AzMismatchRepairCase(
            name="repair_baseline",
            hypothesis="Current AZ baseline repair reference.",
            frontend_params=_frontend_params(c_az=200e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15),
            timing=baseline_timing,
        ),
        AzMismatchRepairCase(
            name="m4r1_cap300_wswn1p1_wswp1p6_nf2",
            hypothesis="Slightly softer big-switch branch may keep most MC benefit while avoiding deep-corner model failure.",
            frontend_params=_frontend_params(c_az=300e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15, w_sw_n=1.1, w_sw_p=1.6, nf_sw=2),
            timing=baseline_timing,
        ),
        AzMismatchRepairCase(
            name="m4r2_cap300_wswn1p2_wswp1p8_nf2",
            hypothesis="Intermediate big-switch sizing tests the highest MC gain that still survives deep PVT.",
            frontend_params=_frontend_params(c_az=300e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15, w_sw_n=1.2, w_sw_p=1.8, nf_sw=2),
            timing=baseline_timing,
        ),
        AzMismatchRepairCase(
            name="m4r3_cap300_wswn1p3_wswp2p0_nf1",
            hypothesis="Keep wide devices but remove switch finger split to reduce model stress in cold corners.",
            frontend_params=_frontend_params(c_az=300e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15, w_sw_n=1.3, w_sw_p=2.0, nf_sw=1),
            timing=baseline_timing,
        ),
        AzMismatchRepairCase(
            name="m4r4_cap300_wswn1p1_wswp1p6_lsw0p20_nf2",
            hypothesis="Longer softer switches may keep symmetry gains while backing away from cold-corner model limits.",
            frontend_params=_frontend_params(c_az=300e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15, w_sw_n=1.1, w_sw_p=1.6, l_sw=0.20, nf_sw=2),
            timing=baseline_timing,
        ),
        AzMismatchRepairCase(
            name="m3r1_cap200_wswn1p1_wswp1p6_rtop600",
            hypothesis="Safe big-switch branch around current baseline should improve MC without deep-PVT invalidity.",
            frontend_params=_frontend_params(c_az=200e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15, w_sw_n=1.1, w_sw_p=1.6, nf_sw=2),
            timing=baseline_timing,
        ),
        AzMismatchRepairCase(
            name="m3r2_cap200_wswn1p1_wswp1p6_rtop700",
            hypothesis="Combine safe big switches with slightly weaker top attenuation for a better MC/corner tradeoff.",
            frontend_params=_frontend_params(c_az=200e-15, r_vcm_top=7e2, r_vcm_bot=5.0, c_out_p=10e-15, w_sw_n=1.1, w_sw_p=1.6, nf_sw=2),
            timing=baseline_timing,
        ),
        AzMismatchRepairCase(
            name="m3r3_cap300_wswn1p1_wswp1p6_rtop700",
            hypothesis="Moderate cap increase plus safe big switches plus weaker top attenuation is the balanced repair candidate.",
            frontend_params=_frontend_params(c_az=300e-15, r_vcm_top=7e2, r_vcm_bot=5.0, c_out_p=10e-15, w_sw_n=1.1, w_sw_p=1.6, nf_sw=2),
            timing=baseline_timing,
        ),
    ]


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


def _rank_key(case: dict) -> tuple[float, float, float, float, float, float]:
    quick = case["quick_mc"]
    tt = case["top_tt"]
    return (
        float(quick["residual_offset_sigma_uV"]),
        float(quick["residual_offset_mean_uV"]),
        float(quick["pedestal_mid50_sigma_uV"]),
        float(tt["residual_offset_uV"]),
        float(tt["pedestal_mid50_uV"]),
        float(tt["settling_mid50_uV"]),
    )


def _render_markdown(payload: dict) -> str:
    lines = [
        "# AZ Mismatch-Repair Batch",
        "",
        f"Generated: `{utc_ts()}`",
        "",
        "| Case | TT Resid uV | TT Ped50 uV | TT Set50 uV | Quick MC Offset Sigma uV | Quick MC Offset Mean uV | Quick MC Ped Sigma uV | Quick MC Set Sigma uV | Survivor |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for case in payload["cases"]:
        tt = case["top_tt"]
        quick = case["quick_mc"]
        lines.append(
            f"| {case['case']} | "
            f"{float(tt['residual_offset_uV']):.2f} | {float(tt['pedestal_mid50_uV']):.2f} | {float(tt['settling_mid50_uV']):.2f} | "
            f"{float(quick['residual_offset_sigma_uV']):.2f} | {float(quick['residual_offset_mean_uV']):.2f} | "
            f"{float(quick['pedestal_mid50_sigma_uV']):.2f} | {float(quick['settling_mid50_sigma_uV']):.2f} | "
            f"{'yes' if case.get('survivor') else 'no'} |"
        )
    lines.extend(["", f"Best quick-MC case: `{payload.get('best_case_by_priority')}`", ""])
    if payload.get("survivors"):
        lines.append("## Survivors")
        lines.append("")
        for case in payload["survivors"]:
            lines.append(f"### {case['case']}")
            lines.append("")
            if "reduced_pvt" in case:
                rpvt = case["reduced_pvt"]
                lines.append(
                    f"- Reduced-PVT worst: residual `{float(rpvt['worst_residual_offset_uV']):.2f} uV`, pedestal_mid50 `{float(rpvt['worst_pedestal_mid50_uV']):.2f} uV`, settling_mid50 `{float(rpvt['worst_settling_mid50_uV']):.2f} uV`"
                )
            if "full_mc" in case:
                mc = case["full_mc"]
                lines.append(
                    f"- Full MC: residual sigma `{float(mc['residual_offset_sigma_uV']):.2f} uV`, mean `{float(mc['residual_offset_mean_uV']):.2f} uV`, pedestal sigma `{float(mc['pedestal_mid50_sigma_uV']):.2f} uV`, settling sigma `{float(mc['settling_mid50_sigma_uV']):.2f} uV`"
                )
            lines.append("")
    if payload["failures"]:
        lines.append("## Failures")
        lines.append("")
        for failure in payload["failures"]:
            lines.append(f"- `{failure['case']}`: `{failure['error']}`")
        lines.append("")
    return "\n".join(lines)


def _top_tt(case: AzMismatchRepairCase) -> dict:
    params = OpampAzTopParams(frontend_az_params=case.frontend_params)
    return run_noise_and_offset_test(params, _top_tb_params(case.timing), corner=h.pdk.Corner.TYP)["metrics"]


def _quick_mc(case: AzMismatchRepairCase, *, samples: int) -> dict:
    params = OpampAzTopParams(frontend_az_params=case.frontend_params)
    metrics = run_noise_and_offset_monte_carlo(params, _top_tb_params(case.timing), samples=samples, model_section="tt_mm")["metrics"]
    return {
        "residual_offset_mean_uV": float(metrics["residual_offset_mean_uV"]),
        "residual_offset_sigma_uV": float(metrics["residual_offset_sigma_uV"]),
        "residual_offset_p99_uV": float(metrics["residual_offset_p99_uV"]),
        "pedestal_mid50_mean_uV": float(metrics["pedestal_mid50_mean_uV"]),
        "pedestal_mid50_sigma_uV": float(metrics["pedestal_mid50_sigma_uV"]),
        "settling_mid50_mean_uV": float(metrics["settling_mid50_mean_uV"]),
        "settling_mid50_sigma_uV": float(metrics["settling_mid50_sigma_uV"]),
        "samples_completed": int(metrics["samples_completed"]),
        "samples_failed": int(metrics["samples_failed"]),
    }


def _full_mc(case: AzMismatchRepairCase, *, samples: int) -> dict:
    return _quick_mc(case, samples=samples)


def run_batch(*, outdir: str, quick_mc_samples: int = 20, full_mc_samples: int = 50, survivor_count: int = 3) -> Path:
    init_sky130_install()
    outroot = Path(outdir)
    outroot.mkdir(parents=True, exist_ok=True)
    global LOG_PATH
    LOG_PATH = outroot / "run.log"

    json_path = outroot / "mismatch_repair.json"
    if json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        completed = {case["case"]: case for case in payload.get("cases", [])}
        failures = payload.get("failures", [])
    else:
        completed = {}
        failures = []

    for case in build_cases():
        if case.name in completed and "quick_mc" in completed[case.name] and "top_tt" in completed[case.name]:
            log(f"[az_mismatch_repair] skip quick {case.name}")
            continue
        log(f"[az_mismatch_repair] running quick screen {case.name}")
        try:
            entry = {
                "case": case.name,
                "hypothesis": case.hypothesis,
                "frontend_params": _serialize_frontend_params(case.frontend_params),
                "timing": case.timing,
                "top_tt": _top_tt(case),
                "quick_mc": _quick_mc(case, samples=quick_mc_samples),
            }
            completed[case.name] = entry
            log(
                f"[az_mismatch_repair] done quick {case.name} "
                f"tt_resid={float(entry['top_tt']['residual_offset_uV']):.2f}uV "
                f"quick_sigma={float(entry['quick_mc']['residual_offset_sigma_uV']):.2f}uV "
                f"quick_ped_sigma={float(entry['quick_mc']['pedestal_mid50_sigma_uV']):.2f}uV "
                f"quick_set_sigma={float(entry['quick_mc']['settling_mid50_sigma_uV']):.2f}uV"
            )
        except Exception as err:
            failures.append({"case": case.name, "error": f"{type(err).__name__}: {err}"})
            log(f"[az_mismatch_repair] failed quick {case.name}: {type(err).__name__}: {err}")

        ranked = sorted(completed.values(), key=_rank_key)
        survivors = {item["case"] for item in ranked[: max(1, min(survivor_count, len(ranked)))]}
        for item in completed.values():
            item["survivor"] = item["case"] in survivors
        payload = {
            "cases": ranked,
            "survivors": [item for item in ranked if item.get("survivor")],
            "failures": failures,
            "best_case_by_priority": ranked[0]["case"] if ranked else None,
        }
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        (outroot / "mismatch_repair.md").write_text(_render_markdown(payload), encoding="utf-8")

    ranked = sorted(completed.values(), key=_rank_key)
    survivors = ranked[: max(1, min(survivor_count, len(ranked)))]
    for item in completed.values():
        item["survivor"] = item["case"] in {case["case"] for case in survivors}
    for case in survivors:
        if "reduced_pvt" in case and "full_mc" in case:
            log(f"[az_mismatch_repair] skip deep {case['case']}")
            continue
        original = next(candidate for candidate in build_cases() if candidate.name == case["case"])
        log(f"[az_mismatch_repair] running deep screen {case['case']}")
        try:
            params = OpampAzTopParams(frontend_az_params=original.frontend_params)
            case["reduced_pvt"] = run_reduced_pvt_custom(params, original.timing)
            case["full_mc"] = _full_mc(original, samples=full_mc_samples)
            log(
                f"[az_mismatch_repair] done deep {case['case']} "
                f"rpvt_worst_resid={float(case['reduced_pvt']['worst_residual_offset_uV']):.2f}uV "
                f"full_sigma={float(case['full_mc']['residual_offset_sigma_uV']):.2f}uV"
            )
        except Exception as err:
            failures.append({"case": case["case"], "error": f"{type(err).__name__}: {err}"})
            log(f"[az_mismatch_repair] failed deep {case['case']}: {type(err).__name__}: {err}")
        payload = {
            "cases": ranked,
            "survivors": [item for item in ranked if item.get("survivor")],
            "failures": failures,
            "best_case_by_priority": ranked[0]["case"] if ranked else None,
        }
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        (outroot / "mismatch_repair.md").write_text(_render_markdown(payload), encoding="utf-8")

    log("[az_mismatch_repair] complete")
    return outroot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="tmp/opamp_v3_az_mismatch_repair")
    parser.add_argument("--quick-mc-samples", type=int, default=20)
    parser.add_argument("--full-mc-samples", type=int, default=50)
    parser.add_argument("--survivor-count", type=int, default=3)
    args = parser.parse_args(argv)
    outroot = run_batch(
        outdir=args.outdir,
        quick_mc_samples=args.quick_mc_samples,
        full_mc_samples=args.full_mc_samples,
        survivor_count=args.survivor_count,
    )
    print(outroot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
