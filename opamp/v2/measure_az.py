from pathlib import Path
import re

import hdl21 as h
import numpy as np
from hdl21.sim import Save, Sim, Tran
from vlsirtools.spice import SimOptions

from .common import (
    default_ngspice_options,
    extract_subckt_name,
    make_test_result,
    print_metrics_table,
    require_sky130_install,
    run_ngspice_sim,
    tran_waveform,
)
from .frontend_az import (
    FrontendAzParams,
    FrontendAzPedestalZeroInputTbParams,
    FrontendAzSettlingInPhaseWindowTbParams,
    frontend_az,
)

def _corner_model_includes():
    install = require_sky130_install()
    base = install.pdk_path / "libs.tech/ngspice"
    return [
        h.sim.Include(base / "corners/tt.spice"),
        h.sim.Include(base / "r+c/res_typical__cap_typical.spice"),
        h.sim.Include(base / "r+c/res_typical__cap_typical__lin.spice"),
        h.sim.Include(base / "corners/tt/specialized_cells.spice"),
    ]

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
        cload_p = h.Cap(c=c_load)(p=vxp, n=VSS)
        cload_n = h.Cap(c=c_load)(p=vxn, n=VSS)
        rbleed_p = h.Res(r=50e6)(p=vxp, n=VSS)
        rbleed_n = h.Res(r=50e6)(p=vxn, n=VSS)
        xdut = dut(
            VINP=vinp,
            VINN=vinn,
            VOFF=voff,
            VXP=vxp,
            VXN=vxn,
            PHI1=phi1,
            PHI1B=phi1b,
            PHI2=phi2,
            PHI2B=phi2b,
            PHI3=phi3,
            PHI3B=phi3b,
            VDD=vdd_sig,
            VSS=VSS,
        )

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=tstop, tstep=tstep),
            Save("time, v(xtop.vxp), v(xtop.vxn), v(xtop.vinp), v(xtop.voff), v(xtop.phi1), v(xtop.phi2), v(xtop.phi3)"),
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
        voff_dc=0.0,
        c_load=float(dut_params.c_az),
        period=float(tb_params.period),
        dead_time=float(tb_params.dead_time),
        tstop=float(tb_params.tstop),
        tstep=float(tb_params.tstep),
        phi1_share=float(tb_params.phi1_share),
        phi2_share=float(tb_params.phi2_share),
        phi3_share=float(tb_params.phi3_share),
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
    sim_options = sim_options or default_ngspice_options("frontend_az_pedestal_zero_input")
    result = run_ngspice_sim(sim, sim_options)
    phi3 = tran_waveform(result, "v(xtop.phi3)")
    vxp = tran_waveform(result, "v(xtop.vxp)")
    vxn = tran_waveform(result, "v(xtop.vxn)")
    active_idx = [idx for idx, value in enumerate(phi3) if float(value) > 0.5 * float(tb_params.vdd)]
    if not active_idx:
        raise RuntimeError("No settle-phase window detected in frontend_az pedestal test")
    run_stop = active_idx[-1]
    vdiff_final = float(vxp[run_stop]) - float(vxn[run_stop])
    pedestal_uv = 1e6 * abs(vdiff_final)
    metrics = {
        "pedestal_uV": pedestal_uv,
        "vxp_final": float(vxp[run_stop]),
        "vxn_final": float(vxn[run_stop]),
        "vdiff_final": vdiff_final,
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
        voff_dc=0.0,
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
    sim_options = sim_options or default_ngspice_options("frontend_az_settling_in_phase_window")
    result = run_ngspice_sim(sim, sim_options)
    time = tran_waveform(result, "time")
    vxp = tran_waveform(result, "v(xtop.vxp)")
    vxn = tran_waveform(result, "v(xtop.vxn)")
    phi3 = tran_waveform(result, "v(xtop.phi3)")
    active_idx = [idx for idx, value in enumerate(phi3) if float(value) > 0.5 * float(tb_params.vdd)]
    if not active_idx:
        raise RuntimeError("No settle-phase window detected in frontend_az settling test")
    run_start = active_idx[-1]
    while run_start > 0 and float(phi3[run_start - 1]) > 0.5 * float(tb_params.vdd):
        run_start -= 1
    run_stop = active_idx[-1]
    vdiff = np.asarray(vxp, dtype=float) - np.asarray(vxn, dtype=float)
    tail_start = run_start + max((run_stop - run_start) * 3 // 4, 1)
    tail = vdiff[tail_start : run_stop + 1]
    final_mean = float(np.mean(tail))
    residue = float(np.max(tail) - np.min(tail))
    residue_uv = 1e6 * abs(residue)

    npts = run_stop - run_start + 1
    mid50_start = run_start + int(npts * 0.25)
    mid50_stop = run_start + int(npts * 0.75)
    mid50 = vdiff[mid50_start : mid50_stop + 1]
    residue_mid50_uv = 1e6 * abs(float(np.max(mid50) - np.min(mid50)))
    mid50_tail_start = max(len(mid50) * 3 // 4, 1)
    residue_mid50_tail_uv = 1e6 * abs(float(np.max(mid50[mid50_tail_start:]) - np.min(mid50[mid50_tail_start:])))

    mid40_start = run_start + int(npts * 0.30)
    mid40_stop = run_start + int(npts * 0.70)
    mid40 = vdiff[mid40_start : mid40_stop + 1]
    residue_mid40_uv = 1e6 * abs(float(np.max(mid40) - np.min(mid40)))
    mid40_tail_start = max(len(mid40) * 3 // 4, 1)
    residue_mid40_tail_uv = 1e6 * abs(float(np.max(mid40[mid40_tail_start:]) - np.min(mid40[mid40_tail_start:])))
    settle_tol = max(30e-6, 0.01 * max(abs(final_mean), 1e-6))
    settle_idx = next((idx for idx in range(run_start, run_stop + 1) if abs(float(vdiff[idx]) - final_mean) <= settle_tol), None)
    if settle_idx is None:
        phase_window_utilization = float("inf")
    else:
        window = max(float(time[run_stop]) - float(time[run_start]), 1e-18)
        phase_window_utilization = (float(time[settle_idx]) - float(time[run_start])) / window
    metrics = {
        "settling_residue_uV": residue_uv,
        "settling_mid50_uV": residue_mid50_uv,
        "settling_mid40_uV": residue_mid40_uv,
        "settling_mid50_tail_uV": residue_mid50_tail_uv,
        "settling_mid40_tail_uV": residue_mid40_tail_uv,
        "phase_window_utilization": phase_window_utilization,
        "target_vdiff": final_mean,
        "vdiff_final": float(vdiff[run_stop]),
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
        "structural": make_test_result(component="frontend_az", category="smoke", purpose="basic", metrics=run_structural_checks(dut_params), passed=True),
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
