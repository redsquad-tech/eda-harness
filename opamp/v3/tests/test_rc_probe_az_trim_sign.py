from __future__ import annotations

import unittest
import importlib
from pathlib import Path

import hdl21 as h
import numpy as np
from hdl21.sim import Save, SaveMode, Sim, Tran
from vlsirtools.spice import SimOptions, SupportedSimulators

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.opamp_az_top import OpampAzTopParams, opamp_az_top
from opamp.v3.prod.rc import current_core_params

from ._helpers import BaseV3SimTest, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_az_trim_sign_metrics.json")
HDL21_GENERATOR_MODULE = importlib.import_module("hdl21.generator")


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


def _base_payload(**updates) -> dict:
    base = current_core_params()
    payload = {field: getattr(base, field) for field in base.__dataclass_fields__}
    payload.update(updates)
    return payload


def _build_calibration_only_test(
    dut_params: OpampAzTopParams,
    *,
    tstop: float = 12e-6,
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


class OpampAzTrimSignProbeTest(BaseV3SimTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        reset_metrics_file(METRICS_PATH)

    def test_probe_az_trim_sign(self) -> None:
        low_target = OpampAzTopParams(
            **_base_payload(r_vdrv_ref_top=3.0e6, r_vdrv_ref_bot=1.0e6)
        )
        high_target = OpampAzTopParams(
            **_base_payload(r_vdrv_ref_top=1.8e6, r_vdrv_ref_bot=1.0e6)
        )

        low = run_ngspice_sim(_build_calibration_only_test(low_target), _simopts("az_trim_sign_low"))
        HDL21_GENERATOR_MODULE.generator.cache.reset()
        high = run_ngspice_sim(_build_calibration_only_test(high_target), _simopts("az_trim_sign_high"))

        low_vtrp = _tran_waveform(low, "v(xtop.xdut.vtrp)")
        low_vtrn = _tran_waveform(low, "v(xtop.xdut.vtrn)")
        low_vx = _tran_waveform(low, "v(xtop.xdut.vx)")
        low_vdrv = _tran_waveform(low, "v(xtop.xdut.vdrv)")
        low_qref = _tran_waveform(low, "v(xtop.xdut.vdrv_qref)")

        high_vtrp = _tran_waveform(high, "v(xtop.xdut.vtrp)")
        high_vtrn = _tran_waveform(high, "v(xtop.xdut.vtrn)")
        high_vx = _tran_waveform(high, "v(xtop.xdut.vx)")
        high_vdrv = _tran_waveform(high, "v(xtop.xdut.vdrv)")
        high_qref = _tran_waveform(high, "v(xtop.xdut.vdrv_qref)")

        low_u = float(np.median((low_vtrn - low_vtrp)[-50:]))
        high_u = float(np.median((high_vtrn - high_vtrp)[-50:]))
        low_vx_final = float(np.median(low_vx[-50:]))
        high_vx_final = float(np.median(high_vx[-50:]))
        low_vdrv_final = float(np.median(low_vdrv[-50:]))
        high_vdrv_final = float(np.median(high_vdrv[-50:]))
        low_qref_final = float(np.median(low_qref[-50:]))
        high_qref_final = float(np.median(high_qref[-50:]))

        payload = {
            "low_target": {
                "vdrv_qref_V": low_qref_final,
                "u_trim_V": low_u,
                "vx_V": low_vx_final,
                "vdrv_V": low_vdrv_final,
            },
            "high_target": {
                "vdrv_qref_V": high_qref_final,
                "u_trim_V": high_u,
                "vx_V": high_vx_final,
                "vdrv_V": high_vdrv_final,
            },
            "delta": {
                "qref_V": high_qref_final - low_qref_final,
                "u_trim_V": high_u - low_u,
                "vx_V": high_vx_final - low_vx_final,
                "vdrv_V": high_vdrv_final - low_vdrv_final,
            },
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertTrue(np.isfinite(low_u))
        self.assertTrue(np.isfinite(high_u))
        self.assertGreater(high_qref_final, low_qref_final)


if __name__ == "__main__":
    unittest.main()
