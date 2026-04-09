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

    # Low-value "short" resistors: use metal-5 generic resistors.
    if target_ohms <= 100.0:
        width_um = 2.0
        sheet_ohm_sq = 0.0113
        length_um = max(0.01, target_ohms * width_um / sheet_ohm_sq)
        return _PdkResChoice(
            module=sky130_hdl21.ress["GEN_M5"],
            params=sky130_hdl21.Sky130GenResParams(w=width_um, l=length_um, m=1),
            needs_bulk=False,
        )

    # Medium-value signal-path resistors: generic poly.
    if target_ohms <= 1e6:
        width_um = 0.35
        sheet_ohm_sq = 442.6
        length_um = max(0.5, target_ohms * width_um / sheet_ohm_sq)
        return _PdkResChoice(
            module=sky130_hdl21.ress["GEN_PO"],
            params=sky130_hdl21.Sky130GenResParams(w=width_um, l=length_um, m=1),
            needs_bulk=False,
        )

    # Very high-value bleeders and weak anchors: xhigh poly precision resistor.
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

