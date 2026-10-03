from __future__ import annotations

from services.language import renderer as templates
from services.language.renderer import LanguageRenderer

RENDERER = LanguageRenderer()


def test_deterministic_for_same_inputs():
    assert RENDERER.ask("Is it red?", "session-1", 1) == RENDERER.ask("Is it red?", "session-1", 1)
    assert RENDERER.reveal("Ace of Spades", 0.97, "session-1") == RENDERER.reveal(
        "Ace of Spades", 0.97, "session-1"
    )


def test_ask_includes_question_text():
    line = RENDERER.ask("Is your card red, or black?", "s", 2)
    assert "Is your card red, or black?" in line


def test_confidence_bands_select_distinct_templates():
    """Low-confidence reveals must never borrow dramatic phrasing (calibration rule)."""
    high = RENDERER.reveal("the two of clubs", 0.97, "s")
    measured = RENDERER.reveal("the two of clubs", 0.70, "s")
    hedged = RENDERER.reveal("the two of clubs", 0.50, "s")
    forced = RENDERER.reveal("the two of clubs", 0.20, "s")

    def band_of(message: str) -> set[str]:
        bands = {
            "high": templates.REVEAL_HIGH,
            "measured": templates.REVEAL_MEASURED,
            "hedged": templates.REVEAL_HEDGED,
            "forced": templates.REVEAL_FORCED,
        }
        found = {
            name
            for name, band in bands.items()
            if message in {t.format(label="the two of clubs") for t in band}
        }
        assert found, f"message not from any band: {message}"
        return found

    assert band_of(high) == {"high"}
    assert band_of(measured) == {"measured"}
    assert band_of(hedged) == {"hedged"}
    assert band_of(forced) == {"forced"}


def test_outcome_lines_exist_for_both_branches():
    assert RENDERER.outcome(True, 4, "s")
    assert RENDERER.outcome(False, 7, "s")
