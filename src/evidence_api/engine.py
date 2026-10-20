"""Generate cited answers and compare identical evidence under controlled changes."""
import json
import importlib.metadata as metadata
import platform
import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from .prompts import PROMPTS
from .evaluation import ABSTENTION, inspect_answer, assess_record, write_reports, archive_run

# Separate from the small-fixture run; document contexts need a larger window.
OPTIONS = {'temperature': 0, 'seed': 42, 'num_ctx': 8192, 'num_predict': 4096}
INPUT_BYTE_BUDGET = 6000


def user_message(question, chunks):
    evidence = '\n\n'.join(
        f"[{c['id']}] Source: {c['source']}; "
        f"location: {'PDF page ' + str(c['page']) if c['page'] else 'unpaginated text'}\n{c['text']}"
        for c in chunks
    )
    return f'Question: {question}\n\nEvidence:\n{evidence}'


def fit_context(question, chunks, prompt_names):
    """Conservative UTF-8 byte budget; use the same selected chunks for both prompts."""
    longest = max(len(PROMPTS[p].encode()) for p in prompt_names)
    if longest + len(user_message(question, []).encode()) > INPUT_BYTE_BUDGET:
        raise ValueError('Question is too large for the input budget.')
    kept, omitted = [], []
    for c in chunks:
        if longest + len(user_message(question, kept + [c]).encode()) <= INPUT_BYTE_BUDGET:
            kept.append(c)
        else:
            omitted.append(c['id'])
    return kept, omitted




class Engine:
    def __init__(self, store, client, root, model='qwen3:4b'):
        self.store, self.client, self.model = store, client, model
        self.runs = Path(root) / 'runs'
        self.runs.mkdir(parents=True, exist_ok=True)

    def generate(self, question, chunks, prompt_name):
        started = perf_counter()
        response = self.client.chat(
            model=self.model, messages=[{'role': 'system', 'content': PROMPTS[prompt_name]},
                                       {'role': 'user', 'content': user_message(question, chunks)}],
            think=True, stream=False, options=OPTIONS,
        )
        answer = (response.message.content or '').strip()
        return {'answer': answer, 'context': chunks, 'prompt_name': prompt_name,
                'user_prompt': user_message(question, chunks),
                'done_reason': response.done_reason, 'generated_tokens': response.eval_count,
                'seconds': round(perf_counter() - started, 2),
                'checks': inspect_answer(answer, chunks, response.done_reason)}

    def answer(self, question, top_k, document_ids, prompt_name):
        hits = self.store.search(question, top_k, document_ids)
        context, omitted = fit_context(question, hits, [prompt_name])
        result = self.generate(question, context, prompt_name)
        result.update({'retrieved': hits, 'omitted_for_budget': omitted,
                       'question': question, 'model': self.model})
        # Keep raw model output, but do not deliver mechanically invalid answers.
        result['raw_answer'] = result['answer']
        result['status'] = 'needs_factual_review' if result['checks']['mechanical_pass'] else 'blocked'
        if result['status'] == 'blocked':
            result['answer'] = None
        return result

    def experiment(self, request):
        hits = self.store.search(request.question, request.top_k, request.document_ids)
        context, omitted = fit_context(request.question, hits, request.prompts)
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:8]
        folder = self.runs / run_id
        folder.mkdir()
        setup = {'run_id': run_id, 'request': request.model_dump(), 'model': self.model,
                 'options': OPTIONS, 'think': True, 'profile': self.store.profile,
                 'prompts': {p: PROMPTS[p] for p in request.prompts},
                 'retrieved': hits, 'omitted_for_budget': omitted,
                 'documents': self.store.documents(),
                 'note': 'Expected answers are review labels, never model inputs.'}
        setup['python'] = platform.python_version()
        setup['api_version'] = '0.3.0'
        setup['packages'] = {}
        for name in ['fastapi', 'pypdf', 'chromadb', 'langchain-text-splitters', 'sentence-transformers', 'ollama']:
            try:
                setup['packages'][name] = metadata.version(name)
            except metadata.PackageNotFoundError:
                setup['packages'][name] = None
        try:
            setup['installed_models'] = self.client.list().model_dump(mode='json')
        except Exception as exc:
            setup['model_inventory_error'] = str(exc)
        (folder / 'setup.json').write_text(json.dumps(setup, indent=2), encoding='utf-8')
        variants = {'retrieved': context, 'reversed': list(reversed(context)), 'no_context': []}
        records = []
        for variant in request.variants:
            for prompt in request.prompts:
                record = {'variant': variant, 'prompt_name': prompt}
                passages = variants[variant]
                try:
                    record.update(self.generate(request.question, passages, prompt))
                    gold = set(request.gold_evidence_ids)
                    record['gold_evidence_recall'] = (
                        len(gold & {c['id'] for c in passages}) / len(gold) if gold else None
                    )
                    # Only the empty-context condition has a universal prescribed response.
                    record['empty_context_check'] = (
                        record['checks']['completed'] and record['checks']['exact_abstention']
                    ) if not passages else None
                except Exception as exc:
                    record['error'] = f'{type(exc).__name__}: {exc}'
                record['checks'] = assess_record(record)
                record['status'] = ('needs_factual_review' if record['checks']['mechanical_pass'] else 'blocked')
                record['delivery_answer'] = record.get('answer') if record['checks']['mechanical_pass'] else None
                records.append(record)
                with (folder / 'answers.jsonl').open('a', encoding='utf-8') as file:
                    file.write(json.dumps(record, ensure_ascii=False) + '\n')
                # Refresh after every attempt, including errors; interrupted runs retain a report.
                write_reports({'run_id': run_id, 'records': records}, folder, setup)
        result = {'run_id': run_id, 'records': records, 'retrieved': hits,
                  'omitted_for_budget': omitted, 'review_required': True}
        result['report_files'] = ['review.json', 'review.csv', 'review_bundle.zip']
        (folder / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        write_reports(result, folder, setup)
        archive_run(folder)
        return result
