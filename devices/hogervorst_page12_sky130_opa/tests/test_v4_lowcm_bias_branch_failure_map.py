from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130, neuron_core_oa_sky130, page12_analog_core, Page12CoreParams
from devices.hogervorst_page12_sky130_opa.opa_bias import OpaBiasGen
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, find_signal, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_lowcm_bias_branch_failure_map_metrics.json")
VIN_POINTS = (0.0, 0.05, 0.1, 0.2, 0.5, 0.9)


def _build_core_real_bias_tb(params: NeuronOaParams, vin_v: float):
    core = page12_analog_core(Page12CoreParams(frontend=params.frontend, monticelli=params.monticelli, output=params.output))
    bias = OpaBiasGen(params.bias)

    @h.module
    class Tb:
        VSS = h.Port()
        avdd, vinp_sig, vinn_sig, vout, iref = h.Signals(5)
        tail_p, tail_n = h.Signals(2)
        vbias1, vbias2, vbias3 = h.Signals(3)
        m24_gate_mid, m35_gate_mid = h.Signals(2)
        pnode_l, pnode_r, nnode_l, nnode_r = h.Signals(4)
        vref_mid, vgp, vgn = h.Signals(3)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=vin_v)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=vin_v)(p=vinn_sig, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e9)(p=vout, n=VSS)

        xbias = bias(
            avdd=avdd,
            agnd=VSS,
            iref=iref,
            i0_p=tail_p,
            i0_n=tail_n,
            ibias_p=m24_gate_mid,
            ibias_n=m35_gate_mid,
            vbias1=vbias1,
            vbias2=vbias2,
            vbias3=vbias3,
        )
        xcore = core(
            vinp=vinp_sig,
            vinn=vinn_sig,
            avdd=avdd,
            agnd=VSS,
            vout=vout,
            tail_p=tail_p,
            tail_n=tail_n,
            vbias1=vbias1,
            vbias2=vbias2,
            vbias3=vbias3,
            m24_gate_mid=m24_gate_mid,
            m35_gate_mid=m35_gate_mid,
            pnode_l=pnode_l,
            pnode_r=pnode_r,
            nnode_l=nnode_l,
            nnode_r=nnode_r,
            vref_mid=vref_mid,
            vgp=vgp,
            vgn=vgn,
        )

    return Tb


def _build_full_dut_tb(params: NeuronOaParams, vin_v: float):
    dut = h.elaborate(neuron_core_oa_sky130(params))
    compile_for_sky130(dut)

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vout, avdd = h.Signals(4)
        iref, vbase, vfeed, vtest = h.Signals(4)
        d_en_oa, d_az_oa, d_inf_oa = h.Signals(3)
        d_treset_oa, d_tcki, d_tcko, d_tdi, d_tdo = h.Signals(5)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        vvinp = h.Vdc(dc=vin_v)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=vin_v)(p=vinn_sig, n=VSS)
        ven = h.Vdc(dc=1.8)(p=d_en_oa, n=VSS)
        vaz = h.Vdc(dc=0.0)(p=d_az_oa, n=VSS)
        vinf = h.Vdc(dc=1.8)(p=d_inf_oa, n=VSS)
        vtreset = h.Vdc(dc=0.0)(p=d_treset_oa, n=VSS)
        vtcki = h.Vdc(dc=0.0)(p=d_tcki, n=VSS)
        vtdi = h.Vdc(dc=0.0)(p=d_tdi, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn_sig)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e9)(p=vout, n=VSS)

        xdut = dut(
            avdd1p2=avdd,
            agnd=VSS,
            vinp=vinp_sig,
            vinn=vinn_sig,
            vout=vout,
            in0u25_oa=iref,
            vbase=vbase,
            vfeed=vfeed,
            d_en_oa=d_en_oa,
            d_az_oa=d_az_oa,
            d_inf_oa=d_inf_oa,
            vtest=vtest,
            d_treset_oa=d_treset_oa,
            d_tcki=d_tcki,
            d_tcko=d_tcko,
            d_tdi=d_tdi,
            d_tdo=d_tdo,
        )

    return Tb


