from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import sky130_hdl21 as sky130


ROOT = Path(__file__).resolve().parents[3]


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

    def assertFinite(self, value: float, msg: str | None = None) -> None:
        self.assertTrue(math.isfinite(value), msg or f"Expected finite value, got {value!r}")
