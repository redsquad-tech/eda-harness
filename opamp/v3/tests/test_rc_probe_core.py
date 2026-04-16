from __future__ import annotations
import math
from pathlib import Path
from uuid import uuid4

import hdl21 as h
import numpy as np
from hdl21.sim import Ac, LogSweep, Op, Save, Sim
from vlsirtools.spice import ResultFormat, SimOptions

from components import require_sky130_install, run_ngspice_sim
from opamp.v3.common import extract_ac_trace, interp_crossing, interp_value, negative_feedback_phase_trace
from opamp.v3.opamp_core import OpampCoreParams, opamp_core
from opamp.v3.tests._helpers import BaseV3SimTest, build_core_params, build_debug_core_params, reset_metrics_file, write_metrics_json


METRICS_PATH = Path(__file__).with_name("rc_probe_metrics.json")


def _debug_params() -> OpampCoreParams:
    return build_debug_core_params()


def _ac_params() -> OpampCoreParams:
    return build_core_params()


def _build_follower_tb(dut, *, vin: float, load_mode: str = "none", load_uA: float = 0.0):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=vin)(p=vinp, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn)
        rl = h.Res(r=1e6)(p=vout, n=VSS)
        cl = h.Cap(c=1e-12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, VDD=vdd, VSS=VSS)
        # External load semantics:
        # - source: inject current into VOUT, DUT must sink it to hold low.
        # - sink: draw current from VOUT, DUT must source it to hold high.
        if load_mode == "source":
            iload = h.Idc(dc=load_uA * 1e-6)(p=vdd, n=vout)
        elif load_mode == "sink":
            iload = h.Idc(dc=load_uA * 1e-6)(p=vout, n=VSS)

    return Tb


def _build_direct_gain_ac_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.4, ac=50e-6)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=0.4, ac=-50e-6)(p=vinn_sig, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Tb


def _build_follower_ac_tb(dut):
    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=1.8)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.9, ac=1.0)(p=vinp_sig, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e12)(p=vout, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VOUT=vout, EN=en, VDD=vdd_sig, VSS=VSS)

    return Tb


