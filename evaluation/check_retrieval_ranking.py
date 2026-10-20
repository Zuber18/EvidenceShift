"""Compare local API and demo retrieval on multi-chunk TXT and DOCX fixtures.

Place this file in evaluation/ and run it from the project root. No language
model generation is performed. Every run saves its fixtures and report.
"""
import argparse
import importlib.metadata
import json
import platform
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

TOPICS = [
    ('Domestic travel', 'Advance approval is optional for domestic rail journeys. '
     'Travellers must retain the train ticket and record the business purpose.'),
    ('International travel', 'International journeys require written approval before booking. '
     'The approval must identify the destination country and the planned travel dates.'),
    ('Expense reimbursement', 'Reimbursement requires an itemised receipt and a business purpose. '
     'Claims must be submitted within thirty days of the purchase.'),
    ('Hotel cancellation', 'Hotel reservations may be cancelled without a fee until forty-eight '
     'hours before arrival. Later cancellation charges require a manager review.'),
    ('Equipment loans', 'Borrowed cameras must be returned to the equipment desk within seven '
     'days. The borrower records the serial number and checks the lens on return.'),
    ('Laboratory access', 'Visitors may enter the chemistry laboratory only with an escort. '
     'Safety goggles and closed shoes are required inside the laboratory.'),
    ('Conference registration', 'Conference registrations costing more than four hundred euros '
     'require budget-owner approval. The request must identify the conference programme.'),
    ('Library borrowing', 'Library books can be borrowed for twenty-one days. A renewal is '
     'permitted only when no other reader has reserved the same book.'),
    ('Bicycle parking', 'Bicycles must be locked in the designated courtyard racks. '
     'Parking in fire exits or inside corridors is prohibited.'),
    ('Data retention', 'Survey responses are retained for ninety days after the study closes. '
     'After that period, identifiable responses must be deleted from the study workspace.'),
    ('Meeting rooms', 'Meeting rooms must be released if the organiser cancels the meeting. '
     'Room bookings may not exceed three hours without facilities approval.'),
    ('Meal allowances', 'Meal allowances are available only for overnight business travel. '
     'A meal supplied by the conference organiser must not be claimed again.'),
]
QUESTIONS = [
    'Does a domestic rail journey require advance approval?',
    'What approval is needed before booking international travel?',
    'What is required to obtain expense reimbursement?',
    'When can a hotel booking be cancelled without paying a fee?',
    'How long can someone borrow a camera?',
    'Can a visitor enter the chemistry laboratory without an escort?',
]


def make_fixtures():
    """Create varied fictional sections long enough to exercise token splitting."""
    from docx import Document
    paragraphs = []
    for number, (title, rule) in enumerate(TOPICS, 1):
        paragraphs.append(
            f'Section {number}: {title}. {rule} '
            f'This section applies specifically to {title.lower()} in the fictional '
            'example organisation. It does not replace the rules in other sections. '
            'The responsible coordinator records requests, checks the relevant dates, '
            'and keeps supporting documents with the request. Exceptions require a '
            'written explanation identifying the particular rule and the person '
            'authorising the exception. An incomplete request is returned for '
            'clarification rather than treated as an automatic approval. '
            f'The controlling subject of this section remains {title.lower()}.'
        )
    text = 'Fictional operations handbook for retrieval testing.\n\n' + '\n\n'.join(paragraphs)
    document = Document()
    document.add_paragraph('Fictional operations handbook for retrieval testing.')
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = 'DOCX table extraction check'
    table.cell(0, 1).text = 'Record the equipment serial number.'
    stream = BytesIO()
    document.save(stream)
    return [('handbook.txt', text.encode('utf-8')), ('handbook.docx', stream.getvalue())]


