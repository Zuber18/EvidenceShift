import hashlib
import json
import re
from io import BytesIO
from types import SimpleNamespace
import numpy as np
import pytest
from fastapi.testclient import TestClient
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from evidence_api.app import create_app, ExperimentRequest
from evidence_api.engine import Engine, ABSTENTION, fit_context, user_message, INPUT_BYTE_BUDGET
from evidence_api.ingestion import parse_document
from evidence_api.store import DocumentStore
from evidence_api.prompts import PROMPTS


class TestEncoder:
    __test__ = False
    def __init__(self):
        self.calls = 0
        self.fail = False
    def encode(self, texts, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError('Simulated embedding failure')
        vectors = np.zeros((len(texts), 64), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in re.findall(r'\w+', text.lower()):
                vectors[i, int(hashlib.md5(word.encode()).hexdigest()[:8], 16) % 64] += 1
        return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1)


class TestLLM:
    __test__ = False
    def __init__(self):
        self.calls = []
        self.fail_at = None
    def list(self):
        return SimpleNamespace(model_dump=lambda **kwargs: {'models': [{'model': 'test-double'}]})
    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == self.fail_at:
            raise TimeoutError('Simulated LLM timeout')
        ids = re.findall(r'\[(doc_[^\]]+)\]', kwargs['messages'][1]['content'])
        answer = f"A test answer [{ids[0]}]." if ids else ABSTENTION
        return SimpleNamespace(message=SimpleNamespace(content=answer), done_reason='stop', eval_count=10)


@pytest.fixture
def store(tmp_path):
    return DocumentStore(tmp_path, TestEncoder(),
                         RecursiveCharacterTextSplitter(chunk_size=180, chunk_overlap=30),
                         {'embedding_model': 'test-hash', 'splitter': 'characters-for-tests'})


@pytest.fixture
def api(store, tmp_path):
    engine = Engine(store, TestLLM(), tmp_path)
    with TestClient(create_app(engine)) as client:
        yield client, engine


def test_ingest_search_scope_deduplicate_delete(api):
    c, e = api
    a = c.post('/documents', files={'file': ('alpha.txt', b'Alpha reactor pressure is 25 bar.')}).json()
    b = c.post('/documents', files={'file': ('beta.md', b'Beta reactor pressure is 80 bar.')}).json()
    calls = e.store.encoder.calls
    same = c.post('/documents', files={'file': ('renamed.txt', b'Alpha reactor pressure is 25 bar.')}).json()
    assert same['deduplicated'] and e.store.encoder.calls == calls
    assert len(c.get('/documents').json()) == 2
    hits = c.post('/search', json={'question': 'reactor pressure', 'document_ids': [a['document_id']]}).json()['passages']
    assert hits and all(x['document_id'] == a['document_id'] for x in hits)
    assert c.get(f"/documents/{a['document_id']}/chunks").json()[0]['page'] == 0
    assert c.delete('/documents/' + a['document_id']).status_code == 200
    assert len(c.get('/documents').json()) == 1
    assert c.post('/search', json={'question': 'pressure', 'document_ids': [a['document_id']]}).status_code == 404


def test_persistence(store):
    doc = store.ingest('policy.txt', b'Policy states refunds within thirty days.')
    reopened = DocumentStore(store.root, TestEncoder(), store.splitter, store.profile)
    assert reopened.documents()[0]['document_id'] == doc['document_id']
    assert reopened.search('refunds', 3)[0]['text'].startswith('Policy')


def test_embedding_error_rolls_back(store):
    store.encoder.fail = True
    with pytest.raises(RuntimeError):
        store.ingest('policy.txt', b'Policy text.')
    assert store.collection.count() == 0
    store.encoder.fail = False
    assert not store.ingest('policy.txt', b'Policy text.')['deduplicated']


def test_partial_ingestion_can_be_retried(store):
    raw = b'Complete document.'
    parsed = parse_document('policy.txt', raw)
    store.collection.add(ids=['partial'], documents=['incomplete'],
                         metadatas=[{'document_id': parsed['document_id'], 'source': 'policy.txt'}],
                         embeddings=[[1.] + [0.] * 63])
    assert not store.ingest('policy.txt', raw)['deduplicated']
    assert store.collection.get(ids=['partial'])['ids'] == []


def test_validation_and_empty_index(api):
    c, _ = api
    assert c.post('/documents', files={'file': ('bad.exe', b'bad')}).status_code == 422
    assert c.post('/documents', files={'file': ('empty.txt', b'')}).status_code == 422
    assert c.post('/documents', files={'file': ('bad.txt', b'\xff')}).status_code == 422
    assert c.post('/documents', files={'file': ('bad.pdf', b'not a pdf')}).status_code == 422
    assert c.post('/search', json={'question': 'x', 'top_k': 0}).status_code == 422
    assert c.post('/search', json={'question': 'x', 'document_ids': []}).status_code == 422
    assert c.post('/search', json={'question': '   '}).status_code == 422
    assert c.post('/search', json={'question': 'x'}).json()['passages'] == []
    assert c.post('/answer', json={'question': 'x'}).json()['checks']['exact_abstention']


def test_pdf_page_provenance_and_blank_page():
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                             NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 50 700 Td (Applications close in January.) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    writer.add_blank_page(width=600, height=800)
    b = BytesIO(); writer.write(b)
    result = parse_document('handbook.pdf', b.getvalue())
    assert result['pages'][0]['page'] == 1 and 'January' in result['pages'][0]['text']
    assert 'page 2' in result['warnings'][0]


def test_labels_stay_out_and_context_variants_saved(api):
    c, e = api
    doc = c.post('/documents', files={'file': ('notes.txt', (b'Apples have seeds. ' * 60))}).json()
    response = c.post('/experiments', json={'question': 'What has seeds?', 'document_ids': [doc['document_id']],
                                           'top_k': 3, 'expected_answer': 'SECRET_REVIEW_LABEL'})
    assert response.status_code == 200
    result = response.json(); assert len(result['records']) == 6
    records = result['records']
    assert [x['id'] for x in records[0]['context']] == list(reversed([x['id'] for x in records[2]['context']]))
    assert records[4]['empty_context_check'] and records[5]['empty_context_check']
    assert all('SECRET_REVIEW_LABEL' not in json.dumps(x['messages']) for x in e.client.calls)
    assert all(x['think'] for x in e.client.calls)
    folder = e.runs / result['run_id']
    assert len((folder / 'answers.jsonl').read_text().splitlines()) == 6
    assert c.get('/runs/' + result['run_id']).json() == result


def test_failure_does_not_erase_other_answers(api):
    c, e = api; e.client.fail_at = 2
    result = c.post('/experiments', json={'question': 'Any evidence?'}).json()
    assert 'error' in result['records'][1] and len(result['records']) == 6
    assert result['records'][2]['checks']['completed']


def test_unknown_gold_rejected(api):
    c, _ = api
    assert c.post('/experiments', json={'question': 'x', 'gold_evidence_ids': ['invented']}).status_code == 422


def test_budget_is_shared_and_citations_not_correctness(api):
    c, e = api
    chunks = [{'id': str(i), 'source': 'x', 'page': 1, 'text': 'é' * 1500} for i in range(8)]
    selected, omitted = fit_context('Question?', chunks, list(PROMPTS))
    assert omitted
    for prompt in PROMPTS.values():
        assert len(prompt.encode()) + len(user_message('Question?', selected).encode()) <= INPUT_BYTE_BUDGET
    checks = c.post('/answer', json={'question': 'x'}).json()['checks']
    assert checks['citation_ids_valid'] and not checks['has_citations']
    assert checks['factual_correctness'] == 'not_automatically_scored'