def _op_case(dut, name: str, *, vin: float, load_mode: str = "none", load_uA: float = 0.0) -> dict[str, float | str]:
    install = require_sky130_install()
    sim = Sim(tb=_build_follower_tb(dut, vin=vin, load_mode=load_mode, load_uA=load_uA), attrs=[Op(), Save("all"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    res = run_ngspice_sim(sim, SimOptions(fmt="sim_data"), rundir=f"./tmp/rc_probe_{uuid4().hex[:8]}")
    d = res.an[0].data
    vdd = float(d["v(xtop.vdd)"])
    vout = float(d["v(xtop.vout)"])
    vdrv = float(d.get("v(xtop.xxdut.vout_int)", d["v(xtop.vout)"]))
    vgn = float(d.get("v(xtop.xxdut.vgn)", 0.0))
    vgp = float(d.get("v(xtop.xxdut.vgp)", vdd))
    vx = float(d["v(xtop.xxdut.vx)"])
    vref = float(d.get("v(xtop.xxdut.vref)", d.get("v(xtop.xxdut.vref1)", 0.0)))
    ibias2 = float(d.get("v(xtop.xxdut.vbp2)", 0.0))
    i_out_p = float(d.get("i(v.xtop.xxdut.vvprobe_outp)", 0.0))
    i_out_n = float(d.get("i(v.xtop.xxdut.vvprobe_outn)", 0.0))
    return {
        "case": name,
        "vin_V": float(vin),
        "load_mode": load_mode,
        "load_uA": float(load_uA),
        "vx_V": vx,
        "vref_V": vref,
        "ibias2_V": ibias2,
        "vdrv_V": vdrv,
        "vgn_V": vgn,
        "vgp_V": vgp,
        "gate_spread_V": vgn - vgp,
        "gate_avg_V": 0.5 * (vgp + vgn),
        "vout_V": vout,
        "abs_error_V": abs(vout - float(vin)),
        "stage2_n_vgs_V": vx,
        "stage2_n_vds_V": vdrv,
        "stage2_p_vsg_V": vdd - ibias2 if ibias2 else float("nan"),
        "stage2_p_vsd_V": vdd - vdrv,
        "out_p_vsg_V": vdd - vgp,
        "out_p_vsd_V": vdd - vout,
        "out_n_vgs_V": vgn,
        "out_n_vds_V": vout,
        "i_stage2_p_A": float(d.get("i(v.xtop.xxdut.vvprobe_s2p)", 0.0)),
        "i_stage2_n_A": float(d.get("i(v.xtop.xxdut.vvprobe_s2n)", 0.0)),
        "i_out_p_A": i_out_p,
        "i_out_n_A": i_out_n,
        "quiescent_overlap_A": abs(i_out_p) + abs(i_out_n),
    }


def _open_loop_metrics(dut) -> dict[str, float | bool]:
    install = require_sky130_install()
    ac_sim = Sim(tb=_build_direct_gain_ac_tb(dut), attrs=[Ac(sweep=LogSweep(1.0, 1e9, 40)), Save("v(xtop.vout)"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    ac_res = run_ngspice_sim(ac_sim, SimOptions(fmt=ResultFormat.SIM_DATA), rundir=f"./tmp/rc_probe_ol_{uuid4().hex[:8]}")
    _, vout_amp = extract_ac_trace(ac_res, "v(xtop.vout)")
    low_freq_vout = complex(np.asarray(vout_amp)[0])
    direct_gain_vv = abs(low_freq_vout) / 100e-6
    direct_gain_db = 20.0 * math.log10(max(direct_gain_vv, 1e-30))

    acf_sim = Sim(tb=_build_follower_ac_tb(dut), attrs=[Ac(sweep=LogSweep(1.0, 1e9, 40)), Save("v(xtop.vout), v(xtop.vinp_sig)"), h.sim.Literal(".temp 27"), install.include(h.pdk.Corner.TYP)])
    acf_res = run_ngspice_sim(acf_sim, SimOptions(fmt=ResultFormat.SIM_DATA), rundir=f"./tmp/rc_probe_cl_{uuid4().hex[:8]}")
    freq, vout_amp = extract_ac_trace(acf_res, "v(xtop.vout)")
    _, vin_amp = extract_ac_trace(acf_res, "v(xtop.vinp_sig)")
    freq = np.asarray(freq, dtype=float)
    closed_loop_gain = np.asarray(vout_amp) / np.where(np.abs(np.asarray(vin_amp)) > 1e-30, np.asarray(vin_amp), 1e-30 + 0j)
    loop_gain = closed_loop_gain / np.where(np.abs(1.0 - closed_loop_gain) > 1e-30, 1.0 - closed_loop_gain, 1e-30 + 0j)
    mag = np.abs(loop_gain)
    phase_deg, _ = negative_feedback_phase_trace(loop_gain)
    gbw_hz, _ = interp_crossing(freq, mag, 1.0)
    phase_margin_deg = float("nan")
    if math.isfinite(gbw_hz):
        phase_at_unity = interp_value(freq, phase_deg, gbw_hz)
        if math.isfinite(phase_at_unity):
            phase_margin_deg = 180.0 + phase_at_unity
    return {
        "aol_db": direct_gain_db,
        "gbw_hz": float(gbw_hz),
        "phase_margin_deg": float(phase_margin_deg),
        "ac_fixture_ok": True,
    }


class TestRcProbeCore(BaseV3SimTest):
    def test_probe_current_rc_core(self):
        reset_metrics_file(METRICS_PATH)
        dut = opamp_core(_debug_params())
        ac_dut = opamp_core(_ac_params())
        payload = {"open_loop": _open_loop_metrics(ac_dut)}
        payload["cases"] = [
            _op_case(dut, "follower_zero", vin=0.0),
            _op_case(dut, "follower_mid", vin=0.9),
            _op_case(dut, "swing_low_target", vin=0.1),
            _op_case(dut, "swing_high_target", vin=1.6),
            _op_case(dut, "drive_source_20u", vin=0.9, load_mode="source", load_uA=20.0),
            _op_case(dut, "drive_sink_20u", vin=0.9, load_mode="sink", load_uA=20.0),
        ]
        write_metrics_json(METRICS_PATH, payload)
        self.assertEqual(len(payload["cases"]), 6)
