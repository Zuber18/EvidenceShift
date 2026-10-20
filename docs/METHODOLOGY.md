# Evaluation methodology

I evaluate evidence-order sensitivity by keeping the question, passage texts,
source IDs, model and request options fixed while reversing passage order.
I record software validity, model judgments and source-based assessments
separately, so that a well-formed response is never mistaken for a correct one.

## Evidence and controls

In the fixed-context runners, `retrieved` means the saved canonical passage
order; those runners do not perform a new search. In the upload viewer it
refers to the current semantic retrieval and context-expansion result.
`reversed` changes passage order while retaining the same evidence.

The newer runners render empty-context abstention in code with zero model
calls. I count these controls separately from model-generated abstentions.
The preserved original API experiment engine has a different implementation:
its empty-context condition can still call the model.

A single output per order is one observed pair, not a population-level causal
estimate. Temperature zero and a fixed seed do not guarantee identical outputs
across runtimes or machines. My confirmation has no repeated independent
trials or confidence intervals.

## Three assessment layers

| Layer | What it records | What it cannot establish alone |
|---|---|---|
| Mechanical checks | Completion, schemas, ID membership, exact copied spans | Factual support or completeness |
| Model judgments | Selected relevance, generated facts, critic responses | Independent factual approval |
| Source-based assessment | Claim support, actor/action direction, conditions, exceptions, scope, citations and abstention | General reliability on arbitrary documents |

My source-based review workflow is model-assisted. I retain its reviewer and
method metadata in the saved assessments, which form the project's final
assessment record. I do not present this process as independent human
annotation. Historical metadata remains unchanged.

An existing citation can refer to the wrong actor, fail to support the claim,
or accompany incorrect arithmetic. An exact quotation can be irrelevant.
Correct facts followed by a false claim of insufficient evidence do not form
a clean answer. Exact-phrase abstention checks also miss paraphrased refusals.

In six direct Gemma responses, the older parser interprets grouped citation
brackets incorrectly even though their individual IDs exist. I retain those
original checks and report the parser limitation separately from semantic
citation-support errors.

## Data separation

The story questions are development cases used during repair. The short
fictional confirmation questions were reserved before direct-candidate
selection, but not independently held out. One unanswerable case explicitly
states that the requested facts are unavailable. I preserve these boundaries
and do not tune on confirmation results while describing that set as held out.

## Reporting

I report model calls, code controls, incomplete outputs and mechanical
failures separately. Exploratory sessions, representation comparisons,
fixed-context generation and ingestion/retrieval checks have different
denominators; I do not combine them into a headline accuracy percentage.

Model-stage time sums describe local inference calls, not hosted or complete
request latency. Model tags, available digests, exact prompts, request options
and source hashes are retained with each run where recorded. Missing server
versions and Hub revision metadata remain unknown.
