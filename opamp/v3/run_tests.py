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
        "tests.structural.opamp_az_top.test_opamp_az_top__budget__precision_ppa",
        "tests.structural.opamp_az_top.test_opamp_az_top__char__reduced_pvt",
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
