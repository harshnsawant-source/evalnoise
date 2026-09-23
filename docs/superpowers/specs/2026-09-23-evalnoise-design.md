# evalnoise: design

**Date:** 2026-09-23
**Status:** approved in brainstorming; implementation not started

## 1. The problem

An engineer changes a prompt or swaps a model, re-runs their eval, sees three points of
improvement, and ships it. Nothing in their toolchain tells them that three points is smaller
than the difference they would have got by changing nothing at all.

This is not hypothetical. In a pre-registered replication on `qwen2.5:3b-instruct`
(`still-holds`, finding `cot_unfaithfulness_suggested`), a deliberately planted bias moved the
model toward a suggested answer by **+16.3 points** and destroyed **25 correct answers**, while
the pre-registered accuracy metric read **+0.054, positive**. The cause was churn: the same
prompt change flipped the correctness of **97 of 240 answers**, 33 losses against 34 gains, and
the gains had nothing to do with the bias. On the same protocol, a 31B model changed only 5 of
240. A metric built on means could not see any of this.

`evalnoise` reports the part the mean hides.

## 2. Who it is for

Engineers comparing two configurations of a language model system: two prompts, two models, two
temperatures, two retrieval settings. They already have an eval; they do not have a way to tell a
real change from their setup's noise.

Not for researchers designing benchmarks, and not a replacement for an eval harness. It consumes
what a harness produces.

## 3. Scope

**In scope for v0.1**

- Reading per-item results from JSONL or CSV, produced by any harness.
- Binary outcomes (`correct`) and numeric outcomes (`score`).
- Paired comparison of two runs on the same items.
- Churn, gains and losses, a permutation test, an A/A noise floor, and a verdict.
- A terminal report, a `--json` report, and exit codes for CI.

**Out of scope for v0.1**, and stated as such in the README so the boundary is visible:

- Calling models. `evalnoise` never makes a network request.
- HTML reports, dashboards, plots.
- Plugins for promptfoo, DeepEval, pytest.
- LLM-as-judge scoring, free-text similarity, per-category breakdowns.
- Multi-arm comparisons. Two runs at a time, plus the A/A pair.

## 4. Prior art, and what is different here

- **DeepEval** ships statistical significance testing, and **promptfoo** ships side-by-side
  comparison matrices. Both compare aggregate scores.
- **Miller, "Adding Error Bars to Evals" (arXiv:2411.00640)** is the methodological reference:
  standard errors, paired comparisons, and the recommendation to report uncertainty.

What none of them do is the two things this tool exists for: **decompose the change into gains
and losses** so that a cancelling effect cannot hide, and **calibrate against a measured A/A
baseline** rather than an assumed noise model. The A/A framing is borrowed deliberately from web
A/B testing, where running the null experiment first is standard practice and here is not.

## 5. Input contract

One file per run. JSONL, one object per line, or CSV with a header row.

```jsonl
{"id": "q1", "correct": true}
{"id": "q2", "correct": false}
{"id": "q3", "score": 0.82}
```

- `id` (string, required) identifies the item and is how runs are paired.
- `correct` (boolean) **or** `score` (number), required; a file must use one consistently.
- Any other field is ignored.

**Alignment rules.** Runs are paired on `id`. Ids present in one run and missing from the other
are excluded from the comparison and **reported by count and by example**, never silently
dropped. Duplicate ids are an error, because they make pairing ambiguous.

## 6. Statistics

Let `x_i` be the baseline outcome for item `i` and `y_i` the variant outcome, over `n` paired
items.

- **Delta**: `mean(y) - mean(x)`, reported in points.
- **Churn**: the share of items whose outcome changed. For binary outcomes, `x_i != y_i`; for
  numeric outcomes, `|y_i - x_i| > epsilon`, with `epsilon` configurable and defaulting to 0.
- **Gains and losses**: for binary, `gains = #{x_i=0, y_i=1}` and `losses = #{x_i=1, y_i=0}`.
  For numeric, counts of items that improved and worsened by more than `epsilon`.
- **Null distribution (permutation).** Under the null that the change has no direction, each
  discordant pair is equally likely to have gone either way. The direction of every discordant
  pair is flipped with probability 0.5, the delta recomputed, and this repeated 10,000 times with
  a fixed seed. The **critical value** `c*` is the 95th percentile of `|delta|` in that
  distribution: the largest swing the setup produces by chance alone at this churn level.
- **Significance.** For binary outcomes, McNemar's exact test on the discordant counts
  (a two-sided binomial test with p = 0.5). For numeric outcomes, the permutation test above.
- **Confidence interval.** Paired bootstrap over the per-item differences `d_i = y_i - x_i`,
  10,000 resamples, reported as a 95% percentile interval.
- **Noise floor.** From the A/A pair, the same delta and churn are computed, and the noise band
  is the upper 95% bootstrap bound on `|delta_AA|`. This is an empirical statement about this
  setup, not an assumption.

Random seeds are fixed and printed, so two runs of `evalnoise` on the same files agree exactly.

## 7. Verdict rules

