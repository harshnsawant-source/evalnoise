# evalnoise v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a CLI that decides whether a change to a language-model setup is a real effect or inside the noise that setup produces anyway.

**Architecture:** Five modules with one job each. `stats.py` and `verdict.py` are pure functions over plain numbers, so the whole decision procedure is testable without touching a file; `load.py` handles parsing and pairing, `report.py` rendering, `cli.py` arguments and exit codes. Data flows one way: files to paired outcomes to statistics to a verdict to a report.

**Tech Stack:** Python 3.10+, standard library only at runtime, `pytest` for tests.

**Spec:** `docs/superpowers/specs/2026-09-23-evalnoise-design.md`

## Global Constraints

- **Zero runtime dependencies.** Standard library only. `pytest` is a dev dependency.
- **Python 3.10 or newer.**
- **No network requests, ever.** The tool never calls a model.
- **Seeded and reproducible.** Default seed `20260923`; two runs on the same files must agree exactly.
- **Exit codes:** `0` REAL, `1` INSIDE_NOISE, `2` INCONCLUSIVE, `3` usage or input error.
- **JSON output carries `schema_version`**, starting at `1`.
- **Strategy-free repository:** the repo documents the tool and nothing else. `grep -ri` for the author's other work must return nothing before each commit.
- **Package/CLI name:** `evalnoise`. Source under `src/evalnoise/`.

## Review Focus

These are inputs the spec implies but does not discuss. Each has a test in the task that owns the code.

1. **Null or NaN outcomes** (`{"id": "q1", "correct": null}`) — must fail with a message naming the id, not crash or silently score as false. Task 5.
2. **CSV with a UTF-8 BOM and string booleans** (`"true"`, `"TRUE"`, `"1"`) — must load, because spreadsheet exports look like this. Task 5.
3. **An A/A file whose ids differ from the baseline's** — must pair on what they share and report the rest, not compare mismatched lists. Task 7.
4. **Every outcome identical in both runs** (zero variance) — bootstrap and permutation must return degenerate-but-valid values, and the verdict must be INSIDE_NOISE with "nothing changed", not a crash or a division by zero. Tasks 3 and 4.
5. **A file mixing `correct` and `score`, or two files using different kinds** — must be an explicit error, because comparing a boolean to a number silently is worse than refusing. Task 5.

---

### Task 1: Package skeleton and the two basic statistics

**Files:**
- Create: `pyproject.toml`, `src/evalnoise/__init__.py`, `src/evalnoise/stats.py`
- Test: `tests/test_stats.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `evalnoise.stats.delta(baseline: list[float], variant: list[float]) -> float`; `evalnoise.stats.churn(baseline: list[float], variant: list[float], epsilon: float = 0.0) -> tuple[int, float]` returning `(changed_count, changed_rate)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stats.py
import pytest

from evalnoise import stats


def test_delta_is_the_difference_of_means():
    baseline = [1, 0, 1, 0]
    variant = [1, 1, 1, 0]
    assert stats.delta(baseline, variant) == pytest.approx(0.25)


def test_delta_is_zero_when_runs_match():
    assert stats.delta([1, 0, 1], [1, 0, 1]) == 0.0


def test_churn_counts_items_whose_outcome_changed():
    changed, rate = stats.churn([1, 0, 1, 0], [1, 1, 1, 0])
    assert changed == 1
    assert rate == pytest.approx(0.25)


def test_churn_ignores_numeric_moves_within_epsilon():
    changed, rate = stats.churn([0.50, 0.50], [0.52, 0.90], epsilon=0.05)
    assert changed == 1
    assert rate == pytest.approx(0.5)


def test_statistics_reject_runs_of_different_length():
    with pytest.raises(ValueError, match="same length"):
        stats.delta([1, 0], [1])
