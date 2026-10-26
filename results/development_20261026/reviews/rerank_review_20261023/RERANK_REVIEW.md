# Reranker development review

The saved run scored 216 question–passage pairs locally. No answers were generated. Pair inputs, raw scores, ordering and selected source text were checked against the saved pilot. Maximum pair length was 257 tokens against the reranker limit of 512.

The reranker recovers missing evidence on the exposed heat-study question, but does not fix all evidence coverage or establish improved answer accuracy.

- **calibration_01**: Annotated mission overview is now rank 3; other directly supporting launch-date passages remain ranks 1 and 2.
- **calibration_02**: Necessary specialist terms and first-use explanation remain available, now rank 1. No demonstrated change to answer reliability without generation.
- **calibration_03**: Both default-list mechanism and None alternative remain available at ranks 1 and 2.
- **calibration_04**: Requested abstract with exact weekly means is now rank 1. Results-section operands remain rank 2. Rounded four-hour prose remains rank 5, so precision selection still needs testing.
- **calibration_05**: Former cosine ranks 24 and 28 become reranker positions 1 and 4. A discussion passage at position 2 independently states 293 prefecture-level cities in China. This repairs the observed missing-sample retrieval in this case, not hallucination generally.
- **calibration_06**: There is still no specified universal Flesch threshold. High relevance cannot establish an answer. Correct abstention must be checked in generation.
- **calibration_07**: Required original function remains rank 1. Prior wrong traces cannot be assumed fixed by reranking.
- **calibration_08**: General clarity passage enters rank 4 and both specialist/passive exceptions remain ranks 1 and 5, but explicit general active-voice preference moves from original rank 5 to reranker rank 6 and is excluded. This is an evidence-coverage tradeoff.

Recommended next comparison: 8 questions × original/reranked contexts × canonical/reversed orders = 32 new generation attempts using the same pinned Qwen 8B model in one run. This isolates the retrieval change from the Qwen 4B replacement. An eventual all-three-model comparison requires 96 attempts for the same design.

Keep the original pilot, failed outputs and reserved benchmark unchanged. Scores are relevance logits, not factual-support probabilities. Candidate depth 40 was chosen after development inspection; this result is not a held-out accuracy estimate.
