from __future__ import annotations

import json
import importlib
import math
import sys
import unittest
from dataclasses import fields
from pathlib import Path

import sky130_hdl21 as sky130

from opamp.v3.opamp_core import OpampCoreParams
from opamp.v3.prod.rc import current_core_params


ROOT = Path(__file__).resolve().parents[3]
HDL21_GENERATOR_MODULE = importlib.import_module("hdl21.generator")


def ensure_repo_root_on_path() -> None:
    root_str = str(ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def init_sky130_install() -> None:
    if sky130.install is not None:
        return
    sky130.install = sky130.Install(
        pdk_path=Path("pdks/sky130A/sky130A").resolve(),
        lib_path=Path("libs.tech/ngspice/sky130.lib.spice"),
        model_ref=Path("libs.ref/sky130_fd_pr/spice"),
    )


class BaseV3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        ensure_repo_root_on_path()


class BaseV3SimTest(BaseV3Test):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        init_sky130_install()

    def setUp(self) -> None:
        super().setUp()
        HDL21_GENERATOR_MODULE.generator.cache.reset()

    def assertFinite(self, value: float, msg: str | None = None) -> None:
        self.assertTrue(math.isfinite(value), msg or f"Expected finite value, got {value!r}")


def reset_metrics_file(path: Path) -> None:
    path.unlink(missing_ok=True)


def write_metrics_json(path: Path, payload: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def build_debug_core_params(**updates) -> OpampCoreParams:
    base = current_core_params()
    payload = {field.name: getattr(base, field.name) for field in fields(base)}
    payload["debug_current_probes"] = True
    payload.update(updates)
    return OpampCoreParams(**payload)


def build_core_params(**updates) -> OpampCoreParams:
    base = current_core_params()
    payload = {field.name: getattr(base, field.name) for field in fields(base)}
    payload.update(updates)
    return OpampCoreParams(**payload)
