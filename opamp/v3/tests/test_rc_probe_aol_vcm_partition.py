from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import numpy as np
from hdl21.sim import Ac, LogSweep, Op, Save, Sim
from vlsirtools.spice import ResultFormat

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.common import extract_ac_trace, unique_ngspice_options
from opamp.v3.opamp_core import opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_aol_vcm_partition_metrics.json")


def _build_core_op_tb(dut, *, v_cm: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=v_cm)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=v_cm)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Tb


def _build_core_ac_tb(dut, *, v_cm: float, v_diff: float):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=v_cm, ac=0.5 * v_diff)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=v_cm, ac=-0.5 * v_diff)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Tb


def _run_op(sim_name: str, sim: Sim):
    return run_ngspice_sim(
        sim,
        unique_ngspice_options(sim_name, fmt=ResultFormat.SIM_DATA),
        rundir=f"./tmp/{sim_name}_{uuid4().hex[:8]}",
    )


class TestRcProbeAolVcmPartition(BaseV3SimTest):
    def test_probe_aol_vcm_partition(self) -> None:
        reset_metrics_file(METRICS_PATH)
        install = require_sky130_install()
        params = build_core_params()
        core = opamp_core(params)
        vcm_points = [0.4, 0.65, 0.9]
        v_diff = 100e-6
        cases: list[dict[str, float]] = []

        for v_cm in vcm_points:
            op_save = [
                "v(xtop.vout)",
                "v(xtop.xxdut.vx)",
                "v(xtop.xxdut.vref)",
                "v(xtop.xxdut.tail1)",
                "v(xtop.xxdut.vdrv)",
                "@m.xtop.xxdut.xxin.xmp.msky130_fd_pr__pfet_01v8[gm]",
                "@m.xtop.xxdut.xxin.xmp.msky130_fd_pr__pfet_01v8[gds]",
                "@m.xtop.xxdut.xxin.xmp.msky130_fd_pr__pfet_01v8[vth]",
                "@m.xtop.xxdut.xxin.xmp.msky130_fd_pr__pfet_01v8[vdsat]",
                "@m.xtop.xxdut.xm_load_out.msky130_fd_pr__nfet_01v8[gm]",
                "@m.xtop.xxdut.xm_load_out.msky130_fd_pr__nfet_01v8[gds]",
                "@m.xtop.xxdut.xm_load_out.msky130_fd_pr__nfet_01v8[vth]",
                "@m.xtop.xxdut.xm_load_out.msky130_fd_pr__nfet_01v8[vdsat]",
                "@m.xtop.xxdut.xm_stage2_n.msky130_fd_pr__nfet_01v8[gm]",
                "@m.xtop.xxdut.xm_stage2_n.msky130_fd_pr__nfet_01v8[gds]",
                "@m.xtop.xxdut.xm_stage2_n.msky130_fd_pr__nfet_01v8[vth]",
                "@m.xtop.xxdut.xm_stage2_n.msky130_fd_pr__nfet_01v8[vdsat]",
                "@m.xtop.xxdut.xm_stage2_p.msky130_fd_pr__pfet_01v8[gm]",
                "@m.xtop.xxdut.xm_stage2_p.msky130_fd_pr__pfet_01v8[gds]",
                "@m.xtop.xxdut.xm_stage2_p.msky130_fd_pr__pfet_01v8[vth]",
                "@m.xtop.xxdut.xm_stage2_p.msky130_fd_pr__pfet_01v8[vdsat]",
            ]
            op_res = _run_op(
                f"rc_aol_vcm_core_op_{str(v_cm).replace('.', 'p')}",
                Sim(
                    tb=_build_core_op_tb(core, v_cm=v_cm),
                    attrs=[
                        Op(),
                        Save(", ".join(op_save)),
                        h.sim.Literal(".temp 27"),
                        install.include(h.pdk.Corner.TYP),
                    ],
                ),
            )
            ac_res = _run_op(
                f"rc_aol_vcm_core_ac_{str(v_cm).replace('.', 'p')}",
                Sim(
                    tb=_build_core_ac_tb(core, v_cm=v_cm, v_diff=v_diff),
                    attrs=[
                        Ac(sweep=LogSweep(1.0, 1e9, 40)),
                        Save("v(xtop.vout)"),
                        h.sim.Literal(".temp 27"),
                        install.include(h.pdk.Corner.TYP),
                    ],
                ),
            )

            _, vout = extract_ac_trace(ac_res, "v(xtop.vout)")
            aol_vv = abs(complex(np.asarray(vout)[0])) / v_diff
            aol_db = float(20.0 * np.log10(max(aol_vv, 1e-30)))

            op_data = getattr(getattr(op_res.an[0], "op", op_res.an[0]), "data")
            vx_dc = float(op_data["v(xtop.xxdut.vx)"])
            vref_dc = float(op_data["v(xtop.xxdut.vref)"])
            tail1_dc = float(op_data["v(xtop.xxdut.tail1)"])
            vdrv_dc = float(op_data["v(xtop.xxdut.vdrv)"])

            gm_xmp = float(op_data["@m.xtop.xxdut.xxin.xmp.msky130_fd_pr__pfet_01v8[gm]"])
            gds_xmp = float(op_data["@m.xtop.xxdut.xxin.xmp.msky130_fd_pr__pfet_01v8[gds]"])
            vdsat_xmp = float(op_data["v(@m.xtop.xxdut.xxin.xmp.msky130_fd_pr__pfet_01v8[vdsat])"])
            vth_xmp = float(op_data["v(@m.xtop.xxdut.xxin.xmp.msky130_fd_pr__pfet_01v8[vth])"])

            gm_load = float(op_data["@m.xtop.xxdut.xm_load_out.msky130_fd_pr__nfet_01v8[gm]"])
            gds_load = float(op_data["@m.xtop.xxdut.xm_load_out.msky130_fd_pr__nfet_01v8[gds]"])
            vdsat_load = float(op_data["v(@m.xtop.xxdut.xm_load_out.msky130_fd_pr__nfet_01v8[vdsat])"])
            vth_load = float(op_data["v(@m.xtop.xxdut.xm_load_out.msky130_fd_pr__nfet_01v8[vth])"])

            gm_s2n = float(op_data["@m.xtop.xxdut.xm_stage2_n.msky130_fd_pr__nfet_01v8[gm]"])
            gds_s2n = float(op_data["@m.xtop.xxdut.xm_stage2_n.msky130_fd_pr__nfet_01v8[gds]"])
            vdsat_s2n = float(op_data["v(@m.xtop.xxdut.xm_stage2_n.msky130_fd_pr__nfet_01v8[vdsat])"])
            vth_s2n = float(op_data["v(@m.xtop.xxdut.xm_stage2_n.msky130_fd_pr__nfet_01v8[vth])"])

            gm_s2p = float(op_data["@m.xtop.xxdut.xm_stage2_p.msky130_fd_pr__pfet_01v8[gm]"])
            gds_s2p = float(op_data["@m.xtop.xxdut.xm_stage2_p.msky130_fd_pr__pfet_01v8[gds]"])
            vdsat_s2p = float(op_data["v(@m.xtop.xxdut.xm_stage2_p.msky130_fd_pr__pfet_01v8[vdsat])"])
            vth_s2p = float(op_data["v(@m.xtop.xxdut.xm_stage2_p.msky130_fd_pr__pfet_01v8[vth])"])

            a1_est_vv = abs(gm_xmp) / max(abs(gds_xmp) + abs(gds_load), 1e-30)
            a2_est_vv = abs(gm_s2n) / max(abs(gds_s2n) + abs(gds_s2p), 1e-30)

            cases.append(
                {
                    "vcm_V": float(v_cm),
                    "aol_db": aol_db,
                    "aol_vv": float(aol_vv),
                    "vx_V": float(vx_dc),
                    "vref_V": float(vref_dc),
                    "tail1_V": float(tail1_dc),
                    "vdrv_V": float(vdrv_dc),
                    "vin_cm_minus_vx_V": float(v_cm - vx_dc),
                    "vdd_minus_tail1_V": float(1.8 - tail1_dc),
                    "gm_xmp_S": gm_xmp,
                    "gds_xmp_S": gds_xmp,
                    "vth_xmp_V": vth_xmp,
                    "vdsat_xmp_V": vdsat_xmp,
                    "stage1_pmos_margin_V": float((tail1_dc - vx_dc) - vdsat_xmp),
                    "gm_load_S": gm_load,
                    "gds_load_S": gds_load,
                    "vth_load_V": vth_load,
                    "vdsat_load_V": vdsat_load,
                    "load_margin_V": float(vx_dc - vdsat_load),
                    "gm_stage2_n_S": gm_s2n,
                    "gds_stage2_n_S": gds_s2n,
                    "vth_stage2_n_V": vth_s2n,
                    "vdsat_stage2_n_V": vdsat_s2n,
                    "stage2_n_margin_V": float(vdrv_dc - vdsat_s2n),
                    "gm_stage2_p_S": gm_s2p,
                    "gds_stage2_p_S": gds_s2p,
                    "vth_stage2_p_V": vth_s2p,
                    "vdsat_stage2_p_V": vdsat_s2p,
                    "stage2_p_margin_V": float((1.8 - vdrv_dc) - vdsat_s2p),
                    "a1_est_vv": float(a1_est_vv),
                    "a2_est_vv": float(a2_est_vv),
                    "a1a2_est_vv": float(a1_est_vv * a2_est_vv),
                    "a1a2_est_db": float(20.0 * np.log10(max(a1_est_vv * a2_est_vv, 1e-30))),
                }
            )

        aol_vals = [float(case["aol_db"]) for case in cases]
        a1_vals = [float(case["a1_est_vv"]) for case in cases]
        a2_vals = [float(case["a2_est_vv"]) for case in cases]
        aol_db_span = max(aol_vals) - min(aol_vals)
        a1_change_ratio = max(a1_vals) / max(min(a1_vals), 1e-30)
        a2_change_ratio = max(a2_vals) / max(min(a2_vals), 1e-30)
        dominant_change_stage = "stage1" if a1_change_ratio > a2_change_ratio else "stage2"
        payload = {
            "cases": cases,
            "summary": {
                "aol_db_span": float(aol_db_span),
                "a1_change_ratio": float(a1_change_ratio),
                "a2_change_ratio": float(a2_change_ratio),
                "dominant_change_stage": dominant_change_stage,
                "aol_cm_dependence_fail": bool(aol_db_span > 6.0),
                "review_hypothesis_stage1_dominant": bool(dominant_change_stage == "stage1"),
            },
        }
        write_metrics_json(METRICS_PATH, payload)

        self.assertEqual(len(cases), len(vcm_points))
        self.assertGreater(cases[-1]["aol_db"], cases[0]["aol_db"])
        self.assertGreater(cases[-1]["stage1_pmos_margin_V"], cases[0]["stage1_pmos_margin_V"])
        self.assertLessEqual(
            aol_db_span,
            6.0,
            (
                f"AOL varies too strongly with VCM: span={aol_db_span:.2f} dB; "
                f"dominant_change_stage={dominant_change_stage}, "
                f"a1_change_ratio={a1_change_ratio:.2f}, a2_change_ratio={a2_change_ratio:.2f}"
            ),
        )
