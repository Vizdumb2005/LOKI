"""Machine-Readable Mentalism Technique Dataset Loader and Policy Consultant (Directive §16).

Loads and validates datasets/mentalism_techniques.yaml and provides policy consulting
functions to select mentalism methods matching session confidence and state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

DEFAULT_DATASET_PATH = Path(__file__).parents[2] / "datasets" / "mentalism_techniques.yaml"


class Technique(BaseModel):
    name: str
    mechanism: str
    required_information: str
    visible_participant_action: str
    hidden_system_state: str
    confidence_requirements: str
    failure_modes: list[str] = Field(default_factory=list)
    psychological_basis: str
    digital_translation: str
    measurable_effect: str


class TechniqueDataset(BaseModel):
    techniques: list[Technique]

    def get_by_name(self, name: str) -> Technique | None:
        name_lower = name.lower()
        for t in self.techniques:
            if name_lower in t.name.lower():
                return t
        return None


_CACHED_DATASET: TechniqueDataset | None = None


def load_techniques(path: Path | str | None = None) -> TechniqueDataset:
    """Load and validate the mentalism technique dataset."""
    global _CACHED_DATASET
    if path is None and _CACHED_DATASET is not None:
        return _CACHED_DATASET

    dataset_path = Path(path) if path else DEFAULT_DATASET_PATH
    if not dataset_path.exists():
        raise FileNotFoundError(f"Mentalism technique dataset not found at {dataset_path}")

    raw_data = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    dataset = TechniqueDataset.model_validate(raw_data)

    if path is None:
        _CACHED_DATASET = dataset
    return dataset


def consult_techniques(
    top_mass: float,
    turn_count: int,
    max_turns: int,
    has_covert_ration: bool = True,
    has_passive_signals: bool = False,
    dataset: TechniqueDataset | None = None,
) -> list[dict[str, Any]]:
    """Consult the technique dataset to recommend applicable techniques for the session context."""
    ds = dataset or load_techniques()
    recommendations = []

    for tech in ds.techniques:
        applicable = False
        reason = ""

        if "Barnum" in tech.name and top_mass < 0.45 and turn_count <= 2:
            applicable = True
            reason = "Low top-mass in early turn; character priming recommended."
        elif "Priming" in tech.name and top_mass >= 0.60:
            applicable = True
            reason = "Dominant favorite identified; choice architecture emphasis eligible."
        elif "Cold Reading" in tech.name and top_mass >= 0.40 and has_covert_ration:
            applicable = True
            reason = "Credible candidate identified with covert turn ration available."
        elif "Causality" in tech.name and has_passive_signals:
            applicable = True
            reason = "Passive telemetry channels available for causality attribution."
        elif "Multiple Outs" in tech.name and turn_count >= max_turns - 2:
            applicable = True
            reason = "Approaching termination; multi-branch reveal planning recommended."
        elif "Hesitation" in tech.name and 0.60 <= top_mass <= 0.85:
            applicable = True
            reason = "Top mass inside calibrated doubt window (0.60-0.85)."
        elif "Entropy" in tech.name and top_mass < 0.80:
            applicable = True
            reason = "High entropy remaining; maximum information gain query recommended."

        if applicable:
            recommendations.append(
                {
                    "technique": tech.name,
                    "reason": reason,
                    "confidence_req": tech.confidence_requirements,
                    "digital_translation": tech.digital_translation,
                }
            )

    return recommendations