```

- [ ] **Step 2: Run the test and watch it fail**

Run: `python -m pytest tests/test_stats.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'evalnoise'`.

- [ ] **Step 3: Create the package and write the minimal implementation**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "evalnoise"
version = "0.1.0"
description = "Decide whether a change to a language-model setup is real or inside the noise."
readme = "README.md"
requires-python = ">=3.10"
license = { file = "LICENSE" }
dependencies = []

[project.scripts]
evalnoise = "evalnoise.cli:main"

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.hatch.build.targets.wheel]
packages = ["src/evalnoise"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
# src/evalnoise/__init__.py
"""Decide whether a change to a language-model setup is real or inside the noise."""

__version__ = "0.1.0"
```

```python
# src/evalnoise/stats.py
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
```

- [ ] **Step 4: Run the test and watch it pass**

Run: `python -m pytest tests/test_stats.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/evalnoise/__init__.py src/evalnoise/stats.py tests/test_stats.py
git commit -m "Add the package and the two numbers everything else rests on"
```

---

### Task 2: Gains, losses, and McNemar's exact test

**Files:**
- Modify: `src/evalnoise/stats.py`
- Test: `tests/test_stats.py`

**Interfaces:**
- Consumes: `stats._check`.
- Produces: `stats.gains_losses(baseline, variant, epsilon: float = 0.0) -> tuple[int, int]` returning `(gains, losses)`; `stats.mcnemar_exact(gains: int, losses: int) -> float` returning a two-sided p-value.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_stats.py
def test_gains_and_losses_are_counted_separately():
    baseline = [1, 1, 0, 0]
    variant = [0, 1, 1, 0]
    gains, losses = stats.gains_losses(baseline, variant)
    assert (gains, losses) == (1, 1)


def test_balanced_flips_are_not_significant():
    #: 34 gains against 33 losses is what a coin does.
    assert stats.mcnemar_exact(34, 33) > 0.5


def test_one_sided_flips_are_significant():
    #: 20 changes, all in one direction: 2 * 0.5**20, far below any threshold.
    assert stats.mcnemar_exact(20, 0) == pytest.approx(2 * 0.5 ** 20)


def test_no_discordant_pairs_gives_p_of_one():
    assert stats.mcnemar_exact(0, 0) == 1.0


def test_mcnemar_is_symmetric():
    assert stats.mcnemar_exact(12, 3) == stats.mcnemar_exact(3, 12)
```

- [ ] **Step 2: Run the test and watch it fail**

Run: `python -m pytest tests/test_stats.py -v`
Expected: FAIL, `AttributeError: module 'evalnoise.stats' has no attribute 'gains_losses'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# add to src/evalnoise/stats.py
from math import comb


def gains_losses(
    baseline: Sequence[Number], variant: Sequence[Number], epsilon: float = 0.0
) -> tuple[int, int]:
    """Items that improved, and items that worsened, counted separately.

    Reporting these apart is the point of the tool: 34 gains and 33 losses average out
    to nothing, and a mean cannot tell that apart from 67 items nobody touched.
    """
    _check(baseline, variant)
    gains = sum(1 for b, v in zip(baseline, variant) if v - b > epsilon)
    losses = sum(1 for b, v in zip(baseline, variant) if b - v > epsilon)
    return gains, losses


def mcnemar_exact(gains: int, losses: int) -> float:
    """Two-sided exact McNemar p-value: a binomial test on the discordant pairs.

    Concordant pairs carry no information about direction, so only the items that
    changed enter the test. Under the null each change was equally likely to go either
    way, so the count of gains is Binomial(gains + losses, 0.5).
    """
    n = gains + losses
    if n == 0:
        return 1.0
    k = min(gains, losses)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)
