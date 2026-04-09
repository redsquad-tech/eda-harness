from pathlib import Path
import re
from dataclasses import dataclass

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Save, SaveMode, Sim, Tran, Op
from vlsirtools.spice import SimOptions, SupportedSimulators

from .common import extract_subckt_name, make_test_result, print_metrics_table, require_sky130_install, run_ngspice_sim
from .pdk_resistor import pdk_resistor


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator_call", "elaboration", "subckt_name", "contains_device"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "startup": {
        "specification_aspect": "bias startup behavior",
        "category": "contract",
        "test_name": "run_startup_test",
        "analysis_type": "Tran",
        "extracted_metrics": ["i_ibias1_est", "i_ibias2_est", "startup_ok"],
        "pass_fail_rule": "both bias outputs reach measurable non-zero current after the generic startup fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["worst_bias"],
        "monte_carlo_required": False,
    },
    "current_accuracy": {
        "specification_aspect": "bias current ratio tracking characterization",
        "category": "char",
        "test_name": "run_current_accuracy_test",
        "analysis_type": "Op",
        "extracted_metrics": ["i_ibias1_est", "i_ibias2_est", "ratio_est", "ratio_error_abs"],
        "pass_fail_rule": "characterize nominal bias-current ratio tracking under the generic load fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load"],
        "monte_carlo_required": False,
    },
    "disable_off": {
        "specification_aspect": "disable-state bias shutdown characterization",
        "category": "char",
        "test_name": "run_disable_off_test",
        "analysis_type": "Op",
        "extracted_metrics": ["i_ibias1_off_est", "i_ibias2_off_est", "vbp_off", "vbp_headroom_to_vdd"],
        "pass_fail_rule": "characterize bias outputs and PMOS bias node when EN is held low",
        "required_corners": ["TT"],
        "required_operating_conditions": ["disabled"],
        "monte_carlo_required": False,
    },
    "reduced_corners": {
        "specification_aspect": "reduced-corner bias robustness characterization",
        "category": "char",
        "test_name": "run_reduced_corner_characterization_test",
        "analysis_type": "Op",
        "extracted_metrics": [
            "cases",
            "stage1_current_min_uA",
            "stage1_current_max_uA",
            "stage1_current_spread_ratio",
            "stage2_current_min_uA",
            "stage2_current_max_uA",
            "stage2_current_spread_ratio",
        ],
        "pass_fail_rule": "characterize mirrored-bias current spread across TT nominal, FF hot, and SS cold decision corners",
        "required_corners": ["TT", "FF", "SS"],
        "required_operating_conditions": ["nominal_vdd", "high_vdd_hot", "low_vdd_cold"],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class BiasGenSpec:
    name: str = "bias_gen"
    purpose: str = "Generate mirrored bias currents for opamp stages."
    component_class: str = "reusable block"
    pins: tuple[str, ...] = ("VDD", "VSS", "EN", "IBIAS1", "IBIAS2", "VBP")
    measurable_behaviors: tuple[str, ...] = ("startup", "current_accuracy", "reduced_corners")
    numeric_pass_fail_criteria: tuple[str, ...] = ("generic startup contract only; product bias-allocation budgets belong in external budget tests",)
    required_corners: tuple[str, ...] = ("TT",)
    statistical_verification_required: bool = False


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


def _tran_waveform(result, signal_name: str):
    tran = result.an[0].tran
    target = signal_name.lower()
    signals = list(tran.signals)
    if target not in [name.lower() for name in signals]:
        raise RuntimeError(f"Signal {signal_name} not found in tran result: {signals}")
    idx = next(idx for idx, name in enumerate(signals) if name.lower() == target)
    nsignals = len(signals)
    data = list(tran.data)
    npts = len(data) // nsignals
    start = idx * npts
    return data[start : start + npts]


@h.paramclass
class BiasGenParams:
    style = h.Param(dtype=str, desc="Bias topology style", default="mirror")
    i_ref = h.Param(dtype=h.Scalar, desc="Reference current in A", default=1.2e-6)
    ratio_stage1 = h.Param(dtype=h.Scalar, desc="Stage-1 current multiplier", default=1.8)
    ratio_stage2 = h.Param(dtype=h.Scalar, desc="Stage-2 current multiplier", default=2.2)
    device_type = h.Param(dtype=str, desc="Bias polarity: n or p", default="n")
    dev_ref = h.Param(dtype=str, desc="Reference device primitive", default="NMOS_1p8V_STD")
    dev_out = h.Param(dtype=str, desc="Output device primitive", default="NMOS_1p8V_STD")
    w_ref = h.Param(dtype=h.Scalar, desc="Reference width in um", default=4.0)
    l_ref = h.Param(dtype=h.Scalar, desc="Reference length in um", default=4.0)
    nf_ref = h.Param(dtype=int, desc="Reference fingers", default=1)
    m_ref = h.Param(dtype=int, desc="Reference multiplier", default=1)
    w_out = h.Param(dtype=h.Scalar, desc="Output width in um", default=4.0)
    l_out = h.Param(dtype=h.Scalar, desc="Output length in um", default=4.0)
    nf_out = h.Param(dtype=int, desc="Output fingers", default=1)
    m_out = h.Param(dtype=int, desc="Output multiplier", default=1)
    en_switch_w = h.Param(dtype=h.Scalar, desc="Enable switch width in um", default=2.0)
    en_switch_l = h.Param(dtype=h.Scalar, desc="Enable switch length in um", default=0.15)


@h.paramclass
class BiasGenStartupTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=10e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=50e-9)
    ramp = h.Param(dtype=h.Scalar, desc="Supply rise time in s", default=200e-9)
    r_load = h.Param(dtype=h.Scalar, desc="Output load resistance in ohm", default=200e3)


