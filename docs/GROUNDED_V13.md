# Grounded pipeline v1.3.0

This version addresses observed pipeline failures from the frozen Qwen 4B, Qwen 8B and Gemma 4B comparison. It is an additive local experiment. The v1.2.1 module, case plan, saved runs, semantic retrieval and current upload demo are preserved. The demo still uses v1.2.1 generation until a validated integration is made explicitly.

## Changes

- Generation schemas enumerate the validated E handles. Local checks still reject unknown/duplicate handles; invalid output is not guessed or repaired.
- Each claim is reviewed separately against its full cited source passages. Code attaches the claim index; the model cannot renumber it or add unrelated claim judgments.
- Every original retrieved passage, including uncited passages, is included in a separate context review before an answer can be delivered. Relevant opposing facts and lost qualifications are checked here.
- Abstention has a separate answerability contract. It has no claim indexes and does not need to provide an unknowable fact to satisfy a coverage boolean.
- Conflict-labelled answers receive an explicit conflict introduction in their rendered text. The model still has to select and report the opposing statements; a label alone is not enough.
- Full passages are packed into bounded batches. Nothing is silently clipped. If an individual passage or candidate cannot fit, the run blocks with a saved error.
- Verification responses have a 512-token output ceiling, while selection/generation retain source settings (4096 in the fixed plan). Each effective request is logged.

## Run

After applying the installer in the existing project root:

```bash
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_grounded_v13.py'
python evaluation/run_benchmark_v13.py --models qwen3:8b
```

Keep Ollama running. No additional model download or cloud API key is needed. The benchmark saves JSON/CSV after every input and a final `benchmark_bundle.zip` under `results/benchmark_v13_<timestamp>/`. Interrupted runs retain checkpoints but may lack the final bundle. Original cases, evidence order, labels and the v1.2.1 case file remain unchanged. Review labels are not supplied in model messages.

The full 22-input development regression batch is intentional: it can reveal new regressions as well as improvements. It is not a held-out benchmark. Once reviewed, test fresh documents and unseen questions separately. Do not claim generalisation from these reused cases.

## Status and provenance

`candidate_ready` means that all required structural and advisory checks completed and permitted delivery. It is not factual certification. `blocked` preserves the candidate (when one exists), stage outputs and error. Empty context still yields a deterministic code abstention without model calls.

The saved run includes original source snapshots, settings, prompts, raw stage outputs, model inventory, evidence quotations, claim verdicts, context/abstention batches, coverage decisions and final rendering. `context_review_complete` is true only after all original context batches were checked, or when the context was empty. A failed earlier claim check may stop the pipeline before context review; such a run cannot be delivered.

## Limits

Semantic checks remain fallible model judgments, particularly with a same-model checker. Moving a field into a schema does not establish its factual truth. These changes enforce the review structure and evidence visibility; real Qwen results are still required to measure the effect.

When cited evidence must be split, at least one full batch must support the complete claim and no batch may contradict it. A claim requiring a cross-batch inference can therefore be conservatively blocked. An abstention is blocked if any batch supplies answering information or is uncertain, including partial premises. Context checks can still miss cross-batch relationships. All such batches and decisions are saved for assessment.

The original 6000-byte input proxy is retained; it is not an exact token count. Oversized indivisible inputs block rather than causing hidden truncation. This does not guarantee that every future document will fit. More checks mean more generation calls and runtime. No retries, fallback model, automatic factual rewriting or quota bypass is implemented.

## Validation completed before delivery

- 45 software tests passed: 23 v1.3 regression tests with simulated model judgments and 22 existing grounded tests.
- Installer checks passed for backups, repeat application, preserved baseline/cases/results, and refusal of an unexpectedly modified baseline.
- Direct reproduction of the saved authentication cases that exceeded v1.2.1 verification budgets: all full sources fit the new batching plans.
- Offline planning for all 14 evidence-bearing Qwen 8B baseline outputs: maximum verification batch size 5959 bytes, below the unchanged 6000-byte cap.
- Real local model generation for this version has not been run in this environment.

Tests verify behaviour when judgments are correct, rejecting, uncertain or malformed. They do not demonstrate that a real model reliably identifies invented times, certainty errors or hidden conflicts. The next saved Qwen 8B run provides that evidence.
