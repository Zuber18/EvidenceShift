# Release status

I intend to publish EvidenceShift as an experimental evaluation project.
The recorded confirmation still contains factual and abstention failures;
reliable arbitrary-document answering has not been established.

## Code and result publication

My release checks cover software contracts, frozen-source integrity, selected
result provenance and the committed file set. I retain failed outputs and
report each experiment with its own scope and denominator.

Project-authored code is licensed under MIT. Third-party dependency, model,
paper and source-document terms remain separate. Virtual environments, local
indexes, credentials and private uploaded sessions stay outside publication.

The local software checks passed before the editorial annotation revision.
After applying that revision, I check syntax-tree equivalence, frozen evidence
integrity and the software suite again. A clean checkout still needs separate
installation validation; a dependency range is not an exact environment lock.

## Live public demo

I have not validated a hosted deployment. Before advertising one, I will check
the chosen free host's current resource limits and test cold starts, dependency
loading, encoder memory, upload limits, session isolation, exports, cleanup,
quotas and inference errors on that host.

I will retain MiniLM/Chroma semantic retrieval. A different hosted model needs
its own labelled evaluation; local Ollama results do not establish its behavior.
The hosting plan has no automatic paid fallback. A static results page alone
does not execute the Python, embedding and inference stack.
