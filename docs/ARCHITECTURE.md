# Execution paths

## Shared semantic retrieval

`ingestion.py` parses text PDFs page by page, UTF-8 TXT/Markdown and DOCX body
paragraphs/tables. DOCX/TXT page 0 means unpaginated. Scanned PDFs need external
OCR. `word_documents.py` checks expanded DOCX size before extraction.

`app.build_engine()` loads `sentence-transformers/all-MiniLM-L6-v2` on CPU,
using its tokenizer for 180-token chunks with 30-token overlap. The code lowers
chunk length if the encoder window requires it. `DocumentStore` batches
normalized embeddings into persistent Chroma with cosine distance. No TF-IDF
implementation is substituted for this path.

`web_demo.semantic.create_store()` shares these retrieval components. Local
upload workspaces enforce the evaluated MiniLM/chunking profile and measure
loaded weights, tokenizer, module settings and package versions. The measured
identity lock refuses a changed fingerprint. It is not a recovered Hub commit.

## Local evidence viewer 2.1

`web_demo/local_app_v21.py` uses `local_upload_v21.Workspace`. Up to 48 chunks
and 20,000 text bytes are treated as a small corpus: all chunks are included
in semantic rank order. Larger corpora use ten semantic hits with adjacent
indexed passages from the same document. Neighbor expansion can cross pages.
The retrieval plan records omissions and whether coverage is complete.

`source_handles.py` splits text at punctuation boundaries, assigns stable IDs
within an unchanged context set, and asks the model to select at most six IDs.
Code copies the original spans and parent citations. Chunk-edge fragments,
PDF headers and incomplete text units may remain. Source-copy correctness is
separate from relevance and answer completeness.

The generator reserves context conservatively using serialized UTF-8 byte
counts, not an exact tokenizer. It chooses an 8K, 16K or 32K request window and
records actual tokens when returned. Oversized/invalid/incomplete outputs are
saved failures, not silently repaired. Empty context skips model inventory
and generation calls. Temporary indexes and persistent result archives have
distinct lifecycles; clearing the viewer does not delete saved source bytes.

## Direct-answer research

The root direct-answer runners send fixed question/context pairs to Ollama.
There is no fresh ingestion, semantic search, ID-selection stage, JSON output
schema, automatic factual judge or hidden retry. The direct baseline compares
three model tags on five known story questions. Confirmation uses only frozen
Qwen 8B on eight reserved fictional questions. The direct runner is not wired
into the local viewer.

## Preserved API and cloud prototype

The original API `/answer` and `/experiments` use `engine.py` and prompt names,
with their own budgets, options and output checks. In that legacy experiment
engine, no-context can still call the model: it is not the newer zero-call
control. The API defaults to Qwen 4B unless configured otherwise.

`web_demo/app.py` and `support.py` retain an earlier Groq-backed prototype.
They are not the recommended local entry point or a tested public deployment.
Same retrieval implementation does not mean identical model behavior,
hardware, dependency state or hosted latency.
