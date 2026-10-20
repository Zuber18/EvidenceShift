# Frozen checker comparison: Qwen 8B and Gemma 4B

**Decision: neither checker is suitable as an automatic factual gate. Stop model swapping on the current diagnostic contract.**

| Measure | Qwen 8B | Gemma 4B |
| --- | ---: | ---: |
| Supported core candidates falsely rejected | 4/10 | 8/10 |
| Supported core candidates appropriately cleared | 6/10 | 2/10 |
| Incorrect authentication candidates flagged | 0/2 | 2/2 |
| Authentication flags with a sound confirmation | 0/2 | 0/2 |
| Known negative controls flagged | 4/4 | 2/4 |
| Known negative controls with a sound confirmation | 3/4 | 0/4 |
| Generation calls | 43 | 55 |
| Sum of stage times, seconds | 155.88 | 163.45 |

These are source-reviewed counts on known development cases, not held-out accuracy. A matching rejection flag alone does not demonstrate detection of the actual error. Gemma's authentication flags target invented or defensible candidate claims. Its two control flags do not identify the planted certainty or time errors with sound confirmation reasoning. It misses the hidden deadline and the deliberately incorrect travel policy.

Gemma repeatedly reverses negative candidate claims, confuses optional behavior with requirements, and calls nearly identical source and candidate text contradictory. It correctly clears the travel answer and retrieved deadline conflict but falsely rejects the reversed deadline conflict. That conflict remains unresolved in the supplied scenario; fictional-fixture labels do not erase it.

All 55 Gemma responses passed local schema validation and ended with stop. The maximum actual input was 5976 bytes, below 6000. Both runs used the same saved candidates, questions, original passages, critic prompts, schemas and generation settings; the checker model differed. Original benchmark hashes, code-copied paragraph catalogs, witness mappings and full paragraph review coverage match. Valid JSON and source-handle membership do not imply valid inference.

The reversed 503 candidate retains a separate citation-support defect. Neither a context-clear result nor an unrelated rejection repairs it. Most order variants also contain different saved answer text, so those pairs do not all isolate source order alone.

## Next implementation

Correct the verifier contract before another model comparison:

1. Anchor each objection to an allowed candidate claim or sentence handle; code copies the exact target text. This prevents fabricated target quotations, though it cannot guarantee correct interpretation of negation.
2. Replace ambiguous invalidates labels with explicit candidate-error verdicts. The current enum sometimes accompanies a reason that says the candidate is correct.
3. Confirm alleged cross-source conflicts with both relevant source passages. A supporting passage alone cannot establish an omitted opposing source. If necessary evidence cannot fit, retain uncertainty.
4. Keep semantic audits advisory. Provenance, allowed handles, verbatim quote fidelity, schema validity and completion are code checks; factual inference remains empirically evaluated.
5. Retain these frozen results and evaluate the revised design on fresh held-out cases as well as the existing regression controls. Do not rerun this unchanged checker solely to seek better outcomes.

No answering pipeline was changed by this review. The paired comparison is complete; no further model run is requested at this stage. The next work is a code and test revision, with end-to-end evaluation still required before release claims.
