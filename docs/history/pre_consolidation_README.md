# EvidenceShift

A document-grounded answer experiment studying citation support, evidence order, abstention, and model behaviour.

The grounded pipeline selects paragraph handles, generates claims against selected evidence, then checks claim support and question coverage. Code copies source passages and renders citation IDs. Its model-based factual check is advisory: passing structural checks does not establish factual correctness.

## Two execution profiles

| Profile | Retrieval | Inference | Inputs |
|---|---|---|---|
| Existing local API | MiniLM embeddings / Chroma | Ollama | PDF, DOCX, TXT, MD |
| Upload demo | Shared local MiniLM / Chroma retrieval | Groq free-tier models | PDF, DOCX, TXT, MD |
| Fixed grounded benchmark | Saved evidence / fictional fixtures | Ollama | Eight predeclared cases |

The demo shares the API parser, token splitter, MiniLM encoder and Chroma search. Generation providers and storage lifecycles differ. Record these differences when comparing results. DOCX parsing is shared by both paths. See docs/SEMANTIC_REVISION.md.

## Run the upload demo

Use Python 3.12 in the existing project environment:

```bash
python -m pip install -r requirements-demo.txt
python -m streamlit run web_demo/app.py
```

Configure `GROQ_API_KEY` in `.streamlit/secrets.toml` locally or in Streamlit's server-side Secrets settings. Copy the placeholder from `web_demo/secrets.example.toml`; never commit a real key. Ingestion and evidence inspection work without a key. See [free deployment](docs/FREE_DEPLOYMENT.md).

## Run the fixed comparison

Ollama must be running. Downloads consume disk space, but no paid inference is used.

```bash
ollama pull qwen3:8b
ollama pull gemma3:4b
python evaluation/run_benchmark.py --models qwen3:4b qwen3:8b gemma3:4b
```

The plan contains eight existing development/fictional cases, 66 pipeline inputs across three models, and up to 126 nonempty-context stage calls. Empty context requires no generation. Identical one-paragraph reverse variants are skipped. This is not a held-out accuracy benchmark.

Every completed pipeline run saves its source, configuration, stage logs, candidate, verdict, and ZIP. The benchmark checkpoints JSON/CSV after every input and writes a consolidated ZIP under `results/`. Manual factual reviews remain pending. Interrupted runs retain checkpoints but may lack the final ZIP.

## Validation

```bash
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_grounded_release.py'
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_release_support.py'
```

These tests cover the added grounded pipeline and demo adapter using simulated model responses. They do not measure model accuracy or replace existing API tests.

## Limits and public results

The demo accepts one document at a time, up to 5 MiB, 50 PDF pages and 100,000 extracted characters. It does not perform OCR. DOCX page numbers are unavailable. Uploaded evidence is sent to the inference provider when a question is submitted. Downloads include question/source excerpts; users should choose suitable documents.

Free hosting can sleep and inference quotas can stop requests. No automatic paid fallback or retry is implemented. Public answers remain marked for factual review. Do not advertise perfect accuracy, verified citations, or independence when generation and verification use the same model.

Before publishing, inspect `git status` and staged changes for private documents, keys and raw local outputs. `.gitignore` does not remove files that were already tracked. Include only deliberately reviewed result artifacts. See [release gates](docs/RELEASE_GATES.md).

Semantic retrieval update: see [parity checks](docs/SEMANTIC_REVISION.md) and [publication plan](docs/REPOSITORY_PLAN.md). Real retrieval parity and free hosting validation are still required.

Grounded v1.3 local regression experiment: see [setup and limitations](docs/GROUNDED_V13.md).

Saved-answer context diagnostic: see [setup and limitations](docs/CONTEXT_AUDIT_V131.md).

Saved-answer context diagnostic: see [setup and limitations](docs/CONTEXT_AUDIT_V132.md).

Fresh baseline candidate evaluation: see [setup and limitations](docs/FRESH_BASELINE.md).

Document ingestion and retrieval evaluation: see [setup and limitations](docs/DOCUMENT_E2E.md).

Local upload demo: see [setup and limitations](docs/LOCAL_UPLOAD.md).
