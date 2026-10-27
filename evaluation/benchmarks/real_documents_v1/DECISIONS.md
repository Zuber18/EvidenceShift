# Benchmark decision record

## Recorded owner choices — 21 October 2026

| Decision | Choice |
|---|---|
| Domain scope | Mixed document QA |
| Source origin | Real documents only |
| Main success rule | Strict pass, with separate partial-credit reporting |

## Proposed implementation details

- 60 new questions; 30 development and 30 reserved, split by document family.
- Six skill categories, ten questions each, balanced across the two splits.
- Six published source documents; two manuals, two guidance pages, two reports.
- Text snapshots from HTML for the first fixed-context benchmark. PDF/DOCX
  extraction receives a separate later evaluation.
- Existing cases remain regression material outside the 60 new questions.
- Original/reversed evidence orders and all three existing models in a later
  execution plan. No model inference is part of this design milestone.
- Required-unit coverage is a diagnostic measure, not permission to pass a response
  containing unsupported claims. A gold-limited partial answer is judged against
  every supported unit and every required uncertainty statement.

## Current owner decision checkpoint

Accept the six-source proposal in README.md and sources.proposed.json, request
replacements, or change the balance of technical and general documents. Source
capture and question authoring start after this choice. Source licences still
need checking before copying content into the repository.

## Later checkpoints

1. Review example questions from the development portion to calibrate the rubric
   and difficulty before authoring the rest. Do not use reserved outputs for this.
2. Accept the final corpus, annotation rules, split and gold hashes before freezing.
3. Agree model-call budget, repetitions and baseline execution before running models.
4. After the reserved evaluation is exposed, record its status and choose whether
   later iterations need new reserved documents.

Every changed decision receives its date, reason and affected versions here.
No silent relabelling, source swaps or favorable replacement runs.
