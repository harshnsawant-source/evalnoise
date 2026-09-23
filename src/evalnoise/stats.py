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
