"""Evaluate fresh fixed contexts with preserved baseline generation; no model judge."""
import argparse
import copy
import csv
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from evidence_api import grounded as base,fresh_candidates as experiment


def load_plan():
    raw=(ROOT/'evaluation/fresh_baseline_cases.json').read_bytes()
    plan=json.loads(raw)
    if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=plan['baseline_module_sha256']:
        raise ValueError('The preserved grounded baseline module changed. Do not run a modified baseline under this plan.')
    if base.VERSION!=plan['baseline_generation_version'] or experiment.VERSION!=plan['experiment_version']:
        raise ValueError('Frozen plan and experiment versions differ')
    if len(plan['cases'])!=plan['case_count'] or len({c['id'] for c in plan['cases']})!=plan['case_count']:
        raise ValueError('Invalid frozen case inventory')
    for case in plan['cases']:
        for passage in case['context']:
            source=(ROOT/'evaluation/fresh_sources'/passage['source']).read_bytes()
            if source.decode('utf-8')!=passage['text'] or hashlib.sha256(source).hexdigest()!=passage['sha256']:
                raise ValueError('Frozen source text differs: '+passage['source'])
    return plan,raw


def report_text(records):
    lines=['# Fresh baseline candidate report','','This report records answers and evidence. It is not an automatic factual score.',
           'Supplied contexts bypass retrieval. Empty-context rows are code controls, not model reasoning tests.','']
    for rec in records:
        r=rec['result']
        lines += ['## '+rec['case_id']+' / '+rec['variant'],'','Question: '+r['question'],'',
                  'Mechanical status: '+r['status'],'','Candidate:', '', '> '+(r['candidate_answer'] or '(No mechanically valid candidate)').replace('\n','\n> '),'',
                  'Source assessment criteria:', '']
        lines += ['- '+x for x in rec['source_review_criteria']]
        for link in r.get('claim_source_records',[]):
            lines += ['', 'Claim '+str(link['claim_index'])+': '+link['claim_text'],'',
                      'Citation IDs: '+', '.join(link['passage_ids']),'']
            for quote in link['selected_quotations']:
                lines += ['> '+quote.replace('\n','\n> '),'']
        lines += ['', 'Original supplied context:', '']
        for passage in r['original_context']:
            lines += ['Passage '+passage['id']+' ('+passage['source']+'):', '', '> '+passage['text'].replace('\n','\n> '),'']
        if r.get('error'):lines += ['Recorded failure: '+r['error'],'']
    return '\n'.join(lines)+'\n'


def run_benchmark(output,client):
    plan,raw=load_plan()
    inventory=client.list().model_dump(mode='json')
    if plan['model'] not in {x['model'] for x in inventory.get('models',[])}:
        raise ValueError('The frozen model tag is not installed: '+plan['model'])
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]
    folder=Path(output)/('fresh_baseline_'+stamp);folder.mkdir(parents=True)
    (folder/'frozen_plan.json').write_bytes(raw)
    snapshot={'experiment_version':experiment.VERSION,'plan_sha256':hashlib.sha256(raw).hexdigest(),
              'plan':plan,'installed_models':inventory,'model_verifier_used':False,
              'generation_prompts':{'select':base.SELECT_PROMPT,'generate':base.GENERATE_PROMPT},
              'interpretation':'Code checks establish provenance and structure, not semantic truth or claim entailment.'}
    (folder/'setup.json').write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
    rows,records=[],[]
    def checkpoint(complete):
        payload={'complete':complete,'experiment_version':experiment.VERSION,'rows':rows,'records':records,
                 'factual_correctness':'not_automatically_scored','production_delivery':False}
        temp=folder/'results.tmp';temp.write_text(json.dumps(payload,indent=2),encoding='utf-8');temp.replace(folder/'results.json')
        if rows:
            with (folder/'results.csv').open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        (folder/'report.md').write_text(report_text(records),encoding='utf-8')
    checkpoint(False)
    for case in plan['cases']:
        for variant in plan['variants']:
            print(case['id']+' / '+variant,flush=True)
            context=copy.deepcopy(case['context'])
            if variant=='reversed':context.reverse()
            elif variant=='no_context':context=[]
            result,bundle=experiment.run(case['question'],context,client,plan['model'],plan['options'],folder/'runs',
                                         {'case_id':case['id'],'variant':variant,'context_origin':'fixed_supplied_passages'})
            records.append({'case_id':case['id'],'variant':variant,'source_review_criteria':(['Prescribed abstention is rendered by code without model calls; this is not a factual reasoning result.'] if variant=='no_context' else case['source_review_criteria']),
                            'result':result,'bundle':str(bundle.relative_to(folder))})
            rows.append({'case_id':case['id'],'variant':variant,'status':result['status'],
                         'answer':result['candidate_answer'],'claims':len(result.get('structured_answer',{}).get('claims',[])),
                         'calls':sum(s['status']!='skipped_input' for s in result['stages']),
                         'seconds':round(sum(s.get('seconds',0) for s in result['stages']),2),
                         'tokens':sum(s.get('generated_tokens',0) or 0 for s in result['stages']),
                         'semantic_citation_support':'not_automatically_scored','error':result.get('error')})
            checkpoint(False)
    checkpoint(True)
    bundle=folder/'fresh_baseline_bundle.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        for path in folder.rglob('*'):
            if path.is_file() and path!=bundle and path.name!='grounded_bundle.zip':z.write(path,path.relative_to(folder))
    print('Records:',len(rows));print('Saved:',bundle.resolve())
    print('Answers and citation evidence are recorded separately; no model verdict approved them.')
    return rows,bundle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=str(ROOT/'results'))
    args=parser.parse_args()
    from ollama import Client
    run_benchmark(args.output,Client(host=os.environ.get('OLLAMA_HOST','http://localhost:11434'),timeout=180.0))

if __name__=='__main__':main()
