from __future__ import annotations

import csv
import importlib
import inspect
import sys
import unittest
from pathlib import Path

import hdl21 as h
import sky130_hdl21 as sky130

from components import (
    extract_subckt_name,
    flatten_metrics,
    format_metrics_table,
    parse_ngspice_scalar,
)


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp" / "test_component_library_contract"


COMPONENT_SPECS = {
    "tg_switch": {
        "module": "components.tg_switch",
        "params": "TgSwitchParams",
        "generator": "tg_switch",
        "csv_params": ["dev_n", "dev_p", "w_n", "l_n", "nf_n", "m_n", "w_p", "l_p", "nf_p", "m_p", "use_dummy_switch", "body_tie_style"],
        "variant_kwargs": {"use_dummy_switch": True},
        "variant_markers": ["dummy_n", "dummy_p"],
        "invalid_kwargs": {"body_tie_style": "bad"},
        "invalid_message": "Unsupported body_tie_style",
    },
    "sample_hold_cap": {
        "module": "components.sample_hold_cap",
        "params": "SampleHoldCapParams",
        "generator": "sample_hold_cap",
        "csv_params": ["cap_dev", "c_target", "unit_w", "unit_l", "nser", "npar", "common_centroid"],
        "variant_kwargs": {"nser": 3},
        "variant_markers": ["cap_0", "cap_1", "cap_2"],
        "invalid_kwargs": {"nser": 0},
        "invalid_message": "nser must be >=",
    },
    "nonoverlap_clk": {
        "module": "components.nonoverlap_clk",
        "params": "NonoverlapClkParams",
        "generator": "nonoverlap_clk",
        "csv_params": ["style", "t_dead", "duty", "buf_stages", "inv_ratio", "trf"],
        "variant_kwargs": {"buf_stages": 3},
        "variant_markers": ["clk_delay_inv_5", "clkb_delay_inv_5"],
        "invalid_kwargs": {"buf_stages": 0},
        "invalid_message": "buf_stages must be >=",
    },
    "diffpair_n": {
        "module": "components.diffpair_n",
        "params": "DiffpairNParams",
        "generator": "diffpair_n",
        "csv_params": ["dev_in", "w_in", "l_in", "nf_in", "m_in", "body_tie", "use_degeneration", "r_deg"],
        "variant_kwargs": {"use_degeneration": True, "r_deg": 250.0},
        "variant_markers": ["rdeg_p", "rdeg_n"],
        "invalid_kwargs": {"body_tie": "bad"},
        "invalid_message": "Unsupported body_tie",
    },
    "diffpair_p": {
        "module": "components.diffpair_p",
        "params": "DiffpairPParams",
        "generator": "diffpair_p",
        "csv_params": ["dev_in", "w_in", "l_in", "nf_in", "m_in", "body_tie", "use_degeneration", "r_deg"],
        "variant_kwargs": {"use_degeneration": True, "r_deg": 250.0},
        "variant_markers": ["rdeg_p", "rdeg_n"],
        "invalid_kwargs": {"body_tie": "bad"},
        "invalid_message": "Unsupported body_tie",
    },
    "tail_bias": {
        "module": "components.tail_bias",
        "params": "TailBiasParams",
        "generator": "tail_bias",
        "csv_params": ["style", "dev_out", "dev_cas", "w_out", "l_out", "nf_out", "m_out", "w_cas", "l_cas", "nf_cas", "m_cas", "i_target"],
        "variant_kwargs": {"style": "cascoded"},
        "variant_markers": ["m_cas", "mid"],
        "invalid_kwargs": {"style": "bad"},
        "invalid_message": "Unsupported style",
    },
    "current_mirror": {
        "module": "components.current_mirror",
        "params": "CurrentMirrorParams",
        "generator": "current_mirror",
        "csv_params": ["device_type", "style", "dev_ref", "dev_out", "ratio", "w_ref", "l_ref", "nf_ref", "m_ref", "w_out", "l_out", "nf_out", "m_out"],
        "variant_kwargs": {"device_type": "p", "style": "wide_swing", "dev_ref": "PMOS_1p8V_STD", "dev_out": "PMOS_1p8V_STD"},
        "variant_markers": ["ref_mid", "out_mid", "sky130_fd_pr__pfet_01v8"],
        "invalid_kwargs": {"ratio": 0},
        "invalid_message": "ratio must be positive",
    },
    "active_load": {
        "module": "components.active_load",
        "params": "ActiveLoadParams",
        "generator": "active_load",
        "csv_params": ["device_type", "style", "dev_load", "ratio", "w_load", "l_load", "nf_load", "m_load", "cross_coupled"],
        "variant_kwargs": {"device_type": "n", "style": "cascoded", "dev_load": "NMOS_1p8V_STD"},
        "variant_markers": ["inp_mid", "outp_mid", "sky130_fd_pr__nfet_01v8"],
        "invalid_kwargs": {"device_type": "bad"},
        "invalid_message": "Unsupported device_type",
    },
    "cascode_block": {
        "module": "components.cascode_block",
        "params": "CascodeBlockParams",
        "generator": "cascode_block",
        "csv_params": ["device_type", "style", "dev_main", "dev_cas", "w_main", "l_main", "nf_main", "m_main", "w_cas", "l_cas", "nf_cas", "m_cas", "vcas_target"],
        "variant_kwargs": {"device_type": "p", "style": "wide_swing", "dev_main": "PMOS_1p8V_STD", "dev_cas": "PMOS_1p8V_STD"},
        "variant_markers": ["mid", "sky130_fd_pr__pfet_01v8"],
        "invalid_kwargs": {"style": "bad"},
        "invalid_message": "Unsupported style",
    },
}


