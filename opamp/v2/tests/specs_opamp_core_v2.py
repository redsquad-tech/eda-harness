# Active `v2` budget tests gate against the minimum SKY130 requirements from
# `opamp_az_spec.md`. The stricter maximum targets remain design goals, but are
# not the first closure gate for the current architecture work.

AOL_DB_MIN = 65.0
GBW_HZ_MIN = 3e5
GBW_HZ_MAX = 1e6
PHASE_MARGIN_DEG_MIN = 30.0
GAIN_MARGIN_DB_MIN = 5.0
IQ_UA_MAX = 20.0
OUTPUT_SWING_LOW_MAX = 0.1
OUTPUT_SWING_HIGH_MIN = 1.6
OUTPUT_CURRENT_ABS_MIN_UA = 20.0
DISABLED_LEAKAGE_NA_MAX = 250.0
