"""Revised local workspace. Baseline service and results remain unchanged."""
import copy
import hashlib
import json
from pathlib import Path
from .local_upload import Workspace as BaselineWorkspace, LOCK, stamp, ollama_client
from . import source_handles as generator

VERSION = 'local-upload-2.1.0'
SMALL_CORPUS_CHUNKS = 48
SMALL_CORPUS_BYTES = 20000


class Workspace(BaselineWorkspace):
    """Use shared semantic retrieval with expanded context and source-unit selection."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.all_passages = []
            with LOCK:
                for document in self.documents:
                    rows = []
                    for offset in range(0, document['chunks'], 100):
                        rows.extend(self.store.chunks(document['document_id'], limit=100, offset=offset))
                    if len(rows) != document['chunks'] or len({p['id'] for p in rows}) != len(rows):
                        raise ValueError('Incomplete or duplicated corpus passage listing')
                    rows.sort(key=lambda p: (p['page'], p['chunk'], p['id']))
                    self.all_passages.extend(rows)
            self.last_retrieval = {}
            self.manifest.update(service_version=VERSION, generation_version=generator.VERSION,
                retrieval_policy='full-small-corpus-or-top10-with-neighbors-v2',
                answer_mode='code_copied_evidence_units',
                note='Copied excerpts only; relevance and completeness are not automatically certified.')
            for name in ('source_handles.py', 'local_upload_v21.py'):
                self.manifest['source_module_sha256'][name] = hashlib.sha256(
                    Path(__file__).with_name(name).read_bytes()).hexdigest()
            (self.folder/'session.json').write_text(json.dumps(self.manifest, indent=2), encoding='utf-8')
        except Exception:
            self.close()
            raise

    def search(self, question):
        """Return complete small-corpus coverage or semantic hits with neighbors.

        Expansion stays within document boundaries. Save the coverage plan and
        omitted passage IDs so missing context remains inspectable.
        """
        if self.closed:
            raise ValueError('The workspace has been cleared.')
        if not question.strip() or len(question) > 1200:
            raise ValueError('Enter a question of 1–1200 characters.')
        size = sum(len(p['text'].encode()) for p in self.all_passages)
        small = len(self.all_passages) <= SMALL_CORPUS_CHUNKS and size <= SMALL_CORPUS_BYTES
        count = len(self.all_passages) if small else 10
        with LOCK:
            hits = self.store.search(question, count, [d['document_id'] for d in self.documents])
        by_id = {p['id']: p for p in self.all_passages}
        if any(p['id'] not in by_id for p in hits):
            raise ValueError('Search returned a passage outside this upload workspace')
        if small:
            if {p['id'] for p in hits} != set(by_id):
                raise ValueError('Full-corpus retrieval omitted passages')
            expanded = hits
        else:
            expanded = []; seen = set()
            positions = {p['id']: i for i, p in enumerate(self.all_passages)}
            for hit in hits:
                index = positions[hit['id']]
                for position in (index, index-1, index+1):
                    if not 0 <= position < len(self.all_passages):
                        continue
                    passage = self.all_passages[position]
                    if passage['document_id'] != hit['document_id'] or passage['id'] in seen:
                        continue
                    seen.add(passage['id'])
                    expanded.append({**passage, 'retrieval_role': 'semantic_hit' if position == index else 'neighbor'})
        self.last_retrieval = {'policy': self.manifest['retrieval_policy'],
            'corpus_chunks': len(self.all_passages), 'corpus_text_bytes': size,
            'complete_corpus_coverage': small, 'semantic_hits': hits,
            'context_ids': [p['id'] for p in expanded],
            'omitted_corpus_ids': [p['id'] for p in self.all_passages if p['id'] not in {h['id'] for h in expanded}]}
        return copy.deepcopy(expanded)

    def ask(self,question,variant='retrieved',client=None):
        """Persist one source-unit selection attempt under the requested order.

        Reverse the same passage set or use an empty-context code control. Save
        errors and raw traces without retrying or certifying factual support.
        """
        if variant not in {'retrieved','reversed','no_context'}:raise ValueError('Unknown evidence-order variant.')
        folder=self.folder/'runs'/stamp('run_');folder.mkdir(parents=True)
        run={'run_id':folder.name,'service_version':VERSION,'question':question,'variant':variant,
             'factual_correctness':'not_automatically_scored','production_delivery':False,
             'embedding_identity':self.identity,'documents':self.documents,'complete':False}
        try:
            hits=self.search(question);used=list(reversed(hits)) if variant=='reversed' else [] if variant=='no_context' else hits
            run.update(retrieved=hits,used_context=used,omitted_for_budget=[], retrieval_plan=copy.deepcopy(self.last_retrieval))
            # Oversized evidence is recorded as a failure; no source text is silently trimmed.
            if used:
                client=client or ollama_client()
                inventory=client.list().model_dump(mode='json');run['model_inventory']=inventory
                if self.plan['model'] not in {m['model'] for m in inventory.get('models',[])}:
                    raise ValueError('The frozen model is not installed in Ollama: '+self.plan['model'])
            else:run['model_inventory']={'check':'skipped for empty-context code control'}
            result,bundle=generator.run(question,used,client,self.plan['model'],self.plan['options'],folder/'trace',
                      {'source':'local_upload_ui','variant':variant,'session_id':self.folder.name})
            run['result']=result;run['status']=result['status']
        except Exception as exc:run.update(status='run_failed',error=f'{type(exc).__name__}: {exc}')
        run['complete']=True
        (folder/'run.json').write_text(json.dumps(run,indent=2),encoding='utf-8')
        candidate=run.get('result',{}).get('candidate_answer')
        lines=['# Local document run','','Question: '+question,'','Variant: '+variant,'','Status: '+run['status'],'',
               'Generated candidate (not factually certified):','','> '+(candidate or '(No mechanically valid candidate)').replace('\n','\n> '),'']
        for passage in run.get('used_context',[]):
            lines+=['Source '+passage['source']+'; page '+str(passage['page'])+'; '+passage['id'],'','> '+passage['text'].replace('\n','\n> '),'']
        if run.get('error') or run.get('result',{}).get('error'):lines+=['Error: '+str(run.get('error') or run['result']['error'])]
        (folder/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        self.runs.append({'run_id':folder.name,'question':question,'variant':variant,'status':run['status'],
                          'answer':candidate,'run_path':str((folder/'run.json').relative_to(self.folder)),
                          'factual_correctness':'not_automatically_scored'})
        self.save_summary()
        return run
