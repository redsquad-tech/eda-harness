import sys
import unittest


TARGETS = {
    "quick": [
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_smoke_package",
    ],
    "char": [
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_smoke_package",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_char_open_loop",
        "devices.hogervorst_page12_sky130_opa.tests.acceptance.test_v4_accept_spec_snapshot",
        "devices.hogervorst_page12_sky130_opa.tests.budget.test_v4_budget_system",
        "devices.hogervorst_page12_sky130_opa.tests.budget.test_v4_budget_bias_blocks",
        "devices.hogervorst_page12_sky130_opa.tests.budget.test_v4_budget_frontend_blocks",
        "devices.hogervorst_page12_sky130_opa.tests.budget.test_v4_budget_monticelli_output_blocks",
        "devices.hogervorst_page12_sky130_opa.tests.budget.test_v4_budget_comp_wrapper_blocks",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_bias_generator_isolated",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_bias_network",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_stage1_nodes",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_mode_isolation",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_mode_matrix",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_scan_stub",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_vtest_isolation",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_az_hold",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_bias_branch_currents",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_current_map",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_frontend_isolated_dc",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_frontend_gain_target",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_stage1_handoff_cm",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_disabled_ab_bias_collapse",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_monticelli_bias",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_output_quiescent",
        "devices.hogervorst_page12_sky130_opa.tests.test_v4_probe_reference_gating",
    ],
}


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    target = argv[0] if argv else "quick"
    if target not in TARGETS:
        print(f"Unknown target: {target}")
        print(f"Available targets: {', '.join(sorted(TARGETS))}")
        return 2
    suite = unittest.defaultTestLoader.loadTestsFromNames(TARGETS[target])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
