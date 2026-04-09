from dataclasses import dataclass


@dataclass(frozen=True)
class BlockRole:
    name: str
    required: bool
    role: str
    constraints: tuple[str, ...]


ARCHITECTURE_EXPERIMENT = "opamp_v2_systematic_redesign"

BLOCK_ROLES: tuple[BlockRole, ...] = (
    BlockRole(
        name="bias_gen",
        required=True,
        role="Provide all downstream bias conditions without extra in-core bias adapters.",
        constraints=(
            "No hidden current-to-voltage conversion path inside opamp_core",
            "Bias interface must be explicit and stable across corners",
        ),
    ),
    BlockRole(
        name="input_stage",
        required=True,
        role="PMOS-input first gain stage with clear ICMR ownership.",
        constraints=(
            "No product-level polarity hacks",
            "Own the first high-gain node",
        ),
    ),
    BlockRole(
        name="gm_stage",
        required=True,
        role="Single second gain stage with one fixed responsibility.",
        constraints=(
            "Either final drive stage or pre-driver, but not both",
            "No mixed-role topology",
        ),
    ),
    BlockRole(
        name="freq_comp",
        required=True,
        role="Compensation only.",
        constraints=(
            "No DC stabilization hacks",
        ),
    ),
    BlockRole(
        name="frontend_az",
        required=True,
        role="Sample/store/apply auto-zero correction only.",
        constraints=(
            "Must not compensate for core defects",
            "Keep sampled-data behavior isolated from core static behavior",
        ),
    ),
    BlockRole(
        name="opamp_core",
        required=True,
        role="Compose the static analog amplifier path.",
        constraints=(
            "No phase logic",
            "No sampled-data behavior",
        ),
    ),
    BlockRole(
        name="opamp_az_top",
        required=True,
        role="Compose frontend_az and opamp_core into the product-level DUT.",
        constraints=(
            "Own top-level precision verification",
        ),
    ),
)

TEST_MATRIX: dict[str, tuple[str, ...]] = {
    "bias_gen": ("contract__startup", "char__current_accuracy"),
    "input_stage": ("contract__icmr", "char__gain_gmro"),
    "gm_stage": ("contract__swing", "char__load_drive", "char__gain_gmro"),
    "freq_comp": ("char__pole_zero_extract",),
    "frontend_az": ("contract__pedestal_zero_input", "contract__settling_in_phase_window"),
    "opamp_core": (
        "budget__open_loop_spec",
        "budget__output_spec",
        "budget__disabled_spec",
        "char__load_sweep",
        "pvt__open_loop_headroom",
        "pvt__output_compliance",
        "char__area_estimate",
    ),
    "opamp_az_top": (
        "budget__precision_ppa",
        "pvt__precision",
        "mc__residual_offset",
        "pex__precision_delta",
    ),
}
