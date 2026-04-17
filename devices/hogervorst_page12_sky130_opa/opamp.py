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
from .source.opa_bias import (
    BiasRefCore,
    BiasRefCoreParams,
    CurrentBiasKind,
    CurrentBiasLeg,
    CurrentBiasLegParams,
    OpaBiasGenParams,
    PmosCascodeSourceLeg,
    PmosCascodeSourceLegParams,
    PmosGateBiasedSourceLeg,
    PmosGateBiasedSourceLegParams,
)


# -----------------------------------------------------------------------------
# Device helpers
# -----------------------------------------------------------------------------


def _nmos(w, l, *, vth=MosVth.STD):
    """Sky130 core NMOS helper."""
    return h.Nmos(w=w, l=l, vth=vth, family=h.MosFamily.CORE)



def _pmos(w, l, *, vth=MosVth.STD):
    """Sky130 core PMOS helper."""
    return h.Pmos(w=w, l=l, vth=vth, family=h.MosFamily.CORE)


# -----------------------------------------------------------------------------
# Geometry parameter blocks
# -----------------------------------------------------------------------------


@h.paramclass
class FrontEndParams:
    """Page-11 / page-12 folded-cascode front-end geometry."""

    w_input_p = h.Param(dtype=h.Scalar, desc="PMOS input-pair width", default=8.0 * U)
    w_input_n = h.Param(dtype=h.Scalar, desc="NMOS input-pair width", default=4.0 * U)
    l_input = h.Param(dtype=h.Scalar, desc="Input-pair length", default=0.50 * U)

    w_pmos_vbias1 = h.Param(dtype=h.Scalar, desc="Top PMOS cascode-pair width", default=4.0 * U)
    w_pmos_vbias2 = h.Param(dtype=h.Scalar, desc="Lower PMOS cascode-pair width", default=4.0 * U)
    w_nmos_vbias3 = h.Param(dtype=h.Scalar, desc="Upper NMOS cascode-pair width", default=3.0 * U)
    w_nmos_mirror = h.Param(dtype=h.Scalar, desc="Bottom NMOS mirror width", default=3.0 * U)
    l_fold = h.Param(dtype=h.Scalar, desc="Folded-cascode device length", default=0.60 * U)


@h.paramclass
class MonticelliParams:
    """Page-12 explicit M22/M23, M24, M33/M34, M35 geometry."""

    w_m22_m23 = h.Param(dtype=h.Scalar, desc="NMOS diode-stack width for M22/M23", default=1.0 * U)
    w_m24 = h.Param(dtype=h.Scalar, desc="NMOS floating-cell width for M24", default=1.5 * U)
    w_m33_m34 = h.Param(dtype=h.Scalar, desc="PMOS diode-stack width for M33/M34", default=1.5 * U)
    w_m35 = h.Param(dtype=h.Scalar, desc="PMOS floating-cell width for M35", default=3.0 * U)
    l_stack = h.Param(dtype=h.Scalar, desc="Diode-stack length", default=0.60 * U)
    l_mont = h.Param(dtype=h.Scalar, desc="Monticelli-cell length", default=0.60 * U)


@h.paramclass
class OutputStageParams:
    """Page-12 output pair and dual Rc-Cc compensation."""

    w_m2 = h.Param(dtype=h.Scalar, desc="PMOS output-device width for M2", default=16.0 * U)
    w_m1 = h.Param(dtype=h.Scalar, desc="NMOS output-device width for M1", default=8.0 * U)
    l_out = h.Param(dtype=h.Scalar, desc="Output-device length", default=0.60 * U)
    rc = h.Param(dtype=h.Scalar, desc="Series compensation resistor", default=12_000)
    cc = h.Param(dtype=h.Scalar, desc="Compensation capacitor", default=9.0 * F)


