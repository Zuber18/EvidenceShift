# V2 tool pilot review

V2 restores the baseline citation protocol and produces correct Python traces. It does not resolve factual reasoning or context-order sensitivity.

| Observation | Saved result |
|---|---|
| Generation attempts | 17: two planner calls, 15 answer calls |
| Factual answers with bracket citations | 13 of 13; citation presence alone is not entailment |
| Appropriate exact abstentions | Both Flesch-score answers |
| Python traces | Both correct; one falsely blocked by punctuation-sensitive parser |
| Arithmetic | Canonical correct 4.15 hours/week; reversed selection refused |
| Non-tool answers | All 12 exactly reproduce the earlier reranked baseline |
| Remaining semantic gaps | One contradictory scope answer; two incomplete revision policies |

The reversed planner chose the results passage rather than the requested abstract and attached hours/week to a quote printing hours. The broader passage does describe weekly durations; the failure is of requested-section adherence and the strict literal-anchor contract, rather than proof that the underlying values are wrong. The guard preserved the failure and prevented an answer from being generated.

The reversed Python answer is correct. The old output parser rejects the comma after each backtick-quoted print call. A punctuation-only offline audit matches both traces, while retaining original blocked status and raw text. Eight offline parser tests cover normal formats, wrong values, negation, omitted/reordered/extra calls and preservation of the input.

The canonical heat-risk answer first states that the result is about Chinese cities, then says the evidence cannot answer whether it applies worldwide. This paraphrased contradiction passes the mechanical abstention check. Both editing-policy answers preserve the two exceptions but omit the available general plain-English/accessibility requirement from the requested policy. The excluded general active-voice passage is a separate retrieval gap.

Next work: retain the offline checker correction without regenerating answers; then test a source-anchored operand candidate selector on development examples, alongside claim-level contradiction and required-coverage review. Define the new protocol before additional generation. Keep the reserved split untouched. Fine-tuning is not justified by this pilot.

These are eight exposed development questions in two orders with one model. No representative accuracy estimate or claim of resolving hallucinations is made.

## calibration_01 / canonical

Supported within the requested scope.

Core answer supported by the supplied cited passage(s).

## calibration_01 / reversed

Supported within the requested scope.

Core answer supported by the supplied cited passage(s).

## calibration_02 / reversed

Supported within the requested scope.

Core answer supported by the supplied cited passage(s).

## calibration_02 / canonical

Supported within the requested scope.

Core answer supported by the supplied cited passage(s).

## calibration_03 / canonical

Supported within the requested scope.

Supported in the question’s omitted-argument scope. New-list wording should remain conditional on L being omitted or None; an explicitly supplied list can still be shared.

## calibration_03 / reversed

Supported within the requested scope.

Supported in the question’s omitted-argument scope. New-list wording should remain conditional on L being omitted or None; an explicitly supplied list can still be shared.

## calibration_04 / reversed

invalid_tool_selection, requested_section_not_followed

Planner cited results c33 instead of abstract c1 and labelled quantities hours/week although the selected literal quote prints hours. The passage does describe weekly durations, but the strict literal-anchor contract correctly refused the selection. No answer generated; no retry.

## calibration_04 / canonical

Supported within the requested scope.

Abstract c1 supports 6.26 minus 2.11 = 4.15 hours/week and the direction self-reported higher than logged.

## calibration_05 / canonical

contradictory_partial_abstention

First sentence correctly restricts the result to the Chinese sample, then the final sentence says evidence does not answer that very scope question. The literal exact-abstention detector misses this paraphrased contradiction.

## calibration_05 / reversed

Supported within the requested scope.

Core answer supported by the supplied cited passage(s).

## calibration_06 / reversed

Supported within the requested scope.

Appropriate exact abstention: supplied passages do not establish a minimum Flesch Reading Ease score.

## calibration_06 / canonical

Supported within the requested scope.

Appropriate exact abstention: supplied passages do not establish a minimum Flesch Reading Ease score.

## calibration_07 / canonical

Supported within the requested scope.

All three printed lists [1], [2], [1, 3] and the separate explicit-list explanation are supported by source c35 and the deterministic trace.

## calibration_07 / reversed

checker_false_rejection

All three printed lists [1], [2], [1, 3] and the separate explicit-list explanation are supported by source c35 and the deterministic trace. Commas between code and outputs break the old parser; the offline punctuation-only audit correctly matches all lists. Original blocked status retained.

## calibration_08 / reversed

incomplete_requested_policy

Both exceptions are correctly supported by c3 and c7, but the requested revised policy omits the general plain-English/accessibility aim supported by c0/c1/c2. The general active-voice preference passage c6 was excluded from the reranked context; that retrieval limitation is separate from the omission of available clarity guidance.

## calibration_08 / canonical

incomplete_requested_policy

Both exceptions are correctly supported by c3 and c7, but the requested revised policy omits the general plain-English/accessibility aim supported by c0/c1/c2. The general active-voice preference passage c6 was excluded from the reranked context; that retrieval limitation is separate from the omission of available clarity guidance.
