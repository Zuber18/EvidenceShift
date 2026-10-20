# Reproduce and inspect

## Read the existing results

Start with `results/published/README.md`. The manifest records SHA-256 hashes
for selected reports and raw records. Run `python scripts/check_repository.py`
to check those hashes, frozen source files, confirmation pairing and record
counts without loading an encoder or calling a model. It is an integrity check,
not an independent recomputation of factual judgments.

## Environment and software checks

Use Python 3.12. Existing work was run on a MacBook Pro M2 Pro with 32 GiB RAM.
The project dependency ranges permit installation; they do not recreate an
exact historical environment. Do not substitute today's package versions for
missing run metadata. The consolidation report records available local
distribution versions without credentials or environment variables.

```bash
python -m pip install -e '.[test,local]'
PYTHONPATH=src:. python -m pytest -q tests
python compare_evidence_models.py --self-test
python run_direct_answer_baseline.py --self-test
python run_direct_confirmation.py --self-test
```

Tests use controlled inference and encoder/store responses where declared.
The API/store tests exercise Chroma with a test encoder, not the real MiniLM
model. Software-test success does not supersede observed semantic failures.

## Optional new inference runs

Existing results are frozen: no inference rerun is needed for consolidation.
To conduct a separately recorded replication, keep Ollama running and install
the explicitly required model tags. The scripts do not pull models themselves.

```bash
python compare_evidence_models.py --phase development
python run_direct_answer_baseline.py
python run_direct_confirmation.py
```

The first command requires Qwen 3 4B, Qwen 3 8B and Gemma 3 4B and records
60 model calls plus six code controls. The second records 30 calls plus three
controls. The last records 16 Qwen 8B calls plus one control and enforces the
selected model digest and frozen baseline runner hashes. Do not use the
matrix runner's older ID-selection confirmation mode to replicate the direct
confirmation. Interrupted-run resume requires the matching saved run folder:

```bash
python run_direct_confirmation.py --resume results/<matching_run_folder>
```

Direct options: temperature 0, seed 42, num_ctx 32768, num_predict 2048,
think false. Confirmation Qwen digest:
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
If the installed tag resolves differently, preserve that fact as a different
run rather than editing the frozen check. The server version observation
failed in the original confirmation; its model digest/options were recorded.

## Retrieval and ingestion

The fixed-context comparisons do not exercise retrieval. The separate
`evaluation/run_document_e2e.py` evaluates document ingestion/retrieval with
actual generated TXT/PDF/DOCX fixtures and frozen generation. See
`docs/DOCUMENT_E2E.md` for its own setup and saved assessment.

The local viewer uses the shared semantic stack and a measured local identity
lock under `config/local_embedding_lock.json`. The lock is machine/environment
specific and remains untracked. A public reference observation records the
original fingerprint, not a portable replacement lock. Do not copy it over a
new machine's measured identity to bypass a mismatch.

Session exports can contain the entire uploaded source document. Local indexes,
weights, credentials, uploads and raw local result folders are not repository
assets. Publication artifacts are an explicit selected copy; originals stay
in place. Historical reports describe the decision at that point in time.
