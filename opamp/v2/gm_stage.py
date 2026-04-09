from pathlib import Path
import re
from dataclasses import dataclass

import hdl21 as h
import numpy as np
import sky130_hdl21
from hdl21.sim import Dc, Op, Save, Sim
from vlsirtools.spice import SimOptions
from vlsirtools.spice import SupportedSimulators

from .common import extract_subckt_name, make_test_result, print_metrics_table, require_sky130_install, run_ngspice_sim
from .opamp_core import SecondStageParams, second_stage


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
    "gain_gmro": {
        "specification_aspect": "small-signal second-stage gain characterization",
        "category": "char",
        "test_name": "run_gain_gmro_test",
        "analysis_type": "Op",
        "extracted_metrics": ["gain_est", "vout_dc", "vbias_dc", "iq_uA"],
        "pass_fail_rule": "characterize nominal second-stage gain and operating point under a weak-load fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load"],
        "monte_carlo_required": False,
    },
    "bias_sensitivity": {
        "specification_aspect": "second-stage bias sensitivity characterization",
        "category": "char",
        "test_name": "run_bias_sensitivity_test",
        "analysis_type": "Op sweep",
        "extracted_metrics": ["cases", "min_vout_dc", "max_vout_dc", "min_iq_uA", "max_iq_uA"],
        "pass_fail_rule": "characterize operating-point sensitivity to the external VBIAS level",
        "required_corners": ["TT"],
        "required_operating_conditions": ["vbias sweep"],
        "monte_carlo_required": False,
    },
    "source_drive_proxy": {
        "specification_aspect": "second-stage forced source-drive proxy characterization",
        "category": "char",
        "test_name": "run_source_drive_proxy_test",
        "analysis_type": "Op sweep",
        "extracted_metrics": ["cases", "worst_vout_source", "worst_current_uA"],
        "pass_fail_rule": "characterize stage-level source-drive degradation under the same forced-current style used by the top-level follower test",
        "required_corners": ["TT"],
        "required_operating_conditions": ["source current sweep"],
        "monte_carlo_required": False,
    },
    "dc_transfer": {
        "specification_aspect": "second-stage DC transfer characterization",
        "category": "char",
        "test_name": "run_dc_transfer_test",
        "analysis_type": "Op sweep",
        "extracted_metrics": ["cases", "min_vout_dc", "max_vout_dc", "min_iq_uA", "max_iq_uA"],
        "pass_fail_rule": "characterize the enabled DC transfer curve of the stage under a weak-load fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["vin sweep"],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class SecondStageSpec:
    name: str = "second_stage"
    purpose: str = "Provide single-ended second-stage gain and output drive."
    component_class: str = "reusable block"
    pins: tuple[str, ...] = ("VIN", "VOUT", "VBIAS", "EN", "VDD", "VSS")
    measurable_behaviors: tuple[str, ...] = ("swing", "load_drive", "gain_gmro", "bias_sensitivity", "source_drive_proxy", "dc_transfer")
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


def _default_vbias_for_stage(dut_params: "SecondStageParams", vdd: float) -> float:
    # Match the actual core operating region more closely than the earlier
    # generic `vdd - 0.75` guess. The default PMOS mirror bias in `opamp_core`
    # lands well below 1 V, and stage-local diagnostics need to probe that region.
    if dut_params.device_type == "p":
        return 0.75
    return min(max(0.8, 0.3), vdd)


def _build_op_tb(
    dut_params: "SecondStageParams",
    *,
    vdd: float,
    vin: float,
    r_load: float,
    load_to_vdd: bool,
    corner,
    vbias_override: float | None = None,
) -> Sim:
    install = require_sky130_install()
    dut = second_stage(dut_params)
    v_bias = vbias_override if vbias_override is not None else _default_vbias_for_stage(dut_params, vdd)

    @h.module
    class Tb:
        VSS = h.Port()
        vin_sig, vout, vbias_sig, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        vvin = h.Vdc(dc=vin)(p=vin_sig, n=VSS)
        vbias = h.Vdc(dc=v_bias)(p=vbias_sig, n=VSS)
        ven = h.Vdc(dc=vdd)(p=en, n=VSS)
        xdut = dut(VIN=vin_sig, VOUT=vout, VBIAS=vbias_sig, EN=en, VDD=vdd_sig, VSS=VSS)
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
            Save("v(xtop.vout), v(xtop.vdd_sig), v(xtop.vin_sig), v(xtop.vbias_sig), i(v.xtop.vvvdd)"),
            install.include(corner),
        ],
    )


