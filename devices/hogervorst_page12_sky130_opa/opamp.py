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


@h.generator
def complementary_cascode_frontend(params: FrontEndParams) -> h.Module:
    """Legacy standalone frontend generator kept for debug benches."""

    @h.module
    class ComplementaryCascodeFrontEnd:
        vinp = h.Input()
        vinn = h.Input()
        avdd = h.Inout()
        agnd = h.Inout()

        tail_p = h.Inout()
        tail_n = h.Inout()
        vbias1 = h.Input()
        vbias2 = h.Input()
        vbias3 = h.Input()

        vgp = h.Output()
        vgn = h.Output()

        pnode_l = h.Signal()
        pnode_r = h.Signal()
        nnode_l = h.Signal()
        nnode_r = h.Signal()
        vref_mid = h.Signal()

        pinp_l = _pmos(params.w_in_p, params.l_in, vth=MosVth.LOW)(
            d=nnode_l, g=vinn, s=tail_p, b=avdd
        )
        pinp_r = _pmos(params.w_in_p, params.l_in, vth=MosVth.LOW)(
            d=nnode_r, g=vinp, s=tail_p, b=avdd
        )

        ninp_l = _nmos(params.w_in_n, params.l_in, vth=MosVth.LOW)(
            d=pnode_l, g=vinp, s=tail_n, b=agnd
        )
        ninp_r = _nmos(params.w_in_n, params.l_in, vth=MosVth.LOW)(
            d=pnode_r, g=vinn, s=tail_n, b=agnd
        )

        mpb1_l = _pmos(params.w_pcas1, params.l_fold, vth=MosVth.HIGH)(
            d=pnode_l, g=vbias1, s=avdd, b=avdd
        )
        mpb1_r = _pmos(params.w_pcas1, params.l_fold, vth=MosVth.HIGH)(
            d=pnode_r, g=vbias1, s=avdd, b=avdd
        )

        mpb2_l = _pmos(params.w_pcas2, params.l_fold)(
            d=vref_mid, g=vbias2, s=pnode_l, b=avdd
        )
        mpb2_r = _pmos(params.w_pcas2, params.l_fold)(
            d=vgp, g=vbias2, s=pnode_r, b=avdd
        )

        mnb3_l = _nmos(params.w_ncas, params.l_fold)(
            d=vref_mid, g=vbias3, s=nnode_l, b=agnd
        )
        mnb3_r = _nmos(params.w_ncas, params.l_fold)(
            d=vgn, g=vbias3, s=nnode_r, b=agnd
        )

        mnref = _nmos(params.w_nmir, params.l_fold)(
            d=nnode_l, g=nnode_l, s=agnd, b=agnd
        )
        mnout = _nmos(params.w_nmir, params.l_fold)(
            d=nnode_r, g=nnode_l, s=agnd, b=agnd
        )

    return ComplementaryCascodeFrontEnd


@h.paramclass
class MonticelliParams:
    """Page-12 explicit diode stacks plus Monticelli floating battery."""

    w_m24 = h.Param(dtype=h.Scalar, desc="NMOS floating-battery width", default=1.5 * U)
    w_m35 = h.Param(dtype=h.Scalar, desc="PMOS floating-battery width", default=3.0 * U)
    l_mont = h.Param(dtype=h.Scalar, desc="Monticelli-cell length", default=0.60 * U)
    w_stack_n = h.Param(dtype=h.Scalar, desc="NMOS diode-stack width", default=1.0 * U)
    w_stack_p = h.Param(dtype=h.Scalar, desc="PMOS diode-stack width", default=1.5 * U)
    l_stack = h.Param(dtype=h.Scalar, desc="Diode-stack length", default=0.60 * U)


