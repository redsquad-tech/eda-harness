from __future__ import annotations

import unittest
from pathlib import Path

import hdl21 as h
import numpy as np
from hdl21.sim import Save, SaveMode, Sim, Tran
from vlsirtools.spice import SimOptions, SupportedSimulators

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_az_top import OpampAzTopParams, opamp_az_top
from opamp.v3.prod.rc import current_core_params

from ._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_az_convergence_metrics.json")


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


def _build_convergence_test(
    dut_params: OpampAzTopParams,
    *,
    tstop: float = 20e-6,
    tstep: float = 50e-9,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, den, daz, dinf, vdd = h.Signals(7)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        vden = h.Vdc(dc=1.8)(p=den, n=VSS)
        vdaz = h.Vdc(dc=1.8)(p=daz, n=VSS)
        vdinf = h.Vdc(dc=0.0)(p=dinf, n=VSS)
        vvinp = h.Vdc(dc=0.0)(p=vinp, n=VSS)
        vvinn = h.Vdc(dc=0.0)(p=vinn, n=VSS)
        rprobe = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, D_EN_OA=den, D_AZ_OA=daz, D_INF_OA=dinf, VDD=vdd, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=tstop, tstep=tstep),
            Save(SaveMode.ALL),
            install.include(corner),
        ],
    )


class OpampAzConvergenceProbeTest(BaseV3SimTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        reset_metrics_file(METRICS_PATH)

    def test_probe_az_convergence(self) -> None:
        result = run_ngspice_sim(_build_convergence_test(_base_params()), _simopts("az_convergence"))
        time = _tran_waveform(result, "time")
        vsense = _tran_waveform(result, "v(xtop.xdut.vsense_az)")
        vtarget = _tran_waveform(result, "v(xtop.xdut.vtarget_az)")
        vdrv = _tran_waveform(result, "v(xtop.xdut.vdrv)")
        vtrp = _tran_waveform(result, "v(xtop.xdut.vtrp)")
        vtrn = _tran_waveform(result, "v(xtop.xdut.vtrn)")

        err = vsense - vtarget
        start_mask = (time > 1.5e-6) & (time < 2.5e-6)
        end_mask = time > (float(time[-1]) - 2e-6)
        self.assertTrue(np.any(start_mask))
        self.assertTrue(np.any(end_mask))

        err_start = float(np.median(err[start_mask]))
        err_end = float(np.median(err[end_mask]))
        abs_err_start = float(abs(err_start))
        abs_err_end = float(abs(err_end))

        settle_mask = np.abs(err) < 10e-3
        settle_time = float(time[np.argmax(settle_mask)]) if np.any(settle_mask) else float("nan")

        payload = {
            "error_start_V": err_start,
            "error_end_V": err_end,
            "abs_error_start_V": abs_err_start,
            "abs_error_end_V": abs_err_end,
            "settle_10mV_s": settle_time,
            "vdrv_end_V": float(np.median(vdrv[end_mask])),
            "u_trim_end_V": float(np.median((vtrn - vtrp)[end_mask])),
            "time_stop_s": float(time[-1]),
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertTrue(np.isfinite(abs_err_start))
        self.assertTrue(np.isfinite(abs_err_end))


if __name__ == "__main__":
    unittest.main()
