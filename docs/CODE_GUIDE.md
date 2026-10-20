# Code guide

I keep retrieval, generation, structural validation and assessment separate.
This guide follows the current local viewer and identifies the preserved
research paths so that their different behavior remains explicit.

## Current local upload path

| Module | Responsibility | Key constraint |
|---|---|---|
| `web_demo/local_app_v21.py` | Streamlit controls and display | Presents selected source excerpts; does not claim factual approval |
| `local_upload_v21.py` | Complete-small-corpus or expanded semantic context | Reversal retains the context set; omissions are recorded |
| `local_upload.py` | Upload limits, measured identity, local sessions and exports | Clearing temporary search data does not delete saved source bytes or reports |
| `web_demo/semantic.py` | Shared encoder/splitter and isolated stores | Encoder reuse is serialized; documents belong to their own workspace |
| `app.py` / `build_engine` | Construct the shared MiniLM/tokenizer/Chroma stack | Preserve the evaluated retrieval profile; do not substitute a different index |
| `ingestion.py` | Validate and parse documents | PDF pages are physical pages; non-PDF text is unpaginated |
| `word_documents.py` | Extract DOCX body paragraphs and tables | Expanded ZIP size is bounded; DOCX pages are not invented |
| `store.py` | Persist chunks and perform cosine nearest-neighbor search | Batch writes roll back if ingestion fails; scope queries by document IDs |
| `source_handles.py` | Select code-assigned evidence units and copy source spans | Exact text copying is not a relevance or completeness guarantee |

`source_handles.py` is frozen by hash. Its punctuation-based units can contain
PDF headers and chunk-edge fragments. IDs are stable for an unchanged context
set; they are not universal identifiers across arbitrary documents.

## Direct-answer experiments

`run_direct_answer_baseline.py` sends fixed saved passages directly to each
model without a selection stage or JSON answer schema.
`run_direct_confirmation.py` loads the exact frozen direct runner and requires
the selected Qwen 8B digest. `compare_evidence_models.py` evaluates a different
protocol: constrained passage/text-unit selection.

These three runners are frozen source dependencies. The current viewer does
not import the direct-answer runner. The fixed-context experiments do not
measure fresh retrieval or ingestion.

## Preserved earlier paths

- `engine.py` and `prompts.py`: original API answer and prompt comparison.
  The legacy no-context experiment can still call the model.
- `grounded.py`, `fresh_candidates.py`, `grounded_v13.py`: selection/claim
  generation and the earlier critic or candidate-recording variants.
- `context_audit_v131.py`, `context_audit_v132.py`: saved-answer diagnostics;
  their observed shortcomings remain recorded.
- `source_first.py`, `local_upload_v2.py`: model-authored quotation contracts
  and earlier expanded-context upload service.
- `web_demo/app.py`, `web_demo/support.py`: earlier cloud inference prototype;
  public hosting has not been validated.

## Reading comments and tests

Docstrings on public retrieval/session methods explain units, side effects,
failure behavior and persistence boundaries. Short private helpers do not need
a comment that merely repeats their name. Tests identify their controlled
clients and encoder/store substitutes. Recorded model responses remain
separate evidence.

Some preserved experimental files use compact one-line statements. I retain
that formatting where hashes identify the evaluated source. A future style
refactor should use a new revision and preserve the original frozen snapshots;
it should not be represented as the exact previously evaluated source.
