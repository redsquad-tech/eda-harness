import json
from uuid import uuid4
from dataclasses import asdict, dataclass
from pathlib import Path

import hdl21 as h
import numpy as np
from hdl21.primitives import MosVth
from hdl21.sim import Ac, LogSweep, Op, Save, Sim
from vlsirtools.spice import ResultFormat

from .common import (
    default_ngspice_options,
    extract_ac_trace,
    init_sky130_install,
    interp_crossing,
    interp_value,
    make_test_result,
    negative_feedback_phase_trace,
    op_scalar,
    run_ngspice_sim,
)
from ..opamp import (
    NeuronOaParams,
    OutputStageParams,
    classab_output_stage,
    compile_for_sky130,
    neuron_core_oa_sky130,
)


@dataclass(frozen=True)
class V4OpenLoopTbParams:
    vdd: float = 1.8
    v_cm: float = 0.9
    iref_uA: float = 0.25
    c_load: float = 1e-12
    r_load: float = 1e9
    f_start: float = 1.0
    f_stop: float = 1e9
    npts: int = 200
    temp_c: float = 27.0


@dataclass(frozen=True)
class V4SupplyCurrentTbParams:
    vdd: float = 1.8
    v_cm: float = 0.9
    iref_uA: float = 0.25
    c_load: float = 1e-12
    r_load: float = 1e9
    temp_c: float = 27.0
    en_v: float = 1.8
    az_v: float = 0.0
    inf_v: float = 1.8


@dataclass(frozen=True)
class V4OutputDriveTbParams:
    vdd: float = 1.8
    vin_target: float = 0.9
    iref_uA: float = 0.25
    c_load: float = 1e-12
    r_load: float = 1e9
    temp_c: float = 27.0
    load_current_uA: float = 20.0
    direction: str = "source"


@dataclass(frozen=True)
class V4DebugSweepParams:
    vdd: float = 1.8
    v_cm: float = 0.9
    iref_uA: float = 0.25
    c_load: float = 1e-12
    r_load: float = 1e9
    temp_c: float = 27.0
    en_v: float = 1.8
    az_v: float = 0.0
    inf_v: float = 1.8


@dataclass(frozen=True)
class V4OutputStageDebugParams:
    vdd: float = 1.8
    temp_c: float = 27.0
    vgp_start: float = 0.25
    vgp_stop: float = 0.55
    vgp_step: float = 0.05
    vgn_start: float = 0.20
    vgn_stop: float = 0.40
    vgn_step: float = 0.05
    vout_bias: float = 0.9
    r_load: float = 1e9


def _build_follower_ac_tb(dut_params: NeuronOaParams, tb: V4OpenLoopTbParams, *, corner) -> Sim:
    import sky130_hdl21 as sky130

    init_sky130_install()
    dut = h.elaborate(neuron_core_oa_sky130(dut_params))
    compile_for_sky130(dut)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)

        vvdd = h.Vdc(dc=tb.vdd)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=tb.v_cm, ac=1.0)(p=vinp_sig, n=VSS)
        ven = h.Vdc(dc=tb.vdd)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=tb.vdd)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=0.0)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=tb.iref_uA * 1e-6)(p=iref, n=VSS)

        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=tb.c_load)(p=vout, n=VSS)
        rload = h.Res(r=tb.r_load)(p=vout, n=VSS)

        xdut = dut(
            avdd1p2=avdd,
            agnd=VSS,
            vinp=vinp_sig,
            vinn=vinn_sig,
            vout=vout,
            in0u25_oa=iref,
            vbase=vbase,
            vfeed=vfeed,
            d_en_oa=d_en_oa,
            d_az_oa=d_az_oa,
            d_inf_oa=d_inf_oa,
            vtest=vtest,
            d_treset_oa=d_treset_oa,
            d_tcki=d_tcki,
            d_tcko=d_tcko,
            d_tdi=d_tdi,
            d_tdo=d_tdo,
        )

    return Sim(
        tb=Tb,
        attrs=[
            Ac(sweep=LogSweep(tb.f_start, tb.f_stop, tb.npts)),
            Save("v(xtop.vout), v(xtop.vinp_sig)"),
            h.sim.Literal(f".temp {tb.temp_c}"),
            sky130.install.include(corner),
        ],
    )


def _build_follower_op_tb(dut_params: NeuronOaParams, tb: V4OpenLoopTbParams, *, corner) -> Sim:
    import sky130_hdl21 as sky130

    init_sky130_install()
    dut = h.elaborate(neuron_core_oa_sky130(dut_params))
    compile_for_sky130(dut)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)

        vvdd = h.Vdc(dc=tb.vdd)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=tb.v_cm)(p=vinp_sig, n=VSS)
        ven = h.Vdc(dc=tb.vdd)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=tb.vdd)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=0.0)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=tb.iref_uA * 1e-6)(p=iref, n=VSS)

        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=tb.c_load)(p=vout, n=VSS)
        rload = h.Res(r=tb.r_load)(p=vout, n=VSS)

        xdut = dut(
            avdd1p2=avdd,
            agnd=VSS,
            vinp=vinp_sig,
            vinn=vinn_sig,
            vout=vout,
            in0u25_oa=iref,
            vbase=vbase,
            vfeed=vfeed,
            d_en_oa=d_en_oa,
            d_az_oa=d_az_oa,
            d_inf_oa=d_inf_oa,
            vtest=vtest,
            d_treset_oa=d_treset_oa,
            d_tcki=d_tcki,
            d_tcko=d_tcko,
            d_tdi=d_tdi,
            d_tdo=d_tdo,
        )

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save("i(v.xtop.vvvdd), v(xtop.vout), v(xtop.vinp_sig)"),
            h.sim.Literal(f".temp {tb.temp_c}"),
            sky130.install.include(corner),
        ],
    )


