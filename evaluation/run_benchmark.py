"""Run a fixed evidence benchmark locally; no prompt tuning, paid API, or retries."""
import argparse
import copy
import csv
import hashlib
import json
import sys
import zipfile
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from evidence_api import grounded


def variant_names(case):
    return ['retrieved','reversed','no_context'] if len(case['context'])>1 else ['retrieved','no_context']


def run_benchmark(models,output,client,plan=None):
    plan=plan or json.loads((ROOT/'evaluation/cases.json').read_text())
    if grounded.VERSION!=plan['pipeline_version']:raise ValueError('Pipeline version differs from frozen plan. Do not tune mid-benchmark.')
    inventory=client.list().model_dump(mode='json')
    installed={x['model'] for x in inventory.get('models',[])}
    missing=set(models)-installed
    if missing:raise ValueError('Install these model tags in Ollama first: '+', '.join(sorted(missing)))
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8]
    folder=Path(output)/('benchmark_'+stamp);folder.mkdir(parents=True)
    snapshot={'plan':plan,'requested_models':models,'installed_models':inventory,
              'note':'Existing development cases, not held-out evaluation. Criteria are labels only; no automatic factual approval.'}
    (folder/'setup.json').write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
    rows=[];records=[]
    for model in models:
        for case in plan['cases']:
            for variant in variant_names(case):
                print(f"{model} / {case['id']} / {variant}",flush=True)
                source_id='input_'+hashlib.sha256(f"{stamp}:{model}:{case['id']}:{variant}".encode()).hexdigest()[:12]
                source=folder/'inputs'/source_id;source.mkdir(parents=True)
                context=copy.deepcopy(case['context'])
                if variant=='reversed':context.reverse()
                elif variant=='no_context':context=[]
                setup={'run_id':source_id,'request':{'question':case['question'],'expected_answer':None,'gold_evidence_ids':[]},
                       'model':model,'options':plan['options'],'think':plan['think'],
                       'profile':{'evidence':case['retrieval_profile'],'original_source_run_id':case.get('source_run_id')},
                       'input_only':True,'review_criteria':case['review_criteria']}
                record={'prompt_name':'benchmark_input','variant':variant,'context':context,
                        'user_prompt':json.dumps({'question':case['question'],'evidence':context}), 'input_only':True}
                (source/'setup.json').write_text(json.dumps(setup,indent=2),encoding='utf-8')
                (source/'result.json').write_text(json.dumps({'run_id':source_id,'records':[record]}),encoding='utf-8')
                try:
                    result,bundle=grounded.run(source,folder/'runs',client,prompt='benchmark_input',variant=variant,thinking_mode='off')
                    rec={'model':model,'case_id':case['id'],'variant':variant,'review_criteria':case['review_criteria'],
                         'factual_review':{'status':'pending','reviewer':None,'user_verified':False},'result':result,'bundle':str(bundle.relative_to(folder))}
                    row={'model':model,'case_id':case['id'],'variant':variant,'status':result['status'],
                         'calls':len([s for s in result['stages'] if s['status']!='skipped_input']),
                         'seconds':round(sum(s.get('seconds',0) for s in result['stages']),2),
                         'tokens':sum(s.get('generated_tokens') or 0 for s in result['stages']),
                         'factual_review':'pending','answer':result.get('candidate_answer'),
                         'error':result.get('error'),'bundle':str(bundle.relative_to(folder))}
                except Exception as exc:
                    rec={'model':model,'case_id':case['id'],'variant':variant,'error':f'{type(exc).__name__}: {exc}'}
                    row={'model':model,'case_id':case['id'],'variant':variant,'status':'run_error','calls':None,'seconds':None,
                         'tokens':None,'factual_review':'pending','answer':None,'error':rec['error'],'bundle':None}
                rows.append(row);records.append(rec)
                (folder/'results.json').write_text(json.dumps({'complete':False,'rows':rows,'records':records},indent=2,ensure_ascii=False),encoding='utf-8')
                with (folder/'results.csv').open('w',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (folder/'results.json').write_text(json.dumps({'complete':True,'rows':rows,'records':records},indent=2,ensure_ascii=False),encoding='utf-8')
    bundle=folder/'benchmark_bundle.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob('*'):
            if p.is_file() and p!=bundle and p.name!='grounded_bundle.zip':z.write(p,p.relative_to(folder))
    return rows,bundle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models',nargs='+',default=['qwen3:4b','qwen3:8b','gemma3:4b'])
    parser.add_argument('--output',default=str(ROOT/'results'))
    args=parser.parse_args()
    from ollama import Client
    import os
    rows,bundle=run_benchmark(args.models,args.output,Client(host=os.environ.get('OLLAMA_HOST','http://localhost:11434'),timeout=180.0))
    print('Pipeline inputs:',len(rows));print('Generation calls:',sum(x['calls'] or 0 for x in rows))
    print('Saved:',bundle.resolve());print('Factual reviews are pending; no automatic accuracy score.')

if __name__=='__main__':main()
