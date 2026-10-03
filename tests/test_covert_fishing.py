"""Unit tests for Covert Fishing, Signal Extractor, and Method Policy."""

from __future__ import annotations

from services.language.renderer import LanguageRenderer
from services.language.signal_extractor import AgreementSignal, extract_agreement_signal
from services.policy.method_selector import MentalistMethod, select_method


def test_covert_fishing_renderer():
    renderer = LanguageRenderer("test_seed")
    rendered = renderer.covert_fish("they are an artist or performer", "session123", 1)
    assert "artist or performer" in rendered
    assert isinstance(rendered, str)


def test_extract_agreement_signal():
    assert extract_agreement_signal(None, "yes") == AgreementSignal.STRONG_YES
    assert extract_agreement_signal("Well kind of", "yes") == AgreementSignal.WEAK_YES
    assert extract_agreement_signal("Not really", "no") == AgreementSignal.WEAK_NO
    assert extract_agreement_signal("No way, wrong!", "no") == AgreementSignal.STRONG_NO
    assert extract_agreement_signal("Spot on!", None) == AgreementSignal.STRONG_YES
    assert extract_agreement_signal("Random chatter", None) == AgreementSignal.NEUTRAL


def test_select_method():
    # High confidence -> Direct Inference
    assert select_method(1.0, 0.75, 10, 1) == MentalistMethod.DIRECT_INFERENCE

    # Gaze observation boost -> Direct Inference
    assert (
        select_method(1.5, 0.58, 10, 2, has_gaze_observation=True)
        == MentalistMethod.DIRECT_INFERENCE
    )

    # Turn 1 with forcing -> Choice Forcing
    assert select_method(3.0, 0.20, 10, 1, forcing_eligible=True) == MentalistMethod.CHOICE_FORCING

    # High entropy -> Covert Fishing
    assert select_method(2.5, 0.30, 10, 2) == MentalistMethod.COVERT_FISHING

    # Low entropy -> Progressive Narrowing
    assert select_method(0.5, 0.50, 10, 3) == MentalistMethod.PROGRESSIVE_NARROWING
