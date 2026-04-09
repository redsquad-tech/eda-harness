from __future__ import annotations

import argparse
import json
import sys
import unittest
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class TapeoutValidationCase:
    case_id: str
    filename: str
    component: str
    category: str
    purpose: str
    level: str
    fixture: str
    implementation_status: str
    metrics: tuple[str, ...]
    corners: tuple[str, ...]
    pass_fail_rule: str
    notes: str = ""
    python_test_module: str | None = None


def build_tapeout_validation_plan() -> list[TapeoutValidationCase]:
    return [
        TapeoutValidationCase(
            case_id="top_startup",
            filename="test_opamp_az_top__contract__startup.py",
            component="opamp_az_top",
            category="contract",
            purpose="startup",
            level="top",
            fixture="worst_bias",
            implementation_status="planned",
            metrics=("startup_success", "startup_time_us"),
            corners=("SS/TT/FF x VDDmin/VDDnom/VDDmax x Tmin/Tnom/Tmax",),
            pass_fail_rule="must start reliably and recover from enable cycling at all PVT corners",
            notes="Customer signoff test. New top-level v3 testbench required.",
        ),
        TapeoutValidationCase(
            case_id="top_disable_enable_recovery",
            filename="test_opamp_az_top__contract__disable_enable_recovery.py",
            component="opamp_az_top",
            category="contract",
            purpose="disable_enable_recovery",
            level="top",
            fixture="unity_feedback",
            implementation_status="planned",
            metrics=("recovery_success", "recovery_time_us", "post_reenable_offset_uV"),
            corners=("SS/TT/FF x VDDmin/VDDnom/VDDmax x Tmin/Tnom/Tmax",),
            pass_fail_rule="must re-enable cleanly with no latched or wrong operating point",
            notes="Needed before tapeout because shutdown leakage is a product requirement.",
        ),
        TapeoutValidationCase(
            case_id="top_az_phase_function",
            filename="test_opamp_az_top__contract__az_phase_function.py",
            component="opamp_az_top",
            category="contract",
            purpose="az_phase_function",
            level="top",
            fixture="sc_loop",
            implementation_status="planned",
            metrics=("phase_order_ok", "no_overlap_violation", "no_destructive_charge_sharing"),
            corners=("TT nominal plus reduced PVT decision corners",),
            pass_fail_rule="must tolerate PHI1/PHI2 non-overlap timing without destructive switching behavior",
        ),
        TapeoutValidationCase(
            case_id="top_nominal_open_loop",
            filename="test_opamp_az_top__budget__nominal_open_loop.py",
            component="opamp_az_top",
            category="budget",
            purpose="nominal_open_loop",
            level="top",
            fixture="nominal_load",
            implementation_status="planned",
            metrics=("aol_db", "gbw_hz", "phase_margin_deg", "gain_margin_db"),
            corners=("TT / 1.8 V / 27 C / CL=1 pF",),
            pass_fail_rule="AOL >= 65 dB, GBW in 0.3..1 MHz, PM >= 30 deg, GM >= 5 dB",
        ),
        TapeoutValidationCase(
            case_id="top_nominal_swing_drive",
            filename="test_opamp_az_top__budget__nominal_swing_drive.py",
            component="opamp_az_top",
            category="budget",
            purpose="nominal_swing_drive",
            level="top",
            fixture="current_load",
            implementation_status="planned",
            metrics=("vout_low_actual", "vout_high_actual", "source_drive_v", "sink_drive_v"),
            corners=("TT / 1.8 V / 27 C",),
            pass_fail_rule="must meet low/high swing and +/-20 uA drive requirements at nominal",
        ),
        TapeoutValidationCase(
            case_id="top_nominal_power_leakage",
            filename="test_opamp_az_top__budget__nominal_power_leakage.py",
            component="opamp_az_top",
            category="budget",
            purpose="nominal_power_leakage",
            level="top",
            fixture="nominal_load",
            implementation_status="planned",
            metrics=("iq_uA", "disabled_leakage_nA"),
            corners=("TT / 1.8 V / 27 C",),
            pass_fail_rule="enabled IQ <= 20 uA and disabled leakage <= 250 nA",
        ),
        TapeoutValidationCase(
            case_id="top_pvt_open_loop",
            filename="test_opamp_az_top__pvt__open_loop.py",
            component="opamp_az_top",
            category="pvt",
            purpose="open_loop",
            level="top",
            fixture="nominal_load",
            implementation_status="planned",
            metrics=("worst_aol_db", "worst_gbw_hz", "worst_phase_margin_deg", "worst_gain_margin_db"),
            corners=("SS/TT/FF x 1.6/1.8/1.98 V x -40/27/125 C",),
            pass_fail_rule="must satisfy all open-loop spec minima and GBW bounds across full PVT",
        ),
        TapeoutValidationCase(
            case_id="top_pvt_swing_drive",
            filename="test_opamp_az_top__pvt__swing_drive.py",
            component="opamp_az_top",
            category="pvt",
            purpose="swing_drive",
            level="top",
            fixture="current_load",
            implementation_status="planned",
            metrics=("worst_vout_low", "worst_vout_high", "worst_source_drive_v", "worst_sink_drive_v"),
            corners=("SS/TT/FF x 1.6/1.8/1.98 V x -40/27/125 C",),
            pass_fail_rule="must meet compliant swing and +/-20 uA drive across full PVT",
        ),
        TapeoutValidationCase(
            case_id="top_pvt_power_leakage",
            filename="test_opamp_az_top__pvt__power_leakage.py",
            component="opamp_az_top",
            category="pvt",
            purpose="power_leakage",
            level="top",
            fixture="nominal_load",
            implementation_status="planned",
            metrics=("worst_iq_uA", "worst_disabled_leakage_nA"),
            corners=("SS/TT/FF x 1.6/1.8/1.98 V x -40/27/125 C",),
            pass_fail_rule="enabled IQ and disabled leakage must meet full-PVT limits",
        ),
        TapeoutValidationCase(
            case_id="top_pvt_load_stability",
            filename="test_opamp_az_top__pvt__load_stability.py",
            component="opamp_az_top",
            category="pvt",
            purpose="load_stability",
            level="top",
            fixture="nominal_load",
            implementation_status="planned",
            metrics=("phase_margin_deg", "gain_margin_db", "gbw_hz"),
            corners=("TT/1.8/27, SS/1.6/125, FF/1.98/-40 with CL=0/0.5/1/2 pF",),
            pass_fail_rule="must remain stable for CL = 0..2 pF",
        ),
        TapeoutValidationCase(
            case_id="top_residual_offset_budget",
            filename="test_opamp_az_top__budget__residual_offset.py",
            component="opamp_az_top",
            category="budget",
            purpose="residual_offset",
            level="top",
            fixture="unity_feedback",
            implementation_status="planned",
            metrics=("residual_offset_uV",),
            corners=("TT / 1.8 V / 27 C",),
            pass_fail_rule="residual offset after AZ <= 250 uV minimum requirement",
        ),
        TapeoutValidationCase(
            case_id="top_pedestal_budget",
            filename="test_opamp_az_top__budget__pedestal.py",
            component="opamp_az_top",
            category="budget",
            purpose="pedestal",
            level="top",
            fixture="sc_loop",
            implementation_status="planned",
            metrics=("pedestal_mid50_uV",),
            corners=("TT / 1.8 V / 27 C",),
            pass_fail_rule="pedestal-equivalent input error <= 100 uV minimum requirement",
        ),
        TapeoutValidationCase(
            case_id="top_hold_droop_budget",
            filename="test_opamp_az_top__budget__hold_droop.py",
            component="opamp_az_top",
            category="budget",
            purpose="hold_droop",
            level="top",
            fixture="sc_loop",
            implementation_status="planned",
            metrics=("settling_mid50_uV",),
            corners=("TT / 1.8 V / 27 C",),
            pass_fail_rule="hold droop contribution per AZ cycle <= 50 uV minimum requirement",
        ),
        TapeoutValidationCase(
            case_id="top_reduced_pvt_precision",
            filename="test_opamp_az_top__pvt__residual_offset_pedestal_settling.py",
            component="opamp_az_top",
            category="pvt",
            purpose="residual_offset_pedestal_settling",
            level="top",
            fixture="sc_loop",
            implementation_status="legacy_available",
            metrics=("worst_residual_offset_uV", "worst_pedestal_mid50_uV", "worst_settling_mid50_uV"),
            corners=("reduced decision corners; extend to full PVT for signoff",),
            pass_fail_rule="worst reduced/full PVT AZ metrics must meet spec limits",
            python_test_module="tests.structural.opamp_az_top.test_opamp_az_top__char__reduced_pvt",
        ),
        TapeoutValidationCase(
            case_id="top_az_frequency_sweep",
            filename="test_opamp_az_top__pvt__az_frequency_sweep.py",
            component="opamp_az_top",
            category="pvt",
            purpose="az_frequency_sweep",
            level="top",
            fixture="sc_loop",
            implementation_status="planned",
            metrics=("residual_offset_uV", "pedestal_mid50_uV", "settling_mid50_uV"),
            corners=("TT plus reduced PVT; faz=10/50/100/200 kHz",),
            pass_fail_rule="must meet AZ error metrics across timing frequency sweep",
        ),
        TapeoutValidationCase(
            case_id="top_nonoverlap_sweep",
            filename="test_opamp_az_top__pvt__nonoverlap_sweep.py",
            component="opamp_az_top",
            category="pvt",
            purpose="nonoverlap_sweep",
            level="top",
            fixture="sc_loop",
            implementation_status="planned",
            metrics=("residual_offset_uV", "pedestal_mid50_uV", "settling_mid50_uV"),
            corners=("TT plus reduced PVT; deadtime=10/20/50 ns",),
            pass_fail_rule="must tolerate required non-overlap timing range",
        ),
        TapeoutValidationCase(
            case_id="top_mc_residual_offset",
            filename="test_opamp_az_top__mc__residual_offset.py",
            component="opamp_az_top",
            category="mc",
            purpose="residual_offset",
            level="top",
            fixture="unity_feedback",
            implementation_status="planned",
            metrics=("mean_uV", "sigma_uV", "p99_uV", "max_uV", "yield"),
            corners=("TT mismatch-only, no process variation, 200 samples minimum",),
            pass_fail_rule="MC residual offset yield must satisfy customer acceptance criteria",
        ),
        TapeoutValidationCase(
            case_id="top_mc_pedestal",
            filename="test_opamp_az_top__mc__pedestal.py",
            component="opamp_az_top",
            category="mc",
            purpose="pedestal",
            level="top",
            fixture="sc_loop",
            implementation_status="planned",
            metrics=("mean_uV", "sigma_uV", "p99_uV", "max_uV", "yield"),
            corners=("TT mismatch-only, no process variation, 200 samples minimum",),
            pass_fail_rule="MC pedestal distribution must remain inside customer acceptance criteria",
        ),
        TapeoutValidationCase(
            case_id="top_mc_hold_droop",
            filename="test_opamp_az_top__mc__hold_droop.py",
            component="opamp_az_top",
            category="mc",
            purpose="hold_droop",
            level="top",
            fixture="sc_loop",
            implementation_status="planned",
            metrics=("mean_uV", "sigma_uV", "p99_uV", "max_uV", "yield"),
            corners=("TT mismatch-only, no process variation, 200 samples minimum",),
            pass_fail_rule="MC hold droop distribution must remain inside customer acceptance criteria",
        ),
        TapeoutValidationCase(
            case_id="top_mc_startup_yield",
            filename="test_opamp_az_top__mc__startup_yield.py",
            component="opamp_az_top",
            category="mc",
            purpose="startup_yield",
            level="top",
            fixture="worst_bias",
            implementation_status="planned",
            metrics=("startup_yield", "worst_startup_time_us"),
            corners=("TT mismatch-only, 100 samples minimum",),
            pass_fail_rule="must show no unacceptable startup failures under mismatch",
        ),
        TapeoutValidationCase(
            case_id="core_quick_tt",
            filename="test_opamp_core_v3__char__tt_nominal.py",
            component="opamp_core_v3",
            category="char",
            purpose="tt_nominal",
            level="core",
            fixture="nominal_load",
            implementation_status="v3_available",
            metrics=("aol_db", "gbw_hz", "phase_margin_deg", "gain_margin_db", "iq_uA", "vout_low_actual", "disabled_leakage_nA"),
            corners=("TT / 1.8 V / 27 C",),
            pass_fail_rule="characterization only; appendix data for customer",
            python_test_module="opamp.v3.tests.test_opamp_core_v3__char__tt_nominal",
        ),
        TapeoutValidationCase(
            case_id="core_screen_fast_nominal",
            filename="test_opamp_core_v3__screen__fast_nominal.py",
            component="opamp_core_v3",
            category="char",
            purpose="fast_nominal",
            level="core",
            fixture="nominal_load",
            implementation_status="v3_available",
            metrics=("smoke_nominal_ok",),
            corners=("TT / 1.8 V / 27 C",),
            pass_fail_rule="characterization/screen only",
            python_test_module="opamp.v3.tests.test_opamp_core_v3__screen__fast_nominal",
        ),
        TapeoutValidationCase(
            case_id="top_legacy_precision_budget",
            filename="test_opamp_az_top__budget__precision_ppa.py",
            component="opamp_az_top",
            category="budget",
            purpose="precision_ppa",
            level="top",
            fixture="unity_feedback",
            implementation_status="legacy_available",
            metrics=("residual_offset_uV", "pedestal_mid50_uV", "settling_mid50_uV"),
            corners=("TT / 1.8 V / 27 C",),
            pass_fail_rule="legacy baseline nominal precision budget",
            python_test_module="tests.structural.opamp_az_top.test_opamp_az_top__budget__precision_ppa",
        ),
        TapeoutValidationCase(
            case_id="top_pex_open_loop",
            filename="test_opamp_az_top__pex__open_loop.py",
            component="opamp_az_top",
            category="pex",
            purpose="open_loop",
            level="top",
            fixture="nominal_load",
            implementation_status="planned",
            metrics=("schematic_vs_pex_delta_aol_db", "schematic_vs_pex_delta_gbw_pct", "schematic_vs_pex_delta_pm_deg"),
            corners=("TT plus reduced decision corners",),
            pass_fail_rule="PEX deltas must stay within agreed signoff envelope",
        ),
        TapeoutValidationCase(
            case_id="top_pex_precision",
            filename="test_opamp_az_top__pex__residual_offset_pedestal_settling.py",
            component="opamp_az_top",
            category="pex",
            purpose="precision",
            level="top",
            fixture="sc_loop",
            implementation_status="planned",
            metrics=("schematic_vs_pex_delta_residual_offset_uV", "schematic_vs_pex_delta_pedestal_uV", "schematic_vs_pex_delta_settling_uV"),
            corners=("TT plus reduced decision corners",),
            pass_fail_rule="PEX precision deltas must remain inside agreed signoff envelope",
        ),
    ]


