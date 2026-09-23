import pytest

from evalnoise import stats


def test_delta_is_the_difference_of_means():
    baseline = [1, 0, 1, 0]
    variant = [1, 1, 1, 0]
    assert stats.delta(baseline, variant) == pytest.approx(0.25)


def test_delta_is_zero_when_runs_match():
    assert stats.delta([1, 0, 1], [1, 0, 1]) == 0.0


def test_churn_counts_items_whose_outcome_changed():
    changed, rate = stats.churn([1, 0, 1, 0], [1, 1, 1, 0])
    assert changed == 1
    assert rate == pytest.approx(0.25)


def test_churn_ignores_numeric_moves_within_epsilon():
    changed, rate = stats.churn([0.50, 0.50], [0.52, 0.90], epsilon=0.05)
    assert changed == 1
    assert rate == pytest.approx(0.5)


def test_statistics_reject_runs_of_different_length():
    with pytest.raises(ValueError, match="same length"):
        stats.delta([1, 0], [1])
