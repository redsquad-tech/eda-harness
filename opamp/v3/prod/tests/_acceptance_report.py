from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import hdl21 as h

from opamp.v3.specs import max_required_output_high

from ._acceptance_helpers import LOAD_SWEEP, MAX_SPEC, PVT_GRID, TIMING_SWEEP, core_drive, core_leakage, core_open_loop, core_swing, top_noise_offset, top_noise_offset_mc


LOAD_CASES = (
    ("tt", "tt_v1p80_t27", 1.8, 27.0),
    ("ss", "ss_v1p60_t125", 1.6, 125.0),
    ("ff", "ff_v1p98_tm40", 1.98, -40.0),
)


@dataclass(frozen=True)
class AcceptanceRow:
    metric: str
    condition: str
    requirement: str
    measured: str
    passed: bool


def _fmt_num(value: float, unit: str = "") -> str:
    if unit in {"Hz", "uV", "uA", "nA"}:
        return f"{value:.2f} {unit}"
    if unit in {"V", "deg", "dB"}:
        return f"{value:.3f} {unit}"
    if unit == "":
        return f"{value:.4f}"
    return f"{value:.4g} {unit}"


def _row_ge(metric: str, condition: str, measured: float, threshold: float, unit: str) -> AcceptanceRow:
    return AcceptanceRow(metric, condition, f">= {_fmt_num(threshold, unit)}", _fmt_num(measured, unit), measured >= threshold)


def _row_le(metric: str, condition: str, measured: float, threshold: float, unit: str) -> AcceptanceRow:
    return AcceptanceRow(metric, condition, f"<= {_fmt_num(threshold, unit)}", _fmt_num(measured, unit), measured <= threshold)


def _row_between(metric: str, condition: str, measured: float, lo: float, hi: float, unit: str) -> AcceptanceRow:
    return AcceptanceRow(metric, condition, f"{_fmt_num(lo, unit)} .. {_fmt_num(hi, unit)}", _fmt_num(measured, unit), lo <= measured <= hi)


def _condition(corner_label: str, vdd: float, temp_c: float) -> str:
    return f"{corner_label} / {vdd:.2f} V / {temp_c:.0f} C"


def _core_rows_for_case(label: str, corner, vdd: float, temp_c: float, c_load: float = 1e-12, drive_uA: float | None = None) -> list[AcceptanceRow]:
    cond = _condition(label.upper(), vdd, temp_c)
    ac = core_open_loop(label, corner, vdd, temp_c, c_load)
    swing = core_swing(label, corner, vdd, temp_c, c_load)
    rows = [
        _row_ge("core.aol_db", cond, float(ac["aol_db"]), MAX_SPEC.aol_db_min, "dB"),
        _row_between("core.gbw_hz", cond, float(ac["gbw_hz"]), MAX_SPEC.gbw_hz_min, MAX_SPEC.gbw_hz_max, "Hz"),
        _row_ge("core.phase_margin_deg", cond, float(ac["phase_margin_deg"]), MAX_SPEC.phase_margin_deg_min, "deg"),
        _row_ge("core.gain_margin_db", cond, float(ac["gain_margin_db"]), MAX_SPEC.gain_margin_db_min, "dB"),
        _row_le("core.iq_uA", cond, float(ac["iq_uA"]), MAX_SPEC.iq_uA_max, "uA"),
        _row_le("core.vout_low_actual", cond, float(swing["vout_low_actual"]), MAX_SPEC.output_swing_low_max_v, "V"),
        _row_ge("core.vout_high_actual", cond, float(swing["vout_high_actual"]), max_required_output_high(vdd), "V"),
    ]
    if drive_uA is not None:
        drive = core_drive(label, corner, vdd, temp_c, c_load, drive_uA)
        rows.extend(
            [
                _row_le("core.vout_source", cond + f" / +{drive_uA:.0f} uA", float(drive["vout_source"]), MAX_SPEC.output_swing_low_max_v, "V"),
                _row_ge("core.vout_sink", cond + f" / -{drive_uA:.0f} uA", float(drive["vout_sink"]), max_required_output_high(vdd), "V"),
            ]
        )
    return rows


