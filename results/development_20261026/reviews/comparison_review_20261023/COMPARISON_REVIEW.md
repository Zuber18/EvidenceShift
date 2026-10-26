# Original versus reranked Qwen 8B: development comparison review

All 32 attempts finished normally and passed the mechanical checks. All original-arm requests and answers exactly reproduced the earlier 16 Qwen 8B records. No model calls were made during review.

## Findings

| Task | Original evidence | Reranked evidence |
|---|---|---|
| Launch date | Correct in both orders | Correct in both orders; direct overview citation |
| Specialist terms | Permission and first-use obligation correct | Preserved in both orders |
| Mutable-default explanation | Supported mechanism summary | Supported mechanism summary |
| Reading-time calculation | Four hours, or 4.15 with insufficient citation and missing weekly scope | Four hours/week in both orders; requested 4.15 remains missing |
| Heat-study scope | Appropriate context abstention; required sample not retrieved | Actual Chinese sample answered; canonical has contradictory partial abstention, reversed is supported |
| Missing Flesch threshold | Exact abstention in both orders | Exact abstention in both orders |
| Python execution trace | Wrong final list in both orders | Still wrong in both orders |
| Editing policy | Canonical preserves exceptions; reversed contradicts them | Both preserve exceptions; general-policy coverage still incomplete |

## Interpretation

Reranking improves availability and use of evidence on the heat-study scope question and removes the reversed editing-exception contradiction in this run. It does not solve exact calculation, Python state tracking, full policy coverage or contradictory partial abstention.

The arithmetic task requires 6.26 − 2.11 = 4.15 hours/week. The reranked answers instead use a legitimate approximate four-hour summary from another passage. The failure is selecting the wrong precision/operation for the question, not proof that internal subtraction was attempted and failed.

The Python trace is [1], [2], [1, 3]. In the middle call, the explicitly supplied list receives 2; it does not modify the default list reused by the first and third calls. Reranking leaves this reasoning failure intact.

The editing policy’s general plain-English obligation and active-voice preference remain required by the frozen gold. Correctly preserving exceptions alone is not full policy coverage.

All known citation IDs passing membership checks did not establish claim support or correct reasoning. No overall accuracy percentage is assigned here; inspect the record dimensions and exposed-development limits.

## Next step

Keep weights fixed. Develop explicit computation/state-trace checks and a consistency gate using question and cited evidence, without reference answers or benchmark-specific output replacement. Freeze the proposed method and generation budget before a new run. Revisit fine-tuning only with a separate training corpus and untouched evaluation data.

Eight exposed development questions; one sample per condition and fixed seed. Context-faithful abstention is distinguished from end-to-end document coverage. No representative accuracy, independent human validation, other-model improvement or general hallucination-resolution claim.

## Record assessments

### calibration_01 · original · canonical

Verdict: **supported_answer**.

Correct launch date. Supplied citation supports it. Reranked arm cites the requested mission-overview passage directly.

Failure codes: none assigned

### calibration_01 · original · reversed

Verdict: **supported_answer**.

Correct launch date. Supplied citation supports it. Reranked arm cites the requested mission-overview passage directly.

Failure codes: none assigned

### calibration_01 · reranked · canonical

Verdict: **supported_answer**.

Correct launch date. Supplied citation supports it. Reranked arm cites the requested mission-overview passage directly.

Failure codes: none assigned

### calibration_01 · reranked · reversed

Verdict: **supported_answer**.

Correct launch date. Supplied citation supports it. Reranked arm cites the requested mission-overview passage directly.

Failure codes: none assigned

### calibration_02 · original · canonical

Verdict: **supported_answer**.

Preserves permission to use needed specialist terms and the obligation to explain them on first use.

Failure codes: none assigned

### calibration_02 · original · reversed

Verdict: **supported_answer**.

Preserves permission to use needed specialist terms and the obligation to explain them on first use.

Failure codes: none assigned

### calibration_02 · reranked · canonical

Verdict: **supported_answer**.

Preserves permission to use needed specialist terms and the obligation to explain them on first use.

Failure codes: none assigned

### calibration_02 · reranked · reversed

Verdict: **supported_answer**.

Preserves permission to use needed specialist terms and the obligation to explain them on first use.

Failure codes: none assigned

### calibration_03 · original · canonical

Verdict: **supported_mechanism_summary**.

