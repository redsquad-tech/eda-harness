import hdl21 as h
from hdl21.primitives import MosVth

# Sky130 MOS wrappers expect geometry values in microns, not SI-scaled meters.
U = 1.0
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

        mp = h.Pmos(w=params.wp, l=params.lp, vth=params.pvth, family=h.MosFamily.CORE)(
            d=o, g=i, s=avdd, b=avdd
        )
        mn = h.Nmos(w=params.wn, l=params.ln, vth=params.nvth, family=h.MosFamily.CORE)(
            d=o, g=i, s=agnd, b=agnd
        )

    return CmosInv


@h.generator
def cmos_nand2(params: InvParams) -> h.Module:
    """Small CMOS NAND2, only for local mode decode."""

    @h.module
    class CmosNand2:
        a = h.Input()
        b = h.Input()
        o = h.Output()
        avdd = h.Inout()
        agnd = h.Inout()

        mp_a = h.Pmos(w=params.wp, l=params.lp, vth=params.pvth, family=h.MosFamily.CORE)(
            d=o, g=a, s=avdd, b=avdd
        )
        mp_b = h.Pmos(w=params.wp, l=params.lp, vth=params.pvth, family=h.MosFamily.CORE)(
            d=o, g=b, s=avdd, b=avdd
        )
        nmid = h.Signal()
        mn_a = h.Nmos(w=params.wn, l=params.ln, vth=params.nvth, family=h.MosFamily.CORE)(
            d=o, g=a, s=nmid, b=agnd
        )
        mn_b = h.Nmos(w=params.wn, l=params.ln, vth=params.nvth, family=h.MosFamily.CORE)(
            d=nmid, g=b, s=agnd, b=agnd
        )

    return CmosNand2


@h.paramclass
class SwitchParams:
    """Generic analog switch device sizes."""

    wp = h.Param(dtype=h.Scalar, desc="PMOS width", default=4.0 * U)
    lp = h.Param(dtype=h.Scalar, desc="PMOS length", default=0.30 * U)
    wn = h.Param(dtype=h.Scalar, desc="NMOS width", default=3.0 * U)
    ln = h.Param(dtype=h.Scalar, desc="NMOS length", default=0.30 * U)
    pvth = h.Param(dtype=MosVth, desc="PMOS threshold", default=MosVth.STD)
    nvth = h.Param(dtype=MosVth, desc="NMOS threshold", default=MosVth.STD)


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

        psw = h.Pmos(w=params.wp, l=params.lp, vth=params.pvth, family=h.MosFamily.CORE)(
            d=a, g=en_b, s=b, b=avdd
        )
        nsw = h.Nmos(w=params.wn, l=params.ln, vth=params.nvth, family=h.MosFamily.CORE)(
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

        sw = h.Nmos(w=params.wn, l=params.ln, vth=params.nvth, family=h.MosFamily.CORE)(
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

        sw = h.Pmos(w=params.wp, l=params.lp, vth=params.pvth, family=h.MosFamily.CORE)(
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

        m1 = h.Nmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth, family=h.MosFamily.CORE)(
            d=outp, g=inp, s=tail, b=bulk
        )
        m2 = h.Nmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth, family=h.MosFamily.CORE)(
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

        m1 = h.Pmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth, family=h.MosFamily.CORE)(
            d=outp, g=inp, s=tail, b=bulk
        )
        m2 = h.Pmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth, family=h.MosFamily.CORE)(
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
def CurrentSinkN(params: CurrentSourceParams) -> h.Module:
    @h.module
    class _CurrentSinkN:
        d = h.Inout()
        vg = h.Input()
        VSS = h.Inout()

        m = h.Nmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth, family=h.MosFamily.CORE)(
            d=d, g=vg, s=VSS, b=VSS
        )

    return _CurrentSinkN


@h.generator
def CurrentSourceP(params: CurrentSourceParams) -> h.Module:
    @h.module
    class _CurrentSourceP:
        d = h.Inout()
        vg = h.Input()
        VDD = h.Inout()

        m = h.Pmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth, family=h.MosFamily.CORE)(
            d=d, g=vg, s=VDD, b=VDD
        )

    return _CurrentSourceP


@h.generator
def tail_current_nmos(params: CurrentSourceParams) -> h.Module:
    return CurrentSinkN(params)


@h.generator
def tail_current_pmos(params: CurrentSourceParams) -> h.Module:
    return CurrentSourceP(params)


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


@h.paramclass
class FoldDeviceParams:
    """Single common-gate folding device."""

    w = h.Param(dtype=h.Scalar, desc="Device width", default=1.2 * U)
    l = h.Param(dtype=h.Scalar, desc="Device length", default=1.0 * U)
    npar = h.Param(dtype=int, desc="Parallel fingers", default=1)
    vth = h.Param(dtype=MosVth, desc="Threshold", default=MosVth.STD)


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
            w=params.w_src, l=params.l_src, npar=params.npar, vth=params.src_vth, family=h.MosFamily.CORE
        )(d=mid, g=vbias_src, s=avdd, b=avdd)
        mc = h.Pmos(
            w=params.w_cas, l=params.l_cas, npar=params.npar, vth=params.cas_vth, family=h.MosFamily.CORE
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
            w=params.w_cas, l=params.l_cas, npar=params.npar, vth=params.cas_vth, family=h.MosFamily.CORE
        )(d=out, g=vbias_cas, s=mid, b=agnd)
        ms = h.Nmos(
            w=params.w_src, l=params.l_src, npar=params.npar, vth=params.src_vth, family=h.MosFamily.CORE
        )(d=mid, g=vbias_src, s=agnd, b=agnd)

    return NmosCascodeSink


@h.generator
def nmos_fold_device(params: FoldDeviceParams) -> h.Module:
    """NMOS common-gate fold device from a PMOS-pair drain into a stage output node."""

    @h.module
    class NmosFoldDevice:
        drain = h.Inout()
        source = h.Inout()
        bias = h.Input()
        agnd = h.Inout()

        m = h.Nmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth, family=h.MosFamily.CORE)(
            d=drain, g=bias, s=source, b=agnd
        )

    return NmosFoldDevice


@h.generator
def pmos_fold_device(params: FoldDeviceParams) -> h.Module:
    """PMOS common-gate fold device from a stage output node into an NMOS-pair drain."""

    @h.module
    class PmosFoldDevice:
        drain = h.Inout()
        source = h.Inout()
        bias = h.Input()
        avdd = h.Inout()

        m = h.Pmos(w=params.w, l=params.l, npar=params.npar, vth=params.vth, family=h.MosFamily.CORE)(
            d=drain, g=bias, s=source, b=avdd
        )

    return PmosFoldDevice


from .opa_bias import BiasGenParams, OpaBiasGen, OpaBiasGenParams, bias_generator
