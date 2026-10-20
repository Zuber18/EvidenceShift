# Publication and repository plan

## Release order

1. Apply and test shared semantic retrieval; save the parity report.
2. Freeze the grounded pipeline and run the local eight-case comparison across the declared models.
3. Review answers, citation support, abstentions and verifier decisions against saved source passages. Distinguish correct answers rejected by the verifier from incorrect answers accepted by it.
4. Add unseen documents/questions after development cases. Report these separately.
5. Test a free-hosted semantic demo, including cold start, model download, memory, upload isolation, downloads, quota errors and session clearing.
6. Consolidate the repository and reviewed results, then publish GitHub and the LinkedIn explanation.

Local results are appropriate to publish: record hardware, model tag/digest/quantization, embedding revision, package versions, prompts, source hashes, parameters, elapsed time and review method. Do not present local measurements as hosted performance. A working demo complements the experiments; it does not replace the evidence.

## Intended repository contents

- `src/`: shared ingestion, retrieval, API and grounded pipeline.
- `web_demo/`: upload UI, session lifecycle and provider adapter.
- `evaluation/`: frozen cases, fixtures, comparison and parity runners.
- `tests/`: meaningful software checks, with mocks clearly labelled.
- `docs/`: architecture, setup, methodology, limitations, experiment history and deployment instructions.
- `results/published/`: deliberately reviewed, non-sensitive result JSON/CSV, summaries and reproducibility manifests.
- `references/`: bibliography, source URLs and notes explaining how each paper relates to this implementation.
- Root README, dependency configuration and suitable licensing after ownership/dependency review.

Raw local runs remain in ignored `results/`; selected public artifacts will be deliberately added under `results/published/` at consolidation. Keep private uploads, credentials, model weight downloads, vector databases, caches, backups and virtual environments out of Git. The patch does not change ignore rules or publish any artifacts automatically.

Research PDFs may only be redistributed where their licences permit it. The default is a bibliography with DOI/arXiv/publisher links and focused implementation notes. Citing a paper does not mean its methods were reproduced.

## Writing and code review

Use direct technical prose, consistent names and runnable instructions. Explain assumptions, design decisions and non-obvious constraints in comments; avoid narrating obvious statements. Remove redundant scaffolding and conversational or promotional phrasing. Preserve useful limitations, real citations, required notices, licence attribution and truthful experiment/reviewer metadata. Existing saved results remain historical records.

## Hosting

GitHub stores versioned project code and public result artifacts. A live upload demo also requires application compute and model inference. GitHub Pages or a static Vercel site can host a project/results page; those alone do not run the Python/MiniLM/Chroma stack.

The first application-host candidate remains Streamlit Community Cloud, with free-plan Groq inference and no automatic retry or paid fallback. It must pass the real resource checks before being called supported. Vercel can be assessed if useful; it is not a guarantee that the full local stack or local Ollama model fits the free plan. We will not replace semantic retrieval to make a host fit.

No paid platform, paid model endpoint, managed vector database or credit-card upgrade is part of this plan. Free quotas may prevent availability, in which case pause requests rather than silently switch to billing.
