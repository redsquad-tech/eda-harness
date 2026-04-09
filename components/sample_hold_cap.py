from pathlib import Path

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Ac, LogSweep, Save, SaveMode, Sim
from vlsirtools.spice import ResultFormat, SimOptions, SupportedSimulators

from components import extract_subckt_name, print_metrics_table, require_sky130_install, run_ngspice_sim


VERIFICATION_PLAN = {
    "structural": {
        "specification_aspect": "generator/export contract",
        "category": "structural",
        "test_name": "run_structural_checks",
        "analysis_type": "generator/elaboration/export",
        "extracted_metrics": ["generator call", "elaboration", "subckt name", "cap cell presence"],
        "pass_fail_rule": "all structural checks pass",
        "required_corners": [],
        "required_operating_conditions": [],
        "monte_carlo_required": False,
    },
    "ac_smoke_tt": {
        "specification_aspect": "AC capacitor behavior",
        "category": "contract",
        "test_name": "run_ac_test",
        "analysis_type": "Ac",
        "extracted_metrics": ["source current magnitude"],
        "pass_fail_rule": "AC current magnitude is non-zero at TT",
        "required_corners": ["TT"],
        "required_operating_conditions": ["1 kHz to 1 MHz"],
        "monte_carlo_required": False,
    },
}


def _cap_primitive(cap_dev: str):
    aliases = {
        "MIM_M3": sky130_hdl21.primitives.MIM_M3,
        "MIM_M4": sky130_hdl21.primitives.MIM_M4,
        "cap_mim_m3__base": sky130_hdl21.primitives.MIM_M3,
        "cap_mim_m4__base": sky130_hdl21.primitives.MIM_M4,
    }
    try:
        return aliases[cap_dev]
    except KeyError as err:
        raise ValueError(f"Unsupported cap_dev: {cap_dev}") from err


def _cap_params(unit_w: h.Scalar, unit_l: h.Scalar, npar: int):
    return sky130_hdl21.Sky130MimParams(w=unit_w, l=unit_l, mf=npar)


def _default_ngspice_options(test_name: str) -> SimOptions:
    return SimOptions(
        simulator=SupportedSimulators.NGSPICE,
        fmt=ResultFormat.SIM_DATA,
        rundir=f"./tmp/{test_name}",
    )


def _passive_corner_includes(install):
    base = install.pdk_path / "libs.tech/ngspice"
    return [
        h.sim.Include(base / "corners/tt.spice"),
        h.sim.Include(base / "r+c/res_typical__cap_typical.spice"),
        h.sim.Include(base / "r+c/res_typical__cap_typical__lin.spice"),
        h.sim.Include(base / "corners/tt/specialized_cells.spice"),
    ]


def _extract_ac_current_magnitude(result) -> float:
    ac = result.an[0]
    for key, data in ac.data.items():
        if key.startswith("i("):
            return abs(data[0])
    raise RuntimeError(f"No AC current trace found in result keys: {list(ac.data.keys())}")


@h.paramclass
class SampleHoldCapParams:
    cap_dev = h.Param(dtype=str, desc="Cap device: MIM_M3, MIM_M4, cap_mim_m3__base, or cap_mim_m4__base", default="MIM_M3")
    c_target = h.Param(dtype=h.Scalar, desc="Target capacitance in F; design intent only", default=100e-15)
    unit_w = h.Param(dtype=h.Scalar, desc="Unit capacitor width in um", default=3.0)
    unit_l = h.Param(dtype=h.Scalar, desc="Unit capacitor length in um", default=3.0)
    nser = h.Param(dtype=int, desc="Number of capacitor sections in series", default=1)
    npar = h.Param(dtype=int, desc="Parallel multiplier per section", default=1)
    common_centroid = h.Param(dtype=bool, desc="Layout intent flag only; no electrical effect", default=False)


@h.paramclass
class SampleHoldCapAcTbParams:
    v_ac = h.Param(dtype=h.Scalar, desc="AC source magnitude in V", default=1.0)
    f_start = h.Param(dtype=h.Scalar, desc="AC sweep start frequency in Hz", default=1e3)
    f_stop = h.Param(dtype=h.Scalar, desc="AC sweep stop frequency in Hz", default=1e6)
    npts = h.Param(dtype=int, desc="AC sweep points per decade", default=5)


