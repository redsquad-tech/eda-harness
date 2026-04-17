import hdl21 as h
from hdl21.primitives import MosVth


# Sky130 MOS wrappers expect geometry values in microns.
U = 1.0


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
