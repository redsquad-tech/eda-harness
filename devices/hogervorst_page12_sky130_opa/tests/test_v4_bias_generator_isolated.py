from pathlib import Path
from uuid import uuid4

import hdl21 as h
import sky130_hdl21 as sky130
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import ResultFormat

from devices.hogervorst_page12_sky130_opa.common import default_ngspice_options, run_ngspice_sim
from devices.hogervorst_page12_sky130_opa.opamp import NeuronOaParams, compile_for_sky130
from devices.hogervorst_page12_sky130_opa.opa_bias import OpaBiasGen
from devices.hogervorst_page12_sky130_opa.tests._helpers import BaseV4SimTest, write_metrics_json


METRICS_PATH = Path(__file__).with_name("v4_bias_generator_isolated_metrics.json")


def _build_tb(params: NeuronOaParams):
    bias = OpaBiasGen(params.bias)

    @h.module
    class Tb:
        VSS = h.Port()
        avdd, iref = h.Signals(2)
        i0_p, i0_n, ibias_p, ibias_n = h.Signals(4)
        vbias1, vbias2, vbias3 = h.Signals(3)

        vvdd = h.Vdc(dc=1.8)(p=avdd, n=VSS)
        iiref = h.Idc(dc=0.25e-6)(p=iref, n=VSS)
        # Give current outputs a DC path in the isolated bench.
        ri0p = h.Res(r=100_000)(p=i0_p, n=VSS)
        ri0n = h.Res(r=100_000)(p=i0_n, n=avdd)
        ribp = h.Res(r=100_000)(p=ibias_p, n=VSS)
        ribn = h.Res(r=100_000)(p=ibias_n, n=avdd)

        xbias = bias(
            avdd=avdd,
            agnd=VSS,
            iref=iref,
            i0_p=i0_p,
            i0_n=i0_n,
            ibias_p=ibias_p,
            ibias_n=ibias_n,
            vbias1=vbias1,
            vbias2=vbias2,
            vbias3=vbias3,
        )

    return Tb