def _init_sky130_install() -> None:
    if sky130.install is not None:
        return
    sky130.install = sky130.Install(
        pdk_path=Path("pdks/sky130A/sky130A").resolve(),
        lib_path=Path("libs.tech/ngspice/sky130.lib.spice"),
        model_ref=Path("libs.ref/sky130_fd_pr/spice"),
    )


def _load_module(component_name: str):
    return importlib.import_module(COMPONENT_SPECS[component_name]["module"])


def _params_cls(component_name: str):
    spec = COMPONENT_SPECS[component_name]
    module = _load_module(component_name)
    return getattr(module, spec["params"])


def _dut_params(component_name: str, **kwargs):
    return _params_cls(component_name)(**kwargs)


def _builder_corner(component_name: str):
    return "TT" if component_name in {"sample_hold_cap", "nonoverlap_clk"} else h.pdk.Corner.TYP


def _registry_rows() -> list[dict[str, str]]:
    with (ROOT / "components.csv").open() as f:
        return list(csv.DictReader(f))


class TestComponentLibraryContractCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        _init_sky130_install()

    def test_component_library__contract__registry_matches_modules_and_params(self) -> None:
        registry = {row["name"]: row for row in _registry_rows()}
        self.assertEqual(set(registry), set(COMPONENT_SPECS))

        for component_name, spec in COMPONENT_SPECS.items():
            with self.subTest(component=component_name):
                module = _load_module(component_name)
                params_cls = getattr(module, spec["params"])

                self.assertTrue(hasattr(module, spec["generator"]))
                self.assertEqual(list(params_cls.__dataclass_fields__), spec["csv_params"])
                self.assertEqual(registry[component_name]["parameters"].split(","), spec["csv_params"])

    def test_component_library__contract__verification_plan_schema(self) -> None:
        required_keys = {"test", "analysis", "metrics", "rule", "corners", "sweeps", "monte_carlo"}
        for component_name in COMPONENT_SPECS:
            with self.subTest(component=component_name):
                module = _load_module(component_name)
                plan = module.VERIFICATION_PLAN
                self.assertIn("structural", plan)
                for test_name, payload in plan.items():
                    self.assertEqual(set(payload), required_keys)
                    self.assertTrue(callable(getattr(module, payload["test"])))
                    self.assertIsInstance(payload["metrics"], list)
                    self.assertIsInstance(payload["corners"], list)
                    self.assertIsInstance(payload["sweeps"], list)
                    self.assertIsInstance(payload["monte_carlo"], bool)
                    self.assertIsInstance(test_name, str)

    def test_component_library__contract__build_testbenches_use_single_vss_port(self) -> None:
        for component_name in COMPONENT_SPECS:
            module = _load_module(component_name)
            params = _dut_params(component_name)
            for builder_name, builder in inspect.getmembers(module, inspect.isfunction):
                if not builder_name.startswith("build_"):
                    continue
                with self.subTest(component=component_name, builder=builder_name):
                    sim = builder(params, corner=_builder_corner(component_name))
                    self.assertEqual(list(sim.tb.ports), ["VSS"])

    def test_component_library__contract__export_spice_creates_valid_netlists(self) -> None:
        for component_name in COMPONENT_SPECS:
            with self.subTest(component=component_name):
                module = _load_module(component_name)
                out_path = TMP_ROOT / f"{component_name}.sp"
                exported = module.export_spice(out_path, _dut_params(component_name))
                text = exported.read_text()
                subckt_name = extract_subckt_name(text)

                self.assertEqual(exported, out_path)
                self.assertTrue(exported.exists())
                self.assertTrue(subckt_name)
                self.assertIn(".SUBCKT", text)
                self.assertIn(".ENDS", text)

    def test_component_library__contract__variant_topologies_export_expected_markers(self) -> None:
        for component_name, spec in COMPONENT_SPECS.items():
            with self.subTest(component=component_name):
                module = _load_module(component_name)
                params = _dut_params(component_name, **spec["variant_kwargs"])
                checks = module.run_structural_checks(params)
                text = module.export_spice(TMP_ROOT / f"{component_name}__variant.sp", params).read_text()

                self.assertTrue(all(checks.values()), checks)
                for marker in spec["variant_markers"]:
                    self.assertIn(marker, text)

    def test_component_library__contract__invalid_params_raise_value_error(self) -> None:
        for component_name, spec in COMPONENT_SPECS.items():
            with self.subTest(component=component_name):
                module = _load_module(component_name)
                generator = getattr(module, spec["generator"])
                with self.assertRaisesRegex(ValueError, spec["invalid_message"]):
                    generator(_dut_params(component_name, **spec["invalid_kwargs"]))

    def test_component_library__contract__shared_helpers_cover_expected_shapes(self) -> None:
        rows = flatten_metrics(
            {
                "structural": {"generator_call": True, "elaboration": True},
                "mirror_op": {"ratio_est": 1.97},
                "scalar_section": 5,
            }
        )
        table = format_metrics_table({"structural": {"generator_call": True}, "scalar_section": 5}, title="demo")

        self.assertIn(("structural", "generator_call", "PASS"), rows)
        self.assertIn(("scalar_section", "value", "5"), rows)
        self.assertIn("demo", table)
        self.assertIn("test", table)
        self.assertIn("value", table)
        self.assertEqual(parse_ngspice_scalar("v(out) = 1.234e-03", "v(out)"), 1.234e-03)
        with self.assertRaisesRegex(ValueError, "Could not find scalar"):
            parse_ngspice_scalar("v(in) = 0.1", "v(out)")


if __name__ == "__main__":
    unittest.main()
