"""Preserved baseline selection/generation with mechanical checks and no model gate.

Candidates are recorded for source-based assessment. No result is a factual
approval or production response; retrieval and deployed routes are unchanged.
"""
import copy
import json
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from . import grounded as base

VERSION='fresh-candidates-1.0.0'


def run(question, context, client, model, options, output, metadata=None):
    if not isinstance(question,str) or not question.strip():
        raise ValueError('Question must be nonempty')
    if len({c['id'] for c in context}) != len(context):
        raise ValueError('Duplicate context passage IDs')
    folder=Path(output)/('candidate_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid4().hex[:8])
    folder.mkdir(parents=True)
    source={'question':question,'context':copy.deepcopy(context),'metadata':metadata or {}}
    (folder/'source_result.json').write_text(json.dumps(source,indent=2),encoding='utf-8')
    (folder/'source_setup.json').write_text(json.dumps({'model':model,'options':options,'think':False}),encoding='utf-8')
    config={'experiment_version':VERSION,'baseline_generation_version':base.VERSION,'model':model,
            'options':options,'think':False,'model_verifier_used':False,
            'prompts':{'select':base.SELECT_PROMPT,'generate':base.GENERATE_PROMPT},
            'schemas':{'select':base.selection_schema(context) if context else None,'generate':base.ANSWER_SCHEMA},
            'scope':'Preserved baseline generation prompts/schemas; verifier omitted. Candidate recording only.'}
    (folder/'setup.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    result={'experiment_version':VERSION,'run_id':folder.name,'question':question,'original_context':copy.deepcopy(context),
            'metadata':metadata or {},'stages':[],'status':'in_progress','complete':False,
            'candidate_answer':None,'delivery_answer':None,'factual_correctness':'not_automatically_scored',
            'mechanical_checks':{},'model_verifier_used':False}
    base.save(folder,result)
    try:
        if not context:
            result.update(candidate_answer=base.ABSTENTION,status='empty_context_control',
                          structured_answer={'response_type':'insufficient','claims':[]},
                          validated_evidence=[],selection=None,
                          mechanical_checks={'deterministic_abstention':True,'generated_claims':0})
        else:
            selection_input=json.dumps({'question':question,'paragraphs':[
                {'handle':p['selection_handle'],'text':p['quote']} for p in base.evidence_catalog(context)]},ensure_ascii=False)
            selection=base.stage(client,model,options,False,base.SELECT_PROMPT,selection_input,
                                 base.selection_schema(context),'select',folder,result)
            evidence=base.validate_quotes(selection,context)
            result.update(selection=selection,validated_evidence=evidence)
            if selection['answerability']=='insufficient':
                answer={'response_type':'insufficient','claims':[]}
            else:
                payload={'question':question,'answerability':selection['answerability'],'evidence':evidence}
                answer=base.stage(client,model,options,False,base.GENERATE_PROMPT,json.dumps(payload,ensure_ascii=False),
                                  base.ANSWER_SCHEMA,'generate',folder,result)
            result['structured_answer']=answer
            candidate=base.validate_claims(answer,selection,evidence)
            known={e['handle']:e for e in evidence}
            support_records=[]
            for i,claim in enumerate(answer['claims']):
                ids=list(dict.fromkeys(p for h in claim['evidence'] for p in known[h]['passage_ids']))
                support_records.append({'claim_index':i,'claim_text':claim['text'],'evidence_handles':claim['evidence'],
                     'passage_ids':ids,'selected_quotations':[known[h]['quote'] for h in claim['evidence']],
                     'original_cited_passages':[c for c in context if c['id'] in ids],
                     'semantic_citation_support':'not_automatically_scored'})
            result.update(candidate_answer=candidate,status='candidate_recorded',claim_source_records=support_records,
                          mechanical_checks={'selection_schema_valid':True,'selected_handles_valid':True,
                             'selected_quotes_copied_from_source':True,'answer_schema_valid':True,
                             'claim_evidence_handles_valid':True,'rendered_citation_ids_valid':True,
                             'generated_claims':len(answer['claims'])})
    except Exception as exc:
        result.update(status='mechanical_failure',error=f'{type(exc).__name__}: {exc}',candidate_answer=None)
    result['complete']=True
    base.save(folder,result)
    return result,folder/'grounded_bundle.zip'
