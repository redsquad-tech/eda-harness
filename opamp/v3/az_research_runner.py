from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import hdl21 as h

from opamp.v1.frontend_az import FrontendAzParams
from opamp.v1.opamp_az_top import OpampAzTopNoiseAndOffsetTbParams, OpampAzTopParams
from opamp.v1.tests.structural._helpers import init_sky130_install

from .autonomous_az_batches import (
    REDUCED_PVT_CASES,
    _default_timing,
    _frontend_params,
    _frontend_ped_tb,
    _frontend_settle_tb,
    _make_top_params,
    _rank_key,
    _serialize_frontend_params,
    _top_tb,
    run_reduced_pvt_custom,
)
from .az_research_plan import AzResearchHypothesis, AzResearchTest, AzResearchVariant, build_az_research_plan, build_az_research_tests
from opamp.v1.frontend_az import run_pedestal_zero_input_test, run_settling_in_phase_window_test
from opamp.v1.opamp_az_top import run_noise_and_offset_test
from opamp.v1.opamp_az_top import run_noise_and_offset_monte_carlo


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


@dataclass(frozen=True)
class ExecutableAzVariant:
    variant: AzResearchVariant
    frontend_params: FrontendAzParams | None
    timing: dict[str, float] | None
    runnable: bool
    unavailable_reason: str | None = None


def _timing(**updates: float) -> dict[str, float]:
    payload = _default_timing()
    payload.update(updates)
    return payload


def _tt_top_metrics(frontend_params: FrontendAzParams, timing: dict[str, float]) -> dict:
    top_params = _make_top_params(frontend_params)
    return run_noise_and_offset_test(
        top_params,
        _top_tb(timing, vdd=1.8, temp_c=27.0),
        corner=h.pdk.Corner.TYP,
    )["metrics"]


def _frontend_tt_metrics(frontend_params: FrontendAzParams, timing: dict[str, float]) -> dict:
    return {
        "pedestal_zero_input": run_pedestal_zero_input_test(
            frontend_params,
            _frontend_ped_tb(timing),
            corner=h.pdk.Corner.TYP,
        )["metrics"],
        "settling_in_phase_window": run_settling_in_phase_window_test(
            frontend_params,
            _frontend_settle_tb(timing),
            corner=h.pdk.Corner.TYP,
        )["metrics"],
    }


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


def _timing_sanity_metrics(frontend_params: FrontendAzParams, timing: dict[str, float]) -> dict:
    top_params = _make_top_params(frontend_params)
    probes = {
        "deadtime_half": {**timing, "dead_time": max(float(timing["dead_time"]) * 0.5, 10e-9)},
        "deadtime_1p5x": {**timing, "dead_time": float(timing["dead_time"]) * 1.5},
        "period_1p2x": {**timing, "period": float(timing["period"]) * 1.2, "tstop": float(timing["tstop"]) * 1.2},
    }
    results: dict[str, dict] = {}
    for label, probe_timing in probes.items():
        tt = run_noise_and_offset_test(top_params, _top_tb(probe_timing, vdd=1.8, temp_c=27.0), corner=h.pdk.Corner.TYP)["metrics"]
        ff = run_noise_and_offset_test(top_params, _top_tb(probe_timing, vdd=1.98, temp_c=125.0), corner=h.pdk.Corner.FAST)["metrics"]
        results[label] = {"TT_V1.80_T27C": tt, "FF_V1.98_T125C": ff}
    return results


def _deadtime_sweep_metrics(frontend_params: FrontendAzParams, timing: dict[str, float]) -> dict:
    top_params = _make_top_params(frontend_params)
    base_dead = float(timing["dead_time"])
    dead_times = [max(50e-9, 0.5 * base_dead), base_dead, min(float(timing["period"]) / 6.0, 2.0 * base_dead)]
    results: dict[str, dict] = {}
    for dead in dead_times:
        probe_timing = {**timing, "dead_time": dead}
        label = f"dead_{dead * 1e9:.0f}ns"
        tt = run_noise_and_offset_test(top_params, _top_tb(probe_timing, vdd=1.8, temp_c=27.0), corner=h.pdk.Corner.TYP)["metrics"]
        ff = run_noise_and_offset_test(top_params, _top_tb(probe_timing, vdd=1.98, temp_c=125.0), corner=h.pdk.Corner.FAST)["metrics"]
        results[label] = {"TT_V1.80_T27C": tt, "FF_V1.98_T125C": ff}
    return results


