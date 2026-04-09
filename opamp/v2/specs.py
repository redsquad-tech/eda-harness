from dataclasses import dataclass


@dataclass(frozen=True)
class OpampAzV2TargetSpec:
    vdd_nominal_v: float = 1.8
    vdd_min_v: float = 1.6
    vdd_max_v: float = 1.98
    temp_min_c: float = -40.0
    temp_max_c: float = 125.0
    c_load_nominal_f: float = 1e-12
    c_load_max_f: float = 2e-12
    aol_db_min: float = 75.0
    gbw_hz_min: float = 5e5
    gbw_hz_max: float = 1e6
    phase_margin_deg_min: float = 30.0
    gain_margin_db_min: float = 5.0
    iq_uA_max: float = 15.0
    output_swing_low_max_v: float = 0.1
    output_swing_high_min_v: float = 1.7
    output_current_abs_min_uA: float = 25.0
    disabled_leakage_nA_max: float = 15.0
    residual_offset_uV_max: float = 150.0
    pedestal_mid50_uV_max: float = 50.0
    settling_mid50_uV_max: float = 30.0
    active_area_um2_min: float = 3000.0
    active_area_um2_max: float = 5000.0

