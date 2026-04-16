from __future__ import annotations

import unittest
from pathlib import Path

import hdl21 as h
import numpy as np
from hdl21.sim import Save, SaveMode, Sim, Tran

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_az_top import OpampAzHoldTbParams, OpampAzTopParams, opamp_az_top
from opamp.v3.prod.rc import current_core_params
from vlsirtools.spice import SimOptions, SupportedSimulators

from ._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_az_hold_200us_metrics.json")


def _simopts(name: str) -> SimOptions:
    return SimOptions(simulator=SupportedSimulators.NGSPICE, rundir=f"./tmp/{name}")


def _tran_waveform(result, signal_name: str) -> np.ndarray:
    tran = result.an[0].tran
    target = signal_name.lower()
    signals = list(tran.signals)
    idx = next((i for i, name in enumerate(signals) if name.lower() == target), None)
    if idx is None and "xtop.xdut." in target:
        suffix = target.split("xtop.xdut.", 1)[1]
        idx = next((i for i, name in enumerate(signals) if name.lower().endswith(suffix)), None)
    if idx is None:
        raise RuntimeError(f"Signal {signal_name} not found in tran result: {signals}")
    nsignals = len(signals)
    data = np.asarray(list(tran.data), dtype=float)
    npts = len(data) // nsignals
    start = idx * npts
    return data[start : start + npts]


def _base_params() -> OpampAzTopParams:
    return OpampAzTopParams(opamp_core_params=current_core_params())


def _build_hold_probe_test(
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

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, den, daz, dinf, vdd = h.Signals(7)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        vden = h.Vdc(dc=tb_params.vdd)(p=den, n=VSS)
        vdaz = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=t_az, rise=20e-9, fall=20e-9, width=tstop, period=2 * tstop)(p=daz, n=VSS)
        vdinf = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=t_az + t_lat, rise=20e-9, fall=20e-9, width=t_inf, period=2 * tstop)(p=dinf, n=VSS)
        vvin = h.Vdc(dc=tb_params.vin)(p=vinp, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, D_EN_OA=den, D_AZ_OA=daz, D_INF_OA=dinf, VDD=vdd, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=tstop, tstep=float(tb_params.tstep)),
            Save(SaveMode.ALL),
            install.include(corner),
        ],
    )


class OpampAzHold200usProbeTest(BaseV3SimTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        reset_metrics_file(METRICS_PATH)

    def test_probe_az_hold_200us(self) -> None:
        tb = OpampAzHoldTbParams(vin=0.9, t_inf=260e-6)
        result = run_ngspice_sim(
            _build_hold_probe_test(_base_params(), tb),
            _simopts("az_hold_200us"),
        )
        time = _tran_waveform(result, "time")
        vout = _tran_waveform(result, "v(xtop.vout)")
        vtrp = _tran_waveform(result, "v(xtop.xdut.vtrp)")
        vtrn = _tran_waveform(result, "v(xtop.xdut.vtrn)")
        dinf = _tran_waveform(result, "v(xtop.dinf)")

        inf_start = float(tb.t_az + tb.t_lat)
        hold_start = inf_start + 5e-6
        hold_end = inf_start + 205e-6
        window_mask = (dinf > 0.9) & (time >= hold_start) & (time <= hold_end)
        self.assertTrue(np.any(window_mask))

        time_win = time[window_mask]
        vout_win = vout[window_mask]
        u_win = (vtrn - vtrp)[window_mask]

        vout_drift = float(vout_win[-1] - vout_win[0])
        u_drift = float(u_win[-1] - u_win[0])
        payload = {
            "hold_window_start_s": float(time_win[0]),
            "hold_window_end_s": float(time_win[-1]),
            "vout_start_V": float(vout_win[0]),
            "vout_end_V": float(vout_win[-1]),
            "vout_drift_V": vout_drift,
            "u_trim_start_V": float(u_win[0]),
            "u_trim_end_V": float(u_win[-1]),
            "u_trim_drift_V": u_drift,
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertTrue(np.isfinite(vout_drift))
        self.assertTrue(np.isfinite(u_drift))


if __name__ == "__main__":
    unittest.main()
