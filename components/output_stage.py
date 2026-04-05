from pathlib import Path
import re
from dataclasses import dataclass

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Op, Save, Sim
from vlsirtools.spice import SimOptions
from vlsirtools.spice import SupportedSimulators

from components import extract_subckt_name, make_test_result, print_metrics_table, require_sky130_install, run_ngspice_sim


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
    "swing": {
        "specification_aspect": "single-ended output swing behavior",
        "category": "contract",
        "test_name": "run_swing_test",
        "analysis_type": "Dc/Op",
        "extracted_metrics": ["output_swing_low", "output_swing_high"],
        "pass_fail_rule": "component exposes measurable low and high swing operating points under the generic load fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load"],
        "monte_carlo_required": False,
    },
    "load_drive": {
        "specification_aspect": "load drive",
        "category": "char",
        "test_name": "run_load_drive_test",
        "analysis_type": "Op",
        "extracted_metrics": ["source_current", "sink_current"],
        "pass_fail_rule": "characterize nominal source and sink drive under the generic current-load fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["current_load"],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class OutputStageSpec:
    name: str = "output_stage"
    purpose: str = "Provide single-ended output buffering and load drive."
    component_class: str = "reusable block"
    pins: tuple[str, ...] = ("VIN", "VOUT", "IBIAS", "VDD", "VSS")
    measurable_behaviors: tuple[str, ...] = ("swing", "load_drive")
    numeric_pass_fail_criteria: tuple[str, ...] = ("generic swing and drive contracts only; product output-drive budgets belong in external budget tests",)
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
    return SimOptions(simulator=SupportedSimulators.NGSPICE, rundir=f"./tmp/{test_name}")


def _op_scalar(result, signal_name: str) -> float:
    op = result.an[0].op
    target = signal_name.lower()
    for name, value in zip(op.signals, op.data):
        if name.lower() == target:
            return float(value)
    raise RuntimeError(f"Signal {signal_name} not found in op result: {list(op.signals)}")


@h.paramclass
class OutputStageParams:
    style = h.Param(dtype=str, desc="Output-stage topology", default="push_pull")
    device_type = h.Param(dtype=str, desc="Amplifying device polarity", default="p")
    w_amp = h.Param(dtype=h.Scalar, desc="Amplifier width in um", default=4.0)
    l_amp = h.Param(dtype=h.Scalar, desc="Amplifier length in um", default=1.0)
    nf_amp = h.Param(dtype=int, desc="Amplifier fingers", default=1)
    m_amp = h.Param(dtype=int, desc="Amplifier multiplier", default=1)
    w_load_scale = h.Param(dtype=h.Scalar, desc="Load width scale relative to amplifier", default=3.0)
    l_load = h.Param(dtype=h.Scalar, desc="Load length in um", default=1.0)
    i_bias = h.Param(dtype=h.Scalar, desc="Bias current metadata in A", default=2e-6)
    r_out_target = h.Param(dtype=h.Scalar, desc="Nominal output load in ohm", default=100e3)


@h.paramclass
class OutputStageSwingTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)


@h.paramclass
class OutputStageLoadDriveTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    r_load = h.Param(dtype=h.Scalar, desc="Nominal load resistance in ohm", default=100e3)


