/** Verify that the browser keeps experiment denominators and controls separate. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pairFor, filteredRecords, citationIds, confirmationBuckets, assessmentDistribution, toCsv, safeState, modelComparisons} from '../website/core.mjs';
const data=JSON.parse(readFileSync(new URL('../website/data/experiments.json',import.meta.url),'utf8'));
const confirmation=data.experiments.find(e=>e.id==='direct_confirmation');

test('recorded denominators and zero-call controls remain distinct',()=>{
  assert.deepEqual(data.experiments.map(e=>[e.records.length,e.calls,e.controls]),[[17,16,1],[33,30,3],[66,60,6]]);
  assert.equal(data.experiments.reduce((n,e)=>n+e.pairs,0),53);
  assert.equal(Object.keys(data.passages).length,27);
});
test('all saved comparisons retain the same sources in exact reversed order',()=>{
  for(const e of data.experiments)for(const m of e.models)for(const representation of e.representations)for(const c of e.cases){
    const pair=pairFor(e,m,representation,c.id);
    assert.deepEqual(pair.retrieved.context_ids,[...pair.reversed.context_ids].reverse());
    assert.equal(pair.retrieved.question,pair.reversed.question);
  }
});
test('confirmation outcome buckets reproduce owner-assessed counts',()=>{
  assert.deepEqual(confirmationBuckets(confirmation.records).map(r=>r.count),[9,2,4,1]);
});
test('the arithmetic showcase uses the actual differing answers',()=>{
  const pair=pairFor(confirmation,'qwen3:8b','direct','confirm_6');
  assert.match(pair.retrieved.answer,/12/);
  assert.match(pair.reversed.answer,/8/);
  assert.equal(pair.retrieved.assessment,'supported_answer');
  assert.equal(pair.reversed.assessment,'material_arithmetic_error');
});
test('controls are excluded by default and never join an order pair',()=>{
  assert.equal(filteredRecords(confirmation,'qwen3:8b','direct').length,16);
  assert.equal(filteredRecords(confirmation,'qwen3:8b','direct','all',true).length,17);
  assert.deepEqual(Object.keys(pairFor(confirmation,'qwen3:8b','direct','confirm_1')).sort(),['retrieved','reversed']);
});
test('outcome filters return exact recorded categories',()=>{
  assert.equal(filteredRecords(confirmation,'qwen3:8b','direct','correct_core_with_false_abstention').length,4);
  assert.equal(filteredRecords(confirmation,'qwen3:8b','direct','material_arithmetic_error').length,1);
});
test('citation navigation accepts known grouped IDs without rewriting stored checks',()=>{
  assert.deepEqual([...citationIds('A [id1, id2] and [unknown].',['id1','id2'])],['id1','id2']);
  const e=data.experiments.find(e=>e.id==='direct_answer');
  assert.equal(e.records.filter(r=>r.group_parser_limitation).length,6);
  assert.ok(e.records.filter(r=>r.group_parser_limitation).every(r=>r.checks.citation_ids_valid===false));
});
test('distribution totals never drop categories or include controls',()=>{
  for(const e of data.experiments)assert.equal(assessmentDistribution(e).reduce((n,r)=>n+r.count,0),e.calls);
});
test('query parameters fall back to known model, case and representation values',()=>{
  const state=safeState(data,new URLSearchParams('experiment=unknown&model=<script>&case=bad&representation=bad&order=bad'));
  assert.deepEqual(state,{experiment:'direct_answer',model:'all',sourceModel:'qwen3:8b',representation:'direct',caseId:'1f939d31',order:'retrieved'});
});
test('share-link state recovers a specific recorded comparison',()=>{
  const state=safeState(data,new URLSearchParams('experiment=model_matrix&model=gemma3:4b&case=ae8d2dc4&representation=sentence_units&order=reversed'));
  assert.equal(state.model,'gemma3:4b');assert.equal(state.representation,'sentence_units');assert.equal(state.order,'reversed');
});
test('CSV quotes multiline text, preserves rows and neutralizes formula cells',()=>{
  const csv=toCsv([{id:'id',question:'=1+1',answer:'Line 1\n"Line 2"',model:'x',notes:'a,b'}]);
  assert.match(csv,/"'=1\+1"/);assert.match(csv,/"Line 1\n""Line 2"""/);assert.match(csv,/"a,b"/);
});
test('every displayed record has a source hash and a current owner assessment',()=>{
  for(const e of data.experiments){assert.equal(e.reviewer,'Zuber Shaikh');for(const r of e.records){
    assert.match(r.raw_sha256,/^[a-f0-9]{64}$/);assert.ok(r.notes);assert.equal(r.model_calls,r.order==='no_context'?0:1);
  }}
});

test('the default opens the three-model baseline and comparisons retain every model',()=>{
  const state=safeState(data,new URLSearchParams());assert.equal(state.experiment,'direct_answer');
  const exp=data.experiments.find(e=>e.id===state.experiment);
  const comparisons=modelComparisons(exp,state.representation,state.caseId);
  assert.deepEqual(comparisons.map(c=>c.model),['qwen3:4b','qwen3:8b','gemma3:4b']);
  assert.equal(comparisons.flatMap(c=>Object.values(c.pair)).length,6);
  assert.equal(filteredRecords(exp,'all','direct').length,30);
  assert.equal(filteredRecords(exp,'all','direct','all',true).length,33);
});
test('confirmation remains explicitly limited to its actual tested model',()=>{
  assert.deepEqual(modelComparisons(confirmation,'direct','confirm_1').map(c=>c.model),['qwen3:8b']);
});

test('each model selection changes the displayed answer pairs and record scope',()=>{
  const exp=data.experiments.find(e=>e.id==='direct_answer');
  for(const model of exp.models){
    const state=safeState(data,new URLSearchParams({experiment:exp.id,model,case:exp.cases[0].id}));
    assert.equal(state.model,model);assert.equal(state.sourceModel,model);
    const groups=modelComparisons(exp,state.representation,state.caseId,state.model);
    assert.deepEqual(groups.map(g=>g.model),[model]);
    assert.equal(Object.values(groups[0].pair).length,2);
    assert.equal(filteredRecords(exp,model,'direct').length,10);
  }
});
test('All models restores three pairs while shared citation state retains its source model',()=>{
  const state=safeState(data,new URLSearchParams('experiment=direct_answer&model=all&source_model=gemma3:4b'));
  assert.equal(state.model,'all');assert.equal(state.sourceModel,'gemma3:4b');
  const exp=data.experiments.find(e=>e.id===state.experiment);
  assert.equal(modelComparisons(exp,state.representation,state.caseId,state.model).length,3);
  assert.equal(safeState(data,new URLSearchParams('experiment=direct_confirmation&model=all')).model,'qwen3:8b');
});
