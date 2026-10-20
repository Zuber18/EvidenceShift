"""Parse with pypdf; delegate token-aware chunking to LangChain."""
import hashlib
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader

MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 1000
MAX_TEXT = 5_000_000


def parse_document(filename: str, raw: bytes):
    source = Path(filename.replace('\\', '/')).name
    extension = Path(source).suffix.lower()
    if extension not in {'.pdf', '.txt', '.md', '.docx'}:
        raise ValueError('Supported formats: PDF, DOCX, UTF-8 TXT and MD.')
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('Upload a nonempty file no larger than 20 MiB.')
    sha = hashlib.sha256(raw).hexdigest()
    doc_id = 'doc_' + hashlib.sha256(raw + extension.encode()).hexdigest()[:20]
    warnings, pages, total = [], [], 0
    if extension == '.pdf':
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted:
            raise ValueError('Encrypted PDFs are not supported. Upload a decrypted copy.')
        if len(reader.pages) > MAX_PAGES:
            raise ValueError('PDF exceeds the 1,000-page limit.')
        extracted = ((i, page.extract_text() or '') for i, page in enumerate(reader.pages, 1))
    elif extension == '.docx':
        from .word_documents import extract_docx
        extracted = [(0, extract_docx(raw))]
    else:
        # Page 0 means not paginated, rather than claiming a PDF page exists.
        extracted = [(0, raw.decode('utf-8-sig'))]
    for page, text in extracted:
        total += len(text)
        if total > MAX_TEXT:
            raise ValueError('Extracted text exceeds the 5-million-character limit.')
        if text.strip():
            pages.append({'page': page, 'text': text})
        elif page:
            warnings.append(f'PDF page {page} had no extractable text and was skipped.')
    if not pages:
        raise ValueError('No extractable text. Scanned PDFs need OCR first; OCR is not included.')
    return {'document_id': doc_id, 'sha256': sha, 'source': source,
            'extension': extension, 'pages': pages, 'warnings': warnings}


def split_pages(parsed, splitter):
    """Split within pages, retaining actual PDF page numbers and stable chunk IDs."""
    chunks = []
    for page in parsed['pages']:
        for i, text in enumerate(splitter.split_text(page['text'])):
            if text.strip():
                chunks.append({
                    'id': f"{parsed['document_id']}_p{page['page']}_c{i}",
                    'text': text,
                    'metadata': {
                        'document_id': parsed['document_id'], 'source': parsed['source'],
                        'sha256': parsed['sha256'], 'page': page['page'], 'chunk': i,
                    },
                })
    if not chunks:
        raise ValueError('The splitter produced no text chunks.')
    return chunks
