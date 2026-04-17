from pathlib import Path

import numpy as np
import sky130_hdl21 as sky130
from vlsirtools.spice import ResultFormat, SimOptions, SupportedSimulators

from components import extract_subckt_name, make_test_result, run_ngspice_sim


def default_ngspice_options(test_name: str, *, fmt=ResultFormat.SIM_DATA) -> SimOptions:
    return SimOptions(
        simulator=SupportedSimulators.NGSPICE,
        fmt=fmt,
        rundir=f"./tmp/{test_name}",
    )


def extract_ac_trace(result, trace_name: str):
    ac = result.an[0]
    target = trace_name.lower()
    for key, data in ac.data.items():
        if key.lower() == target:
            return ac.freq, data
    raise RuntimeError(f"AC trace {trace_name} not found in result keys: {list(ac.data.keys())}")


def interp_value(x, y, x_target: float) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) == 0 or len(y) == 0:
        return float("nan")
    if x_target < x[0] or x_target > x[-1]:
        return float("nan")
    return float(np.interp(x_target, x, y))


def interp_crossing(x, y, target: float):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 2 or len(y) < 2:
        return float("nan"), -1
    delta = y - target
    for idx in range(len(delta) - 1):
        a = delta[idx]
        b = delta[idx + 1]
        if a == 0.0:
            return float(x[idx]), idx
        if a * b <= 0.0 and a != b:
            frac = a / (a - b)
            return float(x[idx] + frac * (x[idx + 1] - x[idx])), idx
    return float("nan"), -1


def negative_feedback_phase_trace(loop_gain):
    phase_deg = np.unwrap(np.angle(loop_gain)) * 180.0 / np.pi
    phase_deg = np.where(phase_deg > 0.0, phase_deg - 360.0, phase_deg)
    low_freq_phase_deg_raw = float(phase_deg[0]) if len(phase_deg) else float("nan")
    return phase_deg, low_freq_phase_deg_raw


def op_scalar(result, signal_name: str) -> float:
    target = signal_name.lower()
    op = result.an[0]
    for name, value in op.data.items():
        if name.lower() == target:
            return float(value)
    raise RuntimeError(f"Signal {signal_name} not found in op result: {list(op.data.keys())}")


def sky130_root() -> Path:
    root = Path("pdks/sky130A/sky130A").resolve()
    if not root.exists():
        raise RuntimeError(f"Missing SKY130 PDK root: {root}")
    return root


def init_sky130_install() -> None:
    if sky130.install is not None:
        return
    root = sky130_root()
    lib_path = root / "libs.tech/ngspice/sky130.lib.spice"
    model_ref = root / "libs.ref/sky130_fd_pr/spice"
    if not lib_path.exists():
        raise RuntimeError(f"Missing SKY130 ngspice library: {lib_path}")
    if not model_ref.exists():
        raise RuntimeError(f"Missing SKY130 model directory: {model_ref}")
    sky130.install = sky130.Install(pdk_path=root, lib_path=lib_path, model_ref=model_ref)


__all__ = [
    "default_ngspice_options",
    "extract_ac_trace",
    "extract_subckt_name",
    "init_sky130_install",
    "interp_crossing",
    "interp_value",
    "make_test_result",
    "negative_feedback_phase_trace",
    "op_scalar",
    "run_ngspice_sim",
    "sky130_root",
]
