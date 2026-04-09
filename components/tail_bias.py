from pathlib import Path
import re

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Op, Save, SaveMode, Sim
from vlsirtools.spice import SimOptions, SupportedSimulators

from components import extract_subckt_name, print_metrics_table, require_sky130_install, run_ngspice_sim


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator call", "elaboration", "subckt name", "NMOS presence"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "nominal_op_tt": {
        "specification_aspect": "nominal tail-bias operating point",
        "category": "contract",
        "test_name": "run_op_test",
        "analysis_type": "Op",
        "extracted_metrics": ["v(out)", "i(vvdd)"],
        "pass_fail_rule": "nominal smoke test only",
        "required_corners": ["TT"],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "bias_order_tt": {
        "specification_aspect": "tail-bias control monotonicity",
        "category": "contract",
        "test_name": "run_bias_order_test",
        "analysis_type": "Op",
        "extracted_metrics": ["v(out) at low bias", "v(out) at high bias", "v(out)_low - v(out)_high"],
        "pass_fail_rule": "higher bias should increase sink current and lower OUT",
        "required_corners": ["TT"],
        "required_operating_conditions": ["v_bias"],
        "monte_carlo_required": False,
    },
}


def _mos_primitive(name: str):
    try:
        return getattr(sky130_hdl21.primitives, name)
    except AttributeError as err:
        raise ValueError(f"Unsupported SKY130 primitive: {name}") from err


def _mos_params(w: h.Scalar, l: h.Scalar, nf: int, mult: int):
    return sky130_hdl21.Sky130MosParams(w=w, l=l, nf=nf, mult=mult)


def _default_ngspice_options(test_name: str) -> SimOptions:
    return SimOptions(
        simulator=SupportedSimulators.NGSPICE,
        rundir=f"./tmp/{test_name}",
    )


def _op_scalar(result, signal_name: str) -> float:
    op = result.an[0].op
    target = signal_name.lower()
    for name, value in zip(op.signals, op.data):
        if name.lower() == target:
            return float(value)
    raise RuntimeError(f"Signal {signal_name} not found in op result: {list(op.signals)}")


@h.paramclass
class TailBiasParams:
    style = h.Param(dtype=str, desc="Implementation style: simple or cascoded", default="simple")
    dev_out = h.Param(dtype=str, desc="SKY130 NMOS primitive name for output device", default="NMOS_1p8V_STD")
    dev_cas = h.Param(dtype=str, desc="SKY130 NMOS primitive name for cascode device", default="NMOS_1p8V_STD")
    w_out = h.Param(dtype=h.Scalar, desc="Output-device width in um", default=1.0)
    l_out = h.Param(dtype=h.Scalar, desc="Output-device length in um", default=0.15)
    nf_out = h.Param(dtype=int, desc="Output-device fingers", default=1)
    m_out = h.Param(dtype=int, desc="Output-device multiplier", default=1)
    w_cas = h.Param(dtype=h.Scalar, desc="Cascode-device width in um", default=1.0)
    l_cas = h.Param(dtype=h.Scalar, desc="Cascode-device length in um", default=0.15)
    nf_cas = h.Param(dtype=int, desc="Cascode-device fingers", default=1)
    m_cas = h.Param(dtype=int, desc="Cascode-device multiplier", default=1)
    i_target = h.Param(dtype=h.Scalar, desc="Target tail current in A; design-intent metadata", default=100e-6)


@h.paramclass
class TailBiasOpTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    v_bias = h.Param(dtype=h.Scalar, desc="Bias control voltage in V", default=0.9)
    r_load = h.Param(dtype=h.Scalar, desc="Load resistance from VDD to OUT in ohm", default=20e3)


@h.paramclass
class TailBiasOrderTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    v_bias_lo = h.Param(dtype=h.Scalar, desc="Lower bias voltage in V", default=0.75)
    v_bias_hi = h.Param(dtype=h.Scalar, desc="Higher bias voltage in V", default=0.95)
    r_load = h.Param(dtype=h.Scalar, desc="Load resistance from VDD to OUT in ohm", default=20e3)