@h.paramclass
class SecondStageSwingTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)


@h.paramclass
class SecondStageLoadDriveTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    r_load = h.Param(dtype=h.Scalar, desc="Nominal load resistance in ohm", default=100e3)


@h.paramclass
class SecondStageGainGmroTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    vin_cm = h.Param(dtype=h.Scalar, desc="Input bias voltage in V", default=0.6)
    vin_step = h.Param(dtype=h.Scalar, desc="Small-signal input perturbation in V", default=10e-3)
    r_probe = h.Param(dtype=h.Scalar, desc="Weak output load in ohm", default=1e12)


@h.paramclass
class SecondStageBiasSensitivityTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    vin_cm = h.Param(dtype=h.Scalar, desc="Input bias voltage in V", default=0.6)
    r_probe = h.Param(dtype=h.Scalar, desc="Weak output load in ohm", default=1e12)
    vbias_start = h.Param(dtype=h.Scalar, desc="Bias sweep start voltage in V", default=0.6)
    vbias_stop = h.Param(dtype=h.Scalar, desc="Bias sweep stop voltage in V", default=1.2)
    vbias_step = h.Param(dtype=h.Scalar, desc="Bias sweep step in V", default=0.1)


@h.paramclass
class SecondStageSourceDriveTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    vin = h.Param(dtype=h.Scalar, desc="Input bias voltage in V", default=0.6)
    current_start_uA = h.Param(dtype=h.Scalar, desc="Forced source-current sweep start in uA", default=5.0)
    current_stop_uA = h.Param(dtype=h.Scalar, desc="Forced source-current sweep stop in uA", default=25.0)
    current_step_uA = h.Param(dtype=h.Scalar, desc="Forced source-current step in uA", default=5.0)
    r_probe = h.Param(dtype=h.Scalar, desc="Weak output probe resistance in ohm", default=1e12)


@h.paramclass
class SecondStageDcTransferTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    vin_start = h.Param(dtype=h.Scalar, desc="Input sweep start voltage in V", default=0.0)
    vin_stop = h.Param(dtype=h.Scalar, desc="Input sweep stop voltage in V", default=1.8)
    vin_step = h.Param(dtype=h.Scalar, desc="Input sweep step in V", default=0.1)
    r_probe = h.Param(dtype=h.Scalar, desc="Weak output load in ohm", default=1e12)


def _build_source_drive_proxy_tb(
    dut_params: "SecondStageParams",
    *,
    vdd: float,
    vin: float,
    current_load_uA: float,
    r_probe: float,
    corner,
) -> Sim:
    install = require_sky130_install()
    dut = second_stage(dut_params)
    v_bias = _default_vbias_for_stage(dut_params, vdd)
    current_load = 1e-6 * current_load_uA

    @h.module
    class Tb:
        VSS = h.Port()
        vin_sig, vout, vbias_sig, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        vvin = h.Vdc(dc=vin)(p=vin_sig, n=VSS)
        vbias = h.Vdc(dc=v_bias)(p=vbias_sig, n=VSS)
        ven = h.Vdc(dc=vdd)(p=en, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        iload = h.Idc(dc=current_load)(p=vout, n=VSS)
        xdut = dut(VIN=vin_sig, VOUT=vout, VBIAS=vbias_sig, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            h.sim.Options(name="method", value="gear"),
            h.sim.Options(name="itl1", value=500),
            Save("v(xtop.vout), v(xtop.vin_sig), v(xtop.vbias_sig), i(v.xtop.vvvdd)"),
            install.include(corner),
        ],
    )


