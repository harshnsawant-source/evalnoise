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


def test_gains_and_losses_are_counted_separately():
    baseline = [1, 1, 0, 0]
    variant = [0, 1, 1, 0]
    gains, losses = stats.gains_losses(baseline, variant)
    assert (gains, losses) == (1, 1)


def test_balanced_flips_are_not_significant():
    #: 34 gains against 33 losses is what a coin does.
    assert stats.mcnemar_exact(34, 33) > 0.5


def test_one_sided_flips_are_significant():
    #: 20 changes, all in one direction: 2 * 0.5**20, far below any threshold.
    assert stats.mcnemar_exact(20, 0) == pytest.approx(2 * 0.5 ** 20)


def test_no_discordant_pairs_gives_p_of_one():
    assert stats.mcnemar_exact(0, 0) == 1.0


def test_mcnemar_is_symmetric():
    assert stats.mcnemar_exact(12, 3) == stats.mcnemar_exact(3, 12)
