from __future__ import annotations

import hdl21 as h
from hdl21.primitives import MosVth

from .generators import (
    U,
    F,
    BiasGenParams,
    CascodeBranchParams,
    CurrentSourceParams,
    DiffPairParams,
    InvParams,
    SwitchParams,
    bias_generator,
    cmos_inv,
    nmos_cascode_sink,
    nmos_diffpair,
    nmos_switch,
    pmos_cascode_source,
    pmos_diffpair,
    pmos_switch,
    tail_current_nmos,
    tail_current_pmos,
    transmission_gate,
)


@h.paramclass
class FrontEndParams:
    """Complementary input stage plus high-resistance output nodes."""

    n_pair = h.Param(
        dtype=DiffPairParams,
        desc="NMOS input pair",
        default=DiffPairParams(w=1.8 * U, l=1.0 * U, npar=1, vth=MosVth.STD),
    )
    p_pair = h.Param(
        dtype=DiffPairParams,
        desc="PMOS input pair",
        default=DiffPairParams(w=2.2 * U, l=1.0 * U, npar=1, vth=MosVth.STD),
    )
    n_tail = h.Param(
        dtype=CurrentSourceParams,
        desc="NMOS tail sink",
        default=CurrentSourceParams(w=1.0 * U, l=2.0 * U, npar=1, vth=MosVth.STD),
    )
    p_tail = h.Param(
        dtype=CurrentSourceParams,
        desc="PMOS tail source",
        default=CurrentSourceParams(w=1.2 * U, l=2.0 * U, npar=1, vth=MosVth.STD),
    )
    p_load = h.Param(
        dtype=CascodeBranchParams,
        desc="PMOS cascode load",
        default=CascodeBranchParams(
            w_src=1.0 * U,
            l_src=2.0 * U,
            w_cas=0.9 * U,
            l_cas=1.2 * U,
            npar=1,
            src_vth=MosVth.STD,
            cas_vth=MosVth.STD,
        ),
    )
    n_load = h.Param(
        dtype=CascodeBranchParams,
        desc="NMOS cascode load",
        default=CascodeBranchParams(
            w_src=0.9 * U,
            l_src=2.0 * U,
            w_cas=0.9 * U,
            l_cas=1.2 * U,
            npar=1,
            src_vth=MosVth.STD,
            cas_vth=MosVth.STD,
        ),
    )


@h.generator
def complementary_cascode_frontend(params: FrontEndParams) -> h.Module:
    """
    Structural first stage inspired by the rail-to-rail folded/cascode front end.

    It is intentionally lighter than the exact Hogervorst schematic, but keeps the
    two main ideas: complementary input pairs and high-resistance internal nodes.
    """

    @h.module
    class ComplementaryCascodeFrontEnd:
        vinp = h.Input()
        vinn = h.Input()
        avdd = h.Inout()
        agnd = h.Inout()

        vbp_tail = h.Input()
        vbp_cas = h.Input()
        vbn_tail = h.Input()
        vbn_cas = h.Input()

        drv_p = h.Output()
        drv_n = h.Output()

        p_tail_node = h.Signal()
        n_tail_node = h.Signal()

        # Complementary differential pairs.
        # The PMOS pair drains are intentionally crossed to align small-signal polarity
        # with the NMOS pair.
        p_tail = tail_current_pmos(params.p_tail)(
            out=p_tail_node, bias=vbp_tail, avdd=avdd
        )
        p_in = pmos_diffpair(params.p_pair)(
            inp=vinp,
            inn=vinn,
            outp=drv_n,
            outn=drv_p,
            tail=p_tail_node,
            bulk=avdd,
        )

        n_tail = tail_current_nmos(params.n_tail)(
            out=n_tail_node, bias=vbn_tail, agnd=agnd
        )
        n_in = nmos_diffpair(params.n_pair)(
            inp=vinp,
            inn=vinn,
            outp=drv_p,
            outn=drv_n,
            tail=n_tail_node,
            bulk=agnd,
        )

        # High-resistance loads for gain.
        pld_p = pmos_cascode_source(params.p_load)(
            out=drv_p, vbias_src=vbp_tail, vbias_cas=vbp_cas, avdd=avdd
        )
        pld_n = pmos_cascode_source(params.p_load)(
            out=drv_n, vbias_src=vbp_tail, vbias_cas=vbp_cas, avdd=avdd
        )
        nld_p = nmos_cascode_sink(params.n_load)(
            out=drv_p, vbias_src=vbn_tail, vbias_cas=vbn_cas, agnd=agnd
        )
        nld_n = nmos_cascode_sink(params.n_load)(
            out=drv_n, vbias_src=vbn_tail, vbias_cas=vbn_cas, agnd=agnd
        )

    return ComplementaryCascodeFrontEnd


