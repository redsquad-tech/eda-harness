import hdl21 as h
from hdl21.primitives import MosVth

from ..opamp import FrontEndParams, MonticelliParams, OutputStageParams


def _nmos(w, l, *, vth=MosVth.STD):
    return h.Nmos(w=w, l=l, vth=vth, family=h.MosFamily.CORE)


def _pmos(w, l, *, vth=MosVth.STD):
    return h.Pmos(w=w, l=l, vth=vth, family=h.MosFamily.CORE)


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

        pinp_l = _pmos(params.w_in_p, params.l_in, vth=MosVth.LOW)(d=nnode_l, g=vinn, s=tail_p, b=avdd)
        pinp_r = _pmos(params.w_in_p, params.l_in, vth=MosVth.LOW)(d=nnode_r, g=vinp, s=tail_p, b=avdd)
        ninp_l = _nmos(params.w_in_n, params.l_in, vth=MosVth.LOW)(d=pnode_l, g=vinp, s=tail_n, b=agnd)
        ninp_r = _nmos(params.w_in_n, params.l_in, vth=MosVth.LOW)(d=pnode_r, g=vinn, s=tail_n, b=agnd)
        mpb1_l = _pmos(params.w_pcas1, params.l_fold, vth=MosVth.HIGH)(d=pnode_l, g=vbias1, s=avdd, b=avdd)
        mpb1_r = _pmos(params.w_pcas1, params.l_fold, vth=MosVth.HIGH)(d=pnode_r, g=vbias1, s=avdd, b=avdd)
        mpb2_l = _pmos(params.w_pcas2, params.l_fold)(d=vref_mid, g=vbias2, s=pnode_l, b=avdd)
        mpb2_r = _pmos(params.w_pcas2, params.l_fold)(d=vgp, g=vbias2, s=pnode_r, b=avdd)
        mnb3_l = _nmos(params.w_ncas, params.l_fold)(d=vref_mid, g=vbias3, s=nnode_l, b=agnd)
        mnb3_r = _nmos(params.w_ncas, params.l_fold)(d=vgn, g=vbias3, s=nnode_r, b=agnd)
        mnref = _nmos(params.w_nmir, params.l_fold)(d=nnode_l, g=nnode_l, s=agnd, b=agnd)
        mnout = _nmos(params.w_nmir, params.l_fold)(d=nnode_r, g=nnode_l, s=agnd, b=agnd)

    return ComplementaryCascodeFrontEnd


@h.generator
def monticelli_cell(params: MonticelliParams) -> h.Module:
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

        mn22 = _nmos(params.w_stack_n, params.l_stack)(d=vb_m24, g=vb_m24, s=n_mid, b=agnd)
        mn23 = _nmos(params.w_stack_n, params.l_stack)(d=n_mid, g=n_mid, s=agnd, b=agnd)
        mp33 = _pmos(params.w_stack_p, params.l_stack, vth=MosVth.HIGH)(d=p_mid, g=p_mid, s=avdd, b=avdd)
        mp34 = _pmos(params.w_stack_p, params.l_stack, vth=MosVth.HIGH)(d=vb_m35, g=vb_m35, s=p_mid, b=avdd)
        m24 = _nmos(params.w_m24, params.l_mont)(d=vgp, g=vb_m24, s=vgn, b=agnd)
        m35 = _pmos(params.w_m35, params.l_mont)(d=vgn, g=vb_m35, s=vgp, b=avdd)

    return MonticelliCell


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

        m2 = _pmos(params.w_out_p, params.l_out)(d=vout, g=vgp, s=avdd, b=avdd)
        m1 = _nmos(params.w_out_n, params.l_out)(d=vout, g=vgn, s=agnd, b=agnd)
        rcp = h.Res(r=params.rc)(p=vgp, n=ccp_mid)
        ccp = h.Cap(c=params.cc)(p=ccp_mid, n=vout)
        rcn = h.Res(r=params.rc)(p=vgn, n=ccn_mid)
        ccn = h.Cap(c=params.cc)(p=ccn_mid, n=vout)

    return ClassAbOutputStage