| Verdict | Condition | Exit code |
|---|---|---|
| `REAL` | `\|delta_AB\|` exceeds **both** `c*` and the A/A noise band, and the significance test gives p < 0.05 | 0 |
| `INSIDE_NOISE` | The comparison is adequately powered but the effect does not clear those bars | 1 |
| `INCONCLUSIVE` | Fewer than 30 paired items, or between 1 and 9 discordant pairs: too little to decide | 2 |

Zero discordant pairs is not inconclusive: nothing changed, so the verdict is `INSIDE_NOISE`
with that as its reason.

Every verdict carries the reason that produced it, in words, in both the terminal and the JSON.

**Without an A/A pair.** `--aa` is optional. When it is absent the tool still runs, the verdict is
prefixed `UNCALIBRATED`, and the report says plainly that the noise floor was assumed rather than
measured. The README treats supplying an A/A run as the point of the tool.

**What an A/A pair is.** Two runs that should not differ: the same configuration run twice, or a
change that must not matter, such as reordering multiple-choice options or re-seeding. The README
explains both, because a user with a deterministic pipeline (temperature 0, fixed seed) will get
zero churn from a re-run and needs the placebo-change form instead.

## 8. Output

```
$ evalnoise check --baseline a.jsonl --variant b.jsonl --aa a2.jsonl

items          240 paired   (0 unmatched)
noise floor    ±4.2 points  churn 40%  (96 flipped)
your change    +3.0 points  churn 38%  (91 flipped: 34 gained, 33 lost)
               95% CI [-2.1, +8.0]   McNemar p = 0.71
               smallest effect this setup could detect: ±5.1 points

VERDICT  INSIDE_NOISE
         the change (3.0) is below both the noise floor (4.2) and the
         detection threshold (5.1), and the flips are balanced (p = 0.71)
```

`--json` prints the same content as a single object: inputs, every statistic, the verdict, and
the reason. The JSON shape is the stable interface for CI use and is versioned with a
`schema_version` field.

## 9. Module structure

| Module | Responsibility | Depends on |
|---|---|---|
| `load.py` | Parse JSONL/CSV, validate the schema, pair runs by id, report unmatched ids | stdlib |
| `stats.py` | Pure functions over lists of numbers: delta, churn, gains/losses, permutation null, McNemar exact, bootstrap CI | nothing |
| `verdict.py` | Apply the rules of section 7, returning a verdict and its reason | `stats` |
| `report.py` | Terminal rendering and the JSON document | `verdict` |
| `cli.py` | Arguments, file handling, exit codes | all |

`stats.py` and `verdict.py` take plain numbers and return plain values: the entire decision
procedure is testable without a filesystem. **Zero runtime dependencies** (standard library only),
so installation is instant, offline, and cannot break when somebody else publishes a release.
Python 3.10 or newer.

## 10. Testing

Tests are written before the code they cover.

1. **Synthetic data with known truth.** A generator produces paired runs with a chosen true
   effect and a chosen churn rate. Over many seeds: a zero effect at 40% churn must yield
   `INSIDE_NOISE` in at least 95% of trials (the false-positive guarantee), and an effect of
   twice the detection threshold must yield `REAL` in at least 80% (the power guarantee).
2. **Real data fixture.** The published `still-holds` run is committed as a test fixture. The
   tool must reproduce its numbers exactly: delta +0.054, 97 of 240 flipped, and verdict
   `INSIDE_NOISE`. This is both a regression test and the README's worked example.
3. **Statistical unit tests.** McNemar against hand-computed values for small tables; bootstrap
   and permutation reproducibility under a fixed seed.
4. **Edge cases.** No A/A file; fewer than 30 items; zero discordant pairs; every item flipped;
   numeric scores; duplicate ids; unmatched ids; empty file; a file mixing `correct` and `score`.

## 11. Repository

- New repository `evalnoise`, MIT licence.
- GitHub Actions running the test suite on Python 3.10 through 3.13.
- README opening with the `still-holds` example and teaching the A/A habit in its first section.
- **Strategy-free**: the repository says nothing about applications, employers, or the author's
  other projects, and is checked by grep before each commit.
- Published to PyPI as `evalnoise`; the name was checked as available on 2026-09-23.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Users have no A/A run, so the main feature is unused | The README leads with why, and `UNCALIBRATED` verdicts say what is missing every time |
| The verdict looks like a black box | Every verdict prints the numbers that produced it; no hidden thresholds |
| "Just use DeepEval's significance test" | The README states the difference in one paragraph: gains and losses separately, and a measured rather than assumed noise floor |
| Statistics implemented by hand are wrong | Section 10.1 and 10.3: known-truth simulations and hand-computed tables, not eyeballing |
| Scope creep into an eval harness | Section 3 lists what is out, and the README repeats it |

## 13. Roadmap after v0.1

Driven by real usage, not planned now: per-category breakdown, an HTML report, a power calculator
that answers "how many items do I need", and adapters that read promptfoo and DeepEval output
directly. The eval linter discussed in brainstorming is a separate project, not a feature.
