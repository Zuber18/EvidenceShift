# Frozen three-model regression review

The final method improves output structure but does not reliably prevent factual errors, scope contradictions, missed abstention or incorrect citation attachment. The evaluation phase is closed for this release.

| Model | Normal completions | Rendered answers | Appropriate exact abstentions | Main observed limitation |
|---|---:|---:|---:|---|
| Qwen 3 8B | 6/6 | 6/6 | 2 | Citation over-selection and one locally unsupported specialist-term claim |
| Qwen 3 4B instruct replacement | 6/6 | 5/6 | 2 | One blocked status/content conflict; one geography/metric error |
| Gemma 3 4B | 6/6 | 6/6 | 0 | Unsupported worldwide claim, two missed abstentions and citation misattribution |

These counts measure the named outcomes only. They are not semantic accuracy scores. There are three distinct questions in each model’s six trials.

All 18 outputs are valid JSON. One Qwen 4B output violates the cross-field rule for insufficient evidence and is blocked before rendering. All 18 calls completed normally with no thinking output. Frozen file hashes, full requests, schema payloads, raw streamed content and result rendering were verified. Other than the model field, request payloads match across models for corresponding question/order inputs. All six repeated Qwen 8B answers exactly reproduce the final diagnostic, including its citation weaknesses.

Gemma’s reversed heat answer incorrectly extends the Chinese study result worldwide, then names the Chinese sample. Qwen 4B’s canonical heat answer correctly identifies the sample but adds southern/central geography associated with a hazard component instead of the abstract’s northwestern overall-risk pattern. These two rendered factual failures pass format and citation-membership checks.

Qwen 8B and the replacement Qwen 4B correctly abstain on the missing Flesch threshold. Gemma does not invent a threshold but labels absence from the full guidance as answered, citing excerpts that do not establish that absence. This violates the prescribed abstention protocol.

Citation support remains separate from truth in context. In the reversed Qwen 8B policy and several smaller-model policy parts, true statements are attached to passages that do not establish the local claim. Gemma’s canonical policy explicitly attributes passive-voice guidance to the vocabulary passage c2 instead of c7. Filled slots and known IDs are insufficient evidence checks.

Keep all failures. Freeze prompts and weights; publish this as a small, exposed development regression with manually specified question-only requirements. It is not the full 100-question evaluation, and it does not show the hallucination problem is solved. The earlier retrieval, arithmetic and restricted Python-trace results retain their separate scopes.

## qwen3:8b / calibration_05 / canonical

supported_core: citation_overselection

Correct scope and sample; all five passages cited for each part, including passages not directly establishing the sample.

## qwen3:8b / calibration_05 / reversed

supported_core: supported core

Core claims and requested coverage are supported by the saved passages; this is not a claim that every selected citation is minimal.

## qwen3:8b / calibration_06 / reversed

appropriate_abstention: supported core

Exact abstention is appropriate: no required minimum score is established by the supplied passages.

## qwen3:8b / calibration_06 / canonical

appropriate_abstention: supported core

Exact abstention is appropriate: no required minimum score is established by the supplied passages.

## qwen3:8b / calibration_08 / canonical

supported_core: supported core

Core claims and requested coverage are supported by the saved passages; this is not a claim that every selected citation is minimal.

## qwen3:8b / calibration_08 / reversed

supported_core: local_citation_support_incomplete, citation_overselection

Blanket-rule paragraph includes the specialist-term exception but omits direct supporting passage c3 from that paragraph’s citations. A later paragraph correctly cites c3.

## qwen3:4b-instruct-2507-q4_K_M / calibration_05 / canonical

needs_correction: material_factual_error, metric_conflation, citation_support_incomplete

Sample is correct, but the answer says higher heat risk is concentrated in southern/central China. That geography describes the hazard component in c19; abstract c6 describes overall risk as higher in northwestern China. Selected c40/c60/c6 do not support the added geographic assertion.

## qwen3:4b-instruct-2507-q4_K_M / calibration_05 / reversed

blocked_no_final_answer: cross_field_contract_failure, inconsistent_answerability

The model sets worldwide_scope to insufficient_evidence while supplying nonempty text and IDs, and both rejects worldwide scope and says it cannot confirm or deny it. Raw JSON is valid; the runtime invariant correctly blocks rendering. Draft findings are not final-answer failures.

## qwen3:4b-instruct-2507-q4_K_M / calibration_06 / reversed

appropriate_abstention: supported core

Exact abstention is appropriate: no required minimum score is established by the supplied passages.

## qwen3:4b-instruct-2507-q4_K_M / calibration_06 / canonical

appropriate_abstention: supported core

Exact abstention is appropriate: no required minimum score is established by the supplied passages.

## qwen3:4b-instruct-2507-q4_K_M / calibration_08 / canonical

supported_core: citation_overselection, local_citation_support_incomplete, qualification_overstatement

Core rejection, general aim and exceptions are covered. Some claims about specialist-term permission and first-use explanation appear in general-aim slots without c3 among those slot citations. The proposed passive policy says only in the listed circumstances, although source c7 introduces examples with These include. Added active-voice responsibility rules are not explicitly established by the selected passage.

## qwen3:4b-instruct-2507-q4_K_M / calibration_08 / reversed

supported_core: citation_overselection, local_citation_support_incomplete

Core rejection, general aim and exceptions are covered. Some claims about specialist-term permission and first-use explanation appear in general-aim slots without c3 among those slot citations.

## gemma3:4b / calibration_05 / canonical

supported_core: implicit_scope_decision, citation_overselection

Correct Chinese sample and percentage; rejects worldwide scope implicitly rather than giving an explicit negative decision. Component-risk c19 is an unnecessary supporting citation.

## gemma3:4b / calibration_05 / reversed

needs_correction: material_factual_error, scope_generalization, cross_part_contradiction

Incorrectly says the percentage can describe cities worldwide while the next part correctly identifies the Chinese sample. Valid IDs and completed slots failed to detect the unsupported generalization.

## gemma3:4b / calibration_06 / reversed

protocol_failure: missed_required_abstention, unsupported_absence_attribution, citation_overselection

No numeric threshold is invented, but the model marks the part answered and claims the full guidance does not state one. The supplied excerpts do not establish full-document absence; required insufficient_evidence/exact-abstention behavior is not followed.

## gemma3:4b / calibration_06 / canonical

protocol_failure: missed_required_abstention, unsupported_absence_attribution, citation_overselection

No numeric threshold is invented, but the model marks the part answered and claims the full guidance does not state one. The supplied excerpts do not establish full-document absence; required insufficient_evidence/exact-abstention behavior is not followed.

## gemma3:4b / calibration_08 / canonical

needs_correction: local_citation_support_incomplete, source_misattribution

Passive-voice conditions are attributed to c2, which discusses vocabulary; the direct source is c7. The blanket-rule paragraph also omits c7. Added no-exceptions claims are unsupported and potentially confusing about the documented exceptions. The specialist policy weakens the needed condition to explained.

## gemma3:4b / calibration_08 / reversed

needs_correction: local_citation_support_incomplete, source_misattribution

First and specialist-term paragraphs quote or paraphrase c3 but cite c7/c2/c1 or c2/c1 instead. Their core content exists in context; the selected IDs fail to support those local claims. Passive-voice paragraph correctly cites c7.
