from pathlib import Path
import re
from dataclasses import dataclass

import hdl21 as h
import numpy as np
from hdl21.sim import Save, SaveMode, Sim, Tran
from vlsirtools.spice import SimOptions

from components import extract_subckt_name, make_test_result, print_metrics_table, require_sky130_install, run_ngspice_sim
from components.frontend_az import (
    FrontendAzParams,
    frontend_az,
    run_pedestal_zero_input_test,
    run_settling_in_phase_window_test,
)
from components.opamp_core import (
    OpampCoreClosedLoopStepTbParams,
    OpampCoreOpenLoopTbParams,
    OpampCoreParams,
    opamp_core,
    run_closed_loop_step_test as run_core_closed_loop_step_test,
    run_open_loop_test as run_core_open_loop_test,
)


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator_call", "elaboration", "subckt_name", "contains_frontend_az", "contains_opamp_core"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "open_loop": {
        "specification_aspect": "core-referred open-loop AC proxy characterization",
        "category": "char",
        "test_name": "run_open_loop_test",
        "analysis_type": "Ac/Op",
        "extracted_metrics": ["aol_db", "gbw_hz", "phase_margin_deg", "gain_margin_db", "iq_uA", "ac_fixture_ok", "measurement_mode"],
        "pass_fail_rule": "characterize nominal core-referred open-loop behavior for the switched top-level composition",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load"],
        "monte_carlo_required": False,
    },
    "closed_loop_step": {
        "specification_aspect": "top-level closed-loop step response",
        "category": "contract",
        "test_name": "run_closed_loop_step_test",
        "analysis_type": "Tran",
        "extracted_metrics": ["vout_final", "overshoot"],
        "pass_fail_rule": "top-level block produces measurable closed-loop transient behavior under the generic unity_feedback fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["unity_feedback"],
        "monte_carlo_required": False,
    },
    "noise_and_offset": {
        "specification_aspect": "top-level residual offset",
        "category": "contract",
        "test_name": "run_noise_and_offset_test",
        "analysis_type": "Tran/Noise",
        "extracted_metrics": ["residual_offset_uV", "pedestal_uV", "settling_residue_uV"],
        "pass_fail_rule": "top-level AZ path exposes measurable residual-offset and pedestal behavior",
        "required_corners": ["TT"],
        "required_operating_conditions": ["sc_loop"],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class OpampAzTopSpec:
    name: str = "opamp_az_top"
    purpose: str = "Integrate the auto-zero frontend with the opamp core."
    component_class: str = "top-level composition"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOUT", "EN", "PHI1", "PHI2", "VDD", "VSS")
    measurable_behaviors: tuple[str, ...] = ("open_loop", "closed_loop_step", "noise_and_offset")
    numeric_pass_fail_criteria: tuple[str, ...] = ("generic composition contracts only; product budgets belong in external budget tests",)
    required_corners: tuple[str, ...] = ("TT",)
    statistical_verification_required: bool = False


@h.paramclass
class OpampAzTopParams:
    frontend_az_params = h.Param(dtype=FrontendAzParams, desc="Frontend AZ parameters", default=FrontendAzParams())
    opamp_core_params = h.Param(dtype=OpampCoreParams, desc="Core opamp parameters", default=OpampCoreParams())


@h.paramclass
class OpampAzTopOpenLoopTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Load capacitance in F", default=1e-12)


@h.paramclass
class OpampAzTopClosedLoopStepTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Load capacitance in F", default=1e-12)
    v_step = h.Param(dtype=h.Scalar, desc="Step amplitude in V", default=10e-3)


@h.paramclass
class OpampAzTopNoiseAndOffsetTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=8e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=50e-9)


@h.generator
def opamp_az_top(params: OpampAzTopParams) -> h.Module:
    frontend_inst = frontend_az(params.frontend_az_params)
    core_inst = opamp_core(params.opamp_core_params)

    mod = h.Module(name="OpampAzTop")
    mod.VINP, mod.VINN, mod.VOUT, mod.EN, mod.PHI1, mod.PHI2, mod.VDD, mod.VSS = h.Ports(8)
    mod.vxp, mod.vxn = h.Signals(2)

    mod.xfront = frontend_inst(VINP=mod.VINP, VINN=mod.VINN, VXP=mod.vxp, VXN=mod.vxn, PHI1=mod.PHI1, PHI2=mod.PHI2, VDD=mod.VDD, VSS=mod.VSS)
    mod.xcore = core_inst(VINP=mod.vxp, VINN=mod.vxn, VOUT=mod.VOUT, EN=mod.EN, VDD=mod.VDD, VSS=mod.VSS)
    return mod


