"""Read per-item results, and pair two runs on their ids.

The rule behind every error here: refuse rather than guess. A duplicate id makes
pairing ambiguous, a null outcome is not a failure, and a boolean compared against a
score is a comparison of two different things. Silently choosing one interpretation
would produce a verdict that looks sound and is not.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

TRUE = {"true", "1", "yes", "t", "y"}
FALSE = {"false", "0", "no", "f", "n"}


class LoadError(Exception):
    """Something in the input made a trustworthy comparison impossible."""


@dataclass(frozen=True)
class Run:
    outcomes: dict[str, float]
    kind: str  # "binary" or "numeric"
    path: str


@dataclass(frozen=True)
class Paired:
    ids: list[str]
    baseline: list[float]
    variant: list[float]
    unmatched_baseline: list[str]
    unmatched_variant: list[str]


def _as_binary(value: object, item_id: str, path: Path) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and value in (0, 1):
        return float(value)
    if isinstance(value, str) and value.strip().lower() in TRUE | FALSE:
        return 1.0 if value.strip().lower() in TRUE else 0.0
    raise LoadError(
        f"{path}: item {item_id!r} has a 'correct' value that is not true or false: {value!r}"
    )


def _as_number(value: object, item_id: str, path: Path) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise LoadError(
            f"{path}: item {item_id!r} has a 'score' that is not a number: {value!r}"
        ) from None
    if number != number:  # NaN
        raise LoadError(f"{path}: item {item_id!r} has a 'score' of NaN")
    return number


def _rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".csv":
        return [dict(row) for row in csv.DictReader(text.splitlines())]
    rows = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise LoadError(f"{path}: line {number} is not valid JSON: {exc.msg}") from None
    return rows


def load_run(path: str | Path) -> Run:
    """Read one run's results. Raises LoadError with a message naming the problem."""
    path = Path(path)
    if not path.exists():
        raise LoadError(f"{path}: no such file")
    outcomes: dict[str, float] = {}
    kind: str | None = None
    for row in _rows(path):
        item_id = row.get("id")
        if item_id is None or str(item_id).strip() == "":
            raise LoadError(f"{path}: a row has no 'id'")
        item_id = str(item_id)
        if item_id in outcomes:
            raise LoadError(f"{path}: duplicate id {item_id!r}")
        has_correct = "correct" in row and row["correct"] not in ("", None)
        has_score = "score" in row and row["score"] not in ("", None)
        if has_correct and has_score:
            raise LoadError(f"{path}: item {item_id!r} has both 'correct' and 'score'")
        if has_correct:
            row_kind, value = "binary", _as_binary(row["correct"], item_id, path)
        elif has_score:
            row_kind, value = "numeric", _as_number(row["score"], item_id, path)
        elif "correct" in row or "score" in row:
            raise LoadError(f"{path}: item {item_id!r} has an empty outcome")
        else:
            raise LoadError(f"{path}: item {item_id!r} has neither 'correct' nor 'score'")
        if kind is None:
            kind = row_kind
        elif kind != row_kind:
            raise LoadError(f"{path}: the file uses both 'correct' and 'score'; use one")
        outcomes[item_id] = value
    if not outcomes:
        raise LoadError(f"{path}: no items")
    return Run(outcomes=outcomes, kind=kind or "binary", path=str(path))


def pair(a: Run, b: Run) -> Paired:
    """Align two runs on the ids they share."""
    if a.kind != b.kind:
        raise LoadError(
            f"cannot compare a {a.kind} run with a {b.kind} run: the outcome kind differs"
        )
    shared = sorted(set(a.outcomes) & set(b.outcomes))
    if not shared:
        raise LoadError("the two runs share no ids")
    return Paired(
        ids=shared,
        baseline=[a.outcomes[i] for i in shared],
        variant=[b.outcomes[i] for i in shared],
        unmatched_baseline=sorted(set(a.outcomes) - set(b.outcomes)),
        unmatched_variant=sorted(set(b.outcomes) - set(a.outcomes)),
    )
