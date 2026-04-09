from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class AzResearchVariant:
    variant_id: str
    family: str
    hypothesis_id: str
    frontend_changes: tuple[str, ...]
    timing_changes: tuple[str, ...]
    rationale: str
    current_reference_metrics: tuple[str, ...]
    expected_improvement: tuple[str, ...]
    kill_if: tuple[str, ...]


@dataclass(frozen=True)
class AzResearchTest:
    test_id: str
    purpose: str
    fixture: str
    corners: tuple[str, ...]
    metrics: tuple[str, ...]
    pass_rule: str
    applies_to_families: tuple[str, ...]


@dataclass(frozen=True)
class AzResearchHypothesis:
    hypothesis_id: str
    title: str
    problem: str
    statement: str
    success_metrics: tuple[str, ...]
    variants: tuple[AzResearchVariant, ...]
    tests: tuple[str, ...]


def build_az_research_plan() -> tuple[AzResearchHypothesis, ...]:
    tests = build_az_research_tests()
    by_family = {test.test_id: test for test in tests}

    h1_variants = (
        AzResearchVariant(
            variant_id="az_h1_v1_cap200_shuntp10_freq200k",
            family="combo_corner_balance",
            hypothesis_id="az_h1",
            frontend_changes=("c_az = 200 fF", "c_out_p = 10 fF"),
            timing_changes=("period = 5 us", "dead_time = 0.5 us", "phi1/phi2/phi3 = 0.4/0.2/0.4"),
            rationale="Current best balanced corner-reduction branch from the autonomous batches.",
            current_reference_metrics=(
                "TT residual 38.40 uV",
                "TT pedestal_mid50 5.25 uV",
                "TT settling_mid50 3.86 uV",
                "RPVT worst residual 1977.66 uV",
                "RPVT worst pedestal_mid50 316.32 uV",
                "RPVT worst settling_mid50 78.13 uV",
            ),
            expected_improvement=(
                "reduce worst reduced-PVT residual toward < 1000 uV",
                "reduce worst reduced-PVT pedestal_mid50 toward < 150 uV",
                "reduce worst reduced-PVT settling_mid50 toward <= 50 uV",
            ),
            kill_if=(
                "TT residual > 150 uV",
                "TT pedestal_mid50 > 50 uV",
                "TT settling_mid50 > 30 uV",
            ),
        ),
        AzResearchVariant(
            variant_id="az_h1_v2_cap150_shuntp10_freq200k",
            family="combo_corner_balance",
            hypothesis_id="az_h1",
            frontend_changes=("c_az = 150 fF", "c_out_p = 10 fF"),
            timing_changes=("period = 5 us", "dead_time = 0.5 us", "phi1/phi2/phi3 = 0.4/0.2/0.4"),
            rationale="Lower-cap version to test whether 200 fF is over-driving hot/fast residual.",
            current_reference_metrics=(
                "TT residual 37.90 uV",
                "RPVT worst residual 2018.78 uV",
                "RPVT worst pedestal_mid50 331.74 uV",
                "RPVT worst settling_mid50 81.08 uV",
            ),
            expected_improvement=(
                "same nominal class as v1",
                "slightly better hot/fast residual or pedestal tradeoff",
            ),
            kill_if=(
                "corners worse than v1 in all three reduced-PVT metrics",
            ),
        ),
        AzResearchVariant(
            variant_id="az_h1_v3_shunt_both10_freq200k",
            family="combo_corner_balance",
            hypothesis_id="az_h1",
            frontend_changes=("c_az = 70 fF", "c_out_p = 10 fF", "c_out_n = 10 fF"),
            timing_changes=("period = 5 us", "dead_time = 0.5 us"),
            rationale="Tests whether symmetric edge filtering helps reduced-PVT more than cap increase.",
            current_reference_metrics=(
                "TT residual 36.35 uV",
                "RPVT worst residual 2105.02 uV",
                "RPVT worst pedestal_mid50 354.49 uV",
                "RPVT worst settling_mid50 84.70 uV",
            ),
            expected_improvement=("rule out or confirm symmetric shunt as a real topology direction",),
            kill_if=("TT settling_mid50 > 10 uV with no corner benefit over v1",),
        ),
    )

    h2_variants = (
        AzResearchVariant(
            variant_id="az_h2_v1_cap200_shuntp10_rtop600",
            family="nominal_safe_finish",
            hypothesis_id="az_h2",
            frontend_changes=("c_az = 200 fF", "c_out_p = 10 fF", "r_vcm_top = 600 ohm"),
            timing_changes=("legacy timing",),
            rationale="Current best conservative baseline patch that preserves nominal behavior strongly.",
            current_reference_metrics=(
                "TT residual 8.14 uV",
                "TT pedestal_mid50 13.40 uV",
                "TT settling_mid50 4.81 uV",
                "RPVT worst residual 2372.18 uV",
                "RPVT worst pedestal_mid50 5147.88 uV",
                "RPVT worst settling_mid50 522.14 uV",
            ),
            expected_improvement=(
                "keep nominal almost baseline-clean",
                "improve reduced-PVT without aggressive timing",
            ),
            kill_if=("TT residual > 20 uV", "TT pedestal_mid50 > 25 uV"),
        ),
        AzResearchVariant(
            variant_id="az_h2_v2_cap200_shuntp10_rtop600_freq200k",
            family="nominal_safe_finish",
            hypothesis_id="az_h2",
            frontend_changes=("c_az = 200 fF", "c_out_p = 10 fF", "r_vcm_top = 600 ohm"),
            timing_changes=("period = 5 us", "dead_time = 0.5 us"),
            rationale="Combines the best nominal-safe RC trim with the strongest timing lever.",
            current_reference_metrics=("predicted from follow-up frontier; not yet promoted",),
            expected_improvement=(
                "bridge the gap between conservative and aggressive branches",
                "target reduced-PVT pedestal_mid50 < 250 uV while keeping TT residual < 75 uV",
            ),
            kill_if=("TT residual > 100 uV", "TT pedestal_mid50 > 25 uV"),
        ),
        AzResearchVariant(
            variant_id="az_h2_v3_cap150_shuntp10_rtop600_freq200k",
            family="nominal_safe_finish",
            hypothesis_id="az_h2",
            frontend_changes=("c_az = 150 fF", "c_out_p = 10 fF", "r_vcm_top = 600 ohm"),
            timing_changes=("period = 5 us", "dead_time = 0.5 us"),
            rationale="Intermediate-cap fallback if 200 fF is too aggressive in nominal or MC.",
            current_reference_metrics=("predicted from follow-up frontier; not yet promoted",),
            expected_improvement=("same corner direction with potentially lower residual sigma",),
            kill_if=("worse than h2_v2 on both nominal and corners",),
        ),
    )

    h3_variants = (
        AzResearchVariant(
            variant_id="az_h3_v1_cap200_shuntp10_dead50ns",
            family="deadtime_window",
            hypothesis_id="az_h3",
            frontend_changes=("c_az = 200 fF", "c_out_p = 10 fF"),
            timing_changes=("dead_time = 50 ns", "period = 20 us"),
            rationale="Current strongest corner winner, but nominal residual regressed too much.",
            current_reference_metrics=(
                "TT residual 207.70 uV",
                "RPVT worst residual 1785.97 uV",
                "RPVT worst pedestal_mid50 1734.48 uV",
                "RPVT worst settling_mid50 182.76 uV",
            ),
            expected_improvement=("establish upper bound of dead-time leverage",),
            kill_if=("TT residual > 250 uV",),
        ),
        AzResearchVariant(
            variant_id="az_h3_v2_cap200_shuntp10_dead100ns",
            family="deadtime_window",
            hypothesis_id="az_h3",
            frontend_changes=("c_az = 200 fF", "c_out_p = 10 fF"),
            timing_changes=("dead_time = 100 ns", "period = 20 us"),
            rationale="Test whether a slightly less aggressive dead-time cut keeps corner benefit but repairs nominal residual.",
            current_reference_metrics=("not yet measured",),
            expected_improvement=("TT residual < 150 uV with corner metrics still better than freq200k baseline",),
            kill_if=("corners degrade back toward baseline while TT residual remains > 150 uV",),
        ),
        AzResearchVariant(
            variant_id="az_h3_v3_cap200_shuntp10_dead200ns",
            family="deadtime_window",
            hypothesis_id="az_h3",
            frontend_changes=("c_az = 200 fF", "c_out_p = 10 fF"),
            timing_changes=("dead_time = 200 ns", "period = 20 us"),
            rationale="Bridges between the safe legacy timing and aggressive short-dead-time branch.",
            current_reference_metrics=("not yet measured",),
            expected_improvement=("recover a balanced dead-time operating point if it exists",),
            kill_if=("TT pedestal_mid50 > 50 uV and corners not better than freq200k branch",),
        ),
    )

    h4_variants = (
        AzResearchVariant(
            variant_id="az_h4_v1_mc_cap200_shuntp10_freq200k",
            family="mc_gate",
            hypothesis_id="az_h4",
            frontend_changes=("same as aggressive patch candidate",),
            timing_changes=("same as aggressive patch candidate",),
            rationale="Mismatch-only gate for the strongest current candidate.",
            current_reference_metrics=("nominal and reduced-PVT already strong",),
            expected_improvement=(
                "quantify mean/sigma on residual/pedestal/settling",
                "decide if this branch is viable for tapeout-facing closure",
            ),
            kill_if=("MC sigma makes 3-sigma exceed minimum spec limits badly",),
        ),
        AzResearchVariant(
            variant_id="az_h4_v2_mc_cap200_shuntp10_rtop600",
            family="mc_gate",
            hypothesis_id="az_h4",
            frontend_changes=("same as conservative fallback",),
            timing_changes=("legacy timing",),
            rationale="Mismatch-only gate for the safer nominal fallback.",
            current_reference_metrics=("nominal very clean, corners moderate",),
            expected_improvement=("check whether conservative branch has materially better mismatch robustness",),
            kill_if=("MC result is not better than aggressive branch while corners remain much worse",),
        ),
    )

    return (
        AzResearchHypothesis(
            hypothesis_id="az_h1",
            title="Fast timing plus positive shunt plus larger cap is the main reduced-PVT closure axis",
            problem="Current AZ top passes nominal but still fails reduced-PVT by a large margin.",
            statement="The dominant remaining AZ error is dynamic and edge-related; positive-side shunt filtering with larger sampling capacitance and faster timing should cut worst hot/fast pedestal and settling without breaking nominal precision.",
            success_metrics=(
                "TT residual <= 100 uV",
                "TT pedestal_mid50 <= 25 uV",
                "TT settling_mid50 <= 10 uV",
                "RPVT worst pedestal_mid50 < 350 uV",
                "RPVT worst settling_mid50 < 100 uV",
            ),
            variants=h1_variants,
            tests=tuple(by_family[test_id].test_id for test_id in ("az_tt_precision", "az_reduced_pvt", "az_timing_sanity")),
        ),
        AzResearchHypothesis(
            hypothesis_id="az_h2",
            title="RC finish can make a safe baseline patch if aggressive timing is too risky",
            problem="The aggressive timing branch improves corners strongly, but may be harder to productize.",
            statement="A weaker but more nominal-safe branch may exist by combining the best cap/shunt topology with modest attenuation-path retuning.",
            success_metrics=(
                "TT residual <= 25 uV",
                "TT pedestal_mid50 <= 20 uV",
                "RPVT worst pedestal_mid50 < 1000 uV",
                "RPVT worst settling_mid50 < 250 uV",
            ),
            variants=h2_variants,
            tests=tuple(by_family[test_id].test_id for test_id in ("az_tt_precision", "az_reduced_pvt", "az_nominal_frontend")),
        ),
        AzResearchHypothesis(
            hypothesis_id="az_h3",
            title="A narrower dead-time window may outperform both legacy and freq200k branches",
            problem="`dead10ns` improved corners strongly but damaged nominal residual too much.",
            statement="There may be an intermediate dead-time region that keeps most corner benefit while recovering nominal residual and pedestal.",
            success_metrics=(
                "TT residual <= 150 uV",
                "TT pedestal_mid50 <= 50 uV",
                "RPVT worst residual < 1800 uV",
                "RPVT worst pedestal_mid50 < 1200 uV",
            ),
            variants=h3_variants,
            tests=tuple(by_family[test_id].test_id for test_id in ("az_tt_precision", "az_reduced_pvt", "az_deadtime_sweep")),
        ),
        AzResearchHypothesis(
            hypothesis_id="az_h4",
            title="Only finalists should enter mismatch screening",
            problem="Nominal and reduced-PVT do not tell whether a branch is manufacturable.",
            statement="Mismatch-only Monte Carlo is the gate between a promising AZ branch and a real baseline candidate.",
            success_metrics=(
                "MC residual mean near nominal expectation",
                "MC residual sigma small enough that 3-sigma is near or below minimum spec",
                "MC pedestal and settling spread do not reopen spec catastrophically",
            ),
            variants=h4_variants,
            tests=tuple(by_family[test_id].test_id for test_id in ("az_mc_offset", "az_mc_pedestal_settling")),
        ),
    )


