from __future__ import annotations

import hdl21 as h
from hdl21.primitives import MosVth

# Convenient SI-prefix shorthands.
U = h.Prefix.MICRO
N = h.Prefix.NANO
P = h.Prefix.PICO
F = h.Prefix.FEMTO


@h.paramclass
class InvParams:
    """Small CMOS inverter, used only for local control complements."""

    wp = h.Param(dtype=h.Scalar, desc="PMOS width", default=1.0 * U)
    lp = h.Param(dtype=h.Scalar, desc="PMOS length", default=0.50 * U)
    wn = h.Param(dtype=h.Scalar, desc="NMOS width", default=0.60 * U)
    ln = h.Param(dtype=h.Scalar, desc="NMOS length", default=0.50 * U)
    pvth = h.Param(dtype=MosVth, desc="PMOS threshold", default=MosVth.STD)
    nvth = h.Param(dtype=MosVth, desc="NMOS threshold", default=MosVth.STD)


@h.generator
def cmos_inv(params: InvParams) -> h.Module:
    @h.module
    class CmosInv:
        i = h.Input()
        o = h.Output()
        avdd = h.Inout()
        agnd = h.Inout()

        mp = h.Pmos(w=params.wp, l=params.lp, vth=params.pvth)(
            d=o, g=i, s=avdd, b=avdd
        )
        mn = h.Nmos(w=params.wn, l=params.ln, vth=params.nvth)(
            d=o, g=i, s=agnd, b=agnd
        )

    return CmosInv


@h.paramclass
class SwitchParams:
    """Generic analog switch device sizes."""

    wp = h.Param(dtype=h.Scalar, desc="PMOS width", default=4.0 * U)
    lp = h.Param(dtype=h.Scalar, desc="PMOS length", default=0.30 * U)
    wn = h.Param(dtype=h.Scalar, desc="NMOS width", default=3.0 * U)
    ln = h.Param(dtype=h.Scalar, desc="NMOS length", default=0.30 * U)
    pvth = h.Param(dtype=MosVth, desc="PMOS threshold", default=MosVth.LOW)
    nvth = h.Param(dtype=MosVth, desc="NMOS threshold", default=MosVth.LOW)


@h.generator
def transmission_gate(params: SwitchParams) -> h.Module:
    """Complementary analog switch."""

    @h.module
    class TransmissionGate:
        a = h.Inout()
        b = h.Inout()
        en = h.Input()
        en_b = h.Input()
        avdd = h.Inout()
        agnd = h.Inout()

        psw = h.Pmos(w=params.wp, l=params.lp, vth=params.pvth)(
            d=a, g=en_b, s=b, b=avdd
        )
        nsw = h.Nmos(w=params.wn, l=params.ln, vth=params.nvth)(
            d=a, g=en, s=b, b=agnd
        )

    return TransmissionGate


@h.generator
def nmos_switch(params: SwitchParams) -> h.Module:
    """Single-ended NMOS switch, typically used for ground-side clamping."""

    @h.module
    class NmosSwitch:
        a = h.Inout()
        b = h.Inout()
        en = h.Input()
        agnd = h.Inout()

        sw = h.Nmos(w=params.wn, l=params.ln, vth=params.nvth)(
            d=a, g=en, s=b, b=agnd
        )

    return NmosSwitch


@h.generator
def pmos_switch(params: SwitchParams) -> h.Module:
    """Single-ended PMOS switch, typically used for supply-side clamping."""

    @h.module
    class PmosSwitch:
        a = h.Inout()
        b = h.Inout()
        en_b = h.Input()
        avdd = h.Inout()

        sw = h.Pmos(w=params.wp, l=params.lp, vth=params.pvth)(
            d=a, g=en_b, s=b, b=avdd
        )

    return PmosSwitch


@h.paramclass
class DiffPairParams:
    """Simple differential pair."""

    w = h.Param(dtype=h.Scalar, desc="Input device width", default=2.0 * U)
    l = h.Param(dtype=h.Scalar, desc="Input device length", default=1.0 * U)
    npar = h.Param(dtype=int, desc="Parallel fingers", default=1)
    vth = h.Param(dtype=MosVth, desc="Threshold", default=MosVth.STD)


