from pathlib import Path
import re
from dataclasses import dataclass

import hdl21 as h
from hdl21.sim import Save, Sim, Tran
from vlsirtools.spice import SimOptions, SupportedSimulators

from components import extract_subckt_name, make_test_result, print_metrics_table, require_sky130_install, run_ngspice_sim
from components.sample_hold_cap import SampleHoldCapParams, sample_hold_cap
from components.tg_switch import TgSwitchParams, tg_switch


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator_call", "elaboration", "subckt_name", "contains_tg_switch", "contains_sample_hold_cap"],
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
    name: str = "frontend_az"
    purpose: str = "Sample, hold, and forward input signals for auto-zero operation."
    component_class: str = "reusable block"
    pins: tuple[str, ...] = ("VINP", "VINN", "VXP", "VXN", "PHI1", "PHI2", "VDD", "VSS")
    measurable_behaviors: tuple[str, ...] = ("pedestal_zero_input", "settling_in_phase_window")
    numeric_pass_fail_criteria: tuple[str, ...] = ("generic transient contract only; product budgets belong in external budget tests",)
    required_corners: tuple[str, ...] = ("TT",)
    statistical_verification_required: bool = False


@h.paramclass
class FrontendAzParams:
    c_az = h.Param(dtype=h.Scalar, desc="Per-side AZ capacitor in F", default=200e-15)
    w_sw_n = h.Param(dtype=h.Scalar, desc="NMOS switch width in um", default=0.65)
    w_sw_p = h.Param(dtype=h.Scalar, desc="PMOS switch width in um", default=1.0)
    l_sw = h.Param(dtype=h.Scalar, desc="Switch length in um", default=0.15)
    nf_sw = h.Param(dtype=int, desc="Switch fingers", default=1)
    m_sw = h.Param(dtype=int, desc="Switch multiplier", default=1)
    use_dummy_switch = h.Param(dtype=bool, desc="Add dummy TG devices", default=False)
    r_vcm_top = h.Param(dtype=h.Scalar, desc="Top resistor for internal common-mode generator in ohm", default=3e6)
    r_vcm_bot = h.Param(dtype=h.Scalar, desc="Bottom resistor for internal common-mode generator in ohm", default=1e6)


@h.paramclass
class FrontendAzPedestalZeroInputTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    period = h.Param(dtype=h.Scalar, desc="Clock period in s", default=2e-6)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=8e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=20e-9)


@h.paramclass
class FrontendAzSettlingInPhaseWindowTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Observation capacitance in F", default=100e-15)
    period = h.Param(dtype=h.Scalar, desc="Clock period in s", default=2e-6)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=8e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=20e-9)


