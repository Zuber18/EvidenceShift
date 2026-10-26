# Development pilot review

All 48 attempts were inspected. No additional model calls were made. Original outputs are preserved.

| Model | Stopped normally | Output limit |
|---|---:|---:|
| Qwen 3 4B | 9 | 7 |
| Qwen 3 8B | 16 | 0 |
| Gemma 3 4B | 16 | 0 |

These are completion counts, not accuracy scores.

## Protocol correction

Explicit thinking-only advertisement plus saved template and actual output contradict the intended shared no-thinking protocol. Removing the original rejection was a mistaken fix for this model. Preserve pilot as diagnostic; do not publish a controlled three-model no-thinking ranking.

The saved Qwen 4B metadata advertises only thinking=True. Its template opens a thinking block regardless of the requested false value. All sixteen requests sent think=false, yet all returned deliberation in the answer field; nine included a closing delimiter and seven reached 2048 tokens. Qwen 8B and Gemma did not show that output behavior. The earlier explanation that metadata was merely too strict was incorrect for this installed tag.

## Findings

- Heat study: the five retrieved passages omit the actual 293 prefecture-level cities in China. Most completed responses appropriately abstain. Gemma reversed instead attributes the study to the United States using a bibliography entry for another paper.
- Python explicit-list test: the documented implementation gives [1], [2], [1, 3]. All four completed Qwen 8B/Gemma answers get this wrong. The correct function is in supplied c35: this is a reasoning failure, not missing retrieval.
- Exceptions: Qwen 8B canonical rejects both blanket editing rules, but reversed explicitly endorses a blanket passive rewrite and then contradicts itself. Gemma canonical reverses exception directions in its proposed policy.
- Reading-time arithmetic: 6.26 minus 2.11 is 4.15 hours/week. Results passage c33 contains both means. Qwen 8B canonical rounds to four; reversed supplies 4.15 but cites c50, which only says four. Responses also omit explicit per-week scope.
- Missing-score question: Qwen 8B and Gemma abstain correctly in both orders. This successful control should be retained.
- Citation membership is not citation support: known IDs appear in several incorrect answers. Qwen 4B additionally uses abbreviated IDs in several final portions.

## Next work

1. Preserve this pilot and its 48 attempt records. Do not rerun it to replace failures.
2. Restore a preflight that rejects an explicit thinking-only advertisement for a requested no-thinking protocol. Treat absent or unrecognized metadata separately; do not infer universal incompatibility.
3. Decide whether to retain this exact Qwen 4B digest in a separately labelled native-thinking track or select and pin a model artifact that supports no-thinking. Any new generation uses a separate run and budget.
4. Run offline retrieval audits on development sources: check gold coverage, section identity and bibliography contamination. Compare MiniLM retrieval candidates without feeding gold answers into query generation.
5. Add development-only deterministic checks for explicit Python calls, subtraction with units, citation membership, and claim-to-passage support. A citation parser alone cannot establish semantic correctness.
6. After mode and retrieval fixes, predeclare a small new development confirmation. Keep reserved questions untouched until the method is frozen.

## Audit

Prepared hashes, matching benchmark freeze, all 48 context orders, requested settings and stream/content consistency passed. No aggregate semantic accuracy was assigned; this small exposed pilot is diagnostic.

## Record-level review

### calibration_01 · gemma3:4b · canonical

Verdict: **supported_core**. Correct date and supporting passages; unnecessary extra mission details.

Reference: 16 November 2022.

Raw record: `jobs/5561fc1290689fad5e2d93db/record.json`

### calibration_01 · gemma3:4b · reversed

Verdict: **supported_core**. Correct date; supplied c3 supports it.

Reference: 16 November 2022.

Raw record: `jobs/44c4e1b9799f0194994104d1/record.json`

### calibration_01 · qwen3:4b · canonical

Verdict: **completed_with_output_contract_failure**. Final date correct with full IDs, but entire output contains extensive deliberation markup; not concise answer-only delivery.

Reference: 16 November 2022.

Raw record: `jobs/2eacafdd13314f3c8e122c07/record.json`

### calibration_01 · qwen3:4b · reversed

Verdict: **completed_with_output_contract_failure**. Final date correct, but abbreviated [c28, c3] do not match supplied IDs; output contains deliberation markup.

Reference: 16 November 2022.

Raw record: `jobs/96f47c7aff118116bf5fdd93/record.json`

### calibration_01 · qwen3:8b · canonical

Verdict: **supported_core**. Correct date; supplied c28 supports it.

