from __future__ import annotations

import sys
import unittest


TARGETS: dict[str, list[str]] = {
    "smoke": [
        "opamp.v3.tests.test_v3__smoke__package",
        "opamp.v3.tests.test_v3__smoke__architecture",
        "opamp.v3.tests.test_v3__smoke__current_experiment",
    ],
    "quick_tt": [
        "opamp.v3.tests.test_v3__smoke__package",
        "opamp.v3.tests.test_v3__smoke__architecture",
        "opamp.v3.tests.test_opamp_core_v3__screen__fast_nominal",
        "opamp.v3.tests.test_opamp_core_v3__char__tt_nominal",
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
