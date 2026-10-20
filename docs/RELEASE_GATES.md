# Release status

## Current outcome

A documented experimental evaluation release is the target. Reliable-answer
release criteria have not been met. Confirmation results are frozen; no extra
user-review-pending gate is required. Source-based project assessments are
final for this project and their actual reviewer provenance remains visible.

## Before publishing code and results

- Apply the consolidation and run its integrity check, complete software tests
  and frozen runner self-tests in the evaluated local environment.
- Inspect the exact Git staging set; .gitignore does not untrack existing files.
  Keep source documents, secrets, models, indexes and local sessions out.
- Retain selected reports, raw failures, hashes and methodology without merging
  unlike experiments into one headline accuracy number.
- Project-authored code is licensed under MIT. Retain required third-party
  dependency, model and source-document notices.
- Verify setup from a clean environment separately from historical reproduction.

## Before a live public demo

Choose free compute/inference only after checking current official limits.
Preserve MiniLM/Chroma semantic retrieval; no TF-IDF replacement. Test cold
start, dependency/model loading, memory, multi-session document isolation,
file limits, exports, clearing, quotas and inference errors on the actual host.
A different cloud model requires separate labelled results. No paid fallback.

No hosted test or deployment has been completed by repository consolidation.
A static page alone cannot execute this Python/embedding/Ollama stack. Local
results may be published with their measured scope before hosting is ready.