def _branch_ratio(out_a: float, ref_a: float) -> float:
    return float(out_a) / max(float(ref_a), 1e-30)


def _extract_row(data: dict[str, float], vin_v: float, *, prefix: str, current_prefix: str, supply_key: str) -> dict:
    if prefix:
        p = f"{prefix}."
    else:
        p = ""
    row = {
        "vin_V": vin_v,
        "iq_uA": 1e6 * abs(find_signal(data, exact=supply_key)),
        "vout_V": find_signal(data, exact="v(xtop.vout)"),
        "tail_p_V": find_signal(data, exact=f"v(xtop.{p}tail_p)"),
        "tail_n_V": find_signal(data, exact=f"v(xtop.{p}tail_n)"),
        "vbias1_V": find_signal(data, exact=f"v(xtop.{p}vbias1)"),
        "vbias2_V": find_signal(data, exact=f"v(xtop.{p}vbias2)"),
        "vbias3_V": find_signal(data, exact=f"v(xtop.{p}vbias3)"),
        "m24_gate_mid_V": find_signal(data, exact=f"v(xtop.{p}m24_gate_mid)"),
        "m35_gate_mid_V": find_signal(data, exact=f"v(xtop.{p}m35_gate_mid)"),
        "vgp_V": find_signal(data, exact=f"v(xtop.{p}vgp)"),
        "vgn_V": find_signal(data, exact=f"v(xtop.{p}vgn)"),
        "vg_i0_p_V": find_signal(data, suffix="vg_i0_p)"),
        "vg_i0_n_V": find_signal(data, suffix="vg_i0_n)"),
        "vg_ibias_p_V": find_signal(data, suffix="vg_ibias_p)"),
        "vg_ibias_n_V": find_signal(data, suffix="vg_ibias_n)"),
        "id_i0_p_ref_A": abs(find_signal(data, exact=f"i(@m.xtop.{current_prefix}.xmp_i0_p_ref.msky130_fd_pr__pfet_01v8[id])")),
        "id_i0_p_out_A": abs(find_signal(data, exact=f"i(@m.xtop.{current_prefix}.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id])")),
        "id_i0_n_ref_A": abs(find_signal(data, exact=f"i(@m.xtop.{current_prefix}.xmn_i0_n_ref.msky130_fd_pr__nfet_01v8[id])")),
        "id_i0_n_out_A": abs(find_signal(data, exact=f"i(@m.xtop.{current_prefix}.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id])")),
        "id_ibias_p_ref_A": abs(find_signal(data, exact=f"i(@m.xtop.{current_prefix}.xmp_ibias_p_ref.msky130_fd_pr__pfet_01v8[id])")),
        "id_ibias_p_out_A": abs(find_signal(data, exact=f"i(@m.xtop.{current_prefix}.xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id])")),
        "id_ibias_n_ref_A": abs(find_signal(data, exact=f"i(@m.xtop.{current_prefix}.xmn_ibias_n_ref.msky130_fd_pr__nfet_01v8[id])")),
        "id_ibias_n_out_A": abs(find_signal(data, exact=f"i(@m.xtop.{current_prefix}.xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id])")),
    }
    row["derived"] = {
        "i0_p_ratio": _branch_ratio(row["id_i0_p_out_A"], row["id_i0_p_ref_A"]),
        "i0_n_ratio": _branch_ratio(row["id_i0_n_out_A"], row["id_i0_n_ref_A"]),
        "ibias_p_ratio": _branch_ratio(row["id_ibias_p_out_A"], row["id_ibias_p_ref_A"]),
        "ibias_n_ratio": _branch_ratio(row["id_ibias_n_out_A"], row["id_ibias_n_ref_A"]),
        "track_error_mV": 1e3 * abs(row["vout_V"] - vin_v),
    }
    row["flags"] = {
        "i0_p_dead": row["derived"]["i0_p_ratio"] < 1e-3,
        "i0_n_dead": row["derived"]["i0_n_ratio"] < 1e-3,
        "ibias_p_dead": row["derived"]["ibias_p_ratio"] < 1e-3,
        "ibias_n_dead": row["derived"]["ibias_n_ratio"] < 1e-3,
    }
    return row


