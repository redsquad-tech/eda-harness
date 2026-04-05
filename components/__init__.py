"""Shared utilities for repository HDL21 components."""

from pathlib import Path
import re
from dataclasses import dataclass
from typing import Any

import sky130_hdl21
from vlsirtools.spice import SimOptions, SupportedSimulators

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


def parse_ngspice_scalar(log_text: str, name: str) -> float:
    """Parse a scalar value such as `v(out)` from ngspice output."""
    pattern = re.compile(rf"{re.escape(name)}\s*=\s*([0-9.eE+-]+)")
    match = pattern.search(log_text)
    if match is None:
        raise ValueError(f"Could not find scalar `{name}` in ngspice log")
    return float(match.group(1))


def run_ngspice_sim(sim, sim_options=None, *, rundir: str = "./scratch_ngspice"):
    """Run an HDL21 simulation through the repository-local ngspice compatibility layer."""
    if sim_options is None:
        sim_options = SimOptions(simulator=SupportedSimulators.NGSPICE, rundir=rundir)
    elif sim_options.simulator != SupportedSimulators.NGSPICE:
        raise ValueError(
            f"run_ngspice_sim requires SupportedSimulators.NGSPICE, got {sim_options.simulator}"
        )
    return run_compatible_sim(sim, sim_options)


def _format_metric_value(value: Any) -> str:
    """Format scalar metric values into compact human-readable strings."""
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def flatten_metrics(results: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Flatten nested `run_all_tests()`-style results into table rows."""
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
    """Render `run_all_tests()` results as a compact ASCII table."""
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
    """Print `run_all_tests()` results as a compact ASCII table."""
    print(format_metrics_table(results, title=title))


@dataclass(frozen=True)
class TestResultEnvelope:
    """Canonical repository result payload for component verification."""

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
    """Build a canonical JSON-like verification result payload."""
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
    "extract_subckt_name",
    "flatten_metrics",
    "format_metrics_table",
    "make_test_result",
    "parse_ngspice_scalar",
    "print_metrics_table",
    "require_sky130_install",
    "run_ngspice_sim",
]
