import math
import json
import sys
import unittest
from pathlib import Path

from opamp.v4.common import init_sky130_install


ROOT = Path(__file__).resolve().parents[3]


def ensure_repo_root_on_path() -> None:
    root_str = str(ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


class BaseV4Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        ensure_repo_root_on_path()


class BaseV4SimTest(BaseV4Test):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        init_sky130_install()

    def assertFinite(self, value: float, msg: str | None = None) -> None:
        self.assertTrue(math.isfinite(value), msg or f"Expected finite value, got {value!r}")

    def assertMetricGreater(self, name: str, value: float, threshold: float) -> None:
        self.assertGreater(
            value,
            threshold,
            f"{name}={value:.6g} must be > {threshold:.6g}",
        )

    def assertMetricLess(self, name: str, value: float, threshold: float) -> None:
        self.assertLess(
            value,
            threshold,
            f"{name}={value:.6g} must be < {threshold:.6g}",
        )

    def assertMetricBetween(self, name: str, value: float, low: float, high: float) -> None:
        self.assertGreaterEqual(
            value,
            low,
            f"{name}={value:.6g} must be >= {low:.6g}",
        )
        self.assertLessEqual(
            value,
            high,
            f"{name}={value:.6g} must be <= {high:.6g}",
        )


def write_metrics_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def find_signal(data: dict[str, float], exact: str | None = None, *, suffix: str | None = None) -> float:
    if exact is not None and exact in data:
        return float(data[exact])
    if suffix is not None:
        matches = [float(value) for name, value in data.items() if name.endswith(suffix)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise RuntimeError(f"Signal suffix {suffix!r} matched multiple entries")
    wanted = exact if exact is not None else suffix
    raise RuntimeError(f"Signal {wanted!r} not found")