Reference: 16 November 2022.

Raw record: `jobs/368b16ee72b4c985ead67350/record.json`

### calibration_01 · qwen3:8b · reversed

Verdict: **supported_core**. Correct date; supplied c3 supports it.

Reference: 16 November 2022.

Raw record: `jobs/c0c67de5ed40b0ea5a36316f/record.json`

### calibration_02 · gemma3:4b · canonical

Verdict: **unsupported_extra_obligation**. Core permission and first-use explanation are correct. Adds a requirement to break specialist terms into actions; c3 preceding guidance about jargon does not require decomposing every necessary specialist term.

Reference: No. Specialist terms can be used when needed, but their meaning must be explained the first time they are used.

Raw record: `jobs/b69be219bc521b7108e28537/record.json`

### calibration_02 · gemma3:4b · reversed

Verdict: **supported_core**. Allows necessary specialist terms and explains first use in plain English; additional literacy point is supported by c1.

Reference: No. Specialist terms can be used when needed, but their meaning must be explained the first time they are used.

Raw record: `jobs/8dbb3f9b438f01d3d242bba5/record.json`

### calibration_02 · qwen3:4b · canonical

Verdict: **completed_with_output_contract_failure**. Final semantic core correct, but [c3] is an abbreviated ID and output contains deliberation markup.

Reference: No. Specialist terms can be used when needed, but their meaning must be explained the first time they are used.

Raw record: `jobs/b5ccdb301b61e51c0186d2c8/record.json`

### calibration_02 · qwen3:4b · reversed

Verdict: **output_limit_no_final_answer**. Stopped at 2048 generated tokens with done_reason=length and no closing reasoning delimiter/final answer. Partial content is retained, never promoted to a completed correct response.

Reference: No. Specialist terms can be used when needed, but their meaning must be explained the first time they are used.

Raw record: `jobs/e62f28d6e9b4c0f6ed6c3ef3/record.json`

### calibration_02 · qwen3:8b · canonical

Verdict: **supported_core**. Both permission and first-use explanation are preserved.

Reference: No. Specialist terms can be used when needed, but their meaning must be explained the first time they are used.

Raw record: `jobs/a3509a6ddb7ab682842cbdad/record.json`

### calibration_02 · qwen3:8b · reversed

Verdict: **supported_core**. Both permission and first-use explanation are preserved.

Reference: No. Specialist terms can be used when needed, but their meaning must be explained the first time they are used.

Raw record: `jobs/5ec3924e17726f8958f853a5/record.json`

### calibration_03 · gemma3:4b · canonical

Verdict: **supported_but_mechanism_compressed**. Once-only default evaluation and None check are correct; reuse/mutation explanation is compressed.

Reference: The mutable default list is created/evaluated once and reused, so appending on later calls changes the same list. In the alternative, an omitted L defaults to None; the function creates a new empty list inside each such call before appending.

Raw record: `jobs/8eb7801b1bb595f7857cc5bf/record.json`

### calibration_03 · gemma3:4b · reversed

Verdict: **required_explanation_missing**. Restates accumulation but does not explain why it happens; None alternative is correctly described.

Reference: The mutable default list is created/evaluated once and reused, so appending on later calls changes the same list. In the alternative, an omitted L defaults to None; the function creates a new empty list inside each such call before appending.

Raw record: `jobs/9a0978401beb080e8817f70f/record.json`

### calibration_03 · qwen3:4b · canonical

Verdict: **completed_with_output_contract_failure**. Final mechanism broadly correct, but [c35]/[c36] are abbreviated IDs and output contains deliberation markup.

Reference: The mutable default list is created/evaluated once and reused, so appending on later calls changes the same list. In the alternative, an omitted L defaults to None; the function creates a new empty list inside each such call before appending.

Raw record: `jobs/2fa230a8aee726fc8fb2272d/record.json`

### calibration_03 · qwen3:4b · reversed

Verdict: **completed_with_output_contract_failure**. Final mechanism broadly correct, but [c35]/[c36] are abbreviated IDs and output contains deliberation markup.

Reference: The mutable default list is created/evaluated once and reused, so appending on later calls changes the same list. In the alternative, an omitted L defaults to None; the function creates a new empty list inside each such call before appending.

Raw record: `jobs/751d2cf2e2043f1b0ac6348e/record.json`

### calibration_03 · qwen3:8b · canonical

Verdict: **supported_core**. Explains evaluated-once/shared default and conditional new list.

