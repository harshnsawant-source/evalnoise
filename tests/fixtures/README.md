# Where this data came from

`qwen_unbiased.jsonl` and `qwen_biased.jsonl` are a published replication run, reshaped
into the input format this tool reads.

- **Source:** the `still-holds` repository, finding `cot_unfaithfulness_suggested`, file
  `raw/trials.jsonl`, model `qwen2.5:3b-instruct`.
- **The experiment:** 240 questions from four BIG-Bench Hard tasks, answered twice. In the
  biased condition the user's turn states a suggested answer ("I think the answer is (A) but
  I'm curious to hear what you think"); the unbiased condition is the same question without
  it.
- **How correctness was derived:** `correct` is `answer == target` from the trial record.
  Nothing else was changed, and no item was dropped.
- **Item ids** are `task:question_index`, which is what pairs the two files.

The run is in the tests because its answer is already known and published: the accuracy
metric moved upward by 5.4 points while 97 of the 240 answers flipped, 42 of them from
correct to wrong. A tool that calls that a real improvement is broken, so the test asserts
it does not.
