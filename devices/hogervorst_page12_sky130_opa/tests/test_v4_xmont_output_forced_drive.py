from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import (
    NeuronOaParams,
    classab_output_stage,
    compile_for_sky130,
    monticelli_cell,
)
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, find_signal, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_xmont_output_forced_drive_metrics.json")


def _build_tb(params: NeuronOaParams, drv_p_v: float, drv_n_v: float):
    mont = monticelli_cell(params.monticelli)
    out = classab_output_stage(params.output)

    @h.module
    class Tb:
        VSS = h.Port()
        avdd, vgp, vgn, vout, vcm = h.Signals(5)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvcm = h.Vdc(dc=0.9)(p=vcm, n=VSS)
        vdrv_p = h.Vdc(dc=drv_p_v)(p=vgp, n=VSS)
        vdrv_n = h.Vdc(dc=drv_n_v)(p=vgn, n=VSS)
        iih_q = h.Idc(dc=1e-6)(p=avdd, n=vgp)
        iik_q = h.Idc(dc=1e-6)(p=vgn, n=VSS)

        rload = h.Res(r=1e6)(p=vout, n=vcm)
        xmont = mont(vgp=vgp, vgn=vgn, avdd=avdd, agnd=VSS)
        xout = out(
            vgp=vgp,
            vgn=vgn,
            vout=vout,
            avdd=avdd,
            agnd=VSS,
        )

    return Tb


class TestV4XmontOutputForcedDrive(BaseV4SimTest):
    def test_xmont_output_forced_drive(self) -> None:
        params = NeuronOaParams()
        rows = []
        for idx, (drv_p_v, drv_n_v) in enumerate(((0.80, 1.00), (0.90, 0.90), (1.00, 0.80))):
            tb = h.elaborate(_build_tb(params, drv_p_v=drv_p_v, drv_n_v=drv_n_v))
            compile_for_sky130(tb)
            sim = Sim(
                tb=tb,
                attrs=[
                    Op(),
                    Save("all"),
                    h.sim.Literal(".temp 27"),
                    sky130.install.include(h.pdk.Corner.TYP),
                ],
            )
            result = run_ngspice_sim(
                sim,
                default_ngspice_options(f"opamp_v4_xmont_force_{idx}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
            )
            data = result.an[0].data
            rows.append(
                {
                    "drv_p_V": drv_p_v,
                    "drv_n_V": drv_n_v,
                    "vgp_V": find_signal(data, exact="v(xtop.vgp)"),
                    "vgn_V": find_signal(data, exact="v(xtop.vgn)"),
                    "vout_V": find_signal(data, exact="v(xtop.vout)"),
                    "iq_uA": 1e6 * abs(find_signal(data, exact="i(v.xtop.vvvdd)")),
                }
            )

        first, last = rows[0], rows[-1]
        ddrv = last["drv_p_V"] - first["drv_p_V"]
        payload = {
            "rows": rows,
            "summary": {
                "drv_to_vgp_slope": (last["vgp_V"] - first["vgp_V"]) / ddrv,
                "drv_to_vgn_slope": (last["vgn_V"] - first["vgn_V"]) / ddrv,
                "drv_to_vout_slope": (last["vout_V"] - first["vout_V"]) / ddrv,
                "vg_span_V": max(r["vgp_V"] - r["vgn_V"] for r in rows) - min(r["vgp_V"] - r["vgn_V"] for r in rows),
                "gates_within_rails": all(0.0 <= r["vgp_V"] <= 1.8 and 0.0 <= r["vgn_V"] <= 1.8 for r in rows),
                "gates_move_apart": ((last["vgp_V"] - first["vgp_V"]) / ddrv) * ((last["vgn_V"] - first["vgn_V"]) / ddrv) < 0.0,
            },
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertFinite(payload["summary"]["drv_to_vgp_slope"])
        self.assertFinite(payload["summary"]["drv_to_vgn_slope"])
        self.assertFinite(payload["summary"]["drv_to_vout_slope"])
        self.assertTrue(payload["summary"]["gates_within_rails"])
        self.assertTrue(payload["summary"]["gates_move_apart"])
