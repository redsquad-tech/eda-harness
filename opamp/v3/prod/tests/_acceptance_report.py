from __future__ import annotations

import traceback
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

METRIC_DISPLAY_NAMES = {
    "core.aol_db": "Open-loop gain",
    "core.gbw_hz": "GBW",
    "core.phase_margin_deg": "Phase margin",
    "core.gain_margin_db": "Gain margin",
    "core.iq_uA": "Quiescent current, enabled",
    "core.vout_low_actual": "Output compliant swing low",
    "core.vout_high_actual": "Output compliant swing high",
    "core.vout_source": "Output voltage while sourcing 25 uA",
    "core.vout_sink": "Output voltage while sinking 25 uA",
    "core.disabled_leakage_nA": "Disabled leakage current",
    "top.residual_offset_uV": "Residual input-referred offset after AZ",
    "top.pedestal_mid50_uV": "Pedestal-equivalent input error at nominal",
    "top.settling_mid50_uV": "Hold droop contribution per AZ cycle",
    "top.offset_mean_uV": "MC residual offset mean",
    "top.offset_stddev_uV": "MC residual offset stddev",
    "top.residual_offset_pass_rate": "MC residual offset pass rate",
    "top.residual_offset_p99_uV": "MC residual offset p99",
    "top.pedestal_mid50_p99_uV": "MC pedestal-equivalent input error p99",
    "top.settling_mid50_p99_uV": "MC hold droop contribution p99",
    "report.build": "Report build status",
}


@dataclass(frozen=True)
class AcceptanceRow:
    metric: str
    condition: str
    requirement: str
    measured: str
    passed: bool
    details: str = ""


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


def _row_info(metric: str, condition: str, measured: float, unit: str, requirement: str = "report-only") -> AcceptanceRow:
    return AcceptanceRow(metric, condition, requirement, _fmt_num(measured, unit), True)


def _condition(corner_label: str, vdd: float, temp_c: float) -> str:
    return f"{corner_label} / {vdd:.2f} V / {temp_c:.0f} C"


def _error_row(metric: str, condition: str, exc: BaseException) -> AcceptanceRow:
    tb = traceback.format_exc().strip()
    details = tb if tb and tb != "NoneType: None" else repr(exc)
    return AcceptanceRow(
        metric=metric,
        condition=condition,
        requirement="system-error-free",
        measured=f"ERROR: {type(exc).__name__}: {exc}",
        passed=False,
        details=details,
    )


def metric_display_name(metric: str) -> str:
    return METRIC_DISPLAY_NAMES.get(metric, metric)