@h.generator
def tail_bias(params: TailBiasParams) -> h.Module:
    if params.style not in ("simple", "cascoded"):
        raise ValueError(f"Unsupported style: {params.style}")
    for name, value in (
        ("w_out", params.w_out),
        ("l_out", params.l_out),
        ("w_cas", params.w_cas),
        ("l_cas", params.l_cas),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    for name, value in (
        ("nf_out", params.nf_out),
        ("m_out", params.m_out),
        ("nf_cas", params.nf_cas),
        ("m_cas", params.m_cas),
    ):
        if value < 1:
            raise ValueError(f"{name} must be >= 1")

    nmos_out = _mos_primitive(params.dev_out)
    outpar = _mos_params(params.w_out, params.l_out, params.nf_out, params.m_out)

    mod = h.Module(name="TailBias")
    mod.BIAS, mod.OUT, mod.VDD, mod.VSS = h.Ports(4)

    if params.style == "simple":
        mod.m_out = nmos_out(outpar)(d=mod.OUT, g=mod.BIAS, s=mod.VSS, b=mod.VSS)
        return mod

    nmos_cas = _mos_primitive(params.dev_cas)
    caspar = _mos_params(params.w_cas, params.l_cas, params.nf_cas, params.m_cas)
    mod.mid = h.Signal(name="mid")
    mod.m_cas = nmos_cas(caspar)(d=mod.OUT, g=mod.BIAS, s=mod.mid, b=mod.VSS)
    mod.m_out = nmos_out(outpar)(d=mod.mid, g=mod.BIAS, s=mod.VSS, b=mod.VSS)
    return mod


def build_op_test(
    dut_params: TailBiasParams,
    tb_params: TailBiasOpTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    tb_params = tb_params or TailBiasOpTbParams()
    install = require_sky130_install()
    dut = tail_bias(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        bias, out, vdd = h.Signals(3)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        vbias = h.Vdc(dc=tb_params.v_bias)(p=bias, n=VSS)
        rload = h.Res(r=tb_params.r_load)(p=vdd, n=out)
        xdut = dut(BIAS=bias, OUT=out, VDD=vdd, VSS=VSS)

    return Sim(tb=Tb, attrs=[Op(), Save(SaveMode.ALL), install.include(corner)])


def run_op_test(
    dut_params: TailBiasParams | None = None,
    tb_params: TailBiasOpTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options=None,
):
    dut_params = dut_params or TailBiasParams()
    sim = build_op_test(dut_params, tb_params, corner=corner)
    result = run_ngspice_sim(
        sim,
        sim_options if sim_options is not None else _default_ngspice_options("tail_bias_op"),
    )
    v_out = _op_scalar(result, "v(xtop.out)")
    i_vvdd = _op_scalar(result, "i(v.xtop.vvvdd)")
    return {
        "v_out": v_out,
        "i_vvdd": i_vvdd,
        "i_sink_abs": abs(i_vvdd),
    }


def run_bias_order_test(
    dut_params: TailBiasParams | None = None,
    tb_params: TailBiasOrderTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options=None,
):
    dut_params = dut_params or TailBiasParams()
    tb_params = tb_params or TailBiasOrderTbParams()

    lo = run_op_test(
        dut_params,
        TailBiasOpTbParams(vdd=tb_params.vdd, v_bias=tb_params.v_bias_lo, r_load=tb_params.r_load),
        corner=corner,
        sim_options=sim_options if sim_options is not None else _default_ngspice_options("tail_bias_order_lo"),
    )
    hi = run_op_test(
        dut_params,
        TailBiasOpTbParams(vdd=tb_params.vdd, v_bias=tb_params.v_bias_hi, r_load=tb_params.r_load),
        corner=corner,
        sim_options=sim_options if sim_options is not None else _default_ngspice_options("tail_bias_order_hi"),
    )
    return {
        "v_out_lo_bias": lo["v_out"],
        "v_out_hi_bias": hi["v_out"],
        "v_out_lo_minus_hi": lo["v_out"] - hi["v_out"],
        "i_sink_lo_abs": lo["i_sink_abs"],
        "i_sink_hi_abs": hi["i_sink_abs"],
    }


def run_all_tests(
    dut_params: TailBiasParams | None = None,
    *,
    sim_options=None,
):
    dut_params = dut_params or TailBiasParams()
    return {
        "structural": run_structural_checks(dut_params),
        "nominal_op": run_op_test(dut_params, sim_options=sim_options),
        "bias_order": run_bias_order_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: TailBiasParams | None = None,
    *,
    sim_options=None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="tail_bias")
    return results


def elaborate_dut(params: TailBiasParams | None = None) -> h.Module:
    params = params or TailBiasParams()
    return h.elaborate(tail_bias(params))


def export_spice(path: str | Path, params: TailBiasParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: TailBiasParams | None = None):
    params = params or TailBiasParams()
    dut = tail_bias(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/tail_bias_structural/tail_bias.sp")
    export_spice(netlist_path, params)
    text = netlist_path.read_text()
    subckt_name = extract_subckt_name(text)
    top_level_prefix = mod.name.split("(", 1)[0]
    top_level_present = re.search(rf"^\.SUBCKT\s+{re.escape(top_level_prefix)}", text, flags=re.MULTILINE) is not None

    checks = {
        "generator_call": dut is not None,
        "elaboration": mod is not None,
        "subckt_name": subckt_name is not None,
        "top_level_subckt": top_level_present,
        "contains_nmos": "sky130_fd_pr__nfet_01v8" in text,
    }
    if params.style == "cascoded":
        checks["contains_mid_node"] = " mid " in text or "\n+ mid " in text
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