@h.generator
def nmos_diffpair(params: DiffPairParams) -> h.Module:
    @h.module
    class NmosDiffPair:
        inp = h.Input()
        inn = h.Input()
        outp = h.Output()
        outn = h.Output()
        tail = h.Inout()
        bulk = h.Inout()

        m1 = h.Nmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth)(
            d=outp, g=inp, s=tail, b=bulk
        )
        m2 = h.Nmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth)(
            d=outn, g=inn, s=tail, b=bulk
        )

    return NmosDiffPair


@h.generator
def pmos_diffpair(params: DiffPairParams) -> h.Module:
    @h.module
    class PmosDiffPair:
        inp = h.Input()
        inn = h.Input()
        outp = h.Output()
        outn = h.Output()
        tail = h.Inout()
        bulk = h.Inout()

        m1 = h.Pmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth)(
            d=outp, g=inp, s=tail, b=bulk
        )
        m2 = h.Pmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth)(
            d=outn, g=inn, s=tail, b=bulk
        )

    return PmosDiffPair


@h.paramclass
class CurrentSourceParams:
    """Single-transistor current source / sink."""

    w = h.Param(dtype=h.Scalar, desc="Device width", default=1.5 * U)
    l = h.Param(dtype=h.Scalar, desc="Device length", default=2.0 * U)
    npar = h.Param(dtype=int, desc="Parallel fingers", default=1)
    vth = h.Param(dtype=MosVth, desc="Threshold", default=MosVth.STD)


@h.generator
def tail_current_nmos(params: CurrentSourceParams) -> h.Module:
    @h.module
    class TailCurrentNmos:
        out = h.Inout()
        bias = h.Input()
        agnd = h.Inout()

        m = h.Nmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth)(
            d=out, g=bias, s=agnd, b=agnd
        )

    return TailCurrentNmos


@h.generator
def tail_current_pmos(params: CurrentSourceParams) -> h.Module:
    @h.module
    class TailCurrentPmos:
        out = h.Inout()
        bias = h.Input()
        avdd = h.Inout()

        m = h.Pmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth)(
            d=out, g=bias, s=avdd, b=avdd
        )

    return TailCurrentPmos


@h.paramclass
class CascodeBranchParams:
    """Two-device cascode bias branch."""

    w_src = h.Param(dtype=h.Scalar, desc="Source-device width", default=1.2 * U)
    l_src = h.Param(dtype=h.Scalar, desc="Source-device length", default=2.0 * U)
    w_cas = h.Param(dtype=h.Scalar, desc="Cascode width", default=1.0 * U)
    l_cas = h.Param(dtype=h.Scalar, desc="Cascode length", default=1.2 * U)
    src_vth = h.Param(dtype=MosVth, desc="Source-device threshold", default=MosVth.STD)
    cas_vth = h.Param(dtype=MosVth, desc="Cascode threshold", default=MosVth.STD)
    npar = h.Param(dtype=int, desc="Parallel fingers", default=1)


@h.generator
def pmos_cascode_source(params: CascodeBranchParams) -> h.Module:
    """PMOS cascode current-source branch from AVDD to an output node."""

    @h.module
    class PmosCascodeSource:
        out = h.Output()
        vbias_src = h.Input()
        vbias_cas = h.Input()
        avdd = h.Inout()

        mid = h.Signal()

        ms = h.Pmos(
            w=params.w_src, l=params.l_src, npar=params.npar, vth=params.src_vth
        )(d=mid, g=vbias_src, s=avdd, b=avdd)
        mc = h.Pmos(
            w=params.w_cas, l=params.l_cas, npar=params.npar, vth=params.cas_vth
        )(d=out, g=vbias_cas, s=mid, b=avdd)

    return PmosCascodeSource


@h.generator
def nmos_cascode_sink(params: CascodeBranchParams) -> h.Module:
    """NMOS cascode current-sink branch from an output node to AGND."""

    @h.module
    class NmosCascodeSink:
        out = h.Output()
        vbias_src = h.Input()
        vbias_cas = h.Input()
        agnd = h.Inout()

        mid = h.Signal()

        mc = h.Nmos(
            w=params.w_cas, l=params.l_cas, npar=params.npar, vth=params.cas_vth
        )(d=out, g=vbias_cas, s=mid, b=agnd)
        ms = h.Nmos(
            w=params.w_src, l=params.l_src, npar=params.npar, vth=params.src_vth
        )(d=mid, g=vbias_src, s=agnd, b=agnd)

    return NmosCascodeSink


