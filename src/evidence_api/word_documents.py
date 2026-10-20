"""Extract DOCX body paragraphs and tables without inventing page numbers."""
from io import BytesIO
from zipfile import ZipFile


def extract_docx(raw):
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    with ZipFile(BytesIO(raw)) as archive:
        if sum(info.file_size for info in archive.infolist()) > 10 * 1024 * 1024:
            raise ValueError('DOCX expanded size exceeds the 10 MiB limit.')
    blocks = []
    for block in Document(BytesIO(raw)).iter_inner_content():
        if isinstance(block, Paragraph):
            blocks.append(block.text)
        elif isinstance(block, Table):
            blocks.extend(' | '.join(cell.text for cell in row.cells) for row in block.rows)
    return '\n\n'.join(blocks)
