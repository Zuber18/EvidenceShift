# Software validation

Run from the activated project environment:

```bash
python scripts/check_repository.py
PYTHONPATH=src:. python -m pytest -q tests
python compare_evidence_models.py --self-test
python run_direct_answer_baseline.py --self-test
python run_direct_confirmation.py --self-test
```

Pytest collects both the API/store tests and unittest-based revision tests.
CI uses the same suite and self-tests. Inference clients are controlled in
these tests; no live model benchmark or hosted test is performed by CI.
`scripts/check_repository.py` validates frozen file hashes, record pairing and
the selected result manifest without importing optional runtime packages.

Consolidation packaging checks are saved in the installer's build-validation
record. The installation report records the environment observed at application
time; it does not claim that the complete test suite ran on the user's Mac.
Do not describe missing dependencies or unexecuted tests as passing.

Earlier local real-model runs remain assessed in `results/published/reviews/`.
No software check changes their observed factual failures. Live retrieval,
model inference and future hosted resource checks have separate denominators
and evidence requirements.
