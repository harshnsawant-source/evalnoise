"""The decision, and the words that explain it.

Three bars must all be cleared before a change counts as real: it must be bigger than
what chance produces at this churn level, bigger than the measured A/A difference, and
one-sided enough to fail a coin-toss test. Each bar exists because the other two can be
passed by accident, and every verdict carries the numbers that produced it, because a
verdict a user cannot check is a verdict they will learn to ignore.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    name: str
    reason: str
    exit_code: int


def decide(
    *,
    delta_ab: float,
    gains: int,
    losses: int,
    n: int,
    critical: float,
    noise_band: float | None,
    p_value: float,
    alpha: float = 0.05,
    min_items: int = 30,
    min_discordant: int = 10,
) -> Verdict:
    """Apply the rules of the spec, section 7."""
    discordant = gains + losses
    size = abs(delta_ab)

    if discordant == 0:
        return Verdict("INSIDE_NOISE", "no item changed outcome between the two runs", 1)
    if n < min_items:
        return Verdict(
            "INCONCLUSIVE",
            f"only {n} paired items; {min_items} are needed to decide anything",
            2,
        )
    if discordant < min_discordant:
        return Verdict(
            "INCONCLUSIVE",
            f"only {discordant} items changed; {min_discordant} are needed to test a direction",
            2,
        )

    uncalibrated = noise_band is None
    bars = [("detection threshold", critical)]
    if not uncalibrated:
        bars.append(("noise floor", noise_band))

    too_small = [name for name, bar in bars if size <= bar]
    if too_small:
        floors = " and ".join(f"{name} ({bar:.3f})" for name, bar in bars if name in too_small)
        return Verdict(
            "INSIDE_NOISE",
            f"the change ({size:.3f}) does not clear the {floors}",
            1,
        )
    if p_value >= alpha:
        return Verdict(
            "INSIDE_NOISE",
            f"the flips are balanced ({gains} gained, {losses} lost, p = {p_value:.2f})",
            1,
        )

    reason = (
        f"the change ({size:.3f}) clears every threshold and the flips are one-sided "
        f"({gains} gained, {losses} lost, p = {p_value:.4f})"
    )
    if uncalibrated:
        return Verdict(
            "UNCALIBRATED_REAL",
            reason + "; no A/A pair was supplied, so the noise floor is unmeasured",
            0,
        )
    return Verdict("REAL", reason, 0)