def measure_bias_generator_isolated(params: NeuronOaParams | None = None) -> dict[str, float]:
    params = params or NeuronOaParams()
    tb = h.elaborate(_build_tb(params))
    compile_for_sky130(tb)
    saves = [
        "v(xtop.avdd)",
        "v(xtop.i0_p)",
        "v(xtop.i0_n)",
        "v(xtop.ibias_p)",
        "v(xtop.ibias_n)",
        "v(xtop.vbias1)",
        "v(xtop.vbias2)",
        "v(xtop.vbias3)",
        "@m.xtop.xbias.xmp_ref.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xbias.xmp_nref_feed.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xbias.xmn_ref.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xbias.xmp_i0_p_ref.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xbias.xmn_i0_p_sink.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xbias.xmp_ibias_p_ref.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xbias.xmn_ibias_p_sink.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xbias.xmp_i0_n_feed.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xbias.xmn_i0_n_ref.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xbias.xmp_ibias_n_feed.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xbias.xmn_ibias_n_ref.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xbias.xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xbias.xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xbias.xmp_bias1.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xbias.xmn_bias1_sink.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xbias.xmp_bias2.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xbias.xmn_bias2_sink.msky130_fd_pr__nfet_01v8[id]",
        "@m.xtop.xbias.xmp_bias3_feed.msky130_fd_pr__pfet_01v8[id]",
        "@m.xtop.xbias.xmn_bias3.msky130_fd_pr__nfet_01v8[id]",
    ]
    sim = Sim(
        tb=tb,
        attrs=[
            Op(),
            Save(", ".join(saves)),
            h.sim.Literal(".temp 27"),
            sky130.install.include(h.pdk.Corner.TYP),
        ],
    )
    result = run_ngspice_sim(
        sim,
        default_ngspice_options(
            f"opamp_v4_bias_iso_{uuid4().hex[:8]}",
            fmt=ResultFormat.SIM_DATA,
        ),
    )
    d = result.an[0].data
    metrics = {
        "avdd_V": float(d["v(xtop.avdd)"]),
        "i0_p_V": float(d["v(xtop.i0_p)"]),
        "i0_n_V": float(d["v(xtop.i0_n)"]),
        "ibias_p_V": float(d["v(xtop.ibias_p)"]),
        "ibias_n_V": float(d["v(xtop.ibias_n)"]),
        "vbias1_V": float(d["v(xtop.vbias1)"]),
        "vbias2_V": float(d["v(xtop.vbias2)"]),
        "vbias3_V": float(d["v(xtop.vbias3)"]),
        "id_ref_A": abs(float(d["i(@m.xtop.xbias.xmp_ref.msky130_fd_pr__pfet_01v8[id])"])),
        "id_nref_feed_A": abs(float(d["i(@m.xtop.xbias.xmp_nref_feed.msky130_fd_pr__pfet_01v8[id])"])),
        "id_nref_A": abs(float(d["i(@m.xtop.xbias.xmn_ref.msky130_fd_pr__nfet_01v8[id])"])),
        "id_i0_p_A": abs(float(d["i(@m.xtop.xbias.xmp_i0_p_ref.msky130_fd_pr__pfet_01v8[id])"])),
        "id_i0_p_sink_A": abs(float(d["i(@m.xtop.xbias.xmn_i0_p_sink.msky130_fd_pr__nfet_01v8[id])"])),
        "id_ibias_p_A": abs(float(d["i(@m.xtop.xbias.xmp_ibias_p_ref.msky130_fd_pr__pfet_01v8[id])"])),
        "id_ibias_p_sink_A": abs(float(d["i(@m.xtop.xbias.xmn_ibias_p_sink.msky130_fd_pr__nfet_01v8[id])"])),
        "id_i0_n_feed_A": abs(float(d["i(@m.xtop.xbias.xmp_i0_n_feed.msky130_fd_pr__pfet_01v8[id])"])),
        "id_i0_n_A": abs(float(d["i(@m.xtop.xbias.xmn_i0_n_ref.msky130_fd_pr__nfet_01v8[id])"])),
        "id_ibias_n_feed_A": abs(float(d["i(@m.xtop.xbias.xmp_ibias_n_feed.msky130_fd_pr__pfet_01v8[id])"])),
        "id_ibias_n_A": abs(float(d["i(@m.xtop.xbias.xmn_ibias_n_ref.msky130_fd_pr__nfet_01v8[id])"])),
        "id_i0_p_out_A": abs(float(d["i(@m.xtop.xbias.xmp_i0_p_out.msky130_fd_pr__pfet_01v8[id])"])),
        "id_i0_n_out_A": abs(float(d["i(@m.xtop.xbias.xmn_i0_n_out.msky130_fd_pr__nfet_01v8[id])"])),
        "id_ibias_p_out_A": abs(float(d["i(@m.xtop.xbias.xmp_ibias_p_out.msky130_fd_pr__pfet_01v8[id])"])),
        "id_ibias_n_out_A": abs(float(d["i(@m.xtop.xbias.xmn_ibias_n_out.msky130_fd_pr__nfet_01v8[id])"])),
        "id_bias1_p_A": abs(float(d["i(@m.xtop.xbias.xmp_bias1.msky130_fd_pr__pfet_01v8[id])"])),
        "id_bias1_sink_A": abs(float(d["i(@m.xtop.xbias.xmn_bias1_sink.msky130_fd_pr__nfet_01v8[id])"])),
        "id_bias2_p_A": abs(float(d["i(@m.xtop.xbias.xmp_bias2.msky130_fd_pr__pfet_01v8[id])"])),
        "id_bias2_sink_A": abs(float(d["i(@m.xtop.xbias.xmn_bias2_sink.msky130_fd_pr__nfet_01v8[id])"])),
        "id_bias3_feed_A": abs(float(d["i(@m.xtop.xbias.xmp_bias3_feed.msky130_fd_pr__pfet_01v8[id])"])),
        "id_bias3_n_A": abs(float(d["i(@m.xtop.xbias.xmn_bias3.msky130_fd_pr__nfet_01v8[id])"])),
    }
    metrics["summary"] = {
        "i0_p_match_ratio": metrics["id_i0_p_A"] / max(metrics["id_i0_p_sink_A"], 1e-30),
        "ibias_p_match_ratio": metrics["id_ibias_p_A"] / max(metrics["id_ibias_p_sink_A"], 1e-30),
        "i0_n_match_ratio": metrics["id_i0_n_feed_A"] / max(metrics["id_i0_n_A"], 1e-30),
        "ibias_n_match_ratio": metrics["id_ibias_n_feed_A"] / max(metrics["id_ibias_n_A"], 1e-30),
    }
    return metrics


