# Quantity selection review

Both canonical and reversed answers are supported on this development case.

| Check | Canonical | Reversed |
|---|---|---|
| Selected operands | 6.26 minus 2.11 | 6.26 minus 2.11 |
| Operand roles | Self-reported minus logged | Self-reported minus logged |
| Source units | hours/week | hours/week |
| Calculated difference | 4.15 hours/week | 4.15 hours/week |
| Supporting citation | c1, both labelled means | c1, both labelled means |
| Rounded discussion estimate used | No | No |
| Review verdict | Supported | Supported |

All four model calls completed normally. Frozen hashes, candidate IDs and offsets, source anchors, candidate ordering, request payloads and raw answer streams were checked. The two final answers are identical. No model calls were made during review.

The cited passage gives the self-reported mean as 6.26 hours/week and the logged mean as 2.11 hours/week. The answer states the correct difference and direction and cites that passage. The separate sentence restating the units is redundant but does not change the answer.

The previous v2 run failed reversed-order operand selection: it supplied hours/week for a selected quote printing hours. This candidate-ID run resolves source values and units locally and succeeds in both orders. Canonical numerical correctness is retained. Failed earlier outputs remain part of the record.

The saved runner still uses candidate_unverified and whole_answer_verified: false because its automatic checks do not certify semantic roles or every free-text claim. This separate review assesses these two saved answers as supported. The raw automatic status is preserved.

This is one exposed development question, one model, two passage orders and one generation per stage. It does not establish broad order invariance, repeatability, representative accuracy or resolution of hallucinations. The selector interface and prompt changed together; the run does not isolate their individual causal effects.

Next, preserve this result and address the remaining scope contradiction and incomplete policy answers through evidence planning. Keep model inputs free of expected answers and evaluate source support separately from automatic structural checks. Fine-tuning is not justified by these results.
