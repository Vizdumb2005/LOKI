"""Integration tests proving consult_techniques() is wired into the live policy path (Job b).

Demonstrates that the mentalism technique dataset actively steers turn selection
and that changing technique availability alters session decisions.
"""

from pathlib import Path

from services.effects.loader import load_effects
from services.effects.techniques import (
    TechniqueDataset,
    load_techniques,
)
from services.policy.method_selection import (
    FishingState,
    MethodPolicyParams,
    select_turn,
)


def _uniform(effect):
    n = len(effect.hypotheses)
    return {hid: 1.0 / n for hid in effect.hypotheses}


def test_technique_consultation_steers_live_policy():
    """Prove that technique dataset consultation changes turn plan choice."""
    effects = load_effects(Path("configs/effects"))
    card_effect = effects["card_prediction"]
    uniform_posterior = _uniform(card_effect)

    # 1. With standard dataset: Cold Reading is recommended, so first turn is covert
    default_params = MethodPolicyParams()
    plan_default = select_turn(
        card_effect, uniform_posterior, set(), FishingState(), default_params
    )
    assert plan_default is not None
    assert plan_default.mode == "covert"

    # 2. With customized dataset where Cold Reading technique is removed:
    # select_turn must consult the dataset, see no Cold Reading recommendation,
    # and fall back to direct question mode.
    base_dataset = load_techniques()
    filtered_techniques = [
        t for t in base_dataset.techniques if "Cold Reading" not in t.name
    ]
    no_cold_reading_dataset = TechniqueDataset(techniques=filtered_techniques)

    custom_params = MethodPolicyParams(technique_dataset=no_cold_reading_dataset)
    plan_without_cold_reading = select_turn(
        card_effect, uniform_posterior, set(), FishingState(), custom_params
    )

    assert plan_without_cold_reading is not None
    assert plan_without_cold_reading.mode == "direct"
    assert plan_without_cold_reading.reason == "max_expected_information_gain"

    # Proves the wiring changes real session output
    assert plan_default.mode != plan_without_cold_reading.mode


def test_custom_technique_threshold_gates_fishing():
    """Prove that technique requirements gate covert selection."""
    effects = load_effects(Path("configs/effects"))
    card_effect = effects["card_prediction"]
    uniform_posterior = _uniform(card_effect)

    # Create a technique dataset with an empty technique list
    empty_dataset = TechniqueDataset(techniques=[])
    params = MethodPolicyParams(technique_dataset=empty_dataset)

    plan = select_turn(card_effect, uniform_posterior, set(), FishingState(), params)
    assert plan is not None
    assert plan.mode == "direct"