```

- [ ] **Step 4: Run the test and watch it pass**

Run: `python -m pytest tests/test_stats.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/evalnoise/stats.py tests/test_stats.py
git commit -m "Count gains and losses apart, and test whether the split is a coin"
```

---

### Task 3: The permutation null and the bootstrap interval

**Files:**
- Modify: `src/evalnoise/stats.py`
- Test: `tests/test_stats.py`

**Interfaces:**
- Consumes: `stats._check`, `stats.delta`.
- Produces: `stats.permutation_critical(baseline, variant, *, epsilon=0.0, resamples=10000, seed=20260923, alpha=0.05) -> float`; `stats.bootstrap_ci(baseline, variant, *, resamples=10000, seed=20260923, confidence=0.95) -> tuple[float, float]`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_stats.py
def test_permutation_critical_value_grows_with_churn():
    #: Same number of items; the run with more changed items must tolerate a bigger
    #: swing before a difference counts as real.
    quiet_base = [1] * 96 + [0] * 4
    quiet_var = [1] * 94 + [0] * 6
    noisy_base = [1] * 60 + [0] * 40
    noisy_var = [0] * 40 + [1] * 60
    quiet = stats.permutation_critical(quiet_base, quiet_var)
    noisy = stats.permutation_critical(noisy_base, noisy_var)
    assert noisy > quiet


def test_permutation_is_reproducible_under_a_fixed_seed():
    base = [1, 0] * 50
    var = [1, 1] * 50
    first = stats.permutation_critical(base, var, seed=7)
    second = stats.permutation_critical(base, var, seed=7)
    assert first == second


def test_permutation_critical_is_zero_when_nothing_changed():
    same = [1, 0, 1, 1, 0]
    assert stats.permutation_critical(same, same) == 0.0


def test_bootstrap_interval_contains_the_observed_delta():
    base = [1, 0] * 60
    var = [1, 1] * 60
    low, high = stats.bootstrap_ci(base, var)
    assert low <= stats.delta(base, var) <= high


def test_bootstrap_interval_is_degenerate_when_runs_are_identical():
    same = [1, 1, 0, 0]
    assert stats.bootstrap_ci(same, same) == (0.0, 0.0)
```

- [ ] **Step 2: Run the test and watch it fail**

Run: `python -m pytest tests/test_stats.py -v`
Expected: FAIL, `AttributeError: module 'evalnoise.stats' has no attribute 'permutation_critical'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# add to src/evalnoise/stats.py
import random

DEFAULT_SEED = 20260923
DEFAULT_RESAMPLES = 10_000


def permutation_critical(
    baseline: Sequence[Number],
    variant: Sequence[Number],
    *,
    epsilon: float = 0.0,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    alpha: float = 0.05,
) -> float:
    """The largest swing this setup produces by chance alone.

    Under the null the change had no direction, so each item that moved was equally
    likely to have moved the other way. Flipping each changed item's direction at
    random, many times, gives the distribution of deltas a setup with this much churn
    produces from nothing. The returned value is that distribution's (1 - alpha)
    quantile of |delta|: an effect smaller than this is not distinguishable from churn.
    """
    _check(baseline, variant)
    moves = [v - b for b, v in zip(baseline, variant) if abs(v - b) > epsilon]
    if not moves:
        return 0.0
    n = len(baseline)
    rng = random.Random(seed)
    swings = []
    for _ in range(resamples):
        total = sum(m if rng.random() < 0.5 else -m for m in moves)
        swings.append(abs(total) / n)
    swings.sort()
    index = min(len(swings) - 1, int(round((1 - alpha) * (len(swings) - 1))))
    return swings[index]


def bootstrap_ci(
    baseline: Sequence[Number],
    variant: Sequence[Number],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Percentile interval for the delta, resampling items in pairs.

    Items are resampled as pairs rather than independently, because the two runs saw
    the same items; pairing is what removes the item-difficulty variance that would
    otherwise swamp the effect.
    """
    _check(baseline, variant)
    diffs = [v - b for b, v in zip(baseline, variant)]
    n = len(diffs)
    rng = random.Random(seed)
    means = []
    for _ in range(resamples):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    tail = (1 - confidence) / 2
    low = means[int(round(tail * (len(means) - 1)))]
    high = means[int(round((1 - tail) * (len(means) - 1)))]
    return low, high
```

