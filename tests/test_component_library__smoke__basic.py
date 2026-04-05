from __future__ import annotations

import importlib
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import sky130_hdl21 as sky130

from components import format_metrics_table


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_COMPONENTS = [
    ("tg_switch", "components.tg_switch", None),
    ("sample_hold_cap", "components.sample_hold_cap", None),
    ("nonoverlap_clk", "components.nonoverlap_clk", None),
    ("diffpair_n", "components.diffpair_n", None),
    ("diffpair_p", "components.diffpair_p", None),
    ("tail_bias", "components.tail_bias", None),
    ("current_mirror", "components.current_mirror", None),
    ("active_load", "components.active_load", None),
    ("cascode_block", "components.cascode_block", None),
]


VARIANT_COMPONENTS = [
    (
        "tail_bias_cascoded",
        "components.tail_bias",
        "TailBiasParams",
        {"style": "cascoded"},
    ),
    (
        "current_mirror_p",
        "components.current_mirror",
        "CurrentMirrorParams",
        {
            "device_type": "p",
            "dev_ref": "PMOS_1p8V_STD",
            "dev_out": "PMOS_1p8V_STD",
        },
    ),
    (
        "cascode_block_wide_swing",
        "components.cascode_block",
        "CascodeBlockParams",
        {"style": "wide_swing"},
    ),
]


RESULT_CACHE: dict[tuple[str, tuple[tuple[str, Any], ...] | None], dict[str, Any]] = {}


def _init_sky130_install() -> None:
    if sky130.install is not None:
        return
    sky130.install = sky130.Install(
        pdk_path=Path("pdks/sky130A/sky130A").resolve(),
        lib_path=Path("libs.tech/ngspice/sky130.lib.spice"),
        model_ref=Path("libs.ref/sky130_fd_pr/spice"),
    )


def _sorted_items(kwargs: dict[str, Any] | None) -> tuple[tuple[str, Any], ...] | None:
    if kwargs is None:
        return None
    return tuple(sorted(kwargs.items()))


def _load_component_result(module_path: str, params_cls_name: str | None, kwargs: dict[str, Any] | None) -> dict[str, Any]:
    cache_key = (module_path, _sorted_items(kwargs))
    if cache_key in RESULT_CACHE:
        return RESULT_CACHE[cache_key]

    module = importlib.import_module(module_path)
    if params_cls_name is None:
        result = module.run_all_tests()
    else:
        params_cls = getattr(module, params_cls_name)
        result = module.run_all_tests(params_cls(**(kwargs or {})))
    RESULT_CACHE[cache_key] = result
    return result


class TestComponentLibrarySmokeBasic(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        _init_sky130_install()

    def test_component_library__contract__public_api_shape(self) -> None:
        required = (
            "run_all_tests",
            "print_test_report",
            "elaborate_dut",
            "export_spice",
            "run_structural_checks",
        )
        for component_name, module_path, _ in DEFAULT_COMPONENTS:
            with self.subTest(component=component_name):
                module = importlib.import_module(module_path)
                for attr in required:
                    self.assertTrue(hasattr(module, attr), f"{component_name} missing {attr}")

    def test_component_library__smoke__defaults(self) -> None:
        for component_name, module_path, _ in DEFAULT_COMPONENTS:
            with self.subTest(component=component_name):
                results = _load_component_result(module_path, None, None)
                self.assertIsInstance(results, dict)
                self.assertIn("structural", results)
                self.assertTrue(all(results["structural"].values()), f"{component_name} structural failure: {results['structural']}")
                self.assertGreaterEqual(len(results), 2, f"{component_name} returned no non-structural metrics")

    def test_component_library__smoke__selected_variants(self) -> None:
        for case_name, module_path, params_cls_name, kwargs in VARIANT_COMPONENTS:
            with self.subTest(component=case_name):
                results = _load_component_result(module_path, params_cls_name, kwargs)
                self.assertIn("structural", results)
                self.assertTrue(all(results["structural"].values()), f"{case_name} structural failure: {results['structural']}")

    def test_component_library__contract__metrics_table(self) -> None:
        results = _load_component_result("components.current_mirror", None, None)
        table = format_metrics_table(results, title="current_mirror")
        self.assertIn("current_mirror", table)
        self.assertIn("test", table)
        self.assertIn("metric", table)
        self.assertIn("value", table)
        self.assertIn("structural", table)

    def test_component_library__contract__print_test_report(self) -> None:
        module = importlib.import_module("components.tg_switch")
        buf = io.StringIO()
        with redirect_stdout(buf):
            results = module.print_test_report()
        output = buf.getvalue()
        self.assertIn("tg_switch", output)
        self.assertIn("structural", output)
        self.assertIn("on_smoke", output)
        self.assertIsInstance(results, dict)
        self.assertTrue(all(results["structural"].values()))


if __name__ == "__main__":
    unittest.main()
