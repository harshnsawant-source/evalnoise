"""One test per finding from the branch review.

Each of these failed before the fix that follows it, which is the only proof the
finding was real and is now gone.
"""

import json
import math

import pytest

from evalnoise.cli import main
from evalnoise.load import LoadError, load_run, pair
from evalnoise.report import render_text
from evalnoise.verdict import analyse, decide


def write(tmp_path, name, rows):
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def paired_scores(baseline, variant, kind="numeric"):
    from evalnoise.load import Paired

    ids = [f"q{i}" for i in range(len(baseline))]
    return Paired(ids=ids, baseline=baseline, variant=variant, kind=kind,
                  unmatched_baseline=[], unmatched_variant=[])


# --- Finding 1: epsilon filtered churn but not delta ------------------------------


def test_moves_inside_epsilon_do_not_count_toward_the_delta():
    #: 100 items each improving by 0.04 with epsilon 0.05 is "nothing changed", so the
    #: delta must be 0 too. Reporting +4.0 points beside "no item changed" is the
    #: report contradicting itself.
    ab = paired_scores([0.50] * 100, [0.54] * 100)
    result = analyse(ab, epsilon=0.05)
    assert result["change"]["delta"] == 0.0
    assert result["change"]["churn_count"] == 0
    assert result["verdict"]["name"].endswith("INSIDE_NOISE")


# --- Finding 2: the null was built on a different item set than the delta ---------


def test_the_null_and_the_delta_are_built_from_the_same_items():
    #: 10 items move by +0.5 and 90 by +0.09, with epsilon 0.1. The small moves are
    #: excluded from the change, so they must be excluded from the delta as well;
    #: otherwise the threshold is computed from a tenth of the effect it judges.
    ab = paired_scores([0.0] * 100, [0.5] * 10 + [0.09] * 90)
    result = analyse(ab, epsilon=0.1)
    assert result["change"]["delta"] == pytest.approx(0.05, abs=1e-9)


# --- Finding 3: the A/A pair's unmatched ids vanished -----------------------------


def test_the_noise_floor_reports_how_many_items_it_was_measured_on(tmp_path):
    a = write(tmp_path, "a.jsonl", [{"id": f"q{i}", "correct": i % 2 == 0} for i in range(200)])
    b = write(tmp_path, "b.jsonl", [{"id": f"q{i}", "correct": True} for i in range(200)])
    aa = write(tmp_path, "aa.jsonl", [{"id": f"q{i}", "correct": i % 3 == 0} for i in range(50, 260)])
    baseline, variant, second = load_run(a), load_run(b), load_run(aa)
    result = analyse(pair(baseline, variant), pair(baseline, second))
    assert result["noise_floor"]["paired"] == 150
    assert result["noise_floor"]["unmatched"] == 110
    text = render_text(result)
    assert "150" in text


# --- Finding 4: infinities were accepted as scores --------------------------------


def test_an_infinite_score_is_refused(tmp_path):
    p = tmp_path / "a.jsonl"
    p.write_text('{"id": "q1", "score": Infinity}\n', encoding="utf-8")
    with pytest.raises(LoadError, match="q1"):
        load_run(p)


# --- Finding 5: epsilon and alpha were unvalidated --------------------------------


def test_a_negative_epsilon_is_refused(tmp_path):
    a = write(tmp_path, "a.jsonl", [{"id": f"q{i}", "correct": True} for i in range(40)])
    assert main(["check", "--baseline", str(a), "--variant", str(a), "--epsilon", "-0.5"]) == 3


def test_an_alpha_outside_the_sensible_range_is_refused(tmp_path):
    a = write(tmp_path, "a.jsonl", [{"id": f"q{i}", "correct": True} for i in range(40)])
    assert main(["check", "--baseline", str(a), "--variant", str(a), "--alpha", "0.9"]) == 3


# --- Finding 6: UNCALIBRATED prefixed only REAL -----------------------------------


def test_an_uncalibrated_inside_noise_verdict_says_it_is_uncalibrated():
    v = decide(delta_ab=0.03, gains=34, losses=33, n=240,
               critical=0.051, noise_band=None, p_value=0.71)
    assert v.name == "UNCALIBRATED_INSIDE_NOISE"
    assert v.exit_code == 1


# --- Finding 7: unmatched ids were summed, never shown ----------------------------


def test_unmatched_ids_are_shown_by_side_and_by_example(tmp_path):
    a = write(tmp_path, "a.jsonl", [{"id": f"task:{i}", "correct": True} for i in range(40)])
    b = write(tmp_path, "b.jsonl", [{"id": f"task:{i:04d}", "correct": True} for i in range(40)])
    b_extra = write(tmp_path, "b2.jsonl",
                    [{"id": f"task:{i}", "correct": i % 2 == 0} for i in range(30)] +
                    [{"id": f"other:{i}", "correct": True} for i in range(10)])
    text = render_text(analyse(pair(load_run(a), load_run(b_extra))))
    assert "task:" in text          # an example id, not just a count
    assert "baseline" in text and "variant" in text


# --- Finding 8: a crash exited 1, the same code as INSIDE_NOISE -------------------


def test_a_json_array_file_is_an_input_error_not_a_crash(tmp_path):
    good = write(tmp_path, "a.jsonl", [{"id": f"q{i}", "correct": True} for i in range(40)])
    bad = tmp_path / "b.json"
    bad.write_text(json.dumps([{"id": "q1", "correct": True}]), encoding="utf-8")
    assert main(["check", "--baseline", str(good), "--variant", str(bad)]) == 3


def test_a_directory_instead_of_a_file_is_an_input_error(tmp_path):
    good = write(tmp_path, "a.jsonl", [{"id": f"q{i}", "correct": True} for i in range(40)])
    assert main(["check", "--baseline", str(good), "--variant", str(tmp_path)]) == 3


# --- Finding 9: a degenerate A/A silently disabled its own bar --------------------


def test_an_aa_pair_that_shows_no_difference_cannot_calibrate_anything():
    ab = paired_scores([0, 1] * 60, [1, 1] * 60, kind="binary")
    identical = paired_scores([0, 1] * 60, [0, 1] * 60, kind="binary")
    result = analyse(ab, identical)
    assert result["verdict"]["name"].startswith("UNCALIBRATED")
    assert "no difference" in result["verdict"]["reason"]


# --- Finding 10: the threshold was labelled as a detectable effect ----------------


def test_the_threshold_is_not_called_the_smallest_detectable_effect():
    text = render_text(analyse(paired_scores([1, 0] * 60, [1, 1] * 60, kind="binary")))
    assert "smallest effect this setup could detect" not in text
    assert "detection threshold" in text


# --- Finding 11: numeric scores were rendered as percentage points ----------------


def test_numeric_scores_are_not_multiplied_by_a_hundred():
    #: Judge scores on a 1-to-5 scale, improving by 0.3. "+30.0 points" is nonsense.
    ab = paired_scores([3.0] * 50, [3.3] * 50)
    text = render_text(analyse(ab))
    assert "+30.0" not in text
    assert "+0.30" in text or "+0.3" in text


# --- Finding 12: the reason used raw fractions, the report used points ------------


def test_the_reason_uses_the_same_units_as_the_report():
    result = analyse(paired_scores([1, 0] * 60, [1, 1] * 60, kind="binary"))
    reason = result["verdict"]["reason"]
    assert "0.0" not in reason.split("(")[1].split(")")[0] or "points" in reason
