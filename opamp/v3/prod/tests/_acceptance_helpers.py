from __future__ import annotations

import functools

import hdl21 as h

from opamp.v1.tests.structural._helpers import init_sky130_install
from opamp.v3.measure_core import (
    OpampCoreDisabledTbParams,
    OpampCoreFollowerTbParams,
    OpampCoreOpenLoopTbParams,
    run_disabled_leakage_test,
    run_open_loop_test,
    run_output_drive_test,
    run_output_swing_test,
)
from opamp.v3.prod.opamp_az_top import (
    OpampAzTopProdNoiseAndOffsetTbParams,
    OpampAzTopProdParams,
    run_noise_and_offset_monte_carlo,
    run_noise_and_offset_test,
)
from opamp.v3.specs import OpampAzV3MaximumSpec


init_sky130_install()


MAX_SPEC = OpampAzV3MaximumSpec()
PROD_PARAMS = OpampAzTopProdParams()
CORE_PARAMS = PROD_PARAMS.opamp_core_params
PVT_GRID = (
    ("tt_v1p60_tm40", h.pdk.Corner.TYP, 1.6, -40.0),
    ("tt_v1p60_t27", h.pdk.Corner.TYP, 1.6, 27.0),
    ("tt_v1p60_t125", h.pdk.Corner.TYP, 1.6, 125.0),
    ("tt_v1p80_tm40", h.pdk.Corner.TYP, 1.8, -40.0),
    ("tt_v1p80_t27", h.pdk.Corner.TYP, 1.8, 27.0),
    ("tt_v1p80_t125", h.pdk.Corner.TYP, 1.8, 125.0),
    ("tt_v1p98_tm40", h.pdk.Corner.TYP, 1.98, -40.0),
    ("tt_v1p98_t27", h.pdk.Corner.TYP, 1.98, 27.0),
    ("tt_v1p98_t125", h.pdk.Corner.TYP, 1.98, 125.0),
    ("ss_v1p60_tm40", h.pdk.Corner.SLOW, 1.6, -40.0),
    ("ss_v1p60_t27", h.pdk.Corner.SLOW, 1.6, 27.0),
    ("ss_v1p60_t125", h.pdk.Corner.SLOW, 1.6, 125.0),
    ("ss_v1p80_tm40", h.pdk.Corner.SLOW, 1.8, -40.0),
    ("ss_v1p80_t27", h.pdk.Corner.SLOW, 1.8, 27.0),
    ("ss_v1p80_t125", h.pdk.Corner.SLOW, 1.8, 125.0),
    ("ss_v1p98_tm40", h.pdk.Corner.SLOW, 1.98, -40.0),
    ("ss_v1p98_t27", h.pdk.Corner.SLOW, 1.98, 27.0),
    ("ss_v1p98_t125", h.pdk.Corner.SLOW, 1.98, 125.0),
    ("ff_v1p60_tm40", h.pdk.Corner.FAST, 1.6, -40.0),
    ("ff_v1p60_t27", h.pdk.Corner.FAST, 1.6, 27.0),
    ("ff_v1p60_t125", h.pdk.Corner.FAST, 1.6, 125.0),
    ("ff_v1p80_tm40", h.pdk.Corner.FAST, 1.8, -40.0),
    ("ff_v1p80_t27", h.pdk.Corner.FAST, 1.8, 27.0),
    ("ff_v1p80_t125", h.pdk.Corner.FAST, 1.8, 125.0),
    ("ff_v1p98_tm40", h.pdk.Corner.FAST, 1.98, -40.0),
    ("ff_v1p98_t27", h.pdk.Corner.FAST, 1.98, 27.0),
    ("ff_v1p98_t125", h.pdk.Corner.FAST, 1.98, 125.0),
)
LOAD_SWEEP = (0.0, 0.5e-12, 1.0e-12, 2.0e-12)
TIMING_SWEEP = (
    ("freq10k", 100e-6, 0.5e-6),
    ("freq50k", 20e-6, 0.5e-6),
    ("freq100k", 10e-6, 0.5e-6),
    ("freq200k", 5e-6, 0.5e-6),
    ("dead10ns", 20e-6, 10e-9),
    ("dead20ns", 20e-6, 20e-9),
    ("dead50ns", 20e-6, 50e-9),
)


@functools.lru_cache(maxsize=None)
def core_open_loop(label: str, corner, vdd: float, temp_c: float, c_load: float = 1e-12) -> dict:
    del label
    return run_open_loop_test(
        CORE_PARAMS,
        OpampCoreOpenLoopTbParams(vdd=vdd, c_load=c_load, temp_c=temp_c),
        corner=corner,
    )["metrics"]


@functools.lru_cache(maxsize=None)
def core_swing(label: str, corner, vdd: float, temp_c: float, c_load: float = 1e-12) -> dict:
    del label
    return run_output_swing_test(
        CORE_PARAMS,
        OpampCoreFollowerTbParams(vdd=vdd, c_load=c_load, temp_c=temp_c),
        corner=corner,
    )["metrics"]


@functools.lru_cache(maxsize=None)
def core_drive(label: str, corner, vdd: float, temp_c: float, c_load: float = 1e-12, drive_uA: float = MAX_SPEC.output_current_abs_min_uA) -> dict:
    del label
    return run_output_drive_test(
        CORE_PARAMS,
        OpampCoreFollowerTbParams(vdd=vdd, c_load=c_load, temp_c=temp_c, drive_current_uA=drive_uA),
        corner=corner,
    )["metrics"]


@functools.lru_cache(maxsize=None)
def core_leakage(label: str, corner, vdd: float, temp_c: float) -> dict:
    del label
    return run_disabled_leakage_test(
        CORE_PARAMS,
        OpampCoreDisabledTbParams(vdd=vdd, temp_c=temp_c),
        corner=corner,
    )["metrics"]


@functools.lru_cache(maxsize=None)
def top_noise_offset(label: str, corner, vdd: float, temp_c: float, period: float = 5e-6, dead_time: float = 0.5e-6) -> dict:
    del label
    return run_noise_and_offset_test(
        PROD_PARAMS,
        OpampAzTopProdNoiseAndOffsetTbParams(vdd=vdd, temp_c=temp_c, period=period, dead_time=dead_time),
        corner=corner,
    )["metrics"]


@functools.lru_cache(maxsize=None)
def top_noise_offset_mc(samples: int = 50, period: float = 5e-6, dead_time: float = 0.5e-6) -> dict:
    return run_noise_and_offset_monte_carlo(
        PROD_PARAMS,
        OpampAzTopProdNoiseAndOffsetTbParams(vdd=1.8, temp_c=27.0, period=period, dead_time=dead_time),
        samples=samples,
        model_section="tt_mm",
    )["metrics"]
