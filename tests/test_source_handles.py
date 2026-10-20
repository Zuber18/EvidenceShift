"""ID selection contracts, using the actual saved 19-chunk story context."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from evidence_api import source_handles as engine

ROOT=Path(__file__).resolve().parents[1]
CONTEXT=json.loads((ROOT/'evaluation/handle_replay_evidence.json').read_text())['context']


def answer(ids, kind='supported'):
    return {'response_type':kind,'unit_ids':ids,'unanswered_parts':[]}


class Client:
    def __init__(self, value=None): self.value=value; self.calls=[]
    def list(self):
        return SimpleNamespace(model_dump=lambda **kwargs:{'models':[{'model':'qwen3:8b','digest':'controlled'}]})
    def chat(self,**kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        value=self.value
        if value is None:
            value=answer([json.loads(kwargs['messages'][1]['content'])['sources'][0]['units'][0]['id']])
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(value)),done_reason='stop',
                               eval_count=20,prompt_eval_count=4000)


class Tests(unittest.TestCase):
    def setUp(self): self.units=engine.evidence_units(CONTEXT)

    def test_ids_and_mappings_stable_under_reversal(self):
        other=engine.evidence_units(list(reversed(CONTEXT)))
        self.assertEqual({u['handle']:u for u in self.units},{u['handle']:u for u in other})
        self.assertNotEqual([u['handle'] for u in self.units],[u['handle'] for u in other])

    def test_every_character_of_source_retained_except_boundary_whitespace(self):
        for passage in CONTEXT:
            spans=[u for u in self.units if u['passage_id']==passage['id']]
            restored=''.join(u['text'] for u in spans)
            self.assertEqual(''.join(restored.split()),''.join(passage['text'].split()))

    def test_combs_and_sale_units_exist_without_model_writing(self):
        self.assertTrue(any('Beautiful combs, with jewels' in u['text'] for u in self.units))
        self.assertTrue(any('I sold the watch to get the money' in u['text'] for u in self.units))

    def test_pdf_opening_not_corrected_or_rewritten(self):
        self.assertTrue(any('O\nNE DOLLAR' in u['text'] for u in self.units))

    def test_abbreviations_not_split_from_names(self):
        text='Mrs. James Young called him Jim. He smiled.'
        self.assertEqual([text[a:b] for a,b in engine.sentence_spans(text)],
                         ['Mrs. James Young called him Jim.','He smiled.'])

    def test_unknown_ids_rejected(self):
        with self.assertRaises(ValueError):
            engine.validate_selection(answer(['U999999']),CONTEXT,self.units)

    def test_duplicate_ids_rejected(self):
        handle=self.units[0]['handle']
        with self.assertRaises(ValueError):
            engine.validate_selection(answer([handle,handle]),CONTEXT,self.units)

    def test_fabricated_quote_field_not_allowed(self):
        value=answer([self.units[0]['handle']]); value['quote']='Jim bought a gold watch.'
        with self.assertRaises(ValueError):
            engine.validate_selection(value,CONTEXT,self.units)

    def test_insufficient_with_ids_still_rejected(self):
        with self.assertRaises(ValueError):
            engine.validate_selection(answer([self.units[0]['handle']],'insufficient'),CONTEXT,self.units)

    def test_supported_empty_still_rejected(self):
        with self.assertRaises(ValueError):
            engine.validate_selection(answer([]),CONTEXT,self.units)

    def test_code_selects_original_span_and_passage(self):
        unit=next(u for u in self.units if 'I sold the watch to get the money' in u['text'])
        record=engine.validate_selection(answer([unit['handle']]),CONTEXT,self.units)[0]
        passage=next(p for p in CONTEXT if p['id']==unit['passage_id'])
        self.assertEqual(record['claim_text'],passage['text'][record['span_start']:record['span_end']])

    def run_engine(self,context,client):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        return engine.run('What did Jim buy?',context,client,'qwen3:8b',
            {'temperature':0,'seed':42,'num_ctx':8192,'num_predict':4096},temp.name)[0]

    def test_no_context_zero_calls(self):
        client=Client(); result=self.run_engine([],client)
        self.assertEqual(result['status'],'empty_context_control');self.assertEqual(client.calls,[])

    def test_full_live_context_fits_existing_budget(self):
        client=Client();result=self.run_engine(CONTEXT,client)
        self.assertEqual(result['status'],'candidate_recorded')
        self.assertEqual(len(client.calls),1)
        stage=result['stages'][0]
        self.assertLessEqual(stage['num_ctx'],32768)
        self.assertEqual(stage['options']['num_predict'],2048)
        self.assertFalse(result['mechanical_checks']['semantic_relevance_verified'])

    def test_failed_response_saved_without_retry(self):
        client=Client(answer(['invented']));result=self.run_engine(CONTEXT,client)
        self.assertEqual(result['status'],'mechanical_failure')
        self.assertIsNone(result['candidate_answer']);self.assertEqual(len(client.calls),1)
        self.assertIn('invented',result['stages'][0]['raw_output'])

    def test_irrelevant_unit_remains_semantically_unverified(self):
        # Selection is allowed to be wrong; do not conflate membership with relevance.
        unit=next(u for u in self.units if 'electric bell' in u['text'])
        result=self.run_engine(CONTEXT,Client(answer([unit['handle']])))
        self.assertEqual(result['status'],'candidate_recorded')
        self.assertFalse(result['mechanical_checks']['answer_completeness_verified'])

    def test_edited_catalog_cannot_forge_source(self):
        units=copy.deepcopy(self.units);units[0]['text']='Invented quotation.'
        with self.assertRaisesRegex(ValueError,'catalog differs'):
            engine.validate_selection(answer([units[0]['handle']]),CONTEXT,units)


if __name__=='__main__': unittest.main()