def _build_dc_transfer_tb(
    dut_params: "SecondStageParams",
    *,
    vdd: float,
    vin: float,
    r_probe: float,
    corner,
) -> Sim:
    install = require_sky130_install()
    dut = second_stage(dut_params)
    v_bias = _default_vbias_for_stage(dut_params, vdd)

    @h.module
    class Tb:
        VSS = h.Port()
        vin_sig, vout, vbias_sig, en, vdd_sig = h.Signals(5)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        vvin = h.Vdc(dc=vin)(p=vin_sig, n=VSS)
        vbias = h.Vdc(dc=v_bias)(p=vbias_sig, n=VSS)
        ven = h.Vdc(dc=vdd)(p=en, n=VSS)
        rload = h.Res(r=r_probe)(p=vout, n=VSS)
        xdut = dut(VIN=vin_sig, VOUT=vout, VBIAS=vbias_sig, EN=en, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Op(),
            h.sim.Options(name="method", value="gear"),
            h.sim.Options(name="itl1", value=500),
            Save("v(xtop.vout), v(xtop.vin_sig), v(xtop.vbias_sig), i(v.xtop.vvvdd)"),
            install.include(corner),
        ],
    )


def build_swing_test(
    dut_params: SecondStageParams,
    tb_params: SecondStageSwingTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or SecondStageSwingTbParams()
    return _build_op_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        vin=0.0,
        r_load=float(dut_params.r_out_target),
        load_to_vdd=False,
        vbias_override=None,
        corner=corner,
    )


