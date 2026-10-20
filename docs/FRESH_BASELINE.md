# Fresh baseline candidate evaluation

This experiment freezes the answering component and evaluates it separately from model-based verification. It reuses the installed grounded 1.2.1 selection prompt, generation prompt, schemas, evidence extraction, citation assignment and mechanical validation. The unreliable verifier is omitted. This is therefore a generation-only experiment, not an identical end-to-end rerun of 1.2.1 and not an automatic factual-approval system.

## Run

Save install_fresh_baseline.py in the existing project root. With the project virtual environment activated and Ollama running:

```bash
python install_fresh_baseline.py .
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_fresh_candidates.py'
python evaluation/run_fresh_baseline.py
```

Run the last command after the tests show OK. The frozen model is the already-installed qwen3:8b. There are no new dependencies, paid APIs or prompt revisions. Baseline options remain temperature=0, seed=42, num_ctx=8192, num_predict=4096 and think=false. No automatic retries or selective regeneration occur.

The plan has eight fresh fictional scenarios: build receipt versus execution success, optional export email, a retention exception, conditional workspace access, a processing-credit calculation, explicit document precedence, unresolved dispatch dates and a missing access code. Source texts are stored under evaluation/fresh_sources/ and snapshotted in the plan. Each case has supplied, reversed and no_context variants: 24 records, including eight deterministic empty-context controls. At most 32 model calls are needed. A selection of insufficient evidence skips answer generation and is still subject to source-based assessment later.

These are fresh fixed cases authored after the earlier experiments. They are not an independently held-out benchmark. Freeze the plan before the first run; keep the snapshot and raw outputs even when answers fail. Do not change prompts or sources to rescue individual outcomes.

## Scope

Supplied and reversed contexts are fixed passages, not new retrieval results. This isolates answer generation under evidence ordering. MiniLM/Chroma retrieval, ingestion, prior results, installed answering routes and the demo remain unchanged. A later end-to-end upload/retrieval evaluation is still required; this run cannot establish retrieval accuracy or hosted performance.

The experiment calls only the preserved baseline selection and generation stages. It records a candidate after code checks succeed; it never sets a delivery_answer or calls a semantic verifier. Removing that verifier prevents its judgment from hiding the candidate during evaluation. It does not repair hallucinations, omissions, false abstentions or citation entailment errors.

## Results and review

Everything saves under results/fresh_baseline_<timestamp>/. JSON, CSV and report.md are checkpointed after each case variant. The final fresh_baseline_bundle.zip includes the frozen plan, full original contexts, exact prompts/schemas/options, raw model outputs, selected quotations and claim-to-source mappings. Upload the ZIP for source-based assessment; no separate Word document is needed.

Mechanical checks establish allowed handles, original copied quotations, code-rendered citation IDs, schema validity and completed generation. They do not establish that cited text supports the meaning of a generated claim. Even a deliberately unsupported claim can satisfy these mechanical checks; an automated test verifies it is never labelled factually approved.

Assess each nonempty-context answer on factual correctness, necessary conditions, completeness for the question, claim-by-claim citation support, and justified abstention or conflict handling. Report these dimensions separately. Empty-context controls are code behavior, not evidence of model reasoning quality. The report retains all original context so omitted opposing evidence can be identified even if the model never selected it.

The 13 component tests use controlled model responses. They test prompt preservation, provenance, handle validation, failure retention and report saving. They do not measure Qwen's factual accuracy. Semantic results await the real local run.

## Experimental decision

The verifier experiments through context-audit-1.3.2 remain frozen diagnostics. Do not promote them as automatic answer gates or reinterpret inconclusive outputs as correct answers. The new evaluation does not delete or modify those experiments. After source-based assessment of this fixed run, consolidate the observed results and limitations, then test the actual document ingestion/retrieval path before public-demo claims.
