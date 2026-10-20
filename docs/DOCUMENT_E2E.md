# Real document ingestion and semantic retrieval evaluation

This suite exercises the installed FastAPI upload and search routes in process, then passes the actual search results to the frozen fresh_candidates generator. It uses the existing build_engine(data_root=...) implementation, MiniLM embeddings, token-aware LangChain splitting and Chroma cosine search. No TF-IDF, alternate vector index, prompt tuning or semantic approval gate is introduced. The deployed /answer route and browser demo are not modified or tested by this suite.

## Run

Save install_document_e2e.py in the existing project root. With the project virtual environment activated and Ollama running:

```bash
python install_document_e2e.py .
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_document_e2e.py'
python evaluation/run_document_e2e.py
```

Run the last command only after the tests show OK. The already-installed qwen3:8b model and MiniLM model are used. Existing dependencies include pypdf, python-docx, FastAPI, httpx, Chroma, LangChain splitters and sentence-transformers. The suite does not install or upgrade anything. Existing user documents, indexes and answering modules remain untouched.

## Test design

The eight frozen fresh scenarios supply sixteen source texts. The suite writes all sixteen as TXT, PDF and DOCX, producing 48 fixture files. These are generated evaluation documents, not real-world or independently held-out data. Each PDF has a shared heading on page 1 and operative evidence on page 2. DOCX uses ordinary paragraphs and is unpaginated. Equivalent logical text can have different page/chunk boundaries, so identical cross-format rankings are not assumed.

Each format receives its own isolated index under the current run directory. All sixteen documents are uploaded through POST /documents; chunks and the document catalog are read through their API routes. One duplicate upload per format checks deduplication. File hashes, deterministic document/chunk identifiers, source labels, physical PDF page numbers and full operative-text extraction are checked. TXT/DOCX must retain page 0, rather than invented physical page numbers.

For each of the eight questions, POST /search searches the whole sixteen-document format corpus with top_k=5. No case document filter, gold IDs or expected answer is sent. Search results are compared with the saved indexed chunks. Post-search evidence coverage requires both the expected document ID and the exact whitespace-normalized operative text. Multi-source questions require all listed evidence units. The access-code question has no positive answer evidence, so its recall is undefined rather than scored as an automatic success.

Required-evidence labels cannot change retrieval or candidate prompts. Generation uses the fixed earlier selection/generation prompts, options and mechanical checks. No context is silently dropped to meet an input budget; an oversized model input is retained as a recorded failure. A complete run creates 24 answer records: eight questions across three formats, with at most 48 model calls. Existing empty-context and reversed-order controls are not repeated here.

## Saved results

Everything is stored under results/document_e2e_<timestamp>/:

- setup.json, frozen_plan.json and requirements.json record the profile, versions, hashes, model inventory and evaluation plan.
- fixtures/ retains the exact uploaded TXT/PDF/DOCX bytes.
- results.json includes parsed chunks, provenance checks, indexed metadata, search hits, evidence coverage and generated candidates.
- results.csv separates retrieval coverage, candidate mechanical status and errors.
- runs/ contains exact model prompts, schemas, raw outputs, quoted evidence and claim-to-source mappings.
- report.md is a readable answer/evidence report.
- document_e2e_bundle.zip contains the reviewable run files and fixtures. Generated indexes are excluded from the ZIP and from Git tracking.

JSON/CSV checkpoints are written after ingestion and each answer record. Startup and per-format failures are retained in the final bundle. The command exits unsuccessfully if a format cannot be evaluated; upload the saved bundle even in that case. Mechanical candidate failures remain recorded findings and never authorize delivery.

## What the results mean

Extraction checks establish fixture fidelity and metadata, not support for generated claims. Exact required-text coverage measures whether known evidence survived retrieval; it is not semantic relevance, citation entailment or factual accuracy. Nonempty retrieval does not establish that the question is answerable. Both answer quality and claim-level citation support still require source-based project assessment.

The ten component tests exercise the real PDF/DOCX parser on generated files and use controlled API/model responses for orchestration. They do not establish actual embedding quality, Chroma rankings or Qwen reasoning. Those are measured by the local run. Earlier API/demo retrieval parity was a separate small-corpus experiment; this suite does not establish hosting capacity or browser/network behavior.

The known build-receipt negation error, dispatch answerability mismatch and presentation caveats remain frozen limitations. This suite does not repair them. Its purpose is to identify whether any additional failure occurs during extraction, retrieval or generation. Do not silently change top_k, sources, prompts or model to rescue individual results.