@h.paramclass
class MonticelliParams:
    """Simplified Monticelli-style gate-drive cell."""

    p_stack_w = h.Param(dtype=h.Scalar, desc="PMOS bias stack width", default=1.2 * U)
    p_stack_l = h.Param(dtype=h.Scalar, desc="PMOS bias stack length", default=1.0 * U)
    n_stack_w = h.Param(dtype=h.Scalar, desc="NMOS bias stack width", default=1.0 * U)
    n_stack_l = h.Param(dtype=h.Scalar, desc="NMOS bias stack length", default=1.0 * U)
    bridge_p_w = h.Param(dtype=h.Scalar, desc="PMOS bridge width", default=2.5 * U)
    bridge_p_l = h.Param(dtype=h.Scalar, desc="PMOS bridge length", default=0.50 * U)
    bridge_n_w = h.Param(dtype=h.Scalar, desc="NMOS bridge width", default=2.0 * U)
    bridge_n_l = h.Param(dtype=h.Scalar, desc="NMOS bridge length", default=0.50 * U)


@h.generator
def monticelli_cell(params: MonticelliParams) -> h.Module:
    """
    Simplified Monticelli-inspired class-AB bias cell.

    This is not a paper-exact transistor-for-transistor clone.
    It preserves the two important functions:
    1. quiescent separation between VGP and VGN,
    2. complementary modulation of that separation by the first stage.
    """

    @h.module
    class MonticelliCell:
        drv_p = h.Input()
        drv_n = h.Input()
        vgp = h.Output()
        vgn = h.Output()
        avdd = h.Inout()
        agnd = h.Inout()

        p_mid = h.Signal()
        n_mid = h.Signal()

        # M33-M34 style PMOS bias stack.
        mp33 = h.Pmos(w=params.p_stack_w, l=params.p_stack_l, vth=MosVth.STD)(
            d=p_mid, g=p_mid, s=avdd, b=avdd
        )
        mp34 = h.Pmos(w=params.p_stack_w, l=params.p_stack_l, vth=MosVth.STD)(
            d=vgp, g=vgp, s=p_mid, b=avdd
        )

        # M22-M23 style NMOS bias stack.
        mn22 = h.Nmos(w=params.n_stack_w, l=params.n_stack_l, vth=MosVth.STD)(
            d=n_mid, g=n_mid, s=agnd, b=agnd
        )
        mn23 = h.Nmos(w=params.n_stack_w, l=params.n_stack_l, vth=MosVth.STD)(
            d=vgn, g=vgn, s=n_mid, b=agnd
        )

        # M24 / M35 inspired bridge.
        m24 = h.Nmos(w=params.bridge_n_w, l=params.bridge_n_l, vth=MosVth.STD)(
            d=vgp, g=drv_n, s=vgn, b=agnd
        )
        m35 = h.Pmos(w=params.bridge_p_w, l=params.bridge_p_l, vth=MosVth.STD)(
            d=vgn, g=drv_p, s=vgp, b=avdd
        )

    return MonticelliCell


@h.paramclass
class OutputStageParams:
    """Push-pull class-AB output stage with dual compensation branches."""

    wp_out = h.Param(dtype=h.Scalar, desc="PMOS output width", default=14.0 * U)
    lp_out = h.Param(dtype=h.Scalar, desc="PMOS output length", default=0.50 * U)
    wn_out = h.Param(dtype=h.Scalar, desc="NMOS output width", default=9.0 * U)
    ln_out = h.Param(dtype=h.Scalar, desc="NMOS output length", default=0.50 * U)
    npar_p = h.Param(dtype=int, desc="PMOS parallel fingers", default=1)
    npar_n = h.Param(dtype=int, desc="NMOS parallel fingers", default=1)
    header = h.Param(
        dtype=SwitchParams,
        desc="Supply header switch sizing",
        default=SwitchParams(wp=5.0 * U, lp=0.30 * U, wn=3.0 * U, ln=0.30 * U),
    )
    footer = h.Param(
        dtype=SwitchParams,
        desc="Ground footer switch sizing",
        default=SwitchParams(wp=5.0 * U, lp=0.30 * U, wn=4.0 * U, ln=0.30 * U),
    )
    rc = h.Param(dtype=h.Scalar, desc="Series compensation resistor", default=50_000)
    cc = h.Param(dtype=h.Scalar, desc="Compensation capacitor", default=300 * F)