def run_swing_test(
    dut_params: SecondStageParams | None = None,
    tb_params: SecondStageSwingTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or SecondStageParams()
    tb_params = tb_params or SecondStageSwingTbParams()
    vdd = float(tb_params.vdd)
    sim_options = sim_options or _default_ngspice_options("second_stage_swing")
    if dut_params.device_type == "n":
        sim_hi = _build_op_tb(
            dut_params,
            vdd=vdd,
            vin=0.0,
            r_load=float(dut_params.r_out_target),
            load_to_vdd=False,
            vbias_override=None,
            corner=corner,
        )
        sim_lo = _build_op_tb(
            dut_params,
            vdd=vdd,
            vin=vdd,
            r_load=float(dut_params.r_out_target),
            load_to_vdd=True,
            vbias_override=None,
            corner=corner,
        )
    else:
        sim_hi = _build_op_tb(
            dut_params,
            vdd=vdd,
            vin=0.0,
            r_load=float(dut_params.r_out_target),
            load_to_vdd=False,
            vbias_override=None,
            corner=corner,
        )
        sim_lo = _build_op_tb(
            dut_params,
            vdd=vdd,
            vin=vdd,
            r_load=float(dut_params.r_out_target),
            load_to_vdd=True,
            vbias_override=None,
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
        component="second_stage",
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
    dut_params: SecondStageParams,
    tb_params: SecondStageLoadDriveTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or SecondStageLoadDriveTbParams()
    return _build_op_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        vin=0.0,
        r_load=float(tb_params.r_load),
        load_to_vdd=False,
        corner=corner,
    )


def build_gain_gmro_test(
    dut_params: SecondStageParams,
    tb_params: SecondStageGainGmroTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or SecondStageGainGmroTbParams()
    return _build_op_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        vin=float(tb_params.vin_cm),
        r_load=float(tb_params.r_probe),
        load_to_vdd=False,
        vbias_override=None,
        corner=corner,
    )


def run_gain_gmro_test(
    dut_params: SecondStageParams | None = None,
    tb_params: SecondStageGainGmroTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or SecondStageParams()
    tb_params = tb_params or SecondStageGainGmroTbParams()
    sim_options = sim_options or _default_ngspice_options("second_stage_gain_gmro")
    pos = run_ngspice_sim(
        _build_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            vin=float(tb_params.vin_cm) + 0.5 * float(tb_params.vin_step),
            r_load=float(tb_params.r_probe),
            load_to_vdd=False,
            vbias_override=None,
            corner=corner,
        ),
        sim_options,
    )
    neg = run_ngspice_sim(
        _build_op_tb(
            dut_params,
            vdd=float(tb_params.vdd),
            vin=float(tb_params.vin_cm) - 0.5 * float(tb_params.vin_step),
            r_load=float(tb_params.r_probe),
            load_to_vdd=False,
            vbias_override=None,
            corner=corner,
        ),
        SimOptions(simulator=sim_options.simulator, rundir=f"{sim_options.rundir}_neg"),
    )
    vout_pos = _op_scalar(pos, "v(xtop.vout)")
    vout_neg = _op_scalar(neg, "v(xtop.vout)")
    vbias_dc = 0.5 * (_op_scalar(pos, "v(xtop.vbias_sig)") + _op_scalar(neg, "v(xtop.vbias_sig)"))
    iq_abs = 0.5 * (abs(_op_scalar(pos, "i(v.xtop.vvvdd)")) + abs(_op_scalar(neg, "i(v.xtop.vvvdd)")))
    gain_est = abs((vout_pos - vout_neg) / max(float(tb_params.vin_step), 1e-18))
    metrics = {
        "vout_pos": vout_pos,
        "vout_neg": vout_neg,
        "vout_dc": 0.5 * (vout_pos + vout_neg),
        "vbias_dc": vbias_dc,
        "gain_est": gain_est,
        "iq_uA": 1e6 * iq_abs,
    }
    return make_test_result(
        component="second_stage",
        category="char",
        purpose="gain_gmro",
        metrics=metrics,
    )


def run_load_drive_test(
    dut_params: SecondStageParams | None = None,
    tb_params: SecondStageLoadDriveTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or SecondStageParams()
    tb_params = tb_params or SecondStageLoadDriveTbParams()
    vdd = float(tb_params.vdd)
    sim_options = sim_options or _default_ngspice_options("second_stage_load_drive")
    if dut_params.device_type == "n":
        source_sim = _build_op_tb(
            dut_params,
            vdd=vdd,
            vin=0.0,
            r_load=float(tb_params.r_load),
            load_to_vdd=False,
            vbias_override=None,
            corner=corner,
        )
        sink_sim = _build_op_tb(
            dut_params,
            vdd=vdd,
            vin=vdd,
            r_load=float(tb_params.r_load),
            load_to_vdd=True,
            vbias_override=None,
            corner=corner,
        )
    else:
        source_sim = _build_op_tb(
            dut_params,
            vdd=vdd,
            vin=0.0,
            r_load=float(tb_params.r_load),
            load_to_vdd=False,
            vbias_override=None,
            corner=corner,
        )
        sink_sim = _build_op_tb(
            dut_params,
            vdd=vdd,
            vin=vdd,
            r_load=float(tb_params.r_load),
            load_to_vdd=True,
            vbias_override=None,
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
        component="second_stage",
        category="char",
        purpose="load_drive",
        metrics=metrics,
    )


def run_bias_sensitivity_test(
    dut_params: SecondStageParams | None = None,
    tb_params: SecondStageBiasSensitivityTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or SecondStageParams()
    tb_params = tb_params or SecondStageBiasSensitivityTbParams()
    sim_options = sim_options or _default_ngspice_options("second_stage_bias_sensitivity")
    start = float(tb_params.vbias_start)
    stop = float(tb_params.vbias_stop)
    step = float(tb_params.vbias_step)
    cases = []
    for idx, vbias in enumerate(np.arange(start, stop + 0.5 * step, step)):
        result = run_ngspice_sim(
            _build_op_tb(
                dut_params,
                vdd=float(tb_params.vdd),
                vin=float(tb_params.vin_cm),
                r_load=float(tb_params.r_probe),
                load_to_vdd=False,
                vbias_override=float(vbias),
                corner=corner,
            ),
            SimOptions(simulator=sim_options.simulator, rundir=f"{sim_options.rundir}_{idx}"),
        )
        cases.append(
            {
                "vbias_dc": float(vbias),
                "vout_dc": _op_scalar(result, "v(xtop.vout)"),
                "iq_uA": 1e6 * abs(_op_scalar(result, "i(v.xtop.vvvdd)")),
            }
        )
    return make_test_result(
        component="second_stage",
        category="char",
        purpose="bias_sensitivity",
        metrics={
            "cases": cases,
            "min_vout_dc": min(case["vout_dc"] for case in cases),
            "max_vout_dc": max(case["vout_dc"] for case in cases),
            "min_iq_uA": min(case["iq_uA"] for case in cases),
            "max_iq_uA": max(case["iq_uA"] for case in cases),
        },
    )


def run_source_drive_proxy_test(
    dut_params: SecondStageParams | None = None,
    tb_params: SecondStageSourceDriveTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or SecondStageParams()
    tb_params = tb_params or SecondStageSourceDriveTbParams()
    sim_options = sim_options or _default_ngspice_options("second_stage_source_drive_proxy")
    start = float(tb_params.current_start_uA)
    stop = float(tb_params.current_stop_uA)
    step = float(tb_params.current_step_uA)
    cases = []
    for idx, current_uA in enumerate(np.arange(start, stop + 0.5 * step, step)):
        result = run_ngspice_sim(
            _build_source_drive_proxy_tb(
                dut_params,
                vdd=float(tb_params.vdd),
                vin=float(tb_params.vin),
                current_load_uA=float(current_uA),
                r_probe=float(tb_params.r_probe),
                corner=corner,
            ),
            SimOptions(simulator=sim_options.simulator, rundir=f"{sim_options.rundir}_{idx}"),
        )
        cases.append(
            {
                "current_uA": float(current_uA),
                "vout_source": _op_scalar(result, "v(xtop.vout)"),
                "iq_uA": 1e6 * abs(_op_scalar(result, "i(v.xtop.vvvdd)")),
            }
        )
    worst_case = min(cases, key=lambda case: case["vout_source"]) if cases else None
    return make_test_result(
        component="second_stage",
        category="char",
        purpose="source_drive_proxy",
        metrics={
            "cases": cases,
            "worst_vout_source": None if worst_case is None else worst_case["vout_source"],
            "worst_current_uA": None if worst_case is None else worst_case["current_uA"],
        },
    )


def run_dc_transfer_test(
    dut_params: SecondStageParams | None = None,
    tb_params: SecondStageDcTransferTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or SecondStageParams()
    tb_params = tb_params or SecondStageDcTransferTbParams()
    sim_options = sim_options or _default_ngspice_options("second_stage_dc_transfer")
    start = float(tb_params.vin_start)
    stop = float(tb_params.vin_stop)
    step = float(tb_params.vin_step)
    cases = []
    for idx, vin in enumerate(np.arange(start, stop + 0.5 * step, step)):
        result = run_ngspice_sim(
            _build_dc_transfer_tb(
                dut_params,
                vdd=float(tb_params.vdd),
                vin=float(vin),
                r_probe=float(tb_params.r_probe),
                corner=corner,
            ),
            SimOptions(simulator=sim_options.simulator, rundir=f"{sim_options.rundir}_{idx}"),
        )
        cases.append(
            {
                "vin_dc": float(vin),
                "vout_dc": _op_scalar(result, "v(xtop.vout)"),
                "iq_uA": 1e6 * abs(_op_scalar(result, "i(v.xtop.vvvdd)")),
            }
        )
    return make_test_result(
        component="second_stage",
        category="char",
        purpose="dc_transfer",
        metrics={
            "cases": cases,
            "min_vout_dc": min(case["vout_dc"] for case in cases),
            "max_vout_dc": max(case["vout_dc"] for case in cases),
            "min_iq_uA": min(case["iq_uA"] for case in cases),
            "max_iq_uA": max(case["iq_uA"] for case in cases),
        },
    )


def run_all_tests(
    dut_params: SecondStageParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or SecondStageParams()
    return {
        "structural": make_test_result(
            component="second_stage",
            category="smoke",
            purpose="basic",
            metrics=run_structural_checks(dut_params),
            passed=True,
        ),
        "swing": run_swing_test(dut_params, sim_options=sim_options),
        "load_drive": run_load_drive_test(dut_params, sim_options=sim_options),
        "gain_gmro": run_gain_gmro_test(dut_params, sim_options=sim_options),
        "bias_sensitivity": run_bias_sensitivity_test(dut_params, sim_options=sim_options),
        "source_drive_proxy": run_source_drive_proxy_test(dut_params, sim_options=sim_options),
        "dc_transfer": run_dc_transfer_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: SecondStageParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="second_stage")
    return results


def elaborate_dut(params: SecondStageParams | None = None) -> h.Module:
    params = params or SecondStageParams()
    return h.elaborate(second_stage(params))


def export_spice(path: str | Path, params: SecondStageParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: SecondStageParams | None = None):
    params = params or SecondStageParams()
    dut = second_stage(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/second_stage_structural/second_stage.sp")
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