def _safe_collect(metric_prefix: str, condition: str, builder: Callable[[], list[AcceptanceRow]]) -> list[AcceptanceRow]:
    try:
        return builder()
    except BaseException as exc:
        return [_error_row(metric_prefix, condition, exc)]


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
    rows.extend(
        _safe_collect(
            "core.reduced.tt",
            _condition("TT", 1.8, 27.0),
            lambda: _core_rows_for_case("tt", h.pdk.Corner.TYP, 1.8, 27.0, drive_uA=MAX_SPEC.output_current_abs_min_uA),
        )
    )
    rows.extend(
        _safe_collect(
            "core.disabled_leakage_nA",
            _condition("FF", 1.98, -40.0),
            lambda: [
                _row_le(
                    "core.disabled_leakage_nA",
                    _condition("FF", 1.98, -40.0),
                    float(core_leakage("ff", h.pdk.Corner.FAST, 1.98, -40.0)["disabled_leakage_nA"]),
                    MAX_SPEC.disabled_leakage_nA_max,
                    "nA",
                )
            ],
        )
    )

    rows.extend(
        _safe_collect(
            "top.reduced.tt",
            _condition("TT", 1.8, 27.0),
            lambda: [
                _row_le("top.residual_offset_uV", _condition("TT", 1.8, 27.0), float(top_noise_offset("tt", h.pdk.Corner.TYP, 1.8, 27.0)["residual_offset_uV"]), MAX_SPEC.residual_offset_uV_max, "uV"),
                _row_le("top.pedestal_mid50_uV", _condition("TT", 1.8, 27.0), float(top_noise_offset("tt", h.pdk.Corner.TYP, 1.8, 27.0)["pedestal_mid50_uV"]), MAX_SPEC.pedestal_mid50_uV_max, "uV"),
                _row_le("top.settling_mid50_uV", _condition("TT", 1.8, 27.0), float(top_noise_offset("tt", h.pdk.Corner.TYP, 1.8, 27.0)["settling_mid50_uV"]), MAX_SPEC.settling_mid50_uV_max, "uV"),
            ],
        )
    )
    for label, corner, vdd, temp_c in [
        ("tt", h.pdk.Corner.TYP, 1.8, 27.0),
        ("ss_hot", h.pdk.Corner.SLOW, 1.6, 125.0),
        ("ff_cold", h.pdk.Corner.FAST, 1.98, -40.0),
        ("ss_cold", h.pdk.Corner.SLOW, 1.6, -40.0),
        ("ff_hot", h.pdk.Corner.FAST, 1.98, 125.0),
    ]:
        cond = _condition(label.upper(), vdd, temp_c)
        rows.extend(
            _safe_collect(
                "top.reduced.pvt",
                cond,
                lambda label=label, corner=corner, vdd=vdd, temp_c=temp_c, cond=cond: [
                    _row_le("top.residual_offset_uV", cond, float(top_noise_offset(label, corner, vdd, temp_c)["residual_offset_uV"]), MAX_SPEC.residual_offset_uV_max, "uV"),
                    _row_le("top.pedestal_mid50_uV", cond, float(top_noise_offset(label, corner, vdd, temp_c)["pedestal_mid50_uV"]), MAX_SPEC.pedestal_mid50_uV_max, "uV"),
                    _row_le("top.settling_mid50_uV", cond, float(top_noise_offset(label, corner, vdd, temp_c)["settling_mid50_uV"]), MAX_SPEC.settling_mid50_uV_max, "uV"),
                ],
            )
        )
    rows.extend(
        _safe_collect(
            "top.mc",
            "TT mismatch-only MC / 50 samples",
            lambda: (
                lambda mc: [
                    _row_info("top.offset_mean_uV", "TT mismatch-only MC / 50 samples", float(mc["residual_offset_mean_uV"]), "uV"),
                    _row_info("top.offset_stddev_uV", "TT mismatch-only MC / 50 samples", float(mc["residual_offset_sigma_uV"]), "uV"),
                    _row_ge("top.residual_offset_pass_rate", "TT mismatch-only MC / 50 samples", float(mc["residual_offset_pass_rate_vs_maximum"]), 0.99, ""),
                    _row_le("top.residual_offset_p99_uV", "TT mismatch-only MC / 50 samples", float(mc["residual_offset_p99_uV"]), MAX_SPEC.residual_offset_uV_max, "uV"),
                    _row_le("top.pedestal_mid50_p99_uV", "TT mismatch-only MC / 50 samples", float(mc["pedestal_mid50_p99_uV"]), MAX_SPEC.pedestal_mid50_uV_max, "uV"),
                    _row_le("top.settling_mid50_p99_uV", "TT mismatch-only MC / 50 samples", float(mc["settling_mid50_p99_uV"]), MAX_SPEC.settling_mid50_uV_max, "uV"),
                ]
            )(top_noise_offset_mc(samples=50)),
        )
    )
    return rows


def full_pvt_core_rows() -> list[AcceptanceRow]:
    rows: list[AcceptanceRow] = []
    for label, corner, vdd, temp_c in PVT_GRID:
        cond = _condition(label.upper(), vdd, temp_c)
        rows.extend(_safe_collect("core.full_pvt", cond, lambda label=label, corner=corner, vdd=vdd, temp_c=temp_c: _core_rows_for_case(label, corner, vdd, temp_c, drive_uA=MAX_SPEC.output_current_abs_min_uA)))
        rows.extend(
            _safe_collect(
                "core.disabled_leakage_nA",
                cond,
                lambda label=label, corner=corner, vdd=vdd, temp_c=temp_c, cond=cond: [
                    _row_le("core.disabled_leakage_nA", cond, float(core_leakage(label, corner, vdd, temp_c)["disabled_leakage_nA"]), MAX_SPEC.disabled_leakage_nA_max, "nA")
                ],
            )
        )
    return rows


def full_pvt_top_rows() -> list[AcceptanceRow]:
    rows: list[AcceptanceRow] = []
    for label, corner, vdd, temp_c in PVT_GRID:
        cond = _condition(label.upper(), vdd, temp_c)
        rows.extend(
            _safe_collect(
                "top.full_pvt",
                cond,
                lambda label=label, corner=corner, vdd=vdd, temp_c=temp_c, cond=cond: [
                    _row_le("top.residual_offset_uV", cond, float(top_noise_offset(label, corner, vdd, temp_c)["residual_offset_uV"]), MAX_SPEC.residual_offset_uV_max, "uV"),
                    _row_le("top.pedestal_mid50_uV", cond, float(top_noise_offset(label, corner, vdd, temp_c)["pedestal_mid50_uV"]), MAX_SPEC.pedestal_mid50_uV_max, "uV"),
                    _row_le("top.settling_mid50_uV", cond, float(top_noise_offset(label, corner, vdd, temp_c)["settling_mid50_uV"]), MAX_SPEC.settling_mid50_uV_max, "uV"),
                ],
            )
        )
    return rows


