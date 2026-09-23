"""Statistics over paired runs.

Every function here takes plain sequences of numbers and returns plain values: no
files, no configuration, no global state. That is what makes the decision procedure
testable without a filesystem, and it is why this module has no imports beyond the
standard library.

Booleans are numbers in Python, so binary outcomes (True/False) and numeric scores
flow through the same code; `epsilon` is what separates them: with epsilon = 0 any
difference counts as a change, which is what binary outcomes need.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb

Number = float | int | bool


def _check(baseline: Sequence[Number], variant: Sequence[Number]) -> None:
    if len(baseline) != len(variant):
        raise ValueError("baseline and variant must be the same length")
    if not baseline:
        raise ValueError("no paired items")


def delta(baseline: Sequence[Number], variant: Sequence[Number]) -> float:
    """Mean of the variant minus mean of the baseline."""
    _check(baseline, variant)
    n = len(baseline)
    return sum(variant) / n - sum(baseline) / n


def churn(
    baseline: Sequence[Number], variant: Sequence[Number], epsilon: float = 0.0
) -> tuple[int, float]:
    """How many items changed outcome, and what share of the total that is."""
    _check(baseline, variant)
    changed = sum(1 for b, v in zip(baseline, variant) if abs(v - b) > epsilon)
    return changed, changed / len(baseline)


def gains_losses(
    baseline: Sequence[Number], variant: Sequence[Number], epsilon: float = 0.0
) -> tuple[int, int]:
    """Items that improved, and items that worsened, counted separately.

    Reporting these apart is the point of the tool: 34 gains and 33 losses average out
    to nothing, and a mean cannot tell that apart from 67 items nobody touched.
    """
    _check(baseline, variant)
    gains = sum(1 for b, v in zip(baseline, variant) if v - b > epsilon)
    losses = sum(1 for b, v in zip(baseline, variant) if b - v > epsilon)
    return gains, losses


def mcnemar_exact(gains: int, losses: int) -> float:
    """Two-sided exact McNemar p-value: a binomial test on the discordant pairs.

    Concordant pairs carry no information about direction, so only the items that
    changed enter the test. Under the null each change was equally likely to go either
    way, so the count of gains is Binomial(gains + losses, 0.5).
    """
    n = gains + losses
    if n == 0:
        return 1.0
    k = min(gains, losses)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)