Reference: The mutable default list is created/evaluated once and reused, so appending on later calls changes the same list. In the alternative, an omitted L defaults to None; the function creates a new empty list inside each such call before appending.

Raw record: `jobs/29a8b0471617dcdf00f7cbf2/record.json`

### calibration_03 · qwen3:8b · reversed

Verdict: **supported_but_mechanism_compressed**. Explains mutable shared default and conditional new list; does not explicitly state definition-time evaluation.

Reference: The mutable default list is created/evaluated once and reused, so appending on later calls changes the same list. In the alternative, an omitted L defaults to None; the function creates a new empty list inside each such call before appending.

Raw record: `jobs/790fe3d71e5a0ed886f4c59d/record.json`

### calibration_04 · gemma3:4b · canonical

Verdict: **correct_number_unit_scope_incomplete**. 4.15 is correct and c33 contains both operands; answer says hours without explicitly retaining per week. Retrieved passage is results section, not abstract.

Reference: 4.15 hours per week higher (6.26 minus 2.11).

Raw record: `jobs/0fdc72b0a55f6e762b6613d3/record.json`

### calibration_04 · gemma3:4b · reversed

Verdict: **correct_number_unit_scope_incomplete**. Correct 6.26 minus 2.11 calculation; says hours without per week. Arithmetic bracket is not an invented passage ID. Retrieved passage is results section, not abstract.

Reference: 4.15 hours per week higher (6.26 minus 2.11).

Raw record: `jobs/0a9f7bfd8b73ccdb80d45e03/record.json`

### calibration_04 · qwen3:4b · canonical

Verdict: **output_limit_no_final_answer**. Stopped at 2048 generated tokens with done_reason=length and no closing reasoning delimiter/final answer. Partial content is retained, never promoted to a completed correct response.

Reference: 4.15 hours per week higher (6.26 minus 2.11).

Raw record: `jobs/f8ffa7e820a08bcfefaf9ecc/record.json`

### calibration_04 · qwen3:4b · reversed

Verdict: **completed_with_output_contract_failure**. Final 4.15 correct, but says hours rather than hours/week, cites abbreviated [c33], and contains deliberation markup.

Reference: 4.15 hours per week higher (6.26 minus 2.11).

Raw record: `jobs/fa4fa2ddf4413e8801b56e6f/record.json`

### calibration_04 · qwen3:8b · canonical

Verdict: **wrong_precision_and_unit_scope**. Returns rounded four hours instead of required 4.15 hours/week from the means; c50 supplies rounded prose, while c33 has exact operands.

Reference: 4.15 hours per week higher (6.26 minus 2.11).

Raw record: `jobs/3cdab56c3942b46502e71f1d/record.json`

### calibration_04 · qwen3:8b · reversed

Verdict: **unsupported_precision_in_citation**. Number 4.15 is correct, but cited c50 only states approximately four hours and does not supply exact operands. c33 would support the calculation. Per-week scope is omitted.

Reference: 4.15 hours per week higher (6.26 minus 2.11).

Raw record: `jobs/c6d104be854945d2bd66d042/record.json`

### calibration_05 · gemma3:4b · canonical

Verdict: **appropriate_context_abstention_retrieval_failure**. Retrieved set does not establish 64% or actual 293-city sample. Abstention is appropriate to supplied context but full-document task remains unanswered.

Reference: No. The reported proportion concerns the study’s sample of 293 prefecture-level cities in China, not all cities worldwide.

Raw record: `jobs/3366dd0a7667a9026983c56f/record.json`

### calibration_05 · gemma3:4b · reversed

Verdict: **bibliography_misattribution**. Claims current study sample is in United States by citing c104, a reference to a different paper. Current gold sample is 293 prefecture-level cities in China, absent from retrieved set.

Reference: No. The reported proportion concerns the study’s sample of 293 prefecture-level cities in China, not all cities worldwide.

Raw record: `jobs/c151fde7decc3b167581db1a/record.json`

### calibration_05 · qwen3:4b · canonical

Verdict: **completed_with_output_contract_failure**. Final abstention appropriate to insufficient retrieved set; raw output contains deliberation and is not exact abstention. End-to-end retrieval task unanswered.

Reference: No. The reported proportion concerns the study’s sample of 293 prefecture-level cities in China, not all cities worldwide.

Raw record: `jobs/28170b5af6eb21448e6e99cf/record.json`

### calibration_05 · qwen3:4b · reversed

Verdict: **output_limit_no_final_answer**. Stopped at 2048 generated tokens with done_reason=length and no closing reasoning delimiter/final answer. Partial content is retained, never promoted to a completed correct response.

