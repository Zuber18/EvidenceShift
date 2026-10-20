# Anchored advisory audit 1.3.2

This adds a diagnostic alongside the existing pipeline. It revises the verifier contract after the Qwen/Gemma comparison showed invented target claims, inverted verdict meanings and incomplete conflict evidence. It does not change retrieval, regenerate answers, approve delivery or certify factual correctness.

## Install and run

Save the installer in the existing project root. With the project virtual environment activated:

```bash
python install_context_audit_v132.py .
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_context_audit_v132.py'
python evaluation/recheck_context_v132.py --latest
```

Run the last command only after tests show OK. Ollama must be running with qwen3:8b already installed. The runner uses the most recent completed results/benchmark_v13_* directory. Use --source PATH instead of --latest to select the exact original directory or benchmark_bundle.zip explicitly. It never reads a previous diagnostic as its benchmark source.

For the reviewed benchmark there are 25 tasks: 13 saved substantive answers, four known negative controls, and eight new regression controls in four supported/incorrect pairs. The pairs cover negation, optional behavior, conditional access and opposing source dates. They are authored development controls, not a held-out test set. Expected labels are kept out of the model messages. No new dependencies or hosted services are required.

## Code-enforced changes

Each complete nonblank candidate line receives a C handle. These units are not assumed to be atomic factual claims. An objection can select a handle but cannot supply a replacement quotation. Code copies that exact original line into the saved review and passes its citation-aliased equivalent to the model. The full candidate remains available for interpreting context and an already reported conflict. This anchors the target; it cannot guarantee the model interprets negation correctly.

Objections select one to three allowed paragraph handles. Code copies their witnesses and full parent passages. The explicit confirmation verdicts are candidate_has_material_error, objection_not_demonstrated, and insufficient_evidence. The ambiguous invalidates enum is rejected. These names clarify the target; empirical testing is still required to assess whether verdicts and reasons agree.

For cross_source_conflict, at least two selected paragraph witnesses must include distinct original passage IDs. Both complete parent passages are supplied together. This is a provenance check, not proof that those passages genuinely oppose each other or are independent documents. If that witness set cannot fit the 6000-byte input bound, confirmation is recorded as inconclusive without dropping or separately judging one side. Repeated or unknown witness handles are rejected.

All original source paragraphs are reviewed in bounded critic batches. Cross-batch conflict discovery remains unproven and is explicitly recorded as not_established when there is more than one batch. The model may fail to propose an objection or select the wrong evidence; code does not claim otherwise. A claim of unsupported specificity cannot be established merely because one selected witness omits a detail that might exist elsewhere.

Each call preserves prompts, options, schemas, raw output and completion metadata. Output is limited to 512 tokens. No automatic retries, selective regeneration or hidden prompt changes occur. Exceeding an indivisible paragraph budget produces a recorded failure rather than silent truncation.

## Saved results

The runner checkpoints JSON and CSV after each task and writes a Markdown run summary. Results live in results/context_recheck_v132_<timestamp>/. The final anchored_audit_bundle.zip includes original benchmark snapshots, all controls, raw stages, exact targets, witness sets and confirmation outputs. Upload this ZIP for source-based review.

- advisory_no_error_reported means no material error was reported by this audit. It does not mean supported, factually correct or citation-verified.
- advisory_error_reported means the model confirmed at least one alleged error; it can still be a false objection.
- advisory_inconclusive means no error was reported but at least one required confirmation lacked evidence or remained uncertain.
- audit_failed means transport, completion, schema or planning failed.

When an error and an uncertain objection coexist, the status reports the error; both detailed judgments remain saved. No status authorizes delivery. The reversed 503 candidate's existing citation defect remains outside this context-only diagnostic's expected outcome. Claim-to-citation support still needs its own evaluation.

## Validation and release decision

The 19 automated tests use controlled model responses. They verify anchoring, handles, explicit verdicts, complete witness sets, budget behavior, saved provenance and the runner. They do not measure factual reasoning accuracy. The installer verifies expected existing module hashes, refuses conflicting additions before writing, and saves backups for README/gitignore changes. Existing answering modules, data and prior results are preserved.

Evaluate supported cases, erroneous candidates and negative controls together; accepting more answers alone is not success. Review verdict reasons as well as statuses. Keep the previous frozen results. A fresh held-out evaluation and end-to-end answer test are required before release claims. This diagnostic is not yet connected to the demo or production answer route.
