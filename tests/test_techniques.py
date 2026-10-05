"""Tests for the machine-readable mentalism technique dataset (§16)."""

from services.effects.techniques import (
    Technique,
    TechniqueDataset,
    consult_techniques,
    load_techniques,
)


def test_load_mentalism_techniques():
    dataset = load_techniques()
    assert isinstance(dataset, TechniqueDataset)
    assert len(dataset.techniques) >= 10

    for tech in dataset.techniques:
        assert isinstance(tech, Technique)
        assert tech.name
        assert tech.mechanism
        assert tech.required_information
        assert tech.visible_participant_action
        assert tech.hidden_system_state
        assert tech.confidence_requirements
        assert isinstance(tech.failure_modes, list)
        assert len(tech.failure_modes) >= 1
        assert tech.psychological_basis
        assert tech.digital_translation
        assert tech.measurable_effect


def test_get_by_name():
    dataset = load_techniques()
    tech = dataset.get_by_name("Barnum")
    assert tech is not None
    assert "Barnum" in tech.name

    tech_none = dataset.get_by_name("NonexistentTechnique123")
    assert tech_none is None


def test_consult_techniques():
    # Early turn low top-mass
    recs = consult_techniques(top_mass=0.25, turn_count=1, max_turns=10, has_covert_ration=True)
    names = [r["technique"] for r in recs]
    assert any("Barnum" in n for n in names)

    # Dominant favorite with high top-mass
    recs_high = consult_techniques(
        top_mass=0.70, turn_count=3, max_turns=10, has_covert_ration=True
    )
    names_high = [r["technique"] for r in recs_high]
    assert any("Priming" in n or "Choice Architecture" in n for n in names_high)
    assert any("Cold Reading" in n for n in names_high)