def reduced_acceptance_rows() -> list[AcceptanceRow]:
    rows: list[AcceptanceRow] = []
    rows.extend(_core_rows_for_case("tt", h.pdk.Corner.TYP, 1.8, 27.0, drive_uA=MAX_SPEC.output_current_abs_min_uA))
    leak = core_leakage("ff", h.pdk.Corner.FAST, 1.98, -40.0)
    rows.append(_row_le("core.disabled_leakage_nA", _condition("FF", 1.98, -40.0), float(leak["disabled_leakage_nA"]), MAX_SPEC.disabled_leakage_nA_max, "nA"))

    tt = top_noise_offset("tt", h.pdk.Corner.TYP, 1.8, 27.0)
    rows.extend(
        [
            _row_le("top.residual_offset_uV", _condition("TT", 1.8, 27.0), float(tt["residual_offset_uV"]), MAX_SPEC.residual_offset_uV_max, "uV"),
            _row_le("top.pedestal_mid50_uV", _condition("TT", 1.8, 27.0), float(tt["pedestal_mid50_uV"]), MAX_SPEC.pedestal_mid50_uV_max, "uV"),
            _row_le("top.settling_mid50_uV", _condition("TT", 1.8, 27.0), float(tt["settling_mid50_uV"]), MAX_SPEC.settling_mid50_uV_max, "uV"),
        ]
    )
    for label, corner, vdd, temp_c in [
        ("tt", h.pdk.Corner.TYP, 1.8, 27.0),
        ("ss_hot", h.pdk.Corner.SLOW, 1.6, 125.0),
        ("ff_cold", h.pdk.Corner.FAST, 1.98, -40.0),
        ("ss_cold", h.pdk.Corner.SLOW, 1.6, -40.0),
        ("ff_hot", h.pdk.Corner.FAST, 1.98, 125.0),
    ]:
        m = top_noise_offset(label, corner, vdd, temp_c)
        cond = _condition(label.upper(), vdd, temp_c)
        rows.extend(
            [
                _row_le("top.residual_offset_uV", cond, float(m["residual_offset_uV"]), MAX_SPEC.residual_offset_uV_max, "uV"),
                _row_le("top.pedestal_mid50_uV", cond, float(m["pedestal_mid50_uV"]), MAX_SPEC.pedestal_mid50_uV_max, "uV"),
                _row_le("top.settling_mid50_uV", cond, float(m["settling_mid50_uV"]), MAX_SPEC.settling_mid50_uV_max, "uV"),
            ]
        )
    mc = top_noise_offset_mc(samples=50)
    rows.extend(
        [
            _row_ge("top.residual_offset_pass_rate", "TT mismatch-only MC / 50 samples", float(mc["residual_offset_pass_rate_vs_maximum"]), 0.99, ""),
            _row_le("top.residual_offset_p99_uV", "TT mismatch-only MC / 50 samples", float(mc["residual_offset_p99_uV"]), MAX_SPEC.residual_offset_uV_max, "uV"),
            _row_le("top.pedestal_mid50_p99_uV", "TT mismatch-only MC / 50 samples", float(mc["pedestal_mid50_p99_uV"]), MAX_SPEC.pedestal_mid50_uV_max, "uV"),
            _row_le("top.settling_mid50_p99_uV", "TT mismatch-only MC / 50 samples", float(mc["settling_mid50_p99_uV"]), MAX_SPEC.settling_mid50_uV_max, "uV"),
        ]
    )
    return rows


def full_pvt_core_rows() -> list[AcceptanceRow]:
    rows: list[AcceptanceRow] = []
    for label, corner, vdd, temp_c in PVT_GRID:
        rows.extend(_core_rows_for_case(label, corner, vdd, temp_c, drive_uA=MAX_SPEC.output_current_abs_min_uA))
        leak = core_leakage(label, corner, vdd, temp_c)
        rows.append(_row_le("core.disabled_leakage_nA", _condition(label.upper(), vdd, temp_c), float(leak["disabled_leakage_nA"]), MAX_SPEC.disabled_leakage_nA_max, "nA"))
    return rows