@h.paramclass
class BiasGenCurrentAccuracyTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    r_load = h.Param(dtype=h.Scalar, desc="Output load resistance in ohm", default=200e3)


@h.paramclass
class BiasGenDisableTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    r_load = h.Param(dtype=h.Scalar, desc="Output load resistance in ohm", default=200e3)


@h.generator
def bias_gen(params: BiasGenParams) -> h.Module:
    if params.style != "mirror":
        raise ValueError(f"Unsupported style: {params.style}")
    if params.device_type not in ("n", "p"):
        raise ValueError(f"Unsupported device_type: {params.device_type}")
    if params.i_ref <= 0:
        raise ValueError("i_ref must be positive")
    if params.ratio_stage1 <= 0 or params.ratio_stage2 <= 0:
        raise ValueError("ratio_stage1 and ratio_stage2 must be positive")
    for name, value in (
        ("w_ref", params.w_ref),
        ("l_ref", params.l_ref),
        ("w_out", params.w_out),
        ("l_out", params.l_out),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    for name, value in (
        ("nf_ref", params.nf_ref),
        ("m_ref", params.m_ref),
        ("nf_out", params.nf_out),
        ("m_out", params.m_out),
    ):
        if value < 1:
            raise ValueError(f"{name} must be >= 1")

    ref_prim = _mos_primitive(params.dev_ref)
    out_prim = _mos_primitive(params.dev_out)
    ref_par = _mos_params(params.w_ref, params.l_ref, params.nf_ref, params.m_ref)
    out1_par = _mos_params(params.w_out * params.ratio_stage1, params.l_out, params.nf_out, params.m_out)
    out2_par = _mos_params(params.w_out * params.ratio_stage2, params.l_out, params.nf_out, params.m_out)
    en_sw_par = _mos_params(params.en_switch_w, params.en_switch_l, 1, 1)

    mod = h.Module(name="BiasGen")
    mod.VDD, mod.VSS, mod.EN, mod.IBIAS1, mod.IBIAS2, mod.VBP = h.Ports(6)
    mod.iref = h.Signal(name="iref")
    r_ref = 1.8 / float(params.i_ref)

    if params.device_type == "n":
        mod.r_ref = pdk_resistor(r_ref, p=mod.VDD, n=mod.iref, bulk=mod.VSS)
        mod.m_ref = ref_prim(ref_par)(d=mod.iref, g=mod.iref, s=mod.VSS, b=mod.VSS)
        mod.m_out1 = out_prim(out1_par)(d=mod.IBIAS1, g=mod.iref, s=mod.VSS, b=mod.VSS)
        mod.m_out2 = out_prim(out2_par)(d=mod.IBIAS2, g=mod.iref, s=mod.VSS, b=mod.VSS)
    else:
        mod.ref_ret = h.Signal(name="ref_ret")
        mod.r_ref = pdk_resistor(r_ref, p=mod.iref, n=mod.ref_ret, bulk=mod.VSS)
        mod.m_ref_en = sky130_hdl21.primitives.NMOS_1p8V_STD(en_sw_par)(d=mod.ref_ret, g=mod.EN, s=mod.VSS, b=mod.VSS)
        mod.m_ref = ref_prim(ref_par)(d=mod.iref, g=mod.iref, s=mod.VDD, b=mod.VDD)
        mod.m_out1 = out_prim(out1_par)(d=mod.IBIAS1, g=mod.iref, s=mod.VDD, b=mod.VDD)
        mod.m_out2 = out_prim(out2_par)(d=mod.IBIAS2, g=mod.iref, s=mod.VDD, b=mod.VDD)
        # Hard-disable the PMOS mirror by pulling the shared gate reference and both
        # output bias rails up to VDD when EN is low. This makes VSG -> 0 throughout
        # the mirror instead of relying only on the diode-connected reference node.
        disable_par = _mos_params(params.w_ref * 4.0, params.l_ref, params.nf_ref, params.m_ref)
        mod.m_disable_ref = sky130_hdl21.primitives.PMOS_1p8V_STD(disable_par)(
            d=mod.iref,
            g=mod.EN,
            s=mod.VDD,
            b=mod.VDD,
        )
        mod.m_disable_out1 = sky130_hdl21.primitives.PMOS_1p8V_STD(disable_par)(
            d=mod.IBIAS1,
            g=mod.EN,
            s=mod.VDD,
            b=mod.VDD,
        )
        mod.m_disable_out2 = sky130_hdl21.primitives.PMOS_1p8V_STD(disable_par)(
            d=mod.IBIAS2,
            g=mod.EN,
            s=mod.VDD,
            b=mod.VDD,
        )
    mod.vbp_alias = h.Res(r=1e-3)(p=mod.VBP, n=mod.iref)

    return mod


def build_startup_test(
    dut_params: BiasGenParams,
    tb_params: BiasGenStartupTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or BiasGenStartupTbParams()
    install = require_sky130_install()
    dut = bias_gen(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        en, ibias1, ibias2, vbp, vdd = h.Signals(5)
        vvdd = h.Vpulse(
            v1=0.0,
            v2=tb_params.vdd,
            delay=0.0,
            rise=tb_params.ramp,
            fall=tb_params.ramp,
            width=tb_params.tstop,
            period=2 * tb_params.tstop,
        )(p=vdd, n=VSS)
        ven = h.Vdc(dc=tb_params.vdd)(p=en, n=VSS)
        xdut = dut(VDD=vdd, VSS=VSS, EN=en, IBIAS1=ibias1, IBIAS2=ibias2, VBP=vbp)
        if dut_params.device_type == "n":
            rload1 = h.Res(r=tb_params.r_load)(p=vdd, n=ibias1)
            rload2 = h.Res(r=tb_params.r_load)(p=vdd, n=ibias2)
        else:
            rload1 = h.Res(r=tb_params.r_load)(p=ibias1, n=VSS)
            rload2 = h.Res(r=tb_params.r_load)(p=ibias2, n=VSS)

    return Sim(tb=Tb, attrs=[Tran(tstop=tb_params.tstop, tstep=tb_params.tstep), Save(SaveMode.ALL), install.include(corner)])


def run_startup_test(
    dut_params: BiasGenParams | None = None,
    tb_params: BiasGenStartupTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or BiasGenParams()
    tb_params = tb_params or BiasGenStartupTbParams()
    result = run_ngspice_sim(
        build_startup_test(dut_params, tb_params, corner=corner),
        sim_options if sim_options is not None else _default_ngspice_options("bias_gen_startup"),
    )
    v1 = float(_tran_waveform(result, "v(xtop.ibias1)")[-1])
    v2 = float(_tran_waveform(result, "v(xtop.ibias2)")[-1])
    if dut_params.device_type == "n":
        i1 = max((tb_params.vdd - v1) / tb_params.r_load, 0.0)
        i2 = max((tb_params.vdd - v2) / tb_params.r_load, 0.0)
    else:
        i1 = max(v1 / tb_params.r_load, 0.0)
        i2 = max(v2 / tb_params.r_load, 0.0)
    metrics = {
        "v_ibias1_final": v1,
        "v_ibias2_final": v2,
        "i_ibias1_est": i1,
        "i_ibias2_est": i2,
        "startup_ok": i1 > 0 and i2 > 0,
    }
    return make_test_result(
        component="bias_gen",
        category="contract",
        purpose="startup",
        metrics=metrics,
        passed=bool(metrics["startup_ok"]),
        margin={
            "i_ibias1_est": metrics["i_ibias1_est"],
            "i_ibias2_est": metrics["i_ibias2_est"],
        },
    )


def _build_accuracy_style_op_test(
    dut_params: BiasGenParams,
    tb_params: BiasGenCurrentAccuracyTbParams | BiasGenDisableTbParams,
    *,
    en_voltage: float,
    corner=h.pdk.Corner.TYP,
):
    install = require_sky130_install()
    dut = bias_gen(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        en, ibias1, ibias2, vbp, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        ven = h.Vdc(dc=en_voltage)(p=en, n=VSS)
        xdut = dut(VDD=vdd, VSS=VSS, EN=en, IBIAS1=ibias1, IBIAS2=ibias2, VBP=vbp)
        if dut_params.device_type == "n":
            rload1 = h.Res(r=tb_params.r_load)(p=vdd, n=ibias1)
            rload2 = h.Res(r=tb_params.r_load)(p=vdd, n=ibias2)
        else:
            rload1 = h.Res(r=tb_params.r_load)(p=ibias1, n=VSS)
            rload2 = h.Res(r=tb_params.r_load)(p=ibias2, n=VSS)

    return Sim(tb=Tb, attrs=[Op(), Save(SaveMode.ALL), install.include(corner)])


def build_current_accuracy_test(
    dut_params: BiasGenParams,
    tb_params: BiasGenCurrentAccuracyTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or BiasGenCurrentAccuracyTbParams()
    return _build_accuracy_style_op_test(dut_params, tb_params, en_voltage=float(tb_params.vdd), corner=corner)


def build_disable_off_test(
    dut_params: BiasGenParams,
    tb_params: BiasGenDisableTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or BiasGenDisableTbParams()
    return _build_accuracy_style_op_test(dut_params, tb_params, en_voltage=0.0, corner=corner)


def run_current_accuracy_test(
    dut_params: BiasGenParams | None = None,
    tb_params: BiasGenCurrentAccuracyTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or BiasGenParams()
    tb_params = tb_params or BiasGenCurrentAccuracyTbParams()
    result = run_ngspice_sim(
        build_current_accuracy_test(dut_params, tb_params, corner=corner),
        sim_options if sim_options is not None else _default_ngspice_options("bias_gen_current_accuracy"),
    )
    v1 = _op_scalar(result, "v(xtop.ibias1)")
    v2 = _op_scalar(result, "v(xtop.ibias2)")
    if dut_params.device_type == "n":
        i1 = max((tb_params.vdd - v1) / tb_params.r_load, 0.0)
        i2 = max((tb_params.vdd - v2) / tb_params.r_load, 0.0)
    else:
        i1 = max(v1 / tb_params.r_load, 0.0)
        i2 = max(v2 / tb_params.r_load, 0.0)
    ratio_est = i2 / i1 if i1 > 0 else float("nan")
    ratio_target = float(dut_params.ratio_stage2 / dut_params.ratio_stage1)
    metrics = {
        "i_ibias1_est": i1,
        "i_ibias2_est": i2,
        "ratio_est": ratio_est,
        "ratio_target": ratio_target,
        "ratio_error_abs": abs(ratio_est - ratio_target),
    }
    return make_test_result(
        component="bias_gen",
        category="char",
        purpose="current_accuracy",
        metrics=metrics,
    )


def run_disable_off_test(
    dut_params: BiasGenParams | None = None,
    tb_params: BiasGenDisableTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or BiasGenParams()
    tb_params = tb_params or BiasGenDisableTbParams()
    result = run_ngspice_sim(
        build_disable_off_test(dut_params, tb_params, corner=corner),
        sim_options if sim_options is not None else _default_ngspice_options("bias_gen_disable_off"),
    )
    v1 = _op_scalar(result, "v(xtop.ibias1)")
    v2 = _op_scalar(result, "v(xtop.ibias2)")
    vbp = _op_scalar(result, "v(xtop.vbp)")
    if dut_params.device_type == "n":
        i1 = max((tb_params.vdd - v1) / tb_params.r_load, 0.0)
        i2 = max((tb_params.vdd - v2) / tb_params.r_load, 0.0)
    else:
        i1 = max(v1 / tb_params.r_load, 0.0)
        i2 = max(v2 / tb_params.r_load, 0.0)
    metrics = {
        "i_ibias1_off_est": i1,
        "i_ibias2_off_est": i2,
        "vbp_off": vbp,
        "vbp_headroom_to_vdd": float(tb_params.vdd) - vbp,
    }
    return make_test_result(
        component="bias_gen",
        category="char",
        purpose="disable_off",
        metrics=metrics,
    )


def run_reduced_corner_characterization_test(
    dut_params: BiasGenParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    del sim_options
    dut_params = dut_params or BiasGenParams()
    cases = {}
    decision_corners = (
        ("TT_1.80V_27C", h.pdk.Corner.TYP, 1.8),
        ("FF_1.98V_125C", h.pdk.Corner.FAST, 1.98),
        ("SS_1.62V_-40C", h.pdk.Corner.SLOW, 1.62),
    )
    stage1_currents_uA = []
    stage2_currents_uA = []
    for label, corner, vdd in decision_corners:
        result = run_current_accuracy_test(
            dut_params,
            BiasGenCurrentAccuracyTbParams(vdd=vdd),
            corner=corner,
        )
        metrics = result["metrics"]
        i1_uA = 1e6 * float(metrics["i_ibias1_est"])
        i2_uA = 1e6 * float(metrics["i_ibias2_est"])
        stage1_currents_uA.append(i1_uA)
        stage2_currents_uA.append(i2_uA)
        cases[label] = {
            "i_ibias1_uA": i1_uA,
            "i_ibias2_uA": i2_uA,
            "ratio_est": float(metrics["ratio_est"]),
            "ratio_target": float(metrics["ratio_target"]),
            "ratio_error_abs": float(metrics["ratio_error_abs"]),
        }

    def spread_ratio(values: list[float]) -> float:
        vmax = max(values)
        vmin = min(values)
        return float("inf") if vmin <= 0.0 else vmax / vmin

    return make_test_result(
        component="bias_gen",
        category="char",
        purpose="reduced_corners",
        metrics={
            "cases": cases,
            "stage1_current_min_uA": min(stage1_currents_uA),
            "stage1_current_max_uA": max(stage1_currents_uA),
            "stage1_current_spread_ratio": spread_ratio(stage1_currents_uA),
            "stage2_current_min_uA": min(stage2_currents_uA),
            "stage2_current_max_uA": max(stage2_currents_uA),
            "stage2_current_spread_ratio": spread_ratio(stage2_currents_uA),
        },
    )


def run_all_tests(
    dut_params: BiasGenParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or BiasGenParams()
    return {
        "structural": make_test_result(
            component="bias_gen",
            category="smoke",
            purpose="basic",
            metrics=run_structural_checks(dut_params),
            passed=True,
        ),
        "startup": run_startup_test(dut_params, sim_options=sim_options),
        "current_accuracy": run_current_accuracy_test(dut_params, sim_options=sim_options),
        "disable_off": run_disable_off_test(dut_params, sim_options=sim_options),
        "reduced_corners": run_reduced_corner_characterization_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: BiasGenParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="bias_gen")
    return results


def elaborate_dut(params: BiasGenParams | None = None) -> h.Module:
    params = params or BiasGenParams()
    return h.elaborate(bias_gen(params))


def export_spice(path: str | Path, params: BiasGenParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: BiasGenParams | None = None):
    params = params or BiasGenParams()
    dut = bias_gen(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/bias_gen_structural/bias_gen.sp")
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
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
