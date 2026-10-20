# Selected results

These are frozen experimental records, not a reliable-answer certificate.
The report copies preserve the project's final source-based assessments and
reviewer metadata. Original local evidence is not moved or rewritten.

## Read in this order

1. `reviews/direct_confirmation_20261020/README.md` and `assessment.json`:
   16 completed calls, nine clean, two minor caveats, four correct-core/false
   abstention responses, one arithmetic error; one code control is separate.
2. `reviews/direct_answer_20261020/`: 30 calls across three models, including
   six output-limit failures and unresolved Qwen 8B direction/abstention errors.
3. `reviews/model_matrix_20261019/`: 60 ID-selection calls; structural validity
   does not resolve missing-fact abstention or relevance.
4. `reviews/document_e2e_20261019/`: actual three-format ingestion/retrieval
   checks, reported separately from generation failures.
5. Earlier reviews: development history and evidence for rejected revisions.

## Raw evidence and integrity

`raw/model_matrix/`, `raw/direct_answer/` and `raw/direct_confirmation/`
contain unchanged job `record.json` files, plans, summaries, model inventory,
available version observations and frozen runner snapshots. Job records retain
the supplied context, outputs and model stages. Redundant nested exports,
per-stage duplicate files and rendered answer copies were not included.
`raw_archive_sources.json` records the exact source archive hash, selection
policy and included members. This is a selected extraction, not an assertion
that the original ZIP can be byte-for-byte reconstructed from the selection.

`manifest.json` hashes every publication data file and the frozen source
dependencies used by the root runners. Run `python scripts/check_repository.py`
to check integrity and confirmation pairs/counts. This does not score semantic
correctness or replace the source-based assessment.

I manually verified the saved assessments against the source passages.
The current review metadata identifies me, Zuber Shaikh, as the project
reviewer. These findings apply to the recorded cases and are not a
representative estimate over arbitrary user documents. Stage timing records
local model calls rather than hosted or end-to-end latency. Historical
next-step notes describe their original experiment phase; the root README
states the current direction. Failed outputs remain part of the record.

The current assessment metadata was revised after my manual verification.
Raw model outputs, source passages, run plans and frozen source snapshots
were not changed. The publication manifest identifies this reviewed revision.