def build_az_research_tests() -> tuple[AzResearchTest, ...]:
    return (
        AzResearchTest(
            test_id="az_tt_precision",
            purpose="Nominal top-level AZ precision check",
            fixture="noise_and_offset",
            corners=("TT / 1.8 V / 27 C",),
            metrics=("residual_offset_uV", "pedestal_mid50_uV", "settling_mid50_uV"),
            pass_rule="Use as nominal gate before spending reduced-PVT time.",
            applies_to_families=("combo_corner_balance", "nominal_safe_finish", "deadtime_window"),
        ),
        AzResearchTest(
            test_id="az_reduced_pvt",
            purpose="Reduced-PVT corner closure check",
            fixture="noise_and_offset",
            corners=("TT/SS/FF reduced decision corners",),
            metrics=("worst_residual_offset_uV", "worst_pedestal_mid50_uV", "worst_settling_mid50_uV"),
            pass_rule="Primary ranking test for all pre-MC AZ branches.",
            applies_to_families=("combo_corner_balance", "nominal_safe_finish", "deadtime_window"),
        ),
        AzResearchTest(
            test_id="az_timing_sanity",
            purpose="Confirm timing-dependent winner is not a single-point accident",
            fixture="noise_and_offset",
            corners=("TT nominal", "FF / 1.98 V / 125 C"),
            metrics=("residual_offset_uV", "pedestal_mid50_uV", "settling_mid50_uV"),
            pass_rule="Small timing perturbation should not cause catastrophic metric jumps.",
            applies_to_families=("combo_corner_balance",),
        ),
        AzResearchTest(
            test_id="az_nominal_frontend",
            purpose="Frontend-only nominal pedestal/settling sanity",
            fixture="frontend_az transient",
            corners=("TT nominal",),
            metrics=("pedestal_uV", "settling_mid50_uV"),
            pass_rule="Use to catch pathological frontend changes before top-level ranking.",
            applies_to_families=("nominal_safe_finish",),
        ),
        AzResearchTest(
            test_id="az_deadtime_sweep",
            purpose="Short dead-time exploration around promising branches",
            fixture="noise_and_offset",
            corners=("TT nominal", "FF / 1.98 V / 125 C"),
            metrics=("residual_offset_uV", "pedestal_mid50_uV", "settling_mid50_uV"),
            pass_rule="Identify the narrowest viable dead-time band before MC.",
            applies_to_families=("deadtime_window",),
        ),
        AzResearchTest(
            test_id="az_mc_offset",
            purpose="Mismatch-only residual-offset MC gate",
            fixture="mismatch-only Monte Carlo",
            corners=("TT mismatch-only",),
            metrics=("mean_uV", "sigma_uV", "p99_uV"),
            pass_rule="Finalists only. Use to decide baseline promotion order.",
            applies_to_families=("mc_gate",),
        ),
        AzResearchTest(
            test_id="az_mc_pedestal_settling",
            purpose="Mismatch-only pedestal and settling MC gate",
            fixture="mismatch-only Monte Carlo",
            corners=("TT mismatch-only",),
            metrics=("pedestal_mean_uV", "pedestal_sigma_uV", "settling_mean_uV", "settling_sigma_uV"),
            pass_rule="Finalists only. Reject branches with excessive dynamic spread.",
            applies_to_families=("mc_gate",),
        ),
    )