def measure_lowcm_bias_branch_failure_map() -> dict:
    params = NeuronOaParams()
    payload = {"core_real_bias": {"rows": []}, "full_dut": {"rows": []}}
    core_save = ", ".join(
        [
            "all",
            "@m.xtop.xbias.xmp_i0_p_ref.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xbias.xmn_i0_n_ref.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xbias.xmp_ibias_p_ref.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xbias.xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xbias.xmn_ibias_n_ref.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xbias.xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id]",
        ]
    )
    dut_save = ", ".join(
        [
            "all",
            "@m.xtop.xxdut.xbias.xmp_i0_p_ref.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmn_i0_n_ref.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmp_ibias_p_ref.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmn_ibias_n_ref.msky130_fd_pr__nfet_01v8[id]",
            "@m.xtop.xxdut.xbias.xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id]",
        ]
    )

    for vin_v in VIN_POINTS:
        core_tb = h.elaborate(_build_core_real_bias_tb(params, vin_v))
        compile_for_sky130(core_tb)
        core_res = run_ngspice_sim(
            Sim(tb=core_tb, attrs=[Op(), Save(core_save), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)]),
            default_ngspice_options(f"opamp_v4_biasfail_core_{vin_v}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
        )
        payload["core_real_bias"]["rows"].append(
            _extract_row(core_res.an[0].data, vin_v, prefix="", current_prefix="xbias", supply_key="i(v.xtop.vvvdd)")
        )

        dut_tb = h.elaborate(_build_full_dut_tb(params, vin_v))
        dut_res = run_ngspice_sim(
            Sim(tb=dut_tb, attrs=[Op(), Save(dut_save), h.sim.Literal(".temp 27"), sky130.install.include(h.pdk.Corner.TYP)]),
            default_ngspice_options(f"opamp_v4_biasfail_dut_{vin_v}_{uuid4().hex[:8]}", fmt=ResultFormat.SIM_DATA),
        )
        payload["full_dut"]["rows"].append(
            _extract_row(dut_res.an[0].data, vin_v, prefix="xxdut", current_prefix="xxdut.xbias", supply_key="i(v.xtop.vvvdd)")
        )

    row = payload["full_dut"]["rows"][VIN_POINTS.index(0.1)]
    dead = [name for name in ("i0_p", "i0_n", "ibias_p", "ibias_n") if row["flags"][f"{name}_dead"]]
    if len(dead) == 1:
        primary = dead[0]
    elif len(dead) > 1:
        primary = "multiple_dead_branches"
    else:
        primary = "no_single_dead_branch"
    payload["verdict"] = {
        "vin0p1_dead_branches_full_dut": dead,
        "vin0p1_primary_suspect": primary,
    }
    return payload


class TestV4LowCmBiasBranchFailureMap(BaseV4SimTest):
    def test_lowcm_bias_branch_failure_map(self) -> None:
        payload = measure_lowcm_bias_branch_failure_map()
        write_metrics_json(METRICS_PATH, payload)

        self.assertEqual(len(payload["core_real_bias"]["rows"]), len(VIN_POINTS))
        self.assertEqual(len(payload["full_dut"]["rows"]), len(VIN_POINTS))
        for mode in ("core_real_bias", "full_dut"):
            for row in payload[mode]["rows"]:
                self.assertFinite(row["iq_uA"], f"{mode}:{row['vin_V']}: iq_uA")
                self.assertFinite(row["vout_V"], f"{mode}:{row['vin_V']}: vout_V")
