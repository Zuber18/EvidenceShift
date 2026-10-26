# Evidence coverage pilot review

The pilot failed before answer writing. It does not demonstrate an improvement in contradictions, policy coverage or abstention.

| Observed outcome | Count |
|---|---|
| Planner calls completed normally | 6 |
| Plans rejected for nonliteral source quotes | 4 |
| Plans rejected for invalid JSON | 2 |
| Writer calls | 0 |
| Final answers | 0 |

Frozen file hashes and all six raw generation streams were checked. There was no truncation or thinking output. The writer was correctly skipped after plan rejection.

The quotation contract exposed an interface weakness: the model reconstructed plausible source wording rather than reliably copying exact extracted text. Heat-risk quotes remove PDF line breaks and split-word artifacts; policy quotes also change punctuation and quotation marks. These are not all unsupported factual inventions, but they are not exact spans and must not silently be accepted as verbatim evidence. The Flesch plans have an extra closing brace; their intended abstention is not a valid pipeline result.

Separately, all four well-formed heat-risk and policy drafts mark an answerable decision unsupported. Evidence that the study concerns Chinese cities supports rejecting worldwide generalization. The guide’s explicit exceptions support rejecting the proposed blanket rules. An appropriate negative answer must be distinguished from missing evidence. Fixing quote copying or JSON alone would leave this issue unresolved.

The policy plans also attach general accessibility claims to exception quotations instead of selecting the available general-guidance passages. The reversed policy claim omits the specialist-term exception despite including related evidence. Real citations or filled slots alone would not establish complete support.

Do not rerun the same protocol. The next design should select existing evidence IDs, use constrained JSON output, and freeze question-only requested parts before generation. Keep answerability and semantic support review separate from syntax and renderer checks. Do not loosen the quote guard or overwrite this failed run. Fine-tuning remains unjustified by this small development sample.

## calibration_05 / canonical

nonliteral_evidence_quote, false_unsupported_classification

The study’s Chinese sample supports rejecting worldwide generalization. The plan instead calls that decision unsupported. The cited numerical facts are present, but model-retyped quotes remove source line breaks and extraction artifacts, violating the exact-span contract.

## calibration_05 / reversed

nonliteral_evidence_quote, false_unsupported_classification

The study’s Chinese sample supports rejecting worldwide generalization. The plan instead calls that decision unsupported. The cited numerical facts are present, but model-retyped quotes remove source line breaks and extraction artifacts, violating the exact-span contract.

## calibration_06 / reversed

invalid_json

The draft classification as unsupported is consistent with the saved source review, but an extra closing brace makes the output invalid JSON. It cannot count as a successful pipeline abstention.

## calibration_06 / canonical

invalid_json

The draft classification as unsupported is consistent with the saved source review, but an extra closing brace makes the output invalid JSON. It cannot count as a successful pipeline abstention.

## calibration_08 / canonical

nonliteral_evidence_quote, false_unsupported_classification

The two exceptions support rejecting the blanket rules. The plan instead calls that decision unsupported. Quotations alter punctuation, line breaks and quotation marks. General accessibility claims are not supported by the selected c3/c7 quotes; c0/c1 were available but not selected.

## calibration_08 / reversed

nonliteral_evidence_quote, false_unsupported_classification

The two exceptions support rejecting the blanket rules. The plan instead calls that decision unsupported. Quotations alter punctuation, line breaks and quotation marks. General accessibility claims are not supported by the selected c3/c7 quotes; c0/c1 were available but not selected. The proposed policy claim also fails to state the specialist-term exception despite listing specialist-term evidence.