@h.generator
def monticelli_cell(params: MonticelliParams) -> h.Module:
    """Legacy standalone Monticelli cell kept for local debug benches."""

    @h.module
    class MonticelliCell:
        vb_m24 = h.Inout()
        vb_m35 = h.Inout()
        vgp = h.Inout()
        vgn = h.Inout()
        avdd = h.Inout()
        agnd = h.Inout()

        n_mid = h.Signal()
        p_mid = h.Signal()

        mn22 = _nmos(params.w_stack_n, params.l_stack)(
            d=vb_m24, g=vb_m24, s=n_mid, b=agnd
        )
        mn23 = _nmos(params.w_stack_n, params.l_stack)(
            d=n_mid, g=n_mid, s=agnd, b=agnd
        )

        mp33 = _pmos(params.w_stack_p, params.l_stack, vth=MosVth.HIGH)(
            d=p_mid, g=p_mid, s=avdd, b=avdd
        )
        mp34 = _pmos(params.w_stack_p, params.l_stack, vth=MosVth.HIGH)(
            d=vb_m35, g=vb_m35, s=p_mid, b=avdd
        )

        m24 = _nmos(params.w_m24, params.l_mont)(
            d=vgp, g=vb_m24, s=vgn, b=agnd
        )
        m35 = _pmos(params.w_m35, params.l_mont)(
            d=vgn, g=vb_m35, s=vgp, b=avdd
        )

    return MonticelliCell


@h.paramclass
class OutputStageParams:
    """Page-12 push-pull output plus dual Rc-Cc compensation."""

    w_out_p = h.Param(dtype=h.Scalar, desc="PMOS output width", default=16.0 * U)
    w_out_n = h.Param(dtype=h.Scalar, desc="NMOS output width", default=8.0 * U)
    l_out = h.Param(dtype=h.Scalar, desc="Output length", default=0.60 * U)
    rc = h.Param(dtype=h.Scalar, desc="Series compensation resistor", default=12_000)
    cc = h.Param(dtype=h.Scalar, desc="Compensation capacitor", default=9.0 * F)