def _build_top_smoke_tb(
    dut_params: OpampAzTopParams,
    *,
    vdd: float,
    v_step: float,
    c_load: float,
    tstop: float,
    tstep: float,
    corner,
) -> Sim:
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)
    period = 2e-6
    nonoverlap = 0.1 * period
    phi_width = 0.5 * period - nonoverlap

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, phi1, phi2, vdd_sig = h.Signals(7)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=vdd)(p=en, n=VSS)
        vvinp = h.Vpulse(v1=0.0, v2=v_step, delay=3 * period, rise=50e-9, fall=50e-9, width=tstop, period=2 * tstop)(p=vinp, n=VSS)
        vvinn = h.Vdc(dc=0.0)(p=vinn, n=VSS)
        vphi1 = h.Vpulse(
            v1=0.0,
            v2=vdd,
            delay=0.0,
            rise=20e-9,
            fall=20e-9,
            width=phi_width,
            period=period,
        )(p=phi1, n=VSS)
        vphi2 = h.Vpulse(
            v1=0.0,
            v2=vdd,
            delay=0.5 * period,
            rise=20e-9,
            fall=20e-9,
            width=phi_width,
            period=period,
        )(p=phi2, n=VSS)
        cload = h.Cap(c=c_load)(p=vout, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, PHI1=phi1, PHI2=phi2, VDD=vdd_sig, VSS=VSS)

    return Sim(tb=Tb, attrs=[Tran(tstop=tstop, tstep=tstep), Save(SaveMode.ALL), install.include(corner)])


def _tran_waveform(result, signal_name: str):
    tran = result.an[0].tran
    target = signal_name.lower()
    signals = list(tran.signals)
    idx = next((i for i, name in enumerate(signals) if name.lower() == target), None)
    if idx is None:
        raise RuntimeError(f"Signal {signal_name} not found in tran result: {signals}")
    nsignals = len(signals)
    data = list(tran.data)
    npts = len(data) // nsignals
    start = idx * npts
    return np.asarray(data[start : start + npts], dtype=float)


def build_open_loop_test(
    dut_params: OpampAzTopParams,
    tb_params: OpampAzTopOpenLoopTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or OpampAzTopOpenLoopTbParams()
    return _build_top_smoke_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        v_step=1e-3,
        c_load=float(tb_params.c_load),
        tstop=5e-6,
        tstep=50e-9,
        corner=corner,
    )


def run_open_loop_test(
    dut_params: OpampAzTopParams | None = None,
    tb_params: OpampAzTopOpenLoopTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampAzTopParams()
    tb_params = tb_params or OpampAzTopOpenLoopTbParams()
    core = run_core_open_loop_test(
        dut_params.opamp_core_params,
        OpampCoreOpenLoopTbParams(vdd=tb_params.vdd, c_load=tb_params.c_load),
        corner=corner,
        sim_options=sim_options,
    )
    core_metrics = core["metrics"]
    return make_test_result(
        component="opamp_az_top",
        category="char",
        purpose="open_loop",
        metrics={
            "vout_pos": core_metrics["vout_pos"],
            "vout_neg": core_metrics["vout_neg"],
            "gain_est": core_metrics["gain_est"],
            "aol_db": core_metrics["aol_db"],
            "gbw_hz": core_metrics["gbw_hz"],
            "phase_margin_deg": core_metrics["phase_margin_deg"],
            "gain_margin_db": core_metrics["gain_margin_db"],
            "iq_uA": core_metrics["iq_uA"],
            "core_bias_ratio_est": core_metrics["bias_ratio_est"],
            "ac_fixture_ok": core_metrics["ac_fixture_ok"],
            "measurement_mode": "core_proxy",
        },
    )


def build_closed_loop_step_test(
    dut_params: OpampAzTopParams,
    tb_params: OpampAzTopClosedLoopStepTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or OpampAzTopClosedLoopStepTbParams()
    return _build_top_smoke_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        v_step=float(tb_params.v_step),
        c_load=float(tb_params.c_load),
        tstop=10e-6,
        tstep=100e-9,
        corner=corner,
    )


def run_closed_loop_step_test(
    dut_params: OpampAzTopParams | None = None,
    tb_params: OpampAzTopClosedLoopStepTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampAzTopParams()
    tb_params = tb_params or OpampAzTopClosedLoopStepTbParams()
    core = run_core_closed_loop_step_test(
        dut_params.opamp_core_params,
        OpampCoreClosedLoopStepTbParams(vdd=tb_params.vdd, c_load=tb_params.c_load, v_step=tb_params.v_step),
        corner=corner,
        sim_options=sim_options,
    )
    core_metrics = core["metrics"]
    return make_test_result(
        component="opamp_az_top",
        category="contract",
        purpose="closed_loop_step",
        metrics={
            "vout_final": core_metrics["vout_final"],
            "overshoot": core_metrics["overshoot"],
            "target_step": core_metrics["target_step"],
        },
        passed=bool(core["pass"]),
        margin=core.get("margin", {}),
    )


def build_noise_and_offset_test(
    dut_params: OpampAzTopParams,
    tb_params: OpampAzTopNoiseAndOffsetTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or OpampAzTopNoiseAndOffsetTbParams()
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)
    period = 2e-6
    nonoverlap = 0.1 * period
    phi_width = 0.5 * period - nonoverlap

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, phi1, phi2, vdd_sig = h.Signals(7)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=tb_params.vdd)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.0)(p=vinp, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn)
        vphi1 = h.Vpulse(
            v1=0.0,
            v2=tb_params.vdd,
            delay=0.0,
            rise=20e-9,
            fall=20e-9,
            width=phi_width,
            period=period,
        )(p=phi1, n=VSS)
        vphi2 = h.Vpulse(
            v1=0.0,
            v2=tb_params.vdd,
            delay=0.5 * period,
            rise=20e-9,
            fall=20e-9,
            width=phi_width,
            period=period,
        )(p=phi2, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, PHI1=phi1, PHI2=phi2, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=float(tb_params.tstop), tstep=float(tb_params.tstep)),
            Save("time, v(xtop.vout), v(xtop.phi2)"),
            install.include(corner),
        ],
    )


