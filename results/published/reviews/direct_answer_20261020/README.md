# Direct-answer baseline assessment — 20 October 2026

Direct Qwen 3 8B is the strongest candidate for a limited confirmation run, with
its current prompt frozen. It is not release-ready. On the ten development trials
it gives three supported substantive answers and four justified exact abstentions.
It reverses gift-giving roles once and wrongly abstains on both why trials.
These are five reused questions in two orders, not a general accuracy benchmark.

Qwen 3 4B: six trials hit the 2048-token output limit. Four complete, but all four
include analysis-like text in the answer field despite think=False; final suffixes
abstain correctly. Preserve raw records. Do not silently strip content or treat
this as a clean model-capability comparison. Template/runtime/output handling
needs isolation before using this model in the app.

Gemma 3 4B: roles, contradictions, mixed abstention and citation support fail on
several trials. Three absent-fact responses are semantically clean abstentions;
one of those uses different wording from the prescribed exact phrase.

Citation audit correction: six Gemma answers group multiple existing IDs inside
one bracket. Original strict parsing reports those groups as unknown. All
individual IDs exist. This corrects the interpretation of the parser output;
it does not validate claims or change the preserved original results.

33 total records: 30 model calls and three zero-call controls. Model-stage time
sums to 858.32 seconds; this is not a hosted latency benchmark. The question and
full-context digest matches the previous matrix. All 15 order pairs, actual
question strings, options and runner snapshot hash were checked.

Next: reserved synthetic confirmation with direct Qwen 8B only and no prompt
changes. Confirmation is diagnostic, not production approval. Keep known failures
in the project. Do not run the previous ID-selection confirmation path for this
candidate. See assessment.json, answer_review.csv and model_summary.csv.