@h.generator
def classab_output_stage(params: OutputStageParams) -> h.Module:
    @h.module
    class ClassAbOutputStage:
        vgp = h.Input()
        vgn = h.Input()
        vout = h.Output()
        avdd = h.Inout()
        agnd = h.Inout()

        d_en_oa = h.Input()
        d_en_b = h.Input()
        d_inf_oa = h.Input()
        d_inf_b = h.Input()

        psrc1, psrc = h.Signals(2)
        nsrc1, nsrc = h.Signals(2)
        ccp_mid, ccn_mid = h.Signals(2)

        # Output-stage supply gating: both d_en and d_inf must be asserted.
        phead1 = pmos_switch(params.header)(
            a=avdd, b=psrc1, en_b=d_en_b, avdd=avdd
        )
        phead2 = pmos_switch(params.header)(
            a=psrc1, b=psrc, en_b=d_inf_b, avdd=avdd
        )
        nfoot1 = nmos_switch(params.footer)(
            a=nsrc, b=nsrc1, en=d_inf_oa, agnd=agnd
        )
        nfoot2 = nmos_switch(params.footer)(
            a=nsrc1, b=agnd, en=d_en_oa, agnd=agnd
        )

        mp_out = h.Pmos(w=params.wp_out, l=params.lp_out, npar=params.npar_p, vth=MosVth.STD)(
            d=vout, g=vgp, s=psrc, b=avdd
        )
        mn_out = h.Nmos(w=params.wn_out, l=params.ln_out, npar=params.npar_n, vth=MosVth.STD)(
            d=vout, g=vgn, s=nsrc, b=agnd
        )

        # Dual Miller-style compensation branches.
        rcp = h.Res(r=params.rc)(p=vgp, n=ccp_mid)
        ccp = h.Cap(c=params.cc)(p=ccp_mid, n=vout)
        rcn = h.Res(r=params.rc)(p=vgn, n=ccn_mid)
        ccn = h.Cap(c=params.cc)(p=ccn_mid, n=vout)

    return ClassAbOutputStage


@h.paramclass
class NeuronOaParams:
    """Top-level parameters for the Sky130 architectural implementation."""

    inv = h.Param(dtype=InvParams, desc="Small inverters", default=InvParams())
    tg = h.Param(dtype=SwitchParams, desc="Transmission gate switches", default=SwitchParams())
    rail_sw = h.Param(
        dtype=SwitchParams,
        desc="Single-ended rail switches",
        default=SwitchParams(wp=5.0 * U, lp=0.30 * U, wn=4.0 * U, ln=0.30 * U),
    )
    bias = h.Param(dtype=BiasGenParams, desc="Bias generator", default=BiasGenParams())
    frontend = h.Param(dtype=FrontEndParams, desc="Input / gain stage", default=FrontEndParams())
    monticelli = h.Param(
        dtype=MonticelliParams,
        desc="Monticelli-like AB cell",
        default=MonticelliParams(),
    )
    output = h.Param(dtype=OutputStageParams, desc="Output stage", default=OutputStageParams())


