import hdl21 as h
from hdl21.primitives import MosVth

from .generators import (
    U,
    F,
    InvParams,
    SwitchParams,
    cmos_inv,
    nmos_switch,
    pmos_switch,
    transmission_gate,
)
from .opa_bias import OpaBiasGen, OpaBiasGenParams


def _nmos(w, l, *, vth=MosVth.STD):
    return h.Nmos(w=w, l=l, vth=vth, family=h.MosFamily.CORE)


def _pmos(w, l, *, vth=MosVth.STD):
    return h.Pmos(w=w, l=l, vth=vth, family=h.MosFamily.CORE)


@h.paramclass
class FrontEndParams:
    """Page-12 folded-cascode first stage."""

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

        # PMOS rail-to-rail input pair. Reference page-12 uses drains folded into NMOS side.
        pinp_l = _pmos(params.w_in_p, params.l_in, vth=MosVth.LOW)(
            d=nnode_l, g=vinn, s=tail_p, b=avdd
        )
        pinp_r = _pmos(params.w_in_p, params.l_in, vth=MosVth.LOW)(
            d=nnode_r, g=vinp, s=tail_p, b=avdd
        )

        # NMOS rail-to-rail input pair. Drains fold into PMOS side.
        ninp_l = _nmos(params.w_in_n, params.l_in, vth=MosVth.LOW)(
            d=pnode_l, g=vinp, s=tail_n, b=agnd
        )
        ninp_r = _nmos(params.w_in_n, params.l_in, vth=MosVth.LOW)(
            d=pnode_r, g=vinn, s=tail_n, b=agnd
        )

        # Upper PMOS folded-cascode bias devices.
        mpb1_l = _pmos(params.w_pcas1, params.l_fold, vth=MosVth.HIGH)(
            d=pnode_l, g=vbias1, s=avdd, b=avdd
        )
        mpb1_r = _pmos(params.w_pcas1, params.l_fold, vth=MosVth.HIGH)(
            d=pnode_r, g=vbias1, s=avdd, b=avdd
        )

        # Upper signal-path PMOS devices.
        mpb2_l = _pmos(params.w_pcas2, params.l_fold)(
            d=vref_mid, g=vbias2, s=pnode_l, b=avdd
        )
        mpb2_r = _pmos(params.w_pcas2, params.l_fold)(
            d=vgp, g=vbias2, s=pnode_r, b=avdd
        )

        # Lower signal-path NMOS devices.
        mnb3_l = _nmos(params.w_ncas, params.l_fold)(
            d=vref_mid, g=vbias3, s=nnode_l, b=agnd
        )
        mnb3_r = _nmos(params.w_ncas, params.l_fold)(
            d=vgn, g=vbias3, s=nnode_r, b=agnd
        )

        # Bottom NMOS mirror/sink pair.
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
    @h.module
    class MonticelliCell:
        m24_gate_mid = h.Inout()
        m35_gate_mid = h.Inout()
        vgp = h.Inout()
        vgn = h.Inout()
        avdd = h.Inout()
        agnd = h.Inout()

        n_mid = h.Signal()
        p_mid = h.Signal()

        # Page-12 lower branch:
        # current source -> M24 gate mid -> M23 -> M22 -> AGND.
        # `m24_gate_mid` is the M24-gate midpoint driven from the PMOS current-source side.
        mn23 = _nmos(params.w_stack_n, params.l_stack)(
            d=m24_gate_mid, g=m24_gate_mid, s=n_mid, b=agnd
        )
        mn22 = _nmos(params.w_stack_n, params.l_stack)(
            d=n_mid, g=n_mid, s=agnd, b=agnd
        )

        # Page-12 upper branch:
        # AVDD -> M33 -> M34 -> M35 gate mid -> current sink.
        # `m35_gate_mid` is the M35-gate midpoint drained by the NMOS current-sink side.
        mp33 = _pmos(params.w_stack_p, params.l_stack, vth=MosVth.HIGH)(
            d=p_mid, g=p_mid, s=avdd, b=avdd
        )
        mp34 = _pmos(params.w_stack_p, params.l_stack, vth=MosVth.HIGH)(
            d=m35_gate_mid, g=m35_gate_mid, s=p_mid, b=avdd
        )

        # Explicit Monticelli floating battery.
        m24 = _nmos(params.w_m24, params.l_mont)(
            d=vgp, g=m24_gate_mid, s=vgn, b=agnd
        )
        m35 = _pmos(params.w_m35, params.l_mont)(
            d=vgn, g=m35_gate_mid, s=vgp, b=avdd
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
    @h.module
    class ClassAbOutputStage:
        vgp = h.Input()
        vgn = h.Input()
        vout = h.Output()
        avdd = h.Inout()
        agnd = h.Inout()

        ccp_mid, ccn_mid = h.Signals(2)

        # Page-12 common-source push-pull output stage.
        m2 = _pmos(params.w_out_p, params.l_out)(d=vout, g=vgp, s=avdd, b=avdd)
        m1 = _nmos(params.w_out_n, params.l_out)(d=vout, g=vgn, s=agnd, b=agnd)

        # Dual Rc-Cc compensation branches from VGP/VGN to Vout.
        rcp = h.Res(r=params.rc)(p=vgp, n=ccp_mid)
        ccp = h.Cap(c=params.cc)(p=ccp_mid, n=vout)
        rcn = h.Res(r=params.rc)(p=vgn, n=ccn_mid)
        ccn = h.Cap(c=params.cc)(p=ccn_mid, n=vout)

    return ClassAbOutputStage


@h.paramclass
class Page12CoreParams:
    frontend = h.Param(dtype=FrontEndParams, desc="Front-end sizing", default=FrontEndParams())
    monticelli = h.Param(dtype=MonticelliParams, desc="Monticelli sizing", default=MonticelliParams())
    output = h.Param(dtype=OutputStageParams, desc="Output-stage sizing", default=OutputStageParams())


@h.generator
def page12_analog_core(params: Page12CoreParams) -> h.Module:
    """Paper-oriented analog core with a unified central column and explicit top-level observability."""

    @h.module
    class Page12AnalogCore:
        vinp = h.Input()
        vinn = h.Input()
        avdd = h.Inout()
        agnd = h.Inout()
        vout = h.Output()

        tail_p = h.Inout()
        tail_n = h.Inout()
        vbias1 = h.Input()
        vbias2 = h.Input()
        vbias3 = h.Input()
        m24_gate_mid = h.Inout()
        m35_gate_mid = h.Inout()

        pnode_l = h.Inout()
        pnode_r = h.Inout()
        nnode_l = h.Inout()
        nnode_r = h.Inout()
        vref_mid = h.Inout()
        vgp = h.Inout()
        vgn = h.Inout()

        n_mid = h.Signal()
        p_mid = h.Signal()
        ccp_mid, ccn_mid = h.Signals(2)

        # Complementary rail-to-rail input pairs.
        pin_l = _pmos(params.frontend.w_in_p, params.frontend.l_in, vth=MosVth.LOW)(
            d=nnode_l, g=vinn, s=tail_p, b=avdd
        )
        pin_r = _pmos(params.frontend.w_in_p, params.frontend.l_in, vth=MosVth.LOW)(
            d=nnode_r, g=vinp, s=tail_p, b=avdd
        )
        nin_l = _nmos(params.frontend.w_in_n, params.frontend.l_in, vth=MosVth.LOW)(
            d=pnode_l, g=vinp, s=tail_n, b=agnd
        )
        nin_r = _nmos(params.frontend.w_in_n, params.frontend.l_in, vth=MosVth.LOW)(
            d=pnode_r, g=vinn, s=tail_n, b=agnd
        )

        # Left full reference branch: avdd -> p-stack -> vref_mid -> n-stack -> agnd.
        fc_p1_l = _pmos(params.frontend.w_pcas1, params.frontend.l_fold, vth=MosVth.HIGH)(
            d=pnode_l, g=vbias1, s=avdd, b=avdd
        )
        fc_p2_l = _pmos(params.frontend.w_pcas2, params.frontend.l_fold)(
            d=vref_mid, g=vbias2, s=pnode_l, b=avdd
        )
        fc_n1_l = _nmos(params.frontend.w_ncas, params.frontend.l_fold)(
            d=vref_mid, g=vbias3, s=nnode_l, b=agnd
        )
        fc_n2_l = _nmos(params.frontend.w_nmir, params.frontend.l_fold)(
            d=nnode_l, g=nnode_l, s=agnd, b=agnd
        )

        # Right split driver side: upper PMOS half ends at vgp, lower NMOS half starts at vgn.
        fc_p1_r = _pmos(params.frontend.w_pcas1, params.frontend.l_fold, vth=MosVth.HIGH)(
            d=pnode_r, g=vbias1, s=avdd, b=avdd
        )
        fc_p2_r = _pmos(params.frontend.w_pcas2, params.frontend.l_fold)(
            d=vgp, g=vbias2, s=pnode_r, b=avdd
        )
        fc_n1_r = _nmos(params.frontend.w_ncas, params.frontend.l_fold)(
            d=vgn, g=vbias3, s=nnode_r, b=agnd
        )
        fc_n2_r = _nmos(params.frontend.w_nmir, params.frontend.l_fold)(
            d=nnode_r, g=nnode_l, s=agnd, b=agnd
        )

        # Monticelli bias branches and floating battery.
        m23 = _nmos(params.monticelli.w_stack_n, params.monticelli.l_stack)(
            d=m24_gate_mid, g=m24_gate_mid, s=n_mid, b=agnd
        )
        m22 = _nmos(params.monticelli.w_stack_n, params.monticelli.l_stack)(
            d=n_mid, g=n_mid, s=agnd, b=agnd
        )
        m33 = _pmos(params.monticelli.w_stack_p, params.monticelli.l_stack, vth=MosVth.HIGH)(
            d=p_mid, g=p_mid, s=avdd, b=avdd
        )
        m34 = _pmos(params.monticelli.w_stack_p, params.monticelli.l_stack, vth=MosVth.HIGH)(
            d=m35_gate_mid, g=m35_gate_mid, s=p_mid, b=avdd
        )
        m24 = _nmos(params.monticelli.w_m24, params.monticelli.l_mont)(
            d=vgp, g=m24_gate_mid, s=vgn, b=agnd
        )
        m35 = _pmos(params.monticelli.w_m35, params.monticelli.l_mont)(
            d=vgn, g=m35_gate_mid, s=vgp, b=avdd
        )

        # Output stage begins only after the internal driver nodes.
        m2 = _pmos(params.output.w_out_p, params.output.l_out)(d=vout, g=vgp, s=avdd, b=avdd)
        m1 = _nmos(params.output.w_out_n, params.output.l_out)(d=vout, g=vgn, s=agnd, b=agnd)
        rcp = h.Res(r=params.output.rc)(p=vgp, n=ccp_mid)
        ccp = h.Cap(c=params.output.cc)(p=ccp_mid, n=vout)
        rcn = h.Res(r=params.output.rc)(p=vgn, n=ccn_mid)
        ccn = h.Cap(c=params.output.cc)(p=ccn_mid, n=vout)

    return Page12AnalogCore


@h.paramclass
class NeuronOaParams:
    inv = h.Param(dtype=InvParams, desc="Small inverters", default=InvParams())
    tg = h.Param(dtype=SwitchParams, desc="Transmission gate switches", default=SwitchParams())
    rail_sw = h.Param(
        dtype=SwitchParams,
        desc="Single-ended rail switches",
        default=SwitchParams(wp=5.0 * U, lp=0.30 * U, wn=4.0 * U, ln=0.30 * U),
    )
    bias = h.Param(dtype=OpaBiasGenParams, desc="OPA bias generator", default=OpaBiasGenParams())
    frontend = h.Param(dtype=FrontEndParams, desc="Page-12 folded first stage", default=FrontEndParams())
    monticelli = h.Param(dtype=MonticelliParams, desc="Page-12 Monticelli cell", default=MonticelliParams())
    output = h.Param(dtype=OutputStageParams, desc="Page-12 output stage", default=OutputStageParams())
    analog_core = h.Param(dtype=Page12CoreParams, desc="Unified page-12 analog core", default=Page12CoreParams())


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
        tail_p, tail_n, m24_gate_mid, m35_gate_mid = h.Signals(4)
        pnode_l, pnode_r, nnode_l, nnode_r = h.Signals(4)
        vref_mid = h.Signal()
        vgp, vgn = h.Signals(2)

    # Local control complements.
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

    # Keep the external reference pin interface from the current wrapper.
    NeuronCoreOaSky130.iref_sw = transmission_gate(params.tg)(
        a=NeuronCoreOaSky130.in0u25_oa,
        b=NeuronCoreOaSky130.iref_int,
        en=NeuronCoreOaSky130.d_en_oa,
        en_b=NeuronCoreOaSky130.d_en_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )

    # Reuse the existing idealized bias generator as wrapper support.
    NeuronCoreOaSky130.bias = OpaBiasGen(params.bias)(
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
        iref=NeuronCoreOaSky130.iref_int,
        i0_p=NeuronCoreOaSky130.tail_p,
        i0_n=NeuronCoreOaSky130.tail_n,
        ibias_p=NeuronCoreOaSky130.m24_gate_mid,
        ibias_n=NeuronCoreOaSky130.m35_gate_mid,
        vbias1=NeuronCoreOaSky130.vbias1,
        vbias2=NeuronCoreOaSky130.vbias2,
        vbias3=NeuronCoreOaSky130.vbias3,
    )

    # Optional AZ hook stays outside the core.
    NeuronCoreOaSky130.az_short = transmission_gate(params.tg)(
        a=NeuronCoreOaSky130.vgp,
        b=NeuronCoreOaSky130.vgn,
        en=NeuronCoreOaSky130.d_az_oa,
        en_b=NeuronCoreOaSky130.d_az_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )

    # Unified page-12 analog core.
    NeuronCoreOaSky130.analog_core = page12_analog_core(
        Page12CoreParams(
            frontend=params.frontend,
            monticelli=params.monticelli,
            output=params.output,
        )
    )(
        vinp=NeuronCoreOaSky130.vinp,
        vinn=NeuronCoreOaSky130.vinn,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
        vout=NeuronCoreOaSky130.vout,
        tail_p=NeuronCoreOaSky130.tail_p,
        tail_n=NeuronCoreOaSky130.tail_n,
        vbias1=NeuronCoreOaSky130.vbias1,
        vbias2=NeuronCoreOaSky130.vbias2,
        vbias3=NeuronCoreOaSky130.vbias3,
        m24_gate_mid=NeuronCoreOaSky130.m24_gate_mid,
        m35_gate_mid=NeuronCoreOaSky130.m35_gate_mid,
        pnode_l=NeuronCoreOaSky130.pnode_l,
        pnode_r=NeuronCoreOaSky130.pnode_r,
        nnode_l=NeuronCoreOaSky130.nnode_l,
        nnode_r=NeuronCoreOaSky130.nnode_r,
        vref_mid=NeuronCoreOaSky130.vref_mid,
        vgp=NeuronCoreOaSky130.vgp,
        vgn=NeuronCoreOaSky130.vgn,
    )

    # Product-level outer hooks kept outside the core.
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