@h.paramclass
class NeuronOaParams:
    # Shell helpers kept from the uploaded wrapper.
    inv = h.Param(dtype=InvParams, desc="Small inverters", default=InvParams())
    tg = h.Param(dtype=SwitchParams, desc="Transmission-gate switches", default=SwitchParams())
    rail_sw = h.Param(
        dtype=SwitchParams,
        desc="Single-ended rail switches",
        default=SwitchParams(wp=5.0 * U, lp=0.30 * U, wn=4.0 * U, ln=0.30 * U),
    )
    bias = h.Param(
        dtype=OpaBiasGenParams,
        desc="Retained only for compatibility with the larger project shell",
        default=OpaBiasGenParams(),
    )

    frontend = h.Param(dtype=FrontEndParams, desc="Page-12 folded-cascode front-end", default=FrontEndParams())
    monticelli = h.Param(dtype=MonticelliParams, desc="Page-12 Monticelli local bias network", default=MonticelliParams())
    output = h.Param(dtype=OutputStageParams, desc="Page-12 output stage", default=OutputStageParams())

    # Idealized debug-only bias hooks.
    # These are not the final silicon bias generator. They are local ideal
    # sources used only to make the textbook core easier to probe during bring-up.
    vbias1_V = h.Param(dtype=h.Scalar, desc="Ideal Vbias1 voltage", default=0.82383252916907)
    vbias2_V = h.Param(dtype=h.Scalar, desc="Ideal Vbias2 voltage", default=0.890730977583764)
    vbias3_V = h.Param(dtype=h.Scalar, desc="Ideal Vbias3 voltage", default=0.6335259806583905)

    i0_p_uA = h.Param(dtype=h.Scalar, desc="Ideal PMOS-input tail current I0 in uA", default=1.6)
    i0_n_uA = h.Param(dtype=h.Scalar, desc="Ideal NMOS-input tail current I0 in uA", default=1.6)

    # NMOS-side Monticelli stack debug source:
    # AVDD -> Idc -> vb_m24.
    ibias_nmos_stack_uA = h.Param(
        dtype=h.Scalar,
        desc="Ideal current injected from AVDD into vb_m24, in uA",
        default=0.45,
    )
    use_real_vb_m24_bias = h.Param(
        dtype=bool,
        desc="Use non-ideal current-bias leg for vb_m24 instead of ideal Idc",
        default=False,
    )
    use_cascoded_vb_m24_bias = h.Param(
        dtype=bool,
        desc="Use cascoded PMOS source leg for vb_m24 when the real leg is enabled",
        default=False,
    )
    use_local_vgp_vb_m24_bias = h.Param(
        dtype=bool,
        desc="Use a local PMOS source into vb_m24 gated by VGP",
        default=False,
    )

    # PMOS-side Monticelli stack debug source:
    # vb_m35 -> Idc -> AGND.
    ibias_pmos_stack_uA = h.Param(
        dtype=h.Scalar,
        desc="Ideal current sunk from vb_m35 into AGND, in uA",
        default=0.45,
    )
    vb_m35_V = h.Param(
        dtype=h.Scalar,
        desc="Legacy ideal voltage on vb_m35, retained only for quick rollback",
        default=1.05,
    )

    iref_term_ohm = h.Param(dtype=h.Scalar, desc="Termination for the external iref pin", default=1e6)


# -----------------------------------------------------------------------------
# Main module
# -----------------------------------------------------------------------------


