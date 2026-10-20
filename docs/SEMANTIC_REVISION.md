# Shared semantic retrieval

The demo uses the existing local API's `build_engine` to obtain the encoder, tokenizer-aware splitter and retrieval profile. It creates isolated temporary stores using the same `DocumentStore` class. No TF-IDF retrieval or character-based demo splitter remains.

The API factory gains an optional `data_root` argument; its existing no-argument behaviour is preserved. The shared parser gains DOCX body paragraph/table extraction. Existing PDF/TXT/MD parsing and chunk ID rules are unchanged. DOCX locations are unpaginated (page zero).

## Reproducibility

Default settings are MiniLM-L6-v2, normalized embeddings, the existing token-aware splitter (up to 180 tokens with 30-token overlap), Chroma cosine distance and top five results. `EMBEDDING_MODEL` and `EMBEDDING_REVISION` apply to both paths. Preserve the resolved revision and installed package versions when reporting comparisons. Matching source code alone does not establish cross-machine numerical equality.

Run from the project root:

```bash
python -m pip install -r requirements-demo.txt
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_grounded_release.py'
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_release_support.py'
python evaluation/check_retrieval_parity.py
```

The last command downloads the configured embedding model if uncached and runs real embeddings/Chroma on a small fixture. It makes no Ollama or Groq generation call. Results and a ZIP are saved automatically under `results/retrieval_parity_<timestamp>/`, including failures. Upload that JSON before proceeding to the answer baseline.

The fixture check compares document IDs, chunk text and metadata, complete retrieval profiles, top-five ordering and distances (tolerance 1e-5). A mismatch needs investigation; tied nearest neighbours can have different ordering. Passing is evidence for this fixture, not proof of universal parity.

## Remaining differences

- The public demo has stricter upload/text limits and temporary, per-document storage. Local API data remains persistent.
- The demo and local API share retrieval. The grounded v1.2.1 experiment remains separate from the older single-answer API generation path.
- Cloud inference is still Groq; local inference is Ollama. Models and provider reasoning options differ and are logged. The cloud output ceiling is 4096 tokens, matching the local grounded ceiling, but provider schema/transport semantics and context management are not identical.
- Context omission and stage byte caps remain recorded. Same-model factual checks remain advisory.
- The shared parser extracts DOCX paragraphs and tables, not tracked changes, text boxes, embedded objects or reliable page numbers.

## Storage and lifecycle

Each processed demo document gets its own temporary directory, Chroma collection and source copy. New document ingestion closes the previous session document; the Clear button deletes that collection and temporary directory. Abrupt termination or a disconnected browser is not a reliable immediate cleanup signal. Server restarts and temporary-directory lifecycle govern residual temporary data. This is not durable storage or a provider-retention guarantee.

## Validation scope

The patch passed 33 unit tests using simulated retrieval and provider responses, plus Python compilation and installer preflight/reapplication checks. Its real embedding parity check must run in the installed project. Cloud build, memory use, restart behaviour, concurrency and actual inference still need end-to-end tests. Free hosting is a deployment target, not a capacity guarantee.
