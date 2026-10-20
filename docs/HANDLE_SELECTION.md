# Evidence ID selection revision 2.1.0

The 2.0.0 live replay failed: nine quotation-contract failures, one response-label
contract failure, and a mechanically valid but irrelevant flute response. This
revision removes model-authored quotations. It does not certify relevance.

## Run inside the existing project

Stop Streamlit with Ctrl+C and keep Ollama running. Use the existing venv.

```bash
python install_handle_selection.py .
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_source_handles.py'
python evaluation/run_handle_replay.py
```

The replay uses the same eight questions, both context orders and two zero-call
controls. It locates the original PDF in saved session archives under results/;
`--bundle /path/to/session.zip` is also supported. All results and the ZIP are
saved inside this project. No additional report preparation is necessary.

Optional UI after replay:

```bash
python -m streamlit run web_demo/local_app_v21.py
```

## Scope

- Same MiniLM encoder, chunker, Chroma index, embedding identity lock and retrieval
  policy as 2.0.0. Small corpora still use all indexed chunks; larger corpora use
  top-ten hits and neighboring passages.
- Same Qwen 3 8B model, temperature, seed, thinking setting, output reservation,
  context-budget algorithm and no-retry policy.
- Code splits indexed passages into punctuation-based evidence units, retaining
  original offsets and text. This is not a linguistic sentence parser: PDF
  headers, abbreviations and chunk-edge fragments can remain. Context is grouped
  by parent passage in the model input. No source text is corrected or stitched.
- IDs map to the same units under reversed passage order. IDs are stable within
  an unchanged context set, not globally permanent document identifiers.
- The model selects at most six IDs from a dynamic schema enum. Code copies the
  original text and attaches source citations. The model cannot supply quotation
  wording or a separate quotation-to-passage assignment.
- Invalid/duplicate IDs, incompatible answerability labels, incomplete generation
  and context-budget failures are still retained as failures. They are not
  silently repaired or retried.
- Exact copied text can be irrelevant or incomplete. Insufficient responses can
  still be unjustified. Those outcomes require source-based assessment and remain
  separate from structural validity.

The changed unit representation, schema and instructions form one output-method
revision. The experiment cannot attribute results to only one of these elements.
The display remains an evidence view, not a polished generated answer.

## Release criterion

Do not treat a higher structural pass count as accuracy improvement. Inspect
whether each answerable question gets the required facts and correct actor/action
roles, whether partial questions disclose missing support, and whether absent
facts produce justified abstention in both orders. Preserve 2.0.0 as a failed
baseline. The replay remains a repair test on known questions, not a held-out
benchmark or proof of reliability on arbitrary documents.
