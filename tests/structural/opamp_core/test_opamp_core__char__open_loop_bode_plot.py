from __future__ import annotations

import json
import math
import os
import sys
import unittest
from pathlib import Path

import hdl21 as h
import hdl21.sim.proto as sim_proto
import numpy as np
from hdl21.sim.proto import to_proto

from components.ngspice_netlister import _export_save_compat, write_compatible_netlist
from components.opamp_core import (
    OpampCoreOpenLoopTbParams,
    OpampCoreParams,
    _build_open_loop_tb,
    _default_ngspice_options,
    _extract_ac_trace,
    _interp_crossing,
    _interp_value,
    _negative_feedback_phase_trace,
    run_ngspice_sim,
)
from tests.structural._helpers import init_sky130_install


ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = ROOT / "tmp" / "opamp_core_open_loop_bode_debug"


def _svg_polyline(points: list[tuple[float, float]], *, stroke: str, stroke_width: float = 2.0) -> str:
    coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polyline fill="none" stroke="{stroke}" stroke-width="{stroke_width:.2f}" points="{coords}" />'


def _svg_text(x: float, y: float, text: str, *, size: int = 14, anchor: str = "start") -> str:
    safe = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" '
        f'font-family="monospace" fill="#111">{safe}</text>'
    )


def _scale_log_x(freq: np.ndarray, x0: float, width: float) -> np.ndarray:
    log_f = np.log10(np.maximum(freq, 1e-30))
    lo = float(np.min(log_f))
    hi = float(np.max(log_f))
    span = max(hi - lo, 1e-12)
    return x0 + width * (log_f - lo) / span


def _scale_linear(values: np.ndarray, y0: float, height: float, lo: float, hi: float) -> np.ndarray:
    span = max(hi - lo, 1e-12)
    return y0 + height * (1.0 - (values - lo) / span)