def load_sweep_rows() -> list[AcceptanceRow]:
    rows: list[AcceptanceRow] = []
    corner_map = {"tt": h.pdk.Corner.TYP, "ss": h.pdk.Corner.SLOW, "ff": h.pdk.Corner.FAST}
    for prefix, label, vdd, temp_c in LOAD_CASES:
        for c_load in LOAD_SWEEP:
            case = f"{label}_cl_{c_load:.2e}"
            rows.extend(_safe_collect("core.load_sweep", _condition(case.upper(), vdd, temp_c), lambda case=case, prefix=prefix, vdd=vdd, temp_c=temp_c, c_load=c_load: _core_rows_for_case(case, corner_map[prefix], vdd, temp_c, c_load)))
    return rows


def timing_mc_rows() -> list[AcceptanceRow]:
    rows: list[AcceptanceRow] = []
    for label, period, dead_time in TIMING_SWEEP:
        cond = f"{label} / TT / 1.80 V / 27 C"
        rows.extend(
            _safe_collect(
                "top.timing",
                cond,
                lambda label=label, period=period, dead_time=dead_time, cond=cond: [
                    _row_le("top.residual_offset_uV", cond, float(top_noise_offset(label, h.pdk.Corner.TYP, 1.8, 27.0, period=period, dead_time=dead_time)["residual_offset_uV"]), MAX_SPEC.residual_offset_uV_max, "uV"),
                    _row_le("top.pedestal_mid50_uV", cond, float(top_noise_offset(label, h.pdk.Corner.TYP, 1.8, 27.0, period=period, dead_time=dead_time)["pedestal_mid50_uV"]), MAX_SPEC.pedestal_mid50_uV_max, "uV"),
                    _row_le("top.settling_mid50_uV", cond, float(top_noise_offset(label, h.pdk.Corner.TYP, 1.8, 27.0, period=period, dead_time=dead_time)["settling_mid50_uV"]), MAX_SPEC.settling_mid50_uV_max, "uV"),
                ],
            )
        )
    rows.extend(
        _safe_collect(
            "top.mc",
            "TT mismatch-only MC / 50 samples",
            lambda: (
                lambda mc: [
                    _row_info("top.offset_mean_uV", "TT mismatch-only MC / 50 samples", float(mc["residual_offset_mean_uV"]), "uV"),
                    _row_info("top.offset_stddev_uV", "TT mismatch-only MC / 50 samples", float(mc["residual_offset_sigma_uV"]), "uV"),
                    _row_ge("top.residual_offset_pass_rate", "TT mismatch-only MC / 50 samples", float(mc["residual_offset_pass_rate_vs_maximum"]), 0.99, ""),
                    _row_le("top.residual_offset_p99_uV", "TT mismatch-only MC / 50 samples", float(mc["residual_offset_p99_uV"]), MAX_SPEC.residual_offset_uV_max, "uV"),
                    _row_le("top.pedestal_mid50_p99_uV", "TT mismatch-only MC / 50 samples", float(mc["pedestal_mid50_p99_uV"]), MAX_SPEC.pedestal_mid50_uV_max, "uV"),
                    _row_le("top.settling_mid50_p99_uV", "TT mismatch-only MC / 50 samples", float(mc["settling_mid50_p99_uV"]), MAX_SPEC.settling_mid50_uV_max, "uV"),
                ]
            )(top_noise_offset_mc(samples=50)),
        )
    )
    return rows


def failing_rows(rows: Iterable[AcceptanceRow]) -> list[AcceptanceRow]:
    return [row for row in rows if not row.passed]


def rows_to_markdown(rows: Iterable[AcceptanceRow]) -> str:
    lines = [
        "| Name | Condition | Requirement | Measured | Pass | Details |",
        "|---|---|---|---:|:---:|---|",
    ]
    for row in rows:
        details = row.details.replace("\n", "<br>") if row.details else ""
        lines.append(f"| {metric_display_name(row.metric)} | {row.condition} | {row.requirement} | {row.measured} | {'PASS' if row.passed else 'FAIL'} | {details} |")
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