- [ ] **Step 4: Run the test and watch it pass**

Run: `python -m pytest tests/test_stats.py -v`
Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add src/evalnoise/stats.py tests/test_stats.py
git commit -m "Measure what chance alone produces at this level of churn"
```

---

### Task 4: The verdict rules

**Files:**
- Create: `src/evalnoise/verdict.py`
- Test: `tests/test_verdict.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure rules over numbers).
- Produces: `verdict.Verdict` (frozen dataclass with `name: str`, `reason: str`, `exit_code: int`); `verdict.decide(*, delta_ab: float, gains: int, losses: int, n: int, critical: float, noise_band: float | None, p_value: float, alpha: float = 0.05, min_items: int = 30, min_discordant: int = 10) -> Verdict`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_verdict.py
from evalnoise.verdict import decide


def test_a_large_one_sided_effect_is_real():
    v = decide(delta_ab=0.12, gains=30, losses=4, n=240,
               critical=0.05, noise_band=0.042, p_value=0.0001)
    assert v.name == "REAL"
    assert v.exit_code == 0


def test_an_effect_below_the_noise_floor_is_inside_noise():
    v = decide(delta_ab=0.03, gains=34, losses=33, n=240,
               critical=0.051, noise_band=0.042, p_value=0.71)
    assert v.name == "INSIDE_NOISE"
    assert v.exit_code == 1
    assert "noise floor" in v.reason


def test_an_effect_above_the_floor_but_balanced_is_inside_noise():
    #: Clears both thresholds on size, but the flips are a coin toss.
    v = decide(delta_ab=0.09, gains=34, losses=33, n=240,
               critical=0.05, noise_band=0.042, p_value=0.71)
    assert v.name == "INSIDE_NOISE"
    assert "balanced" in v.reason


def test_too_few_items_is_inconclusive():
    v = decide(delta_ab=0.2, gains=5, losses=0, n=20,
               critical=0.05, noise_band=0.04, p_value=0.03)
    assert v.name == "INCONCLUSIVE"
    assert v.exit_code == 2
    assert "20" in v.reason


def test_too_few_changed_items_is_inconclusive():
    v = decide(delta_ab=0.02, gains=4, losses=1, n=240,
               critical=0.01, noise_band=0.005, p_value=0.2)
    assert v.name == "INCONCLUSIVE"


def test_nothing_changed_is_inside_noise_not_inconclusive():
    v = decide(delta_ab=0.0, gains=0, losses=0, n=240,
               critical=0.0, noise_band=0.04, p_value=1.0)
    assert v.name == "INSIDE_NOISE"
    assert "no item changed" in v.reason


def test_without_a_noise_floor_the_verdict_says_so():
    v = decide(delta_ab=0.12, gains=30, losses=4, n=240,
               critical=0.05, noise_band=None, p_value=0.0001)
    assert v.name == "UNCALIBRATED_REAL"
    assert "no A/A" in v.reason
    assert v.exit_code == 0
```

- [ ] **Step 2: Run the test and watch it fail**

Run: `python -m pytest tests/test_verdict.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'evalnoise.verdict'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/evalnoise/verdict.py
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
        return Verdict("UNCALIBRATED_REAL", reason + "; no A/A pair was supplied, so the noise floor is unmeasured", 0)
    return Verdict("REAL", reason, 0)
```

- [ ] **Step 4: Run the test and watch it pass**

Run: `python -m pytest tests/test_verdict.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/evalnoise/verdict.py tests/test_verdict.py
git commit -m "Decide, and say why in words the user can check"
```

---

### Task 5: Loading and pairing result files

**Files:**
- Create: `src/evalnoise/load.py`
- Test: `tests/test_load.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load.LoadError` (Exception); `load.Run` (frozen dataclass: `outcomes: dict[str, float]`, `kind: str` which is `"binary"` or `"numeric"`, `path: str`); `load.load_run(path) -> Run`; `load.Paired` (frozen dataclass: `ids: list[str]`, `baseline: list[float]`, `variant: list[float]`, `unmatched_baseline: list[str]`, `unmatched_variant: list[str]`); `load.pair(a: Run, b: Run) -> Paired`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_load.py
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
```

