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

import random
from collections.abc import Sequence
from math import comb

DEFAULT_SEED = 20260923
DEFAULT_RESAMPLES = 10_000

Number = float | int | bool


def _check(baseline: Sequence[Number], variant: Sequence[Number]) -> None:
    if len(baseline) != len(variant):
        raise ValueError("baseline and variant must be the same length")
    if not baseline:
        raise ValueError("no paired items")


def effective_diffs(
    baseline: Sequence[Number], variant: Sequence[Number], epsilon: float = 0.0
) -> list[float]:
    """Per-item movement, with anything at or below `epsilon` treated as no movement.

    Every statistic in this module is built on this list, which is the only way they can
    agree. An earlier version applied epsilon to churn, to gains and losses, and to the
    permutation null, but not to the delta: a hundred items each improving by 0.04 under
    an epsilon of 0.05 then reported "+4.0 points" and "no item changed outcome" in the
    same breath, and the detection threshold was computed from a different set of items
    than the delta it was compared against.
    """
    if epsilon < 0:
        raise ValueError("epsilon must not be negative")
    _check(baseline, variant)
    return [(v - b) if abs(v - b) > epsilon else 0.0 for b, v in zip(baseline, variant)]


def delta(
    baseline: Sequence[Number], variant: Sequence[Number], epsilon: float = 0.0
) -> float:
    """Mean movement from baseline to variant, ignoring moves within epsilon."""
    diffs = effective_diffs(baseline, variant, epsilon)
    return sum(diffs) / len(diffs)


def churn(
    baseline: Sequence[Number], variant: Sequence[Number], epsilon: float = 0.0
) -> tuple[int, float]:
    """How many items changed outcome, and what share of the total that is."""
    diffs = effective_diffs(baseline, variant, epsilon)
    changed = sum(1 for d in diffs if d != 0.0)
    return changed, changed / len(diffs)


def gains_losses(
    baseline: Sequence[Number], variant: Sequence[Number], epsilon: float = 0.0
) -> tuple[int, int]:
    """Items that improved, and items that worsened, counted separately.

    Reporting these apart is the point of the tool: 34 gains and 33 losses average out
    to nothing, and a mean cannot tell that apart from 67 items nobody touched.
    """
    diffs = effective_diffs(baseline, variant, epsilon)
    return sum(1 for d in diffs if d > 0), sum(1 for d in diffs if d < 0)


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


def permutation_critical(
    baseline: Sequence[Number],
    variant: Sequence[Number],
    *,
    epsilon: float = 0.0,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    alpha: float = 0.05,
) -> float:
    """The largest swing this setup produces by chance alone.

    Under the null the change had no direction, so each item that moved was equally
    likely to have moved the other way. Flipping each changed item's direction at
    random, many times, gives the distribution of deltas a setup with this much churn
    produces from nothing. The returned value is that distribution's (1 - alpha)
    quantile of |delta|: an effect smaller than this is not distinguishable from churn.
    """
    moves = [d for d in effective_diffs(baseline, variant, epsilon) if d != 0.0]
    if not moves:
        return 0.0
    n = len(baseline)
    rng = random.Random(seed)
    swings = []
    for _ in range(resamples):
        total = sum(m if rng.random() < 0.5 else -m for m in moves)
        swings.append(abs(total) / n)
    swings.sort()
    index = min(len(swings) - 1, int(round((1 - alpha) * (len(swings) - 1))))
    return swings[index]


def bootstrap_ci(
    baseline: Sequence[Number],
    variant: Sequence[Number],
    *,
    epsilon: float = 0.0,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Percentile interval for the delta, resampling items in pairs.

    Items are resampled as pairs rather than independently, because the two runs saw
    the same items; pairing is what removes the item-difficulty variance that would
    otherwise swamp the effect.
    """
    diffs = effective_diffs(baseline, variant, epsilon)
    n = len(diffs)
    rng = random.Random(seed)
    means = []
    for _ in range(resamples):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    tail = (1 - confidence) / 2
    low = means[int(round(tail * (len(means) - 1)))]
    high = means[int(round((1 - tail) * (len(means) - 1)))]
    return low, high