def _write_bode_svg(
    path: Path,
    *,
    freq: np.ndarray,
    mag_db: np.ndarray,
    phase_deg: np.ndarray,
    gbw_hz: float,
    phase_margin_deg: float,
) -> None:
    width = 1280.0
    height = 920.0
    margin_l = 90.0
    margin_r = 30.0
    top = 70.0
    plot_h = 300.0
    gap = 90.0
    bottom_h = 300.0
    plot_w = width - margin_l - margin_r

    mag_min = 20.0 * math.floor(float(np.min(mag_db)) / 20.0) - 20.0
    mag_max = 20.0 * math.ceil(float(np.max(mag_db)) / 20.0) + 20.0
    phase_min = 45.0 * math.floor(float(np.min(phase_deg)) / 45.0) - 45.0
    phase_max = 45.0 * math.ceil(float(np.max(phase_deg)) / 45.0) + 45.0

    x = _scale_log_x(freq, margin_l, plot_w)
    y_mag = _scale_linear(mag_db, top, plot_h, mag_min, mag_max)
    y_phase = _scale_linear(phase_deg, top + plot_h + gap, bottom_h, phase_min, phase_max)

    log_f = np.log10(np.maximum(freq, 1e-30))
    decade_lo = int(math.floor(float(np.min(log_f))))
    decade_hi = int(math.ceil(float(np.max(log_f))))

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
        '<rect width="100%" height="100%" fill="#fffdf8" />',
        _svg_text(margin_l, 35.0, "Baseline OpAmp Core Open-Loop Bode Plot", size=22),
        _svg_text(margin_l, 55.0, "Loop gain reconstructed from series-injection bench: T = -(Vout - Vfb) / Vfb", size=14),
        f'<rect x="{margin_l:.2f}" y="{top:.2f}" width="{plot_w:.2f}" height="{plot_h:.2f}" fill="#ffffff" stroke="#999" />',
        f'<rect x="{margin_l:.2f}" y="{top + plot_h + gap:.2f}" width="{plot_w:.2f}" height="{bottom_h:.2f}" fill="#ffffff" stroke="#999" />',
    ]

    for decade in range(decade_lo, decade_hi + 1):
        fx = 10.0 ** decade
        xpos = float(_scale_log_x(np.asarray([fx]), margin_l, plot_w)[0])
        elements.append(
            f'<line x1="{xpos:.2f}" y1="{top:.2f}" x2="{xpos:.2f}" y2="{top + plot_h + gap + bottom_h:.2f}" stroke="#ddd" />'
        )
        label = f"1e{decade} Hz"
        elements.append(_svg_text(xpos, top + plot_h + gap + bottom_h + 25.0, label, size=12, anchor="middle"))

    for value in range(int(mag_min), int(mag_max) + 1, 20):
        ypos = float(_scale_linear(np.asarray([value]), top, plot_h, mag_min, mag_max)[0])
        elements.append(f'<line x1="{margin_l:.2f}" y1="{ypos:.2f}" x2="{margin_l + plot_w:.2f}" y2="{ypos:.2f}" stroke="#eee" />')
        elements.append(_svg_text(margin_l - 10.0, ypos + 4.0, f"{value} dB", size=12, anchor="end"))

    for value in range(int(phase_min), int(phase_max) + 1, 45):
        ypos = float(_scale_linear(np.asarray([value]), top + plot_h + gap, bottom_h, phase_min, phase_max)[0])
        elements.append(f'<line x1="{margin_l:.2f}" y1="{ypos:.2f}" x2="{margin_l + plot_w:.2f}" y2="{ypos:.2f}" stroke="#eee" />')
        elements.append(_svg_text(margin_l - 10.0, ypos + 4.0, f"{value} deg", size=12, anchor="end"))

    elements.append(_svg_polyline(list(zip(x.tolist(), y_mag.tolist())), stroke="#005bbb", stroke_width=2.2))
    elements.append(_svg_polyline(list(zip(x.tolist(), y_phase.tolist())), stroke="#c62828", stroke_width=2.2))

    elements.append(_svg_text(margin_l, top - 12.0, "Magnitude", size=16))
    elements.append(_svg_text(margin_l, top + plot_h + gap - 12.0, "Phase", size=16))

    unity_y = float(_scale_linear(np.asarray([0.0]), top, plot_h, mag_min, mag_max)[0])
    elements.append(f'<line x1="{margin_l:.2f}" y1="{unity_y:.2f}" x2="{margin_l + plot_w:.2f}" y2="{unity_y:.2f}" stroke="#999" stroke-dasharray="6,4" />')
    phase_180_y = float(_scale_linear(np.asarray([-180.0]), top + plot_h + gap, bottom_h, phase_min, phase_max)[0])
    elements.append(f'<line x1="{margin_l:.2f}" y1="{phase_180_y:.2f}" x2="{margin_l + plot_w:.2f}" y2="{phase_180_y:.2f}" stroke="#999" stroke-dasharray="6,4" />')

    if math.isfinite(gbw_hz):
        gbw_x = float(_scale_log_x(np.asarray([gbw_hz]), margin_l, plot_w)[0])
        elements.append(f'<line x1="{gbw_x:.2f}" y1="{top:.2f}" x2="{gbw_x:.2f}" y2="{top + plot_h + gap + bottom_h:.2f}" stroke="#2e7d32" stroke-dasharray="8,5" />')
        elements.append(_svg_text(gbw_x + 6.0, top + 20.0, f"GBW = {gbw_hz:.3e} Hz", size=13))
    if math.isfinite(phase_margin_deg):
        elements.append(_svg_text(margin_l + 320.0, top + 20.0, f"Phase margin = {phase_margin_deg:.2f} deg", size=13))

    elements.extend(
        [
            f'<line x1="{margin_l + 770:.2f}" y1="{top - 28:.2f}" x2="{margin_l + 820:.2f}" y2="{top - 28:.2f}" stroke="#005bbb" stroke-width="2.2" />',
            _svg_text(margin_l + 828.0, top - 23.0, "|T| in dB", size=13),
            f'<line x1="{margin_l + 930:.2f}" y1="{top - 28:.2f}" x2="{margin_l + 980:.2f}" y2="{top - 28:.2f}" stroke="#c62828" stroke-width="2.2" />',
            _svg_text(margin_l + 988.0, top - 23.0, "phase(T)", size=13),
        ]
    )

    elements.append("</svg>")
    path.write_text("\n".join(elements))