@h.generator
def frontend_az(params: FrontendAzParams) -> h.Module:
    if params.c_az <= 0:
        raise ValueError("c_az must be positive")
    if params.w_sw_n <= 0 or params.w_sw_p <= 0 or params.l_sw <= 0:
        raise ValueError("w_sw_n, w_sw_p, and l_sw must be positive")
    if params.nf_sw < 1 or params.m_sw < 1:
        raise ValueError("nf_sw and m_sw must be >= 1")
    if params.r_vcm_top <= 0 or params.r_vcm_bot <= 0:
        raise ValueError("r_vcm_top and r_vcm_bot must be positive")

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
    cap_params = SampleHoldCapParams(c_target=params.c_az)

    tg = tg_switch(tg_params)
    cap = sample_hold_cap(cap_params)

    mod = h.Module(name="FrontendAz")
    mod.VINP, mod.VINN, mod.VXP, mod.VXN, mod.PHI1, mod.PHI2, mod.VDD, mod.VSS = h.Ports(8)
    mod.samp_p, mod.samp_n, mod.vcm = h.Signals(3)

    # Generate a quiet internal common-mode anchor used during the sample_zero phase.
    mod.rvcm_top = h.Res(r=params.r_vcm_top)(p=mod.VDD, n=mod.vcm)
    mod.rvcm_bot = h.Res(r=params.r_vcm_bot)(p=mod.vcm, n=mod.VSS)

    # Phase 1: sample inputs onto the left plates of the AZ capacitors.
    mod.xsw_samp_p = tg(A=mod.VINP, B=mod.samp_p, PHI=mod.PHI1, PHIB=mod.PHI2, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_samp_n = tg(A=mod.VINN, B=mod.samp_n, PHI=mod.PHI1, PHIB=mod.PHI2, VDD=mod.VDD, VSS=mod.VSS)

    # Phase 1: force the core-facing nodes to a known common mode.
    mod.xsw_reset_p = tg(A=mod.vcm, B=mod.VXP, PHI=mod.PHI1, PHIB=mod.PHI2, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_reset_n = tg(A=mod.vcm, B=mod.VXN, PHI=mod.PHI1, PHIB=mod.PHI2, VDD=mod.VDD, VSS=mod.VSS)

    # Phase 2: translate the sampled charge onto the core-facing nodes by
    # reconnecting the left plates to the common-mode anchor.
    mod.xsw_rebias_p = tg(A=mod.samp_p, B=mod.vcm, PHI=mod.PHI2, PHIB=mod.PHI1, VDD=mod.VDD, VSS=mod.VSS)
    mod.xsw_rebias_n = tg(A=mod.samp_n, B=mod.vcm, PHI=mod.PHI2, PHIB=mod.PHI1, VDD=mod.VDD, VSS=mod.VSS)

    # AZ storage capacitors are now between the sampled plates and the core inputs,
    # so the stored charge can shift the core input pair during the amplify phase.
    mod.xcap_p = cap(P=mod.samp_p, N=mod.VXP)
    mod.xcap_n = cap(P=mod.samp_n, N=mod.VXN)

    # Weak bleeders prevent the floating core-input nodes from drifting indefinitely
    # while keeping the sampled charge dominant over a single AZ phase.
    mod.rbleed_p = h.Res(r=50e6)(p=mod.VXP, n=mod.vcm)
    mod.rbleed_n = h.Res(r=50e6)(p=mod.VXN, n=mod.vcm)
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
    c_load: float,
    period: float,
    tstop: float,
    tstep: float,
    corner,
) -> Sim:
    if corner != h.pdk.Corner.TYP:
        raise ValueError(f"frontend_az transient tests currently support only TT, got {corner}")
    dut = frontend_az(dut_params)
    nonoverlap = 0.1 * period
    phi_width = 0.5 * period - nonoverlap

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vxp, vxn, phi1, phi2, vdd_sig = h.Signals(7)
        vvdd = h.Vdc(dc=vdd)(p=vdd_sig, n=VSS)
        vvinp = h.Vpulse(
            v1=0.0,
            v2=vinp_hi,
            delay=period,
            rise=50e-9,
            fall=50e-9,
            width=tstop,
            period=2 * tstop,
        )(p=vinp, n=VSS)
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
        cload_p = h.Cap(c=c_load)(p=vxp, n=VSS)
        cload_n = h.Cap(c=c_load)(p=vxn, n=VSS)
        rbleed_p = h.Res(r=1e6)(p=vxp, n=VSS)
        rbleed_n = h.Res(r=1e6)(p=vxn, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VXP=vxp, VXN=vxn, PHI1=phi1, PHI2=phi2, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=tstop, tstep=tstep),
            Save("v(xtop.vxp), v(xtop.vxn), v(xtop.vinp), v(xtop.phi1), v(xtop.phi2)"),
            h.sim.Param(name="mc_mm_switch", val=0),
            h.sim.Param(name="mc_pr_switch", val=0),
            *_corner_model_includes(),
        ],
    )


def build_pedestal_zero_input_test(
    dut_params: FrontendAzParams,
    tb_params: FrontendAzPedestalZeroInputTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or FrontendAzPedestalZeroInputTbParams()
    return _build_tran_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        vinp_hi=0.0,
        c_load=float(dut_params.c_az),
        period=float(tb_params.period),
        tstop=float(tb_params.tstop),
        tstep=float(tb_params.tstep),
        corner=corner,
    )


