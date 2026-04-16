from io import StringIO
from pathlib import Path
import re
from dataclasses import dataclass

import hdl21 as h
import numpy as np
from hdl21.sim import Save, Sim, Tran
from vlsirtools.spice import SimOptions, SupportedSimulators

from components import extract_subckt_name, make_test_result, print_metrics_table, require_sky130_install, run_ngspice_sim
from components.tg_switch import TgSwitchParams, tg_switch
from .pdk_passives import pdk_mim_capacitor, pdk_resistor


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator_call", "elaboration", "subckt_name", "contains_tg_switch", "contains_pdk_resistor", "contains_pdk_mim_cap"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "pedestal_zero_input": {
        "specification_aspect": "zero-input switched-cap pedestal behavior",
        "category": "contract",
        "test_name": "run_pedestal_zero_input_test",
        "analysis_type": "Tran",
        "extracted_metrics": ["pedestal_uV"],
        "pass_fail_rule": "zero-input switching sequence produces a finite and measurable pedestal result",
        "required_corners": ["TT"],
        "required_operating_conditions": ["hold_cap"],
        "monte_carlo_required": False,
    },
    "settling_in_phase_window": {
        "specification_aspect": "settling during amplify phase",
        "category": "contract",
        "test_name": "run_settling_in_phase_window_test",
        "analysis_type": "Tran",
        "extracted_metrics": ["settling_residue_uV", "phase_window_utilization"],
        "pass_fail_rule": "frontend exposes measurable settling behavior during the amplify phase window",
        "required_corners": ["TT"],
        "required_operating_conditions": ["sc_loop"],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class FrontendAzSpec:
    name: str = "frontend_az_v3"
    purpose: str = "Native v3 auto-zero frontend with sampled output-error correction applied to the non-inverting path."
    component_class: str = "main-branch reusable block"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOFF", "VXP", "VXN", "PHI1", "PHI1B", "PHI2", "PHI2B", "PHI3", "PHI3B", "VDD", "VSS")
    measurable_behaviors: tuple[str, ...] = ("pedestal_zero_input", "settling_in_phase_window")
    numeric_pass_fail_criteria: tuple[str, ...] = ("generic transient contract only; product budgets belong in external budget tests",)
    required_corners: tuple[str, ...] = ("TT",)
    statistical_verification_required: bool = False


@h.paramclass
class FrontendAzParams:
    c_az = h.Param(dtype=h.Scalar, desc="Per-side AZ capacitor in F", default=1e-12)
    w_sw_n = h.Param(dtype=h.Scalar, desc="NMOS switch width in um", default=0.65)
    w_sw_p = h.Param(dtype=h.Scalar, desc="PMOS switch width in um", default=1.0)
    l_sw = h.Param(dtype=h.Scalar, desc="Switch length in um", default=0.15)
    nf_sw = h.Param(dtype=int, desc="Switch fingers", default=1)
    m_sw = h.Param(dtype=int, desc="Switch multiplier", default=1)
    use_dummy_switch = h.Param(dtype=bool, desc="Add dummy TG devices", default=False)
    r_vcm_top = h.Param(dtype=h.Scalar, desc="Top resistor for sampled output-error attenuator in ohm", default=1e3)
    r_vcm_bot = h.Param(dtype=h.Scalar, desc="Bottom resistor for sampled output-error attenuator in ohm", default=1e6)
    r_out_p = h.Param(dtype=h.Scalar, desc="Series resistor from SC non-inverting node to core input in ohm", default=1.0)
    r_out_n = h.Param(dtype=h.Scalar, desc="Series resistor from SC inverting node to core input in ohm", default=1.0)
    c_out_p = h.Param(dtype=h.Scalar, desc="Optional shunt capacitor on core-facing non-inverting input in F", default=0.0)
    c_out_n = h.Param(dtype=h.Scalar, desc="Optional shunt capacitor on core-facing inverting input in F", default=0.0)
    c_corr_n_scale = h.Param(dtype=h.Scalar, desc="Fractional mirrored correction capacitor on the inverting path", default=0.0)


@h.paramclass
class FrontendAzPedestalZeroInputTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    period = h.Param(dtype=h.Scalar, desc="Clock period in s", default=20e-6)
    dead_time = h.Param(dtype=h.Scalar, desc="Clock dead time between PHI1 and PHI2 in s", default=2e-6)
    phi1_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to sample_zero", default=0.4)
    phi2_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to correction_apply", default=0.2)
    phi3_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to settle", default=0.4)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=120e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=100e-9)


@h.paramclass
class FrontendAzSettlingInPhaseWindowTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Observation capacitance in F", default=100e-15)
    period = h.Param(dtype=h.Scalar, desc="Clock period in s", default=20e-6)
    dead_time = h.Param(dtype=h.Scalar, desc="Clock dead time between PHI1 and PHI2 in s", default=2e-6)
    phi1_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to sample_zero", default=0.4)
    phi2_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to correction_apply", default=0.2)
    phi3_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to settle", default=0.4)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=120e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=100e-9)


@h.generator
def frontend_az(params: FrontendAzParams) -> h.Module:
    c_az = float(params.c_az)
    w_sw_n = float(params.w_sw_n)
    w_sw_p = float(params.w_sw_p)
    l_sw = float(params.l_sw)
    r_vcm_top = float(params.r_vcm_top)
    r_vcm_bot = float(params.r_vcm_bot)
    r_out_p = float(params.r_out_p)
    r_out_n = float(params.r_out_n)
    c_out_p = float(params.c_out_p)
    c_out_n = float(params.c_out_n)
    c_corr_n_scale = float(params.c_corr_n_scale)

    if c_az <= 0:
        raise ValueError("c_az must be positive")
    if w_sw_n <= 0 or w_sw_p <= 0 or l_sw <= 0:
        raise ValueError("w_sw_n, w_sw_p, and l_sw must be positive")
    if params.nf_sw < 1 or params.m_sw < 1:
        raise ValueError("nf_sw and m_sw must be >= 1")
    if r_vcm_top <= 0 or r_vcm_bot <= 0:
        raise ValueError("r_vcm_top and r_vcm_bot must be positive")
    if r_out_p <= 0 or r_out_n <= 0:
        raise ValueError("r_out_p and r_out_n must be positive")
    if c_out_p < 0 or c_out_n < 0:
        raise ValueError("c_out_p and c_out_n must be >= 0")
    if c_corr_n_scale < 0:
        raise ValueError("c_corr_n_scale must be >= 0")

    tg_params = TgSwitchParams(
        w_n=params.w_sw_n,
        l_n=params.l_sw,
        nf_n=params.nf_sw,
        m_n=params.m_sw,
        w_p=params.w_sw_p,
        l_p=params.l_sw,
        nf_p=params.nf_sw,
        m_p=params.m_sw,
        use_dummy_switch=params.use_dummy_switch,
    )
    tg = tg_switch(tg_params)

    mod = h.Module(name="FrontendAzV3")
    mod.VINP, mod.VINN, mod.VOFF, mod.VXP, mod.VXN, mod.PHI1, mod.PHI1B, mod.PHI2, mod.PHI2B, mod.PHI3, mod.PHI3B, mod.VDD, mod.VSS = h.Ports(13)
    mod.samp_p, mod.samp_n, mod.voff_sense, mod.vxp_sc, mod.vxn_sc = h.Signals(5)

    mod.rvoff_top = pdk_resistor(params.r_vcm_top, p=mod.VOFF, n=mod.voff_sense, bulk=mod.VSS)
    mod.rvoff_bot = pdk_resistor(params.r_vcm_bot, p=mod.voff_sense, n=mod.VSS, bulk=mod.VSS)

    mod.xsw_err_sample = tg(A=mod.voff_sense, B=mod.samp_p, PHI=mod.PHI1, PHIB=mod.PHI1B, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_vxp_reset = tg(A=mod.VSS, B=mod.vxp_sc, PHI=mod.PHI1, PHIB=mod.PHI1B, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_vxp_apply = tg(A=mod.VINP, B=mod.samp_p, PHI=mod.PHI3, PHIB=mod.PHI3B, VDD=mod.VDD, VSS=mod.VSS)
    mod.xcap_p = pdk_mim_capacitor(params.c_az, p=mod.samp_p, n=mod.vxp_sc)
    mod.rout_p = pdk_resistor(params.r_out_p, p=mod.vxp_sc, n=mod.VXP, bulk=mod.VSS)
    if c_out_p > 0:
        mod.cout_p = pdk_mim_capacitor(params.c_out_p, p=mod.VXP, n=mod.VSS)

    mod.xsw_vxn_reset = tg(A=mod.VSS, B=mod.vxn_sc, PHI=mod.PHI1, PHIB=mod.PHI1B, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_vxn_track = tg(A=mod.VINN, B=mod.vxn_sc, PHI=mod.PHI3, PHIB=mod.PHI3B, VDD=mod.VDD, VSS=mod.VSS)
    mod.xcap_n = pdk_mim_capacitor(max(0.5 * params.c_az, 1e-15), p=mod.vxn_sc, n=mod.VSS)
    if c_corr_n_scale > 0:
        mod.xsw_err_sample_n = tg(A=mod.voff_sense, B=mod.samp_n, PHI=mod.PHI1, PHIB=mod.PHI1B, VDD=mod.VDD, VSS=mod.VSS)
        mod.xsw_vxn_apply_corr = tg(A=mod.VINN, B=mod.samp_n, PHI=mod.PHI3, PHIB=mod.PHI3B, VDD=mod.VDD, VSS=mod.VSS)
        mod.xcap_corr_n = pdk_mim_capacitor(max(c_corr_n_scale * params.c_az, 1e-15), p=mod.samp_n, n=mod.vxn_sc)
    mod.rout_n = pdk_resistor(params.r_out_n, p=mod.vxn_sc, n=mod.VXN, bulk=mod.VSS)
    if c_out_n > 0:
        mod.cout_n = pdk_mim_capacitor(params.c_out_n, p=mod.VXN, n=mod.VSS)

    mod.rbleed_p = pdk_resistor(500e6, p=mod.VXP, n=mod.VSS, bulk=mod.VSS)
    mod.rbleed_n = pdk_resistor(500e6, p=mod.VXN, n=mod.VSS, bulk=mod.VSS)
    return mod


def _default_ngspice_options(test_name: str) -> SimOptions:
    return SimOptions(simulator=SupportedSimulators.NGSPICE, rundir=f"./tmp/{test_name}")


def _corner_model_includes():
    install = require_sky130_install()
    base = install.pdk_path / "libs.tech/ngspice"
    return [
        h.sim.Include(base / "corners/tt.spice"),
        h.sim.Include(base / "r+c/res_typical__cap_typical.spice"),
        h.sim.Include(base / "r+c/res_typical__cap_typical__lin.spice"),
        h.sim.Include(base / "corners/tt/specialized_cells.spice"),
    ]


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
    return data[start : start + npts]


def _build_tran_tb(
    dut_params: FrontendAzParams,
    *,
    vdd: float,
    vinp_hi: float,
    voff_dc: float,
    c_load: float,
    period: float,
    dead_time: float,
    tstop: float,
    tstep: float,
    phi1_share: float,
    phi2_share: float,
    phi3_share: float,
    corner,
) -> Sim:
    if corner != h.pdk.Corner.TYP:
        raise ValueError(f"frontend_az transient tests currently support only TT, got {corner}")
    dut = frontend_az(dut_params)
    dead_time = max(dead_time, 0.0)
    active_time = period - 3.0 * dead_time
    share_sum = phi1_share + phi2_share + phi3_share
    if active_time <= 0:
        raise ValueError("period must be greater than 3 * dead_time for three-phase AZ timing")
    if min(phi1_share, phi2_share, phi3_share) <= 0 or share_sum <= 0:
        raise ValueError("phase shares must be positive for three-phase AZ timing")
    phi1_width = active_time * phi1_share / share_sum
    phi2_width = active_time * phi2_share / share_sum
    phi3_width = active_time * phi3_share / share_sum
    phi2_delay = phi1_width + dead_time
    phi3_delay = phi1_width + dead_time + phi2_width + dead_time

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, voff, vxp, vxn, phi1, phi1b, phi2, phi2b, phi3, phi3b, vdd_sig = h.Signals(12)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        vvinp = h.Vpulse(v1=0.0, v2=vinp_hi, delay=period, rise=50e-9, fall=50e-9, width=tstop, period=2 * tstop)(p=vinp, n=VSS)
        vvinn = h.Vdc(dc=0.0)(p=vinn, n=VSS)
        vvoff = h.Vdc(dc=voff_dc)(p=voff, n=VSS)
        vphi1 = h.Vpulse(v1=0.0, v2=vdd, delay=0.0, rise=20e-9, fall=20e-9, width=phi1_width, period=period)(p=phi1, n=VSS)
        vphi1b = h.Vpulse(v1=vdd, v2=0.0, delay=0.0, rise=20e-9, fall=20e-9, width=phi1_width, period=period)(p=phi1b, n=VSS)
        vphi2 = h.Vpulse(v1=0.0, v2=vdd, delay=phi2_delay, rise=20e-9, fall=20e-9, width=phi2_width, period=period)(p=phi2, n=VSS)
        vphi2b = h.Vpulse(v1=vdd, v2=0.0, delay=phi2_delay, rise=20e-9, fall=20e-9, width=phi2_width, period=period)(p=phi2b, n=VSS)
        vphi3 = h.Vpulse(v1=0.0, v2=vdd, delay=phi3_delay, rise=20e-9, fall=20e-9, width=phi3_width, period=period)(p=phi3, n=VSS)
        vphi3b = h.Vpulse(v1=vdd, v2=0.0, delay=phi3_delay, rise=20e-9, fall=20e-9, width=phi3_width, period=period)(p=phi3b, n=VSS)
        cobs_p = h.Cap(c=c_load)(p=vxp, n=VSS)
        cobs_n = h.Cap(c=c_load)(p=vxn, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOFF=voff, VXP=vxp, VXN=vxn, PHI1=phi1, PHI1B=phi1b, PHI2=phi2, PHI2B=phi2b, PHI3=phi3, PHI3B=phi3b, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            *(_corner_model_includes()),
            Tran(tstop=tstop, tstep=tstep),
            Save("time, v(xtop.vxp), v(xtop.vxn), v(xtop.phi3)"),
        ],
    )


def _pedestal_from_result(result) -> float:
    vxp = np.asarray(_tran_waveform(result, "v(xtop.vxp)"), dtype=float)
    return float(vxp[-1] * 1e6)


def _phase_window_metrics(result) -> tuple[float, float]:
    time = np.asarray(_tran_waveform(result, "time"), dtype=float)
    vxp = np.asarray(_tran_waveform(result, "v(xtop.vxp)"), dtype=float)
    phi3 = np.asarray(_tran_waveform(result, "v(xtop.phi3)"), dtype=float)
    active = np.where(phi3 > 0.5 * np.max(phi3))[0]
    if active.size < 2:
        raise RuntimeError("Unable to identify amplify window from PHI3 waveform")
    first = int(active[0])
    last = int(active[-1])
    phase_window_util = float(time[last] - time[first])
    settle = float((vxp[last] - vxp[first]) * 1e6)
    return settle, phase_window_util


def run_pedestal_zero_input_test(
    dut_params: FrontendAzParams | None = None,
    tb_params: FrontendAzPedestalZeroInputTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or FrontendAzParams()
    tb_params = tb_params or FrontendAzPedestalZeroInputTbParams()
    sim = _build_tran_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        vinp_hi=0.0,
        voff_dc=1e-3,
        c_load=100e-15,
        period=float(tb_params.period),
        dead_time=float(tb_params.dead_time),
        tstop=float(tb_params.tstop),
        tstep=float(tb_params.tstep),
        phi1_share=float(tb_params.phi1_share),
        phi2_share=float(tb_params.phi2_share),
        phi3_share=float(tb_params.phi3_share),
        corner=corner,
    )
    result = run_ngspice_sim(sim, options=_default_ngspice_options("frontend_az_pedestal_zero_input"))
    metrics = {"pedestal_uV": _pedestal_from_result(result)}
    return make_test_result("frontend_az", "pedestal_zero_input", "tran", [str(corner)], [f"vdd={float(tb_params.vdd):.3f}"], metrics)


def run_settling_in_phase_window_test(
    dut_params: FrontendAzParams | None = None,
    tb_params: FrontendAzSettlingInPhaseWindowTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    dut_params = dut_params or FrontendAzParams()
    tb_params = tb_params or FrontendAzSettlingInPhaseWindowTbParams()
    sim = _build_tran_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        vinp_hi=0.1,
        voff_dc=50e-3,
        c_load=float(tb_params.c_load),
        period=float(tb_params.period),
        dead_time=float(tb_params.dead_time),
        tstop=float(tb_params.tstop),
        tstep=float(tb_params.tstep),
        phi1_share=float(tb_params.phi1_share),
        phi2_share=float(tb_params.phi2_share),
        phi3_share=float(tb_params.phi3_share),
        corner=corner,
    )
    result = run_ngspice_sim(sim, options=_default_ngspice_options("frontend_az_settling_in_phase_window"))
    settling_residue_uV, phase_window_utilization = _phase_window_metrics(result)
    metrics = {
        "settling_residue_uV": settling_residue_uV,
        "phase_window_utilization": phase_window_utilization,
    }
    return make_test_result("frontend_az", "settling_in_phase_window", "tran", [str(corner)], [f"vdd={float(tb_params.vdd):.3f}"], metrics)


def run_structural_checks(params: FrontendAzParams | None = None):
    params = params or FrontendAzParams()
    dut = frontend_az(params)
    mod = h.elaborate(dut)
    stream = StringIO()
    h.netlist(mod, stream, fmt="spice")
    netlist_text = stream.getvalue()
    subckt_name = extract_subckt_name(netlist_text)
    has_pdk_nmos = re.search(r"sky130_fd_pr__nfet_01v8", netlist_text, re.IGNORECASE) is not None
    has_pdk_pmos = re.search(r"sky130_fd_pr__pfet_01v8", netlist_text, re.IGNORECASE) is not None
    has_generic_mos_models = re.search(r"(?<!_)\\b(nmos|pmos)\\b", netlist_text, re.IGNORECASE) is not None
    return {
        "generator_call": dut is not None,
        "elaboration": mod is not None,
        "subckt_name": subckt_name,
        "contains_tg_switch": re.search(r"TgSwitch", netlist_text, re.IGNORECASE) is not None,
        "contains_pdk_resistor": re.search(r"sky130_fd_pr__res_", netlist_text, re.IGNORECASE) is not None,
        "contains_pdk_mim_cap": re.search(r"sky130_fd_pr__cap_mim_", netlist_text, re.IGNORECASE) is not None,
        "contains_pdk_nmos": has_pdk_nmos,
        "contains_pdk_pmos": has_pdk_pmos,
        "contains_no_generic_mos_models": not has_generic_mos_models,
    }


def write_verification_report_md(path: str | Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    structural = run_structural_checks()
    pedestal = run_pedestal_zero_input_test()
    settling = run_settling_in_phase_window_test()

    lines = [
        "# frontend_az Verification Report",
        "",
        f"- Spec: `{FrontendAzSpec()}`",
        "",
        "## Structural Checks",
    ]
    lines.extend(print_metrics_table(structural).splitlines())
    lines.append("")
    lines.append("## Pedestal Zero Input")
    lines.extend(print_metrics_table(pedestal["metrics"]).splitlines())
    lines.append("")
    lines.append("## Settling In Phase Window")
    lines.extend(print_metrics_table(settling["metrics"]).splitlines())
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