def full_pvt_top_rows() -> list[AcceptanceRow]:
    rows: list[AcceptanceRow] = []
    for label, corner, vdd, temp_c in PVT_GRID:
        m = top_noise_offset(label, corner, vdd, temp_c)
        cond = _condition(label.upper(), vdd, temp_c)
        rows.extend(
            [
                _row_le("top.residual_offset_uV", cond, float(m["residual_offset_uV"]), MAX_SPEC.residual_offset_uV_max, "uV"),
                _row_le("top.pedestal_mid50_uV", cond, float(m["pedestal_mid50_uV"]), MAX_SPEC.pedestal_mid50_uV_max, "uV"),
                _row_le("top.settling_mid50_uV", cond, float(m["settling_mid50_uV"]), MAX_SPEC.settling_mid50_uV_max, "uV"),
            ]
        )
    return rows


def load_sweep_rows() -> list[AcceptanceRow]:
    rows: list[AcceptanceRow] = []
    corner_map = {"tt": h.pdk.Corner.TYP, "ss": h.pdk.Corner.SLOW, "ff": h.pdk.Corner.FAST}
    for prefix, label, vdd, temp_c in LOAD_CASES:
        for c_load in LOAD_SWEEP:
            case = f"{label}_cl_{c_load:.2e}"
            rows.extend(_core_rows_for_case(case, corner_map[prefix], vdd, temp_c, c_load))
    return rows


def timing_mc_rows() -> list[AcceptanceRow]:
    rows: list[AcceptanceRow] = []
    for label, period, dead_time in TIMING_SWEEP:
        m = top_noise_offset(label, h.pdk.Corner.TYP, 1.8, 27.0, period=period, dead_time=dead_time)
        cond = f"{label} / TT / 1.80 V / 27 C"
        rows.extend(
            [
                _row_le("top.residual_offset_uV", cond, float(m["residual_offset_uV"]), MAX_SPEC.residual_offset_uV_max, "uV"),
                _row_le("top.pedestal_mid50_uV", cond, float(m["pedestal_mid50_uV"]), MAX_SPEC.pedestal_mid50_uV_max, "uV"),
                _row_le("top.settling_mid50_uV", cond, float(m["settling_mid50_uV"]), MAX_SPEC.settling_mid50_uV_max, "uV"),
            ]
        )
    mc = top_noise_offset_mc(samples=50)
    rows.extend(
        [
            _row_ge("top.residual_offset_pass_rate", "TT mismatch-only MC / 50 samples", float(mc["residual_offset_pass_rate_vs_maximum"]), 0.99, ""),
            _row_le("top.residual_offset_p99_uV", "TT mismatch-only MC / 50 samples", float(mc["residual_offset_p99_uV"]), MAX_SPEC.residual_offset_uV_max, "uV"),
            _row_le("top.pedestal_mid50_p99_uV", "TT mismatch-only MC / 50 samples", float(mc["pedestal_mid50_p99_uV"]), MAX_SPEC.pedestal_mid50_uV_max, "uV"),
            _row_le("top.settling_mid50_p99_uV", "TT mismatch-only MC / 50 samples", float(mc["settling_mid50_p99_uV"]), MAX_SPEC.settling_mid50_uV_max, "uV"),
        ]
    )
    return rows


def failing_rows(rows: Iterable[AcceptanceRow]) -> list[AcceptanceRow]:
    return [row for row in rows if not row.passed]


def rows_to_markdown(rows: Iterable[AcceptanceRow]) -> str:
    lines = [
        "| Metric | Condition | Requirement | Measured | Pass |",
        "|---|---|---|---:|:---:|",
    ]
    for row in rows:
        lines.append(f"| {row.metric} | {row.condition} | {row.requirement} | {row.measured} | {'PASS' if row.passed else 'FAIL'} |")
    return "\n".join(lines)


def assert_report_ok(testcase, report_name: str, row_builder: Callable[[], list[AcceptanceRow]]) -> None:
    rows = row_builder()
    failed = failing_rows(rows)
    summary = (
        f"\n[{report_name}] total_checks={len(rows)} failed_checks={len(failed)} "
        f"passed={len(failed) == 0}\n\n"
    )
    table = rows_to_markdown(rows)
    print(summary + table + "\n")
    if failed:
        message = summary + table
        testcase.fail(message)
