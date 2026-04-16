"""Shared simulation utilities for `opamp.v3`."""

import math
import warnings
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic.warnings import PydanticDeprecatedSince20

# Keep unit-test output focused on real simulation failures.
# Apply filters before importing libraries that emit them during import/ setup.
warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)
warnings.simplefilter("ignore", PydanticDeprecatedSince20)
warnings.filterwarnings(
    "ignore",
    message=r"`pydantic_encoder` is deprecated.*",
    category=Warning,
    module=r"hdl21\.params",
)
warnings.filterwarnings(
    "ignore",
    category=ResourceWarning,
    module=r"vlsirtools\.spice\.ngspice",
)

import hdl21 as h
import numpy as np
import sky130_hdl21
from vlsirtools.spice import ResultFormat, SimOptions, SupportedSimulators

from components.ngspice_netlister import run_compatible_sim


PDK_ROOT = Path("./pdks/sky130A")


def require_sky130_install():
    if sky130_hdl21.install is None:
        raise RuntimeError(
            "sky130_hdl21.install is not initialized. "
            f"Initialize the SKY130 PDK install before running tests or simulations. "
            f"Repository PDK root: {PDK_ROOT}."
        )
    return sky130_hdl21.install


def passive_corner_includes(install):
    base = install.pdk_path / "libs.tech/ngspice"
    return [
        h.sim.Include(base / "r+c/res_typical__cap_typical.spice"),
        h.sim.Include(base / "r+c/res_typical__cap_typical__lin.spice"),
        h.sim.Include(base / "corners/tt/specialized_cells.spice"),
    ]


def run_ngspice_sim(sim, sim_options=None, *, rundir: str = "./scratch_ngspice"):
    if sim_options is None:
        sim_options = SimOptions(simulator=SupportedSimulators.NGSPICE, rundir=rundir)
    elif sim_options.simulator != SupportedSimulators.NGSPICE:
        raise ValueError(f"run_ngspice_sim requires NGSPICE, got {sim_options.simulator}")
    return run_compatible_sim(sim, sim_options)


def default_ngspice_options(test_name: str, *, fmt: ResultFormat | None = None) -> SimOptions:
    kwargs: dict[str, Any] = {
        "simulator": SupportedSimulators.NGSPICE,
        "rundir": f"./tmp/{test_name}",
    }
    if fmt is not None:
        kwargs["fmt"] = fmt
    return SimOptions(**kwargs)


def unique_ngspice_options(test_name: str, *, fmt: ResultFormat | None = None) -> SimOptions:
    suffix = uuid4().hex[:8]
    return default_ngspice_options(f"{test_name}_{suffix}", fmt=fmt)


def op_scalar(result, signal_name: str) -> float:
    op = getattr(result.an[0], "op", result.an[0])
    target = signal_name.lower()
    if isinstance(getattr(op, "data", None), dict):
        for name, value in op.data.items():
            if name.lower() == target:
                return float(value)
        raise RuntimeError(f"Signal {signal_name} not found in op result: {list(op.data.keys())}")
    for name, value in zip(op.signals, op.data):
        if name.lower() == target:
            return float(value)
    raise RuntimeError(f"Signal {signal_name} not found in op result")


def extract_ac_trace(result, signal_name: str):
    ac = result.an[0]
    target = signal_name.lower()
    data_map = getattr(ac, "data", None)
    freq = getattr(ac, "freq", None)
    if not isinstance(data_map, dict) or freq is None:
        raise RuntimeError(f"Unsupported AC result shape for signal {signal_name}: {type(ac)}")
    for key, data in data_map.items():
        if key.lower() == target:
            return freq, data
    raise RuntimeError(f"AC trace {signal_name} not found in result keys: {list(data_map.keys())}")


def interp_crossing(x_vals, y_vals, target: float):
    for idx in range(1, len(y_vals)):
        y0 = float(y_vals[idx - 1])
        y1 = float(y_vals[idx])
        if (y0 - target) == 0.0:
            return float(x_vals[idx - 1]), idx - 1
        if (y0 - target) * (y1 - target) <= 0.0 and y1 != y0:
            frac = (target - y0) / (y1 - y0)
            x = float(x_vals[idx - 1] + frac * (x_vals[idx] - x_vals[idx - 1]))
            return x, idx
    return float("nan"), None


def interp_value(x_vals, y_vals, x_target: float):
    for idx in range(1, len(x_vals)):
        x0 = float(x_vals[idx - 1])
        x1 = float(x_vals[idx])
        if x0 <= x_target <= x1 and x1 != x0:
            frac = (x_target - x0) / (x1 - x0)
            return float(y_vals[idx - 1] + frac * (y_vals[idx] - y_vals[idx - 1]))
    return float("nan")


def negative_feedback_phase_trace(loop_gain: np.ndarray):
    if len(loop_gain) == 0:
        return np.asarray([], dtype=float), float("nan")
    phase_deg = np.unwrap(np.angle(loop_gain)) * 180.0 / math.pi
    if float(phase_deg[0]) > 90.0:
        phase_deg = phase_deg - 360.0
    return phase_deg, float(phase_deg[0])


def make_test_result(*, component: str, category: str, purpose: str, metrics: dict[str, Any], passed: bool | None = None):
    payload = {
        "component": component,
        "category": category,
        "purpose": purpose,
        "metrics": metrics,
    }
    if passed is not None and category != "char":
        payload["pass"] = bool(passed)
    return payload