def run_pedestal_zero_input_test(
    dut_params: FrontendAzParams | None = None,
    tb_params: FrontendAzPedestalZeroInputTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or FrontendAzParams()
    tb_params = tb_params or FrontendAzPedestalZeroInputTbParams()
    sim = build_pedestal_zero_input_test(dut_params, tb_params, corner=corner)
    sim_options = sim_options or _default_ngspice_options("frontend_az_pedestal_zero_input")
    result = run_ngspice_sim(sim, sim_options)
    vxp = _tran_waveform(result, "v(xtop.vxp)")
    vxn = _tran_waveform(result, "v(xtop.vxn)")
    pedestal_uv = 1e6 * max(abs(float(vxp[-1])), abs(float(vxn[-1])))
    metrics = {
        "pedestal_uV": pedestal_uv,
        "vxp_final": float(vxp[-1]),
        "vxn_final": float(vxn[-1]),
        "c_az_fF": float(dut_params.c_az) / 1e-15,
    }
    return make_test_result(
        component="frontend_az",
        category="contract",
        purpose="pedestal_zero_input",
        metrics=metrics,
        passed=bool(pedestal_uv < 1e3),
        margin={"pedestal_uV": 1e3 - pedestal_uv},
    )


def build_settling_in_phase_window_test(
    dut_params: FrontendAzParams,
    tb_params: FrontendAzSettlingInPhaseWindowTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    tb_params = tb_params or FrontendAzSettlingInPhaseWindowTbParams()
    return _build_tran_tb(
        dut_params,
        vdd=float(tb_params.vdd),
        vinp_hi=0.1,
        c_load=float(tb_params.c_load),
        period=float(tb_params.period),
        tstop=float(tb_params.tstop),
        tstep=float(tb_params.tstep),
        corner=corner,
    )


def run_settling_in_phase_window_test(
    dut_params: FrontendAzParams | None = None,
    tb_params: FrontendAzSettlingInPhaseWindowTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or FrontendAzParams()
    tb_params = tb_params or FrontendAzSettlingInPhaseWindowTbParams()
    sim = build_settling_in_phase_window_test(dut_params, tb_params, corner=corner)
    sim_options = sim_options or _default_ngspice_options("frontend_az_settling_in_phase_window")
    result = run_ngspice_sim(sim, sim_options)
    time = _tran_waveform(result, "time")
    vxp = _tran_waveform(result, "v(xtop.vxp)")
    phi2 = _tran_waveform(result, "v(xtop.phi2)")
    active_idx = [idx for idx, value in enumerate(phi2) if float(value) > 0.5 * float(tb_params.vdd)]
    if not active_idx:
        raise RuntimeError("No amplify-phase window detected in frontend_az settling test")
    run_start = active_idx[-1]
    while run_start > 0 and float(phi2[run_start - 1]) > 0.5 * float(tb_params.vdd):
        run_start -= 1
    run_stop = active_idx[-1]
    target = 0.1 * float(dut_params.c_az) / (float(dut_params.c_az) + float(tb_params.c_load))
    residue = abs(float(vxp[run_stop]) - target)
    residue_uv = 1e6 * residue
    settle_tol = max(100e-6, 0.01 * abs(target))
    settle_idx = next(
        (idx for idx in range(run_start, run_stop + 1) if abs(float(vxp[idx]) - target) <= settle_tol),
        None,
    )
    if settle_idx is None:
        phase_window_utilization = float("inf")
    else:
        window = max(float(time[run_stop]) - float(time[run_start]), 1e-18)
        phase_window_utilization = (float(time[settle_idx]) - float(time[run_start])) / window
    metrics = {
        "settling_residue_uV": residue_uv,
        "phase_window_utilization": phase_window_utilization,
        "target_vxp": target,
        "vxp_final": float(vxp[run_stop]),
        "c_load_fF": float(tb_params.c_load) / 1e-15,
    }
    return make_test_result(
        component="frontend_az",
        category="contract",
        purpose="settling_in_phase_window",
        metrics=metrics,
        passed=bool(residue_uv < 1e5 and phase_window_utilization <= 1.0),
        margin={"settling_residue_uV": 1e5 - residue_uv},
    )


def run_all_tests(
    dut_params: FrontendAzParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or FrontendAzParams()
    return {
        "structural": make_test_result(
            component="frontend_az",
            category="smoke",
            purpose="basic",
            metrics=run_structural_checks(dut_params),
            passed=True,
        ),
        "pedestal_zero_input": run_pedestal_zero_input_test(dut_params, sim_options=sim_options),
        "settling_in_phase_window": run_settling_in_phase_window_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: FrontendAzParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="frontend_az")
    return results


def elaborate_dut(params: FrontendAzParams | None = None) -> h.Module:
    params = params or FrontendAzParams()
    return h.elaborate(frontend_az(params))


def export_spice(path: str | Path, params: FrontendAzParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: FrontendAzParams | None = None):
    params = params or FrontendAzParams()
    dut = frontend_az(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/frontend_az_structural/frontend_az.sp")
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
        "contains_tg_switch": "TgSwitch" in text,
        "contains_sample_hold_cap": "SampleHoldCap" in text,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