- [ ] **Step 2: Run the test and watch it fail**

Run: `python -m pytest tests/test_load.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'evalnoise.load'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/evalnoise/load.py
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
    raise LoadError(f"{path}: item {item_id!r} has a 'correct' value that is not true or false: {value!r}")


def _as_number(value: object, item_id: str, path: Path) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise LoadError(f"{path}: item {item_id!r} has a 'score' that is not a number: {value!r}") from None
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
        raise LoadError(f"cannot compare a {a.kind} run with a {b.kind} run: the outcome kind differs")
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
```

- [ ] **Step 4: Run the test and watch it pass**

Run: `python -m pytest tests/test_load.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/evalnoise/load.py tests/test_load.py
git commit -m "Read results, and refuse the inputs that would make a verdict a lie"
```

---

### Task 6: The analysis object and the two reports

**Files:**
- Modify: `src/evalnoise/verdict.py`
- Create: `src/evalnoise/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `load.Paired`, `stats.*`, `verdict.decide`.
- Produces: `verdict.analyse(paired_ab: Paired, paired_aa: Paired | None = None, *, epsilon: float = 0.0, seed: int = 20260923, alpha: float = 0.05) -> dict`; `report.render_text(analysis: dict) -> str`; `report.render_json(analysis: dict) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
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
```

- [ ] **Step 2: Run the test and watch it fail**

Run: `python -m pytest tests/test_report.py -v`
Expected: FAIL, `ImportError: cannot import name 'analyse' from 'evalnoise.verdict'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# add to src/evalnoise/verdict.py
from evalnoise import stats
from evalnoise.load import Paired

SCHEMA_VERSION = 1


