"""Chroma owns persistence and nearest-neighbor search; no custom vector index."""
import hashlib
import json
from pathlib import Path
from threading import RLock
import chromadb
from .ingestion import parse_document, split_pages


class DocumentStore:
    """Own document bytes and Chroma passages for one retrieval profile.

    The collection name separates embedding/chunking profiles. Encoding and
    index persistence remain separate from answer generation.
    """
    def __init__(self, root, encoder, splitter, profile):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.encoder, self.splitter, self.profile = encoder, splitter, profile
        self.lock = RLock()
        # Different encoders or chunking settings must not share an index.
        fingerprint = hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()[:16]
        self.client = chromadb.PersistentClient(path=str(self.root / 'chroma'))
        self.collection = self.client.get_or_create_collection(
            name=f'passages-{fingerprint}', embedding_function=None,
            configuration={'hnsw': {'space': 'cosine'}},
        )
        self.originals = self.root / 'originals' / fingerprint
        self.originals.mkdir(parents=True, exist_ok=True)

    def encode(self, texts):
        """Return normalized embedding vectors as database-compatible lists."""
        return self.encoder.encode(texts, batch_size=32, normalize_embeddings=True,
                                   convert_to_numpy=True).tolist()

    def ingest(self, filename, raw):
        """Deduplicate, chunk, embed and persist one document.

        On a failed batch or original-file write, remove that document's partial
        index entries. Identical bytes and extension produce a stable document ID.
        """
        parsed = parse_document(filename, raw)
        doc_id = parsed['document_id']
        with self.lock:
            old = self.collection.get(where={'document_id': doc_id}, include=['metadatas'])
            saved_path = self.originals / (doc_id + parsed['extension'])
            if old['ids'] and saved_path.exists():
                return {'document_id': doc_id, 'source': old['metadatas'][0]['source'],
                        'chunks': len(old['ids']), 'deduplicated': True,
                        'warnings': parsed['warnings']}
            if old['ids']:
                self.collection.delete(where={'document_id': doc_id})
            chunks = split_pages(parsed, self.splitter)
            saved_path = self.originals / (doc_id + parsed['extension'])
            try:
                # Batch both embedding and database writes; don't embed all documents at query time.
                for start in range(0, len(chunks), 64):
                    batch = chunks[start:start + 64]
                    self.collection.add(
                        ids=[c['id'] for c in batch], documents=[c['text'] for c in batch],
                        metadatas=[c['metadata'] for c in batch],
                        embeddings=self.encode([c['text'] for c in batch]),
                    )
                temporary = saved_path.with_suffix('.tmp')
                temporary.write_bytes(raw)
                temporary.replace(saved_path)
            except Exception:
                self.collection.delete(where={'document_id': doc_id})
                saved_path.unlink(missing_ok=True)
                raise
            return {'document_id': doc_id, 'source': parsed['source'], 'sha256': parsed['sha256'],
                    'chunks': len(chunks), 'deduplicated': False, 'warnings': parsed['warnings']}

    def documents(self):
        """Build a document catalog from paginated metadata without loading text."""
        grouped = {}
        with self.lock:
            # Metadata-only pages avoid materializing all extracted text for the catalog.
            for offset in range(0, self.collection.count(), 1000):
                result = self.collection.get(limit=1000, offset=offset, include=['metadatas'])
                for m in result['metadatas']:
                    d = grouped.setdefault(m['document_id'], {
                        'document_id': m['document_id'], 'source': m['source'],
                        'sha256': m['sha256'], 'chunks': 0,
                    })
                    d['chunks'] += 1
        return list(grouped.values())

    def search(self, question, top_k, document_ids=None):
        """Return cosine-nearest passages, optionally restricted to document IDs.

        Distances are retrieval scores, not factual-support confidence.
        """
        with self.lock:
            count = self.collection.count()
            if not count:
                return []
            kwargs = {'where': {'document_id': {'$in': document_ids}}} if document_ids else {}
            result = self.collection.query(
                query_embeddings=self.encode([question]), n_results=min(top_k, count),
                include=['documents', 'metadatas', 'distances'], **kwargs,
            )
        return [{'id': cid, 'text': text, **meta, 'distance': float(distance)}
                for cid, text, meta, distance in zip(
                    result['ids'][0], result['documents'][0],
                    result['metadatas'][0], result['distances'][0])]

    def chunks(self, document_id, limit=50, offset=0):
        """Read a paginated chunk listing for one indexed document."""
        result = self.collection.get(where={'document_id': document_id}, limit=limit,
                                     offset=offset, include=['documents', 'metadatas'])
        return [{'id': cid, 'text': text, **meta} for cid, text, meta in
                zip(result['ids'], result['documents'], result['metadatas'])]

    def delete(self, document_id):
        """Delete indexed passages and original bytes for one document.

        Existing experiment archives retain their own saved evidence.
        """
        with self.lock:
            found = self.collection.get(where={'document_id': document_id}, include=[])
            self.collection.delete(where={'document_id': document_id})
            for path in self.originals.glob(document_id + '.*'):
                path.unlink()
            return len(found['ids'])
