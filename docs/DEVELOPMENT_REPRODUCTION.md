# Inspecting the development release

Use Python 3.12. The release checker uses the standard library and makes no network or model calls:

```bash
python scripts/check_repository.py
python scripts/check_development_release.py
```

The existing project environment can run the repository test suite:

```bash
PYTHONPATH=src:. python -m pytest -q tests
```

For a fresh environment, follow the root README installation instructions before running tests. Do not upgrade the environment used for the saved experiments before retaining its package record.

Preview the recorded-results website locally:

```bash
python -m http.server 8080 --directory website
```

Open http://localhost:8080/development-regression.html. It reads saved data and runs no model. The original explorer remains at the root. All data and source text in the new page are escaped when rendered.

For live document work, the existing local MiniLM/Chroma and Ollama viewer remains:

```bash
python -m streamlit run web_demo/local_app_v21.py
```

The website is a recorded-results demo; it is not hosted live inference. No TF-IDF replacement was introduced. The local viewer and experimental development runners are separate paths; the final structured-coverage diagnostic is not silently substituted into the upload app.

## What is reproducible

Raw bundles preserve the exact requests, model digests, native metadata, streamed outputs, source contexts and code snapshots. The release checker validates their bytes. The final public page can be inspected on any machine with a browser. Review meaning against the saved passages; automatic format checks are not a truth test.

The historical development runners depend on earlier prepared plans, source snapshots and local index state. They are retained for traceability; a fresh clone is not claimed to replay the entire chain with one command. Original prepared plans may include machine-specific paths, and replaying them after changing files is intentionally refused. Do not edit their hashes to force a replay. New experiments require newly prepared plans, the pinned artifacts and equivalent source extraction/retrieval inputs.

The final regression freezes one method across three models and both orders. Its three cases were already exposed during development, and its coverage requirements were manually specified from the questions. It does not assess general automatic question decomposition, all 100 authored questions, OCR, full-document absence, arbitrary uploads, or hosted latency. Stage timings in saved records are local measurements and are not end-to-end service latency.

After this release, further benchmark expansion, generic evidence planning and stronger claim-to-source verification are future work. Failed development outputs are part of the findings.
