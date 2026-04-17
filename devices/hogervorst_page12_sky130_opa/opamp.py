import hdl21 as h
from hdl21.primitives import MosVth

from .source.generators import (
    U,
    F,
    InvParams,
    SwitchParams,
    cmos_inv,
    nmos_switch,
    pmos_switch,
    transmission_gate,
)
from .source.opa_bias import OpaBiasGenParams


def _nmos(w, l, *, vth=MosVth.STD):
    return h.Nmos(w=w, l=l, vth=vth, family=h.MosFamily.CORE)


def _pmos(w, l, *, vth=MosVth.STD):
    return h.Pmos(w=w, l=l, vth=vth, family=h.MosFamily.CORE)


@h.paramclass
class FrontEndParams:
    """Page-12 folded-cascode first-stage geometry."""

    w_in_p = h.Param(dtype=h.Scalar, desc="PMOS input-pair width", default=8.0 * U)
    w_in_n = h.Param(dtype=h.Scalar, desc="NMOS input-pair width", default=4.0 * U)
    l_in = h.Param(dtype=h.Scalar, desc="Input-pair length", default=0.50 * U)
    w_pcas1 = h.Param(dtype=h.Scalar, desc="Top PMOS folded-cascode width", default=4.0 * U)
    w_pcas2 = h.Param(dtype=h.Scalar, desc="Second PMOS folded-cascode width", default=4.0 * U)
    w_ncas = h.Param(dtype=h.Scalar, desc="NMOS folded-cascode width", default=3.0 * U)
    w_nmir = h.Param(dtype=h.Scalar, desc="Bottom NMOS mirror width", default=3.0 * U)
    l_fold = h.Param(dtype=h.Scalar, desc="Folded-cascode device length", default=0.60 * U)


@h.paramclass
class MonticelliParams:
    """Page-12 explicit diode stacks plus Monticelli floating battery."""

    w_m24 = h.Param(dtype=h.Scalar, desc="NMOS floating-battery width", default=1.5 * U)
    w_m35 = h.Param(dtype=h.Scalar, desc="PMOS floating-battery width", default=3.0 * U)
    l_mont = h.Param(dtype=h.Scalar, desc="Monticelli-cell length", default=0.60 * U)
    w_stack_n = h.Param(dtype=h.Scalar, desc="NMOS diode-stack width", default=1.0 * U)
    w_stack_p = h.Param(dtype=h.Scalar, desc="PMOS diode-stack width", default=1.5 * U)
    l_stack = h.Param(dtype=h.Scalar, desc="Diode-stack length", default=0.60 * U)


@h.paramclass
class OutputStageParams:
    """Page-12 push-pull output plus dual Rc-Cc compensation."""

    w_out_p = h.Param(dtype=h.Scalar, desc="PMOS output width", default=16.0 * U)
    w_out_n = h.Param(dtype=h.Scalar, desc="NMOS output width", default=8.0 * U)
    l_out = h.Param(dtype=h.Scalar, desc="Output length", default=0.60 * U)
    rc = h.Param(dtype=h.Scalar, desc="Series compensation resistor", default=12_000)
    cc = h.Param(dtype=h.Scalar, desc="Compensation capacitor", default=9.0 * F)


@h.paramclass
class NeuronOaParams:
    inv = h.Param(dtype=InvParams, desc="Small inverters", default=InvParams())
    tg = h.Param(dtype=SwitchParams, desc="Transmission gate switches", default=SwitchParams())
    rail_sw = h.Param(
        dtype=SwitchParams,
        desc="Single-ended rail switches",
        default=SwitchParams(wp=5.0 * U, lp=0.30 * U, wn=4.0 * U, ln=0.30 * U),
    )
    bias = h.Param(
        dtype=OpaBiasGenParams,
        desc="Legacy bias-generator parameters kept only for compatibility",
        default=OpaBiasGenParams(),
    )
    frontend = h.Param(dtype=FrontEndParams, desc="Page-12 folded first stage", default=FrontEndParams())
    monticelli = h.Param(dtype=MonticelliParams, desc="Page-12 Monticelli cell", default=MonticelliParams())
    output = h.Param(dtype=OutputStageParams, desc="Page-12 output stage", default=OutputStageParams())

    vbias1_V = h.Param(dtype=h.Scalar, desc="Ideal frontend bias-1 voltage", default=0.82383252916907)
    vbias2_V = h.Param(dtype=h.Scalar, desc="Ideal frontend bias-2 voltage", default=0.890730977583764)
    vbias3_V = h.Param(dtype=h.Scalar, desc="Ideal frontend bias-3 voltage", default=0.6335259806583905)
    tail_p_uA = h.Param(dtype=h.Scalar, desc="Ideal PMOS tail current in uA", default=1.6)
    tail_n_uA = h.Param(dtype=h.Scalar, desc="Ideal NMOS tail current in uA", default=1.6)
    vb_m24_uA = h.Param(dtype=h.Scalar, desc="Ideal PMOS-source current into vb_m24 in uA", default=0.45)
    vb_m35_uA = h.Param(dtype=h.Scalar, desc="Ideal NMOS-sink current from vb_m35 in uA", default=0.45)
    iref_term_ohm = h.Param(dtype=h.Scalar, desc="Termination for the external iref pin", default=1e6)


