import hdl21 as h
from hdl21.primitives import MosVth
from enum import Enum


# Sky130 MOS wrappers expect geometry values in microns.
U = 1.0


class CurrentBiasKind(str, Enum):
    SOURCE = "source"
    SINK = "sink"


@h.paramclass
class OpaBiasGenParams:
    """Simple mirror-derived bias generator for OPA shell and frontend biases."""

    ref_w = h.Param(dtype=h.Scalar, desc="Reference PMOS width", default=1.2 * U)
    ref_l = h.Param(dtype=h.Scalar, desc="Reference PMOS length", default=2.0 * U)
    nref_feed_w = h.Param(dtype=h.Scalar, desc="PMOS feed width for the NMOS reference diode", default=1.0 * U)
    nref_feed_l = h.Param(dtype=h.Scalar, desc="PMOS feed length for the NMOS reference diode", default=2.0 * U)
    nref_w = h.Param(dtype=h.Scalar, desc="NMOS reference-diode width", default=0.9 * U)
    nref_l = h.Param(dtype=h.Scalar, desc="NMOS reference-diode length", default=1.5 * U)

    i0_p_w = h.Param(dtype=h.Scalar, desc="PMOS output-device width for I0 tail source", default=3.0 * U)
    i0_p_l = h.Param(dtype=h.Scalar, desc="PMOS output-device length for I0 tail source", default=0.8 * U)
    i0_n_w = h.Param(dtype=h.Scalar, desc="NMOS output-device width for I0 tail sink", default=2.0 * U)
    i0_n_l = h.Param(dtype=h.Scalar, desc="NMOS output-device length for I0 tail sink", default=0.8 * U)
    ibias_p_w = h.Param(dtype=h.Scalar, desc="PMOS output-device width for Monticelli PMOS source", default=1.5 * U)
    ibias_p_l = h.Param(dtype=h.Scalar, desc="PMOS output-device length for Monticelli PMOS source", default=1.0 * U)
    ibias_n_w = h.Param(dtype=h.Scalar, desc="NMOS output-device width for Monticelli NMOS sink", default=1.0 * U)
    ibias_n_l = h.Param(dtype=h.Scalar, desc="NMOS output-device length for Monticelli NMOS sink", default=1.0 * U)
    bias1_p_w = h.Param(dtype=h.Scalar, desc="PMOS bias-device width for frontend vbias1", default=4.0 * U)
    bias1_p_l = h.Param(dtype=h.Scalar, desc="PMOS bias-device length for frontend vbias1", default=0.6 * U)
    bias2_p_w = h.Param(dtype=h.Scalar, desc="PMOS bias-device width for frontend vbias2", default=4.0 * U)
    bias2_p_l = h.Param(dtype=h.Scalar, desc="PMOS bias-device length for frontend vbias2", default=0.6 * U)
    bias3_n_w = h.Param(dtype=h.Scalar, desc="NMOS bias-device width for frontend vbias3", default=3.0 * U)
    bias3_n_l = h.Param(dtype=h.Scalar, desc="NMOS bias-device length for frontend vbias3", default=0.6 * U)


@h.paramclass
class BiasRefCoreParams:
    ref_w = h.Param(dtype=h.Scalar, desc="Reference PMOS width", default=1.2 * U)
    ref_l = h.Param(dtype=h.Scalar, desc="Reference PMOS length", default=2.0 * U)
    nref_feed_w = h.Param(dtype=h.Scalar, desc="PMOS feed width for the NMOS reference diode", default=1.0 * U)
    nref_feed_l = h.Param(dtype=h.Scalar, desc="PMOS feed length for the NMOS reference diode", default=2.0 * U)
    nref_w = h.Param(dtype=h.Scalar, desc="NMOS reference-diode width", default=0.9 * U)
    nref_l = h.Param(dtype=h.Scalar, desc="NMOS reference-diode length", default=1.5 * U)


@h.paramclass
class PmosMirrorSourceLegParams:
    out_w = h.Param(dtype=h.Scalar, desc="PMOS output width", default=3.0 * U)
    out_l = h.Param(dtype=h.Scalar, desc="PMOS output length", default=0.8 * U)
    vth = h.Param(dtype=MosVth, desc="PMOS threshold flavor", default=MosVth.HIGH)
    sink_w = h.Param(dtype=h.Scalar, desc="NMOS sink width", default=0.9 * U)
    sink_l = h.Param(dtype=h.Scalar, desc="NMOS sink length", default=1.5 * U)