@h.generator
def output_stage(params: OutputStageParams) -> h.Module:
    if params.style not in ("common_source", "source_follower", "push_pull"):
        raise ValueError(f"Unsupported style: {params.style}")
    if params.device_type not in ("n", "p"):
        raise ValueError(f"Unsupported device_type: {params.device_type}")
    if params.w_amp <= 0 or params.l_amp <= 0 or params.w_load_scale <= 0 or params.l_load <= 0:
        raise ValueError("w_amp, l_amp, w_load_scale, and l_load must be positive")
    if params.nf_amp < 1 or params.m_amp < 1:
        raise ValueError("nf_amp and m_amp must be >= 1")
    if params.i_bias <= 0 or params.r_out_target <= 0:
        raise ValueError("i_bias and r_out_target must be positive")

    mod = h.Module(name="OutputStage")
    mod.VIN, mod.VOUT, mod.IBIAS, mod.VDD, mod.VSS = h.Ports(5)

    if params.style == "source_follower":
        nmos = _mos_primitive("NMOS_1p8V_STD")
        pmos = _mos_primitive("PMOS_1p8V_STD")
        npar = _mos_params(params.w_amp, params.l_amp, params.nf_amp, params.m_amp)
        ppar = _mos_params(params.w_amp * params.w_load_scale, params.l_load, params.nf_amp, params.m_amp)
        # Complementary source follower:
        # - NMOS drain at VDD, source at VOUT for pull-up assistance
        # - PMOS drain at VSS, source at VOUT for pull-down assistance
        # Both gates are driven from VIN; the stage is non-inverting but does
        # require level-shift-aware system integration at the opamp top level.
        mod.m_n = nmos(npar)(d=mod.VDD, g=mod.VIN, s=mod.VOUT, b=mod.VSS)
        mod.m_p = pmos(ppar)(d=mod.VSS, g=mod.VIN, s=mod.VOUT, b=mod.VDD)
    elif params.style == "push_pull":
        nmos = _mos_primitive("NMOS_1p8V_STD")
        pmos = _mos_primitive("PMOS_1p8V_STD")
        npar = _mos_params(params.w_amp, params.l_amp, params.nf_amp, params.m_amp)
        ppar = _mos_params(params.w_amp * params.w_load_scale, params.l_load, params.nf_amp, params.m_amp)
        # CMOS inverter-like output stage. Both pull-up and pull-down are
        # signal-driven from VIN, making it suitable as a true drive stage.
        mod.m_p = pmos(ppar)(d=mod.VOUT, g=mod.VIN, s=mod.VDD, b=mod.VDD)
        mod.m_n = nmos(npar)(d=mod.VOUT, g=mod.VIN, s=mod.VSS, b=mod.VSS)
    else:
        amp_name = "NMOS_1p8V_STD" if params.device_type == "n" else "PMOS_1p8V_STD"
        load_name = "PMOS_1p8V_STD" if params.device_type == "n" else "NMOS_1p8V_STD"
        amp_prim = _mos_primitive(amp_name)
        load_prim = _mos_primitive(load_name)
        amp_par = _mos_params(params.w_amp, params.l_amp, params.nf_amp, params.m_amp)
        load_par = _mos_params(params.w_amp * params.w_load_scale, params.l_load, params.nf_amp, params.m_amp)
        if params.device_type == "n":
            mod.m_load = load_prim(load_par)(d=mod.VOUT, g=mod.IBIAS, s=mod.VDD, b=mod.VDD)
            mod.m_amp = amp_prim(amp_par)(d=mod.VOUT, g=mod.VIN, s=mod.VSS, b=mod.VSS)
        else:
            mod.m_load = load_prim(load_par)(d=mod.VOUT, g=mod.IBIAS, s=mod.VSS, b=mod.VSS)
            mod.m_amp = amp_prim(amp_par)(d=mod.VOUT, g=mod.VIN, s=mod.VDD, b=mod.VDD)

    mod.ibias_probe = h.Res(r=1e9)(p=mod.IBIAS, n=mod.VSS)
    return mod


def _build_op_tb(
    dut_params: OutputStageParams,
    *,
    vdd: float,
    vin: float,
    r_load: float,
    load_to_vdd: bool,
    corner,
) -> Sim:
    install = require_sky130_install()
    dut = output_stage(dut_params)
    v_bias = 0.75 if dut_params.device_type == "p" else max(vdd - 0.75, 0.3)

    @h.module
    class Tb:
        VSS = h.Port()
        vin_sig, vout, ibias, vdd_sig = h.Signals(4)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        vvin = h.Vdc(dc=vin)(p=vin_sig, n=VSS)
        vbias = h.Vdc(dc=v_bias)(p=ibias, n=VSS)
        xdut = dut(VIN=vin_sig, VOUT=vout, IBIAS=ibias, VDD=vdd_sig, VSS=VSS)
        if load_to_vdd:
            rload = h.Res(r=r_load)(p=vdd_sig, n=vout)
        else:
            rload = h.Res(r=r_load)(p=vout, n=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            h.sim.Options(name="method", value="gear"),
            h.sim.Options(name="itl1", value=500),
            Save("v(xtop.vout), v(xtop.vdd_sig), v(xtop.vin_sig), v(xtop.ibias), i(v.xtop.vvvdd)"),
            install.include(corner),
        ],
    )


def build_swing_test(
    dut_params: OutputStageParams,
    tb_params: OutputStageSwingTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or OutputStageSwingTbParams()
    return _build_op_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        vin=0.0,
        r_load=float(dut_params.r_out_target),
        load_to_vdd=False,
        corner=corner,
    )


