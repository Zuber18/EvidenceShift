# Local upload demo using the evaluated generator

This is a new local entry point alongside the previous cloud prototype. It uses Ollama qwen3:8b, the evaluated fresh_candidates selection/generation component, and the existing shared MiniLM/token-aware LangChain/Chroma retrieval implementation. It does not alter the API /answer route or the cloud app. There is no model-based factual approval gate and no new answer prompt.

## Install and start

Save install_local_upload.py in the existing project root and use the project virtual environment:

```bash
python install_local_upload.py .
python -m pip install -r requirements-local-upload.txt
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_local_upload.py'
python -m streamlit run web_demo/local_app.py
```

Start the UI after the tests show OK. Ollama must be running with qwen3:8b installed for normal answer generation. The service requires a loopback OLLAMA_HOST URL; the default is http://localhost:11434. Search inspection and the no-context code control do not call Ollama. The existing MiniLM model must be available to the shared loader; it may load from the existing cache.

## First representative-document smoke test

Open the local URL printed by Streamlit. Upload a few representative documents, click Process documents, and ask three to five questions. Include a straightforward fact, a condition or exception, and something the documents do not answer. Multiple documents share an isolated workspace so cross-document evidence can be inspected. Keep the default retrieved order for the initial test; the sidebar also exposes reversed and no_context controls.

Inspect the original source passages rather than treating citation membership as proof. The baseline generator's build-receipt negation error and supported/conflict label mismatch remain known limitations. No code silently repairs a failed candidate or retries to obtain a more favorable result. Large retrieved evidence can exceed the generation input cap; that remains a saved failure rather than silently dropping sources.

Click Prepare complete session export and Download documents, answers and evidence report after all questions. Share local_upload_smoke_bundle.zip for source-based assessment. The ZIP contains uploaded source bytes, exact questions, retrieval hits, candidate claims/citations, model inventory, embedding identity and raw stage traces. Local saving of source bytes is explicit in the UI.

## Files and isolation

Up to eight unique documents can be processed from PDF, DOCX, TXT or Markdown. Limits: 5 MiB per file, 20 MiB combined uploads, 100,000 combined extracted characters, 50 text-bearing pages per document. Identical documents are deduplicated. PDFs must have extractable text; OCR is not included. DOCX/TXT remain unpaginated.

The shared API store factory supplies the existing encoder, tokenizer-based splitter and Chroma search. Each workspace searches only its uploaded document IDs and uses top_k=5. The encoder is serialized across local sessions. Temporary indexes live under data_local/upload_sessions/ and are removed when Clear current workspace is used. Session artifacts and source bytes remain under results/local_upload_session_<timestamp>/. Closing a browser tab is not promised to delete saved artifacts.

Each question saves runs/<run>/run.json, report.md and a complete generator trace. summary.json and runs.csv update automatically. The full-session ZIP is saved in the session folder and excludes temporary indexes and redundant nested ZIP files. It includes every question in that workspace, not just the last displayed answer. Starting another workspace creates another saved session.

## Measured embedding identity

On the first workspace, the service hashes the exact loaded parameter bytes with their names, dtypes and shapes. It also hashes tokenizer configuration and records pooling/module configuration, maximum input length, retrieval settings and relevant package versions. This measurement is cached for the loaded encoder, which the service treats as immutable. Saved model tensors are not included in the report.

The measured identity is recorded in config/local_embedding_lock.json and embedding_identity.json in each saved session. Subsequent workspaces refuse a different fingerprint instead of replacing the lock silently. If the configuration changes intentionally, preserve the existing lock and results for comparison before recording another identity. Clearing a workspace does not reset this lock.

This fingerprint identifies the local loaded parameter/configuration state. It does not infer a Hugging Face commit when revision metadata is null, pin a remote Hub snapshot, guarantee bitwise output across environments or certify model behavior. Exact Hub revision pinning remains a separate deployment task. Ollama's model inventory, including any returned model digest, is recorded for each normal generation run.

## Validation scope

The thirteen unit tests use controlled parameter arrays, model responses and store/search results, plus the actual TXT parser. They establish service contracts and report provenance; they do not exercise a real Torch encoder, live Streamlit browser state or Ollama inference. The existing three-format ingestion/retrieval run separately passed the small fixture corpus. The first real-document UI session is the next validation step.

This is a local experimental demo. No hosting, Groq credential, public deployment or factual-accuracy guarantee is implied by installing it. Original cloud/API entry points and all frozen benchmark outputs remain preserved. Repository consolidation and free-host capacity testing follow representative-document review.
