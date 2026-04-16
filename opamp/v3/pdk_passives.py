from __future__ import annotations

from dataclasses import dataclass

import hdl21 as h
import sky130_hdl21


@dataclass(frozen=True)
class _PdkResChoice:
    module: object
    params: object
    needs_bulk: bool


def _choose_resistor(target_ohms: float) -> _PdkResChoice:
    if target_ohms <= 0:
        raise ValueError(f"target_ohms must be positive, got {target_ohms}")

    if target_ohms <= 100.0:
        width_um = 2.0
        sheet_ohm_sq = 0.0113
        length_um = max(0.01, target_ohms * width_um / sheet_ohm_sq)
        return _PdkResChoice(
            module=sky130_hdl21.ress["GEN_M5"],
            params=sky130_hdl21.Sky130GenResParams(w=width_um, l=length_um, m=1),
            needs_bulk=False,
        )

    if target_ohms <= 1e6:
        width_um = 0.35
        sheet_ohm_sq = 442.6
        length_um = max(0.5, target_ohms * width_um / sheet_ohm_sq)
        return _PdkResChoice(
            module=sky130_hdl21.ress["GEN_PO"],
            params=sky130_hdl21.Sky130GenResParams(w=width_um, l=length_um, m=1),
            needs_bulk=False,
        )

    width_um = 0.35
    sheet_ohm_sq = 22468.57
    length_um = max(0.5, target_ohms * width_um / sheet_ohm_sq)
    return _PdkResChoice(
        module=sky130_hdl21.ress["PM_PREC_0p35"],
        params=sky130_hdl21.Sky130PrecResParams(l=length_um, mult=1, m=1),
        needs_bulk=True,
    )


def pdk_resistor(target_ohms: float, *, p, n, bulk=None):
    choice = _choose_resistor(float(target_ohms))
    if choice.needs_bulk:
        if bulk is None:
            raise ValueError(f"bulk connection is required for target_ohms={target_ohms}")
        return choice.module(choice.params)(p=p, n=n, b=bulk)
    return choice.module(choice.params)(p=p, n=n)


def pdk_precision_resistor(target_ohms: float, *, p, n, bulk):
    """Analog-grade precision P-poly resistor.

    Use this for bias-setting references where generic poly would distort the
    intended current law. Maps to the same PM_PREC device family already used
    for large bias resistors elsewhere in the core.
    """

    target_ohms = float(target_ohms)
    if target_ohms <= 0:
        raise ValueError(f"target_ohms must be positive, got {target_ohms}")

    width_um = 0.35
    sheet_ohm_sq = 22468.57
    length_um = max(0.5, target_ohms * width_um / sheet_ohm_sq)
    params = sky130_hdl21.Sky130PrecResParams(l=length_um, mult=1, m=1)
    return sky130_hdl21.ress["PM_PREC_0p35"](params)(p=p, n=n, b=bulk)


def pdk_mim_capacitor(target_farad: float, *, p, n, cap_dev: str = "MIM_M3", density_f_per_um2: float = 2.0e-15):
    if target_farad <= 0:
        raise ValueError(f"target_farad must be positive, got {target_farad}")

    primitives = {
        "MIM_M3": sky130_hdl21.primitives.MIM_M3,
        "MIM_M4": sky130_hdl21.primitives.MIM_M4,
    }
    try:
        prim = primitives[cap_dev]
    except KeyError as err:
        raise ValueError(f"Unsupported cap_dev: {cap_dev}") from err

    area_um2 = max(float(target_farad) / float(density_f_per_um2), 4.0)
    side_um = area_um2 ** 0.5
    params = sky130_hdl21.Sky130MimParams(w=side_um, l=side_um, mf=1)
    return prim(params)(p=p, n=n)
