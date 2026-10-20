# Qwen 8B context diagnostic 1.3.1 — source review

**Decision: improved on some cases, still unsuitable as an automatic answer gate.**

| Measure on frozen development cases | Original v1.3 gate | Context diagnostic |
| --- | ---: | ---: |
| Supported core candidates falsely rejected | 10/10 | 4/10 |
| Supported core candidates cleared | 0/10 | 6/10 |

The diagnostic missed both erroneous authentication comparisons. All four known negative controls received rejection flags, but only three had at least one sound source-based confirmation. The hidden-deadline control received the expected flag for an invalid reason: the confirmation says the candidate is supported while emitting the rejection enum. Thus 4/4 flags cannot be reported as four reliable detections.

The four remaining false rejections are retrieved 202, travel conditions, and both deadline orders. The model still treats fictional-source labels as invalidating valid scenario reasoning. It also confuses whether “invalidates” applies to the answer or to the objection. A separate architectural gap is that confirmation only sees the selected witness's parent sources: a conflict across two sources cannot reliably be confirmed when the opposing source is absent.

The reversed 503 candidate still has a citation-support defect. Its context-clear result is not an approval of its citations. The per-record review separates this issue from the context check.

All 43 raw responses passed local schema validation and finished with stop. The maximum actual input was 5976 bytes against the 6000-byte budget. Original benchmark hash, preserved candidates/context, paragraph catalogs, witness mappings and complete review coverage were recomputed. These mechanical successes did not prevent semantic failures. Summed generation-stage time was 155.88 seconds, not a hosted latency estimate.

## Next controlled comparison

Run from the existing project root with the virtual environment activated and Ollama running:

```bash
python evaluation/recheck_context_v131.py --latest --model gemma3:4b
```

This uses the already-installed diagnostic runner and Gemma model. It rechecks the same saved Qwen candidates and four controls without changing prompts, regenerating answers or altering delivery. It automatically creates a separate results/context_recheck_v131_<timestamp>/ directory and context_recheck_bundle.zip. Share that new bundle for a source-based comparison.

This is a single checker-model comparison, not another prompt revision. Its purpose is to measure whether the current checker is the bottleneck before changing the architecture. Review both outcomes and their reasons; do not choose a checker merely because it accepts more answers. No claim is made that Gemma will succeed. Neither model audit should serve as an automatic factual certificate. An eventual revised verifier needs an explicit candidate-error target, source sets sufficient for the alleged conflict, and failure behavior that preserves uncertainty. These remain design requirements, not implemented fixes.

The counts are on known development cases only. A held-out evaluation and end-to-end run remain necessary before release claims.