def run_swing_test(
    dut_params: OutputStageParams | None = None,
    tb_params: OutputStageSwingTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OutputStageParams()
    tb_params = tb_params or OutputStageSwingTbParams()
    vdd = float(tb_params.vdd)
    sim_options = sim_options or _default_ngspice_options("output_stage_swing")
    sim_hi = _build_op_tb(
        dut_params,
        vdd=vdd,
        vin=0.0,
        r_load=float(dut_params.r_out_target),
        load_to_vdd=False,
        corner=corner,
    )
    sim_lo = _build_op_tb(
        dut_params,
        vdd=vdd,
        vin=vdd,
        r_load=float(dut_params.r_out_target),
        load_to_vdd=True,
        corner=corner,
    )
    hi = run_ngspice_sim(sim_hi, sim_options)
    lo = run_ngspice_sim(sim_lo, SimOptions(simulator=sim_options.simulator, rundir=f"{sim_options.rundir}_low"))
    swing_high = _op_scalar(hi, "v(xtop.vout)")
    swing_low = _op_scalar(lo, "v(xtop.vout)")
    metrics = {
        "output_swing_low": swing_low,
        "output_swing_high": swing_high,
        "swing_span": swing_high - swing_low,
    }
    return make_test_result(
        component="output_stage",
        category="contract",
        purpose="swing",
        metrics=metrics,
        passed=bool(0.0 <= swing_low < swing_high <= float(tb_params.vdd)),
        margin={
            "low_headroom": swing_low,
            "high_headroom": float(tb_params.vdd) - swing_high,
        },
    )


def build_load_drive_test(
    dut_params: OutputStageParams,
    tb_params: OutputStageLoadDriveTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or OutputStageLoadDriveTbParams()
    return _build_op_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        vin=0.0,
        r_load=float(tb_params.r_load),
        load_to_vdd=False,
        corner=corner,
    )


def run_load_drive_test(
    dut_params: OutputStageParams | None = None,
    tb_params: OutputStageLoadDriveTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OutputStageParams()
    tb_params = tb_params or OutputStageLoadDriveTbParams()
    vdd = float(tb_params.vdd)
    sim_options = sim_options or _default_ngspice_options("output_stage_load_drive")
    source_sim = _build_op_tb(
        dut_params,
        vdd=vdd,
        vin=0.0,
        r_load=float(tb_params.r_load),
        load_to_vdd=False,
        corner=corner,
    )
    sink_sim = _build_op_tb(
        dut_params,
        vdd=vdd,
        vin=vdd,
        r_load=float(tb_params.r_load),
        load_to_vdd=True,
        corner=corner,
    )
    source = run_ngspice_sim(source_sim, sim_options)
    sink = run_ngspice_sim(sink_sim, SimOptions(simulator=sim_options.simulator, rundir=f"{sim_options.rundir}_sink"))
    vout_source = _op_scalar(source, "v(xtop.vout)")
    vout_sink = _op_scalar(sink, "v(xtop.vout)")
    metrics = {
        "source_current": max(vout_source / float(tb_params.r_load), 0.0),
        "sink_current": max((float(tb_params.vdd) - vout_sink) / float(tb_params.r_load), 0.0),
        "vout_source": vout_source,
        "vout_sink": vout_sink,
    }
    return make_test_result(
        component="output_stage",
        category="char",
        purpose="load_drive",
        metrics=metrics,
    )


def run_all_tests(
    dut_params: OutputStageParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OutputStageParams()
    return {
        "structural": make_test_result(
            component="output_stage",
            category="smoke",
            purpose="basic",
            metrics=run_structural_checks(dut_params),
            passed=True,
        ),
        "swing": run_swing_test(dut_params, sim_options=sim_options),
        "load_drive": run_load_drive_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: OutputStageParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="output_stage")
    return results


def elaborate_dut(params: OutputStageParams | None = None) -> h.Module:
    params = params or OutputStageParams()
    return h.elaborate(output_stage(params))


def export_spice(path: str | Path, params: OutputStageParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: OutputStageParams | None = None):
    params = params or OutputStageParams()
    dut = output_stage(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/output_stage_structural/output_stage.sp")
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
    if params.style in ("source_follower", "push_pull"):
        checks["contains_device"] = "sky130_fd_pr__nfet_01v8" in text and "sky130_fd_pr__pfet_01v8" in text
    elif params.device_type == "n":
        checks["contains_device"] = "sky130_fd_pr__nfet_01v8" in text
    else:
        checks["contains_device"] = "sky130_fd_pr__pfet_01v8" in text
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
