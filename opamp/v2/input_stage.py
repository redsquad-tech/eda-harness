from pathlib import Path
import re
from dataclasses import dataclass

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Op, Save, SaveMode, Sim
from vlsirtools.spice import SimOptions, SupportedSimulators

from .common import extract_subckt_name, make_test_result, print_metrics_table, require_sky130_install, run_ngspice_sim
from .opamp_core import GainStageParams, gain_stage


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator_call", "elaboration", "subckt_name", "contains_diffpair", "contains_mirror_load"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "gain_gmro": {
        "specification_aspect": "small-signal first-stage gain characterization",
        "category": "char",
        "test_name": "run_gain_gmro_test",
        "analysis_type": "Op",
        "extracted_metrics": ["diff_gain_est", "output_span", "vx_dc", "vref_dc", "tail_nominal_uA"],
        "pass_fail_rule": "characterize nominal first-stage gain behavior under the generic probe fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load"],
        "monte_carlo_required": False,
    },
    "icmr": {
        "specification_aspect": "input common-mode range support",
        "category": "contract",
        "test_name": "run_icmr_test",
        "analysis_type": "Op",
        "extracted_metrics": ["lo_in_range", "hi_in_range", "vcm_lo", "vcm_hi"],
        "pass_fail_rule": "outputs remain measurable and within supply rails at the generic common-mode endpoints",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load", "v_cm sweep"],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class GainStageSpec:
    name: str = "gain_stage"
    purpose: str = "Provide the first differential gain stage for the opamp core."
    component_class: str = "reusable block"
    pins: tuple[str, ...] = ("VINP", "VINN", "VX", "VREF", "IBIAS", "VDD", "VSS")
    measurable_behaviors: tuple[str, ...] = ("gain_gmro", "icmr")
    numeric_pass_fail_criteria: tuple[str, ...] = ("generic common-mode contract only; product gain budgets belong in external budget tests",)
    required_corners: tuple[str, ...] = ("TT",)
    statistical_verification_required: bool = False


@h.paramclass
class GainStageGainGmroTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    v_cm = h.Param(dtype=h.Scalar, desc="Input common-mode voltage in V", default=0.4)
    v_diff = h.Param(dtype=h.Scalar, desc="Differential excitation in V", default=10e-3)
    r_probe = h.Param(dtype=h.Scalar, desc="Output probe resistance in ohm", default=1e12)


@h.paramclass
class GainStageIcmrTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    v_cm_lo = h.Param(dtype=h.Scalar, desc="Low-end common mode in V", default=0.0)
    v_cm_hi = h.Param(dtype=h.Scalar, desc="High-end common mode in V", default=0.9)
    r_probe = h.Param(dtype=h.Scalar, desc="Output probe resistance in ohm", default=1e12)


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


def _build_op_tb(
    dut_params: GainStageParams,
    *,
    vdd: float,
    v_cm: float,
    v_diff: float,
    r_probe: float,
    corner,
) -> Sim:
    install = require_sky130_install()
    dut = gain_stage(dut_params)
    vinp = v_cm + 0.5 * v_diff
    vinn = v_cm - 0.5 * v_diff

    @h.module
    class Tb:
        VSS = h.Port()
        vinp_sig, vinn_sig, vx, vref, ibias, vdd_sig = h.Signals(6)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        vvinp = h.Vdc(dc=vinp)(p=vinp_sig, n=VSS)
        vvinn = h.Vdc(dc=vinn)(p=vinn_sig, n=VSS)
        ibias_src = h.Idc(dc=dut_params.i_tail)(p=vdd_sig, n=ibias)
        rprobe_vx = h.Res(r=r_probe)(p=vx, n=VSS)
        rprobe_vref = h.Res(r=r_probe)(p=vref, n=VSS)
        xdut = dut(VINP=vinp_sig, VINN=vinn_sig, VX=vx, VREF=vref, IBIAS=ibias, VDD=vdd_sig, VSS=VSS)

    return Sim(tb=Tb, attrs=[Op(), Save(SaveMode.ALL), install.include(corner)])


def build_gain_gmro_test(
    dut_params: GainStageParams,
    tb_params: GainStageGainGmroTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or GainStageGainGmroTbParams()
    return _build_op_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        v_cm=float(tb_params.v_cm),
        v_diff=float(tb_params.v_diff),
        r_probe=float(tb_params.r_probe),
        corner=corner,
    )


def run_gain_gmro_test(
    dut_params: GainStageParams | None = None,
    tb_params: GainStageGainGmroTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or GainStageParams()
    tb_params = tb_params or GainStageGainGmroTbParams()
    pos = run_ngspice_sim(
        build_gain_gmro_test(dut_params, tb_params, corner=corner),
        sim_options if sim_options is not None else _default_ngspice_options("gain_stage_gain_pos"),
    )
    neg = run_ngspice_sim(
        _build_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            v_cm=float(tb_params.v_cm),
            v_diff=-float(tb_params.v_diff),
            r_probe=float(tb_params.r_probe),
            corner=corner,
        ),
        _default_ngspice_options("gain_stage_gain_neg"),
    )
    vx_pos = _op_scalar(pos, "v(xtop.vx)")
    vref_pos = _op_scalar(pos, "v(xtop.vref)")
    vx_neg = _op_scalar(neg, "v(xtop.vx)")
    vref_neg = _op_scalar(neg, "v(xtop.vref)")
    gain_est = abs((vx_pos - vx_neg) / (2 * float(tb_params.v_diff)))
    metrics = {
        "vx_pos": vx_pos,
        "vref_pos": vref_pos,
        "vx_neg": vx_neg,
        "vref_neg": vref_neg,
        "vx_dc": 0.5 * (vx_pos + vx_neg),
        "vref_dc": 0.5 * (vref_pos + vref_neg),
        "tail_nominal_uA": 1e6 * float(dut_params.i_tail),
        "diff_gain_est": gain_est,
        "output_span": abs(vx_pos - vx_neg),
    }
    return make_test_result(
        component="gain_stage",
        category="char",
        purpose="gain_gmro",
        metrics=metrics,
    )


def build_icmr_test(
    dut_params: GainStageParams,
    tb_params: GainStageIcmrTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or GainStageIcmrTbParams()
    return _build_op_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        v_cm=float(tb_params.v_cm_lo),
        v_diff=0.0,
        r_probe=float(tb_params.r_probe),
        corner=corner,
    )


def run_icmr_test(
    dut_params: GainStageParams | None = None,
    tb_params: GainStageIcmrTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or GainStageParams()
    tb_params = tb_params or GainStageIcmrTbParams()
    lo = run_ngspice_sim(
        _build_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            v_cm=float(tb_params.v_cm_lo),
            v_diff=0.0,
            r_probe=float(tb_params.r_probe),
            corner=corner,
        ),
        sim_options if sim_options is not None else _default_ngspice_options("gain_stage_icmr_lo"),
    )
    hi = run_ngspice_sim(
        _build_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            v_cm=float(tb_params.v_cm_hi),
            v_diff=0.0,
            r_probe=float(tb_params.r_probe),
            corner=corner,
        ),
        _default_ngspice_options("gain_stage_icmr_hi"),
    )
    lo_vx = _op_scalar(lo, "v(xtop.vx)")
    lo_vref = _op_scalar(lo, "v(xtop.vref)")
    hi_vx = _op_scalar(hi, "v(xtop.vx)")
    hi_vref = _op_scalar(hi, "v(xtop.vref)")
    metrics = {
        "vcm_lo": float(tb_params.v_cm_lo),
        "vcm_hi": float(tb_params.v_cm_hi),
        "vx_lo": lo_vx,
        "vref_lo": lo_vref,
        "vx_hi": hi_vx,
        "vref_hi": hi_vref,
        "lo_in_range": 0.0 <= lo_vx <= float(tb_params.vdd) and 0.0 <= lo_vref <= float(tb_params.vdd),
        "hi_in_range": 0.0 <= hi_vx <= float(tb_params.vdd) and 0.0 <= hi_vref <= float(tb_params.vdd),
    }
    return make_test_result(
        component="gain_stage",
        category="contract",
        purpose="icmr",
        metrics=metrics,
        passed=bool(metrics["lo_in_range"] and metrics["hi_in_range"]),
        margin={
            "lo_headroom_min": min(lo_vx, lo_vref),
            "hi_headroom_max": float(tb_params.vdd) - max(hi_vx, hi_vref),
        },
    )


def run_all_tests(
    dut_params: GainStageParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or GainStageParams()
    return {
        "structural": make_test_result(
            component="gain_stage",
            category="smoke",
            purpose="basic",
            metrics=run_structural_checks(dut_params),
            passed=True,
        ),
        "gain_gmro": run_gain_gmro_test(dut_params, sim_options=sim_options),
        "icmr": run_icmr_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: GainStageParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="gain_stage")
    return results


def elaborate_dut(params: GainStageParams | None = None) -> h.Module:
    params = params or GainStageParams()
    return h.elaborate(gain_stage(params))


def export_spice(path: str | Path, params: GainStageParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: GainStageParams | None = None):
    params = params or GainStageParams()
    dut = gain_stage(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/gain_stage_structural/gain_stage.sp")
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
        "contains_diffpair": "DiffpairP" in text,
        "contains_mirror_load": text.count("sky130_fd_pr__nfet_01v8") >= 2,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