def summarize_plan(plan: list[TapeoutValidationCase]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for case in plan:
        summary[case.implementation_status] = summary.get(case.implementation_status, 0) + 1
    return summary


def render_markdown(plan: list[TapeoutValidationCase]) -> str:
    summary = summarize_plan(plan)
    lines = [
        "# Opamp V3 Tapeout Validation Test Plan",
        "",
        "This is the customer-facing validation list for tapeout readiness.",
        "",
        f"Planned cases: `{len(plan)}`",
        f"Implementation status summary: `{json.dumps(summary, sort_keys=True)}`",
        "",
        "| Test File | Component | Category | Level | Status | Key Metrics | Corners | Pass Rule |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for case in plan:
        lines.append(
            f"| `{case.filename}` | `{case.component}` | `{case.category}` | `{case.level}` | "
            f"`{case.implementation_status}` | `{', '.join(case.metrics)}` | `{'; '.join(case.corners)}` | "
            f"{case.pass_fail_rule} |"
        )
    return "\n".join(lines) + "\n"


def render_json(plan: list[TapeoutValidationCase]) -> str:
    payload = {
        "summary": summarize_plan(plan),
        "cases": [asdict(case) for case in plan],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def run_available(plan: list[TapeoutValidationCase]) -> int:
    modules = [case.python_test_module for case in plan if case.python_test_module]
    if not modules:
        print("No implemented tapeout-validation tests are currently mapped.")
        return 2
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["md", "json", "run-available", "summary"], nargs="?", default="summary")
    parser.add_argument("--write", dest="write_path", help="Optional path to write the rendered output.")
    args = parser.parse_args(argv or sys.argv[1:])

    plan = build_tapeout_validation_plan()

    if args.command == "run-available":
        return run_available(plan)

    if args.command == "md":
        output = render_markdown(plan)
    elif args.command == "json":
        output = render_json(plan)
    else:
        output = json.dumps(summarize_plan(plan), indent=2, sort_keys=True) + "\n"

    if args.write_path:
        Path(args.write_path).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