def _write_bench_svg(path: Path) -> None:
    width = 1180
    height = 500
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fffdf8" />',
        _svg_text(60, 40, "Baseline Open-Loop AC Fixture", size=24),
        _svg_text(60, 68, "Series injection between VOUT and VINN, with VINP biased at VCM", size=15),
        '<rect x="430" y="120" width="250" height="180" fill="#ffffff" stroke="#111" stroke-width="2" rx="8" />',
        _svg_text(555, 170, "opamp_core", size=24, anchor="middle"),
        _svg_text(555, 205, "VINP VINN VOUT EN VDD VSS", size=13, anchor="middle"),
        '<line x1="240" y1="170" x2="430" y2="170" stroke="#111" stroke-width="2" />',
        '<line x1="680" y1="210" x2="840" y2="210" stroke="#111" stroke-width="2" />',
        '<line x1="840" y1="210" x2="840" y2="140" stroke="#111" stroke-width="2" />',
        '<line x1="840" y1="140" x2="240" y2="140" stroke="#111" stroke-width="2" />',
        '<line x1="240" y1="140" x2="240" y2="230" stroke="#111" stroke-width="2" />',
        '<line x1="240" y1="230" x2="430" y2="230" stroke="#111" stroke-width="2" />',
        _svg_text(200, 165, "VINP", size=16, anchor="end"),
        _svg_text(200, 225, "VINN", size=16, anchor="end"),
        _svg_text(870, 215, "VOUT", size=16),
        '<circle cx="240" cy="170" r="4" fill="#111" />',
        '<circle cx="240" cy="230" r="4" fill="#111" />',
        '<circle cx="840" cy="210" r="4" fill="#111" />',
        '<rect x="115" y="150" width="70" height="40" fill="#eef6ff" stroke="#111" />',
        _svg_text(150, 175, "VCM", size=16, anchor="middle"),
        '<rect x="470" y="340" width="80" height="50" fill="#eef6ff" stroke="#111" />',
        _svg_text(510, 370, "VDD", size=18, anchor="middle"),
        '<rect x="585" y="340" width="80" height="50" fill="#eef6ff" stroke="#111" />',
        _svg_text(625, 370, "EN", size=18, anchor="middle"),
        '<line x1="510" y1="340" x2="510" y2="300" stroke="#111" stroke-width="2" />',
        '<line x1="625" y1="340" x2="625" y2="300" stroke="#111" stroke-width="2" />',
        '<line x1="470" y1="250" x2="470" y2="300" stroke="#111" stroke-width="2" />',
        '<line x1="625" y1="250" x2="625" y2="300" stroke="#111" stroke-width="2" />',
        '<line x1="470" y1="300" x2="510" y2="300" stroke="#111" stroke-width="2" />',
        '<line x1="625" y1="300" x2="680" y2="300" stroke="#111" stroke-width="2" />',
        '<line x1="680" y1="300" x2="680" y2="250" stroke="#111" stroke-width="2" />',
        '<line x1="745" y1="210" x2="790" y2="210" stroke="#111" stroke-width="2" />',
        '<circle cx="790" cy="210" r="4" fill="#111" />',
        '<rect x="720" y="85" width="110" height="45" fill="#fff3e0" stroke="#111" />',
        _svg_text(775, 113, "L = 1e9 H", size=16, anchor="middle"),
        '<line x1="775" y1="130" x2="775" y2="210" stroke="#111" stroke-width="2" />',
        '<rect x="640" y="235" width="120" height="45" fill="#e8f5e9" stroke="#111" />',
        _svg_text(700, 263, "Vtest AC=1", size=16, anchor="middle"),
        '<line x1="700" y1="235" x2="700" y2="210" stroke="#111" stroke-width="2" />',
        '<line x1="700" y1="280" x2="700" y2="330" stroke="#111" stroke-width="2" />',
        '<line x1="700" y1="330" x2="240" y2="330" stroke="#111" stroke-width="2" />',
        '<line x1="240" y1="330" x2="240" y2="230" stroke="#111" stroke-width="2" />',
        '<rect x="885" y="170" width="90" height="40" fill="#eef6ff" stroke="#111" />',
        _svg_text(930, 195, "Cload", size=16, anchor="middle"),
        '<line x1="930" y1="210" x2="930" y2="300" stroke="#111" stroke-width="2" />',
        '<rect x="995" y="170" width="90" height="40" fill="#eef6ff" stroke="#111" />',
        _svg_text(1040, 195, "Rprobe", size=16, anchor="middle"),
        '<line x1="1040" y1="210" x2="1040" y2="300" stroke="#111" stroke-width="2" />',
        '<line x1="930" y1="300" x2="1040" y2="300" stroke="#111" stroke-width="2" />',
        '<line x1="700" y1="330" x2="1040" y2="330" stroke="#111" stroke-width="2" />',
        _svg_text(1070, 338, "VSS", size=16),
        _svg_text(60, 430, "Measured loop gain:", size=18),
        _svg_text(250, 430, "T(f) = -(Vout - Vfb) / Vfb", size=18),
        _svg_text(60, 460, "where Vfb is the small-signal voltage on the VINN side of the break.", size=15),
        "</svg>",
    ]
    path.write_text("\n".join(elements))