@h.generator
def neuron_core_oa_sky130(params: NeuronOaParams) -> h.Module:
    """
    Sky130-oriented architectural implementation of the two-stage RR/class-AB op-amp.

    Important notes:
    - Pin names are kept compatible with the uploaded NASP requirements.
    - The analog core is structural and synthesizable to a transistor-level netlist.
    - Offset auto-zero storage and scan-chain logic are intentionally left as light hooks,
      not full signoff-ready implementations.
    """

    @h.module
    class NeuronCoreOaSky130:
        # Functional analog interface.
        avdd1p2 = h.Inout()
        agnd = h.Inout()
        vinp = h.Input()
        vinn = h.Input()
        vout = h.Output()
        in0u25_oa = h.Inout()
        vbase = h.Inout()
        vfeed = h.Inout()

        # Control interface.
        d_en_oa = h.Input()
        d_az_oa = h.Input()
        d_inf_oa = h.Input()

        # Test interface.
        vtest = h.Inout()
        d_treset_oa = h.Input()
        d_tcki = h.Input()
        d_tcko = h.Output()
        d_tdi = h.Input()
        d_tdo = h.Output()

        # Internal control complements.
        d_en_b, d_az_b, d_inf_b, d_tdi_b = h.Signals(4)

        # Bias and core nodes.
        iref_int = h.Signal()
        vbp_tail, vbp_cas, vbn_tail, vbn_cas = h.Signals(4)
        drv_p, drv_n = h.Signals(2)
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

    # Disconnect the external reference pin in disabled mode.
    NeuronCoreOaSky130.iref_sw = transmission_gate(params.tg)(
        a=NeuronCoreOaSky130.in0u25_oa,
        b=NeuronCoreOaSky130.iref_int,
        en=NeuronCoreOaSky130.d_en_oa,
        en_b=NeuronCoreOaSky130.d_en_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )

    # Bias generation.
    NeuronCoreOaSky130.bias = bias_generator(params.bias)(
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
        iref=NeuronCoreOaSky130.iref_int,
        vbp_tail=NeuronCoreOaSky130.vbp_tail,
        vbp_cas=NeuronCoreOaSky130.vbp_cas,
        vbn_tail=NeuronCoreOaSky130.vbn_tail,
        vbn_cas=NeuronCoreOaSky130.vbn_cas,
    )

    # Disabled-mode bias clamps. This approximates the spec requirement that current
    # sources and mirrors collapse to their supply rails when disabled.
    NeuronCoreOaSky130.clamp_vbp_tail = pmos_switch(params.rail_sw)(
        a=NeuronCoreOaSky130.avdd1p2,
        b=NeuronCoreOaSky130.vbp_tail,
        en_b=NeuronCoreOaSky130.d_en_oa,
        avdd=NeuronCoreOaSky130.avdd1p2,
    )
    NeuronCoreOaSky130.clamp_vbp_cas = pmos_switch(params.rail_sw)(
        a=NeuronCoreOaSky130.avdd1p2,
        b=NeuronCoreOaSky130.vbp_cas,
        en_b=NeuronCoreOaSky130.d_en_oa,
        avdd=NeuronCoreOaSky130.avdd1p2,
    )
    NeuronCoreOaSky130.clamp_vbn_tail = nmos_switch(params.rail_sw)(
        a=NeuronCoreOaSky130.vbn_tail,
        b=NeuronCoreOaSky130.agnd,
        en=NeuronCoreOaSky130.d_en_b,
        agnd=NeuronCoreOaSky130.agnd,
    )
    NeuronCoreOaSky130.clamp_vbn_cas = nmos_switch(params.rail_sw)(
        a=NeuronCoreOaSky130.vbn_cas,
        b=NeuronCoreOaSky130.agnd,
        en=NeuronCoreOaSky130.d_en_b,
        agnd=NeuronCoreOaSky130.agnd,
    )

    # First stage.
    NeuronCoreOaSky130.frontend = complementary_cascode_frontend(params.frontend)(
        vinp=NeuronCoreOaSky130.vinp,
        vinn=NeuronCoreOaSky130.vinn,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
        vbp_tail=NeuronCoreOaSky130.vbp_tail,
        vbp_cas=NeuronCoreOaSky130.vbp_cas,
        vbn_tail=NeuronCoreOaSky130.vbn_tail,
        vbn_cas=NeuronCoreOaSky130.vbn_cas,
        drv_p=NeuronCoreOaSky130.drv_p,
        drv_n=NeuronCoreOaSky130.drv_n,
    )

    # Calibration hook: short the internal differential nodes during AZ.
    # This is only a placeholder for a future sampled-offset cell.
    NeuronCoreOaSky130.az_short = transmission_gate(params.tg)(
        a=NeuronCoreOaSky130.drv_p,
        b=NeuronCoreOaSky130.drv_n,
        en=NeuronCoreOaSky130.d_az_oa,
        en_b=NeuronCoreOaSky130.d_az_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )

    # Monticelli-inspired class-AB control cell.
    NeuronCoreOaSky130.mont = monticelli_cell(params.monticelli)(
        drv_p=NeuronCoreOaSky130.drv_p,
        drv_n=NeuronCoreOaSky130.drv_n,
        vgp=NeuronCoreOaSky130.vgp,
        vgn=NeuronCoreOaSky130.vgn,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )

    # Output-gate clamps for non-inference modes.
    # Using two parallel clamps on each side gives the equivalent of
    #   disabled OR not-inference
    # without adding explicit digital logic.
    NeuronCoreOaSky130.vgp_clamp_inf = pmos_switch(params.rail_sw)(
        a=NeuronCoreOaSky130.avdd1p2,
        b=NeuronCoreOaSky130.vgp,
        en_b=NeuronCoreOaSky130.d_inf_oa,
        avdd=NeuronCoreOaSky130.avdd1p2,
    )
    NeuronCoreOaSky130.vgp_clamp_dis = pmos_switch(params.rail_sw)(
        a=NeuronCoreOaSky130.avdd1p2,
        b=NeuronCoreOaSky130.vgp,
        en_b=NeuronCoreOaSky130.d_en_oa,
        avdd=NeuronCoreOaSky130.avdd1p2,
    )
    NeuronCoreOaSky130.vgn_clamp_inf = nmos_switch(params.rail_sw)(
        a=NeuronCoreOaSky130.vgn,
        b=NeuronCoreOaSky130.agnd,
        en=NeuronCoreOaSky130.d_inf_b,
        agnd=NeuronCoreOaSky130.agnd,
    )
    NeuronCoreOaSky130.vgn_clamp_dis = nmos_switch(params.rail_sw)(
        a=NeuronCoreOaSky130.vgn,
        b=NeuronCoreOaSky130.agnd,
        en=NeuronCoreOaSky130.d_en_b,
        agnd=NeuronCoreOaSky130.agnd,
    )

    # Class-AB output stage.
    NeuronCoreOaSky130.output_stage = classab_output_stage(params.output)(
        vgp=NeuronCoreOaSky130.vgp,
        vgn=NeuronCoreOaSky130.vgn,
        vout=NeuronCoreOaSky130.vout,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
        d_en_oa=NeuronCoreOaSky130.d_en_oa,
        d_en_b=NeuronCoreOaSky130.d_en_b,
        d_inf_oa=NeuronCoreOaSky130.d_inf_oa,
        d_inf_b=NeuronCoreOaSky130.d_inf_b,
    )

    # Auxiliary switches required by the product-level spec.
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

    # Output-to-test switch. The full scan/daisy-chain controller is left for digital integration;
    # here d_tdi is used as the architectural placeholder enable.
    NeuronCoreOaSky130.vout_to_vtest = transmission_gate(params.tg)(
        a=NeuronCoreOaSky130.vout,
        b=NeuronCoreOaSky130.vtest,
        en=NeuronCoreOaSky130.d_tdi,
        en_b=NeuronCoreOaSky130.d_tdi_b,
        avdd=NeuronCoreOaSky130.avdd1p2,
        agnd=NeuronCoreOaSky130.agnd,
    )

    # Scan-chain pass-through placeholders.
    NeuronCoreOaSky130.tck_short = h.Short()(  # Architectural stub
        p=NeuronCoreOaSky130.d_tcki,
        n=NeuronCoreOaSky130.d_tcko,
    )
    NeuronCoreOaSky130.tdi_short = h.Short()(  # Architectural stub
        p=NeuronCoreOaSky130.d_tdi,
        n=NeuronCoreOaSky130.d_tdo,
    )

    # d_treset_oa is intentionally reserved for the future scan / trim storage logic.
    return NeuronCoreOaSky130


def compile_for_sky130(src):
    """
    Compile generic HDL21 primitives to Sky130 external modules.

    Newer package releases use `sky130_hdl21`, while older Hdl21 trees used `sky130`.
    This helper accepts either.
    """

    try:
        import sky130_hdl21 as sky130_pdk  # type: ignore
    except ImportError:
        import sky130 as sky130_pdk  # type: ignore

    sky130_pdk.compile(src)
    return src
