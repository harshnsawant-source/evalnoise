"""The tool against a published run, where the answer is already known.

Source: still-holds, finding cot_unfaithfulness_suggested, qwen2.5:3b-instruct.
A suggested answer was planted in the user's turn. The accuracy metric moved +5.4
points, upward, while 97 of 240 answers flipped. The verdict must be INSIDE_NOISE:
that is the whole argument for this tool, so it is a test.
"""

import pytest

from evalnoise.load import load_run, pair
from evalnoise.verdict import analyse

FIXTURES = "tests/fixtures"


@pytest.fixture(scope="module")
def analysis():
    baseline = load_run(f"{FIXTURES}/qwen_unbiased.jsonl")
    variant = load_run(f"{FIXTURES}/qwen_biased.jsonl")
    return analyse(pair(baseline, variant))


def test_reproduces_the_published_numbers(analysis):
    assert analysis["items"]["paired"] == 240
    assert analysis["change"]["churn_count"] == 97
    assert analysis["change"]["gains"] == 55
    assert analysis["change"]["losses"] == 42
    assert analysis["change"]["delta"] == pytest.approx(0.0542, abs=0.0005)
    assert analysis["change"]["churn_rate"] == pytest.approx(0.404, abs=0.001)


def test_the_positive_delta_does_not_survive_the_verdict(analysis):
    #: No A/A pair exists for this published run, so only the detection threshold and the
    #: balance of flips are available to judge it — and the change clears neither.
    assert analysis["verdict"]["name"] == "INSIDE_NOISE"
    assert analysis["change"]["p_value"] > 0.05
