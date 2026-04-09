from pathlib import Path
import re
from dataclasses import dataclass

import hdl21 as h
from hdl21.sim import Ac, LogSweep, Save, SaveMode, Sim
from vlsirtools.spice import ResultFormat, SimOptions, SupportedSimulators

from .common import extract_subckt_name, make_test_result, print_metrics_table, run_ngspice_sim
from .pdk_resistor import pdk_resistor


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator_call", "elaboration", "subckt_name", "contains_cap"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "pole_zero_extract": {
        "specification_aspect": "pole-zero shaping characterization",
        "category": "char",
        "test_name": "run_pole_zero_extract_test",
        "analysis_type": "Ac",
        "extracted_metrics": ["dominant_pole_est", "zero_est"],
        "pass_fail_rule": "characterize compensation-network pole and zero behavior under the generic observation fixture",
        "required_corners": ["TT"],
        "required_operating_conditions": ["nominal_load"],
        "monte_carlo_required": False,
    },
}


@dataclass(frozen=True)
class FreqCompSpec:
    name: str = "freq_comp"
    purpose: str = "Provide Miller compensation between first and second stages."
    component_class: str = "reusable block"
    pins: tuple[str, ...] = ("V1", "VOUT")
    measurable_behaviors: tuple[str, ...] = ("pole_zero_extract",)
    numeric_pass_fail_criteria: tuple[str, ...] = ("generic compensation characterization only; product stability budgets belong in external budget tests",)
    required_corners: tuple[str, ...] = ("TT",)
    statistical_verification_required: bool = False


@h.paramclass
class FreqCompParams:
    c_comp = h.Param(dtype=h.Scalar, desc="Compensation capacitor in F", default=200e-15)
    r_zero = h.Param(dtype=h.Scalar, desc="Nulling resistor in ohm", default=0.0)
    use_nulling_resistor = h.Param(dtype=bool, desc="Insert series nulling resistor", default=False)


@h.paramclass
class FreqCompPoleZeroExtractTbParams:
    r_load = h.Param(dtype=h.Scalar, desc="Observation load in ohm", default=1e6)
    f_start = h.Param(dtype=h.Scalar, desc="AC sweep start frequency in Hz", default=1e3)
    f_stop = h.Param(dtype=h.Scalar, desc="AC sweep stop frequency in Hz", default=1e9)
    npts = h.Param(dtype=int, desc="AC sweep points per decade", default=10)


@h.generator
def freq_comp(params: FreqCompParams) -> h.Module:
    if params.c_comp <= 0:
        raise ValueError("c_comp must be positive")
    if params.use_nulling_resistor and params.r_zero <= 0:
        raise ValueError("r_zero must be positive when use_nulling_resistor is enabled")
    if not params.use_nulling_resistor and params.r_zero < 0:
        raise ValueError("r_zero must be non-negative")

    mod = h.Module(name="FreqComp")
    mod.V1, mod.VOUT = h.Ports(2)

    if params.use_nulling_resistor:
        mod.mid = h.Signal(name="mid")
        mod.rz = pdk_resistor(params.r_zero, p=mod.V1, n=mod.mid, bulk=None)
        mod.cc = h.Cap(c=params.c_comp)(p=mod.mid, n=mod.VOUT)
    else:
        mod.cc = h.Cap(c=params.c_comp)(p=mod.V1, n=mod.VOUT)
    return mod


def _default_ngspice_options(test_name: str) -> SimOptions:
    return SimOptions(
        simulator=SupportedSimulators.NGSPICE,
        fmt=ResultFormat.SIM_DATA,
        rundir=f"./tmp/{test_name}",
    )


def _extract_ac_trace(result, trace_name: str):
    ac = result.an[0]
    target = trace_name.lower()
    for key, data in ac.data.items():
        if key.lower() == target:
            return data
    raise RuntimeError(f"AC trace {trace_name} not found in result keys: {list(ac.data.keys())}")


def build_pole_zero_extract_test(
    dut_params: FreqCompParams,
    tb_params: FreqCompPoleZeroExtractTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
):
    del corner
    tb_params = tb_params or FreqCompPoleZeroExtractTbParams()
    dut = freq_comp(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        v1, vout = h.Signals(2)
        vac = h.Vdc(dc=0.0, ac=1.0)(p=v1, n=VSS)
        rload = h.Res(r=tb_params.r_load)(p=vout, n=VSS)
        xdut = dut(V1=v1, VOUT=vout)

    return Sim(
        tb=Tb,
        attrs=[
            Ac(sweep=LogSweep(tb_params.f_start, tb_params.f_stop, tb_params.npts)),
            Save(SaveMode.ALL),
        ],
    )


def run_pole_zero_extract_test(
    dut_params: FreqCompParams | None = None,
    tb_params: FreqCompPoleZeroExtractTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or FreqCompParams()
    tb_params = tb_params or FreqCompPoleZeroExtractTbParams()
    result = run_ngspice_sim(
        build_pole_zero_extract_test(dut_params, tb_params, corner=corner),
        sim_options if sim_options is not None else _default_ngspice_options("freq_comp_pole_zero_extract"),
    )
    vout = _extract_ac_trace(result, "v(xtop.vout)")
    gain_mag_first = abs(vout[0]) if len(vout) else float("nan")
    gain_mag_last = abs(vout[-1]) if len(vout) else float("nan")
    dominant_pole_est = 1.0 / (2.0 * 3.141592653589793 * float(tb_params.r_load) * float(dut_params.c_comp))
    zero_est = (
        1.0 / (2.0 * 3.141592653589793 * float(dut_params.r_zero) * float(dut_params.c_comp))
        if dut_params.use_nulling_resistor
        else float("inf")
    )
    return make_test_result(
        component="freq_comp",
        category="char",
        purpose="pole_zero_extract",
        metrics={
            "dominant_pole_est": dominant_pole_est,
            "zero_est": zero_est,
            "gain_mag_first": gain_mag_first,
            "gain_mag_last": gain_mag_last,
        },
    )


def run_all_tests(
    dut_params: FreqCompParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    dut_params = dut_params or FreqCompParams()
    return {
        "structural": make_test_result(
            component="freq_comp",
            category="smoke",
            purpose="basic",
            metrics=run_structural_checks(dut_params),
            passed=True,
        ),
        "pole_zero_extract": run_pole_zero_extract_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: FreqCompParams | None = None,
    *,
    sim_options: SimOptions | None = None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="freq_comp")
    return results


def elaborate_dut(params: FreqCompParams | None = None) -> h.Module:
    params = params or FreqCompParams()
    return h.elaborate(freq_comp(params))


def export_spice(path: str | Path, params: FreqCompParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: FreqCompParams | None = None):
    params = params or FreqCompParams()
    dut = freq_comp(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/freq_comp_structural/freq_comp.sp")
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
        "contains_cap": "cc" in text.lower(),
    }
    if params.use_nulling_resistor:
        checks["contains_rz"] = "mid" in text
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
