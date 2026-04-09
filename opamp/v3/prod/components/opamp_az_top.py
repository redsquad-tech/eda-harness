from dataclasses import dataclass
from uuid import uuid4

import hdl21 as h
import numpy as np
from hdl21.sim import Save, SaveMode, Sim, Tran
from vlsirtools.spice import SimOptions

from components import make_test_result, require_sky130_install, run_ngspice_sim
from opamp.v3.frontend_az import FrontendAzParams, frontend_az
from opamp.v3.measure_core import OpampCoreFollowerTbParams, OpampCoreOpenLoopTbParams
from opamp.v3.opamp_core import OpampCoreParams, opamp_core
from opamp.v3.specs import OpampAzV3MaximumSpec, OpampAzV3TargetSpec
from ..rc import current_core_params, current_frontend_params, current_noise_offset_timing


@dataclass(frozen=True)
class OpampAzTopProdSpec:
    name: str = "opamp_az_top_v3_prod"
    purpose: str = "Production DUT: native v3 AZ frontend plus v3 core."
    component_class: str = "product candidate"
    pins: tuple[str, ...] = ("VINP", "VINN", "VOUT", "EN", "PHI1", "PHI1B", "PHI2", "PHI2B", "PHI3", "PHI3B", "VDD", "VSS")


@h.paramclass
class OpampAzTopProdParams:
    frontend_az_params = h.Param(
        dtype=FrontendAzParams,
        desc="Production AZ frontend parameters",
        default=current_frontend_params(),
    )
    opamp_core_params = h.Param(dtype=OpampCoreParams, desc="v3 core parameters", default=current_core_params())


@h.paramclass
class OpampAzTopProdNoiseAndOffsetTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    period = h.Param(dtype=h.Scalar, desc="AZ clock period in s", default=current_noise_offset_timing()["period"])
    dead_time = h.Param(dtype=h.Scalar, desc="Clock dead time between PHI1 and PHI2 in s", default=current_noise_offset_timing()["dead_time"])
    phi1_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to sample_zero", default=current_noise_offset_timing()["phi1_share"])
    phi2_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to correction_apply", default=current_noise_offset_timing()["phi2_share"])
    phi3_share = h.Param(dtype=h.Scalar, desc="Fraction of active time allocated to settle", default=current_noise_offset_timing()["phi3_share"])
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=current_noise_offset_timing()["tstop"])
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=current_noise_offset_timing()["tstep"])
    temp_c = h.Param(dtype=h.Scalar, desc="Simulation temperature in C", default=27.0)


@h.paramclass
class OpampAzTopProdClosedLoopStepTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Supply voltage in V", default=1.8)
    c_load = h.Param(dtype=h.Scalar, desc="Load capacitance in F", default=1e-12)
    v_step = h.Param(dtype=h.Scalar, desc="Step amplitude in V", default=10e-3)
    tstop = h.Param(dtype=h.Scalar, desc="Transient stop time in s", default=10e-6)
    tstep = h.Param(dtype=h.Scalar, desc="Transient step in s", default=100e-9)


@h.generator
def opamp_az_top(params: OpampAzTopProdParams) -> h.Module:
    frontend_inst = frontend_az(params.frontend_az_params)
    core_inst = opamp_core(params.opamp_core_params)

    mod = h.Module(name="OpampAzTopV3Prod")
    mod.VINP, mod.VINN, mod.VOUT, mod.EN, mod.PHI1, mod.PHI1B, mod.PHI2, mod.PHI2B, mod.PHI3, mod.PHI3B, mod.VDD, mod.VSS = h.Ports(12)
    mod.vxp, mod.vxn = h.Signals(2)
    mod.xfront = frontend_inst(
        VINP=mod.VINP,
        VINN=mod.VINN,
        VOFF=mod.VOUT,
        VXP=mod.vxp,
        VXN=mod.vxn,
        PHI1=mod.PHI1,
        PHI1B=mod.PHI1B,
        PHI2=mod.PHI2,
        PHI2B=mod.PHI2B,
        PHI3=mod.PHI3,
        PHI3B=mod.PHI3B,
        VDD=mod.VDD,
        VSS=mod.VSS,
    )
    mod.xcore = core_inst(VINP=mod.vxp, VINN=mod.vxn, VOUT=mod.VOUT, EN=mod.EN, VDD=mod.VDD, VSS=mod.VSS)
    return mod


