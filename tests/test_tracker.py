from __future__ import annotations

import pytest

from services.hypothesis.metrics import entropy, normalize
from services.hypothesis.tracker import Tracker


def test_uniform_52_entropy_is_log2_52():
    tracker = Tracker([f"h{i}" for i in range(52)])
    assert tracker.entropy() == pytest.approx(5.700439718141093)


def test_point_mass_has_zero_entropy():
    tracker = Tracker(["a", "b", "c"], prior={"a": 0.0, "b": 1.0, "c": 0.0})
    assert tracker.entropy() == pytest.approx(0.0)


def test_bayesian_update_matches_hand_computation():
    tracker = Tracker(["a", "b"])
    # P(e|a) = 0.9, P(e|b) = 0.1  ->  P(a|e) = 0.9
    tracker.update({"a": 0.9, "b": 0.1})
    posterior = tracker.posterior
    assert posterior["a"] == pytest.approx(0.9)
    assert posterior["b"] == pytest.approx(0.1)


def test_update_normalizes_posterior():
    tracker = Tracker(["a", "b", "c"], prior={"a": 2.0, "b": 1.0, "c": 1.0})
    tracker.update({"a": 1.0, "b": 1.0, "c": 0.0})
    assert sum(tracker.posterior.values()) == pytest.approx(1.0)
    assert tracker.posterior["a"] == pytest.approx(2 / 3)


def test_all_zero_likelihoods_rejected():
    tracker = Tracker(["a", "b"])
    with pytest.raises(ValueError, match="eliminated every hypothesis"):
        tracker.update({"a": 0.0, "b": 0.0})


def test_missing_likelihood_vector_rejected():
    tracker = Tracker(["a", "b", "c"])
    with pytest.raises(ValueError, match="missing hypotheses"):
        tracker.update({"a": 1.0, "b": 1.0})


def test_prior_validation():
    with pytest.raises(ValueError, match="unknown hypotheses"):
        Tracker(["a"], prior={"z": 1.0})
    with pytest.raises(ValueError, match="missing hypotheses"):
        Tracker(["a", "b"], prior={"a": 1.0})
    with pytest.raises(ValueError):
        Tracker(["a", "b"], prior={"a": -1.0, "b": 2.0})


def test_map_and_top_k_deterministic_tiebreak():
    tracker = Tracker(["b", "a"])  # uniform: ids break the tie in sorted order
    hid, p = tracker.map_hypothesis()
    assert (hid, p) == ("a", pytest.approx(0.5))
    assert [h for h, _ in tracker.top_k(2)] == ["a", "b"]


def test_normalize_rejects_non_positive():
    with pytest.raises(ValueError):
        normalize({"a": 0.0, "b": 0.0})
    with pytest.raises(ValueError):
        normalize({"a": -1.0, "b": 2.0})


def test_entropy_of_two_way_split():
    assert entropy({"a": 0.5, "b": 0.5}) == pytest.approx(1.0)