@h.generator
def classab_output_stage(params: OutputStageParams) -> h.Module:
    """Legacy standalone output stage kept for local debug benches."""

    @h.module
    class ClassAbOutputStage:
        vgp = h.Input()
        vgn = h.Input()
        vout = h.Output()
        avdd = h.Inout()
        agnd = h.Inout()

        ccp_mid, ccn_mid = h.Signals(2)

        m2 = _pmos(params.w_out_p, params.l_out)(d=vout, g=vgp, s=avdd, b=avdd)
        m1 = _nmos(params.w_out_n, params.l_out)(d=vout, g=vgn, s=agnd, b=agnd)

        rcp = h.Res(r=params.rc)(p=vgp, n=ccp_mid)
        ccp = h.Cap(c=params.cc)(p=ccp_mid, n=vout)
        rcn = h.Res(r=params.rc)(p=vgn, n=ccn_mid)
        ccn = h.Cap(c=params.cc)(p=ccn_mid, n=vout)

    return ClassAbOutputStage


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

    NeuronCoreOaSky130.inv_en = cmos_inv(params.inv)(
        i=NeuronCoreOaSky130.d_en_oa,
        o=NeuronCoreOaSky130.d_en_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )
    NeuronCoreOaSky130.inv_az = cmos_inv(params.inv)(
        i=NeuronCoreOaSky130.d_az_oa,
        o=NeuronCoreOaSky130.d_az_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )
    NeuronCoreOaSky130.inv_inf = cmos_inv(params.inv)(
        i=NeuronCoreOaSky130.d_inf_oa,
        o=NeuronCoreOaSky130.d_inf_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )
    NeuronCoreOaSky130.inv_tdi = cmos_inv(params.inv)(
        i=NeuronCoreOaSky130.d_tdi,
        o=NeuronCoreOaSky130.d_tdi_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )

    NeuronCoreOaSky130.iref_sw = transmission_gate(params.tg)(
        a=NeuronCoreOaSky130.in0u25_oa,
        b=NeuronCoreOaSky130.iref_int,
        en=NeuronCoreOaSky130.d_en_oa,
        en_b=NeuronCoreOaSky130.d_en_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )
    NeuronCoreOaSky130.iref_term = h.Res(r=params.iref_term_ohm)(
        p=NeuronCoreOaSky130.iref_int,
        n=NeuronCoreOaSky130.agnd,
    )

    NeuronCoreOaSky130.vbias1_src = h.Vdc(dc=params.vbias1_V)(
        p=NeuronCoreOaSky130.vbias1,
        n=NeuronCoreOaSky130.agnd,
    )
    NeuronCoreOaSky130.vbias2_src = h.Vdc(dc=params.vbias2_V)(
        p=NeuronCoreOaSky130.vbias2,
        n=NeuronCoreOaSky130.agnd,
    )
    NeuronCoreOaSky130.vbias3_src = h.Vdc(dc=params.vbias3_V)(
        p=NeuronCoreOaSky130.vbias3,
        n=NeuronCoreOaSky130.agnd,
    )
    NeuronCoreOaSky130.itail_p = h.Idc(dc=params.tail_p_uA * 1e-6)(
        p=NeuronCoreOaSky130.avdd1p2,
        n=NeuronCoreOaSky130.tail_p,
    )
    NeuronCoreOaSky130.itail_n = h.Idc(dc=params.tail_n_uA * 1e-6)(
        p=NeuronCoreOaSky130.tail_n,
        n=NeuronCoreOaSky130.agnd,
    )
    NeuronCoreOaSky130.ibias_m24 = h.Idc(dc=params.vb_m24_uA * 1e-6)(
        p=NeuronCoreOaSky130.avdd1p2,
        n=NeuronCoreOaSky130.vb_m24,
    )
    NeuronCoreOaSky130.ibias_m35 = h.Idc(dc=params.vb_m35_uA * 1e-6)(
        p=NeuronCoreOaSky130.vb_m35,
        n=NeuronCoreOaSky130.agnd,
    )

    NeuronCoreOaSky130.pinp_l = _pmos(params.frontend.w_in_p, params.frontend.l_in, vth=MosVth.LOW)(
        d=NeuronCoreOaSky130.nnode_l, g=NeuronCoreOaSky130.vinn, s=NeuronCoreOaSky130.tail_p, b=NeuronCoreOaSky130.avdd1p2
    )
    NeuronCoreOaSky130.pinp_r = _pmos(params.frontend.w_in_p, params.frontend.l_in, vth=MosVth.LOW)(
        d=NeuronCoreOaSky130.nnode_r, g=NeuronCoreOaSky130.vinp, s=NeuronCoreOaSky130.tail_p, b=NeuronCoreOaSky130.avdd1p2
    )
    NeuronCoreOaSky130.ninp_l = _nmos(params.frontend.w_in_n, params.frontend.l_in, vth=MosVth.LOW)(
        d=NeuronCoreOaSky130.pnode_l, g=NeuronCoreOaSky130.vinp, s=NeuronCoreOaSky130.tail_n, b=NeuronCoreOaSky130.agnd
    )
    NeuronCoreOaSky130.ninp_r = _nmos(params.frontend.w_in_n, params.frontend.l_in, vth=MosVth.LOW)(
        d=NeuronCoreOaSky130.pnode_r, g=NeuronCoreOaSky130.vinn, s=NeuronCoreOaSky130.tail_n, b=NeuronCoreOaSky130.agnd
    )
    NeuronCoreOaSky130.mpb1_l = _pmos(params.frontend.w_pcas1, params.frontend.l_fold, vth=MosVth.HIGH)(
        d=NeuronCoreOaSky130.pnode_l, g=NeuronCoreOaSky130.vbias1, s=NeuronCoreOaSky130.avdd1p2, b=NeuronCoreOaSky130.avdd1p2
    )
    NeuronCoreOaSky130.mpb1_r = _pmos(params.frontend.w_pcas1, params.frontend.l_fold, vth=MosVth.HIGH)(
        d=NeuronCoreOaSky130.pnode_r, g=NeuronCoreOaSky130.vbias1, s=NeuronCoreOaSky130.avdd1p2, b=NeuronCoreOaSky130.avdd1p2
    )
    NeuronCoreOaSky130.mpb2_l = _pmos(params.frontend.w_pcas2, params.frontend.l_fold)(
        d=NeuronCoreOaSky130.vref_mid, g=NeuronCoreOaSky130.vbias2, s=NeuronCoreOaSky130.pnode_l, b=NeuronCoreOaSky130.avdd1p2
    )
    NeuronCoreOaSky130.mpb2_r = _pmos(params.frontend.w_pcas2, params.frontend.l_fold)(
        d=NeuronCoreOaSky130.vgp, g=NeuronCoreOaSky130.vbias2, s=NeuronCoreOaSky130.pnode_r, b=NeuronCoreOaSky130.avdd1p2
    )
    NeuronCoreOaSky130.mnb3_l = _nmos(params.frontend.w_ncas, params.frontend.l_fold)(
        d=NeuronCoreOaSky130.vref_mid, g=NeuronCoreOaSky130.vbias3, s=NeuronCoreOaSky130.nnode_l, b=NeuronCoreOaSky130.agnd
    )
    NeuronCoreOaSky130.mnb3_r = _nmos(params.frontend.w_ncas, params.frontend.l_fold)(
        d=NeuronCoreOaSky130.vgn, g=NeuronCoreOaSky130.vbias3, s=NeuronCoreOaSky130.nnode_r, b=NeuronCoreOaSky130.agnd
    )
    NeuronCoreOaSky130.mnref = _nmos(params.frontend.w_nmir, params.frontend.l_fold)(
        d=NeuronCoreOaSky130.nnode_l, g=NeuronCoreOaSky130.nnode_l, s=NeuronCoreOaSky130.agnd, b=NeuronCoreOaSky130.agnd
    )
    NeuronCoreOaSky130.mnout = _nmos(params.frontend.w_nmir, params.frontend.l_fold)(
        d=NeuronCoreOaSky130.nnode_r, g=NeuronCoreOaSky130.nnode_l, s=NeuronCoreOaSky130.agnd, b=NeuronCoreOaSky130.agnd
    )

    NeuronCoreOaSky130.az_short = transmission_gate(params.tg)(
        a=NeuronCoreOaSky130.vgp,
        b=NeuronCoreOaSky130.vgn,
        en=NeuronCoreOaSky130.d_az_oa,
        en_b=NeuronCoreOaSky130.d_az_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )

    NeuronCoreOaSky130.mn22 = _nmos(params.monticelli.w_stack_n, params.monticelli.l_stack)(
        d=NeuronCoreOaSky130.vb_m24, g=NeuronCoreOaSky130.vb_m24, s=NeuronCoreOaSky130.n_mid, b=NeuronCoreOaSky130.agnd
    )
    NeuronCoreOaSky130.mn23 = _nmos(params.monticelli.w_stack_n, params.monticelli.l_stack)(
        d=NeuronCoreOaSky130.n_mid, g=NeuronCoreOaSky130.n_mid, s=NeuronCoreOaSky130.agnd, b=NeuronCoreOaSky130.agnd
    )
    NeuronCoreOaSky130.mp33 = _pmos(params.monticelli.w_stack_p, params.monticelli.l_stack, vth=MosVth.HIGH)(
        d=NeuronCoreOaSky130.p_mid, g=NeuronCoreOaSky130.p_mid, s=NeuronCoreOaSky130.avdd1p2, b=NeuronCoreOaSky130.avdd1p2
    )
    NeuronCoreOaSky130.mp34 = _pmos(params.monticelli.w_stack_p, params.monticelli.l_stack, vth=MosVth.HIGH)(
        d=NeuronCoreOaSky130.vb_m35, g=NeuronCoreOaSky130.vb_m35, s=NeuronCoreOaSky130.p_mid, b=NeuronCoreOaSky130.avdd1p2
    )
    NeuronCoreOaSky130.m24 = _nmos(params.monticelli.w_m24, params.monticelli.l_mont)(
        d=NeuronCoreOaSky130.vgp, g=NeuronCoreOaSky130.vb_m24, s=NeuronCoreOaSky130.vgn, b=NeuronCoreOaSky130.agnd
    )
    NeuronCoreOaSky130.m35 = _pmos(params.monticelli.w_m35, params.monticelli.l_mont)(
        d=NeuronCoreOaSky130.vgn, g=NeuronCoreOaSky130.vb_m35, s=NeuronCoreOaSky130.vgp, b=NeuronCoreOaSky130.avdd1p2
    )

    NeuronCoreOaSky130.m2 = _pmos(params.output.w_out_p, params.output.l_out)(
        d=NeuronCoreOaSky130.vout, g=NeuronCoreOaSky130.vgp, s=NeuronCoreOaSky130.avdd1p2, b=NeuronCoreOaSky130.avdd1p2
    )
    NeuronCoreOaSky130.m1 = _nmos(params.output.w_out_n, params.output.l_out)(
        d=NeuronCoreOaSky130.vout, g=NeuronCoreOaSky130.vgn, s=NeuronCoreOaSky130.agnd, b=NeuronCoreOaSky130.agnd
    )
    NeuronCoreOaSky130.rcp = h.Res(r=params.output.rc)(p=NeuronCoreOaSky130.vgp, n=NeuronCoreOaSky130.ccp_mid)
    NeuronCoreOaSky130.ccp = h.Cap(c=params.output.cc)(p=NeuronCoreOaSky130.ccp_mid, n=NeuronCoreOaSky130.vout)
    NeuronCoreOaSky130.rcn = h.Res(r=params.output.rc)(p=NeuronCoreOaSky130.vgn, n=NeuronCoreOaSky130.ccn_mid)
    NeuronCoreOaSky130.ccn = h.Cap(c=params.output.cc)(p=NeuronCoreOaSky130.ccn_mid, n=NeuronCoreOaSky130.vout)

    NeuronCoreOaSky130.vbase_sw = nmos_switch(params.rail_sw)(
        a=NeuronCoreOaSky130.vbase,
        b=NeuronCoreOaSky130.agnd,
        en=NeuronCoreOaSky130.d_inf_oa,
        agnd=NeuronCoreOaSky130.agnd,
    )
    NeuronCoreOaSky130.vfeed_sw = pmos_switch(params.rail_sw)(
        a=NeuronCoreOaSky130.avdd1p2,
        b=NeuronCoreOaSky130.vfeed,
        en_b=NeuronCoreOaSky130.d_inf_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
    )
    NeuronCoreOaSky130.vout_to_vtest = transmission_gate(params.tg)(
        a=NeuronCoreOaSky130.vout,
        b=NeuronCoreOaSky130.vtest,
        en=NeuronCoreOaSky130.d_tdi,
        en_b=NeuronCoreOaSky130.d_tdi_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )

    NeuronCoreOaSky130.tck_short = h.Res(r=1e-3)(
        p=NeuronCoreOaSky130.d_tcki,
        n=NeuronCoreOaSky130.d_tcko,
    )
    NeuronCoreOaSky130.tdi_short = h.Res(r=1e-3)(
        p=NeuronCoreOaSky130.d_tdi,
        n=NeuronCoreOaSky130.d_tdo,
    )

    return NeuronCoreOaSky130


def compile_for_sky130(src):
    try:
        import sky130_hdl21 as sky130_pdk  # type: ignore
    except ImportError:
        import sky130 as sky130_pdk  # type: ignore

    sky130_pdk.compile(src)
    return src