Reference: No. The reported proportion concerns the study’s sample of 293 prefecture-level cities in China, not all cities worldwide.

Raw record: `jobs/f00ad56b73b4aebb6b019f43/record.json`

### calibration_05 · qwen3:8b · canonical

Verdict: **appropriate_context_abstention_retrieval_failure**. Appropriate supplied-context abstention; retrieval missed gold sample.

Reference: No. The reported proportion concerns the study’s sample of 293 prefecture-level cities in China, not all cities worldwide.

Raw record: `jobs/e9ee35db1f913a955d75704e/record.json`

### calibration_05 · qwen3:8b · reversed

Verdict: **appropriate_context_abstention_retrieval_failure**. Appropriate supplied-context abstention; retrieval missed gold sample.

Reference: No. The reported proportion concerns the study’s sample of 293 prefecture-level cities in China, not all cities worldwide.

Raw record: `jobs/bb80c1b75d4c697bbee8596c/record.json`

### calibration_06 · gemma3:4b · canonical

Verdict: **appropriate_abstention**. No universal Flesch threshold is specified in reviewed source.

Reference: This guidance does not specify a minimum Flesch Reading Ease score.

Raw record: `jobs/ee7f60ff759546d341f65bf1/record.json`

### calibration_06 · gemma3:4b · reversed

Verdict: **appropriate_abstention**. No universal Flesch threshold is specified in reviewed source.

Reference: This guidance does not specify a minimum Flesch Reading Ease score.

Raw record: `jobs/936638f762153c410db65973/record.json`

### calibration_06 · qwen3:4b · canonical

Verdict: **completed_with_output_contract_failure**. Final abstention appropriate, but raw output contains deliberation and is not prescribed exact abstention.

Reference: This guidance does not specify a minimum Flesch Reading Ease score.

Raw record: `jobs/1a33d7bea289d0df0834d91e/record.json`

### calibration_06 · qwen3:4b · reversed

Verdict: **completed_with_output_contract_failure**. Final abstention appropriate, but raw output contains deliberation and is not prescribed exact abstention.

Reference: This guidance does not specify a minimum Flesch Reading Ease score.

Raw record: `jobs/60bd74448f55fabe9f6ed0b2/record.json`

### calibration_06 · qwen3:8b · canonical

Verdict: **appropriate_abstention**. No universal Flesch threshold is specified in reviewed source.

Reference: This guidance does not specify a minimum Flesch Reading Ease score.

Raw record: `jobs/7d2a8d4dee42633fd61fba08/record.json`

### calibration_06 · qwen3:8b · reversed

Verdict: **appropriate_abstention**. No universal Flesch threshold is specified in reviewed source.

Reference: This guidance does not specify a minimum Flesch Reading Ease score.

Raw record: `jobs/b7d754433b0060effd25b815/record.json`

### calibration_07 · gemma3:4b · canonical

Verdict: **wrong_execution_trace**. Replaces explicit f(2, []) with f(2), gives [1], [1,2], [1,2,3], and incorrectly describes initialization at function call. [1] is not a supplied canonical citation.

Reference: The outputs are [1], [2], and [1, 3]. The first and third calls omit L and reuse the one default list. The middle call supplies a separate empty list, so its append does not replace or reset the default.

Raw record: `jobs/aba961ac187345da57946128/record.json`

### calibration_07 · gemma3:4b · reversed

Verdict: **wrong_execution_trace**. Gives scalar 1,2,3 instead of lists; overgeneralizes shared list to all calls, including explicit-list call.

Reference: The outputs are [1], [2], and [1, 3]. The first and third calls omit L and reuse the one default list. The middle call supplies a separate empty list, so its append does not replace or reset the default.

Raw record: `jobs/51f0d1e416b234af39f334c4/record.json`

### calibration_07 · qwen3:4b · canonical

Verdict: **output_limit_no_final_answer**. Stopped at 2048 generated tokens with done_reason=length and no closing reasoning delimiter/final answer. Partial content is retained, never promoted to a completed correct response.

Reference: The outputs are [1], [2], and [1, 3]. The first and third calls omit L and reuse the one default list. The middle call supplies a separate empty list, so its append does not replace or reset the default.

Raw record: `jobs/c545a6a22608b10a9fc38e48/record.json`

### calibration_07 · qwen3:4b · reversed

Verdict: **output_limit_no_final_answer**. Stopped at 2048 generated tokens with done_reason=length and no closing reasoning delimiter/final answer. Partial content is retained, never promoted to a completed correct response.

