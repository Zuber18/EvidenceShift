# Validation — 13 October 2026

- 10 automated tests passed with real FastAPI TestClient, Chroma persistence, pypdf and LangChain text splitting.
- Tests cover scoped retrieval, upload validation, deduplication without re-embedding, persistence across reopening, embedding-error rollback, retry of partial ingestion, PDF page provenance, empty index behavior, evidence order reversal, no-context abstention, label separation, saved runs, unknown gold IDs, and context budgeting.
- Embedding and LLM calls in these tests use deterministic test doubles. This verifies mechanics, not semantic retrieval or model accuracy.
- Real RFC 9110 downloaded from its publisher (502,941 bytes), parsed and indexed in a temporary Chroma database; 833 chunks with the smoke test's 800-character/120-overlap splitter. Search returned five passages with test embeddings. The production tokenizer-based splitter will produce a different chunk count.
- The document and temporary index are not bundled. The notebook optionally downloads the real document on the user's machine.
- Editable package installation succeeded using pip's isolated build environment, with model dependencies omitted in the test environment. Full Mac dependency resolution and live MiniLM/Qwen execution remain to be verified locally.
- Python source, notebook code cells and pyproject TOML parsed successfully. Notebook output cells are intentionally empty.
- No claim of a passed real-document accuracy benchmark or a public live API is made.
