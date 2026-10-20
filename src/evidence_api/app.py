"""FastAPI handles validation, uploads, OpenAPI docs and synchronous worker dispatch."""
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pypdf.errors import PdfReadError
from .engine import Engine
from .ingestion import MAX_BYTES

DocumentId = Annotated[str, StringConstraints(pattern=r'^doc_[a-f0-9]{20}$')]
PromptName = Literal['original', 'candidate_v2', 'candidate_v3']
Variant = Literal['retrieved', 'reversed', 'no_context']


class SearchRequest(BaseModel):
    """Validate a question and optional document scope before retrieval."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=1200)
    top_k: int = Field(default=5, ge=1, le=8)
    document_ids: list[DocumentId] | None = Field(default=None, min_length=1)


class AnswerRequest(SearchRequest):
    """Select a preserved API prompt for one document-grounded response."""
    prompt_name: PromptName = 'original'


class ExperimentRequest(SearchRequest):
    """Declare prompt/order comparisons and labels excluded from model input."""
    prompts: list[PromptName] = Field(default=['original', 'candidate_v2'], min_length=1, max_length=3)
    variants: list[Variant] = Field(default=['retrieved', 'reversed', 'no_context'], min_length=1, max_length=3)
    expected_answer: str | None = Field(default=None, max_length=4000)
    gold_evidence_ids: list[str] = Field(default_factory=list, max_length=100)


def build_engine(data_root=None):
    """Construct the CPU encoder, tokenizer-aware splitter, store and client.

    The caller may provide an isolated data root. Instantiating the Ollama
    client does not establish that its server or selected model is ready.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from sentence_transformers import SentenceTransformer
    from ollama import Client
    from .store import DocumentStore
    root = Path(data_root if data_root is not None else os.environ.get('EVIDENCESHIFT_DATA', 'data_local')).resolve()
    model = os.environ.get('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
    revision = os.environ.get('EMBEDDING_REVISION')
    encoder = SentenceTransformer(model, revision=revision, device='cpu')
    # Respect MiniLM's input window: split by this encoder's tokens, not arbitrary characters.
    chunk_tokens = min(180, encoder.max_seq_length - 8)
    if chunk_tokens < 40:
        raise ValueError('Embedding model input window is too small.')
    splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        encoder.tokenizer, chunk_size=chunk_tokens, chunk_overlap=30,
    )
    profile = {'embedding_model': model, 'requested_revision': revision,
               'resolved_revision': getattr(encoder[0].auto_model.config, '_commit_hash', None),
               'chunk_tokens': chunk_tokens, 'overlap_tokens': 30,
               'splitter': 'recursive-huggingface-token-v1', 'parser': 'pypdf-page-v1'}
    store = DocumentStore(root, encoder, splitter, profile)
    return Engine(store, Client(host=os.environ.get('OLLAMA_HOST', 'http://localhost:11434'),
                               timeout=180.0), root,
                  model=os.environ.get('OLLAMA_MODEL', 'qwen3:4b'))


def create_app(engine=None):
    """Create API routes around an injected or lifespan-initialized engine.

    Engine injection supports controlled tests without loading real weights.
    """
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = engine if engine is not None else build_engine()
        yield

    app = FastAPI(title='EvidenceShift — Document API', version='0.3.0', lifespan=lifespan,
                  description='Local document RAG and controlled evidence experiments. '
                              'Answers require review; valid citation IDs do not prove correctness.')

    def backend():
        return app.state.engine

    def check_documents(document_ids):
        if document_ids:
            known = {d['document_id'] for d in backend().store.documents()}
            unknown = set(document_ids) - known
            if unknown:
                raise HTTPException(404, f'Unknown document IDs: {sorted(unknown)}')

    @app.get('/health')
    def health():
        return {'status': 'ready', 'model': backend().model,
                'profile': backend().store.profile,
                'ollama_status': 'not_checked', 'documents': len(backend().store.documents())}

    @app.post('/documents', status_code=201)
    def ingest(file: Annotated[UploadFile, File()]):
        try:
            raw = file.file.read(MAX_BYTES + 1)
            return backend().store.ingest(file.filename or '', raw)
        except (ValueError, UnicodeError, PdfReadError) as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            file.file.close()

    @app.get('/documents')
    def documents():
        return backend().store.documents()

    @app.get('/documents/{document_id}/chunks')
    def chunks(document_id: DocumentId, limit: int = Query(50, ge=1, le=200),
               offset: int = Query(0, ge=0)):
        check_documents([document_id])
        return backend().store.chunks(document_id, limit, offset)

    @app.delete('/documents/{document_id}')
    def delete(document_id: DocumentId):
        check_documents([document_id])
        return {'deleted_chunks': backend().store.delete(document_id),
                'note': 'Earlier experiment records still retain their evidence snapshots.'}

    @app.post('/search')
    def search(request: SearchRequest):
        check_documents(request.document_ids)
        return {'passages': backend().store.search(request.question, request.top_k, request.document_ids)}

    @app.post('/answer')
    def answer(request: AnswerRequest):
        check_documents(request.document_ids)
        try:
            return backend().answer(**request.model_dump())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(503, f'Generation failed: {exc}') from exc

    @app.post('/experiments')
    def experiment(request: ExperimentRequest):
        check_documents(request.document_ids)
        request.prompts = list(dict.fromkeys(request.prompts))
        request.variants = list(dict.fromkeys(request.variants))
        if request.gold_evidence_ids:
            found = backend().store.collection.get(ids=request.gold_evidence_ids, include=['metadatas'])
            if set(found['ids']) != set(request.gold_evidence_ids):
                raise HTTPException(422, 'Gold evidence IDs must exist in this index.')
            if request.document_ids and any(m['document_id'] not in request.document_ids for m in found['metadatas']):
                raise HTTPException(422, 'Gold evidence must belong to the selected documents.')
        try:
            return backend().experiment(request)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get('/runs/{run_id}')
    def run(run_id: Annotated[str, StringConstraints(pattern=r'^\d{8}T\d{6}Z_[a-f0-9]{8}$')]):
        folder = backend().runs / run_id
        if not folder.is_dir():
            raise HTTPException(404, 'Run not found.')
        result_path = folder / 'result.json'
        if result_path.exists():
            return json.loads(result_path.read_text(encoding='utf-8'))
        answers = folder / 'answers.jsonl'
        return {'run_id': run_id, 'status': 'partial', 'records':
                [json.loads(line) for line in answers.read_text().splitlines()] if answers.exists() else []}

    return app


app = create_app()