def compare_document(local_store, demo, retrieve, name):
    """Compare outputs, not merely the top-level success flags."""
    session = demo['_semantic_session']
    document_id = demo['document_id']
    local_chunks = local_store.chunks(document_id, limit=200)
    demo_chunks = session.store.chunks(document_id, limit=200)
    ordered = lambda rows: sorted(rows, key=lambda row: row['id'])
    record = {
        'source': name,
        'local_chunk_count': len(local_chunks),
        'demo_chunk_count': len(demo_chunks),
        'enough_chunks_for_ranking': len(local_chunks) >= 6 and len(demo_chunks) >= 6,
        'chunks_match': ordered(local_chunks) == ordered(demo_chunks),
        'profiles_match': local_store.profile == session.profile,
        'profile': dict(local_store.profile),
        'chunks': ordered(local_chunks),
        'queries': [],
    }
    for question in QUESTIONS:
        local = local_store.search(question, 5, [document_id])
        hosted = retrieve(demo, question)
        ids_match = [row['id'] for row in local] == [row['id'] for row in hosted]
        distances_match = len(local) == len(hosted) and all(
            abs(a['distance'] - b['distance']) <= 1e-5 for a, b in zip(local, hosted)
        )
        contents_match = len(local) == len(hosted) and all(
            {key: value for key, value in a.items() if key != 'distance'} ==
            {key: value for key, value in b.items() if key != 'distance'}
            for a, b in zip(local, hosted)
        )
        record['queries'].append({
            'question': question, 'five_results_each': len(local) == len(hosted) == 5,
            'ordered_ids_match': ids_match, 'distances_match': distances_match,
            'contents_match': contents_match, 'local': local, 'demo': hosted,
        })
    record['passed'] = all(record[key] for key in (
        'enough_chunks_for_ranking', 'chunks_match', 'profiles_match'
    )) and all(all(query[key] for key in (
        'five_results_each', 'ordered_ids_match', 'distances_match', 'contents_match'
    )) for query in record['queries'])
    return record


def check(output, engine_factory=None, demo_api=None):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:8]
    folder = Path(output) / ('retrieval_ranking_' + stamp)
    folder.mkdir(parents=True)
    report = {
        'check': 'multi-chunk-semantic-parity-v1', 'complete': False, 'passed': False,
        'documents': [], 'top_k': 5, 'distance_tolerance': 1e-5,
        'note': 'Local API versus demo retrieval on this machine. This does not test '
                'cloud hosting, answer accuracy, or independently assess retrieval relevance.',
    }
    path = folder / 'retrieval_ranking.json'
    try:
        if engine_factory is None:
            from evidence_api.app import build_engine
            engine_factory = build_engine
        if demo_api is None:
            from web_demo.support import parse_upload, retrieve, close_document
            demo_api = (parse_upload, retrieve, close_document)
        parse_upload, retrieve, close_document = demo_api
        with tempfile.TemporaryDirectory(prefix='evidenceshift_ranking_') as tmp:
            local = engine_factory(data_root=tmp)
            for name, raw in make_fixtures():
                (folder / name).write_bytes(raw)
                summary = local.store.ingest(name, raw)
                demo = parse_upload(name, raw)
                try:
                    result = compare_document(local.store, demo, retrieve, name)
                    result['document_ids_match'] = summary['document_id'] == demo['document_id']
                    result['passed'] = result['passed'] and result['document_ids_match']
                    report['documents'].append(result)
                    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
                    print(name, 'chunks:', result['local_chunk_count'], 'passed:', result['passed'])
                finally:
                    close_document(demo)
        report['passed'] = len(report['documents']) == 2 and all(
            item['passed'] for item in report['documents']
        )
        report['packages'] = {}
        for name in ['chromadb', 'sentence-transformers', 'langchain-text-splitters', 'pypdf', 'python-docx']:
            try:
                report['packages'][name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                report['packages'][name] = None
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
    report['complete'] = True
    report['platform'] = platform.platform()
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    with zipfile.ZipFile(folder / 'retrieval_ranking.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for item in folder.iterdir():
            if item.suffix != '.zip':
                archive.write(item, item.name)
    print('Passed:', report['passed'])
    print('Saved:', path.resolve())
    if report.get('error'):
        print('Error:', report['error'])
    return report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(ROOT / 'results'))
    args = parser.parse_args()
    raise SystemExit(0 if check(args.output) else 1)