Correct shared-default/conditional-new-list explanation in the omitted-argument context. Accumulation is described without explicitly naming append; original reversed also leaves once-only evaluation implicit. Do not read the None check as copying an explicitly supplied list.

Failure codes: none assigned

### calibration_03 · original · reversed

Verdict: **supported_mechanism_summary**.

Correct shared-default/conditional-new-list explanation in the omitted-argument context. Accumulation is described without explicitly naming append; original reversed also leaves once-only evaluation implicit. Do not read the None check as copying an explicitly supplied list.

Failure codes: none assigned

### calibration_03 · reranked · canonical

Verdict: **supported_mechanism_summary**.

Correct shared-default/conditional-new-list explanation in the omitted-argument context. Accumulation is described without explicitly naming append; original reversed also leaves once-only evaluation implicit. Do not read the None check as copying an explicitly supplied list.

Failure codes: none assigned

### calibration_03 · reranked · reversed

Verdict: **supported_mechanism_summary**.

Correct shared-default/conditional-new-list explanation in the omitted-argument context. Accumulation is described without explicitly naming append; original reversed also leaves once-only evaluation implicit. Do not read the None check as copying an explicitly supplied list.

Failure codes: none assigned

### calibration_04 · original · canonical

Verdict: **rounded_summary_instead_of_requested_calculation**.

Returns four hours rather than 6.26 minus 2.11 = 4.15 hours/week. C50 supports an approximate summary, not the requested precision. Weekly scope is omitted.

Failure codes: NUMERIC_ERROR, QUALIFICATION_LOSS

### calibration_04 · original · reversed

Verdict: **correct_number_with_insufficient_citation_and_unit_scope**.

4.15 is numerically correct, but cited c50 only states an average of four hours; it does not establish the exact operands/difference. The answer omits the per-week unit.

Failure codes: CITATION_SUPPORT, QUALIFICATION_LOSS

### calibration_04 · reranked · canonical

Verdict: **rounded_summary_instead_of_requested_calculation**.

Returns four hours/week from the Bland–Altman discussion in c35 despite both exact means being available in c1 and c33. Weekly unit improves, but requested 4.15 is not supplied. This establishes precision/operation-selection failure, not an observed internal subtraction error.

Failure codes: NUMERIC_ERROR

### calibration_04 · reranked · reversed

Verdict: **rounded_summary_instead_of_requested_calculation**.

Returns four hours/week from the Bland–Altman discussion in c35 despite both exact means being available in c1 and c33. Weekly unit improves, but requested 4.15 is not supplied. This establishes precision/operation-selection failure, not an observed internal subtraction error.

Failure codes: NUMERIC_ERROR

### calibration_05 · original · canonical

Verdict: **context_appropriate_abstention_with_end_to_end_retrieval_failure**.

Correctly refrains from guessing given the supplied five passages. The document is answerable, but the necessary sample/result was omitted by retrieval, leaving the end-to-end task unanswered. Do not label this a generation hallucination.

Failure codes: RETRIEVAL_MISS, MISSING_REQUIRED_UNIT

### calibration_05 · original · reversed

Verdict: **context_appropriate_abstention_with_end_to_end_retrieval_failure**.

Correctly refrains from guessing given the supplied five passages. The document is answerable, but the necessary sample/result was omitted by retrieval, leaving the end-to-end task unanswered. Do not label this a generation hallucination.

Failure codes: RETRIEVAL_MISS, MISSING_REQUIRED_UNIT

### calibration_05 · reranked · canonical

Verdict: **correct_sample_with_contradictory_partial_abstention**.

Correctly states 293 prefecture-level cities in China, not cities worldwide, then says the evidence does not answer whether the result can be described worldwide. That refusal conflicts with its own supported scope statement.

Failure codes: MIXED_ABSTENTION

### calibration_05 · reranked · reversed

Verdict: **supported_answer**.

Correctly identifies 293 prefecture-level Chinese cities and rejects worldwide generalization. Uses the paper’s 64.16% discussion result, consistent with the abstract’s rounded 64%. C60 supports count/country/proportion, while c40 also establishes prefecture-level scope; the answer is jointly supported by its cited passages.

Failure codes: none assigned

### calibration_06 · original · canonical

Verdict: **appropriate_exact_abstention**.

No universal minimum Flesch score is specified in the reviewed source. Exact prescribed abstention is appropriate in both arms/orders.

Failure codes: none assigned

### calibration_06 · original · reversed

