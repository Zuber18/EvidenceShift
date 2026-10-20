"""Local demo service contracts with actual TXT parsing and controlled model/store responses."""
import copy
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from evidence_api import local_upload as service,grounded as base
from evidence_api.ingestion import parse_document
PROFILE={'embedding_model':'sentence-transformers/all-MiniLM-L6-v2','chunk_tokens':180,'overlap_tokens':30,'splitter':'recursive-huggingface-token-v1','resolved_revision':None}


class Tensor:
    def __init__(self,raw=b'weights'):self.raw=raw
    def detach(self):return self
    def cpu(self):return self
    def contiguous(self):return self
    def numpy(self):return SimpleNamespace(dtype='float32',shape=(1,),tobytes=lambda order:self.raw)


class Encoder:
    def __init__(self,raw=b'weights'):
        self.raw=raw;self.max_seq_length=256;self._modules={}
        self.tokenizer=SimpleNamespace(backend_tokenizer=SimpleNamespace(to_str=lambda:json.dumps({'model':{'vocab':{'a':0}},'padding':None,'truncation':None})))
    def state_dict(self):return {'weight':Tensor(self.raw)}


class Store:
    def __init__(self,path):
        self.profile=copy.deepcopy(PROFILE);self.encoder=Encoder();self.docs={};self.rows=[];self.searches=[];self.deleted=[]
        self.collection=SimpleNamespace(name='controlled-store');self.client=SimpleNamespace(delete_collection=lambda name:self.deleted.append(name))
    def ingest(self,name,raw):
        doc=parse_document(name,raw);key=doc['document_id'];old=key in self.docs
        if old:return {**self.docs[key],'deduplicated':True}
        summary={'document_id':key,'source':doc['source'],'chunks':len(doc['pages']),'deduplicated':False}
        self.docs[key]=summary
        for page in doc['pages']:
            self.rows.append({'id':key+f"_p{page['page']}_c0",'document_id':key,'source':doc['source'],'page':page['page'],'chunk':0,'sha256':doc['sha256'],'text':page['text'],'distance':0.1})
        return summary
    def search(self,question,top_k,document_ids):
        self.searches.append((question,top_k,document_ids));return copy.deepcopy(self.rows[:top_k])


