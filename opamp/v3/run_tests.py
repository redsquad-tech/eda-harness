from __future__ import annotations

import sys
import unittest


TARGETS: dict[str, list[str]] = {
    "smoke": [
        "opamp.v3.tests.test_v3__smoke__package",
        "opamp.v3.tests.test_v3__smoke__architecture",
        "opamp.v3.tests.test_v3__smoke__current_experiment",
        "opamp.v3.tests.test_v3__smoke__autonomous_az_batches",
        "opamp.v3.tests.test_v3__smoke__autonomous_az_mismatch_batches",
        "opamp.v3.tests.test_v3__smoke__autonomous_az_mismatch_repair_batches",
        "opamp.v3.tests.test_v3__smoke__autonomous_az_residual_shaping_batches",
        "opamp.v3.tests.test_v3__smoke__autonomous_followup_batches",
        "opamp.v3.tests.test_v3__smoke__az_research_plan",
        "opamp.v3.tests.test_v3__smoke__az_research_runner",
        "opamp.v3.tests.test_v3__smoke__tapeout_validation",
    ],
    "quick_tt": [
        "opamp.v3.tests.test_v3__smoke__package",
        "opamp.v3.tests.test_v3__smoke__architecture",
        "opamp.v3.tests.test_opamp_core_v3__screen__fast_nominal",
        "opamp.v3.tests.test_opamp_core_v3__char__tt_nominal",
    ],
    "tapeout_available": [
        "opamp.v3.tests.test_opamp_core_v3__screen__fast_nominal",
        "opamp.v3.tests.test_opamp_core_v3__char__tt_nominal",
        "opamp.v1.tests.structural.opamp_az_top.test_opamp_az_top__budget__precision_ppa",
        "opamp.v1.tests.structural.opamp_az_top.test_opamp_az_top__char__reduced_pvt",
    ],
    "prod_acceptance": [
        "opamp.v3.prod.tests.test_prod__acceptance__maximum_spec",
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
    target = argv[0] if argv else "smoke"
    if target not in TARGETS:
        print(f"Unknown target: {target}")
        print(f"Available targets: {', '.join(sorted(TARGETS))}")
        return 2
    suite = unittest.defaultTestLoader.loadTestsFromNames(TARGETS[target])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
