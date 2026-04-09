"""Shared utilities for `opamp.v2` modules."""

import math
from pathlib import Path
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import numpy as np
import sky130_hdl21
from vlsirtools.spice import ResultFormat, SimOptions, SupportedSimulators

from components.ngspice_netlister import run_compatible_sim


PDK_ROOT = Path("./pdks/sky130A")


def require_sky130_install():
    """Return the configured SKY130 installation or raise a clear error."""
    if sky130_hdl21.install is None:
        raise RuntimeError(
            "sky130_hdl21.install is not initialized. "
            f"Initialize the SKY130 PDK install before running tests or simulations. "
            f"Repository PDK root: {PDK_ROOT}."
        )
    return sky130_hdl21.install


def extract_subckt_name(netlist_text: str) -> str:
    """Extract the first .SUBCKT name from a SPICE netlist."""
    for line in netlist_text.splitlines():
        if line.startswith(".SUBCKT "):
            return line.split()[1]
    raise ValueError("No .SUBCKT definition found in netlist")


def run_ngspice_sim(sim, sim_options=None, *, rundir: str = "./scratch_ngspice"):
    """Run an HDL21 simulation through the repository-local ngspice compatibility layer."""
    if sim_options is None:
        sim_options = SimOptions(simulator=SupportedSimulators.NGSPICE, rundir=rundir)
    elif sim_options.simulator != SupportedSimulators.NGSPICE:
        raise ValueError(
            f"run_ngspice_sim requires SupportedSimulators.NGSPICE, got {sim_options.simulator}"
        )
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


def op_scalar_suffix(result, suffix: str) -> float:
    op = getattr(result.an[0], "op", result.an[0])
    target = suffix.lower()
    if isinstance(getattr(op, "data", None), dict):
        for name, value in op.data.items():
            if name.lower().endswith(target):
                return float(value)
        raise RuntimeError(f"Signal suffix {suffix} not found in op result: {list(op.data.keys())}")
    for name, value in zip(op.signals, op.data):
        if name.lower().endswith(target):
            return float(value)
    raise RuntimeError(f"Signal suffix {suffix} not found in op result")


def tran_waveform(result, signal_name: str):
    tran = getattr(result.an[0], "tran", result.an[0])
    target = signal_name.lower()
    if hasattr(tran, "signals") and hasattr(tran, "data"):
        signals = list(tran.signals)
        idx = next((idx for idx, name in enumerate(signals) if name.lower() == target), None)
        if idx is None:
            raise RuntimeError(f"Signal {signal_name} not found in tran result: {signals}")
        nsignals = len(signals)
        data = list(tran.data)
        npts = len(data) // nsignals
        start = idx * npts
        return data[start : start + npts]
    if isinstance(getattr(tran, "data", None), dict):
        for name, value in tran.data.items():
            if name.lower() == target:
                return value
        raise RuntimeError(f"Signal {signal_name} not found in tran result keys: {list(tran.data.keys())}")
    raise RuntimeError(f"Unsupported tran result shape for signal {signal_name}: {type(tran)}")


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


def extract_ac_trace_suffix(result, suffix: str):
    ac = result.an[0]
    target = suffix.lower()
    data_map = getattr(ac, "data", None)
    freq = getattr(ac, "freq", None)
    if not isinstance(data_map, dict) or freq is None:
        raise RuntimeError(f"Unsupported AC result shape for suffix {suffix}: {type(ac)}")
    for key, data in data_map.items():
        if key.lower().endswith(target):
            return freq, data
    raise RuntimeError(f"AC trace suffix {suffix} not found in result keys: {list(data_map.keys())}")


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


def _format_metric_value(value: Any) -> str:
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def flatten_metrics(results: dict[str, Any]) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for section, payload in results.items():
        if isinstance(payload, dict):
            if {"component", "category", "purpose", "metrics"}.issubset(payload.keys()):
                if "pass" in payload:
                    rows.append((section, "pass", _format_metric_value(payload["pass"])))
                for metric, value in payload["metrics"].items():
                    rows.append((section, metric, _format_metric_value(value)))
                continue
            for metric, value in payload.items():
                rows.append((section, metric, _format_metric_value(value)))
        else:
            rows.append((section, "value", _format_metric_value(payload)))
    return rows


def format_metrics_table(results: dict[str, Any], *, title: str | None = None) -> str:
    rows = flatten_metrics(results)
    headers = ("test", "metric", "value")
    body = [headers, *rows]
    widths = [max(len(str(row[idx])) for row in body) for idx in range(3)]

    def fmt(row: tuple[str, str, str]) -> str:
        return " | ".join(str(cell).ljust(widths[idx]) for idx, cell in enumerate(row))

    sep = "-+-".join("-" * width for width in widths)
    lines = []
    if title is not None:
        lines.append(title)
    lines.append(fmt(headers))
    lines.append(sep)
    lines.extend(fmt(row) for row in rows)
    return "\n".join(lines)


def print_metrics_table(results: dict[str, Any], *, title: str | None = None) -> None:
    print(format_metrics_table(results, title=title))


@dataclass(frozen=True)
class TestResultEnvelope:
    component: str
    category: str
    purpose: str
    metrics: dict[str, Any]
    passed: bool | None = None
    corner_worst: str | None = None
    margin: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None
    spec_name: str | None = None
    violations: list[str] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "component": self.component,
            "category": self.category,
            "purpose": self.purpose,
            "metrics": self.metrics,
        }
        if self.category != "char":
            payload["pass"] = bool(self.passed)
        if self.corner_worst is not None:
            payload["corner_worst"] = self.corner_worst
        if self.category in ("contract", "budget"):
            payload["margin"] = self.margin or {}
        elif self.margin:
            payload["margin"] = self.margin
        if self.artifacts:
            payload["artifacts"] = self.artifacts
        if self.spec_name is not None:
            payload["spec_name"] = self.spec_name
        if self.violations is not None:
            payload["violations"] = self.violations
        return payload


def make_test_result(
    *,
    component: str,
    category: str,
    purpose: str,
    metrics: dict[str, Any],
    passed: bool | None = None,
    corner_worst: str | None = None,
    margin: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
    spec_name: str | None = None,
    violations: list[str] | None = None,
) -> dict[str, Any]:
    return TestResultEnvelope(
        component=component,
        category=category,
        purpose=purpose,
        metrics=metrics,
        passed=passed,
        corner_worst=corner_worst,
        margin=margin,
        artifacts=artifacts,
        spec_name=spec_name,
        violations=violations,
    ).as_dict()


__all__ = [
    "PDK_ROOT",
    "default_ngspice_options",
    "extract_ac_trace",
    "extract_ac_trace_suffix",
    "extract_subckt_name",
    "flatten_metrics",
    "format_metrics_table",
    "interp_crossing",
    "interp_value",
    "make_test_result",
    "negative_feedback_phase_trace",
    "op_scalar",
    "op_scalar_suffix",
    "print_metrics_table",
    "require_sky130_install",
    "run_ngspice_sim",
    "tran_waveform",
]
