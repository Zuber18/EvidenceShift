# Software validation

I use contract tests to validate parsing, storage, source mapping, orchestration
and report persistence. I keep these checks separate from live-model outcomes
and source-based factual assessments.

## Run locally

From the activated project environment:

```bash
python scripts/check_repository.py
PYTHONPATH=src:. python -m pytest -q tests
python compare_evidence_models.py --self-test
python run_direct_answer_baseline.py --self-test
python run_direct_confirmation.py --self-test
```

Pytest collects both the API/store tests and unittest-based revision tests.
The CI workflow runs this suite and the root runner self-tests. CI does not
execute a live inference benchmark or a hosted smoke test.

## Recorded checks

The consolidated local project passed 172 tests and two subtests on 20 October
2026, followed by 24 runner self-tests: eight matrix, twelve direct-baseline and
four confirmation tests. The publication integrity check verified 188 selected
files, seven frozen source dependencies and eight confirmation reversal pairs.
Those results preceded this documentation-only source annotation revision.

## Scope

Inference clients are controlled where declared. API/store tests use a test
encoder with Chroma; they do not establish equivalence to real MiniLM ranking.
The separate document end-to-end experiment records actual ingestion/retrieval
behavior on its limited fixture corpus.

`scripts/check_repository.py` validates stored hashes, record counts and order
pairing without importing the inference stack. It does not recompute semantic
judgments. Passing software checks does not erase the recorded factual failures.

This editorial revision adds docstrings to selected, non-frozen modules. Its
build check compares syntax trees after removing docstrings to confirm that
imports, prompts, schemas, branches, calculations and executable statements
remain unchanged. Callable documentation metadata can change; frozen source
snapshots and publication data remain byte-for-byte preserved.