def _build_supply_current_op_tb(
    dut_params: NeuronOaParams, tb: V4SupplyCurrentTbParams, *, corner
) -> Sim:
    import sky130_hdl21 as sky130

    init_sky130_install()
    dut = h.elaborate(neuron_core_oa_sky130(dut_params))
    compile_for_sky130(dut)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)

        vvdd = h.Vdc(dc=tb.vdd)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=tb.v_cm)(p=vinp_sig, n=VSS)
        ven = h.Vdc(dc=tb.en_v)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=tb.az_v)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=tb.inf_v)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=0.0)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=tb.iref_uA * 1e-6)(p=iref, n=VSS)

        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=tb.c_load)(p=vout, n=VSS)
        rload = h.Res(r=tb.r_load)(p=vout, n=VSS)

        xdut = dut(
            avdd1p2=avdd,
            agnd=VSS,
            vinp=vinp_sig,
            vinn=vinn_sig,
            vout=vout,
            in0u25_oa=iref,
            vbase=vbase,
            vfeed=vfeed,
            d_en_oa=d_en_oa,
            d_az_oa=d_az_oa,
            d_inf_oa=d_inf_oa,
            vtest=vtest,
            d_treset_oa=d_treset_oa,
            d_tcki=d_tcki,
            d_tcko=d_tcko,
            d_tdi=d_tdi,
            d_tdo=d_tdo,
        )

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save("i(v.xtop.vvvdd), v(xtop.vout)"),
            h.sim.Literal(f".temp {tb.temp_c}"),
            sky130.install.include(corner),
        ],
    )


def _build_output_drive_op_tb(
    dut_params: NeuronOaParams, tb: V4OutputDriveTbParams, *, corner
) -> Sim:
    import sky130_hdl21 as sky130

    init_sky130_install()
    dut = h.elaborate(neuron_core_oa_sky130(dut_params))
    compile_for_sky130(dut)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)

        vvdd = h.Vdc(dc=tb.vdd)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=tb.vin_target)(p=vinp_sig, n=VSS)
        ven = h.Vdc(dc=tb.vdd)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=tb.vdd)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=0.0)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=tb.iref_uA * 1e-6)(p=iref, n=VSS)

        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=tb.c_load)(p=vout, n=VSS)
        rload = h.Res(r=tb.r_load)(p=vout, n=VSS)

        if tb.direction == "source":
            iload = h.Idc(dc=tb.load_current_uA * 1e-6)(p=vout, n=VSS)
        elif tb.direction == "sink":
            iload = h.Idc(dc=tb.load_current_uA * 1e-6)(p=avdd, n=vout)
        else:
            raise ValueError(f"Unknown output-drive direction {tb.direction!r}")

        xdut = dut(
            avdd1p2=avdd,
            agnd=VSS,
            vinp=vinp_sig,
            vinn=vinn_sig,
            vout=vout,
            in0u25_oa=iref,
            vbase=vbase,
            vfeed=vfeed,
            d_en_oa=d_en_oa,
            d_az_oa=d_az_oa,
            d_inf_oa=d_inf_oa,
            vtest=vtest,
            d_treset_oa=d_treset_oa,
            d_tcki=d_tcki,
            d_tcko=d_tcko,
            d_tdi=d_tdi,
            d_tdo=d_tdo,
        )

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save("i(v.xtop.vvvdd), v(xtop.vout), v(xtop.vinp_sig)"),
            h.sim.Literal(f".temp {tb.temp_c}"),
            sky130.install.include(corner),
        ],
    )


