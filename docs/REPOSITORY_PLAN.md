# Repository and publication plan

I keep the application and frozen evaluation runners in their existing
import-compatible locations. The root README identifies the current entry
points; architecture and methodology explain how the paths differ. Historical
guides describe the revision that existed when each experiment was run.

## Code and comments

I document parsing limits, identity checks, context coverage, failure handling
and persistence boundaries where those decisions affect behavior. Comments
explain constraints and assumptions rather than narrating each statement.
[The code guide](CODE_GUIDE.md) maps the active path and preserved experiments.

Frozen runner and generator files retain their exact bytes. Formatting or
editing them would change the source hashes used by the recorded experiments.
Readability changes to those files require a separately identified revision,
with the original snapshots retained.

## Results

I publish a deliberate selection under `results/published/`: source-based
assessments, failed and successful raw records, run plans and provenance.
The manifests identify the selected source archives and extracted files.
Original local runs, uploads, indexes and environment files remain outside
the publication tree. An unchanged historical next-step note does not override
the current project status.

## Release sequence

1. Finish editorial review and retain passing software and integrity checks.
2. Inspect the exact committed publication set and its license/source notices.
3. Push the reviewed local commit and inspect the actual GitHub CI result.
4. Assess free-host capacity using the current official resource limits.
5. Test the chosen hosted stack separately before advertising a live demo.

My local results can be published as an experimental evaluation project before
a live demo is ready. I do not claim that hosting or reliable arbitrary-document
answering is already solved.

## Hosting boundary

I intend to retain the MiniLM/Chroma semantic retrieval implementation. A static
results site is separate from the compute needed by the Python application,
encoder and inference service. Any different hosted model needs labelled
evaluation; its behavior is not inferred from local Ollama results. The plan
uses free resources without an automatic paid fallback.

Research papers are linked in `references/README.md`. Code licensing does not
relicense third-party papers, models, libraries or source documents.