@h.generator
def sample_hold_cap(params: SampleHoldCapParams) -> h.Module:
    if params.nser < 1:
        raise ValueError(f"nser must be >= 1, got {params.nser}")
    if params.npar < 1:
        raise ValueError(f"npar must be >= 1, got {params.npar}")

    cap_prim = _cap_primitive(params.cap_dev)
    cap_params = _cap_params(params.unit_w, params.unit_l, params.npar)

    mod = h.Module(name="SampleHoldCap")
    mod.P = h.Port()
    mod.N = h.Port()

    nodes = [mod.P]
    for idx in range(params.nser - 1):
        sig = h.Signal(name=f"nser_{idx}")
        setattr(mod, f"nser_{idx}", sig)
        nodes.append(sig)
    nodes.append(mod.N)

    for idx in range(params.nser):
        inst = cap_prim(cap_params)(p=nodes[idx], n=nodes[idx + 1])
        setattr(mod, f"cap_{idx}", inst)

    return mod


def build_ac_test(
    dut_params: SampleHoldCapParams,
    tb_params: SampleHoldCapAcTbParams | None = None,
    *,
    corner,
) -> Sim:
    if corner != "TT":
        raise ValueError(f"sample_hold_cap AC smoke test currently supports only TT, got {corner}")

    tb_params = tb_params or SampleHoldCapAcTbParams()
    install = require_sky130_install()
    dut = sample_hold_cap(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        p = h.Signal()
        vac = h.Vdc(dc=0.0, ac=tb_params.v_ac)(p=p, n=VSS)
        xdut = dut(P=p, N=VSS)

    return Sim(
        tb=Tb,
        attrs=[
            Ac(sweep=LogSweep(tb_params.f_start, tb_params.f_stop, tb_params.npts)),
            Save(SaveMode.ALL),
            h.sim.Param(name="mc_mm_switch", val=0),
            h.sim.Param(name="mc_pr_switch", val=0),
            *_passive_corner_includes(install),
        ],
    )


def run_ac_test(
    dut_params: SampleHoldCapParams | None = None,
    tb_params: SampleHoldCapAcTbParams | None = None,
    *,
    corner="TT",
    sim_options=None,
):
    dut_params = dut_params or SampleHoldCapParams()
    sim = build_ac_test(dut_params, tb_params, corner=corner)
    return run_ngspice_sim(
        sim,
        sim_options if sim_options is not None else _default_ngspice_options("sample_hold_cap_ac"),
    )


def run_all_tests(
    dut_params: SampleHoldCapParams | None = None,
    *,
    sim_options=None,
):
    dut_params = dut_params or SampleHoldCapParams()
    structural = run_structural_checks(dut_params)
    ac_result = run_ac_test(dut_params, sim_options=sim_options)
    return {
        "structural": structural,
        "ac_smoke": {
            "current_magnitude": _extract_ac_current_magnitude(ac_result),
        },
    }


def print_test_report(
    dut_params: SampleHoldCapParams | None = None,
    *,
    sim_options=None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="sample_hold_cap")
    return results


def elaborate_dut(params: SampleHoldCapParams | None = None) -> h.Module:
    params = params or SampleHoldCapParams()
    return h.elaborate(sample_hold_cap(params))


def export_spice(path: str | Path, params: SampleHoldCapParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: SampleHoldCapParams | None = None):
    params = params or SampleHoldCapParams()
    dut = sample_hold_cap(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/sample_hold_cap_structural/sample_hold_cap.sp")
    export_spice(netlist_path, params)
    text = netlist_path.read_text()
    subckt_name = extract_subckt_name(text)
    cap_cell_name = _cap_primitive(params.cap_dev).name

    checks = {
        "generator_call": dut is not None,
        "elaboration": mod is not None,
        "subckt_name": subckt_name.startswith("SampleHoldCap"),
        "contains_cap_cell": cap_cell_name in text,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
