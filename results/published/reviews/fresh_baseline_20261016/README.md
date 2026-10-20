# Fresh baseline source review

**The fresh run exposes answer quality clearly, but does not establish reliable factuality.**

| Nonempty-context outcome | Count |
| --- | ---: |
| Supported core content | 13/16 |
| Material factual error | 2/16 |
| Selection/generation contract failure | 1/16 |

The 13 core-supported outcomes comprise 11 substantive answers and two justified abstentions. Two have presentation caveats: the reversed precedence answer gives the correct date without explaining the override; the reversed dispatch answer attributes both dates but does not explicitly label the unresolved disagreement and uses supported as its response type. These caveats are retained rather than silently treated as full rubric success.

Eight additional no-context records are deterministic code controls and are excluded from reasoning counts. No production answer was delivered by this evaluation.

## Material findings

- Both build-receipt orders incorrectly say that the build has started. The selected and cited rule explicitly says receipt does not confirm execution and a queued build may never run. Retrieval or evidence availability cannot explain this error in the fixed-context test; it is introduced during generation.
- Optional email, retention exceptions, human/service-account access distinctions, and the 16-credit calculation are correctly handled in both orders. The calculation is a supported derivation using the quantity in the question and the allowance/rate in the cited source.
- Explicit precedence correctly yields 12 November 2028 in both orders. Only the supplied order explains that the newer notice explicitly replaces the other notice; recency alone is not used as the review rule.
- Supplied dispatch is a mechanical failure: selection says supported, generation says conflict, and the preserved baseline validator rejects the mismatch. The raw generated text contains both dates, but it is not counted as a completed candidate. Reversal renders both attributed dates while keeping the inappropriate supported category.
- Both nonempty-context access-code questions receive the justified prescribed abstention.

## Citation support

There are 28 rendered claims: two are contradicted by their citations; the other 26 have a supporting cited basis, including four claims that use arithmetic with the question. One of those 26 also carries an irrelevant extra citation: the reversed build answer cites the identifier/status passage alongside the operative rule for the no-success-guarantee claim. A supporting citation set does not make every citation in that set useful.

Do not headline 26/28 as a reliability score. Claims are correlated, verbosity changes the denominator, and an answer containing one material false statement remains materially wrong. Detailed answer-level and claim-level assessments are saved separately.

## Mechanical verification and limits

All 30 calls returned schema-valid outputs with stop completion. Actual inputs reached at most 2123 bytes, below the 6000-byte cap. Summed stage time was 81.31 seconds, not a hosted latency measurement. The frozen plan and baseline hashes, source hashes, context orders, selected quotations and 15 nonempty rendered candidates were recomputed. The one dispatch contract failure was reproduced. The generation prompts match the preserved baseline; no model-verifier call occurred.

Seven pairs produce candidates in both orders with agreeing core conclusions; agreement includes the wrong build answer. The dispatch pair changes in completion/labels. These are observations from one fixed run, not a general source-order invariance claim.

The cases are fresh synthetic fixed contexts, not independently held-out real-document evaluation. They bypass semantic retrieval. These results cannot establish retrieval quality, hosting parity or improvement over earlier different case sets.

## Next phase

Preserve this run and stop selective prompt retries. Test the real document path: TXT/PDF/DOCX ingestion, source/page metadata, semantic retrieval of all required supporting and opposing evidence, then the same frozen answer generation on retrieved context. Assess factual correctness and claim-level citation support separately. Keep the known build negation error, dispatch contract failure and presentation caveats visible in project results. Code checks and model audits must not be labelled factual certification.