def _build_debug_op_tb(
    dut_params: NeuronOaParams,
    tb: V4DebugSweepParams,
    *,
    vinp_v: float,
    vinn_v: float,
    corner,
    feedback_to: str = "none",
) -> Sim:
    import sky130_hdl21 as sky130

    init_sky130_install()
    dut = h.elaborate(neuron_core_oa_sky130(dut_params))
    compile_for_sky130(dut)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)

        vvdd = h.Vdc(dc=tb.vdd)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=vinp_v)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=vinn_v)(p=vinn_sig, n=VSS)
        ven = h.Vdc(dc=tb.en_v)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=tb.az_v)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=tb.inf_v)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=0.0)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=tb.iref_uA * 1e-6)(p=iref, n=VSS)

        cload = h.Cap(c=tb.c_load)(p=vout, n=VSS)
        rload = h.Res(r=tb.r_load)(p=vout, n=VSS)

        if feedback_to == "vinn":
            rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        elif feedback_to == "vinp":
            rfb = h.Res(r=1.0)(p=vout, n=vinp_sig)
        elif feedback_to != "none":
            raise ValueError(f"Unknown feedback_to={feedback_to!r}")

        xdut = dut(
            avdd1p2=avdd,
            agnd=VSS,
            vinp=vinp_sig,
            vinn=vinn_sig,
            vout=vout,
            in0u25_oa=iref,
            vbase=vbase,
            vfeed=vfeed,
            d_en_oa=d_en_oa,
            d_az_oa=d_az_oa,
            d_inf_oa=d_inf_oa,
            vtest=vtest,
            d_treset_oa=d_treset_oa,
            d_tcki=d_tcki,
            d_tcko=d_tcko,
            d_tdi=d_tdi,
            d_tdo=d_tdo,
        )

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save(
                "v(xtop.vinp_sig), v(xtop.vinn_sig), v(xtop.vout), "
                "v(xtop.xxdut.vout_int), v(xtop.xxdut.drv_p), v(xtop.xxdut.drv_n), "
                "v(xtop.xxdut.xfrontend.pfold_p), v(xtop.xxdut.xfrontend.pfold_n), "
                "v(xtop.xxdut.xfrontend.nfold_p), v(xtop.xxdut.xfrontend.nfold_n), "
                "v(xtop.xxdut.vgp), v(xtop.xxdut.vgn), v(xtop.xxdut.vbp_tail), "
                "v(xtop.xxdut.vbp_cas), v(xtop.xxdut.vbn_tail), v(xtop.xxdut.vbn_cas), "
                "i(v.xtop.vvvdd)"
            ),
            h.sim.Literal(f".temp {tb.temp_c}"),
            sky130.install.include(corner),
        ],
    )


def _build_output_stage_debug_tb(
    params: OutputStageParams,
    tb: V4OutputStageDebugParams,
    *,
    vgp_v: float,
    vgn_v: float,
    corner,
) -> Sim:
    import sky130_hdl21 as sky130

    init_sky130_install()
    dut = h.elaborate(classab_output_stage(params))
    compile_for_sky130(dut)

    @h.module
    class Tb:
        VSS = h.Port()
        avdd, vgp, vgn, vout = h.Signals(4)
        vout_bias = h.Signal()

        vvdd = h.Vdc(dc=tb.vdd)(p=avdd, n=VSS)
        vvgp = h.Vdc(dc=vgp_v)(p=vgp, n=VSS)
        vvgn = h.Vdc(dc=vgn_v)(p=vgn, n=VSS)
        vvout_bias = h.Vdc(dc=tb.vout_bias)(p=vout_bias, n=VSS)
        rbias = h.Res(r=tb.r_load)(p=vout, n=vout_bias)

        xdut = dut(
            vgp=vgp,
            vgn=vgn,
            vout=vout,
            avdd=avdd,
            agnd=VSS,
        )

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save(
                "v(xtop.vgp), v(xtop.vgn), v(xtop.vout), "
                "v(xtop.xxdut.psrc), v(xtop.xxdut.nsrc), i(v.xtop.vvvdd)"
            ),
            h.sim.Literal(f".temp {tb.temp_c}"),
            sky130.install.include(corner),
        ],
    )


def _build_raw_push_pull_output_tb(
    params: OutputStageParams,
    tb: V4OutputStageDebugParams,
    *,
    vgp_v: float,
    vgn_v: float,
    corner,
) -> Sim:
    import sky130_hdl21 as sky130

    init_sky130_install()

    @h.module
    class RawPushPull:
        vgp = h.Input()
        vgn = h.Input()
        vout = h.Output()
        avdd = h.Inout()
        agnd = h.Inout()
        ccp_mid, ccn_mid = h.Signals(2)

        mp_out = h.Pmos(
            w=params.wp_out,
            l=params.lp_out,
            npar=params.npar_p,
            vth=MosVth.STD,
            family=h.MosFamily.CORE,
        )(d=vout, g=vgp, s=avdd, b=avdd)
        mn_out = h.Nmos(
            w=params.wn_out,
            l=params.ln_out,
            npar=params.npar_n,
            vth=MosVth.STD,
            family=h.MosFamily.CORE,
        )(d=vout, g=vgn, s=agnd, b=agnd)
        rcp = h.Res(r=params.rc)(p=vgp, n=ccp_mid)
        ccp = h.Cap(c=params.cc)(p=ccp_mid, n=vout)
        rcn = h.Res(r=params.rc)(p=vgn, n=ccn_mid)
        ccn = h.Cap(c=params.cc)(p=ccn_mid, n=vout)

    dut = h.elaborate(RawPushPull)
    compile_for_sky130(dut)

    @h.module
    class Tb:
        VSS = h.Port()
        avdd, vgp, vgn, vout = h.Signals(4)
        vout_bias = h.Signal()

        vvdd = h.Vdc(dc=tb.vdd)(p=avdd, n=VSS)
        vvgp = h.Vdc(dc=vgp_v)(p=vgp, n=VSS)
        vvgn = h.Vdc(dc=vgn_v)(p=vgn, n=VSS)
        vvout_bias = h.Vdc(dc=tb.vout_bias)(p=vout_bias, n=VSS)
        rbias = h.Res(r=tb.r_load)(p=vout, n=vout_bias)

        xdut = dut(
            vgp=vgp,
            vgn=vgn,
            vout=vout,
            avdd=avdd,
            agnd=VSS,
        )

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            Save("v(xtop.vgp), v(xtop.vgn), v(xtop.vout), i(v.xtop.vvvdd)"),
            h.sim.Literal(f".temp {tb.temp_c}"),
            sky130.install.include(corner),
        ],
    )