Verdict: **appropriate_exact_abstention**.

No universal minimum Flesch score is specified in the reviewed source. Exact prescribed abstention is appropriate in both arms/orders.

Failure codes: none assigned

### calibration_06 · reranked · canonical

Verdict: **appropriate_exact_abstention**.

No universal minimum Flesch score is specified in the reviewed source. Exact prescribed abstention is appropriate in both arms/orders.

Failure codes: none assigned

### calibration_06 · reranked · reversed

Verdict: **appropriate_exact_abstention**.

No universal minimum Flesch score is specified in the reviewed source. Exact prescribed abstention is appropriate in both arms/orders.

Failure codes: none assigned

### calibration_07 · original · canonical

Verdict: **wrong_execution_trace**.

Correct trace is [1], [2], [1, 3]. The explicit middle [] is a separate object and does not append 2 to the default. All four responses give a wrong final list despite the required function being supplied at rank 1. The cited default-list example uses a different middle call; it does not support the requested trace.

Failure codes: CONTRADICTED_CLAIM, WRONG_RELATION, CITATION_SUPPORT

### calibration_07 · original · reversed

Verdict: **wrong_execution_trace**.

Correct trace is [1], [2], [1, 3]. The explicit middle [] is a separate object and does not append 2 to the default. All four responses give a wrong final list despite the required function being supplied at rank 1. The cited default-list example uses a different middle call; it does not support the requested trace.

Failure codes: CONTRADICTED_CLAIM, WRONG_RELATION, CITATION_SUPPORT

### calibration_07 · reranked · canonical

Verdict: **wrong_execution_trace**.

Correct trace is [1], [2], [1, 3]. The explicit middle [] is a separate object and does not append 2 to the default. All four responses give a wrong final list despite the required function being supplied at rank 1. The cited default-list example uses a different middle call; it does not support the requested trace.

Failure codes: CONTRADICTED_CLAIM, WRONG_RELATION, CITATION_SUPPORT

### calibration_07 · reranked · reversed

Verdict: **wrong_execution_trace**.

Correct trace is [1], [2], [1, 3]. The explicit middle [] is a separate object and does not append 2 to the default. All four responses give a wrong final list despite the required function being supplied at rank 1. The cited default-list example uses a different middle call; it does not support the requested trace.

Failure codes: CONTRADICTED_CLAIM, WRONG_RELATION, CITATION_SUPPORT

### calibration_08 · original · canonical

Verdict: **exceptions_preserved_but_general_policy_incomplete**.

Rejects both blanket rules and correctly preserves needed terminology/first-use explanation and passive-voice exceptions. However, the frozen gold also requires retaining the general plain-English obligation and normal active-voice preference; these are not explicitly stated as general policy. Reranked context omits the explicit active-voice rule at c6, though it remains in the original arm. This is an exception-handling improvement, not full coverage of every policy unit.

Failure codes: MISSING_REQUIRED_UNIT

### calibration_08 · original · reversed

Verdict: **contradiction_bad_citation_and_incomplete_policy**.

Explicitly endorses rewriting every passive sentence, contradicting the supplied exception and its own closing policy. C1 does not establish the claimed active-voice rule. Plain-English obligation is not stated in the proposed policy.

Failure codes: MISSING_REQUIRED_UNIT, CONTRADICTED_CLAIM, CITATION_SUPPORT

### calibration_08 · reranked · canonical

Verdict: **exceptions_preserved_but_general_policy_incomplete**.

Rejects both blanket rules and correctly preserves needed terminology/first-use explanation and passive-voice exceptions. However, the frozen gold also requires retaining the general plain-English obligation and normal active-voice preference; these are not explicitly stated as general policy. Reranked context omits the explicit active-voice rule at c6, though it remains in the original arm. This is an exception-handling improvement, not full coverage of every policy unit.

Failure codes: MISSING_REQUIRED_UNIT

### calibration_08 · reranked · reversed

Verdict: **exceptions_preserved_but_general_policy_incomplete**.

Rejects both blanket rules and correctly preserves needed terminology/first-use explanation and passive-voice exceptions. However, the frozen gold also requires retaining the general plain-English obligation and normal active-voice preference; these are not explicitly stated as general policy. Reranked context omits the explicit active-voice rule at c6, though it remains in the original arm. This is an exception-handling improvement, not full coverage of every policy unit.

Failure codes: MISSING_REQUIRED_UNIT

