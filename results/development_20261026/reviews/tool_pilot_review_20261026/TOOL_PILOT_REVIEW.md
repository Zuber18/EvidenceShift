# Tool pilot review

The v1 answer-writing protocol regressed despite correct arithmetic and Python traces. Preserve this run as a failed development result.

- 32 generation attempts completed.
- All 12 factual answers lacked required bracket citations.
- Five answers also appended contradictory abstention.
- Two exact abstentions were appropriate; two editing-policy abstentions were incorrect.
- Both computations yielded 4.15, but reversed order omitted weekly scope.
- Both Python traces produced the correct printed lists.

The new writer prompt omitted the baseline’s explicit square-bracket citation rule. Feeding negative audit flags to the writer may have encouraged abstention, but this run does not isolate that cause.

V2 preserves the original baseline request for all 12 non-tool inputs. Two traces use deterministic routing; only two arithmetic inputs need planner calls. Maximum: 18 generation attempts. Generator inputs exclude internal audit flags. Weekly quantity selection must retain explicit weekly units.

22 offline runner tests passed. Actual saved non-tool input payloads were checked for equality against the baseline construction. No live model inference was performed during repair. No aggregate semantic accuracy or general hallucination-resolution claim is made.

## calibration_01 / canonical

citation_format_missing

Core factual answer supported by saved passages; format and any contradictory abstention assessed separately.

## calibration_01 / reversed

citation_format_missing

Core factual answer supported by saved passages; format and any contradictory abstention assessed separately.

## calibration_02 / reversed

citation_format_missing

Core factual answer supported by saved passages; format and any contradictory abstention assessed separately.

## calibration_02 / canonical

citation_format_missing

Core factual answer supported by saved passages; format and any contradictory abstention assessed separately.

## calibration_03 / canonical

citation_format_missing, contradictory_abstention

Core factual answer supported by saved passages; format and any contradictory abstention assessed separately.

## calibration_03 / reversed

citation_format_missing, contradictory_abstention

Core factual answer supported by saved passages; format and any contradictory abstention assessed separately.

## calibration_04 / reversed

citation_format_missing, temporal_scope_omitted

Computed difference 4.15 is correct for the selected reported means. Answer and selected units omit weekly scope.

## calibration_04 / canonical

citation_format_missing

Computed difference 4.15 is correct for the selected reported means.

## calibration_05 / canonical

citation_format_missing

Core factual answer supported by saved passages; format and any contradictory abstention assessed separately.

## calibration_05 / reversed

citation_format_missing, contradictory_abstention

Core factual answer supported by saved passages; format and any contradictory abstention assessed separately.

## calibration_06 / reversed

Appropriate abstention.

Appropriate abstention: no minimum Flesch score is established.

## calibration_06 / canonical

Appropriate abstention.

Appropriate abstention: no minimum Flesch score is established.

## calibration_07 / canonical

citation_format_missing, contradictory_abstention

All three derived printed lists are correct; accompanying contradictory abstention remains a failure.

## calibration_07 / reversed

citation_format_missing, contradictory_abstention

All three derived printed lists are correct; accompanying contradictory abstention remains a failure.

## calibration_08 / reversed

false_abstention

Both policy exceptions are established in supplied passages; exact abstention is incorrect.

## calibration_08 / canonical

false_abstention

Both policy exceptions are established in supplied passages; exact abstention is incorrect.
