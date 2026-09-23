# evalnoise

**Your eval says the new prompt is 3 points better. Is it?**

`evalnoise` reads the per-item results you already have and answers one question: is this
change real, or is it inside the noise your setup produces anyway?

## The run that explains why this exists

A published replication on `qwen2.5:3b-instruct` planted a suggested answer in the user's
turn ("I think the answer is (A) but I'm curious to hear what you think") and measured what
happened to 240 questions. The accuracy metric went **up** by 5.4 points.

Underneath that number, **42 correct answers had been destroyed**:

```
$ evalnoise check --baseline unbiased.jsonl --variant biased.jsonl

items          240 paired   (none unmatched)
noise floor    not measured - no --aa pair was supplied
your change    +5.4 points  churn 40%  (97 flipped: 55 gained, 42 lost)
               95% CI [-2.5, +13.3]   McNemar p = 0.22
               detection threshold (chance alone reaches this 5% of the time): +/-7.9 points

VERDICT  UNCALIBRATED_INSIDE_NOISE
         the change (5.4 points) does not clear the detection threshold (7.9 points);
         no A/A pair was supplied, so the noise floor is unmeasured
```

97 of 240 answers flipped. 55 happened to land right, 42 landed wrong, and the average of
those two is the "+5.4" a dashboard would have shown you. The data for this example is in
`tests/fixtures/`, and it is a test: if this tool ever calls that result an improvement,
the build fails.

## Measure your noise floor: run an A/A first

An A/A pair is two runs that **should not differ**:

- the same configuration twice, if anything in your pipeline is non-deterministic, or
- a change that must not matter, such as reordering multiple-choice options or re-seeding,
  if your pipeline is deterministic and a re-run would be identical.

Whatever difference that produces is your noise floor. Pass it with `--aa`:

```
$ evalnoise check --baseline a.jsonl --variant b.jsonl --aa a2.jsonl
```

Without `--aa` the tool still works, but every verdict is prefixed `UNCALIBRATED`, as in
the example above: it can tell you what chance produces at your churn level, but not what
your own pipeline does when nothing changes. An A/A pair that flips *nothing* is treated
the same way, because a pair that shows no difference has measured no floor.

## Install

```
pip install evalnoise
```

Python 3.10 or newer. **No dependencies**, no network access, nothing to configure.

## Input

One file per run, JSONL or CSV, from any harness. Two fields matter:

```jsonl
{"id": "q1", "correct": true}
{"id": "q2", "correct": false}
{"id": "q3", "score": 0.82}
```

`id` pairs the runs; `correct` (boolean) or `score` (number) is the outcome. Every other
field is ignored, so exporting from promptfoo, DeepEval or your own script is a few lines.
Ids in one run and not the other are reported, never silently dropped.

## Exit codes

| Code | Verdict | Meaning |
|---|---|---|
| 0 | `REAL` | Bigger than chance, bigger than your noise floor, and one-sided |
| 0 | `UNCALIBRATED_REAL` | The same, but no noise floor was measured: treat with care |
| 1 | `INSIDE_NOISE` | The result does not support shipping |
| 1 | `UNCALIBRATED_INSIDE_NOISE` | The same, without a measured noise floor |
| 2 | `INCONCLUSIVE` | Too few items, or too few changed, to decide |
| 3 | (none) | Bad input or bad settings; the message says what and where |

A gate that accepts exit code 0 accepts `UNCALIBRATED_REAL` too, so pass `--aa` if that
distinction matters to you.

So it can gate a pull request:

```yaml
- run: evalnoise check --baseline before.jsonl --variant after.jsonl --aa before2.jsonl
```

`--json` prints the whole analysis, including every number behind the verdict, with a
`schema_version` field.

## How it decides

Three bars, all printed with their numbers, and a change must clear all of them:

1. **Bigger than chance.** The items that changed are re-flipped at random 10,000 times to
   see how large a swing this much churn produces from nothing.
2. **Bigger than your measured noise floor**, from the A/A pair. This is the only one that
   uses evidence from your own pipeline, which is why `--aa` matters.
3. **One-sided.** 34 gains against 33 losses is a coin toss. McNemar's exact test.

For binary outcomes bars 1 and 3 are close relatives — sign-flipping ±1 moves *is* the
binomial the exact test computes — so treat them as one conservative check plus the A/A
floor, not three independent ones. Nothing is hidden: every verdict prints the values that
produced it, and a fixed seed means two runs on the same files agree exactly.

## What it does not do

- It never calls a model, and never makes a network request.
- No charts, no dashboards, no HTML.
- No LLM-as-judge scoring; it reads what your harness already scored.
- Two runs at a time, plus the A/A pair.

## How this differs from the eval tools you already use

DeepEval ships significance testing and promptfoo compares prompts side by side. Both work
on **aggregate scores**, and the example above is a result whose aggregate score is exactly
what misleads: +5.4, positive, while 42 answers broke. `evalnoise` reports gains and losses
separately so a cancelling effect cannot hide, and calibrates against a noise floor you
**measure** rather than one it assumes. It is meant to run next to those tools, on their
output, not instead of them.

## Licence

MIT.
