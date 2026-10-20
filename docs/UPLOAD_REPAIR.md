# Local upload revision: source-first evidence

The uploaded Gift of the Magi sessions exposed missing retrieval evidence,
role reversal, invented explanations, incomplete answers, unsupported citations,
and two inputs rejected by the old 6,000-byte cap. The source assessment is saved
under `results/reviews/local_upload_20261019/assessment.json`.

## Install and verify

Save `install_upload_repair.py` in the existing project root. Stop the old
Streamlit terminal with Ctrl+C; keep Ollama running. Activate the existing venv.

```bash
python install_upload_repair.py .
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_source_first.py'
python evaluation/run_upload_repair.py
```

The replay locates the original PDF in saved local sessions and runs eight saved
questions in both evidence orders plus two no-context controls. It saves every
attempt and a complete ZIP after each attempt. The final terminal line identifies
the ZIP under `results/local_upload_session_.../`. Upload that file for assessment.
If the original session directory was moved, pass `--bundle /path/to/session.zip`.
Nothing is downloaded, sent to an external model provider or published.

To open the revised interface afterwards:

```bash
python -m streamlit run web_demo/local_app_v2.py
```

The old `web_demo/local_app.py` remains the baseline. The revised UI has separate
session state and export controls in the sidebar as well as at the bottom.
No new dependency or model installation is required.

## What changed

- The same measured MiniLM encoder, tokenizer-aware splitter and Chroma index
  remain in use. No TF-IDF fallback was introduced.
- Small corpora (at most 48 chunks and 20,000 text bytes, including chunk overlap)
  supply every indexed passage, in semantic rank order. This is full-corpus
  evidence mode, not an improvement claim about top-five retrieval recall.
- Larger corpora use ten semantic hits plus the preceding and following indexed
  passage in the same document. Neighbors can cross page boundaries. Missing
  corpus IDs and the seed hits are recorded. Retrieval can still miss evidence.
- Reversed uses exactly the same expanded context in reverse order.
- The model selects exact excerpts. Code checks each contiguous span against its
  assigned passage, copies the original source wording and attaches citations.
  Whitespace differences are allowed; word replacement, removal within a span,
  invented prose and swapped actor names are rejected.
- This is an explicit tradeoff: the answer display contains source excerpts,
  not a polished generated explanation. It prevents unquoted paraphrases from
  being delivered through this path. It does not establish excerpt relevance,
  complete answers, correct conflict classification, or justified abstention.
- A single extraction call replaces selection plus paraphrase generation.
  Partial-answer notes are model judgments and are labelled separately.
- Input budgeting includes serialized messages/schema, a 2,048-token output
  reservation and a 1,024-token template margin. UTF-8 byte count is a conservative
  token proxy, not exact model tokenization. The smallest 8k/16k/32k context that
  fits the estimate is requested. Oversized inputs fail without trimming evidence.
  Actual `prompt_eval_count`, raw output, options and timing are recorded. This
  does not independently prove the server never truncates a prompt.
- Larger context settings can increase local memory use. There are no retries or
  hidden model calls. No-context controls remain zero-call code abstentions.

## Evaluation limits

The supplied regression passages are the 17 unique chunks visible in the saved
traces, not a reconstruction of all 19 original chunks. The live replay re-ingests
the actual saved PDF to obtain its complete index. Expected-answer assessments
are not passed to the model. The replay combines multiple pipeline changes and
does not isolate their individual causal effects. Local controlled tests do not
substitute for an Ollama run or browser test on the user's machine.

The original API routes, cloud demo, generator, embedding identity lock and saved
results are preserved. The repair is not yet a cloud deployment or a claim of
universal factual reliability.

## Reference

- https://docs.ollama.com/api/chat — structured format and prompt token metrics.
- https://docs.ollama.com/context-length — context length and memory use.

## Rollback

The installer records added/changed paths and prior copies under
`fix_backups/upload_repair_<timestamp>/manifest.json`. Original application files
are not replaced. To run the baseline, launch `web_demo/local_app.py` again.
