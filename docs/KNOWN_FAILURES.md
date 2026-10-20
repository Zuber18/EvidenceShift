# Known failures and boundaries

| Finding | Saved evidence | Consequence |
|---|---|---|
| Direct Qwen 8B reverses giver/recipient on the story gift question | Direct baseline assessment | An existing citation can refer to the opposite action direction |
| Direct Qwen 8B abstains on the answerable gift-usability question in both orders | Direct baseline assessment | Conservative wording alone does not ensure justified abstention |
| Four confirmation trials give correct facts then falsely claim insufficient evidence | Confirmation assessment | Correct core content does not make the entire answer clean |
| Kit total changes from 12 to 8 under reversed order | Confirmation case 6 | The relevant citation does not validate arithmetic |
| ID selection copies exact spans but selects irrelevant text for missing facts | Viewer 2.1 replay and model matrix | Mechanical improvement did not resolve semantic reliability |
| Model-authored quotations fail exact-span contracts | Viewer 2.0 replay | Quote validation can block output without solving relevance |
| Earlier model critics reject supported answers or remain inconclusive | Critic assessments | No automatic factual approval gate is justified |
| Direct Qwen 4B hits the output limit on six answerable trials | Direct baseline raw outputs | Runtime/model/template handling remains unresolved; no capability-only conclusion |
| Grouped citation brackets are misread by the older parser in six Gemma responses | Direct baseline assessment | Preserve raw checks and report the parser caveat separately |

The direct-answer and source-handle viewer findings concern different paths.
Neither is a reliable arbitrary-document QA system. Current evaluation does not
establish resistance to prompt injection, success on scanned files, very long
or complex documents, numerical tables, arbitrary API feeds, or multilingual
retrieval. These are scope boundaries, not newly observed test failures.

The embedding identity lock measures the local stack and refuses changes. It
does not pin a Hub revision or make future installations equivalent. Existing
request budgets are byte-based estimates. Dependency ranges are not a lockfile.
No validated free-hosted deployment or cloud/local answer parity is claimed.

See the source-based reports in `results/published/reviews/` and the selected
unchanged raw records in `results/published/raw/`. Preserve failed outputs;
do not selectively rerun them to replace the recorded results.