@h.paramclass
class BiasGenParams:
    """Simple bias generator driven from the external current-reference pin."""

    ref_w = h.Param(dtype=h.Scalar, desc="Reference PMOS width", default=1.2 * U)
    ref_l = h.Param(dtype=h.Scalar, desc="Reference PMOS length", default=2.0 * U)
    p_tail_w = h.Param(dtype=h.Scalar, desc="PMOS tail-bias mirror width", default=1.2 * U)
    p_tail_l = h.Param(dtype=h.Scalar, desc="PMOS tail-bias mirror length", default=2.0 * U)
    p_cas_w = h.Param(dtype=h.Scalar, desc="PMOS cascode-bias mirror width", default=1.2 * U)
    p_cas_l = h.Param(dtype=h.Scalar, desc="PMOS cascode-bias mirror length", default=2.0 * U)
    n_tail_feed_w = h.Param(dtype=h.Scalar, desc="PMOS feed width for NMOS tail bias", default=1.0 * U)
    n_tail_feed_l = h.Param(dtype=h.Scalar, desc="PMOS feed length for NMOS tail bias", default=2.0 * U)
    n_cas_feed_w = h.Param(dtype=h.Scalar, desc="PMOS feed width for NMOS cascode bias", default=1.0 * U)
    n_cas_feed_l = h.Param(dtype=h.Scalar, desc="PMOS feed length for NMOS cascode bias", default=2.0 * U)
    n_tail_w = h.Param(dtype=h.Scalar, desc="NMOS tail-bias diode width", default=0.9 * U)
    n_tail_l = h.Param(dtype=h.Scalar, desc="NMOS tail-bias diode length", default=1.5 * U)
    n_cas_w = h.Param(dtype=h.Scalar, desc="NMOS cascode-bias diode width", default=0.9 * U)
    n_cas_l = h.Param(dtype=h.Scalar, desc="NMOS cascode-bias diode length", default=1.5 * U)


@h.generator
def bias_generator(params: BiasGenParams) -> h.Module:
    """
    Very small current-reference fanout.

    This is intentionally simple. It is good enough for an architectural cut,
    not a final low-drift bias tree.
    """

    @h.module
    class BiasGenerator:
        avdd = h.Inout()
        agnd = h.Inout()
        iref = h.Inout()

        vbp_tail = h.Output()
        vbp_cas = h.Output()
        vbn_tail = h.Output()
        vbn_cas = h.Output()

        # External current sink establishes the PMOS reference overdrive.
        mp_ref = h.Pmos(w=params.ref_w, l=params.ref_l, vth=MosVth.STD)(
            d=iref, g=iref, s=avdd, b=avdd
        )

        # PMOS bias nodes.
        mp_tail = h.Pmos(w=params.p_tail_w, l=params.p_tail_l, vth=MosVth.STD)(
            d=vbp_tail, g=iref, s=avdd, b=avdd
        )
        mp_cas = h.Pmos(w=params.p_cas_w, l=params.p_cas_l, vth=MosVth.STD)(
            d=vbp_cas, g=iref, s=avdd, b=avdd
        )

        # NMOS bias nodes are generated by mirrored PMOS currents through
        # diode-connected NMOS devices.
        mp_n_tail = h.Pmos(
            w=params.n_tail_feed_w, l=params.n_tail_feed_l, vth=MosVth.STD
        )(d=vbn_tail, g=iref, s=avdd, b=avdd)
        mn_tail = h.Nmos(w=params.n_tail_w, l=params.n_tail_l, vth=MosVth.STD)(
            d=vbn_tail, g=vbn_tail, s=agnd, b=agnd
        )

        mp_n_cas = h.Pmos(
            w=params.n_cas_feed_w, l=params.n_cas_feed_l, vth=MosVth.STD
        )(d=vbn_cas, g=iref, s=avdd, b=avdd)
        mn_cas = h.Nmos(w=params.n_cas_w, l=params.n_cas_l, vth=MosVth.STD)(
            d=vbn_cas, g=vbn_cas, s=agnd, b=agnd
        )

    return BiasGenerator
