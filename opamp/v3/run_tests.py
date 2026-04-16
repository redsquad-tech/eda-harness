from __future__ import annotations

import sys
import unittest


TARGETS: dict[str, list[str]] = {
    "output_stage_experiments": [
        "opamp.v3.tests.test_rc_probe_gate_drivers",
        "opamp.v3.tests.test_rc_probe_output_subckt",
        "opamp.v3.tests.test_rc_probe_forced_output_pair",
        "opamp.v3.tests.test_rc_probe_output_headroom_limits",
        "opamp.v3.tests.test_rc_probe_small_signal_nominal",
    ],
    "rc_mandatory": [
        "opamp.v3.tests.test_rc_probe_first_stage",
        "opamp.v3.tests.test_rc_probe_core_bias_breakdown",
        "opamp.v3.tests.test_rc_probe_stage2_standalone",
        "opamp.v3.tests.test_rc_probe_loop_partition_ac",
        "opamp.v3.tests.test_rc_probe_gate_drivers",
        "opamp.v3.tests.test_rc_probe_forced_output_pair",
        "opamp.v3.tests.test_rc_probe_output_subckt",
        "opamp.v3.tests.test_rc_probe_output_headroom_limits",
        "opamp.v3.tests.test_rc_probe_small_signal_nominal",
        "opamp.v3.tests.test_rc_probe_output_current_profile",
        "opamp.v3.tests.test_rc_probe_open_loop_metrics",
        "opamp.v3.tests.test_rc_probe_core_nominal_balance",
        "opamp.v3.tests.test_rc_probe_core",
    ],
    "rc_probe_sanity": [
        "opamp.v3.tests.test_rc_probe_output_ic_sweep",
        "opamp.v3.tests.test_rc_probe_output_op_vs_tran",
    ],
    "rc_block_budgets": [
        "opamp.v3.tests.test_rc_budget_stage1",
        "opamp.v3.tests.test_rc_budget_stage2",
        "opamp.v3.tests.test_rc_budget_output_driver",
        "opamp.v3.tests.test_rc_budget_output_driver_dc",
        "opamp.v3.tests.test_rc_budget_output_path",
    ],
    "prod_reduced_acceptance": [
        "opamp.v3.prod.tests.test_prod__acceptance__maximum_spec",
    ],
    "prod_full_acceptance": [
        "opamp.v3.prod.tests.test_prod__acceptance__maximum_spec",
        "opamp.v3.prod.tests.test_prod__acceptance__full_pvt_core",
        "opamp.v3.prod.tests.test_prod__acceptance__full_pvt_top",
        "opamp.v3.prod.tests.test_prod__acceptance__load_sweep",
        "opamp.v3.prod.tests.test_prod__acceptance__timing_and_mc",
    ],
    "prod_release": [
        "opamp.v3.prod.tests.test_prod__acceptance__maximum_spec",
        "opamp.v3.prod.tests.test_prod__acceptance__full_pvt_core",
        "opamp.v3.prod.tests.test_prod__acceptance__full_pvt_top",
        "opamp.v3.prod.tests.test_prod__acceptance__load_sweep",
        "opamp.v3.prod.tests.test_prod__acceptance__timing_and_mc",
    ],
}


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    target = argv[0] if argv else "output_stage_experiments"
    if target not in TARGETS:
        print(f"Unknown target: {target}")
        print(f"Available targets: {', '.join(sorted(TARGETS))}")
        return 2
    suite = unittest.defaultTestLoader.loadTestsFromNames(TARGETS[target])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