@unittest.skipUnless(
    os.getenv("GENERATE_OPTIONAL_PLOTS") == "1",
    "Optional diagnostic test. Run with GENERATE_OPTIONAL_PLOTS=1 to emit Bode plot artifacts.",
)
class TestOpampCoreCharOpenLoopBodePlot(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT))
        init_sky130_install()
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    def test_opamp_core__char__open_loop_bode_plot(self) -> None:
        dut_params = OpampCoreParams()
        tb_params = OpampCoreOpenLoopTbParams()
        sim = _build_open_loop_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            c_load=float(tb_params.c_load),
            r_probe=float(tb_params.r_probe),
            v_cm=float(tb_params.v_cm),
            f_start=float(tb_params.f_start),
            f_stop=float(tb_params.f_stop),
            npts=int(tb_params.npts),
            temp_c=float(tb_params.temp_c),
            corner=h.pdk.Corner.TYP,
        )
        sim_proto.export_save = _export_save_compat
        netlist_path = write_compatible_netlist(to_proto(sim), ARTIFACT_DIR / "open_loop_bench.sp")
        result = run_ngspice_sim(sim, _default_ngspice_options("opamp_core_open_loop_bode_debug"))

        freq, vout_amp = _extract_ac_trace(result, "v(xtop.vout)")
        _, vfb = _extract_ac_trace(result, "v(xtop.vinn_sig)")
        freq = np.asarray(freq, dtype=float)
        vout_amp = np.asarray(vout_amp)
        vfb = np.asarray(vfb)
        vtest_amp = vout_amp - vfb
        loop_gain = -vtest_amp / np.where(np.abs(vfb) > 1e-30, vfb, 1e-30 + 0j)
        mag = np.abs(loop_gain)
        mag_db = 20.0 * np.log10(np.maximum(mag, 1e-30))
        phase_deg, low_freq_phase_deg_raw = _negative_feedback_phase_trace(loop_gain)
        gbw_hz, _ = _interp_crossing(freq, mag, 1.0)
        phase_at_unity_deg_raw = float("nan")
        phase_margin_deg = float("nan")
        if math.isfinite(gbw_hz):
            phase_at_unity_deg_raw = _interp_value(freq, phase_deg, gbw_hz)
            if math.isfinite(phase_at_unity_deg_raw):
                phase_margin_deg = 180.0 + phase_at_unity_deg_raw

        bode_svg = ARTIFACT_DIR / "open_loop_bode.svg"
        bench_svg = ARTIFACT_DIR / "open_loop_bench.svg"
        metrics_json = ARTIFACT_DIR / "open_loop_bode_metrics.json"
        _write_bode_svg(
            bode_svg,
            freq=freq,
            mag_db=np.asarray(mag_db, dtype=float),
            phase_deg=np.asarray(phase_deg, dtype=float),
            gbw_hz=float(gbw_hz),
            phase_margin_deg=float(phase_margin_deg),
        )
        _write_bench_svg(bench_svg)

        metrics_payload = {
            "tb_params": {
                "vdd": float(tb_params.vdd),
                "c_load": float(tb_params.c_load),
                "r_probe": float(tb_params.r_probe),
                "v_cm": float(tb_params.v_cm),
                "f_start": float(tb_params.f_start),
                "f_stop": float(tb_params.f_stop),
                "npts": int(tb_params.npts),
                "temp_c": float(tb_params.temp_c),
                "corner": "tt",
            },
            "extracted_metrics": {
                "loop_gain_dc_db": float(mag_db[0]),
                "gbw_hz": float(gbw_hz),
                "phase_margin_deg": float(phase_margin_deg),
                "low_freq_phase_deg_raw": float(low_freq_phase_deg_raw),
                "phase_at_unity_deg_raw": float(phase_at_unity_deg_raw),
            },
            "signals": {
                "freq_hz": [float(v) for v in freq.tolist()],
                "vout_real": [float(np.real(v)) for v in vout_amp.tolist()],
                "vout_imag": [float(np.imag(v)) for v in vout_amp.tolist()],
                "vfb_real": [float(np.real(v)) for v in vfb.tolist()],
                "vfb_imag": [float(np.imag(v)) for v in vfb.tolist()],
                "loop_gain_mag_db": [float(v) for v in mag_db.tolist()],
                "loop_gain_phase_deg": [float(v) for v in phase_deg.tolist()],
            },
            "artifacts": {
                "netlist": str(netlist_path),
                "bench_svg": str(bench_svg),
                "bode_svg": str(bode_svg),
            },
        }
        metrics_json.write_text(json.dumps(metrics_payload, indent=2))

        self.assertTrue(bode_svg.exists())
        self.assertTrue(bench_svg.exists())
        self.assertTrue(metrics_json.exists())
        self.assertTrue(netlist_path.exists())


if __name__ == "__main__":
    unittest.main()
