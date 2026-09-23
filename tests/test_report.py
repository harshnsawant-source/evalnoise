import json

from evalnoise.load import Paired
from evalnoise.report import render_json, render_text
from evalnoise.verdict import analyse


def paired(baseline, variant):
    ids = [f"q{i}" for i in range(len(baseline))]
    return Paired(ids=ids, baseline=baseline, variant=variant,
                  unmatched_baseline=[], unmatched_variant=[])


def test_analysis_carries_every_number_the_verdict_used():
    ab = paired([1, 0] * 60, [1, 1] * 60)
    result = analyse(ab)
    assert result["schema_version"] == 1
    assert result["items"]["paired"] == 120
    assert set(result["change"]) >= {"delta", "churn_rate", "gains", "losses", "p_value",
                                     "critical", "ci_low", "ci_high"}
    assert result["verdict"]["name"] in {"REAL", "UNCALIBRATED_REAL", "INSIDE_NOISE", "INCONCLUSIVE"}


def test_analysis_includes_the_noise_floor_when_an_aa_pair_is_given():
    ab = paired([1, 0] * 60, [1, 1] * 60)
    aa = paired([1, 0] * 60, [0, 1] * 60)
    result = analyse(ab, aa)
    assert result["noise_floor"]["band"] > 0
    assert result["noise_floor"]["churn_rate"] > 0


def test_text_report_shows_the_verdict_and_its_reason():
    text = render_text(analyse(paired([1, 0] * 60, [1, 1] * 60)))
    assert "VERDICT" in text
    assert "gained" in text and "lost" in text


def test_json_report_is_machine_readable_and_complete():
    document = json.loads(render_json(analyse(paired([1, 0] * 60, [1, 1] * 60))))
    assert document["schema_version"] == 1
    assert "reason" in document["verdict"]


def test_report_is_ascii_so_it_survives_a_windows_console():
    #: A cp1252 console turns ± and — into replacement characters, which is what a
    #: Windows user saw in the very first run of this tool.
    ab = paired([1, 0] * 60, [1, 1] * 60)
    aa = paired([1, 0] * 60, [0, 1] * 60)
    text = render_text(analyse(ab, aa))
    text.encode("ascii")