@h.paramclass
class PmosCascodeSourceLegParams:
    out_w = h.Param(dtype=h.Scalar, desc="PMOS output width", default=3.0 * U)
    out_l = h.Param(dtype=h.Scalar, desc="PMOS output length", default=0.8 * U)
    cascode_w = h.Param(dtype=h.Scalar, desc="PMOS cascode width", default=3.0 * U)
    cascode_l = h.Param(dtype=h.Scalar, desc="PMOS cascode length", default=1.2 * U)
    vth = h.Param(dtype=MosVth, desc="PMOS threshold flavor", default=MosVth.HIGH)
    sink_w = h.Param(dtype=h.Scalar, desc="NMOS sink width", default=0.9 * U)
    sink_l = h.Param(dtype=h.Scalar, desc="NMOS sink length", default=1.5 * U)


@h.paramclass
class PmosGateBiasedSourceLegParams:
    out_w = h.Param(dtype=h.Scalar, desc="PMOS output width", default=3.0 * U)
    out_l = h.Param(dtype=h.Scalar, desc="PMOS output length", default=0.8 * U)
    vth = h.Param(dtype=MosVth, desc="PMOS threshold flavor", default=MosVth.HIGH)


@h.paramclass
class NmosMirrorSinkLegParams:
    out_w = h.Param(dtype=h.Scalar, desc="NMOS output width", default=2.0 * U)
    out_l = h.Param(dtype=h.Scalar, desc="NMOS output length", default=0.8 * U)
    vth = h.Param(dtype=MosVth, desc="NMOS threshold flavor", default=MosVth.STD)
    feed_w = h.Param(dtype=h.Scalar, desc="PMOS feed width", default=2.0 * U)
    feed_l = h.Param(dtype=h.Scalar, desc="PMOS feed length", default=0.8 * U)


@h.paramclass
class CurrentBiasLegParams:
    kind = h.Param(dtype=CurrentBiasKind, desc="Whether this leg is a PMOS source or NMOS sink", default=CurrentBiasKind.SOURCE)
    out_w = h.Param(dtype=h.Scalar, desc="Output-device width", default=3.0 * U)
    out_l = h.Param(dtype=h.Scalar, desc="Output-device length", default=0.8 * U)
    vth = h.Param(dtype=MosVth, desc="Output-device threshold flavor", default=MosVth.HIGH)
    ref_w = h.Param(dtype=h.Scalar, desc="Reference-side helper-device width", default=0.9 * U)
    ref_l = h.Param(dtype=h.Scalar, desc="Reference-side helper-device length", default=1.5 * U)


@h.paramclass
class PmosBiasVoltageLegParams:
    p_w = h.Param(dtype=h.Scalar, desc="PMOS diode width", default=4.0 * U)
    p_l = h.Param(dtype=h.Scalar, desc="PMOS diode length", default=0.6 * U)
    p_vth = h.Param(dtype=MosVth, desc="PMOS threshold flavor", default=MosVth.HIGH)
    sink_w = h.Param(dtype=h.Scalar, desc="NMOS sink width", default=0.9 * U)
    sink_l = h.Param(dtype=h.Scalar, desc="NMOS sink length", default=1.5 * U)


@h.paramclass
class NmosBiasVoltageLegParams:
    n_w = h.Param(dtype=h.Scalar, desc="NMOS diode width", default=3.0 * U)
    n_l = h.Param(dtype=h.Scalar, desc="NMOS diode length", default=0.6 * U)
    feed_w = h.Param(dtype=h.Scalar, desc="PMOS feed width", default=3.0 * U)
    feed_l = h.Param(dtype=h.Scalar, desc="PMOS feed length", default=0.6 * U)


@h.generator
def BiasRefCore(params: BiasRefCoreParams) -> h.Module:
    @h.module
    class _BiasRefCore:
        avdd = h.Inout()
        agnd = h.Inout()
        iref = h.Inout()
        nref = h.Output()

        mp_ref = h.Pmos(w=params.ref_w, l=params.ref_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=iref, g=iref, s=avdd, b=avdd
        )
        mp_nref_feed = h.Pmos(
            w=params.nref_feed_w, l=params.nref_feed_l, vth=MosVth.STD, family=h.MosFamily.CORE
        )(d=nref, g=iref, s=avdd, b=avdd)
        mn_ref = h.Nmos(
            w=params.nref_w, l=params.nref_l, vth=MosVth.STD, family=h.MosFamily.CORE
        )(d=nref, g=nref, s=agnd, b=agnd)

    return _BiasRefCore


