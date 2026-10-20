# Qwen 8B grounded v1.3 development review

**Result: failed regression; do not promote the new gate.**

Of 22 inputs, eight are deterministic empty-context controls. Of the 14 evidence-bearing inputs, 13 are blocked and only the correct missing-password abstention is delivered. No substantive answer is delivered. Ten supported core answers are falsely blocked. The remaining three substantive candidates have citation or reasoning defects; the gate often gives an unrelated or incorrect reason even for those.

The earlier Qwen 8B v1.2.1 run delivered nine substantive answers, all core-supported under source review, with two citation precision caveats. Those are frozen development cases, not a held-out accuracy claim.

All 78 generation stages in this v1.3 run are schema-valid. No observed input-budget or claim-index failure explains the regression. Most failures are semantic: the context critic demands facts already present or details outside the question. Per-record reasons and source identifiers are in review.json and review.csv.

This is the final source-based project assessment. It remains distinct from software validation and model-generated judgments. The next diagnostic reuses the saved candidates and adds four known bad controls; it does not approve answers for delivery.