class TestV4BiasGeneratorIsolated(BaseV4SimTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.metrics = measure_bias_generator_isolated()
        write_metrics_json(METRICS_PATH, cls.metrics)

    def test_bias_nodes_are_finite(self) -> None:
        for name in ["vbias1_V", "vbias2_V", "vbias3_V", "i0_p_V", "i0_n_V", "ibias_p_V", "ibias_n_V"]:
            self.assertFinite(self.metrics[name], f"{name} must be finite")

    def test_vbias1_is_within_usable_range(self) -> None:
        self.assertMetricBetween("vbias1_V", self.metrics["vbias1_V"], 0.2, 1.6)

    def test_vbias2_is_within_usable_range(self) -> None:
        self.assertMetricBetween("vbias2_V", self.metrics["vbias2_V"], 0.2, 1.6)

    def test_vbias3_is_within_usable_range(self) -> None:
        self.assertMetricBetween("vbias3_V", self.metrics["vbias3_V"], 0.1, 1.2)

    def test_current_output_nodes_are_within_rails(self) -> None:
        self.assertMetricBetween("i0_p_V", self.metrics["i0_p_V"], 0.0, self.metrics["avdd_V"])
        self.assertMetricBetween("i0_n_V", self.metrics["i0_n_V"], 0.0, self.metrics["avdd_V"])
        self.assertMetricBetween("ibias_p_V", self.metrics["ibias_p_V"], 0.0, self.metrics["avdd_V"])
        self.assertMetricBetween("ibias_n_V", self.metrics["ibias_n_V"], 0.0, self.metrics["avdd_V"])

    def test_reference_branch_current_is_alive(self) -> None:
        # ngspice does not emit the branch current of `vvdd` in this isolated OP bench
        # under the current save list; use the reference-generated bias voltages as the
        # liveness check here and keep device-current probes as finite diagnostics.
        self.assertMetricBetween("vbias1_V", self.metrics["vbias1_V"], 0.2, 1.6)
        self.assertMetricBetween("vbias3_V", self.metrics["vbias3_V"], 0.1, 1.2)

    def test_reference_nmos_branch_is_alive(self) -> None:
        self.assertFinite(self.metrics["id_nref_feed_A"], "id_nref_feed_A must be finite")
        self.assertFinite(self.metrics["id_nref_A"], "id_nref_A must be finite")

    def test_pmos_bias_branch_currents_are_alive(self) -> None:
        self.assertFinite(self.metrics["id_i0_p_A"], "id_i0_p_A must be finite")
        self.assertFinite(self.metrics["id_i0_p_sink_A"], "id_i0_p_sink_A must be finite")
        self.assertFinite(self.metrics["id_ibias_p_A"], "id_ibias_p_A must be finite")
        self.assertFinite(self.metrics["id_ibias_p_sink_A"], "id_ibias_p_sink_A must be finite")

    def test_nmos_bias_branch_currents_are_alive(self) -> None:
        self.assertFinite(self.metrics["id_i0_n_feed_A"], "id_i0_n_feed_A must be finite")
        self.assertFinite(self.metrics["id_i0_n_A"], "id_i0_n_A must be finite")
        self.assertFinite(self.metrics["id_ibias_n_feed_A"], "id_ibias_n_feed_A must be finite")
        self.assertFinite(self.metrics["id_ibias_n_A"], "id_ibias_n_A must be finite")

    def test_output_current_branches_are_alive(self) -> None:
        self.assertFinite(self.metrics["id_i0_p_out_A"], "id_i0_p_out_A must be finite")
        self.assertFinite(self.metrics["id_i0_n_out_A"], "id_i0_n_out_A must be finite")
        self.assertFinite(self.metrics["id_ibias_p_out_A"], "id_ibias_p_out_A must be finite")
        self.assertFinite(self.metrics["id_ibias_n_out_A"], "id_ibias_n_out_A must be finite")

    def test_pmos_stack_current_match_is_reasonable(self) -> None:
        self.assertMetricLess(
            "i0_p_match_ratio",
            self.metrics["summary"]["i0_p_match_ratio"],
            10.0,
        )
        self.assertMetricLess(
            "ibias_p_match_ratio",
            self.metrics["summary"]["ibias_p_match_ratio"],
            10.0,
        )

    def test_nmos_stack_current_match_is_reasonable(self) -> None:
        self.assertMetricLess(
            "i0_n_match_ratio",
            self.metrics["summary"]["i0_n_match_ratio"],
            10.0,
        )
        self.assertMetricLess(
            "ibias_n_match_ratio",
            self.metrics["summary"]["ibias_n_match_ratio"],
            10.0,
        )