@h.generator
def PmosMirrorSourceLeg(params: PmosMirrorSourceLegParams) -> h.Module:
    @h.module
    class _PmosMirrorSourceLeg:
        avdd = h.Inout()
        agnd = h.Inout()
        nref = h.Input()
        out = h.Inout()
        vg = h.Output()

        mp_ref = h.Pmos(w=params.out_w, l=params.out_l, vth=params.vth, family=h.MosFamily.CORE)(
            d=vg, g=vg, s=avdd, b=avdd
        )
        mn_sink = h.Nmos(w=params.sink_w, l=params.sink_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=vg, g=nref, s=agnd, b=agnd
        )
        mp_out = h.Pmos(w=params.out_w, l=params.out_l, vth=params.vth, family=h.MosFamily.CORE)(
            d=out, g=vg, s=avdd, b=avdd
        )

    return _PmosMirrorSourceLeg


@h.generator
def PmosCascodeSourceLeg(params: PmosCascodeSourceLegParams) -> h.Module:
    @h.module
    class _PmosCascodeSourceLeg:
        avdd = h.Inout()
        agnd = h.Inout()
        nref = h.Input()
        out = h.Inout()
        vg = h.Output()
        vcasc = h.Output()

        out_mid = h.Signal()

        # Reference stack: avdd -> cascode diode -> mirror diode -> NMOS sink.
        mp_casc_ref = h.Pmos(w=params.cascode_w, l=params.cascode_l, vth=params.vth, family=h.MosFamily.CORE)(
            d=vcasc, g=vcasc, s=avdd, b=avdd
        )
        mp_ref = h.Pmos(w=params.out_w, l=params.out_l, vth=params.vth, family=h.MosFamily.CORE)(
            d=vg, g=vg, s=vcasc, b=avdd
        )
        mn_sink = h.Nmos(w=params.sink_w, l=params.sink_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=vg, g=nref, s=agnd, b=agnd
        )

        # Output stack: avdd -> cascode device -> mirror output -> out.
        mp_casc_out = h.Pmos(
            w=params.cascode_w, l=params.cascode_l, vth=params.vth, family=h.MosFamily.CORE
        )(d=out_mid, g=vcasc, s=avdd, b=avdd)
        mp_out = h.Pmos(w=params.out_w, l=params.out_l, vth=params.vth, family=h.MosFamily.CORE)(
            d=out, g=vg, s=out_mid, b=avdd
        )

    return _PmosCascodeSourceLeg


@h.generator
def PmosGateBiasedSourceLeg(params: PmosGateBiasedSourceLegParams) -> h.Module:
    @h.module
    class _PmosGateBiasedSourceLeg:
        avdd = h.Inout()
        out = h.Inout()
        vg = h.Input()

        mp_out = h.Pmos(w=params.out_w, l=params.out_l, vth=params.vth, family=h.MosFamily.CORE)(
            d=out, g=vg, s=avdd, b=avdd
        )

    return _PmosGateBiasedSourceLeg


@h.generator
def NmosMirrorSinkLeg(params: NmosMirrorSinkLegParams) -> h.Module:
    @h.module
    class _NmosMirrorSinkLeg:
        avdd = h.Inout()
        agnd = h.Inout()
        iref = h.Input()
        out = h.Inout()
        vg = h.Output()

        mp_feed = h.Pmos(w=params.feed_w, l=params.feed_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=vg, g=iref, s=avdd, b=avdd
        )
        mn_ref = h.Nmos(w=params.out_w, l=params.out_l, vth=params.vth, family=h.MosFamily.CORE)(
            d=vg, g=vg, s=agnd, b=agnd
        )
        mn_out = h.Nmos(w=params.out_w, l=params.out_l, vth=params.vth, family=h.MosFamily.CORE)(
            d=out, g=vg, s=agnd, b=agnd
        )

    return _NmosMirrorSinkLeg


@h.generator
def CurrentBiasLeg(params: CurrentBiasLegParams) -> h.Module:
    """Reusable current-bias leg with a single logical interface and explicit polarity.

    `kind="source"` creates a PMOS top-side current source referenced by `nref`.
    `kind="sink"` creates an NMOS bottom-side current sink referenced by `iref`.
    """

    if params.kind == CurrentBiasKind.SOURCE:
        return PmosMirrorSourceLeg(
            PmosMirrorSourceLegParams(
                out_w=params.out_w,
                out_l=params.out_l,
                vth=params.vth,
                sink_w=params.ref_w,
                sink_l=params.ref_l,
            )
        )

    return NmosMirrorSinkLeg(
        NmosMirrorSinkLegParams(
            out_w=params.out_w,
            out_l=params.out_l,
            vth=params.vth,
            feed_w=params.ref_w,
            feed_l=params.ref_l,
        )
    )


