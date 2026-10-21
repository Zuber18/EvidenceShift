/** Pure data helpers shared by the browser and dependency-free Node tests. */
export const LABELS = {
  code_control: 'Code abstention control', supported_answer: 'Supported answer',
  justified_exact_abstention: 'Justified abstention', justified_nonexact_abstention: 'Justified abstention (nonexact)',
  justified_abstention: 'Justified abstention', correct_core_with_false_abstention: 'Correct core + false abstention',
  material_arithmetic_error: 'Arithmetic error', supported_with_scope_caveat: 'Supported · scope caveat',
  supported_with_citation_placement_caveat: 'Supported · citation placement',
  material_error_and_mixed_abstention: 'Wrong fact + mixed abstention', material_role_reversal_no_citations: 'Role reversal · no citations',
  material_role_reversal: 'Role reversal', self_contradiction: 'Self-contradiction',
  self_contradiction_and_citation_defect: 'Contradiction + citation defect',
  correct_core_with_unsupported_citations_and_mixed_abstention: 'Correct core · citation / abstention defects',
  abstention_with_irrelevant_and_unsupported_extra: 'Abstention + unsupported extra', output_limit_failure: 'Output limit failure',
  analysis_in_answer_field: 'Analysis in answer field', unjustified_exact_abstention: 'Unjustified abstention',
  unjustified_abstention: 'Unjustified abstention', core_evidence_with_conflicting_note: 'Core evidence · conflicting note',
  wrong_actor_direction: 'Wrong actor direction', core_evidence_with_irrelevant_note: 'Core evidence · irrelevant note',
  wrong_temporal_evidence: 'Wrong time point', incomplete_causal_evidence: 'Incomplete causal evidence',
  irrelevant_instead_of_abstention: 'Irrelevant text instead of abstention', irrelevant_evidence: 'Irrelevant evidence',
  core_useful_evidence: 'Relevant core evidence', core_evidence_with_confusing_extra: 'Core evidence · confusing extra',
  core_evidence_with_extra: 'Core evidence + extra text', substantial_but_incomplete_explanation: 'Substantial but incomplete',
  core_evidence_with_fragments: 'Core evidence · fragments', core_evidence_with_mixed_time_points: 'Core evidence · mixed times',
};
export function label(value) { return LABELS[value] || value.replaceAll('_', ' '); }
export function modelLabel(value) { return ({ 'qwen3:4b':'Qwen 3 · 4B', 'qwen3:8b':'Qwen 3 · 8B', 'gemma3:4b':'Gemma 3 · 4B' })[value] || value; }
export function tone(value) {
  if (value === 'code_control') return 'control';
  if (['supported_answer','justified_exact_abstention','justified_nonexact_abstention','justified_abstention'].includes(value)) return 'clean';
  if (['supported_with_scope_caveat','supported_with_citation_placement_caveat'].includes(value)) return 'caveat';
  if (value.startsWith('core_')) return 'neutral';
  return 'issue';
}
export function pairFor(experiment, model, representation, caseId) {
  return Object.fromEntries(experiment.records.filter(r => r.model === model && r.representation === representation && r.case_id === caseId && r.order !== 'no_context').map(r => [r.order, r]));
}
export function filteredRecords(experiment, model, representation, outcome='all', controls=false) {
  return experiment.records.filter(r => (model === 'all' || r.model === model) && r.representation === representation && (controls || r.order !== 'no_context') && (outcome === 'all' || r.assessment === outcome));
}
export function citationIds(answer, contextIds) {
  const known = new Set(contextIds), ids = new Set();
  for (const bracket of (answer || '').matchAll(/\[([^\]]+)\]/g)) {
    for (const token of bracket[1].split(/[,\s]+/)) if (known.has(token)) ids.add(token);
  }
  return ids;
}
export function confirmationBuckets(records) {
  const calls = records.filter(r => r.order !== 'no_context');
  const count = names => calls.filter(r => names.includes(r.assessment)).length;
  return [
    {name:'Clean answers / justified abstentions', count:count(['supported_answer','justified_exact_abstention']), tone:'clean'},
    {name:'Supported with minor caveats', count:count(['supported_with_scope_caveat','supported_with_citation_placement_caveat']), tone:'caveat'},
    {name:'Correct core + false abstention', count:count(['correct_core_with_false_abstention']), tone:'issue'},
    {name:'Material arithmetic error', count:count(['material_arithmetic_error']), tone:'issue'},
  ];
}
export function assessmentDistribution(experiment) {
  if (experiment.id === 'direct_confirmation') return confirmationBuckets(experiment.records);
  const items = Object.entries(experiment.assessment_counts).sort((a,b) => b[1]-a[1]).map(([key,count])=>({name:label(key),count,tone:tone(key)}));
  const visible=items.slice(0,5), remainder=items.slice(5).reduce((sum,item)=>sum+item.count,0);
  if (remainder) visible.push({name:'Other recorded assessments', count:remainder, tone:'neutral'});
  return visible;
}
export function toCsv(records) {
  const columns=['job_id','question','model','representation','order','status','assessment','notes','answer','raw_path'];
  // Prefix formula-like cells for spreadsheet safety; JSON retains exact values.
  const cell = value => { let s=String(value ?? ''); if (/^[=+@-]/.test(s)) s="'"+s; return '"'+s.replaceAll('"','""')+'"'; };
  const rows=records.map(r=>[r.id,r.question,r.model,r.representation,r.order,r.status,r.assessment,r.notes,r.answer,r.raw_path]);
  return [columns,...rows].map(row=>row.map(cell).join(',')).join('\r\n')+'\r\n';
}
export function safeState(data, params) {
  const experiment=data.experiments.find(e=>e.id===params.get('experiment')) || data.experiments.find(e=>e.id==='direct_answer') || data.experiments[0];
  const model=experiment.models.includes(params.get('model')) ? params.get('model') : experiment.models.includes('qwen3:8b') ? 'qwen3:8b' : experiment.models[0];
  const representation=experiment.representations.includes(params.get('representation')) ? params.get('representation') : experiment.representations[0];
  const caseId=experiment.cases.some(c=>c.id===params.get('case')) ? params.get('case') : experiment.cases[0].id;
  return {experiment:experiment.id,model,representation,caseId,order:params.get('order')==='reversed'?'reversed':'retrieved'};
}

/** Preserve a separate original/reversed pair for every tested model. */
export function modelComparisons(experiment, representation, caseId) {
  const order=['qwen3:4b','qwen3:8b','gemma3:4b'];
  return order.filter(model=>experiment.models.includes(model)).map(model=>({model,pair:pairFor(experiment,model,representation,caseId)}));
}