@h.generator
def neuron_core_oa_sky130(params: NeuronOaParams) -> h.Module:
    """Sky130 retarget of the page-12 two-stage CMOS op-amp core.

    Scope note:
    - The textbook core is the folded-cascode front-end + local Monticelli class-AB
      network + output pair + Rc-Cc branches.
    - The wrapper logic for test/control pins is preserved from the uploaded file for
      project compatibility, but is clearly separated and commented as non-textbook shell.
    - The local ideal bias sources are debug-only abstractions. They are not meant to be
      signoff-correct bias generation.
    """

    @h.module
    class NeuronCoreOaSky130:
        # -----------------------------------------------------------------
        # External interface
        # -----------------------------------------------------------------
        avdd1p2 = h.Inout()
        agnd = h.Inout()

        vinp = h.Input()  # Vi1 in the methodology figures.
        vinn = h.Input()  # Vi2 in the methodology figures.
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

        # -----------------------------------------------------------------
        # Shell / control nodes (not part of the textbook op-amp core)
        # -----------------------------------------------------------------
        d_en_b, d_az_b, d_inf_b, d_tdi_b = h.Signals(4)
        iref_internal = h.Signal()

        # -----------------------------------------------------------------
        # Textbook core bias nodes
        # -----------------------------------------------------------------
        vbias1, vbias2, vbias3 = h.Signals(3)
        pmos_input_tail, nmos_input_tail = h.Signals(2)
        nref = h.Signal()
        vg_ibias_m24 = h.Signal()

        # -----------------------------------------------------------------
        # Folded-cascode first-stage nodes
        # -----------------------------------------------------------------
        fold_upper_left, fold_upper_right = h.Signals(2)
        fold_lower_left, fold_lower_right = h.Signals(2)

        # Left branch is a single summed node. Right branch produces VGP and VGN.
        sum_left = h.Signal()
        vgp, vgn = h.Signals(2)

        # -----------------------------------------------------------------
        # Local Monticelli bias nodes
        # -----------------------------------------------------------------
        # vb_m24 = gate(M24) = drain/gate(M23)
        # vb_m35 = gate(M35) = drain/gate(M34)
        vb_m24, vb_m35 = h.Signals(2)

        # -----------------------------------------------------------------
        # Compensation branch internal nodes
        # -----------------------------------------------------------------
        top_comp_mid, bot_comp_mid = h.Signals(2)

    dut = NeuronCoreOaSky130
    fp = params.frontend
    mp = params.monticelli
    op = params.output

    avdd = dut.avdd1p2
    vss = dut.agnd

    # ---------------------------------------------------------------------
    # Non-textbook shell logic preserved from the uploaded wrapper
    # ---------------------------------------------------------------------
    dut.inv_en = cmos_inv(params.inv)(i=dut.d_en_oa, o=dut.d_en_b, avdd=avdd, agnd=vss)
    dut.inv_az = cmos_inv(params.inv)(i=dut.d_az_oa, o=dut.d_az_b, avdd=avdd, agnd=vss)
    dut.inv_inf = cmos_inv(params.inv)(i=dut.d_inf_oa, o=dut.d_inf_b, avdd=avdd, agnd=vss)
    dut.inv_tdi = cmos_inv(params.inv)(i=dut.d_tdi, o=dut.d_tdi_b, avdd=avdd, agnd=vss)

    dut.iref_sw = transmission_gate(params.tg)(
        a=dut.in0u25_oa,
        b=dut.iref_internal,
        en=dut.d_en_oa,
        en_b=dut.d_en_b,
        avdd=avdd,
        agnd=vss,
    )
    dut.iref_term = h.Res(r=params.iref_term_ohm)(p=dut.iref_internal, n=vss)

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

    # ---------------------------------------------------------------------
    # Idealized debug-only biasing for the textbook core
    # ---------------------------------------------------------------------
    dut.vbias1_src = h.Vdc(dc=params.vbias1_V)(p=dut.vbias1, n=vss)
    dut.vbias2_src = h.Vdc(dc=params.vbias2_V)(p=dut.vbias2, n=vss)
    dut.vbias3_src = h.Vdc(dc=params.vbias3_V)(p=dut.vbias3, n=vss)

    # Page-11 / page-12 two I0 sources for the complementary rail-to-rail input stage.
    dut.i0_p_source = h.Idc(dc=params.i0_p_uA * 1e-6)(p=avdd, n=dut.pmos_input_tail)
    dut.i0_n_sink = h.Idc(dc=params.i0_n_uA * 1e-6)(p=dut.nmos_input_tail, n=vss)

    # Local reference core used by the non-ideal current-bias leg.
    dut.bias_ref = BiasRefCore(
        BiasRefCoreParams(
            ref_w=params.bias.ref_w,
            ref_l=params.bias.ref_l,
            nref_feed_w=params.bias.nref_feed_w,
            nref_feed_l=params.bias.nref_feed_l,
            nref_w=params.bias.nref_w,
            nref_l=params.bias.nref_l,
        )
    )(avdd=avdd, agnd=vss, iref=dut.iref_internal, nref=dut.nref)

    # Local textbook Monticelli debug biasing.
    # NMOS-side can be driven either by an ideal source or by a non-ideal
    # PMOS mirror leg for A/B comparison against the idealized baseline.
    if params.use_real_vb_m24_bias:
        if params.use_local_vgp_vb_m24_bias:
            dut.ibias_into_vb_m24 = PmosGateBiasedSourceLeg(
                PmosGateBiasedSourceLegParams(
                    out_w=params.bias.ibias_p_w,
                    out_l=params.bias.ibias_p_l,
                    vth=MosVth.HIGH,
                )
            )(avdd=avdd, out=dut.vb_m24, vg=dut.vgp)
        elif params.use_cascoded_vb_m24_bias:
            dut.vcasc_ibias_m24 = h.Signal()
            dut.ibias_into_vb_m24 = PmosCascodeSourceLeg(
                PmosCascodeSourceLegParams(
                    out_w=params.bias.ibias_p_w,
                    out_l=params.bias.ibias_p_l,
                    cascode_w=params.bias.ibias_p_w,
                    cascode_l=max(params.bias.ibias_p_l, 1.2),
                    vth=MosVth.HIGH,
                    sink_w=params.bias.nref_w,
                    sink_l=params.bias.nref_l,
                )
            )(
                avdd=avdd,
                agnd=vss,
                nref=dut.nref,
                out=dut.vb_m24,
                vg=dut.vg_ibias_m24,
                vcasc=dut.vcasc_ibias_m24,
            )
        else:
            dut.ibias_into_vb_m24 = CurrentBiasLeg(
                CurrentBiasLegParams(
                    kind=CurrentBiasKind.SOURCE,
                    out_w=params.bias.ibias_p_w,
                    out_l=params.bias.ibias_p_l,
                    vth=MosVth.HIGH,
                    ref_w=params.bias.nref_w,
                    ref_l=params.bias.nref_l,
                )
            )(avdd=avdd, agnd=vss, nref=dut.nref, out=dut.vb_m24, vg=dut.vg_ibias_m24)
    else:
        dut.ibias_into_vb_m24 = h.Idc(dc=params.ibias_nmos_stack_uA * 1e-6)(p=avdd, n=dut.vb_m24)

    # PMOS-side ideal current sink on the shared M34/M35 gate node.
    dut.ibias_from_vb_m35 = h.Idc(dc=params.ibias_pmos_stack_uA * 1e-6)(p=dut.vb_m35, n=vss)

    # ---------------------------------------------------------------------
    # Textbook core: folded-cascode rail-to-rail input stage
    # ---------------------------------------------------------------------
    # PMOS pair highlighted on page 11 / page 12:
    # left gate = Vi2 = vinn, right gate = Vi1 = vinp.
    dut.pmos_input_left = _pmos(fp.w_input_p, fp.l_input, vth=MosVth.LOW)(
        d=dut.fold_lower_left,
        g=dut.vinn,
        s=dut.pmos_input_tail,
        b=avdd,
    )
    dut.pmos_input_right = _pmos(fp.w_input_p, fp.l_input, vth=MosVth.LOW)(
        d=dut.fold_lower_right,
        g=dut.vinp,
        s=dut.pmos_input_tail,
        b=avdd,
    )

    # NMOS pair highlighted on page 11 / page 12:
    # left gate = Vi1 = vinp, right gate = Vi2 = vinn.
    dut.nmos_input_left = _nmos(fp.w_input_n, fp.l_input, vth=MosVth.LOW)(
        d=dut.fold_upper_left,
        g=dut.vinp,
        s=dut.nmos_input_tail,
        b=vss,
    )
    dut.nmos_input_right = _nmos(fp.w_input_n, fp.l_input, vth=MosVth.LOW)(
        d=dut.fold_upper_right,
        g=dut.vinn,
        s=dut.nmos_input_tail,
        b=vss,
    )

    # Top PMOS folded-cascode pair biased by Vbias1.
    dut.pmos_vbias1_left = _pmos(fp.w_pmos_vbias1, fp.l_fold, vth=MosVth.HIGH)(
        d=dut.fold_upper_left,
        g=dut.vbias1,
        s=avdd,
        b=avdd,
    )
    dut.pmos_vbias1_right = _pmos(fp.w_pmos_vbias1, fp.l_fold, vth=MosVth.HIGH)(
        d=dut.fold_upper_right,
        g=dut.vbias1,
        s=avdd,
        b=avdd,
    )

    # Lower PMOS folded-cascode pair biased by Vbias2.
    dut.pmos_vbias2_left = _pmos(fp.w_pmos_vbias2, fp.l_fold)(
        d=dut.sum_left,
        g=dut.vbias2,
        s=dut.fold_upper_left,
        b=avdd,
    )
    dut.pmos_vbias2_right = _pmos(fp.w_pmos_vbias2, fp.l_fold)(
        d=dut.vgp,
        g=dut.vbias2,
        s=dut.fold_upper_right,
        b=avdd,
    )

    # Upper NMOS folded-cascode pair biased by Vbias3.
    dut.nmos_vbias3_left = _nmos(fp.w_nmos_vbias3, fp.l_fold)(
        d=dut.sum_left,
        g=dut.vbias3,
        s=dut.fold_lower_left,
        b=vss,
    )
    dut.nmos_vbias3_right = _nmos(fp.w_nmos_vbias3, fp.l_fold)(
        d=dut.vgn,
        g=dut.vbias3,
        s=dut.fold_lower_right,
        b=vss,
    )

    # Bottom NMOS mirror pair.
    dut.nmos_mirror_left = _nmos(fp.w_nmos_mirror, fp.l_fold)(
        d=dut.fold_lower_left,
        g=dut.fold_lower_left,
        s=vss,
        b=vss,
    )
    dut.nmos_mirror_right = _nmos(fp.w_nmos_mirror, fp.l_fold)(
        d=dut.fold_lower_right,
        g=dut.fold_lower_left,
        s=vss,
        b=vss,
    )

    # Non-textbook calibration/debug short across VGP and VGN.
    dut.az_short = transmission_gate(params.tg)(
        a=dut.vgp,
        b=dut.vgn,
        en=dut.d_az_oa,
        en_b=dut.d_az_b,
        avdd=avdd,
        agnd=vss,
    )

    # ---------------------------------------------------------------------
    # Textbook core: page-12 local Monticelli network
    # ---------------------------------------------------------------------
    # NMOS-side diode stack:
    #   M23 upper diode-connected NMOS: drain/gate = vb_m24, source = VGN
    #   M22 lower diode-connected NMOS: drain/gate = VGN, source = AGND
    dut.m23 = _nmos(mp.w_m22_m23, mp.l_stack)(
        d=dut.vb_m24,
        g=dut.vb_m24,
        s=dut.vgn,
        b=vss,
    )
    dut.m22 = _nmos(mp.w_m22_m23, mp.l_stack)(
        d=dut.vgn,
        g=dut.vgn,
        s=vss,
        b=vss,
    )

    # PMOS-side diode stack:
    #   M33 upper diode-connected PMOS: drain/gate = VGP, source = AVDD
    #   M34 lower diode-connected PMOS: drain/gate = vb_m35, source = VGP
    dut.m33 = _pmos(mp.w_m33_m34, mp.l_stack, vth=MosVth.HIGH)(
        d=dut.vgp,
        g=dut.vgp,
        s=avdd,
        b=avdd,
    )
    dut.m34 = _pmos(mp.w_m33_m34, mp.l_stack, vth=MosVth.HIGH)(
        d=dut.vb_m35,
        g=dut.vb_m35,
        s=dut.vgp,
        b=avdd,
    )

    # Monticelli floating pair directly between VGP and VGN.
    dut.m24 = _nmos(mp.w_m24, mp.l_mont)(
        d=dut.vgp,
        g=dut.vb_m24,
        s=dut.vgn,
        b=vss,
    )
    dut.m35 = _pmos(mp.w_m35, mp.l_mont)(
        d=dut.vgn,
        g=dut.vb_m35,
        s=dut.vgp,
        b=avdd,
    )

    # ---------------------------------------------------------------------
    # Textbook core: output pair and dual Rc-Cc branches
    # ---------------------------------------------------------------------
    dut.m2 = _pmos(op.w_m2, op.l_out)(
        d=dut.vout,
        g=dut.vgp,
        s=avdd,
        b=avdd,
    )
    dut.m1 = _nmos(op.w_m1, op.l_out)(
        d=dut.vout,
        g=dut.vgn,
        s=vss,
        b=vss,
    )

    dut.rc_top = h.Res(r=op.rc)(p=dut.vgp, n=dut.top_comp_mid)
    dut.cc_top = h.Cap(c=op.cc)(p=dut.top_comp_mid, n=dut.vout)
    dut.rc_bot = h.Res(r=op.rc)(p=dut.vgn, n=dut.bot_comp_mid)
    dut.cc_bot = h.Cap(c=op.cc)(p=dut.bot_comp_mid, n=dut.vout)

    return NeuronCoreOaSky130


# -----------------------------------------------------------------------------
# PDK compilation helper
# -----------------------------------------------------------------------------


def compile_for_sky130(src):
    try:
        import sky130_hdl21 as sky130_pdk  # type: ignore
    except ImportError:
        import sky130 as sky130_pdk  # type: ignore

    sky130_pdk.compile(src)
    return src
