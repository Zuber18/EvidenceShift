# Evidence-ID replay assessment — 19 October 2026

Decision: structural improvement; semantic release criteria not met.

18 attempts: 16 model calls, two zero-call controls. All 16 calls produced valid
schema responses and completed. No mechanical failures. All 64 displayed units
independently match their recorded source offsets. All eight matched order pairs
use the same 19 chunks in reverse order and retain stable ID mappings.

All 16 model responses are labelled supported and leave unanswered_parts empty.
Both birth-date and both standalone-flute trials return irrelevant evidence
instead of abstaining. The reverse savings run selects the later 87-cent remainder
instead of the requested initial $1.87. Reverse marriage omits the identifying
passage. Why and overview questions remain incomplete or fragmented. Four trials
contain useful core evidence; that is not a count of fully correct generated answers.

Prompt tokens: 6746–6762, versus 3933–3949 for 2.0.0. Model-stage seconds sum:
486.96, versus 510.61 previously. These single-run timing measurements do not
establish a statistically reliable speed improvement. Output tokens sum to 705.

Keep 2.1.0 and its failed cases. Further work should use a prespecified comparison
of evidence representations and available generation models, separating source
membership from relevance, completeness and justified abstention. Include new
held-out questions and retain their results before any further tuning.

Details are in assessment.json and answer_review.csv. No automatic overall
accuracy score or user-review-pending state is assigned.
