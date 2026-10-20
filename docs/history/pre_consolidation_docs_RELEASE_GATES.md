# Release gates

Stop prompt tuning during the fixed comparison. If the pipeline changes, keep the previous run and start a separately labelled version.

1. Added pipeline/demo tests pass, and the existing project's required API tests still pass.
2. The HTTP 405 grounded result currently being run is inspected against its saved passages.
3. Run the fixed eight-case comparison across Qwen 4B, Qwen 8B and Gemma 4B. Review each answer's claims, citations, conditions, conflicts and abstentions against source passages. Do not convert `needs_factual_review` into a factual pass automatically.
4. Summarise reviewed outcomes, failures, elapsed time and output tokens by model and variant. Report review denominator and scope. Existing development cases cannot demonstrate generalisation.
5. Test the hosted demo end to end with a text PDF, DOCX, sample policy, empty-match question and a quota/error response. Mock tests cover the adapter; actual provider and hosted tests remain required.
6. Publish clean code and deliberately selected reviewed examples. State shared retrieval and local/cloud generation differences in the README and public post.

A truthful experimental release can include unresolved failures with clear evidence. There is no promised number of tuning iterations that will eliminate factual errors.
