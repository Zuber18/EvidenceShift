"""Compare real local API and demo retrieval; save a report without running an LLM."""
import argparse
import importlib.metadata
import json
import platform
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'src'))


def check(output):
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder=Path(output)/('retrieval_parity_'+stamp)
    folder.mkdir(parents=True,exist_ok=False)
    report={'check':'real-semantic-retrieval-parity','complete':False,'passed':False,'cases':[],
            'note':'Checks ingestion and retrieval parity on a small fixture, not answer accuracy or hosting capacity.'}
    try:
        from evidence_api.app import build_engine
        from web_demo.support import parse_upload,retrieve,close_document
        fixture=(ROOT/'evaluation/fixtures/travel_policy.txt').read_bytes()
        with tempfile.TemporaryDirectory(prefix='evidenceshift_parity_') as tmp:
            local=build_engine(data_root=tmp)
            summary=local.store.ingest('travel_policy.txt',fixture)
            demo=parse_upload('travel_policy.txt',fixture)
            try:
                session=demo['_semantic_session']
                local_chunks=local.store.chunks(summary['document_id'],limit=200)
                demo_chunks=session.store.chunks(demo['document_id'],limit=200)
                ordered=lambda rows: sorted(rows,key=lambda row:row['id'])
                report['chunks_match']=ordered(local_chunks)==ordered(demo_chunks)
                report['profiles_match']=local.store.profile==session.profile
                report['profile']=local.store.profile
                report['document_ids_match']=summary['document_id']==demo['document_id']
                report['chunks']=ordered(local_chunks)
                questions=['Does domestic travel require advance approval?',
                           'What approval is required for international travel?',
                           'When are expenses reimbursable?']
                for question in questions:
                    a=local.store.search(question,5,[summary['document_id']])
                    b=retrieve(demo,question)
                    ids_match=[r['id'] for r in a]==[r['id'] for r in b]
                    distance_match=len(a)==len(b) and all(abs(x['distance']-y['distance'])<=1e-5 for x,y in zip(a,b))
                    report['cases'].append({'question':question,'ids_match':ids_match,
                                            'distances_match':distance_match,'local':a,'demo':b})
                report['passed']=all(report[k] for k in ['chunks_match','profiles_match','document_ids_match']) and all(
                    c['ids_match'] and c['distances_match'] for c in report['cases'])
            finally:
                close_document(demo)
        report['packages']={name:importlib.metadata.version(name) for name in
                            ['chromadb','sentence-transformers','langchain-text-splitters','pypdf']}
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
    report['complete']=True;report['platform']=platform.platform()
    path=folder/'retrieval_parity.json';path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    with zipfile.ZipFile(folder/'retrieval_parity.zip','w',zipfile.ZIP_DEFLATED) as archive:
        archive.write(path,path.name)
    print('Passed:',report['passed']);print('Saved:',path.resolve())
    if report.get('error'): print('Error:',report['error'])
    return report['passed']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=str(ROOT/'results'))
    args=parser.parse_args()
    raise SystemExit(0 if check(args.output) else 1)
