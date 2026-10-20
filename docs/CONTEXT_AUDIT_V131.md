# Saved-answer context diagnostic 1.3.1

This is a diagnostic component alongside grounded v1.3, not a replacement answering pipeline. It tests a specific failure hypothesis: requiring a concrete source witness and independently confirming each objection may reduce the broad context gate's false rejections. Its actual performance is unverified until the local model run is reviewed.

## Run from the existing project root

Use the activated project virtual environment and an available Ollama service with qwen3:8b installed.

```bash
python install_context_audit_v131.py .
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_context_audit_v131.py'
python evaluation/recheck_context_v131.py --latest
```

Run the third command only after the tests pass. The default reads the latest completed results/benchmark_v13_* directory. To choose a preserved benchmark explicitly, use --source PATH instead of --latest; PATH can be its directory or benchmark_bundle.zip.

For this reviewed benchmark, 13 saved substantive candidates and four negative controls are tested. Answers are not regenerated. The negative controls contain three saved incorrect answers and one explicitly labelled synthetic travel-policy error. They test hidden opposing evidence, overstated certainty, invented deadline time and removed qualifications. They are known development controls, not held-out cases.

## What changes

The installer adds a diagnostic module, runner, 13 tests, control definitions, this guide and the saved v1.3 source review under results/reviews/v13_qwen8b_20261016/. Existing answering modules and the demo are unchanged. It checks the expected installed baseline and v1.3 module hashes before making changes. Its backup manifest records any README/gitignore edits and added files.

The critic reviews all code-extracted original source paragraphs in bounded batches. It can return no objections. Each proposed objection must select an allowed paragraph handle; code copies its witness text and source mapping. A separate model call then checks whether that objection invalidates the whole candidate, is already addressed, is outside scope, is not established, or remains uncertain. No model-written quote is accepted. An explicit unresolved source conflict is an acceptable answer when the question requires reporting the conflict.

All stages enforce the 6000-byte input bound and 512-token output limit. Indivisible passages that cannot fit cause a recorded failure; they are not silently truncated. There are no automatic retries or selective answer regeneration. Control expectations are recorded outside model messages.

## Saved output and interpretation

Outputs are checkpointed after each task under results/context_recheck_v131_<timestamp>/. The final context_recheck_bundle.zip contains JSON/CSV summaries, original benchmark inputs, exact prompts/options/schemas, raw responses, source paragraph mappings, objections and confirmation judgments. Share that ZIP for source-based review.

- context_clear: this audit did not confirm a material context objection. It does not certify factual accuracy or citation support.
- context_objection_confirmed: at least one confirmation judged the candidate invalidated by its source witness.
- context_uncertain: an unresolved confirmation remains and no objection was confirmed.
- context_review_failed: an input, transport, completion or schema failure prevented a complete audit.

The reversed 503 candidate has a citation-support defect even if this context-only audit returns context_clear. Citation checking remains a separate unresolved component. The two authentication candidates should trigger a real context objection. The other eleven saved substantive candidates should not be rejected by this context-only test; this expectation does not approve every citation in those answers.

A successful outcome requires reducing false objections while still catching all four known negative controls. Merely making all answers pass is a failure. The same model proposes and confirms objections, so correlated errors remain possible; this is a separate call, not independent verification. Cross-batch relationships and larger unseen documents also remain unproven. The 13 automated tests use controlled responses and validate mechanics, not factual reasoning quality. Do not report this diagnostic as a solved factuality system or deploy it as an answer gate before reviewing actual results.