def elaborate_dut(params: OpampAzTopProdParams | None = None) -> h.Module:
    return h.elaborate(opamp_az_top(params or OpampAzTopProdParams()))


def export_spice(path, params: OpampAzTopProdParams | None = None):
    from pathlib import Path

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as stream:
        h.netlist(mod, stream, fmt="spice")
    return path


def run_structural_checks(params: OpampAzTopProdParams | None = None):
    params = params or OpampAzTopProdParams()
    dut = opamp_az_top(params)
    mod = h.elaborate(dut)
    return {
        "generator_call": dut is not None,
        "elaboration": mod is not None,
        "subckt_name": mod.name.startswith("OpampAzTopV3Prod"),
        "contains_frontend": hasattr(mod, "xfront"),
        "contains_core": hasattr(mod, "xcore"),
    }


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


def _build_noise_and_offset_test(
    dut_params: OpampAzTopProdParams,
    tb_params: OpampAzTopProdNoiseAndOffsetTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    tb_params = tb_params or OpampAzTopProdNoiseAndOffsetTbParams()
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)
    period = float(tb_params.period)
    dead_time = max(float(tb_params.dead_time), 0.0)
    active_time = period - 3.0 * dead_time
    share_sum = float(tb_params.phi1_share) + float(tb_params.phi2_share) + float(tb_params.phi3_share)
    phi1_width = active_time * float(tb_params.phi1_share) / share_sum
    phi2_width = active_time * float(tb_params.phi2_share) / share_sum
    phi3_width = active_time * float(tb_params.phi3_share) / share_sum
    phi2_delay = phi1_width + dead_time
    phi3_delay = phi1_width + dead_time + phi2_width + dead_time

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, phi1, phi1b, phi2, phi2b, phi3, phi3b, vdd_sig = h.Signals(11)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=tb_params.vdd)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.0)(p=vinp, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn)
        vphi1 = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=0.0, rise=20e-9, fall=20e-9, width=phi1_width, period=period)(p=phi1, n=VSS)
        vphi1b = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=0.0, rise=20e-9, fall=20e-9, width=phi1_width, period=period)(p=phi1b, n=VSS)
        vphi2 = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=phi2_delay, rise=20e-9, fall=20e-9, width=phi2_width, period=period)(p=phi2, n=VSS)
        vphi2b = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=phi2_delay, rise=20e-9, fall=20e-9, width=phi2_width, period=period)(p=phi2b, n=VSS)
        vphi3 = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=phi3_delay, rise=20e-9, fall=20e-9, width=phi3_width, period=period)(p=phi3, n=VSS)
        vphi3b = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=phi3_delay, rise=20e-9, fall=20e-9, width=phi3_width, period=period)(p=phi3b, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, PHI1=phi1, PHI1B=phi1b, PHI2=phi2, PHI2B=phi2b, PHI3=phi3, PHI3B=phi3b, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=float(tb_params.tstop), tstep=float(tb_params.tstep)),
            Save("time, v(xtop.vout), v(xtop.phi3)"),
            h.sim.Literal(f".temp {float(tb_params.temp_c)}"),
            install.include(corner),
        ],
    )