def _interp_phase_crossing(freq: np.ndarray, phase_deg: np.ndarray, target_deg: float):
    for idx in range(1, len(phase_deg)):
        p0 = float(phase_deg[idx - 1])
        p1 = float(phase_deg[idx])
        if (p0 - target_deg) == 0.0:
            return float(freq[idx - 1]), idx - 1
        if (p0 - target_deg) * (p1 - target_deg) <= 0.0 and p1 != p0:
            frac = (target_deg - p0) / (p1 - p0)
            x = float(freq[idx - 1] + frac * (freq[idx] - freq[idx - 1]))
            return x, idx
    return float("nan"), None


def _run_debug_op_point(
    dut_params: NeuronOaParams,
    tb: V4DebugSweepParams,
    *,
    vinp_v: float,
    vinn_v: float,
    corner,
    label: str,
    feedback_to: str = "none",
):
    op_result = run_ngspice_sim(
        _build_debug_op_tb(
            dut_params,
            tb,
            vinp_v=vinp_v,
            vinn_v=vinn_v,
            corner=corner,
            feedback_to=feedback_to,
        ),
        default_ngspice_options(f"opamp_v4_debug_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    data = op_result.an[0].data
    return {
        "vinp_V": op_scalar(op_result, "v(xtop.vinp_sig)"),
        "vinn_V": op_scalar(op_result, "v(xtop.vinn_sig)"),
        "vout_V": op_scalar(op_result, "v(xtop.vout)"),
        "vout_int_V": op_scalar(op_result, "v(xtop.xxdut.vout_int)"),
        "drv_p_V": op_scalar(op_result, "v(xtop.xxdut.drv_p)"),
        "drv_n_V": op_scalar(op_result, "v(xtop.xxdut.drv_n)"),
        "pfold_p_V": op_scalar(op_result, "v(xtop.xxdut.xfrontend.pfold_p)"),
        "pfold_n_V": op_scalar(op_result, "v(xtop.xxdut.xfrontend.pfold_n)"),
        "nfold_p_V": op_scalar(op_result, "v(xtop.xxdut.xfrontend.nfold_p)"),
        "nfold_n_V": op_scalar(op_result, "v(xtop.xxdut.xfrontend.nfold_n)"),
        "vgp_V": op_scalar(op_result, "v(xtop.xxdut.vgp)"),
        "vgn_V": op_scalar(op_result, "v(xtop.xxdut.vgn)"),
        "vbp_tail_V": op_scalar(op_result, "v(xtop.xxdut.vbp_tail)"),
        "vbp_cas_V": op_scalar(op_result, "v(xtop.xxdut.vbp_cas)"),
        "vbn_tail_V": op_scalar(op_result, "v(xtop.xxdut.vbn_tail)"),
        "vbn_cas_V": op_scalar(op_result, "v(xtop.xxdut.vbn_cas)"),
        "iq_uA": 1e6 * abs(float(data["i(v.xtop.vvvdd)"])),
    }


def _run_output_stage_debug_point(
    tb: V4OutputStageDebugParams,
    *,
    vgp_v: float,
    vgn_v: float,
    corner,
    label: str,
    output_params: OutputStageParams | None = None,
):
    output_params = output_params or OutputStageParams()
    op_result = run_ngspice_sim(
        _build_output_stage_debug_tb(
            output_params,
            tb,
            vgp_v=vgp_v,
            vgn_v=vgn_v,
            corner=corner,
        ),
        default_ngspice_options(f"opamp_v4_outstage_debug_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    data = op_result.an[0].data
    return {
        "vgp_V": op_scalar(op_result, "v(xtop.vgp)"),
        "vgn_V": op_scalar(op_result, "v(xtop.vgn)"),
        "vout_V": op_scalar(op_result, "v(xtop.vout)"),
        "psrc_V": op_scalar(op_result, "v(xtop.xxdut.psrc)"),
        "nsrc_V": op_scalar(op_result, "v(xtop.xxdut.nsrc)"),
        "iq_uA": 1e6 * abs(float(data["i(v.xtop.vvvdd)"])),
    }


def _run_raw_push_pull_debug_point(
    tb: V4OutputStageDebugParams,
    *,
    vgp_v: float,
    vgn_v: float,
    corner,
    label: str,
    output_params: OutputStageParams | None = None,
):
    output_params = output_params or OutputStageParams()
    op_result = run_ngspice_sim(
        _build_raw_push_pull_output_tb(
            output_params,
            tb,
            vgp_v=vgp_v,
            vgn_v=vgn_v,
            corner=corner,
        ),
        default_ngspice_options(f"opamp_v4_rawpushpull_debug_{label}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
    )
    data = op_result.an[0].data
    return {
        "vgp_V": op_scalar(op_result, "v(xtop.vgp)"),
        "vgn_V": op_scalar(op_result, "v(xtop.vgn)"),
        "vout_V": op_scalar(op_result, "v(xtop.vout)"),
        "iq_uA": 1e6 * abs(float(data["i(v.xtop.vvvdd)"])),
    }


def _slope(rows: list[dict], x_key: str, y_key: str) -> float:
    if len(rows) < 2:
        return float("nan")
    x0 = float(rows[0][x_key])
    x1 = float(rows[-1][x_key])
    y0 = float(rows[0][y_key])
    y1 = float(rows[-1][y_key])
    dx = x1 - x0
    if abs(dx) < 1e-30:
        return float("nan")
    return (y1 - y0) / dx


def _sign_label(value: float) -> str:
    if not np.isfinite(value):
        return "nan"
    if value > 1e-3:
        return "positive"
    if value < -1e-3:
        return "negative"
    return "flat"


def run_open_loop_test(
    dut_params: NeuronOaParams | None = None,
    tb_params: V4OpenLoopTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or NeuronOaParams()
    tb = tb_params or V4OpenLoopTbParams()

    ac_result = run_ngspice_sim(
        _build_follower_ac_tb(dut_params, tb, corner=corner),
        default_ngspice_options("opamp_v4_open_loop_ac", fmt=ResultFormat.SIM_DATA),
    )
    op_result = run_ngspice_sim(
        _build_follower_op_tb(dut_params, tb, corner=corner),
        default_ngspice_options("opamp_v4_open_loop_op", fmt=ResultFormat.SIM_DATA),
    )

    freq, vout_amp = extract_ac_trace(ac_result, "v(xtop.vout)")
    _, vin_amp = extract_ac_trace(ac_result, "v(xtop.vinp_sig)")
    freq = np.asarray(freq, dtype=float)
    vout_amp = np.asarray(vout_amp)
    vin_amp = np.asarray(vin_amp)
    closed_loop_gain = vout_amp / np.where(np.abs(vin_amp) > 1e-30, vin_amp, 1e-30 + 0j)
    loop_gain = closed_loop_gain / np.where(np.abs(1.0 - closed_loop_gain) > 1e-30, 1.0 - closed_loop_gain, 1e-30 + 0j)
    mag = np.abs(loop_gain)
    mag_db = 20.0 * np.log10(np.maximum(mag, 1e-30))
    phase_deg, low_freq_phase_deg_raw = negative_feedback_phase_trace(loop_gain)
    aol_db = float(mag_db[0]) if len(mag_db) else float("nan")
    gbw_hz, _ = interp_crossing(freq, mag, 1.0)
    phase_margin_deg = float("nan")
    phase_at_unity_deg_raw = float("nan")
    if np.isfinite(gbw_hz):
        phase_at_unity_deg_raw = interp_value(freq, phase_deg, gbw_hz)
        if np.isfinite(phase_at_unity_deg_raw):
            phase_margin_deg = 180.0 + phase_at_unity_deg_raw
    phase_cross_hz, _ = _interp_phase_crossing(freq, phase_deg, -180.0)
    gain_margin_db = float("nan")
    if np.isfinite(phase_cross_hz):
        mag_at_phase_cross = interp_value(freq, mag_db, phase_cross_hz)
        if np.isfinite(mag_at_phase_cross):
            gain_margin_db = -float(mag_at_phase_cross)

    return make_test_result(
        component="opamp_v4",
        category="char",
        purpose="open_loop",
        metrics={
            "aol_db": aol_db,
            "gbw_hz": float(gbw_hz),
            "phase_margin_deg": float(phase_margin_deg),
            "gain_margin_db": float(gain_margin_db),
            "phase_at_unity_deg_raw": float(phase_at_unity_deg_raw),
            "low_freq_phase_deg_raw": float(low_freq_phase_deg_raw),
            "iq_uA": 1e6 * abs(op_scalar(op_result, "i(v.xtop.vvvdd)")),
            "vout_dc": op_scalar(op_result, "v(xtop.vout)"),
        },
    )


def run_supply_current_test(
    dut_params: NeuronOaParams | None = None,
    tb_params: V4SupplyCurrentTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or NeuronOaParams()
    tb = tb_params or V4SupplyCurrentTbParams()
    op_result = run_ngspice_sim(
        _build_supply_current_op_tb(dut_params, tb, corner=corner),
        default_ngspice_options("opamp_v4_supply_current_op", fmt=ResultFormat.SIM_DATA),
    )
    return make_test_result(
        component="opamp_v4",
        category="char",
        purpose="supply_current",
        metrics={
            "iq_uA": 1e6 * abs(op_scalar(op_result, "i(v.xtop.vvvdd)")),
            "vout_dc": op_scalar(op_result, "v(xtop.vout)"),
            "en_v": tb.en_v,
            "az_v": tb.az_v,
            "inf_v": tb.inf_v,
            "vdd": tb.vdd,
            "temp_c": tb.temp_c,
        },
    )


def run_output_drive_test(
    dut_params: NeuronOaParams | None = None,
    tb_params: V4OutputDriveTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or NeuronOaParams()
    tb = tb_params or V4OutputDriveTbParams()
    op_result = run_ngspice_sim(
        _build_output_drive_op_tb(dut_params, tb, corner=corner),
        default_ngspice_options(f"opamp_v4_output_drive_{tb.direction}", fmt=ResultFormat.SIM_DATA),
    )
    return make_test_result(
        component="opamp_v4",
        category="char",
        purpose=f"output_drive_{tb.direction}",
        metrics={
            "vout_dc": op_scalar(op_result, "v(xtop.vout)"),
            "vin_target": tb.vin_target,
            "load_current_uA": tb.load_current_uA,
            "direction": tb.direction,
            "iq_uA": 1e6 * abs(op_scalar(op_result, "i(v.xtop.vvvdd)")),
        },
    )


def run_cl_load_sweep(
    dut_params: NeuronOaParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    vdd: float = 1.8,
    temp_c: float = 27.0,
    loads=(0.0, 1e-12, 2e-12),
):
    results = []
    for c_load in loads:
        tb = V4OpenLoopTbParams(vdd=vdd, temp_c=temp_c, c_load=c_load)
        res = run_open_loop_test(dut_params=dut_params, tb_params=tb, corner=corner)
        entry = dict(res["metrics"])
        entry["c_load_f"] = c_load
        results.append(entry)
    return {
        "component": "opamp_v4",
        "category": "char",
        "purpose": "cl_sweep",
        "metrics": results,
    }


def run_open_loop_pvt_matrix(
    dut_params: NeuronOaParams | None = None,
    *,
    vdds=(1.6, 1.8, 1.98),
    temps=(-40.0, 27.0, 125.0),
    corners=(h.pdk.Corner.TYP, h.pdk.Corner.FAST, h.pdk.Corner.SLOW),
    f_start: float = 1.0,
    f_stop: float = 1e8,
    npts: int = 80,
):
    results = []
    for corner in corners:
        for vdd in vdds:
            for temp_c in temps:
                tb = V4OpenLoopTbParams(
                    vdd=vdd,
                    temp_c=temp_c,
                    f_start=f_start,
                    f_stop=f_stop,
                    npts=npts,
                )
                res = run_open_loop_test(dut_params=dut_params, tb_params=tb, corner=corner)
                entry = dict(res["metrics"])
                entry["corner"] = corner.name
                entry["vdd"] = vdd
                entry["temp_c"] = temp_c
                results.append(entry)
    return {
        "component": "opamp_v4",
        "category": "char",
        "purpose": "open_loop_pvt",
        "metrics": results,
    }


def run_spec_compliance(
    dut_params: NeuronOaParams | None = None,
    *,
    output_dir: Path | None = None,
):
    output_dir = output_dir or Path(__file__).resolve().parent
    nominal_open_loop = run_open_loop_test(dut_params=dut_params)
    enabled_current = run_supply_current_test(
        dut_params=dut_params,
        tb_params=V4SupplyCurrentTbParams(en_v=1.8, az_v=0.0, inf_v=1.8),
    )
    disabled_current = run_supply_current_test(
        dut_params=dut_params,
        tb_params=V4SupplyCurrentTbParams(en_v=0.0, az_v=0.0, inf_v=0.0),
    )
    output_drive_high = run_output_drive_test(
        dut_params=dut_params,
        tb_params=V4OutputDriveTbParams(vin_target=1.6, load_current_uA=20.0, direction="source"),
    )
    output_drive_low = run_output_drive_test(
        dut_params=dut_params,
        tb_params=V4OutputDriveTbParams(vin_target=0.1, load_current_uA=20.0, direction="sink"),
    )
    cl_sweep = run_cl_load_sweep(dut_params=dut_params)
    pvt_typ = run_open_loop_pvt_matrix(
        dut_params=dut_params,
        corners=(h.pdk.Corner.TYP,),
    )
    pvt_ffss_nom = run_open_loop_pvt_matrix(
        dut_params=dut_params,
        vdds=(1.8,),
        temps=(27.0,),
        corners=(h.pdk.Corner.FAST, h.pdk.Corner.SLOW),
    )

    payload = {
        "nominal_open_loop": nominal_open_loop["metrics"],
        "enabled_current": enabled_current["metrics"],
        "disabled_current": disabled_current["metrics"],
        "output_drive_high": output_drive_high["metrics"],
        "output_drive_low": output_drive_low["metrics"],
        "cl_sweep": cl_sweep["metrics"],
        "pvt_open_loop": pvt_typ["metrics"] + pvt_ffss_nom["metrics"],
        "tb_defaults": {
            "open_loop": asdict(V4OpenLoopTbParams()),
            "supply_current": asdict(V4SupplyCurrentTbParams()),
            "output_drive": asdict(V4OutputDriveTbParams()),
        },
    }
    json_path = output_dir / "spec_compliance_v4.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def run_input_node_polarity_sweep(
    dut_params: NeuronOaParams | None = None,
    tb_params: V4DebugSweepParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sweep_input: str = "vinp",
    values=(0.7, 0.8, 0.9, 1.0, 1.1),
):
    dut_params = dut_params or NeuronOaParams()
    tb = tb_params or V4DebugSweepParams()
    rows = []
    for idx, value in enumerate(values):
        vinp_v = float(value) if sweep_input == "vinp" else tb.v_cm
        vinn_v = float(value) if sweep_input == "vinn" else tb.v_cm
        rows.append(
            _run_debug_op_point(
                dut_params,
                tb,
                vinp_v=vinp_v,
                vinn_v=vinn_v,
                corner=corner,
                label=f"{sweep_input}_{idx}",
                feedback_to="none",
            )
        )
    x_key = "vinp_V" if sweep_input == "vinp" else "vinn_V"
    watched = ["drv_p_V", "drv_n_V", "vgp_V", "vgn_V", "vout_int_V", "vout_V", "iq_uA"]
    slopes = {key: _slope(rows, x_key, key) for key in watched}
    summary = {}
    for key, value in slopes.items():
        name = key.removesuffix("_V").removesuffix("_uA")
        summary[f"{sweep_input}_rise_moves_{name}"] = _sign_label(value)
        summary[f"{sweep_input}_to_{name}_slope"] = value
    return {
        "component": "opamp_v4",
        "category": "debug",
        "purpose": f"{sweep_input}_node_polarity_sweep",
        "metrics": {
            "sweep_input": sweep_input,
            "rows": rows,
            "summary": summary,
        },
    }


def run_unity_feedback_sense_check(
    dut_params: NeuronOaParams | None = None,
    tb_params: V4DebugSweepParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    drive_values=(0.7, 0.9, 1.1),
):
    dut_params = dut_params or NeuronOaParams()
    tb = tb_params or V4DebugSweepParams()
    topologies = []
    configs = [
        ("feedback_to_vinn_drive_vinp", "vinn", "vinp"),
        ("feedback_to_vinp_drive_vinn", "vinp", "vinn"),
    ]
    for name, feedback_to, drive_input in configs:
        rows = []
        for idx, value in enumerate(drive_values):
            vinp_v = float(value) if drive_input == "vinp" else tb.v_cm
            vinn_v = float(value) if drive_input == "vinn" else tb.v_cm
            row = _run_debug_op_point(
                dut_params,
                tb,
                vinp_v=vinp_v,
                vinn_v=vinn_v,
                corner=corner,
                label=f"{name}_{idx}",
                feedback_to=feedback_to,
            )
            target_key = "vinp_V" if drive_input == "vinp" else "vinn_V"
            row["tracking_error_V"] = row["vout_V"] - row[target_key]
            rows.append(row)
        target_key = "vinp_V" if drive_input == "vinp" else "vinn_V"
        track_err_abs = [abs(float(r["tracking_error_V"])) for r in rows]
        topologies.append(
            {
                "name": name,
                "feedback_to": feedback_to,
                "drive_input": drive_input,
                "rows": rows,
                "summary": {
                    "drive_to_vout_slope": _slope(rows, target_key, "vout_V"),
                    "drive_to_vout_sign": _sign_label(_slope(rows, target_key, "vout_V")),
                    "max_abs_tracking_error_V": max(track_err_abs),
                    "mean_abs_tracking_error_V": sum(track_err_abs) / len(track_err_abs),
                },
            }
        )
    return {
        "component": "opamp_v4",
        "category": "debug",
        "purpose": "unity_feedback_sense_check",
        "metrics": topologies,
    }


def run_debug_sweeps(
    dut_params: NeuronOaParams | None = None,
    tb_params: V4DebugSweepParams | None = None,
    *,
    output_dir: Path | None = None,
):
    output_dir = output_dir or Path(__file__).resolve().parent
    dut_params = dut_params or NeuronOaParams()
    tb_params = tb_params or V4DebugSweepParams()
    payload = {
        "input_to_output_polarity_vinp": run_input_node_polarity_sweep(
            dut_params=dut_params,
            tb_params=tb_params,
            sweep_input="vinp",
        )["metrics"],
        "input_to_output_polarity_vinn": run_input_node_polarity_sweep(
            dut_params=dut_params,
            tb_params=tb_params,
            sweep_input="vinn",
        )["metrics"],
        "unity_feedback_sense_check": run_unity_feedback_sense_check(
            dut_params=dut_params,
            tb_params=tb_params,
        )["metrics"],
        "tb_defaults": asdict(tb_params),
    }
    json_path = output_dir / "debug_sweeps_v4.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def run_stage_gain_partition_sweep(
    dut_params: NeuronOaParams | None = None,
    tb_params: V4DebugSweepParams | None = None,
    out_tb_params: V4OutputStageDebugParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or NeuronOaParams()
    tb = tb_params or V4DebugSweepParams()
    out_tb = out_tb_params or V4OutputStageDebugParams()

    vin_sweep = run_input_node_polarity_sweep(
        dut_params=dut_params,
        tb_params=tb,
        corner=corner,
        sweep_input="vinp",
        values=(0.7, 0.8, 0.9, 1.0, 1.1),
    )["metrics"]

    output_rows_vgp = []
    vgp = out_tb.vgp_start
    while vgp <= out_tb.vgp_stop + 1e-15:
        output_rows_vgp.append(
            _run_output_stage_debug_point(
                out_tb,
                vgp_v=vgp,
                vgn_v=0.30,
                corner=corner,
                label=f"vgp_{vgp:.3f}",
            )
        )
        vgp += out_tb.vgp_step

    output_rows_vgn = []
    vgn = out_tb.vgn_start
    while vgn <= out_tb.vgn_stop + 1e-15:
        output_rows_vgn.append(
            _run_output_stage_debug_point(
                out_tb,
                vgp_v=0.39,
                vgn_v=vgn,
                corner=corner,
                label=f"vgn_{vgn:.3f}",
            )
        )
        vgn += out_tb.vgn_step

    raw_rows_vgp = []
    vgp = out_tb.vgp_start
    while vgp <= out_tb.vgp_stop + 1e-15:
        raw_rows_vgp.append(
            _run_raw_push_pull_debug_point(
                out_tb,
                vgp_v=vgp,
                vgn_v=0.30,
                corner=corner,
                label=f"raw_vgp_{vgp:.3f}",
            )
        )
        vgp += out_tb.vgp_step

    raw_rows_vgn = []
    vgn = out_tb.vgn_start
    while vgn <= out_tb.vgn_stop + 1e-15:
        raw_rows_vgn.append(
            _run_raw_push_pull_debug_point(
                out_tb,
                vgp_v=0.39,
                vgn_v=vgn,
                corner=corner,
                label=f"raw_vgn_{vgn:.3f}",
            )
        )
        vgn += out_tb.vgn_step

    payload = {
        "frontend_to_drv": {
            "rows": [
                {
                    "vinp_V": row["vinp_V"],
                    "drv_p_V": row["drv_p_V"],
                    "drv_n_V": row["drv_n_V"],
                    "vout_int_V": row["vout_int_V"],
                    "vout_V": row["vout_V"],
                }
                for row in vin_sweep["rows"]
            ],
            "summary": {
                "vinp_to_drv_p_sign": vin_sweep["summary"]["vinp_rise_moves_drv_p"],
                "vinp_to_drv_n_sign": vin_sweep["summary"]["vinp_rise_moves_drv_n"],
                "vinp_to_drv_p_slope": vin_sweep["summary"]["vinp_to_drv_p_slope"],
                "vinp_to_drv_n_slope": vin_sweep["summary"]["vinp_to_drv_n_slope"],
            },
        },
        "drv_to_gate": {
            "rows": [
                {
                    "vinp_V": row["vinp_V"],
                    "drv_p_V": row["drv_p_V"],
                    "drv_n_V": row["drv_n_V"],
                    "vgp_V": row["vgp_V"],
                    "vgn_V": row["vgn_V"],
                }
                for row in vin_sweep["rows"]
            ],
            "summary": {
                "vinp_to_vgp_sign": vin_sweep["summary"]["vinp_rise_moves_vgp"],
                "vinp_to_vgn_sign": vin_sweep["summary"]["vinp_rise_moves_vgn"],
                "vinp_to_vgp_slope": vin_sweep["summary"]["vinp_to_vgp_slope"],
                "vinp_to_vgn_slope": vin_sweep["summary"]["vinp_to_vgn_slope"],
            },
        },
        "gate_to_output_stage_vgp_sweep": {
            "rows": output_rows_vgp,
            "summary": {
                "vgp_to_vout_sign": _sign_label(_slope(output_rows_vgp, "vgp_V", "vout_V")),
                "vgp_to_vout_slope": _slope(output_rows_vgp, "vgp_V", "vout_V"),
                "vgp_to_iq_sign": _sign_label(_slope(output_rows_vgp, "vgp_V", "iq_uA")),
                "vgp_to_iq_slope": _slope(output_rows_vgp, "vgp_V", "iq_uA"),
            },
        },
        "gate_to_output_stage_vgn_sweep": {
            "rows": output_rows_vgn,
            "summary": {
                "vgn_to_vout_sign": _sign_label(_slope(output_rows_vgn, "vgn_V", "vout_V")),
                "vgn_to_vout_slope": _slope(output_rows_vgn, "vgn_V", "vout_V"),
                "vgn_to_iq_sign": _sign_label(_slope(output_rows_vgn, "vgn_V", "iq_uA")),
                "vgn_to_iq_slope": _slope(output_rows_vgn, "vgn_V", "iq_uA"),
            },
        },
        "raw_push_pull_vgp_sweep": {
            "rows": raw_rows_vgp,
            "summary": {
                "vgp_to_vout_sign": _sign_label(_slope(raw_rows_vgp, "vgp_V", "vout_V")),
                "vgp_to_vout_slope": _slope(raw_rows_vgp, "vgp_V", "vout_V"),
                "vgp_to_iq_sign": _sign_label(_slope(raw_rows_vgp, "vgp_V", "iq_uA")),
                "vgp_to_iq_slope": _slope(raw_rows_vgp, "vgp_V", "iq_uA"),
            },
        },
        "raw_push_pull_vgn_sweep": {
            "rows": raw_rows_vgn,
            "summary": {
                "vgn_to_vout_sign": _sign_label(_slope(raw_rows_vgn, "vgn_V", "vout_V")),
                "vgn_to_vout_slope": _slope(raw_rows_vgn, "vgn_V", "vout_V"),
                "vgn_to_iq_sign": _sign_label(_slope(raw_rows_vgn, "vgn_V", "iq_uA")),
                "vgn_to_iq_slope": _slope(raw_rows_vgn, "vgn_V", "iq_uA"),
            },
        },
        "tb_defaults": {
            "top_debug": asdict(tb),
            "output_stage_debug": asdict(out_tb),
        },
    }
    return {
        "component": "opamp_v4",
        "category": "debug",
        "purpose": "stage_gain_partition_sweep",
        "metrics": payload,
    }
