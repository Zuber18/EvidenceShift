# Final coverage diagnostic review

All six generations completed normally and produced valid structured responses. Frozen file hashes, raw output streams, exact schema-bearing request payloads and regenerated rendered answers were checked.

| Case | Canonical | Reversed |
|---|---|---|
| Heat-risk scope and sample | Correct core answer; excessive citations | Correct core answer |
| Missing Flesch threshold | Appropriate exact abstention | Appropriate exact abstention |
| Guide exceptions and policy | General aim and both exceptions covered | Coverage improved; first paragraph lacks direct citation for specialist-term exception |

The previous scope contradiction and false unsupported decisions do not appear in these six outputs. Both policy answers now include the general accessibility aim and the specialist-term and passive-voice exceptions. Both genuinely missing-threshold cases abstain. These are observed development improvements, not proof of general reasoning reliability.

Citation support remains imperfect. The canonical heat answer cites all five retrieved passages for both parts, including passages that do not directly establish each stated fact. The reversed policy answer's first paragraph mentions the specialist-term exception but selects c7, c2 and c1 rather than its direct source c3. The later specialist-term paragraph does cite c3. Thus the fact is present and supported in context, while local claim-to-citation binding remains incomplete. The reversed passive-voice policy also includes proposed clarity/user-focus wording, which should not be presented as a verbatim source rule.

Do not revise the prompt again. Freeze this method and run one cross-model development regression: the same three questions, both passage orders, and the installed pinned Qwen 8B, replacement Qwen 4B instruct and Gemma 4B configurations. Maximum 18 attempts. Compare support and citation precision separately from syntax, membership and required fields. Retain every failure and do not select only favorable reruns.

The regression is deliberately limited to these three coverage cases. It does not re-evaluate arithmetic, restricted Python tracing, document parsing or the full 100-question benchmark. Keep earlier results clearly labelled by their own scope, and leave the reserved split untouched. After the regression, consolidate code, reviewed results and limitations for publication. No fine-tuning is planned.
