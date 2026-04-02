from pathlib import Path
from typing import Any

import hdl21 as h
import sky130_hdl21 as sky
from hdl21.sim import Sim

from sweep import SweepConfig, SweepRunner

MosParams = sky.Sky130MosParams
IREF_A = 10e-6

@h.paramclass
class MirrorParams:
    w = h.Param(dtype=float, default=2.0, desc="Width in microns")
    l = h.Param(dtype=float, default=0.15, desc="Length in microns")
    nf = h.Param(dtype=int, default=4, desc="Number of fingers")


@h.generator
def NmosMirror(params: MirrorParams) -> h.Module:
    @h.module
    class NmosCurrentMirror:
        ibias = h.Input(desc="Reference current node")
        iout = h.Output(desc="Mirrored current output")
        vss = h.Inout(desc="Ground / bulk")

        mp = sky.Sky130MosParams(w=params.w, l=params.l, nf=params.nf)

        mref = sky.primitives.NMOS_1p8V_STD(mp)(
            d=ibias, g=ibias, s=vss, b=vss
        )
        mout = sky.primitives.NMOS_1p8V_STD(mp)(
            d=iout, g=ibias, s=vss, b=vss
        )

    return NmosCurrentMirror


ROOT = Path(__file__).resolve().parent
MODEL_LIB = str((ROOT / "../pdks/sky130A/libs.tech/ngspice/sky130.lib.spice").resolve())
RUNDIR = str((ROOT / "scratch").resolve())

mirror_mod = NmosMirror(MirrorParams(w=2.0, l=0.15, nf=4))


def make_tb(vout: float) -> h.Module:
    @h.module
    class MirrorTb:
        ibias = h.Signal()
        iout = h.Signal()
        gnd = h.Ground()

        xdut = mirror_mod(ibias=ibias, iout=iout, vss=gnd)

        iref = h.Idc(dc=IREF_A)(p=ibias, n=gnd)
        voutsrc = h.Vdc(dc=vout)(p=iout, n=gnd)

    return MirrorTb


def build_sim(sim: Sim) -> None:
    sim.op(name="op")


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _walk(item)
    elif hasattr(obj, "__dict__"):
        yield vars(obj)
        for v in vars(obj).values():
            yield from _walk(v)


def _find_value_by_key_fragment(obj: Any, fragments: list[str]) -> float | None:
    fragments = [f.lower() for f in fragments]
    for node in _walk(obj):
        if isinstance(node, dict):
            for k, v in node.items():
                ks = str(k).lower()
                if all(f in ks for f in fragments):
                    try:
                        return float(v)
                    except Exception:
                        pass
    return None


def extract_result(result: Any, vout: float) -> dict[str, Any]:
    # Это intentionally loose, потому что структура result у vlsirtools местами мутная.
    i_voutsrc = _find_value_by_key_fragment(result, ["voutsrc"])
    v_ibias = _find_value_by_key_fragment(result, ["ibias"])
    v_iout = _find_value_by_key_fragment(result, ["iout"])

    iout = None
    error_rel = None
    if i_voutsrc is not None:
        iout = -i_voutsrc
        error_rel = (iout - IREF_A) / IREF_A

    return {
        "vout_v": vout,
        "iref_a": IREF_A,
        "i_voutsrc_a": i_voutsrc,
        "iout_a": iout,
        "error_rel": error_rel,
        "v_ibias_v": v_ibias,
        "v_iout_v": v_iout,
    }


def frange(start: float, stop: float, step: float) -> list[float]:
    vals = []
    x = start
    while x <= stop + 1e-15:
        vals.append(round(x, 12))
        x += step
    return vals


def main() -> None:
    cfg = SweepConfig(
        model_lib=MODEL_LIB,
        model_section="tt",
        rundir=RUNDIR,
        reltol=1e-5,
    )

    runner = SweepRunner[float](
        config=cfg,
        tb_factory=make_tb,
        sim_builder=build_sim,
        extract_fn=extract_result,
    )

    points = frange(0.0, 1.8, 0.1)
    results = runner.run_many(points)

    for r in results:
        if r.ok:
            print(f"Vout={r.value:.3f} OK  {r.data}")
        else:
            print(f"Vout={r.value:.3f} ERR {r.error}")

    out_csv = ROOT / "mirror_sweep.csv"
    runner.save_csv(results, out_csv)
    print(f"\nSaved results to: {out_csv}")


if __name__ == "__main__":
    main()