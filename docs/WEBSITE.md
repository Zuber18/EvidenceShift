# Interactive results explorer

I use the website to make saved evidence-order experiments inspectable without
requiring a Python environment or a model download. The browser presents recorded
answers, manual assessments, original source passages and mechanical checks.
Changing a question or filter does not perform inference.

The page follows a linear sequence: project introduction, research question,
method and evaluation, results, and conclusions. The default detail view is the
three-model direct baseline. Each selected question shows both evidence orders
for all models tested in that protocol; the source selector only chooses whose
citations to inspect. Trial tables and CSV exports include every tested model.
Comparison JSON exports include every model pair for the selected question.
The Qwen 8B confirmation remains a single-model protocol and is identified as such.


## Included experiments

| Experiment | Model calls | Code controls | Exact order pairs |
|---|---:|---:|---:|
| Reserved-case direct confirmation | 16 | 1 | 8 |
| Three-model direct-answer baseline | 30 | 3 | 15 |
| Model / evidence-representation matrix | 60 | 6 | 30 |

The experiments have different protocols and denominators. The website does not
combine them into one accuracy percentage. Source-based assessment labels remain
separate from completion and citation-ID membership checks. Grouped-citation
navigation does not rewrite the older parser's recorded checks.

## Files and data

- `website/`: HTML, CSS, JavaScript, native SVG branding and generated JSON data.
- `scripts/build_site_data.py`: verifies the published manifest and generates the
  browser dataset from actual records and current owner assessments.
- `tests/test_explorer.mjs`: Node's built-in tests for source pairing, control
  exclusion, outcome counts, filters, shared URLs and CSV serialization.
- `.github/workflows/pages.yml`: checks pull requests and deploys the static
  website on main pushes or manual dispatch after GitHub Pages is configured.

The dataset retains source hashes and links to original records pinned to the
build's source commit. Source text, reviewed notes, answers and incomplete raw
responses are never interpreted as executable HTML. There are no third-party
scripts, analytics, API credentials or remote fonts. Only a local theme preference
is stored in the browser. Downloaded JSON retains exact recorded values; CSV
prefixes formula-like cells for spreadsheet safety.

The website's small dataset is a presentation derivative of the published record,
not a replacement for the raw experiment files or their manifests. It must be
regenerated whenever relevant published records change. The build fails on a
publication-hash mismatch or a question, case, record-count or order-pair mismatch.

## Run locally

From the existing project root:

```bash
python scripts/build_site_data.py
node --check website/app.js
node --test tests/test_explorer.mjs
python -m http.server 4321 --directory website
```

Open `http://localhost:4321/`. The browser needs HTTP for the JSON request; opening
`index.html` directly as a local file is not the supported preview path.

## Publish with GitHub Pages

In the repository settings, select **Pages → Build and deployment → Source →
GitHub Actions**. After merging the website change into main, its workflow uploads
only `website/` and deploys that artifact. If the workflow ran before Pages was
enabled, enable Pages and rerun **EvidenceShift results explorer** from Actions.

The intended project URL is `https://Zuber18.github.io/EvidenceShift/`.
The same workflow must complete successfully before that URL is called deployed.

## Live-document boundary

This release has no live file-upload or inference endpoint. It links to the
existing local workspace instructions. The MiniLM/Chroma ingestion and retrieval
implementation is unchanged. Any public live backend needs separate resource,
session-isolation, quota and inference validation on the selected free host.
