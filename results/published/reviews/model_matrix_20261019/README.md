# Model/representation matrix assessment — 19 October 2026

Decision: no configuration qualifies for reserved confirmation.

66 recorded trials: 60 model calls and six zero-call controls. All calls completed
and passed structural validation. All 244 displayed spans match source offsets.
All 30 paired inputs have exactly reversed passage order. Snapshot hashes,
actual question strings and effective model options were independently checked.

Of 24 trials asking for absent facts, four correctly abstain (Qwen 4B birth-date
trials). None of the twelve flute trials abstain correctly. Qwen 8B often selects
useful answerable evidence, but fails all its absent-fact trials. Some Qwen 4B and
Gemma outputs select requested facts while claiming the question unanswered.
These are not fully correct answers. Useful facts and end-to-end correctness
must not be conflated.

No overall accuracy leaderboard is assigned. This is a small development set
with reused questions and one generation per configuration/order. It tests the
ID-selection protocol; it does not isolate a model capability limit.

The reserved confirmation set remains unused. The next diagnostic should compare
direct answers on the same fixed evidence with the constrained evidence-selection
path, recording factual support, question coverage and justified abstention
separately. Do not change the production demo based solely on structural passes.

See assessment.json, answer_review.csv and configuration_summary.csv. No Word
file is required and no user-review-pending status is assigned.
