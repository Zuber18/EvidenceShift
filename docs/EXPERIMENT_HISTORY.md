# Experiment history

These experiments have different questions, evidence and generation paths.
Counts below are not a combined benchmark or a chronological accuracy trend.

| Phase | Evidence and method | Observed result | Decision |
|---|---|---|---|
| Original grounded generation | Paragraph selection, claims, model checking | Critic and citation-support failures | Preserve as baseline |
| Context critics 1.3–1.3.2 | Reassess saved answers with critic/confirmation contracts | False blocking and inconclusive audits | Stop the self-critic loop |
| Fresh candidate baseline | Eight fictional cases, two orders and controls | Supported cases coexist with negation and contract errors | Evaluate actual ingestion/retrieval separately |
| Document end-to-end | 48 generated TXT/PDF/DOCX files, 24 answer records | All 48 provenance checks pass; all 30 required units found over 21 positive queries; generation still fails some cases | Retrieval success is not factual-answer success |
| Exploratory uploads | Repeated story questions on real PDF ingestion | Gift-direction, support, coverage and budget problems | Preserve exploratory scope |
| Source-first 2.0 | 16 model trials, two code controls | Ten mechanical failures; relevance/abstention failures remain | Failed revision |
| Source handles 2.1 | Same 16 model trials and two controls | 16 structural passes, 64 exact spans; none of four absent-fact trials abstains correctly | Mechanical improvement only |
| Model/representation matrix | Three models × two representations × five questions × two orders | 60 structural passes, 244 source spans; only 4/24 absent-fact trials abstain correctly | No reliable ID-selection configuration |
| Direct-answer baseline | Three models × five questions × two orders | 24 completed responses, six output-limit failures; Qwen 8B still has role and abstention errors | Freeze a limited confirmation candidate |
| Direct Qwen 8B confirmation | Eight reserved questions × two orders | Nine clean, two minor caveats, four false-abstention endings, one arithmetic error | Freeze results; publish as experimental evaluation |

Source-based assessments are preserved under `results/published/reviews/`.
Original status strings remain historical evidence. Their requests to run
later phases do not override the current README or the final confirmation
decision. Earlier installer commands should not be rerun as setup for the
consolidated project: they may overwrite a preserved revision.
