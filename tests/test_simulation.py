"""What the tool promises, tested against data whose truth we set.

A verdict procedure cannot be checked by eye: it has to be run many times against
runs with a known effect and known churn. These two tests are the product claim —
a null change is called noise almost always, and a large real change is caught —
and they are why the thresholds in verdict.py can be trusted.
"""

import random

from evalnoise.load import Paired
from evalnoise.verdict import analyse


def simulate(n, churn_rate, true_effect, seed, base_rate=0.6):
    """Paired runs with a known amount of churn and a known effect on top of it.

    Churn has to be UNBIASED or the test is worthless. Flipping every item with the same
    probability is not: on a run that is 60% correct, more correct answers are available
    to break than wrong ones to fix, so a 40% flip rate drags the mean down about 8
    points and the "null" data carries a real effect. An earlier version did exactly
    that, and the resulting false-positive rate of 42% was the tool correctly finding an
    effect the generator had put there. So zeros and ones are flipped at different rates,
    chosen to make gains and losses equal in expectation.

    `true_effect` is the probability that the change rescues an item that would otherwise
    be wrong, so it moves the delta by roughly `true_effect` times the share of items
    sitting at 0 after churn. Applying it to every item instead would waste most of it:
    setting an already-correct item to 1 changes nothing.
    """
    rng = random.Random(seed)
    #: Equal expected gains and losses: P(0) * flip_zero == P(1) * flip_one == churn / 2.
    flip_zero = churn_rate / (2 * (1 - base_rate))
    flip_one = churn_rate / (2 * base_rate)
    baseline, variant = [], []
    for _ in range(n):
        base = 1 if rng.random() < base_rate else 0
        value = base
        if rng.random() < (flip_one if base == 1 else flip_zero):
            value = 1 - base
        if value == 0 and rng.random() < true_effect:
            value = 1
        baseline.append(base)
        variant.append(value)
    ids = [f"q{i}" for i in range(n)]
    return Paired(ids=ids, baseline=baseline, variant=variant, kind="binary",
                  unmatched_baseline=[], unmatched_variant=[])


def test_a_null_change_at_high_churn_is_called_noise_at_least_95_percent_of_the_time():
    false_positives = 0
    trials = 40
    for seed in range(trials):
        ab = simulate(240, churn_rate=0.40, true_effect=0.0, seed=seed)
        aa = simulate(240, churn_rate=0.40, true_effect=0.0, seed=1000 + seed)
        if analyse(ab, aa)["verdict"]["name"].endswith("REAL"):
            false_positives += 1
    assert false_positives <= trials * 0.05


def test_a_large_real_effect_is_caught_at_least_80_percent_of_the_time():
    #: 0.5 here is a delta of about 24 points, roughly twice the binding bar at this
    #: churn level (the A/A noise band runs 10 to 12 points on 240 items).
    caught = 0
    trials = 40
    for seed in range(trials):
        ab = simulate(240, churn_rate=0.40, true_effect=0.50, seed=seed)
        aa = simulate(240, churn_rate=0.40, true_effect=0.0, seed=1000 + seed)
        if analyse(ab, aa)["verdict"]["name"].endswith("REAL"):
            caught += 1
    assert caught >= trials * 0.80
