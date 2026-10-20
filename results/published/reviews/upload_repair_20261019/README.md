# Source-first live replay assessment

Decision: preserve this revision as an evaluated failure; do not promote it as
a reliable answer pipeline.

18 recorded attempts: 16 model calls plus two zero-call controls. All eight
question pairs have exactly reversed evidence order, and all model calls receive
all 19 indexed chunks. The PDF and measured embedding identity match the baseline.

Ten model attempts fail mechanical contracts: nine altered/noncontiguous or
wrongly assigned source excerpts, one insufficient response containing excerpts.
The six remaining model outputs comprise three justified abstentions, one
unjustified abstention, one irrelevant set of excerpts, and one relevant but
long evidence display. All twelve displayed quotations are exact indexed spans;
this demonstrates copying, not semantic answer correctness.

No old 6000-byte budget failures recur. Actual prompts are 3933–3949 tokens;
requesting 32k context is conservative over-allocation rather than proof that
32k was necessary. Stage durations sum to 510.61 seconds; this is not a hosted
latency benchmark.

Next targeted design: code-created sentence/passage handles selected by the model,
then source text copied by code. This removes quotation reproduction as a model
task. Relevance, answer completeness and abstention still require separate
assessment. Do not hide invalid excerpts by fuzzy matching or deleting failures.

Details: assessment.json and answer_review.csv. No user-review-pending field or
automatic semantic accuracy score is used.
