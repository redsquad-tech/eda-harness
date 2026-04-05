from pathlib import Path

import hdl21 as h
import sky130_hdl21
from hdl21.sim import Op, Save, SaveMode, Sim
from vlsirtools.spice import SimOptions, SupportedSimulators

from components import extract_subckt_name, print_metrics_table, require_sky130_install, run_ngspice_sim


VERIFICATION_PLAN = {
    "structural": {
        "test": "run_structural_checks",
        "analysis": "generator/elaboration/export",
        "metrics": ["generator call", "elaboration", "subckt name", "device presence"],
        "rule": "all structural checks pass",
        "corners": [],
        "sweeps": [],
        "monte_carlo": False,
    },
    "on_smoke": {
        "test": "run_on_test",
        "analysis": "Op",
        "metrics": ["simulation completion", "v(xtop.b)"],
        "rule": "smoke test only; no formal numeric acceptance criterion yet",
        "corners": ["TT"],
        "sweeps": [],
        "monte_carlo": False,
    },
    "off_smoke": {
        "test": "run_off_test",
        "analysis": "Op",
        "metrics": ["simulation completion", "v(xtop.b)"],
        "rule": "smoke test only; no formal numeric acceptance criterion yet",
        "corners": ["TT"],
        "sweeps": [],
        "monte_carlo": False,
    },
}


def _mos_primitive(name: str):
    try:
        return getattr(sky130_hdl21.primitives, name)
    except AttributeError as err:
        raise ValueError(f"Unsupported SKY130 primitive: {name}") from err


def _mos_params(w: h.Scalar, l: h.Scalar, nf: int, mult: int):
    return sky130_hdl21.Sky130MosParams(w=w, l=l, nf=nf, mult=mult)


def _default_ngspice_options(test_name: str) -> SimOptions:
    return SimOptions(
        simulator=SupportedSimulators.NGSPICE,
        rundir=f"./tmp/{test_name}",
    )


@h.paramclass
class TgSwitchParams:
    dev_n = h.Param(dtype=str, desc="SKY130 NMOS primitive name", default="NMOS_1p8V_STD")
    dev_p = h.Param(dtype=str, desc="SKY130 PMOS primitive name", default="PMOS_1p8V_STD")
    w_n = h.Param(dtype=h.Scalar, desc="NMOS width in um", default=0.65)
    l_n = h.Param(dtype=h.Scalar, desc="NMOS length in um", default=0.15)
    nf_n = h.Param(dtype=int, desc="NMOS fingers", default=1)
    m_n = h.Param(dtype=int, desc="NMOS multiplier", default=1)
    w_p = h.Param(dtype=h.Scalar, desc="PMOS width in um", default=1.0)
    l_p = h.Param(dtype=h.Scalar, desc="PMOS length in um", default=0.15)
    nf_p = h.Param(dtype=int, desc="PMOS fingers", default=1)
    m_p = h.Param(dtype=int, desc="PMOS multiplier", default=1)
    use_dummy_switch = h.Param(dtype=bool, desc="Add a parasitic-matching dummy pair", default=False)
    body_tie_style = h.Param(dtype=str, desc="Body tie strategy: rails or implicit", default="rails")


@h.paramclass
class TgSwitchOnTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Positive supply in V", default=1.8)
    v_in = h.Param(dtype=h.Scalar, desc="Input voltage at A in V", default=0.9)
    r_load = h.Param(dtype=h.Scalar, desc="Load from B to VSS in ohm", default=1e6)
    v_phi = h.Param(dtype=h.Scalar, desc="ON-state NMOS gate drive in V", default=1.8)
    v_phib = h.Param(dtype=h.Scalar, desc="ON-state PMOS gate drive in V", default=0.0)


@h.paramclass
class TgSwitchOffTbParams:
    vdd = h.Param(dtype=h.Scalar, desc="Positive supply in V", default=1.8)
    v_in = h.Param(dtype=h.Scalar, desc="Input voltage at A in V", default=0.9)
    r_load = h.Param(dtype=h.Scalar, desc="Load from B to VSS in ohm", default=1e6)
    v_phi = h.Param(dtype=h.Scalar, desc="OFF-state NMOS gate drive in V", default=0.0)
    v_phib = h.Param(dtype=h.Scalar, desc="OFF-state PMOS gate drive in V", default=1.8)


@h.generator
def tg_switch(params: TgSwitchParams) -> h.Module:
    if params.body_tie_style not in ("rails", "implicit"):
        raise ValueError(f"Unsupported body_tie_style: {params.body_tie_style}")

    nmos = _mos_primitive(params.dev_n)
    pmos = _mos_primitive(params.dev_p)
    npar = _mos_params(params.w_n, params.l_n, params.nf_n, params.m_n)
    ppar = _mos_params(params.w_p, params.l_p, params.nf_p, params.m_p)

    @h.module
    class TgSwitch:
        A, B, PHI, PHIB, VDD, VSS = h.Ports(6)

        sw_n = nmos(npar)(d=A, g=PHI, s=B, b=VSS)
        sw_p = pmos(ppar)(d=A, g=PHIB, s=B, b=VDD)

        if params.use_dummy_switch:
            dummy = h.Signal()
            dummy_n = nmos(npar)(d=dummy, g=PHIB, s=dummy, b=VSS)
            dummy_p = pmos(ppar)(d=dummy, g=PHI, s=dummy, b=VDD)

    return TgSwitch