def _test_by_id() -> dict[str, AzResearchTest]:
    return {test.test_id: test for test in build_az_research_tests()}


def build_executable_variants() -> dict[str, ExecutableAzVariant]:
    variants: dict[str, ExecutableAzVariant] = {}
    for hypothesis in build_az_research_plan():
        for variant in hypothesis.variants:
            if variant.variant_id == "az_h1_v1_cap200_shuntp10_freq200k":
                frontend = _frontend_params(c_az=200e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15)
                timing = _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)
                variants[variant.variant_id] = ExecutableAzVariant(variant, frontend, timing, True)
            elif variant.variant_id == "az_h1_v2_cap150_shuntp10_freq200k":
                frontend = _frontend_params(c_az=150e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15)
                timing = _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)
                variants[variant.variant_id] = ExecutableAzVariant(variant, frontend, timing, True)
            elif variant.variant_id == "az_h1_v3_shunt_both10_freq200k":
                frontend = _frontend_params(c_az=70e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15, c_out_n=10e-15)
                timing = _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)
                variants[variant.variant_id] = ExecutableAzVariant(variant, frontend, timing, True)
            elif variant.variant_id == "az_h2_v1_cap200_shuntp10_rtop600":
                frontend = _frontend_params(c_az=200e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15)
                timing = _default_timing()
                variants[variant.variant_id] = ExecutableAzVariant(variant, frontend, timing, True)
            elif variant.variant_id == "az_h2_v2_cap200_shuntp10_rtop600_freq200k":
                frontend = _frontend_params(c_az=200e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15)
                timing = _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)
                variants[variant.variant_id] = ExecutableAzVariant(variant, frontend, timing, True)
            elif variant.variant_id == "az_h2_v3_cap150_shuntp10_rtop600_freq200k":
                frontend = _frontend_params(c_az=150e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15)
                timing = _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)
                variants[variant.variant_id] = ExecutableAzVariant(variant, frontend, timing, True)
            elif variant.variant_id == "az_h3_v1_cap200_shuntp10_dead50ns":
                frontend = _frontend_params(c_az=200e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15)
                timing = _timing(dead_time=50e-9, tstop=120e-6)
                variants[variant.variant_id] = ExecutableAzVariant(variant, frontend, timing, True)
            elif variant.variant_id == "az_h3_v2_cap200_shuntp10_dead100ns":
                frontend = _frontend_params(c_az=200e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15)
                timing = _timing(dead_time=100e-9, tstop=120e-6)
                variants[variant.variant_id] = ExecutableAzVariant(variant, frontend, timing, True)
            elif variant.variant_id == "az_h3_v3_cap200_shuntp10_dead200ns":
                frontend = _frontend_params(c_az=200e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15)
                timing = _timing(dead_time=200e-9, tstop=120e-6)
                variants[variant.variant_id] = ExecutableAzVariant(variant, frontend, timing, True)
            elif variant.hypothesis_id == "az_h4":
                if variant.variant_id == "az_h4_v1_mc_cap200_shuntp10_freq200k":
                    frontend = _frontend_params(c_az=200e-15, r_vcm_top=8e2, r_vcm_bot=5.0, c_out_p=10e-15)
                    timing = _timing(period=5e-6, tstop=60e-6, dead_time=0.5e-6)
                    variants[variant.variant_id] = ExecutableAzVariant(variant, frontend, timing, True)
                elif variant.variant_id == "az_h4_v2_mc_cap200_shuntp10_rtop600":
                    frontend = _frontend_params(c_az=200e-15, r_vcm_top=6e2, r_vcm_bot=5.0, c_out_p=10e-15)
                    timing = _default_timing()
                    variants[variant.variant_id] = ExecutableAzVariant(variant, frontend, timing, True)
                else:
                    raise ValueError(f"Unhandled AZ research MC variant: {variant.variant_id}")
            else:
                raise ValueError(f"Unhandled AZ research variant: {variant.variant_id}")
    return variants


