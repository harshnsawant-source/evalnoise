import json

from evalnoise.cli import main


def write(tmp_path, name, pairs):
    path = tmp_path / name
    path.write_text("\n".join(json.dumps({"id": i, "correct": c}) for i, c in pairs), encoding="utf-8")
    return str(path)


def flat(n, pattern):
    return [(f"q{i}", bool(pattern[i % len(pattern)])) for i in range(n)]


def test_a_real_effect_exits_zero(tmp_path, capsys):
    a = write(tmp_path, "a.jsonl", flat(200, [0, 0, 1, 1]))
    b = write(tmp_path, "b.jsonl", flat(200, [1, 1, 1, 1]))
    code = main(["check", "--baseline", a, "--variant", b])
    assert code == 0
    assert "VERDICT" in capsys.readouterr().out


def test_an_unchanged_run_exits_one(tmp_path, capsys):
    a = write(tmp_path, "a.jsonl", flat(200, [0, 1]))
    code = main(["check", "--baseline", a, "--variant", a])
    assert code == 1
    assert "no item changed" in capsys.readouterr().out


def test_too_few_items_exits_two(tmp_path):
    a = write(tmp_path, "a.jsonl", flat(10, [0, 1]))
    b = write(tmp_path, "b.jsonl", flat(10, [1, 1]))
    assert main(["check", "--baseline", a, "--variant", b]) == 2


def test_a_bad_file_exits_three_with_a_message(tmp_path, capsys):
    a = write(tmp_path, "a.jsonl", flat(40, [0, 1]))
    assert main(["check", "--baseline", a, "--variant", str(tmp_path / "missing.jsonl")]) == 3
    assert "no such file" in capsys.readouterr().err


def test_json_flag_prints_only_json(tmp_path, capsys):
    a = write(tmp_path, "a.jsonl", flat(200, [0, 1]))
    b = write(tmp_path, "b.jsonl", flat(200, [1, 1]))
    main(["check", "--baseline", a, "--variant", b, "--json"])
    document = json.loads(capsys.readouterr().out)
    assert document["schema_version"] == 1


def test_an_aa_file_with_different_ids_pairs_on_what_is_shared(tmp_path, capsys):
    a = write(tmp_path, "a.jsonl", flat(200, [0, 1]))
    b = write(tmp_path, "b.jsonl", flat(200, [1, 1]))
    aa = tmp_path / "aa.jsonl"
    aa.write_text("\n".join(json.dumps({"id": f"q{i}", "correct": bool(i % 3)}) for i in range(50, 260)),
                  encoding="utf-8")
    code = main(["check", "--baseline", a, "--variant", b, "--aa", str(aa)])
    assert code in (0, 1, 2)
    assert "noise floor" in capsys.readouterr().out
