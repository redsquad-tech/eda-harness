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
        "extracted_metrics": ["generator call", "elaboration", "subckt name", "device presence"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "nominal_op_tt": {
        "specification_aspect": "nominal cascode operating point",
        "category": "contract",
        "test_name": "run_op_test",
        "analysis_type": "Op",
        "extracted_metrics": ["v(out)", "i_path_est"],
        "pass_fail_rule": "nominal smoke test only",
        "required_corners": ["TT"],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "bias_order_tt": {
        "specification_aspect": "cascode bias monotonicity",
        "category": "contract",
        "test_name": "run_bias_order_test",
        "analysis_type": "Op",
        "extracted_metrics": ["v(out) at low bcas", "v(out) at high bcas"],
        "pass_fail_rule": "BCAS sweep should monotonically change path conduction",
        "required_corners": ["TT"],
        "required_operating_conditions": ["v_bcas"],
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
class CascodeBlockParams:
    device_type = h.Param(dtype=str, desc="Cascode polarity: n or p", default="n")
    style = h.Param(dtype=str, desc="Topology: simple or wide_swing", default="simple")
    dev_main = h.Param(dtype=str, desc="SKY130 primitive name for main device", default="NMOS_1p8V_STD")
    dev_cas = h.Param(dtype=str, desc="SKY130 primitive name for cascode device", default="NMOS_1p8V_STD")
    w_main = h.Param(dtype=h.Scalar, desc="Main-device width in um", default=1.0)
    l_main = h.Param(dtype=h.Scalar, desc="Main-device length in um", default=0.15)
    nf_main = h.Param(dtype=int, desc="Main-device fingers", default=1)
    m_main = h.Param(dtype=int, desc="Main-device multiplier", default=1)
    w_cas = h.Param(dtype=h.Scalar, desc="Cascode-device width in um", default=1.0)
    l_cas = h.Param(dtype=h.Scalar, desc="Cascode-device length in um", default=0.15)
    nf_cas = h.Param(dtype=int, desc="Cascode-device fingers", default=1)
    m_cas = h.Param(dtype=int, desc="Cascode-device multiplier", default=1)
    vcas_target = h.Param(dtype=h.Scalar, desc="Target cascode bias in V; design-intent metadata", default=0.9)


@h.paramclass
class CascodeBlockOpTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    v_in = h.Param(dtype=h.Scalar, desc="Bias applied to IN in V", default=0.5)
    v_bcas = h.Param(dtype=h.Scalar, desc="Cascode bias voltage in V", default=0.9)
    r_load = h.Param(dtype=h.Scalar, desc="Load resistance on OUT in ohm", default=20e3)


@h.paramclass
class CascodeBlockBiasOrderTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    v_in = h.Param(dtype=h.Scalar, desc="Bias applied to IN in V", default=0.5)
    v_bcas_lo = h.Param(dtype=h.Scalar, desc="Lower BCAS voltage in V", default=0.7)
    v_bcas_hi = h.Param(dtype=h.Scalar, desc="Higher BCAS voltage in V", default=1.0)
    r_load = h.Param(dtype=h.Scalar, desc="Load resistance on OUT in ohm", default=20e3)


@h.generator
def cascode_block(params: CascodeBlockParams) -> h.Module:
    if params.device_type not in ("n", "p"):
        raise ValueError(f"Unsupported device_type: {params.device_type}")
    if params.style not in ("simple", "wide_swing"):
        raise ValueError(f"Unsupported style: {params.style}")
    for name, value in (
        ("w_main", params.w_main),
        ("l_main", params.l_main),
        ("w_cas", params.w_cas),
        ("l_cas", params.l_cas),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    for name, value in (
        ("nf_main", params.nf_main),
        ("m_main", params.m_main),
        ("nf_cas", params.nf_cas),
        ("m_cas", params.m_cas),
    ):
        if value < 1:
            raise ValueError(f"{name} must be >= 1")

    main_prim = _mos_primitive(params.dev_main)
    cas_prim = _mos_primitive(params.dev_cas)
    main_par = _mos_params(params.w_main, params.l_main, params.nf_main, params.m_main)
    cas_par = _mos_params(params.w_cas, params.l_cas, params.nf_cas, params.m_cas)

    mod = h.Module(name="CascodeBlock")
    mod.IN, mod.OUT, mod.BCAS, mod.VDD, mod.VSS = h.Ports(5)

    if params.device_type == "n":
        if params.style == "simple":
            mod.m_cas = cas_prim(cas_par)(d=mod.OUT, g=mod.BCAS, s=mod.IN, b=mod.VSS)
            return mod

        mod.mid = h.Signal(name="mid")
        mod.m_cas = cas_prim(cas_par)(d=mod.OUT, g=mod.BCAS, s=mod.mid, b=mod.VSS)
        mod.m_main = main_prim(main_par)(d=mod.mid, g=mod.IN, s=mod.IN, b=mod.VSS)
        return mod

    if params.style == "simple":
        mod.m_cas = cas_prim(cas_par)(d=mod.OUT, g=mod.BCAS, s=mod.IN, b=mod.VDD)
        return mod

    mod.mid = h.Signal(name="mid")
    mod.m_cas = cas_prim(cas_par)(d=mod.OUT, g=mod.BCAS, s=mod.mid, b=mod.VDD)
    mod.m_main = main_prim(main_par)(d=mod.mid, g=mod.IN, s=mod.IN, b=mod.VDD)
    return mod


def build_op_test(
    dut_params: CascodeBlockParams,
    tb_params: CascodeBlockOpTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    tb_params = tb_params or CascodeBlockOpTbParams()
    install = require_sky130_install()
    dut = cascode_block(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        inn, out, bcas, vdd = h.Signals(4)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        vin = h.Vdc(dc=tb_params.v_in)(p=inn, n=VSS)
        vbcas = h.Vdc(dc=tb_params.v_bcas)(p=bcas, n=VSS)
        xdut = dut(IN=inn, OUT=out, BCAS=bcas, VDD=vdd, VSS=VSS)

        if dut_params.device_type == "n":
            rload = h.Res(r=tb_params.r_load)(p=vdd, n=out)
        else:
            rload = h.Res(r=tb_params.r_load)(p=out, n=VSS)

    return Sim(tb=Tb, attrs=[Op(), Save(SaveMode.ALL), install.include(corner)])


def run_op_test(
    dut_params: CascodeBlockParams | None = None,
    tb_params: CascodeBlockOpTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options=None,
):
    dut_params = dut_params or CascodeBlockParams()
    tb_params = tb_params or CascodeBlockOpTbParams()
    sim = build_op_test(dut_params, tb_params, corner=corner)
    result = run_ngspice_sim(
        sim,
        sim_options if sim_options is not None else _default_ngspice_options("cascode_block_op"),
    )
    v_out = _op_scalar(result, "v(xtop.out)")
    if dut_params.device_type == "n":
        i_path_est = max((tb_params.vdd - v_out) / tb_params.r_load, 0.0)
    else:
        i_path_est = max(v_out / tb_params.r_load, 0.0)
    return {
        "v_out": v_out,
        "i_path_est": float(i_path_est),
    }


def run_bias_order_test(
    dut_params: CascodeBlockParams | None = None,
    tb_params: CascodeBlockBiasOrderTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options=None,
):
    dut_params = dut_params or CascodeBlockParams()
    tb_params = tb_params or CascodeBlockBiasOrderTbParams()

    lo = run_op_test(
        dut_params,
        CascodeBlockOpTbParams(vdd=tb_params.vdd, v_in=tb_params.v_in, v_bcas=tb_params.v_bcas_lo, r_load=tb_params.r_load),
        corner=corner,
        sim_options=sim_options if sim_options is not None else _default_ngspice_options("cascode_block_bias_lo"),
    )
    hi = run_op_test(
        dut_params,
        CascodeBlockOpTbParams(vdd=tb_params.vdd, v_in=tb_params.v_in, v_bcas=tb_params.v_bcas_hi, r_load=tb_params.r_load),
        corner=corner,
        sim_options=sim_options if sim_options is not None else _default_ngspice_options("cascode_block_bias_hi"),
    )
    if dut_params.device_type == "n":
        delta = lo["v_out"] - hi["v_out"]
    else:
        delta = hi["v_out"] - lo["v_out"]
    return {
        "v_out_lo_bcas": lo["v_out"],
        "v_out_hi_bcas": hi["v_out"],
        "delta": delta,
        "i_path_lo": lo["i_path_est"],
        "i_path_hi": hi["i_path_est"],
    }


def run_all_tests(
    dut_params: CascodeBlockParams | None = None,
    *,
    sim_options=None,
):
    dut_params = dut_params or CascodeBlockParams()
    return {
        "structural": run_structural_checks(dut_params),
        "nominal_op": run_op_test(dut_params, sim_options=sim_options),
        "bias_order": run_bias_order_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: CascodeBlockParams | None = None,
    *,
    sim_options=None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="cascode_block")
    return results


def elaborate_dut(params: CascodeBlockParams | None = None) -> h.Module:
    params = params or CascodeBlockParams()
    return h.elaborate(cascode_block(params))


def export_spice(path: str | Path, params: CascodeBlockParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: CascodeBlockParams | None = None):
    params = params or CascodeBlockParams()
    dut = cascode_block(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/cascode_block_structural/cascode_block.sp")
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
    }
    if params.device_type == "n":
        checks["contains_device"] = "sky130_fd_pr__nfet_01v8" in text
    else:
        checks["contains_device"] = "sky130_fd_pr__pfet_01v8" in text
    if params.style == "wide_swing":
        checks["contains_mid_node"] = "mid" in text
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
