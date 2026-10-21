# Real-document benchmark: design draft

I am extending EvidenceShift from a small set of known failures to a broader,
source-grounded evaluation. This folder contains the proposed benchmark design
and failure rubric. It does **not** yet contain 60 authored questions or completed
results. Nothing here changes the existing published results or the live website.

## Decisions already made

The project owner selected mixed document QA, real documents only, and a strict
primary pass with partial usefulness reported separately. Fictional fixtures and
previously used questions remain regression tests outside this new benchmark.

## Proposed question allocation

| Primary skill | Development | Reserved evaluation | Total |
|---|---:|---:|---:|
| Direct factual answers | 5 | 5 | 10 |
| Conditions, exceptions and negation | 5 | 5 | 10 |
| Combining necessary passages | 5 | 5 | 10 |
| Calculations, dates and units | 5 | 5 | 10 |
| Scope, attribution and explicit precedence | 5 | 5 | 10 |
| Missing information and unsupported premises | 5 | 5 | 10 |
| **Total planned questions** | **30** | **30** | **60** |

Each question has one primary skill and may have secondary tags. These are design
quotas, not measured findings. If real sources cannot support a quota naturally,
revise and document the design before freezing; do not fabricate source passages,
contradictions or ambiguity merely to fill a cell. `allocation.json` contains 60
planning slots, explicitly labelled as unauthored.

## Proposed sources: decision checkpoint

| Source | Purpose | Proposed split |
|---|---|---|
| [Python 3.12: More Control Flow Tools](https://docs.python.org/3.12/tutorial/controlflow.html) | Technical instructions, defaults and conditions | Development |
| [GOV.UK: Use clear language](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/clear-language/) | Required guidance and specialist-language exceptions | Development |
| [NASA: Artemis I Mission Timeline](https://www.nasa.gov/reference/artemis-i-mission-timeline/) | Mission facts, dates, distances and phase distinctions | Development |
| [PostgreSQL 16: Transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html) | Atomicity, rollback, relationships and worked examples | Reserved |
| [GOV.UK: Using performance data](https://www.gov.uk/service-manual/measuring-success/using-data-to-improve-your-service-an-introduction) | Required metrics, procedures and percentages | Reserved |
| [NOAA: U.S. billion-dollar disasters in 2023](https://www.noaa.gov/news/us-struck-with-historic-number-of-billion-dollar-disasters-in-2023) | Dated reporting, geographical scope and qualified estimates | Reserved |

This is a shortlist, not an approved source corpus. Page bodies were inspected to
establish relevance, but licence review, source snapshots and gold annotation are
not complete. Third-party photographs and linked documents are excluded unless
separately admitted and licensed. `sources.proposed.json` records these limits.

The proposal uses two technical manuals, two guidance documents and two factual
reports. The first version evaluates frozen text from published HTML documents.
It does not establish PDF/DOCX extraction quality. Select the sources before
writing the questions; changing a source later can change the correct answer.

## Evaluation procedure

1. Accept or revise this source mix, six-source shortlist and split proposal.
2. Verify reuse terms and attribution, capture source bytes and extract document
   bodies. Preserve headings, lists, code and tables; record omissions explicitly.
   Record original bytes and extracted-text SHA-256 values, URL, capture date and
   version. Do not label a planned timeline as an observed mission outcome.
3. Write and adjudicate 60 questions against the frozen sources. Record required
   response units, sufficient evidence alternatives, qualifications, disallowed
   inferences, calculation inputs and uncertainty. Exact evidence offsets refer
   to the frozen text, not mutable web pages.
4. Keep complete document families in one split. Both GOV.UK documents belong to
   different guidance families; publisher overlap must remain disclosed. Review
   semantic duplicates across splits and remove any overlapping answer patterns
   that would undermine the intended separation.
5. Freeze the corpus, questions, gold annotations, rubric and split hashes before
   viewing new model outputs. The question author sees the reserved sources;
   therefore this is reserved project evaluation, not independent authorship or
   proof that public facts were absent from model pretraining.
6. Agree the execution plan separately. The suggested pilot is six development
   cases, one per skill, across three models in original/reversed order: 36
   generation calls per pipeline. A full 60-question run is 360 generation calls
   per pipeline, before any verifier calls or repeated trials. This design does
   not initiate inference.
7. Assess without showing model identity/order when practical. Review retrieval
   evidence availability separately from generation support. Save raw failures,
   annotations, disputed verdicts, exposure history and every stage call.
8. Report development and reserved results separately by model and skill. If
   reserved outcomes inform revisions, those cases become exposed regression
   cases for later iterations; do not retain an untouched-evaluation claim.

## What counts as success

A strict pass requires a completed response, factual support, complete required
coverage, adequate citations and appropriate answerability behavior. Correct
facts accompanied by an unsupported extra claim or false refusal do not pass.
An explicitly limited partial answer **can** pass on a genuinely partially
answerable question if it covers every supported part and correctly identifies
all required unknown parts. It cannot pass merely because some facts are right.

Required-unit coverage is recorded separately from strict pass. A response may
cover all requested facts and still fail because it adds a false claim. No
weighted composite score will conceal that distinction. Details and examples are
in [FAILURE_RUBRIC.md](FAILURE_RUBRIC.md); machine-readable definitions are in
`failure_rubric.json`. The case annotation contract is in `case_template.json`.

## Current readiness

- Three owner decisions recorded.
- Question allocation and failure rubric drafted.
- Six real source candidates proposed.
- **0 of 60 questions authored; no gold labels frozen; no inference run.**

Next decision: keep this two-manual / two-guidance / two-report source mix, or
replace any candidates before source capture and question authoring.
