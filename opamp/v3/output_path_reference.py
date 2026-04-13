import hdl21 as h
import sky130_hdl21

from .pdk_passives import pdk_resistor


def _mos_params(w: h.Scalar, l: h.Scalar, nf: int = 1, mult: int = 1):
    return sky130_hdl21.Sky130MosParams(w=w, l=l, nf=nf, mult=mult)


@h.paramclass
class ReferenceOutputPathParams:
    w_out_n = h.Param(dtype=h.Scalar, desc="Output NMOS width in um", default=1.2)
    l_out_n = h.Param(dtype=h.Scalar, desc="Output NMOS length in um", default=0.5)
    w_out_p = h.Param(dtype=h.Scalar, desc="Output PMOS width in um", default=2.4)
    l_out_p = h.Param(dtype=h.Scalar, desc="Output PMOS length in um", default=0.5)
    w_bias_n = h.Param(dtype=h.Scalar, desc="Replica NMOS width in um", default=0.6)
    l_bias_n = h.Param(dtype=h.Scalar, desc="Replica NMOS length in um", default=1.0)
    w_bias_p = h.Param(dtype=h.Scalar, desc="Replica PMOS width in um", default=1.2)
    l_bias_p = h.Param(dtype=h.Scalar, desc="Replica PMOS length in um", default=1.0)
    r_bias = h.Param(dtype=h.Scalar, desc="Bias-spread resistor in ohm", default=120e3)
    w_inv_n = h.Param(dtype=h.Scalar, desc="Helper inverter NMOS width in um", default=0.5)
    l_inv_n = h.Param(dtype=h.Scalar, desc="Helper inverter NMOS length in um", default=2.0)
    w_inv_p = h.Param(dtype=h.Scalar, desc="Helper inverter PMOS width in um", default=1.0)
    l_inv_p = h.Param(dtype=h.Scalar, desc="Helper inverter PMOS length in um", default=2.0)
    r_sig_n = h.Param(dtype=h.Scalar, desc="Weak signal injection resistor to NMOS gate in ohm", default=1.2e6)
    r_sig_p = h.Param(dtype=h.Scalar, desc="Weak signal injection resistor to PMOS gate in ohm", default=1.2e6)
    r_keep_n = h.Param(dtype=h.Scalar, desc="Strong gate keep resistor for NMOS gate in ohm", default=60e3)
    r_keep_p = h.Param(dtype=h.Scalar, desc="Strong gate keep resistor for PMOS gate in ohm", default=60e3)


def default_reference_output_path_params(**overrides) -> ReferenceOutputPathParams:
    params = dict(
        w_out_n=1.2,
        l_out_n=0.5,
        w_out_p=2.4,
        l_out_p=0.5,
        w_bias_n=0.6,
        l_bias_n=1.0,
        w_bias_p=1.2,
        l_bias_p=1.0,
        r_bias=120e3,
        w_inv_n=0.5,
        l_inv_n=2.0,
        w_inv_p=1.0,
        l_inv_p=2.0,
        r_sig_n=1.2e6,
        r_sig_p=1.2e6,
        r_keep_n=60e3,
        r_keep_p=60e3,
    )
    params.update(overrides)
    return ReferenceOutputPathParams(**params)


@h.generator
def reference_output_path_method2(params: ReferenceOutputPathParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="ReferenceOutputPathMethod2")
    mod.VDRV, mod.VOUT, mod.VDD, mod.VSS = h.Ports(4)
    mod.VGN, mod.VGP = h.Signals(2)
    mod.vdrvb, mod.vgn_q, mod.vgp_q = h.Signals(3)
    mod.vout_p, mod.vout_n = h.Signals(2)
    mod.vdd_bias_p, mod.vss_bias_n = h.Signals(2)

    # Helper inverter creates a complementary control input.
    mod.m_inv_p = pmos(_mos_params(params.w_inv_p, params.l_inv_p))(d=mod.vdrvb, g=mod.VDRV, s=mod.VDD, b=mod.VDD)
    mod.m_inv_n = nmos(_mos_params(params.w_inv_n, params.l_inv_n))(d=mod.vdrvb, g=mod.VDRV, s=mod.VSS, b=mod.VSS)

    # Replica-based linked bias spread, matching the output-device polarities.
    mod.vprobe_bias_p = h.Vdc(dc=0)(p=mod.VDD, n=mod.vdd_bias_p)
    mod.m_bias_p = pmos(_mos_params(params.w_bias_p, params.l_bias_p))(d=mod.vgp_q, g=mod.vgp_q, s=mod.vdd_bias_p, b=mod.VDD)
    mod.r_bias = pdk_resistor(params.r_bias, p=mod.vgp_q, n=mod.vgn_q, bulk=mod.VSS)
    mod.vprobe_bias_n = h.Vdc(dc=0)(p=mod.vss_bias_n, n=mod.VSS)
    mod.m_bias_n = nmos(_mos_params(params.w_bias_n, params.l_bias_n))(d=mod.vgn_q, g=mod.vgn_q, s=mod.vss_bias_n, b=mod.VSS)

    # Keep the output-device gates pinned to the bias spread, then perturb them weakly.
    # Use complementary signal injection so the bias network sets quiescent conduction and
    # the signal only nudges the pair around that operating point.
    mod.r_keep_n = pdk_resistor(params.r_keep_n, p=mod.vgn_q, n=mod.VGN, bulk=mod.VSS)
    mod.r_keep_p = pdk_resistor(params.r_keep_p, p=mod.vgp_q, n=mod.VGP, bulk=mod.VSS)
    mod.r_sig_n = pdk_resistor(params.r_sig_n, p=mod.VDRV, n=mod.VGN, bulk=mod.VSS)
    mod.r_sig_p = pdk_resistor(params.r_sig_p, p=mod.vdrvb, n=mod.VGP, bulk=mod.VSS)

    # Push-pull common-source output pair.
    mod.vprobe_outp = h.Vdc(dc=0)(p=mod.vout_p, n=mod.VOUT)
    mod.vprobe_outn = h.Vdc(dc=0)(p=mod.vout_n, n=mod.VOUT)
    mod.m_out_n = nmos(_mos_params(params.w_out_n, params.l_out_n))(d=mod.vout_n, g=mod.VGN, s=mod.VSS, b=mod.VSS)
    mod.m_out_p = pmos(_mos_params(params.w_out_p, params.l_out_p))(d=mod.vout_p, g=mod.VGP, s=mod.VDD, b=mod.VDD)
    return mod


@h.generator
def reference_output_stage_only(params: ReferenceOutputPathParams) -> h.Module:
    pmos = sky130_hdl21.primitives.PMOS_1p8V_STD
    nmos = sky130_hdl21.primitives.NMOS_1p8V_STD

    mod = h.Module(name="ReferenceOutputStageOnly")
    mod.VGN, mod.VGP, mod.VOUT, mod.VDD, mod.VSS = h.Ports(5)
    mod.m_out_n = nmos(_mos_params(params.w_out_n, params.l_out_n))(d=mod.VOUT, g=mod.VGN, s=mod.VSS, b=mod.VSS)
    mod.m_out_p = pmos(_mos_params(params.w_out_p, params.l_out_p))(d=mod.VOUT, g=mod.VGP, s=mod.VDD, b=mod.VDD)
    return mod