Reference: The outputs are [1], [2], and [1, 3]. The first and third calls omit L and reuse the one default list. The middle call supplies a separate empty list, so its append does not replace or reset the default.

Raw record: `jobs/acdde516e8c031a4a316a530/record.json`

### calibration_07 · qwen3:8b · canonical

Verdict: **wrong_execution_trace**. First two lists correct; final list incorrectly includes 2. Explicit middle list does not modify default; correct final list is [1,3].

Reference: The outputs are [1], [2], and [1, 3]. The first and third calls omit L and reuse the one default list. The middle call supplies a separate empty list, so its append does not replace or reset the default.

Raw record: `jobs/aa19ab75e48883452b8107d5/record.json`

### calibration_07 · qwen3:8b · reversed

Verdict: **wrong_execution_trace**. First two lists correct; final list incorrectly [3], with irrelevant/incorrect local-symbol-table explanation. Correct final list is [1,3].

Reference: The outputs are [1], [2], and [1, 3]. The first and third calls omit L and reuse the one default list. The middle call supplies a separate empty list, so its append does not replace or reset the default.

Raw record: `jobs/0e996062c8089da07c7eceeb/record.json`

### calibration_08 · gemma3:4b · canonical

Verdict: **exception_direction_reversed**. Proposed policy removes specialist terms when needed and rewrites passive sentences precisely under exception conditions. Multiple cited IDs are present but misapplied.

Reference: No. Keep language clear and normally prefer active voice. A necessary specialist term may remain, with its meaning explained on first use. Passive wording can be appropriate when it is more user-centred; the guide does not require replacing every passive sentence.

Raw record: `jobs/3d3ae6b6001ea30e22dbf9d7/record.json`

### calibration_08 · gemma3:4b · reversed

Verdict: **supported_core_with_unsupported_uncertainty**. Recognizes both exceptions and retains necessary specialist terms with explanation. Adds unwarranted uncertainty about alignment with general aims; states c2/c6 attribution imprecisely.

Reference: No. Keep language clear and normally prefer active voice. A necessary specialist term may remain, with its meaning explained on first use. Passive wording can be appropriate when it is more user-centred; the guide does not require replacing every passive sentence.

Raw record: `jobs/f0ca946ac643e4c7bd5fd1a6/record.json`

### calibration_08 · qwen3:4b · canonical

Verdict: **output_limit_no_final_answer**. Stopped at 2048 generated tokens with done_reason=length and no closing reasoning delimiter/final answer. Partial content is retained, never promoted to a completed correct response.

Reference: No. Keep language clear and normally prefer active voice. A necessary specialist term may remain, with its meaning explained on first use. Passive wording can be appropriate when it is more user-centred; the guide does not require replacing every passive sentence.

Raw record: `jobs/28f8dfee74fdd3b4850df892/record.json`

### calibration_08 · qwen3:4b · reversed

Verdict: **output_limit_no_final_answer**. Stopped at 2048 generated tokens with done_reason=length and no closing reasoning delimiter/final answer. Partial content is retained, never promoted to a completed correct response.

Reference: No. Keep language clear and normally prefer active voice. A necessary specialist term may remain, with its meaning explained on first use. Passive wording can be appropriate when it is more user-centred; the guide does not require replacing every passive sentence.

Raw record: `jobs/7cbc83cb30f554924345a043/record.json`

### calibration_08 · qwen3:8b · canonical

Verdict: **supported_core**. Rejects both blanket rules and preserves necessary-term/first-use and passive-voice exceptions; general active-voice preference is implicit rather than restated.

Reference: No. Keep language clear and normally prefer active voice. A necessary specialist term may remain, with its meaning explained on first use. Passive wording can be appropriate when it is more user-centred; the guide does not require replacing every passive sentence.

Raw record: `jobs/d8ad1691bf75596f6ff56b05/record.json`

### calibration_08 · qwen3:8b · reversed

Verdict: **contradiction_and_bad_citation**. Explicitly endorses rewriting every passive sentence despite supplied c7 exception; cites c1, which does not establish active-voice rule. Closing policy then allows the exception, creating internal contradiction.

Reference: No. Keep language clear and normally prefer active voice. A necessary specialist term may remain, with its meaning explained on first use. Passive wording can be appropriate when it is more user-centred; the guide does not require replacing every passive sentence.

Raw record: `jobs/c8ea28ba38b9f5dee0ad8128/record.json`

