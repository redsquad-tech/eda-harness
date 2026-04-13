from __future__ import annotations

import unittest
from pathlib import Path

import hdl21 as h
import numpy as np
from hdl21.sim import Save, Sim, Tran
from vlsirtools.spice import SimOptions, SupportedSimulators

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_az_top import OpampAzHoldTbParams, OpampAzTopParams, opamp_az_top
from opamp.v3.prod.rc import current_core_params

from ._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_az_residual_offset_metrics.json")


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


def _build_follower_hold_test(
    dut_params: OpampAzTopParams,
    tb_params: OpampAzHoldTbParams,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)
    t_az = float(tb_params.t_az)
    t_lat = float(tb_params.t_lat)
    t_inf = float(tb_params.t_inf)
    tstop = t_az + t_lat + t_inf
    vin = float(tb_params.vin)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, den, daz, dinf, vdd = h.Signals(7)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        vden = h.Vdc(dc=tb_params.vdd)(p=den, n=VSS)
        vdaz = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=t_az, rise=20e-9, fall=20e-9, width=tstop, period=2 * tstop)(p=daz, n=VSS)
        vdinf = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=t_az + t_lat, rise=20e-9, fall=20e-9, width=t_inf, period=2 * tstop)(p=dinf, n=VSS)
        # Negative feedback for the current core polarity: VINN sees the target, VINP sees VOUT.
        vvin = h.Vdc(dc=vin)(p=vinn, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinp)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, D_EN_OA=den, D_AZ_OA=daz, D_INF_OA=dinf, VDD=vdd, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=tstop, tstep=float(tb_params.tstep)),
            Save("time, v(xtop.vout), v(xtop.vinn), v(xtop.dinf)"),
            install.include(corner),
        ],
    )


class OpampAzResidualOffsetProbeTest(BaseV3SimTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        reset_metrics_file(METRICS_PATH)

    def test_probe_az_residual_offset(self) -> None:
        params = _base_params()
        tb = OpampAzHoldTbParams(vin=0.9, t_inf=260e-6)
        result = run_ngspice_sim(
            _build_follower_hold_test(params, tb, corner=h.pdk.Corner.TYP),
            _simopts("az_top_residual_offset"),
        )
        time = _tran_waveform(result, "time")
        vout = _tran_waveform(result, "v(xtop.vout)")
        dinf = _tran_waveform(result, "v(xtop.dinf)")
        vinn = _tran_waveform(result, "v(xtop.vinn)")

        inf_mask = (dinf > 0.9) & (time > float(tb.t_az + tb.t_lat + 50e-6))
        self.assertTrue(np.any(inf_mask))
        vin_cm = float(np.median(vinn[inf_mask]))
        vout_inf = float(np.median(vout[inf_mask][-50:]))
        residual_offset_v = vout_inf - vin_cm
        residual_offset_uV = residual_offset_v * 1e6

        payload = {
            "vin_cm_V": vin_cm,
            "inference_vout_V": vout_inf,
            "residual_offset_V": residual_offset_v,
            "residual_offset_uV": residual_offset_uV,
            "time_stop_s": float(time[-1]),
        }
        write_metrics_json(METRICS_PATH, payload)

        # Probe only for now: make sure the result is finite and the loop stays inside rails.
        self.assertTrue(np.isfinite(residual_offset_uV))
        self.assertGreater(vout_inf, 0.1)
        self.assertLess(vout_inf, 1.7)


if __name__ == "__main__":
    unittest.main()