def render_markdown(plan: tuple[AzResearchHypothesis, ...], tests: tuple[AzResearchTest, ...]) -> str:
    lines = [
        "# AZ Research Plan",
        "",
        "This file captures the current AZ improvement plan as explicit hypotheses, device variants, and validation tests.",
        "",
        "## Hypotheses",
        "",
    ]
    for hyp in plan:
        lines.append(f"### {hyp.hypothesis_id}: {hyp.title}")
        lines.append("")
        lines.append(f"- Problem: {hyp.problem}")
        lines.append(f"- Hypothesis: {hyp.statement}")
        lines.append("- Success metrics:")
        for metric in hyp.success_metrics:
            lines.append(f"  - {metric}")
        lines.append("- Variants:")
        for variant in hyp.variants:
            lines.append(f"  - `{variant.variant_id}`")
            lines.append(f"    - frontend: {', '.join(variant.frontend_changes)}")
            lines.append(f"    - timing: {', '.join(variant.timing_changes)}")
            lines.append(f"    - rationale: {variant.rationale}")
            lines.append(f"    - expect: {', '.join(variant.expected_improvement)}")
            lines.append(f"    - kill if: {', '.join(variant.kill_if)}")
        lines.append(f"- Tests: {', '.join(hyp.tests)}")
        lines.append("")
    lines.extend(["## Test Matrix", ""])
    for test in tests:
        lines.append(f"### {test.test_id}")
        lines.append("")
        lines.append(f"- Purpose: {test.purpose}")
        lines.append(f"- Fixture: {test.fixture}")
        lines.append(f"- Corners: {', '.join(test.corners)}")
        lines.append(f"- Metrics: {', '.join(test.metrics)}")
        lines.append(f"- Rule: {test.pass_rule}")
        lines.append(f"- Applies to: {', '.join(test.applies_to_families)}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("format", nargs="?", default="md", choices=("md", "json"))
    args = parser.parse_args(argv)
    plan = build_az_research_plan()
    tests = build_az_research_tests()
    if args.format == "json":
        print(json.dumps({"hypotheses": [asdict(item) for item in plan], "tests": [asdict(item) for item in tests]}, indent=2))
    else:
        print(render_markdown(plan, tests))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
