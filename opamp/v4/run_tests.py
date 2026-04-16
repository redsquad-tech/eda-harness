import sys
import unittest


TARGETS = {
    "quick": [
        "opamp.v4.tests.test_v4_smoke_package",
    ],
    "char": [
        "opamp.v4.tests.test_v4_smoke_package",
        "opamp.v4.tests.test_v4_char_open_loop",
        "opamp.v4.tests.test_v4_accept_spec_snapshot",
        "opamp.v4.tests.test_v4_bias_generator_isolated",
        "opamp.v4.tests.test_v4_probe_bias_network",
        "opamp.v4.tests.test_v4_probe_stage1_nodes",
        "opamp.v4.tests.test_v4_probe_mode_isolation",
        "opamp.v4.tests.test_v4_probe_mode_matrix",
        "opamp.v4.tests.test_v4_probe_scan_stub",
        "opamp.v4.tests.test_v4_probe_vtest_isolation",
        "opamp.v4.tests.test_v4_probe_az_hold",
        "opamp.v4.tests.test_v4_probe_bias_branch_currents",
        "opamp.v4.tests.test_v4_probe_current_map",
        "opamp.v4.tests.test_v4_frontend_isolated_dc",
        "opamp.v4.tests.test_v4_frontend_gain_target",
        "opamp.v4.tests.test_v4_stage1_handoff_cm",
        "opamp.v4.tests.test_v4_disabled_ab_bias_collapse",
        "opamp.v4.tests.test_v4_probe_monticelli_bias",
        "opamp.v4.tests.test_v4_probe_output_quiescent",
        "opamp.v4.tests.test_v4_probe_reference_gating",
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
