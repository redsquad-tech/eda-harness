from dataclasses import dataclass


@dataclass(frozen=True)
class BlockRole:
    name: str
    required: bool
    role: str
    constraints: tuple[str, ...]


ARCHITECTURE_EXPERIMENT = "opamp_v3_clean_loop_redesign"

DESIGN_RULES: tuple[str, ...] = (
    "Keep the PMOS-input first stage unless a replacement clearly beats it on TT and reduced decision corners.",
    "Use an explicitly non-inverting final output path.",
    "Treat disable leakage as a first-class architecture constraint.",
    "Do not rely on local node clamps as the primary shutdown mechanism once repeated experiments show they increase off-state current.",
    "Prefer shutdown-aware topology changes over retrofitted shutdown patches when the enabled loop is already nominally healthy.",
    "Do not reintroduce hidden current-to-voltage bias adapters inside the core loop.",
    "Do not push AZ-specific fixes into the static core.",
)

BLOCK_ROLES: tuple[BlockRole, ...] = (
    BlockRole(
        name="opamp_core",
        required=True,
        role="Static amplifier loop with explicit gain partition and explicit non-inverting output path.",
        constraints=(
            "No sampled-data behavior",
            "No output-stage polarity surprises",
            "Shutdown strategy must be structural, not only clamp-based",
        ),
    ),
    BlockRole(
        name="frontend_az",
        required=True,
        role="Sample/store/apply auto-zero correction around the core.",
        constraints=(
            "Must not repair core defects",
            "Keep interface explicit and minimal",
        ),
    ),
    BlockRole(
        name="opamp_az_top",
        required=True,
        role="Compose the static core and AZ front end into the product-level DUT.",
        constraints=(
            "Own top-level precision verification",
        ),
    ),
)

TEST_MATRIX: dict[str, tuple[str, ...]] = {
    "opamp_core": (
        "smoke__package",
        "budget__tt_nominal",
        "char__decision_corners",
        "char__disable_nodes",
    ),
    "frontend_az": (
        "smoke__package",
    ),
    "opamp_az_top": (
        "smoke__package",
        "budget__precision_tt",
    ),
}

NEXT_REVISION_FOCUS: tuple[str, ...] = (
    "Preserve the current v3 enabled-loop baseline that closes minimum nominal AC/current goals.",
    "Stop local shutdown-clamp exploration on the current loop; experiments 36-39 show non-convergence.",
    "Introduce a shutdown-aware first-stage current-path revision instead of more gate/node forcing.",
    "Re-run worst disable corner before reopening broader PVT or AZ work.",
)
