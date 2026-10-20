"""Session-isolated document stores built from the local API's retrieval components."""
from functools import lru_cache
from tempfile import TemporaryDirectory
from threading import RLock

PROFILE = 'shared-local-minilm-chroma-v1'
_ENCODER_LOCK = RLock()


@lru_cache(maxsize=1)
def retrieval_assets():
    """Load the API's encoder and splitter once; never call its answer endpoint."""
    from evidence_api.app import build_engine
    # The empty bootstrap store is isolated from data_local and visitor documents.
    directory = TemporaryDirectory(prefix='evidenceshift_assets_')
    try:
        engine = build_engine(data_root=directory.name)
    except Exception:
        directory.cleanup()
        raise
    return engine.store.encoder, engine.store.splitter, dict(engine.store.profile), directory


def create_store(root):
    from evidence_api.store import DocumentStore
    with _ENCODER_LOCK:
        encoder, splitter, profile, _ = retrieval_assets()
    return DocumentStore(root, encoder, splitter, dict(profile))


class SemanticDocument:
    """Own one temporary Chroma store and its original document for a UI session."""
    def __init__(self, filename, raw, store_factory=None):
        self.directory = TemporaryDirectory(prefix='evidenceshift_document_')
        self.closed = False
        self.store = None
        try:
            self.store = (store_factory or create_store)(self.directory.name)
            with _ENCODER_LOCK:
                summary = self.store.ingest(filename, raw)
            self.document_id = summary['document_id']
            self.profile = dict(self.store.profile)
            self.summary = summary
        except Exception:
            self.close()
            raise

    def search(self, question, top_k=5):
        if self.closed:
            raise ValueError('This document session has been cleared.')
        # The shared encoder is serialized; the store itself also protects Chroma access.
        with _ENCODER_LOCK:
            return self.store.search(question, top_k, [self.document_id])

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.store is not None:
                self.store.client.delete_collection(self.store.collection.name)
        finally:
            self.directory.cleanup()