@h.generator
def PmosBiasVoltageLeg(params: PmosBiasVoltageLegParams) -> h.Module:
    @h.module
    class _PmosBiasVoltageLeg:
        avdd = h.Inout()
        agnd = h.Inout()
        nref = h.Input()
        out = h.Output()

        mp_diode = h.Pmos(w=params.p_w, l=params.p_l, vth=params.p_vth, family=h.MosFamily.CORE)(
            d=out, g=out, s=avdd, b=avdd
        )
        mn_sink = h.Nmos(w=params.sink_w, l=params.sink_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=out, g=nref, s=agnd, b=agnd
        )

    return _PmosBiasVoltageLeg


@h.generator
def NmosBiasVoltageLeg(params: NmosBiasVoltageLegParams) -> h.Module:
    @h.module
    class _NmosBiasVoltageLeg:
        avdd = h.Inout()
        agnd = h.Inout()
        iref = h.Input()
        out = h.Output()

        mp_feed = h.Pmos(w=params.feed_w, l=params.feed_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=out, g=iref, s=avdd, b=avdd
        )
        mn_diode = h.Nmos(w=params.n_w, l=params.n_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=out, g=out, s=agnd, b=agnd
        )

    return _NmosBiasVoltageLeg


@h.generator
def OpaBiasGen(params: OpaBiasGenParams) -> h.Module:
    @h.module
    class _OpaBiasGen:
        avdd = h.Inout()
        agnd = h.Inout()
        iref = h.Inout()

        i0_p = h.Inout()
        i0_n = h.Inout()
        ibias_p = h.Inout()
        ibias_n = h.Inout()
        vbias1 = h.Output()
        vbias2 = h.Output()
        vbias3 = h.Output()

        nref, vg_i0_p, vg_i0_n = h.Signals(3)

        mp_ref = h.Pmos(w=params.ref_w, l=params.ref_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=iref, g=iref, s=avdd, b=avdd
        )
        mp_nref_feed = h.Pmos(
            w=params.nref_feed_w, l=params.nref_feed_l, vth=MosVth.STD, family=h.MosFamily.CORE
        )(d=nref, g=iref, s=avdd, b=avdd)
        mn_ref = h.Nmos(
            w=params.nref_w, l=params.nref_l, vth=MosVth.STD, family=h.MosFamily.CORE
        )(d=nref, g=nref, s=agnd, b=agnd)

        mp_i0_p_ref = h.Pmos(w=params.i0_p_w, l=params.i0_p_l, vth=MosVth.HIGH, family=h.MosFamily.CORE)(
            d=vg_i0_p, g=vg_i0_p, s=avdd, b=avdd
        )
        mn_i0_p_sink = h.Nmos(w=params.nref_w, l=params.nref_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=vg_i0_p, g=nref, s=agnd, b=agnd
        )
        mp_i0_p_out = h.Pmos(w=params.i0_p_w, l=params.i0_p_l, vth=MosVth.HIGH, family=h.MosFamily.CORE)(
            d=i0_p, g=vg_i0_p, s=avdd, b=avdd
        )

        mp_bias1 = h.Pmos(w=params.bias1_p_w, l=params.bias1_p_l, vth=MosVth.HIGH, family=h.MosFamily.CORE)(
            d=vbias1, g=vbias1, s=avdd, b=avdd
        )
        mn_bias1_sink = h.Nmos(w=params.nref_w, l=params.nref_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=vbias1, g=nref, s=agnd, b=agnd
        )
        mp_bias2 = h.Pmos(w=params.bias2_p_w, l=params.bias2_p_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=vbias2, g=vbias2, s=avdd, b=avdd
        )
        mn_bias2_sink = h.Nmos(w=params.nref_w, l=params.nref_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=vbias2, g=nref, s=agnd, b=agnd
        )

        mp_i0_n_feed = h.Pmos(w=params.i0_n_w, l=params.i0_n_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=vg_i0_n, g=iref, s=avdd, b=avdd
        )
        mn_i0_n_ref = h.Nmos(w=params.i0_n_w, l=params.i0_n_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=vg_i0_n, g=vg_i0_n, s=agnd, b=agnd
        )
        mn_i0_n_out = h.Nmos(w=params.i0_n_w, l=params.i0_n_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=i0_n, g=vg_i0_n, s=agnd, b=agnd
        )

        mp_bias3_feed = h.Pmos(w=params.bias3_n_w, l=params.bias3_n_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=vbias3, g=iref, s=avdd, b=avdd
        )
        mn_bias3 = h.Nmos(w=params.bias3_n_w, l=params.bias3_n_l, vth=MosVth.STD, family=h.MosFamily.CORE)(
            d=vbias3, g=vbias3, s=agnd, b=agnd
        )

    return _OpaBiasGen


BiasGenParams = OpaBiasGenParams


@h.generator
def bias_generator(params: OpaBiasGenParams) -> h.Module:
    return OpaBiasGen(params)