def _run_variant(executable: ExecutableAzVariant, hypothesis: AzResearchHypothesis) -> dict:
    if not executable.runnable or executable.frontend_params is None or executable.timing is None:
        return {
            "variant_id": executable.variant.variant_id,
            "hypothesis_id": executable.variant.hypothesis_id,
            "status": "unavailable",
            "reason": executable.unavailable_reason,
        }

    test_map = _test_by_id()
    results: dict[str, dict] = {}
    top_params = _make_top_params(executable.frontend_params)
    for test_id in hypothesis.tests:
        test = test_map[test_id]
        if test_id == "az_tt_precision":
            results[test_id] = _tt_top_metrics(executable.frontend_params, executable.timing)
        elif test_id == "az_reduced_pvt":
            results[test_id] = run_reduced_pvt_custom(top_params, executable.timing)
        elif test_id == "az_nominal_frontend":
            results[test_id] = _frontend_tt_metrics(executable.frontend_params, executable.timing)
        elif test_id == "az_timing_sanity":
            results[test_id] = _timing_sanity_metrics(executable.frontend_params, executable.timing)
        elif test_id == "az_deadtime_sweep":
            results[test_id] = _deadtime_sweep_metrics(executable.frontend_params, executable.timing)
        elif test_id in {"az_mc_offset", "az_mc_pedestal_settling"}:
            mc = run_noise_and_offset_monte_carlo(top_params, _top_tb_params(executable.timing, vdd=1.8, temp_c=27.0), samples=50, model_section="tt_mm")
            metrics = mc["metrics"]
            if test_id == "az_mc_offset":
                results[test_id] = {
                    "mean_uV": float(metrics["residual_offset_mean_uV"]),
                    "sigma_uV": float(metrics["residual_offset_sigma_uV"]),
                    "p99_uV": float(metrics["residual_offset_p99_uV"]),
                    "max_uV": float(metrics["residual_offset_max_uV"]),
                    "pass_rate_vs_target": float(metrics["residual_offset_pass_rate_vs_target"]),
                    "pass_rate_vs_maximum": float(metrics["residual_offset_pass_rate_vs_maximum"]),
                    "samples_completed": int(metrics["samples_completed"]),
                    "samples_failed": int(metrics["samples_failed"]),
                }
            else:
                results[test_id] = {
                    "pedestal_mean_uV": float(metrics["pedestal_mid50_mean_uV"]),
                    "pedestal_sigma_uV": float(metrics["pedestal_mid50_sigma_uV"]),
                    "pedestal_p99_uV": float(metrics["pedestal_mid50_p99_uV"]),
                    "settling_mean_uV": float(metrics["settling_mid50_mean_uV"]),
                    "settling_sigma_uV": float(metrics["settling_mid50_sigma_uV"]),
                    "settling_p99_uV": float(metrics["settling_mid50_p99_uV"]),
                    "samples_completed": int(metrics["samples_completed"]),
                    "samples_failed": int(metrics["samples_failed"]),
                }
        else:
            raise ValueError(f"Unhandled AZ research test: {test.test_id}")
    payload = {
        "variant_id": executable.variant.variant_id,
        "hypothesis_id": executable.variant.hypothesis_id,
        "family": executable.variant.family,
        "status": "ok",
        "frontend_params": _serialize_frontend_params(executable.frontend_params),
        "timing": executable.timing,
        "results": results,
    }
    if "az_tt_precision" in results and "az_reduced_pvt" in results:
        payload["rank_key"] = _rank_key(
            {
                "top_tt": results["az_tt_precision"],
                "reduced_pvt": results["az_reduced_pvt"],
            }
        )
    return payload


