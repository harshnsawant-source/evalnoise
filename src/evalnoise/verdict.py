"""The decision, and the words that explain it.

Three bars must all be cleared before a change counts as real: it must be bigger than
what chance produces at this churn level, bigger than the measured A/A difference, and
one-sided enough to fail a coin-toss test. Each bar exists because the other two can be
passed by accident, and every verdict carries the numbers that produced it, because a
verdict a user cannot check is a verdict they will learn to ignore.
"""

from __future__ import annotations

from dataclasses import dataclass

from evalnoise import stats
from evalnoise.load import Paired

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Verdict:
    name: str
    reason: str
    exit_code: int


def _fmt(value: float, scale: float, unit: str) -> str:
    """The same number, in the same units, as the report prints above the verdict."""
    return f"{value * scale:.1f}{unit}" if unit else f"{value * scale:.3f}"


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
    scale: float = 1.0,
    unit: str = "",
    uncalibrated_reason: str = "no A/A pair was supplied, so the noise floor is unmeasured",
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
        floors = " and ".join(
            f"{name} ({_fmt(bar, scale, unit)})" for name, bar in bars if name in too_small
        )
        return _label(
            "INSIDE_NOISE",
            f"the change ({_fmt(size, scale, unit)}) does not clear the {floors}",
            1,
            uncalibrated,
            uncalibrated_reason,
        )
    if p_value >= alpha:
        return _label(
            "INSIDE_NOISE",
            f"the flips are balanced ({gains} gained, {losses} lost, p = {p_value:.2f})",
            1,
            uncalibrated,
            uncalibrated_reason,
        )

    reason = (
        f"the change ({_fmt(size, scale, unit)}) clears every threshold and the flips are "
        f"one-sided ({gains} gained, {losses} lost, p = {p_value:.4f})"
    )
    return _label("REAL", reason, 0, uncalibrated, uncalibrated_reason)


def _label(name: str, reason: str, exit_code: int, uncalibrated: bool, why: str) -> Verdict:
    """Mark every verdict that rests on an unmeasured noise floor, not only the good news.

    An unprefixed INSIDE_NOISE claims the change is inside *your* setup's noise when no
    noise was measured, which the spec and the README both say it must not do.
    """
    if uncalibrated:
        return Verdict(f"UNCALIBRATED_{name}", f"{reason}; {why}", exit_code)
    return Verdict(name, reason, exit_code)


def _summarise(p: Paired, *, epsilon: float, seed: int, alpha: float) -> dict:
    changed, rate = stats.churn(p.baseline, p.variant, epsilon)
    gains, losses = stats.gains_losses(p.baseline, p.variant, epsilon)
    low, high = stats.bootstrap_ci(p.baseline, p.variant, epsilon=epsilon, seed=seed)
    return {
        "paired": len(p.ids),
        "unmatched": len(p.unmatched_baseline) + len(p.unmatched_variant),
        "delta": stats.delta(p.baseline, p.variant, epsilon),
        "churn_count": changed,
        "churn_rate": rate,
        "gains": gains,
        "losses": losses,
        "ci_low": low,
        "ci_high": high,
        #: For binary outcomes this is McNemar's exact test. For numeric outcomes the same
        #: computation is the sign test over items that improved or worsened, which asks the
        #: question that matters here: did the change push in a direction, or scatter?
        "p_value": stats.mcnemar_exact(gains, losses),
        "critical": stats.permutation_critical(
            p.baseline, p.variant, epsilon=epsilon, seed=seed, alpha=alpha
        ),
    }


def analyse(
    paired_ab: Paired,
    paired_aa: Paired | None = None,
    *,
    epsilon: float = 0.0,
    seed: int = stats.DEFAULT_SEED,
    alpha: float = 0.05,
) -> dict:
    """Everything the verdict rests on, in one serialisable document."""
    change = _summarise(paired_ab, epsilon=epsilon, seed=seed, alpha=alpha)
    #: Binary outcomes are shares, so they read as percentage points. A numeric score sits
    #: on whatever scale its harness used, and multiplying a 1-to-5 judge score by 100
    #: turns a +0.3 improvement into "+30.0 points".
    scale, unit = (100.0, " points") if paired_ab.kind == "binary" else (1.0, "")
    noise = None
    uncalibrated_reason = "no A/A pair was supplied, so the noise floor is unmeasured"
    if paired_aa is not None:
        aa = _summarise(paired_aa, epsilon=epsilon, seed=seed, alpha=alpha)
        #: The band is the upper bound of the A/A difference's interval, not the point
        #: estimate: one A/A run measures the floor with error, and a bar set at the point
        #: estimate would be too low half the time. Measured on simulated runs, this choice
        #: gives a false-positive rate of 0% against 2.5% for the point estimate, at the
        #: same power.
        aa["band"] = max(abs(aa["ci_low"]), abs(aa["ci_high"]))
        noise = aa
        if aa["churn_count"] == 0:
            #: An A/A pair that flipped nothing measures no floor: its band is zero, so
            #: the bar it sets can never bind. A deterministic pipeline produces exactly
            #: this, and the honest answer is that the run is still uncalibrated.
            noise = dict(aa, band=None)
            uncalibrated_reason = (
                "the A/A pair showed no difference at all, so it measures no noise "
                "floor; use a placebo change such as reordering the options"
            )
    decision = decide(
        delta_ab=change["delta"],
        gains=change["gains"],
        losses=change["losses"],
        n=len(paired_ab.ids),
        critical=change["critical"],
        noise_band=None if noise is None else noise["band"],
        p_value=change["p_value"],
        alpha=alpha,
        scale=scale,
        unit=unit,
        uncalibrated_reason=uncalibrated_reason,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "items": {
            "paired": len(paired_ab.ids),
            "kind": paired_ab.kind,
            "unmatched_baseline": len(paired_ab.unmatched_baseline),
            "unmatched_variant": len(paired_ab.unmatched_variant),
            #: Counts alone leave a user staring at "(1920 unmatched)" with no way to see
            #: that the two harnesses wrote ids as task:1 and task:0001.
            "example_unmatched_baseline": paired_ab.unmatched_baseline[:3],
            "example_unmatched_variant": paired_ab.unmatched_variant[:3],
        },
        "units": {"scale": scale, "unit": unit.strip() or None},
        "change": change,
        "noise_floor": noise,
        "verdict": {
            "name": decision.name,
            "reason": decision.reason,
            "exit_code": decision.exit_code,
        },
        "config": {
            "epsilon": epsilon,
            "seed": seed,
            "alpha": alpha,
            "resamples": stats.DEFAULT_RESAMPLES,
        },
    }
