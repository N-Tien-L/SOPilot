from __future__ import annotations

import pytest

from sopilot_eval.agreement import SCALES, agreement, bootstrap_ci, cohens_kappa

S = SCALES["correctness"]


def test_identical_labels_give_kappa_one() -> None:
    labels = ["correct", "wrong", "partial", "correct", "wrong"]
    assert cohens_kappa(labels, labels, S) == pytest.approx(1.0)
    assert cohens_kappa(labels, labels, S, weighted=True) == pytest.approx(1.0)


def test_kappa_matches_a_hand_computed_case() -> None:
    a = ["correct", "correct", "correct", "wrong", "wrong"]
    b = ["correct", "correct", "wrong", "wrong", "wrong"]
    # po = 0.8; pe = 0.6 * 0.4 + 0.4 * 0.6 = 0.48; kappa = (0.8 - 0.48) / (1 - 0.48)
    assert cohens_kappa(a, b, S) == pytest.approx(0.32 / 0.52)


def test_agreeing_by_chance_only_gives_a_kappa_near_zero_or_below() -> None:
    a = ["correct", "wrong"] * 5
    b = ["correct", "correct", "wrong", "wrong", "correct", "correct", "wrong", "wrong", "correct", "correct"]
    assert cohens_kappa(a, b, S) <= 0.05


def test_a_partial_against_wrong_hurts_less_than_correct_against_wrong_when_weighted() -> None:
    base = ["correct", "wrong", "correct", "wrong"]
    near = ["correct", "wrong", "correct", "partial"]
    far = ["correct", "wrong", "correct", "correct"]
    assert cohens_kappa(base, near, S, weighted=True) > cohens_kappa(base, far, S, weighted=True)


def test_a_grader_who_always_says_the_same_label_has_undefined_kappa() -> None:
    assert cohens_kappa(["correct"] * 4, ["correct"] * 4, S) is None


def test_the_bootstrap_interval_is_fixed_by_the_seed_and_contains_the_estimate() -> None:
    a = ["correct", "wrong", "partial", "correct", "wrong", "correct", "partial", "wrong"] * 3
    b = list(a)
    b[0], b[5], b[9] = "wrong", "wrong", "correct"
    lo, hi = bootstrap_ci(a, b, S)
    assert (lo, hi) == bootstrap_ci(a, b, S)
    assert lo <= cohens_kappa(a, b, S) <= hi


def test_the_report_carries_the_confusion_counts() -> None:
    report = agreement(["correct", "wrong", "wrong"], ["correct", "wrong", "partial"], S)
    assert report["n"] == 3 and report["exact_agreement"] == pytest.approx(2 / 3)
    assert report["confusion"] == {"correct|correct": 1, "wrong|partial": 1, "wrong|wrong": 1}


def test_mismatched_lengths_are_refused() -> None:
    with pytest.raises(ValueError):
        cohens_kappa(["correct"], ["correct", "wrong"], S)