def _render_hypothesis_markdown(hypothesis: AzResearchHypothesis, payload: dict) -> str:
    lines = [
        f"# AZ Research Execution {hypothesis.hypothesis_id}",
        "",
        hypothesis.title,
        "",
        f"Generated: `{utc_ts()}`",
        "",
        f"- Problem: {hypothesis.problem}",
        f"- Hypothesis: {hypothesis.statement}",
        "",
        "## Variants",
        "",
    ]
    for variant in payload["variants"]:
        lines.append(f"### {variant['variant_id']}")
        lines.append("")
        lines.append(f"- Status: `{variant['status']}`")
        if variant["status"] != "ok":
            lines.append(f"- Reason: {variant.get('reason', 'n/a')}")
            lines.append("")
            continue
        tt = variant["results"].get("az_tt_precision")
        rpvt = variant["results"].get("az_reduced_pvt")
        if tt:
            lines.append(
                f"- TT: residual `{float(tt['residual_offset_uV']):.2f} uV`, pedestal_mid50 `{float(tt['pedestal_mid50_uV']):.2f} uV`, settling_mid50 `{float(tt['settling_mid50_uV']):.2f} uV`"
            )
        if rpvt:
            lines.append(
                f"- Reduced-PVT worst: residual `{float(rpvt['worst_residual_offset_uV']):.2f} uV`, pedestal_mid50 `{float(rpvt['worst_pedestal_mid50_uV']):.2f} uV`, settling_mid50 `{float(rpvt['worst_settling_mid50_uV']):.2f} uV`"
            )
        if "az_nominal_frontend" in variant["results"]:
            frontend = variant["results"]["az_nominal_frontend"]
            lines.append(
                f"- Frontend TT: pedestal `{float(frontend['pedestal_zero_input']['pedestal_uV']):.2f} uV`, settling_mid50 `{float(frontend['settling_in_phase_window']['settling_mid50_uV']):.2f} uV`"
            )
        if "az_timing_sanity" in variant["results"]:
            sanity = variant["results"]["az_timing_sanity"]
            lines.append(f"- Timing sanity points: {', '.join(sorted(sanity))}")
        if "az_deadtime_sweep" in variant["results"]:
            dead = variant["results"]["az_deadtime_sweep"]
            lines.append(f"- Dead-time sweep points: {', '.join(sorted(dead))}")
        lines.append("")
    if payload["failures"]:
        lines.extend(["## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure['variant_id']}`: `{failure['error']}`")
        lines.append("")
    if payload.get("best_variant_by_priority"):
        lines.append(f"Best variant by current priority: `{payload['best_variant_by_priority']}`")
        lines.append("")
    return "\n".join(lines)


def _write_index(outroot: Path, payloads: dict[str, dict]) -> None:
    lines = [
        "# AZ Research Runner",
        "",
        "Executable hypotheses from `AZ_RESEARCH_PLAN.md`.",
        "",
        "| Hypothesis | Variants Done | Failures | Best Variant | Artifact |",
        "|---|---:|---:|---|---|",
    ]
    for hypothesis_id, payload in sorted(payloads.items()):
        lines.append(
            f"| {hypothesis_id} | {len(payload['variants'])} | {len(payload['failures'])} | "
            f"`{payload.get('best_variant_by_priority')}` | [`{hypothesis_id}.md`](./{hypothesis_id}.md) |"
        )
    (outroot / "index.md").write_text("\n".join(lines), encoding="utf-8")


def run_hypothesis(hypothesis_id: str, outroot: Path) -> dict:
    plan = {item.hypothesis_id: item for item in build_az_research_plan()}
    if hypothesis_id not in plan:
        raise ValueError(f"Unknown hypothesis: {hypothesis_id}")
    hypothesis = plan[hypothesis_id]
    executable_map = build_executable_variants()
    outroot.mkdir(parents=True, exist_ok=True)
    json_path = outroot / f"{hypothesis_id}.json"
    if json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        completed = {item["variant_id"]: item for item in payload.get("variants", [])}
        failures = payload.get("failures", [])
    else:
        completed = {}
        failures = []

    for variant in hypothesis.variants:
        if variant.variant_id in completed:
            log(f"[{hypothesis_id}] skip {variant.variant_id}")
            continue
        log(f"[{hypothesis_id}] running {variant.variant_id}")
        try:
            item = _run_variant(executable_map[variant.variant_id], hypothesis)
            completed[variant.variant_id] = item
            if item["status"] == "ok" and "az_tt_precision" in item["results"] and "az_reduced_pvt" in item["results"]:
                tt = item["results"]["az_tt_precision"]
                rpvt = item["results"]["az_reduced_pvt"]
                log(
                    f"[{hypothesis_id}] done {variant.variant_id} "
                    f"tt_resid={float(tt['residual_offset_uV']):.2f}uV "
                    f"tt_ped50={float(tt['pedestal_mid50_uV']):.2f}uV "
                    f"tt_set50={float(tt['settling_mid50_uV']):.2f}uV "
                    f"rpvt_worst_resid={float(rpvt['worst_residual_offset_uV']):.2f}uV "
                    f"rpvt_worst_ped50={float(rpvt['worst_pedestal_mid50_uV']):.2f}uV "
                    f"rpvt_worst_set50={float(rpvt['worst_settling_mid50_uV']):.2f}uV"
                )
            else:
                log(f"[{hypothesis_id}] recorded {variant.variant_id} status={item['status']}")
        except Exception as err:
            failures.append({"variant_id": variant.variant_id, "error": f"{type(err).__name__}: {err}"})
            log(f"[{hypothesis_id}] failed {variant.variant_id}: {type(err).__name__}: {err}")
        variants = list(completed.values())
        ranked = sorted(
            [item for item in variants if item.get("rank_key") is not None],
            key=lambda item: tuple(item["rank_key"]),
        )
        payload = {
            "hypothesis_id": hypothesis_id,
            "title": hypothesis.title,
            "variants": sorted(variants, key=lambda item: item["variant_id"]),
            "failures": failures,
            "best_variant_by_priority": ranked[0]["variant_id"] if ranked else None,
        }
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        (outroot / f"{hypothesis_id}.md").write_text(_render_hypothesis_markdown(hypothesis, payload), encoding="utf-8")
        cases_dir = outroot / "variants"
        cases_dir.mkdir(parents=True, exist_ok=True)
        if variant.variant_id in completed:
            (cases_dir / f"{variant.variant_id}.json").write_text(
                json.dumps(completed[variant.variant_id], indent=2, sort_keys=True),
                encoding="utf-8",
            )
    ranked = sorted(
        [item for item in completed.values() if item.get("rank_key") is not None],
        key=lambda item: tuple(item["rank_key"]),
    )
    return {
        "hypothesis_id": hypothesis_id,
        "title": hypothesis.title,
        "variants": sorted(completed.values(), key=lambda item: item["variant_id"]),
        "failures": failures,
        "best_variant_by_priority": ranked[0]["variant_id"] if ranked else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="run", choices=("run", "list", "json"))
    parser.add_argument("--hypothesis", action="append", dest="hypotheses")
    parser.add_argument("--outdir", default="tmp/opamp_v3_az_research")
    args = parser.parse_args(argv)

    plan = build_az_research_plan()
    executable = build_executable_variants()
    if args.command == "list":
        for hypothesis in plan:
            print(f"{hypothesis.hypothesis_id}: {hypothesis.title}")
            for variant in hypothesis.variants:
                item = executable[variant.variant_id]
                status = "runnable" if item.runnable else f"unavailable ({item.unavailable_reason})"
                print(f"  - {variant.variant_id}: {status}")
        return 0
    if args.command == "json":
        print(
            json.dumps(
                {
                    "hypotheses": [hyp.hypothesis_id for hyp in plan],
                    "variants": {
                        variant_id: {
                            "runnable": item.runnable,
                            "reason": item.unavailable_reason,
                        }
                        for variant_id, item in executable.items()
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    init_sky130_install()
    selected = args.hypotheses or [hyp.hypothesis_id for hyp in plan if any(item.runnable for item in (executable[var.variant_id] for var in hyp.variants))]
    outroot = Path(args.outdir)
    outroot.mkdir(parents=True, exist_ok=True)
    global LOG_PATH
    LOG_PATH = outroot / "run.log"
    payloads: dict[str, dict] = {}
    log(f"starting AZ research runner: {selected}")
    for hypothesis_id in selected:
        payloads[hypothesis_id] = run_hypothesis(hypothesis_id, outroot)
        _write_index(outroot, payloads)
    log("AZ research runner complete")
    print(outroot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