def run_noise_and_offset_test(
    dut_params: OpampAzTopParams | None = None,
    tb_params: OpampAzTopNoiseAndOffsetTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampAzTopParams()
    tb_params = tb_params or OpampAzTopNoiseAndOffsetTbParams()
    sim = build_noise_and_offset_test(dut_params, tb_params, corner=corner)
    sim_options = sim_options or SimOptions(rundir="./tmp/opamp_az_top_noise_and_offset")
    result = run_ngspice_sim(sim, sim_options)
    time = _tran_waveform(result, "time")
    vout = _tran_waveform(result, "v(xtop.vout)")
    phi2 = _tran_waveform(result, "v(xtop.phi2)")
    active_idx = np.flatnonzero(phi2 > 0.5 * float(tb_params.vdd))
    if len(active_idx) == 0:
        raise RuntimeError("No amplify-phase window detected in opamp_az_top noise_and_offset test")
    run_start = int(active_idx[-1])
    while run_start > 0 and float(phi2[run_start - 1]) > 0.5 * float(tb_params.vdd):
        run_start -= 1
    run_stop = int(active_idx[-1])
    residual_offset_uv = 1e6 * abs(float(vout[run_stop]))
    pedestal_uv = 1e6 * abs(float(np.max(vout[run_start : run_stop + 1]) - np.min(vout[run_start : run_stop + 1])))
    window = max(float(time[run_stop]) - float(time[run_start]), 1e-18)
    phase_window_utilization = float(time[run_stop] - time[run_start]) / window
    metrics = {
        "residual_offset_uV": residual_offset_uv,
        "pedestal_uV": pedestal_uv,
        "settling_residue_uV": residual_offset_uv,
        "vout_final": float(vout[run_stop]),
        "phase_window_utilization": phase_window_utilization,
    }
    return make_test_result(
        component="opamp_az_top",
        category="contract",
        purpose="noise_and_offset",
        metrics=metrics,
        passed=bool(np.isfinite(residual_offset_uv) and np.isfinite(pedestal_uv)),
    )


def run_all_tests(
    dut_params: OpampAzTopParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampAzTopParams()
    return {
        "structural": make_test_result(
            component="opamp_az_top",
            category="smoke",
            purpose="basic",
            metrics=run_structural_checks(dut_params),
            passed=True,
        ),
        "open_loop": run_open_loop_test(dut_params, sim_options=sim_options),
        "closed_loop_step": run_closed_loop_step_test(dut_params, sim_options=sim_options),
        "noise_and_offset": run_noise_and_offset_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: OpampAzTopParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="opamp_az_top")
    return results


def elaborate_dut(params: OpampAzTopParams | None = None) -> h.Module:
    params = params or OpampAzTopParams()
    return h.elaborate(opamp_az_top(params))


def export_spice(path: str | Path, params: OpampAzTopParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: OpampAzTopParams | None = None):
    params = params or OpampAzTopParams()
    dut = opamp_az_top(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/opamp_az_top_structural/opamp_az_top.sp")
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
        "contains_frontend_az": "FrontendAz" in text,
        "contains_opamp_core": "OpampCore" in text,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
