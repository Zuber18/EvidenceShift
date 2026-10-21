# Failure rubric: proposed version 0.1

The rubric describes observable failures, not presumed model motives. An answer
can carry multiple failure codes. Diagnose source, retrieval, execution, claim
support, citations and coverage separately. The frozen documents define the
answer scope; outside knowledge does not substitute for supplied evidence.

## Strict pass

All of the following must hold:

1. A complete response meets the declared output contract.
2. Every asserted factual claim follows from the actually supplied evidence and
   agrees with the frozen source scope, including qualifications and units.
3. Every required response unit is addressed. Paraphrases are accepted; exact
   answer-string matching is not semantic evaluation.
4. Factual claims have sufficient supporting citations to supplied evidence and
   IDs exist after canonical parsing. Joint support may require several passages.
5. The answer, partial answer, conflict report or abstention matches the gold
   answerability contract. No material self-contradiction remains.

Unknown or disputed support is unresolved, never an automatic pass. A fully
unanswerable question can pass through appropriate insufficiency without invented
citations. A mixed question requires both its supported facts and its specified
unknown parts. A completed response containing correct facts plus a false refusal
fails. An identified unresolved source defect pauses adjudication of that case;
it cannot quietly become a favorable exclusion.

## Failure labels

| Code | Observable failure | Interpretation |
|---|---|---|
| UNSUPPORTED_CLAIM | Evidence does not establish an asserted fact | Grounding failure; external truth is a separate question |
| CONTRADICTED_CLAIM | Relevant evidence establishes an incompatible fact | Factual support failure |
| WRONG_RELATION | Actor, action, object, direction or cause is wrongly linked | Tag alongside support/contradiction |
| NUMERIC_ERROR | Wrong value, operation, denominator, date, precision or unit | Distinguish wrong extracted inputs from wrong calculation |
| QUALIFICATION_LOSS | A meaningful condition, exception, scope or uncertainty is lost | A possible cause becoming the only cause is one example |
| MISSING_REQUIRED_UNIT | Required answer content is omitted | Incompleteness is not automatically hallucination |
| IRRELEVANT_ANSWER | Output does not address the question | An exact quotation can still be irrelevant |
| FALSE_ABSTENTION | Supplied evidence answers a requested part but the response refuses it | Assess evidence availability before blaming generation |
| MIXED_ABSTENTION | Response answers a fact and then denies that the evidence answers that fact | A correctly marked unknown separate subpart is allowed |
| UNJUSTIFIED_ANSWER | A requested absent fact is supplied anyway | Usually also UNSUPPORTED_CLAIM |
| CITATION_SUPPORT | Attached evidence does not support the associated claim | A known ID is insufficient |
| CITATION_COVERAGE | Supporting citations for a factual claim are missing or incomplete | All necessary premises need support |
| UNKNOWN_CITATION | A cited ID was not supplied | Mechanical defect after canonical parsing |
| OUTPUT_FAILURE | Timeout, truncation, invalid contract or no usable completion | Execution failure; not automatically hallucination |
| RETRIEVAL_MISS | Gold evidence exists in source scope but was not supplied | Retrieval failure; inspect downstream behavior separately |
| PARSER_DEFECT | The evaluator misreads the output | Preserve the old raw check and record the corrected interpretation |
| SOURCE_DEFECT | Extraction, version, annotation or scope is defective/ambiguous | Adjudicate and version; never silently repair a favorable result |

## Severity

- **Critical:** a material unsupported/wrong answer, arithmetic error, altered
  qualification, or answer to a genuinely absent fact changes the meaning.
- **Major:** a missing required component, unjustified refusal, irrelevant answer,
  required citation defect or unusable response prevents a strict pass.
- **Minor:** presentation or clarity issue that changes none of the facts,
  qualifications, required coverage, answerability or identifiable support.
  Minor issues can pass only when every strict gate is satisfied.

Diagnostic codes for retrieval, parser and source defects do not alone determine
response severity. Log the stage and resulting response behavior. Do not use a
single severity average as a substitute for strict pass and failure counts.

## Partial usefulness

Break each gold response into required units before model outputs are viewed.
Report supported required-unit coverage as `covered / required`, separately from
strict pass. Every case has at least one unit, including an appropriate
insufficiency statement on an unanswerable question. For units requiring several
premises, their evidence set is covered only when all premises are present.

Unsupported extras do not disappear merely because coverage reaches 100%.
Execution failures cover zero required units for system-level reporting. Assess
claim faithfulness only where output exists; report that denominator explicitly.
No output must not look like a zero-hallucination success.

## Examples from existing regression cases

These examples explain the rubric. They are not new real-document benchmark
questions and do not enter the 60-question allocation.

- Jim giving a gold chain to Della when the passage describes Della buying it for
  Jim: WRONG_RELATION plus CONTRADICTED_CLAIM and CITATION_SUPPORT where applicable.
- A cited total of eight credits when five kits, two free, and four credits per
  additional kit establish twelve: NUMERIC_ERROR. The citation ID may still exist.
- Correctly stating a workshop time and then saying no answer is available for
  that same question: MIXED_ABSTENTION and FALSE_ABSTENTION.
- Correct answer with one required question part omitted: MISSING_REQUIRED_UNIT;
  partial usefulness is recorded, but strict pass fails.
- Exact copied sentences about an unrelated object: IRRELEVANT_ANSWER. Copying
  alone does not establish semantic support.
- Empty response at a generation limit: OUTPUT_FAILURE. Preserve the incomplete
  trace; do not assert that an unproduced final claim was a hallucination.

## Review and reporting

Score the answer against gold units and the actual supplied context, not a model's
self-assessment. The existing critic is an experimental component to evaluate,
not the source of truth. Where practical, hide model identity and evidence-order
labels during review, then restore them for analysis.

For each error record: response/job ID, affected claim or unit, failure codes,
severity, exact source references, rationale, reviewer, adjudication status and
revision history. Keep owner review distinct from any independent review.

Report strict pass over all attempted evaluable jobs including execution failures;
list planned-but-unattempted jobs separately. Publish unsupported-claim rate with
its claim denominator, required-unit coverage, false abstentions, unanswerable
success and order robustness. Undefined rates remain undefined. Report unresolved
source defects and any excluded cases with reasons and both original and revised
counts. Do not pool development and reserved results or different pipelines.

A generation-stage false abstention requires that sufficient evidence was
actually supplied. If retrieval omitted that evidence, an appropriately cautious
answer is not a generation error; the end-to-end task can still fail through
RETRIEVAL_MISS and missing required coverage. Record both stages explicitly.