class Client:
    def __init__(self,mode=None):self.mode=mode;self.calls=[];self.lists=0
    def list(self):
        self.lists+=1
        return SimpleNamespace(model_dump=lambda **kw:{'models':[{'model':'qwen3:8b','digest':'controlled-model-digest'}]})
    def chat(self,**kwargs):
        self.calls.append(copy.deepcopy(kwargs));data=json.loads(kwargs['messages'][1]['content'])
        if kwargs['messages'][0]['content']==base.SELECT_PROMPT:
            value={'answerability':'supported','evidence_handles':[data['paragraphs'][-1]['handle']]}
        else:
            assert kwargs['messages'][0]['content']==base.GENERATE_PROMPT
            value={'response_type':'conflict' if self.mode=='mismatch' else 'supported','claims':[{'text':'A controlled candidate.','evidence':['E1']}]}
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(value),thinking=None),done_reason='stop',eval_count=10)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        (self.root/'evaluation').mkdir();(self.root/'evaluation/fresh_baseline_cases.json').write_bytes((ROOT/'evaluation/fresh_baseline_cases.json').read_bytes())
        self.uploads=[('alpha.txt',b'First operative policy.'),('beta.txt',b'Second operative policy.')]
    def workspace(self,uploads=None):
        workspace=service.Workspace(self.root,self.uploads if uploads is None else uploads,store_factory=Store)
        self.addCleanup(workspace.close);return workspace
    def test_model_fingerprint_changes_with_parameter_bytes(self):
        self.assertEqual(service.parameter_digest({'w':Tensor()}),service.parameter_digest({'w':Tensor()}))
        self.assertNotEqual(service.parameter_digest({'w':Tensor(b'a')}),service.parameter_digest({'w':Tensor(b'b')}))
    def test_identity_records_null_revision_without_inventing_hub_commit(self):
        identity=service.identity_for_store(Store('unused'));self.assertIsNone(identity['retrieval_profile']['resolved_revision'])
        self.assertEqual(len(identity['weights_sha256']),64);self.assertEqual(len(identity['fingerprint_sha256']),64)
    def test_lock_creates_matches_and_refuses_changed_identity(self):
        path=self.root/'lock.json';value={'fingerprint_sha256':'a'}
        self.assertEqual(service.enforce_identity_lock(path,value),'created_measured_lock')
        self.assertEqual(service.enforce_identity_lock(path,value),'matched_existing_lock')
        with self.assertRaisesRegex(ValueError,'identity differs'):service.enforce_identity_lock(path,{'fingerprint_sha256':'b'})
        self.assertEqual(json.loads(path.read_text()),value)
    def test_workspace_records_uploaded_bytes_and_scopes_search(self):
        w=self.workspace();hits=w.search('What is the policy?')
        self.assertEqual(len(hits),2);self.assertEqual(w.store.searches[0][1],5)
        self.assertEqual(set(w.store.searches[0][2]),{d['document_id'] for d in w.documents})
        self.assertTrue(all((w.folder/d['archive_path']).exists() for d in w.documents));self.assertTrue((self.root/'config/local_embedding_lock.json').exists())
    def test_duplicate_upload_is_not_a_second_document(self):
        w=self.workspace([self.uploads[0],self.uploads[0]]);self.assertEqual(len(w.documents),1)
    def test_uses_frozen_generation_and_never_approves_fact(self):
        w=self.workspace();c=Client();run=w.ask('What is the policy?',client=c)
        self.assertEqual(run['status'],'candidate_recorded');self.assertIsNone(run['result']['delivery_answer'])
        self.assertEqual([x['messages'][0]['content'] for x in c.calls],[base.SELECT_PROMPT,base.GENERATE_PROMPT])
        self.assertEqual(run['model_inventory']['models'][0]['digest'],'controlled-model-digest')
        self.assertTrue((w.folder/'runs'/run['run_id']/'report.md').exists())
    def test_empty_context_is_rendered_without_model_or_inventory_call(self):
        w=self.workspace();c=Client();r=w.ask('What is the policy?','no_context',c)
        self.assertEqual(c.calls,[]);self.assertEqual(c.lists,0);self.assertEqual(r['result']['candidate_answer'],base.ABSTENTION)
    def test_reversed_order_keeps_original_search_results(self):
        w=self.workspace();r=w.ask('What is the policy?','reversed',Client())
        self.assertEqual(r['used_context'],list(reversed(r['retrieved'])))
    def test_known_contract_failure_is_saved_without_silent_repair(self):
        w=self.workspace();r=w.ask('What is the policy?',client=Client('mismatch'))
        self.assertEqual(r['status'],'mechanical_failure');self.assertIsNone(r['result']['candidate_answer'])
        self.assertIn('Answer type differs',r['result']['error'])
    def test_export_contains_all_sources_runs_and_raw_traces(self):
        w=self.workspace();w.ask('First question?',client=Client());w.ask('Second question?',client=Client())
        with zipfile.ZipFile(w.export()) as z:
            self.assertEqual(len([n for n in z.namelist() if n.endswith('/run.json')]),2)
            self.assertEqual(len([n for n in z.namelist() if n.startswith('uploads/')]),2)
            self.assertTrue(any(n.endswith('/stages.jsonl') for n in z.namelist()))
            self.assertIn('embedding_identity.json',z.namelist());self.assertIn('runs.csv',z.namelist())
            self.assertNotIn('local_upload_smoke_bundle.zip',z.namelist())
    def test_clear_removes_temporary_index_and_preserves_reports(self):
        w=self.workspace();temporary=Path(w.temporary.name);folder=w.folder
        w.close();w.close();self.assertFalse(temporary.exists());self.assertTrue((folder/'session.json').exists())
        with self.assertRaisesRegex(ValueError,'cleared'):w.search('Question?')
    def test_oversized_upload_is_rejected_before_store_creation(self):
        with self.assertRaisesRegex(ValueError,'5 MiB'):self.workspace([('big.txt',b'x'*(service.MAX_FILE+1))])
    def test_local_mode_rejects_remote_ollama_host(self):
        # Check the URL boundary without needing the optional Ollama dependency in unit tests.
        from unittest.mock import patch
        import types
        fake=types.ModuleType('ollama');fake.Client=lambda **kw:None
        with patch.dict(sys.modules,{'ollama':fake}),patch.dict('os.environ',{'OLLAMA_HOST':'https://remote.invalid'}):
            with self.assertRaisesRegex(ValueError,'loopback'):service.ollama_client()

if __name__=='__main__':unittest.main()