def _build_noise_and_offset_mc_test(
    dut_params: OpampAzTopProdParams,
    tb_params: OpampAzTopProdNoiseAndOffsetTbParams | None = None,
    *,
    model_section: str = "tt_mm",
) -> Sim:
    tb_params = tb_params or OpampAzTopProdNoiseAndOffsetTbParams()
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)
    period = float(tb_params.period)
    dead_time = max(float(tb_params.dead_time), 0.0)
    active_time = period - 3.0 * dead_time
    share_sum = float(tb_params.phi1_share) + float(tb_params.phi2_share) + float(tb_params.phi3_share)
    phi1_width = active_time * float(tb_params.phi1_share) / share_sum
    phi2_width = active_time * float(tb_params.phi2_share) / share_sum
    phi3_width = active_time * float(tb_params.phi3_share) / share_sum
    phi2_delay = phi1_width + dead_time
    phi3_delay = phi1_width + dead_time + phi2_width + dead_time

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, phi1, phi1b, phi2, phi2b, phi3, phi3b, vdd_sig = h.Signals(11)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=tb_params.vdd)(p=en, n=VSS)
        vvinp = h.Vdc(dc=0.0)(p=vinp, n=VSS)
        rfb = h.Res(r=1.0)(p=vout, n=vinn)
        vphi1 = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=0.0, rise=20e-9, fall=20e-9, width=phi1_width, period=period)(p=phi1, n=VSS)
        vphi1b = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=0.0, rise=20e-9, fall=20e-9, width=phi1_width, period=period)(p=phi1b, n=VSS)
        vphi2 = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=phi2_delay, rise=20e-9, fall=20e-9, width=phi2_width, period=period)(p=phi2, n=VSS)
        vphi2b = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=phi2_delay, rise=20e-9, fall=20e-9, width=phi2_width, period=period)(p=phi2b, n=VSS)
        vphi3 = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=phi3_delay, rise=20e-9, fall=20e-9, width=phi3_width, period=period)(p=phi3, n=VSS)
        vphi3b = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=phi3_delay, rise=20e-9, fall=20e-9, width=phi3_width, period=period)(p=phi3b, n=VSS)
        cload = h.Cap(c=1e-12)(p=vout, n=VSS)
        rload = h.Res(r=1e6)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, PHI1=phi1, PHI1B=phi1b, PHI2=phi2, PHI2B=phi2b, PHI3=phi3, PHI3B=phi3b, VDD=vdd_sig, VSS=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Tran(tstop=float(tb_params.tstop), tstep=float(tb_params.tstep)),
            Save("time, v(xtop.vout), v(xtop.phi3)"),
            h.sim.Literal(f".temp {float(tb_params.temp_c)}"),
            h.sim.Lib(install.pdk_path / install.lib_path, model_section),
        ],
    )


def build_closed_loop_step_test(
    dut_params: OpampAzTopProdParams,
    tb_params: OpampAzTopProdClosedLoopStepTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    tb_params = tb_params or OpampAzTopProdClosedLoopStepTbParams()
    install = require_sky130_install()
    dut = opamp_az_top(dut_params)
    period = 2e-6
    dead_time = 0.1 * period
    active_time = period - 3.0 * dead_time
    phi1_width = 0.4 * active_time
    phi2_width = 0.2 * active_time
    phi3_width = 0.4 * active_time
    phi2_delay = phi1_width + dead_time
    phi3_delay = phi1_width + dead_time + phi2_width + dead_time

    @h.module
    class Tb:
        VSS = h.Port()
        vinp, vinn, vout, en, phi1, phi1b, phi2, phi2b, phi3, phi3b, vdd_sig = h.Signals(11)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd_sig, n=VSS)
        ven = h.Vdc(dc=tb_params.vdd)(p=en, n=VSS)
        vvinp = h.Vpulse(v1=0.0, v2=tb_params.v_step, delay=3 * period, rise=50e-9, fall=50e-9, width=float(tb_params.tstop), period=2 * float(tb_params.tstop))(p=vinp, n=VSS)
        vvinn = h.Vdc(dc=0.0)(p=vinn, n=VSS)
        vphi1 = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=0.0, rise=20e-9, fall=20e-9, width=phi1_width, period=period)(p=phi1, n=VSS)
        vphi1b = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=0.0, rise=20e-9, fall=20e-9, width=phi1_width, period=period)(p=phi1b, n=VSS)
        vphi2 = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=phi2_delay, rise=20e-9, fall=20e-9, width=phi2_width, period=period)(p=phi2, n=VSS)
        vphi2b = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=phi2_delay, rise=20e-9, fall=20e-9, width=phi2_width, period=period)(p=phi2b, n=VSS)
        vphi3 = h.Vpulse(v1=0.0, v2=tb_params.vdd, delay=phi3_delay, rise=20e-9, fall=20e-9, width=phi3_width, period=period)(p=phi3, n=VSS)
        vphi3b = h.Vpulse(v1=tb_params.vdd, v2=0.0, delay=phi3_delay, rise=20e-9, fall=20e-9, width=phi3_width, period=period)(p=phi3b, n=VSS)
        cload = h.Cap(c=tb_params.c_load)(p=vout, n=VSS)
        xdut = dut(VINP=vinp, VINN=vinn, VOUT=vout, EN=en, PHI1=phi1, PHI1B=phi1b, PHI2=phi2, PHI2B=phi2b, PHI3=phi3, PHI3B=phi3b, VDD=vdd_sig, VSS=VSS)

    return Sim(tb=Tb, attrs=[Tran(tstop=float(tb_params.tstop), tstep=float(tb_params.tstep)), Save(SaveMode.ALL), install.include(corner)])