@h.generator
def neuron_core_oa_sky130(params: NeuronOaParams) -> h.Module:
    @h.module
    class NeuronCoreOaSky130:
        # External interface.
        avdd1p2 = h.Inout()
        agnd = h.Inout()
        vinp = h.Input()
        vinn = h.Input()
        vout = h.Output()
        in0u25_oa = h.Inout()
        vbase = h.Inout()
        vfeed = h.Inout()

        d_en_oa = h.Input()
        d_az_oa = h.Input()
        d_inf_oa = h.Input()

        vtest = h.Inout()
        d_treset_oa = h.Input()
        d_tcki = h.Input()
        d_tcko = h.Output()
        d_tdi = h.Input()
        d_tdo = h.Output()

        # Control and internal analog nodes.
        d_en_b, d_az_b, d_inf_b, d_tdi_b = h.Signals(4)
        iref_int = h.Signal()
        vbias1, vbias2, vbias3 = h.Signals(3)
        tail_p, tail_n, vb_m24, vb_m35 = h.Signals(4)
        vgp, vgn = h.Signals(2)
        pnode_l, pnode_r = h.Signals(2)
        nnode_l, nnode_r = h.Signals(2)
        vref_mid = h.Signal()
        n_mid, p_mid = h.Signals(2)
        ccp_mid, ccn_mid = h.Signals(2)

    dut = NeuronCoreOaSky130
    fp = params.frontend
    mp = params.monticelli
    op = params.output
    avdd = dut.avdd1p2
    vss = dut.agnd
    vgp = dut.vgp
    vgn = dut.vgn
    vb_m24 = dut.vb_m24
    vb_m35 = dut.vb_m35
    vb1 = dut.vbias1
    vb2 = dut.vbias2
    vb3 = dut.vbias3
    tail_p = dut.tail_p
    tail_n = dut.tail_n
    p_l = dut.pnode_l
    p_r = dut.pnode_r
    n_l = dut.nnode_l
    n_r = dut.nnode_r
    vref = dut.vref_mid
    n_mid = dut.n_mid
    p_mid = dut.p_mid
    ccp = dut.ccp_mid
    ccn = dut.ccn_mid

    # Control inversion and pin-level hooks.
    dut.inv_en = cmos_inv(params.inv)(i=dut.d_en_oa, o=dut.d_en_b, avdd=avdd, agnd=vss)
    dut.inv_az = cmos_inv(params.inv)(i=dut.d_az_oa, o=dut.d_az_b, avdd=avdd, agnd=vss)
    dut.inv_inf = cmos_inv(params.inv)(i=dut.d_inf_oa, o=dut.d_inf_b, avdd=avdd, agnd=vss)
    dut.inv_tdi = cmos_inv(params.inv)(i=dut.d_tdi, o=dut.d_tdi_b, avdd=avdd, agnd=vss)

    dut.iref_sw = transmission_gate(params.tg)(
        a=dut.in0u25_oa,
        b=dut.iref_int,
        en=dut.d_en_oa,
        en_b=dut.d_en_b,
        avdd=avdd,
        agnd=vss,
    )
    dut.iref_term = h.Res(r=params.iref_term_ohm)(p=dut.iref_int, n=vss)

    dut.vbase_sw = nmos_switch(params.rail_sw)(a=dut.vbase, b=vss, en=dut.d_inf_oa, agnd=vss)
    dut.vfeed_sw = pmos_switch(params.rail_sw)(a=avdd, b=dut.vfeed, en_b=dut.d_inf_b, avdd=avdd)
    dut.vout_to_vtest = transmission_gate(params.tg)(
        a=dut.vout,
        b=dut.vtest,
        en=dut.d_tdi,
        en_b=dut.d_tdi_b,
        avdd=avdd,
        agnd=vss,
    )
    dut.tck_short = h.Res(r=1e-3)(p=dut.d_tcki, n=dut.d_tcko)
    dut.tdi_short = h.Res(r=1e-3)(p=dut.d_tdi, n=dut.d_tdo)

    # Idealized internal biasing.
    dut.vbias1_src = h.Vdc(dc=params.vbias1_V)(p=vb1, n=vss)
    dut.vbias2_src = h.Vdc(dc=params.vbias2_V)(p=vb2, n=vss)
    dut.vbias3_src = h.Vdc(dc=params.vbias3_V)(p=vb3, n=vss)
    dut.itail_p = h.Idc(dc=params.tail_p_uA * 1e-6)(p=avdd, n=tail_p)
    dut.itail_n = h.Idc(dc=params.tail_n_uA * 1e-6)(p=tail_n, n=vss)
    dut.ibias_m24 = h.Idc(dc=params.vb_m24_uA * 1e-6)(p=avdd, n=vb_m24)
    dut.ibias_m35 = h.Idc(dc=params.vb_m35_uA * 1e-6)(p=vb_m35, n=vss)

    # Folded-cascode frontend.
    # tail_p -> PMOS pair -> NMOS folded nodes
    dut.pinp_l = _pmos(fp.w_in_p, fp.l_in, vth=MosVth.LOW)(d=n_l, g=dut.vinn, s=tail_p, b=avdd)
    dut.pinp_r = _pmos(fp.w_in_p, fp.l_in, vth=MosVth.LOW)(d=n_r, g=dut.vinp, s=tail_p, b=avdd)
    # tail_n -> NMOS pair -> PMOS folded nodes
    dut.ninp_l = _nmos(fp.w_in_n, fp.l_in, vth=MosVth.LOW)(d=p_l, g=dut.vinp, s=tail_n, b=vss)
    dut.ninp_r = _nmos(fp.w_in_n, fp.l_in, vth=MosVth.LOW)(d=p_r, g=dut.vinn, s=tail_n, b=vss)
    # avdd -> mpb1 -> pnodes
    dut.mpb1_l = _pmos(fp.w_pcas1, fp.l_fold, vth=MosVth.HIGH)(d=p_l, g=vb1, s=avdd, b=avdd)
    dut.mpb1_r = _pmos(fp.w_pcas1, fp.l_fold, vth=MosVth.HIGH)(d=p_r, g=vb1, s=avdd, b=avdd)
    # pnodes -> mpb2 -> {vref, vgp}
    dut.mpb2_l = _pmos(fp.w_pcas2, fp.l_fold)(d=vref, g=vb2, s=p_l, b=avdd)
    dut.mpb2_r = _pmos(fp.w_pcas2, fp.l_fold)(d=vgp, g=vb2, s=p_r, b=avdd)
    # nnodes -> mnb3 -> {vref, vgn}
    dut.mnb3_l = _nmos(fp.w_ncas, fp.l_fold)(d=vref, g=vb3, s=n_l, b=vss)
    dut.mnb3_r = _nmos(fp.w_ncas, fp.l_fold)(d=vgn, g=vb3, s=n_r, b=vss)
    # nnodes -> NMOS mirror -> vss
    dut.mnref = _nmos(fp.w_nmir, fp.l_fold)(d=n_l, g=n_l, s=vss, b=vss)
    dut.mnout = _nmos(fp.w_nmir, fp.l_fold)(d=n_r, g=n_l, s=vss, b=vss)
    dut.az_short = transmission_gate(params.tg)(
        a=vgp,
        b=vgn,
        en=dut.d_az_oa,
        en_b=dut.d_az_b,
        avdd=avdd,
        agnd=vss,
    )

    # Monticelli class-AB bias network.
    # vb_m24 -> mn22 -> n_mid -> mn23 -> vss
    dut.mn22 = _nmos(mp.w_stack_n, mp.l_stack)(d=vb_m24, g=vb_m24, s=n_mid, b=vss)
    dut.mn23 = _nmos(mp.w_stack_n, mp.l_stack)(d=n_mid, g=n_mid, s=vss, b=vss)
    # avdd -> mp33 -> p_mid -> mp34 -> vb_m35
    dut.mp33 = _pmos(mp.w_stack_p, mp.l_stack, vth=MosVth.HIGH)(d=p_mid, g=p_mid, s=avdd, b=avdd)
    dut.mp34 = _pmos(mp.w_stack_p, mp.l_stack, vth=MosVth.HIGH)(d=vb_m35, g=vb_m35, s=p_mid, b=avdd)
    # floating battery between vgp and vgn
    dut.m24 = _nmos(mp.w_m24, mp.l_mont)(d=vgp, g=vb_m24, s=vgn, b=vss)
    dut.m35 = _pmos(mp.w_m35, mp.l_mont)(d=vgn, g=vb_m35, s=vgp, b=avdd)

    # Output stage and compensation.
    dut.m2 = _pmos(op.w_out_p, op.l_out)(d=dut.vout, g=vgp, s=avdd, b=avdd)
    dut.m1 = _nmos(op.w_out_n, op.l_out)(d=dut.vout, g=vgn, s=vss, b=vss)
    # {vgp, vgn} -> Rc-Cc -> vout
    dut.rcp = h.Res(r=op.rc)(p=vgp, n=ccp)
    dut.ccp = h.Cap(c=op.cc)(p=ccp, n=dut.vout)
    dut.rcn = h.Res(r=op.rc)(p=vgn, n=ccn)
    dut.ccn = h.Cap(c=op.cc)(p=ccn, n=dut.vout)

    return NeuronCoreOaSky130


def compile_for_sky130(src):
    try:
        import sky130_hdl21 as sky130_pdk  # type: ignore
    except ImportError:
        import sky130 as sky130_pdk  # type: ignore

    sky130_pdk.compile(src)
    return src
