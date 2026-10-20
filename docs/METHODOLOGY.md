# Evaluation methodology

## Questions and controls

Compare the same question, same passage texts and IDs, same model and request
options while reversing passage order. `retrieved` in the fixed-context
research runners means the saved canonical order; it does not perform a new
search. In the viewer it refers to the current retrieval/expansion result.
Reversal changes order only. Empty-context controls in the newer runners are
code abstentions with zero generation calls and are counted separately.

One deterministic-seed output per order is an observed paired result, not a
population-level causal estimate. Temperature zero and a seed do not promise
bitwise reproducibility across runtimes and machines. There are no repeated
independent trials or confidence intervals in the reported confirmation.

## Separate assessment layers

1. Mechanical validity: completion, schema, ID membership, copied source spans.
2. Model judgment: selected relevance, generated facts, optional critic output.
3. Source-based assessment: factual support, actor/action direction, conditions,
   exceptions, scope coverage, citation entailment and justified abstention.

The third layer is the project's final assessment performed by ChatGPT against
saved sources. It is not independent human annotation. No additional user
verification flag or pending review gate is added. Historical records retain
their original reviewer and status metadata rather than being rewritten.

An existing citation ID can support the wrong actor, fail to support a claim,
or accompany a wrong calculation. Exact copied text can be irrelevant. A
correct fact followed by a false claim that evidence is insufficient is not
counted as a clean answer. Exact abstention phrase checks miss paraphrases.
Grouped citations in the direct Gemma run expose a parser-format limitation:
six responses used real IDs in grouped brackets; those are not fabricated IDs.

## Data separation and reporting

Development includes repeated story questions used during repair. The short
fictional confirmation questions were reserved before direct-candidate
selection, but not independently held out. One absence question explicitly
states that the requested facts are unavailable. Keep these limits visible.
Do not tune on confirmation results and continue calling that set held out.

Report model-call denominators, code controls and failures separately. Do not
pool exploratory sessions, ID-selection tests, fixed-context generation and
ingestion/retrieval checks into one accuracy percentage. A failed completion
remains a failure, and a corrected citation parser does not repair semantics.

Model-stage time sums are local generation measurements, not hosted latency
or full end-to-end request timing. Saved model tags/digests and request options
identify runs more precisely than tags alone. Missing server version or Hub
revision metadata stays unknown; no value is inferred from a current release.
