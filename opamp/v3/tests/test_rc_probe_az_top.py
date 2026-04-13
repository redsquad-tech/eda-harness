from __future__ import annotations

import unittest
from pathlib import Path

import hdl21 as h
import numpy as np

from opamp.v3.opamp_az_top import (
    OpampAzHighZTbParams,
    OpampAzHoldTbParams,
    OpampAzTopParams,
    build_highz_test,
    build_hold_test,
    run_structural_checks,
)
from opamp.v3.prod.rc import current_core_params

from ._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json

from components import run_ngspice_sim
from vlsirtools.spice import SimOptions, SupportedSimulators


METRICS_PATH = Path(__file__).with_name("rc_probe_az_top_metrics.json")


def _simopts(name: str) -> SimOptions:
    return SimOptions(simulator=SupportedSimulators.NGSPICE, rundir=f"./tmp/{name}")


def _tran_waveform(result, signal_name: str) -> np.ndarray:
    tran = result.an[0].tran
    target = signal_name.lower()
    signals = list(tran.signals)
    idx = next((i for i, name in enumerate(signals) if name.lower() == target), None)
    if idx is None:
        raise RuntimeError(f"Signal {signal_name} not found in tran result: {signals}")
    nsignals = len(signals)
    data = np.asarray(list(tran.data), dtype=float)
    npts = len(data) // nsignals
    start = idx * npts
    return data[start : start + npts]


def _base_params() -> OpampAzTopParams:
    return OpampAzTopParams(opamp_core_params=current_core_params())


class OpampAzTopProbeTest(BaseV3SimTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        reset_metrics_file(METRICS_PATH)

    def test_probe_az_top(self) -> None:
        params = _base_params()
        structural = run_structural_checks(params)
        self.assertTrue(structural["contains_input_mux"])
        self.assertTrue(structural["contains_trim_pair"])
        self.assertTrue(structural["contains_hold_caps"])
        self.assertTrue(structural["contains_output_isolation"])

        highz_az = run_ngspice_sim(
            build_highz_test(params, OpampAzHighZTbParams(mode_az=1.8, mode_inf=0.0), corner=h.pdk.Corner.TYP),
            _simopts("az_top_highz_az"),
        )
        vout_highz_az = float(np.median(_tran_waveform(highz_az, "v(xtop.vout)")[-20:]))
        # With the output disconnected, VOUT should be dominated by the external probe network,
        # not clamped near the core's nominal mid-point.
        self.assertGreater(abs(vout_highz_az), 0.2)
        hold_tb = OpampAzHoldTbParams(t_inf=260e-6)
        hold = run_ngspice_sim(
            build_hold_test(params, hold_tb, corner=h.pdk.Corner.TYP),
            _simopts("az_top_hold"),
        )
        time = _tran_waveform(hold, "time")
        vout = _tran_waveform(hold, "v(xtop.vout)")
        daz = _tran_waveform(hold, "v(xtop.daz)")
        dinf = _tran_waveform(hold, "v(xtop.dinf)")
        latch_mask = (daz < 0.1) & (dinf < 0.1) & (time > float(hold_tb.t_az + 0.2e-6))
        self.assertTrue(np.any(latch_mask))
        vout_highz_lat = float(np.median(vout[latch_mask][-20:]))
        self.assertTrue(np.isfinite(vout_highz_lat))
        self.assertGreater(vout_highz_lat, -0.2)
        self.assertLess(vout_highz_lat, 0.2)

        inf_mask = dinf > 0.9
        self.assertTrue(np.any(inf_mask))
        vout_inf = float(np.median(vout[inf_mask][-50:]))
        self.assertGreater(vout_inf, 0.5)
        self.assertLess(vout_inf, 1.3)

        # Smoke-level hold criterion:
        # this test validates mode sequencing and stored-state survival only.
        # Real AZ-quality / residual-offset closure is tracked separately.
        inf_hold_mask = inf_mask & (time > float(hold_tb.t_az + hold_tb.t_lat + 50e-6))
        self.assertTrue(np.any(inf_hold_mask))
        inf_vout = vout[inf_hold_mask]
        vout_droop = float(abs(inf_vout[-1] - inf_vout[0]))
        self.assertLess(vout_droop, 0.3)

        payload = {
            "structural": structural,
            "highz_calibration_vout_V": vout_highz_az,
            "highz_latching_vout_V": vout_highz_lat,
            "inference_vout_V": vout_inf,
            "inference_vout_droop_V": vout_droop,
            "az_high_samples": int(np.count_nonzero(daz > 0.9)),
            "inf_high_samples": int(np.count_nonzero(inf_mask)),
            "time_stop_s": float(time[-1]),
        }
        write_metrics_json(METRICS_PATH, payload)


if __name__ == "__main__":
    unittest.main()