def build_on_test(
    dut_params: TgSwitchParams,
    tb_params: TgSwitchOnTbParams | None = None,
    *,
    corner,
) -> Sim:
    tb_params = tb_params or TgSwitchOnTbParams()
    install = require_sky130_install()
    dut = tg_switch(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        a, b, phi, phib, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        vvin = h.Vdc(dc=tb_params.v_in)(p=a, n=VSS)
        vphi = h.Vdc(dc=tb_params.v_phi)(p=phi, n=VSS)
        vphib = h.Vdc(dc=tb_params.v_phib)(p=phib, n=VSS)
        rload = h.Res(r=tb_params.r_load)(p=b, n=VSS)
        xdut = dut(A=a, B=b, PHI=phi, PHIB=phib, VDD=vdd, VSS=VSS)

    return Sim(tb=Tb, attrs=[Op(), Save(SaveMode.ALL), install.include(corner)])


def build_off_test(
    dut_params: TgSwitchParams,
    tb_params: TgSwitchOffTbParams | None = None,
    *,
    corner,
) -> Sim:
    tb_params = tb_params or TgSwitchOffTbParams()
    install = require_sky130_install()
    dut = tg_switch(dut_params)

    @h.module
    class Tb:
        VSS = h.Port()
        a, b, phi, phib, vdd = h.Signals(5)
        vvdd = h.Vdc(dc=tb_params.vdd)(p=vdd, n=VSS)
        vvin = h.Vdc(dc=tb_params.v_in)(p=a, n=VSS)
        vphi = h.Vdc(dc=tb_params.v_phi)(p=phi, n=VSS)
        vphib = h.Vdc(dc=tb_params.v_phib)(p=phib, n=VSS)
        rload = h.Res(r=tb_params.r_load)(p=b, n=VSS)
        xdut = dut(A=a, B=b, PHI=phi, PHIB=phib, VDD=vdd, VSS=VSS)

    return Sim(tb=Tb, attrs=[Op(), Save(SaveMode.ALL), install.include(corner)])


def run_on_test(
    dut_params: TgSwitchParams | None = None,
    tb_params: TgSwitchOnTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options=None,
):
    dut_params = dut_params or TgSwitchParams()
    sim = build_on_test(dut_params, tb_params, corner=corner)
    return run_ngspice_sim(
        sim,
        sim_options if sim_options is not None else _default_ngspice_options("tg_switch_on"),
    )


def run_off_test(
    dut_params: TgSwitchParams | None = None,
    tb_params: TgSwitchOffTbParams | None = None,
    *,
    corner=h.pdk.Corner.TYP,
    sim_options=None,
):
    dut_params = dut_params or TgSwitchParams()
    sim = build_off_test(dut_params, tb_params, corner=corner)
    return run_ngspice_sim(
        sim,
        sim_options if sim_options is not None else _default_ngspice_options("tg_switch_off"),
    )


def run_all_tests(
    dut_params: TgSwitchParams | None = None,
    *,
    sim_options=None,
):
    dut_params = dut_params or TgSwitchParams()
    return {
        "structural": run_structural_checks(dut_params),
        "on_smoke": run_on_test(dut_params, sim_options=sim_options),
        "off_smoke": run_off_test(dut_params, sim_options=sim_options),
    }


def print_test_report(
    dut_params: TgSwitchParams | None = None,
    *,
    sim_options=None,
):
    results = run_all_tests(dut_params, sim_options=sim_options)
    print_metrics_table(results, title="tg_switch")
    return results


def elaborate_dut(params: TgSwitchParams | None = None) -> h.Module:
    params = params or TgSwitchParams()
    return h.elaborate(tg_switch(params))


def export_spice(path: str | Path, params: TgSwitchParams | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mod = elaborate_dut(params)
    with path.open("w") as f:
        h.netlist(mod, f, fmt="spice")
    return path


def run_structural_checks(params: TgSwitchParams | None = None):
    params = params or TgSwitchParams()
    dut = tg_switch(params)
    mod = elaborate_dut(params)
    netlist_path = Path("./tmp/tg_switch_structural/tg_switch.sp")
    export_spice(netlist_path, params)
    text = netlist_path.read_text()
    subckt_name = extract_subckt_name(text)

    checks = {
        "generator_call": dut is not None,
        "elaboration": mod is not None,
        "subckt_name": subckt_name.startswith("TgSwitch_"),
        "contains_nmos": "sky130_fd_pr__nfet_01v8" in text,
        "contains_pmos": "sky130_fd_pr__pfet_01v8" in text,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Structural checks failed: {checks}")
    return checks
