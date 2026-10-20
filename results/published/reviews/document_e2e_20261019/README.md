# Document ingestion, retrieval and answer review

**Milestone: the actual ingestion/search pipeline passes this small three-format fixture evaluation. Answer factuality remains unresolved.**

| Layer | Observed result |
| --- | --- |
| TXT/PDF/DOCX ingestion and provenance | 48/48 documents pass |
| Indexed chunks verified | 64 |
| Deduplication | Pass in all three format indexes |
| Answerable queries with all required evidence in top 5 | 21/21 |
| Required operative evidence units found | 30/30 |
| Core-supported answer outcomes | 20/24, including five presentation caveats |
| Material factual errors | 3/24 |
| Selection/generation contract failure | 1/24 |

The twenty core-supported outcomes comprise seventeen substantive answers and three justified abstentions. Five have presentation caveats: three precedence answers omit the explicit override explanation; two dispatch answers list both attributed dates without explicitly stating that the date is unresolved. The PDF precedence answer additionally includes the superseded date without explaining the supersession. Core support must not be presented as full rubric success.

## Where failures occur

The build-receipt answer incorrectly says execution started in TXT, PDF and DOCX. The complete rule denying that guarantee was retrieved and selected each time. This is a generation error, not an evidence-availability failure.

The PDF dispatch run retrieves and selects both dates, but the selector says supported while generation says conflict. The preserved validator rejects the mismatch. The latent raw answer is not counted as a completed candidate. TXT and DOCX select conflict and render both dates successfully, with the display caveat above.

There are 47 rendered claims: three are contradicted by their own cited source. The other 44 have a supporting cited basis, including six arithmetic claims using the question and rate rule. One PDF build claim includes an irrelevant extra citation. Claim counts are correlated and depend on verbosity; do not headline 44/47 as answer reliability.

## What has been verified

The fixture file hashes, real PDF/DOCX/TXT parser output, physical PDF page metadata, unpaginated TXT/DOCX metadata, deterministic chunk/source identity, actual retrieval snapshots, selected quotations and code-rendered candidates were recomputed. All 45 model calls returned schema-valid output with stop completion. Maximum actual input was 2128 bytes against 6000. Summed model-stage time was 141.18 seconds, not total pipeline runtime or hosted latency.

The three access-code queries have no positive answer-evidence requirements, so their recall is undefined. Their justified abstentions are assessed separately. The 21/21 and 30/30 counts cover only queries/evidence with positive requirements.

## Scope and next phase

These are eight synthetic scenarios repeated across three formats, with sixteen source documents per format. They do not establish performance on arbitrary documents, scans, OCR, complex tables, larger corpora or real workloads. The suite tests in-process upload/search API routes and frozen fresh-candidate generation; it does not validate the current /answer route, browser UI generation or public hosting.

The stored embedding revision is unresolved: both requested_revision and resolved_revision are null. MiniLM settings and package versions are recorded, but exact model revision should be pinned or identified before cross-machine/hosted reproducibility claims.

Preserve this result and move to local upload-demo integration, with source excerpts visible and generated answers clearly unapproved. Keep the observed failures documented. The next release checks are representative real-document smoke tests through the actual UI, exact model-revision recording, repository consolidation and free-host resource checks. Another unchanged synthetic verifier run is not needed.
