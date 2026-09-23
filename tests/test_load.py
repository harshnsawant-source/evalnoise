import pytest

from evalnoise.load import LoadError, load_run, pair


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_jsonl_with_boolean_outcomes(tmp_path):
    p = write(tmp_path, "a.jsonl", '{"id": "q1", "correct": true}\n{"id": "q2", "correct": false}\n')
    run = load_run(p)
    assert run.kind == "binary"
    assert run.outcomes == {"q1": 1.0, "q2": 0.0}


def test_reads_numeric_scores(tmp_path):
    p = write(tmp_path, "a.jsonl", '{"id": "q1", "score": 0.5}\n{"id": "q2", "score": 1}\n')
    run = load_run(p)
    assert run.kind == "numeric"
    assert run.outcomes == {"q1": 0.5, "q2": 1.0}


def test_reads_csv_with_bom_and_string_booleans(tmp_path):
    #: What a spreadsheet export actually looks like.
    p = tmp_path / "a.csv"
    p.write_text("id,correct\nq1,TRUE\nq2,0\n", encoding="utf-8-sig")
    run = load_run(p)
    assert run.kind == "binary"
    assert run.outcomes == {"q1": 1.0, "q2": 0.0}


def test_rejects_a_null_outcome_naming_the_item(tmp_path):
    p = write(tmp_path, "a.jsonl", '{"id": "q1", "correct": null}\n')
    with pytest.raises(LoadError, match="q1"):
        load_run(p)


def test_rejects_a_file_mixing_correct_and_score(tmp_path):
    p = write(tmp_path, "a.jsonl", '{"id": "q1", "correct": true}\n{"id": "q2", "score": 0.4}\n')
    with pytest.raises(LoadError, match="both"):
        load_run(p)


def test_rejects_duplicate_ids(tmp_path):
    p = write(tmp_path, "a.jsonl", '{"id": "q1", "correct": true}\n{"id": "q1", "correct": false}\n')
    with pytest.raises(LoadError, match="duplicate"):
        load_run(p)


def test_rejects_a_missing_id(tmp_path):
    p = write(tmp_path, "a.jsonl", '{"correct": true}\n')
    with pytest.raises(LoadError, match="id"):
        load_run(p)


def test_pairs_on_shared_ids_and_reports_the_rest(tmp_path):
    a = load_run(write(tmp_path, "a.jsonl", '{"id": "q1", "correct": true}\n{"id": "q2", "correct": true}\n'))
    b = load_run(write(tmp_path, "b.jsonl", '{"id": "q2", "correct": false}\n{"id": "q3", "correct": true}\n'))
    paired = pair(a, b)
    assert paired.ids == ["q2"]
    assert paired.baseline == [1.0] and paired.variant == [0.0]
    assert paired.unmatched_baseline == ["q1"]
    assert paired.unmatched_variant == ["q3"]


def test_refuses_to_compare_binary_with_numeric(tmp_path):
    a = load_run(write(tmp_path, "a.jsonl", '{"id": "q1", "correct": true}\n'))
    b = load_run(write(tmp_path, "b.jsonl", '{"id": "q1", "score": 0.4}\n'))
    with pytest.raises(LoadError, match="kind"):
        pair(a, b)