def _summarise(p: Paired, *, epsilon: float, seed: int, alpha: float) -> dict:
    changed, rate = stats.churn(p.baseline, p.variant, epsilon)
    gains, losses = stats.gains_losses(p.baseline, p.variant, epsilon)
    low, high = stats.bootstrap_ci(p.baseline, p.variant, seed=seed)
    return {
        "delta": stats.delta(p.baseline, p.variant),
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
    noise = None
    if paired_aa is not None:
        aa = _summarise(paired_aa, epsilon=epsilon, seed=seed, alpha=alpha)
        aa["band"] = max(abs(aa["ci_low"]), abs(aa["ci_high"]))
        noise = aa
    decision = decide(
        delta_ab=change["delta"],
        gains=change["gains"],
        losses=change["losses"],
        n=len(paired_ab.ids),
        critical=change["critical"],
        noise_band=None if noise is None else noise["band"],
        p_value=change["p_value"],
        alpha=alpha,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "items": {
            "paired": len(paired_ab.ids),
            "unmatched_baseline": len(paired_ab.unmatched_baseline),
            "unmatched_variant": len(paired_ab.unmatched_variant),
        },
        "change": change,
        "noise_floor": noise,
        "verdict": {"name": decision.name, "reason": decision.reason, "exit_code": decision.exit_code},
        "config": {"epsilon": epsilon, "seed": seed, "alpha": alpha,
                   "resamples": stats.DEFAULT_RESAMPLES},
    }
```

```python
# src/evalnoise/report.py
"""Turn an analysis into something a person reads, or a machine parses."""

from __future__ import annotations

import json


def _points(value: float) -> str:
    return f"{value * 100:+.1f}"


def render_text(analysis: dict) -> str:
    change = analysis["change"]
    items = analysis["items"]
    lines = [
        f"items          {items['paired']} paired   "
        f"({items['unmatched_baseline'] + items['unmatched_variant']} unmatched)",
    ]
    noise = analysis["noise_floor"]
    if noise:
        lines.append(
            f"noise floor    ±{noise['band'] * 100:.1f} points  "
            f"churn {noise['churn_rate']:.0%}  ({noise['churn_count']} flipped)"
        )
    else:
        lines.append("noise floor    not measured — no --aa pair was supplied")
    lines += [
        f"your change    {_points(change['delta'])} points  "
        f"churn {change['churn_rate']:.0%}  ({change['churn_count']} flipped: "
        f"{change['gains']} gained, {change['losses']} lost)",
        f"               95% CI [{_points(change['ci_low'])}, {_points(change['ci_high'])}]   "
        f"McNemar p = {change['p_value']:.2f}",
        f"               smallest effect this setup could detect: "
        f"±{change['critical'] * 100:.1f} points",
        "",
        f"VERDICT  {analysis['verdict']['name']}",
        f"         {analysis['verdict']['reason']}",
    ]
    return "\n".join(lines)


def render_json(analysis: dict) -> str:
    return json.dumps(analysis, indent=1, sort_keys=True)
```

- [ ] **Step 4: Run the test and watch it pass**

Run: `python -m pytest tests/test_report.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/evalnoise/verdict.py src/evalnoise/report.py tests/test_report.py
git commit -m "Gather the evidence into one document, and render it two ways"
```

---

### Task 7: The command line

**Files:**
- Create: `src/evalnoise/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load.load_run`, `load.pair`, `load.LoadError`, `verdict.analyse`, `report.render_text`, `report.render_json`.
- Produces: `cli.main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
import json

import pytest

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
```

- [ ] **Step 2: Run the test and watch it fail**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'evalnoise.cli'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/evalnoise/cli.py
"""The command line: arguments in, a verdict and an exit code out."""

from __future__ import annotations

import argparse
import sys

from evalnoise import __version__, stats
from evalnoise.load import LoadError, load_run, pair
from evalnoise.report import render_json, render_text
from evalnoise.verdict import analyse

USAGE_ERROR = 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evalnoise",
        description="Decide whether a change is real or inside the noise your setup already produces.",
    )
    parser.add_argument("--version", action="version", version=f"evalnoise {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="compare two runs")
    check.add_argument("--baseline", required=True, help="results for configuration A")
    check.add_argument("--variant", required=True, help="results for configuration B")
    check.add_argument("--aa", help="a second run of A, or a placebo change: the noise floor")
    check.add_argument("--epsilon", type=float, default=0.0,
                       help="for numeric scores, the move below which nothing counts as changed")
    check.add_argument("--alpha", type=float, default=0.05, help="significance level (default 0.05)")
    check.add_argument("--seed", type=int, default=stats.DEFAULT_SEED, help="random seed")
    check.add_argument("--json", action="store_true", help="print the analysis as JSON")
    check.set_defaults(func=_check)
    return parser


def _check(args: argparse.Namespace) -> int:
    baseline = load_run(args.baseline)
    variant = load_run(args.variant)
    paired_ab = pair(baseline, variant)
    paired_aa = pair(baseline, load_run(args.aa)) if args.aa else None
    analysis = analyse(paired_ab, paired_aa, epsilon=args.epsilon, seed=args.seed, alpha=args.alpha)
    print(render_json(analysis) if args.json else render_text(analysis))
    return analysis["verdict"]["exit_code"]


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except LoadError as exc:
        print(f"evalnoise: {exc}", file=sys.stderr)
        return USAGE_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test and watch it pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: 6 passed. If `_parser` returns `None`, rewrite it as two statements: call `check.set_defaults(func=_check)` on its own line, then `return parser`.

- [ ] **Step 5: Commit**

```bash
git add src/evalnoise/cli.py tests/test_cli.py
git commit -m "Wire the command line, and make CI able to fail on noise"
```

---

### Task 8: The guarantees, proved by simulation

**Files:**
- Create: `tests/test_simulation.py`

**Interfaces:**
- Consumes: `load.Paired`, `verdict.analyse`.
- Produces: nothing; this task adds no source code. It proves the decision procedure behaves as claimed.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_simulation.py
"""What the tool promises, tested against data whose truth we set.

A verdict procedure cannot be checked by eye: it has to be run many times against
runs with a known effect and known churn. These two tests are the product claim —
a null change is called noise almost always, and a large real change is caught —
and they are why the thresholds in verdict.py can be trusted.
"""

import random

from evalnoise.load import Paired
from evalnoise.verdict import analyse


def simulate(n, churn_rate, true_effect, seed):
    """Paired runs where `churn_rate` of items flip at random and `true_effect` is added on top."""
    rng = random.Random(seed)
    baseline, variant = [], []
    for _ in range(n):
        base = 1 if rng.random() < 0.6 else 0
        value = base
        if rng.random() < churn_rate:
            value = 1 - base
        if rng.random() < true_effect:
            value = 1
        baseline.append(base)
        variant.append(value)
    ids = [f"q{i}" for i in range(n)]
    return Paired(ids=ids, baseline=baseline, variant=variant,
                  unmatched_baseline=[], unmatched_variant=[])


def test_a_null_change_at_high_churn_is_called_noise_at_least_95_percent_of_the_time():
    false_positives = 0
    trials = 60
    for seed in range(trials):
        ab = simulate(240, churn_rate=0.40, true_effect=0.0, seed=seed)
        aa = simulate(240, churn_rate=0.40, true_effect=0.0, seed=1000 + seed)
        if analyse(ab, aa)["verdict"]["name"].endswith("REAL"):
            false_positives += 1
    assert false_positives <= trials * 0.05


def test_a_large_real_effect_is_caught_at_least_80_percent_of_the_time():
    caught = 0
    trials = 60
    for seed in range(trials):
        ab = simulate(240, churn_rate=0.40, true_effect=0.25, seed=seed)
        aa = simulate(240, churn_rate=0.40, true_effect=0.0, seed=1000 + seed)
        if analyse(ab, aa)["verdict"]["name"].endswith("REAL"):
            caught += 1
    assert caught >= trials * 0.80
```

- [ ] **Step 2: Run the tests and see where they stand**

Run: `python -m pytest tests/test_simulation.py -v`
Expected: both pass. If the power test fails, do **not** loosen the thresholds in `verdict.py` to make it pass: reduce `resamples` only if the tests are too slow, and if the false-positive test fails, the bug is real and lives in `permutation_critical` or `decide`.

- [ ] **Step 3: Speed the tests up if they take longer than 60 seconds**

`analyse` takes no `resamples` argument, so the way to make these faster is fewer trials, not fewer resamples: change `trials = 60` to `trials = 40` in both tests and leave everything else alone. Forty trials still separates a 5% false-positive rate from a broken procedure. Say in the commit message that you did it.

- [ ] **Step 4: Run the whole suite**

Run: `python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_simulation.py
git commit -m "Prove the two promises: noise is not called real, and real is not called noise"
```

---

### Task 9: The real-data fixture

**Files:**
- Create: `tests/fixtures/qwen_unbiased.jsonl`, `tests/fixtures/qwen_biased.jsonl`, `tests/fixtures/README.md`, `tests/test_real_data.py`

**Interfaces:**
- Consumes: `cli.main`, `load.load_run`, `load.pair`, `verdict.analyse`.
- Produces: nothing; a regression test that the tool reproduces a published result.

- [ ] **Step 1: Build the fixture files from the published data**

The source is the `still-holds` repository, finding `cot_unfaithfulness_suggested`, file `raw/trials.jsonl`: one row per trial with `model`, `task`, `question_index`, `condition` (`unbiased` or `biased`), `target` and `answer`. Correctness is `answer == target`; the item id is `task:question_index`.

```python
# run once, from the evalnoise repository root, with the still-holds path adjusted
import json, pathlib

src = pathlib.Path("../still-holds/findings/cot_unfaithfulness_suggested/raw/trials.jsonl")
rows = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines()]
out = pathlib.Path("tests/fixtures")
out.mkdir(parents=True, exist_ok=True)
for condition, name in (("unbiased", "qwen_unbiased.jsonl"), ("biased", "qwen_biased.jsonl")):
    items = [
        {"id": f'{r["task"]}:{r["question_index"]}', "correct": r["answer"] == r["target"]}
        for r in rows
        if r["model"] == "qwen2.5:3b-instruct" and r["condition"] == condition
    ]
    (out / name).write_text("\n".join(json.dumps(i) for i in items) + "\n", encoding="utf-8")
    print(name, len(items))
```

Expected output: `qwen_unbiased.jsonl 240` and `qwen_biased.jsonl 240`.

Write `tests/fixtures/README.md` recording where the data came from, that it is published under the `still-holds` repository, and that correctness was derived as `answer == target`.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_real_data.py
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
```

- [ ] **Step 3: Run the test and watch it fail, then pass**

Run: `python -m pytest tests/test_real_data.py -v`
Expected: FAIL first with `LoadError: no such file` if step 1 was skipped; PASS once the fixtures exist. If `test_the_positive_delta_does_not_survive_the_verdict` fails because the verdict name is plain `INSIDE_NOISE`, that is the correct behaviour (an uncalibrated run that is inside noise is still inside noise) and the assertion already allows it.

- [ ] **Step 4: Run the whole suite**

Run: `python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures tests/test_real_data.py
git commit -m "Test against a published run whose answer is already known"
```

---

### Task 10: README, licence, and continuous integration

**Files:**
- Create: `README.md`, `LICENSE`, `.github/workflows/tests.yml`
- Modify: `pyproject.toml` (classifiers, URLs)

**Interfaces:**
- Consumes: the finished CLI.
- Produces: nothing in code.

- [ ] **Step 1: Write the README**

It must open with the problem, not the tool. Required content, in this order:

1. One sentence: what the tool decides.
2. **The example**, using the fixture from Task 9: a planted bias destroyed 42 correct answers, the metric read +5.4 points upward, 97 of 240 answers flipped. Show the actual `evalnoise check` output for those two files.
3. **What an A/A pair is and how to make one** — the same configuration twice, or a change that must not matter such as reordering options. Say plainly that without it the noise floor is unmeasured.
4. Install (`pip install evalnoise`), the input format (five lines), and the exit codes.
5. **What it does not do** — the "out of scope" list from the spec, section 3.
6. How it differs from DeepEval's significance testing and promptfoo's comparisons, in one paragraph: gains and losses separately, and a measured rather than assumed noise floor.

- [ ] **Step 2: Add the licence and the workflow**

`LICENSE`: MIT, copyright 2026 Harsh Sawant.

```yaml
# .github/workflows/tests.yml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: python -m pytest -v
```

- [ ] **Step 3: Check the repository rule and the install**

```bash
grep -ri "fellowship\|aviora\|resume\|employer\|recruit" --include="*.md" --include="*.py" --include="*.toml" . || echo "clean"
pip install -e ".[dev]" && evalnoise check --baseline tests/fixtures/qwen_unbiased.jsonl --variant tests/fixtures/qwen_biased.jsonl; echo "exit code: $?"
```

Expected: `clean`, then the report, then `exit code: 1`.

- [ ] **Step 4: Run the whole suite one more time**

Run: `python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add README.md LICENSE .github/workflows/tests.yml pyproject.toml
git commit -m "Explain the problem first, then the tool"
```

---

## Not in this plan

Publishing to PyPI, and creating the GitHub repository, are the author's actions and need his account. The plan leaves the repository ready for both: metadata complete, licence present, tests green in CI.
