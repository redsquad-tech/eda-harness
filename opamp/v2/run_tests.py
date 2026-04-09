from __future__ import annotations

import argparse
import json
import sys
import unittest

from .measure_core import run_load_sweep_test, run_pvt_test
from .measure_top import run_reduced_pvt_test


QUICK_TT_MODULES = [
    "opamp.v2.tests.test_v2__smoke__package",
    "opamp.v2.tests.test_v2__smoke__architecture",
    "opamp.v2.tests.test_opamp_core_v2__screen__fast_nominal",
    "opamp.v2.tests.test_opamp_az_top_v2__budget__precision_ppa",
]

FULL_TT_NOMINAL_MODULES = [
    "opamp.v2.tests.test_v2__smoke__package",
    "opamp.v2.tests.test_v2__smoke__architecture",
    "opamp.v2.tests.test_opamp_core_v2__budget__tt_nominal",
    "opamp.v2.tests.test_opamp_az_top_v2__budget__precision_ppa",
]

CORE_DEBUG_MODULES = [
    "opamp.v2.tests.test_bias_gen_v2__char__disable_off",
    "opamp.v2.tests.test_bias_gen_v2__char__reduced_corners",
    "opamp.v2.tests.test_gm_stage_v2__char__bias_sensitivity",
    "opamp.v2.tests.test_gm_stage_v2__char__source_drive_proxy",
    "opamp.v2.tests.test_gm_stage_v2__char__dc_transfer",
    "opamp.v2.tests.test_opamp_core_v2__char__disable_nodes",
    "opamp.v2.tests.test_opamp_core_v2__char__output_source_sweep",
]


def _run_unittest_modules(module_names: list[str], *, verbosity: int) -> int:
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite(loader.loadTestsFromName(name) for name in module_names)
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


def _print_json(title: str, payload) -> None:
    print(f"\n== {title} ==")
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run opamp/v2 test targets.")
    parser.add_argument(
        "target",
        choices=("quick_tt", "full_tt_nominal", "core_debug", "reduced_pvt", "full_pvt"),
        help="Named test target to run.",
    )
    parser.add_argument("-v", "--verbosity", type=int, default=2, help="unittest verbosity for unittest-backed targets")
    args = parser.parse_args(argv)

    if args.target == "quick_tt":
        return _run_unittest_modules(QUICK_TT_MODULES, verbosity=args.verbosity)

    if args.target == "full_tt_nominal":
        return _run_unittest_modules(FULL_TT_NOMINAL_MODULES, verbosity=args.verbosity)

    if args.target == "core_debug":
        return _run_unittest_modules(CORE_DEBUG_MODULES, verbosity=args.verbosity)

    if args.target == "reduced_pvt":
        _print_json("core.load_sweep", run_load_sweep_test()["metrics"])
        _print_json("top.reduced_pvt", run_reduced_pvt_test()["metrics"])
        return 0

    if args.target == "full_pvt":
        _print_json("core.pvt", run_pvt_test()["metrics"])
        _print_json("top.reduced_pvt", run_reduced_pvt_test()["metrics"])
        return 0

    raise AssertionError(f"Unhandled target: {args.target}")


if __name__ == "__main__":
    raise SystemExit(main())
