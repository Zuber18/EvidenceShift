# October development results

This release retains twelve original development bundles, code reference copies and source-based reviews. The final regression contains three exposed questions, two passage orders and three pinned model configurations: 18 normal completions, 18 valid JSON responses, 17 rendered answers and one blocked cross-field violation. These are structural counts, not semantic accuracy.

The final review records an unsupported worldwide generalization from Gemma, a metric/geography error from the replacement Qwen 4B, missed abstention and citation misattribution. Qwen 8B repeats its earlier outputs but retains citation weaknesses. The smaller Qwen artifact differs from the original Qwen 4B used in historical experiments.

Read `reviews/frozen_regression_review_20261026/FROZEN_REGRESSION_REVIEW.md` and its record-level JSON. Earlier failed runs remain in `raw/`; nothing is replaced by a favorable rerun. `code/` contains reference copies, while each original bundle retains its own code snapshot and request payloads. Use `manifest.json` and `scripts/check_development_release.py` to verify preserved bytes.

The full 100-question real-document benchmark was prepared during development but was not executed as part of this final regression. Do not call these eighteen trials the 100-question benchmark or independent held-out validation. The reserved split remains unused. Arithmetic, tracing and retrieval pilots have separate scopes and should not be pooled into one accuracy figure.