def build_noise_and_offset_test(
    dut_params: OpampAzTopProdParams,
    tb_params: OpampAzTopProdNoiseAndOffsetTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
) -> Sim:
    return _build_noise_and_offset_test(dut_params, tb_params, corner=corner)


def build_noise_and_offset_mc_test(
    dut_params: OpampAzTopProdParams,
    tb_params: OpampAzTopProdNoiseAndOffsetTbParams | None = None,
    *,
    model_section: str = "tt_mm",
) -> Sim:
    return _build_noise_and_offset_mc_test(dut_params, tb_params, model_section=model_section)


def run_noise_and_offset_test(
    dut_params: OpampAzTopProdParams | None = None,
    tb_params: OpampAzTopProdNoiseAndOffsetTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or OpampAzTopProdParams()
    tb_params = tb_params or OpampAzTopProdNoiseAndOffsetTbParams()
    sim = build_noise_and_offset_test(dut_params, tb_params, corner=corner)
    if sim_options is None:
        sim_options = SimOptions(rundir=f"./tmp/opamp_v3_prod_noise_and_offset_{uuid4().hex[:8]}")
    result = run_ngspice_sim(sim, sim_options)
    vout = _tran_waveform(result, "v(xtop.vout)")
    phi3 = _tran_waveform(result, "v(xtop.phi3)")
    active_idx = np.flatnonzero(phi3 > 0.5 * float(tb_params.vdd))
    if len(active_idx) == 0:
        raise RuntimeError("No settle-phase window detected in v3 prod noise_and_offset test")
    run_start = int(active_idx[-1])
    while run_start > 0 and float(phi3[run_start - 1]) > 0.5 * float(tb_params.vdd):
        run_start -= 1
    run_stop = int(active_idx[-1])
    residual_offset_uv = 1e6 * abs(float(vout[run_stop]))

    def _window_p2p(start_frac: float, stop_frac: float) -> float:
        npts = run_stop - run_start + 1
        w_start = run_start + int(npts * start_frac)
        w_stop = run_start + int(npts * stop_frac)
        arr = vout[w_start : w_stop + 1]
        return 1e6 * abs(float(np.max(arr) - np.min(arr)))

    pedestal_mid50_uv = _window_p2p(0.25, 0.75)
    mid50_start = run_start + int((run_stop - run_start + 1) * 0.25)
    mid50_stop = run_start + int((run_stop - run_start + 1) * 0.75)
    mid50 = vout[mid50_start : mid50_stop + 1]
    mid50_tail_start = max(len(mid50) * 3 // 4, 1)
    settling_mid50_uv = 1e6 * abs(float(np.max(mid50[mid50_tail_start:]) - np.min(mid50[mid50_tail_start:])))
    return make_test_result(
        component="opamp_az_top_v3_prod",
        category="acceptance",
        purpose="noise_and_offset",
        metrics={
            "residual_offset_uV": residual_offset_uv,
            "pedestal_mid50_uV": pedestal_mid50_uv,
            "settling_mid50_uV": settling_mid50_uv,
        },
        passed=bool(np.isfinite(residual_offset_uv) and np.isfinite(pedestal_mid50_uv) and np.isfinite(settling_mid50_uv)),
    )


def run_noise_and_offset_monte_carlo(
    dut_params: OpampAzTopProdParams | None = None,
    tb_params: OpampAzTopProdNoiseAndOffsetTbParams | None = None,
    *,
    samples: int = 50,
    model_section: str = "tt_mm",
):
    dut_params = dut_params or OpampAzTopProdParams()
    tb_params = tb_params or OpampAzTopProdNoiseAndOffsetTbParams()
    if samples <= 0:
        raise ValueError("samples must be positive")

    residual_vals_uV: list[float] = []
    pedestal_vals_uV: list[float] = []
    settling_vals_uV: list[float] = []
    failures = 0

    for _ in range(samples):
        try:
            sim = build_noise_and_offset_mc_test(dut_params, tb_params, model_section=model_section)
            result = run_ngspice_sim(sim, SimOptions(rundir=f"./tmp/opamp_v3_prod_mc_{uuid4().hex[:8]}"))
            vout = _tran_waveform(result, "v(xtop.vout)")
            phi3 = _tran_waveform(result, "v(xtop.phi3)")
            active_idx = np.flatnonzero(phi3 > 0.5 * float(tb_params.vdd))
            if len(active_idx) == 0:
                raise RuntimeError("No settle-phase window detected in v3 prod MC test")
            run_start = int(active_idx[-1])
            while run_start > 0 and float(phi3[run_start - 1]) > 0.5 * float(tb_params.vdd):
                run_start -= 1
            run_stop = int(active_idx[-1])
            residual_offset_uv = 1e6 * abs(float(vout[run_stop]))

            def _window_p2p(start_frac: float, stop_frac: float) -> float:
                npts = run_stop - run_start + 1
                w_start = run_start + int(npts * start_frac)
                w_stop = run_start + int(npts * stop_frac)
                arr = vout[w_start : w_stop + 1]
                return 1e6 * abs(float(np.max(arr) - np.min(arr)))

            pedestal_mid50_uv = _window_p2p(0.25, 0.75)
            mid50_start = run_start + int((run_stop - run_start + 1) * 0.25)
            mid50_stop = run_start + int((run_stop - run_start + 1) * 0.75)
            mid50 = vout[mid50_start : mid50_stop + 1]
            mid50_tail_start = max(len(mid50) * 3 // 4, 1)
            settling_mid50_uv = 1e6 * abs(float(np.max(mid50[mid50_tail_start:]) - np.min(mid50[mid50_tail_start:])))
            residual_vals_uV.append(residual_offset_uv)
            pedestal_vals_uV.append(pedestal_mid50_uv)
            settling_vals_uV.append(settling_mid50_uv)
        except Exception:
            failures += 1

    if not residual_vals_uV:
        raise RuntimeError("All Monte Carlo v3 prod AZ samples failed")

    def _summarize(values: list[float], *, target_limit: float, maximum_limit: float, prefix: str) -> dict[str, float | int]:
        arr = np.asarray(values, dtype=float)
        percentiles = np.percentile(arr, [50, 90, 95, 99])
        return {
            f"{prefix}_mean_uV": float(np.mean(arr)),
            f"{prefix}_sigma_uV": float(np.std(arr)),
            f"{prefix}_max_uV": float(np.max(arr)),
            f"{prefix}_p50_uV": float(percentiles[0]),
            f"{prefix}_p90_uV": float(percentiles[1]),
            f"{prefix}_p95_uV": float(percentiles[2]),
            f"{prefix}_p99_uV": float(percentiles[3]),
            f"{prefix}_pass_rate_vs_target": float(np.sum(arr <= target_limit)) / float(len(arr)),
            f"{prefix}_pass_rate_vs_maximum": float(np.sum(arr <= maximum_limit)) / float(len(arr)),
        }

    target = OpampAzV3TargetSpec()
    maximum = OpampAzV3MaximumSpec()
    metrics = {
        "samples_requested": int(samples),
        "samples_completed": int(len(residual_vals_uV)),
        "samples_failed": int(failures),
        "model_section": model_section,
        **_summarize(residual_vals_uV, target_limit=target.residual_offset_uV_max, maximum_limit=maximum.residual_offset_uV_max, prefix="residual_offset"),
        **_summarize(pedestal_vals_uV, target_limit=target.pedestal_mid50_uV_max, maximum_limit=maximum.pedestal_mid50_uV_max, prefix="pedestal_mid50"),
        **_summarize(settling_vals_uV, target_limit=target.settling_mid50_uV_max, maximum_limit=maximum.settling_mid50_uV_max, prefix="settling_mid50"),
    }
    return make_test_result(
        component="opamp_az_top_v3_prod",
        category="acceptance",
        purpose="noise_and_offset_mc",
        metrics=metrics,
        passed=bool(metrics["residual_offset_pass_rate_vs_maximum"] >= 0.99),
    )


def run_reduced_pvt_test(
    dut_params: OpampAzTopProdParams | None = None,
    tb_params: OpampAzTopProdNoiseAndOffsetTbParams | None = None,
):
    dut_params = dut_params or OpampAzTopProdParams()
    tb_params = tb_params or OpampAzTopProdNoiseAndOffsetTbParams()
    cases = {
        "TT_V1.80_T27C": (h.pdk.Corner.TYP, 1.8, 27.0),
        "SS_V1.60_T125C": (h.pdk.Corner.SLOW, 1.6, 125.0),
        "FF_V1.98_T-40C": (h.pdk.Corner.FAST, 1.98, -40.0),
        "SS_V1.60_T-40C": (h.pdk.Corner.SLOW, 1.6, -40.0),
        "FF_V1.98_T125C": (h.pdk.Corner.FAST, 1.98, 125.0),
    }
    results = {}
    worst_residual = -float("inf")
    worst_ped_mid50 = -float("inf")
    worst_set_mid50 = -float("inf")
    for label, (corner, vdd, temp_c) in cases.items():
        case_tb = OpampAzTopProdNoiseAndOffsetTbParams(
            vdd=vdd,
            period=tb_params.period,
            dead_time=tb_params.dead_time,
            phi1_share=tb_params.phi1_share,
            phi2_share=tb_params.phi2_share,
            phi3_share=tb_params.phi3_share,
            tstop=tb_params.tstop,
            tstep=tb_params.tstep,
            temp_c=temp_c,
        )
        result = run_noise_and_offset_test(dut_params, case_tb, corner=corner)
        metrics = result["metrics"]
        results[label] = metrics
        worst_residual = max(worst_residual, float(metrics["residual_offset_uV"]))
        worst_ped_mid50 = max(worst_ped_mid50, float(metrics["pedestal_mid50_uV"]))
        worst_set_mid50 = max(worst_set_mid50, float(metrics["settling_mid50_uV"]))
    return make_test_result(
        component="opamp_az_top_v3_prod",
        category="acceptance",
        purpose="reduced_pvt",
        metrics={
            "cases": results,
            "worst_residual_offset_uV": worst_residual,
            "worst_pedestal_mid50_uV": worst_ped_mid50,
            "worst_settling_mid50_uV": worst_set_mid50,
        },
    )
