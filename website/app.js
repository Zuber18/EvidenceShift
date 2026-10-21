import {label, modelLabel, tone, pairFor, filteredRecords, citationIds, assessmentDistribution, toCsv, safeState, modelComparisons} from './core.mjs';

const $ = id => document.getElementById(id);
const state = {data:null, experiment:'direct_answer',model:'all',sourceModel:'qwen3:8b',representation:'direct',caseId:'1f939d31',order:'retrieved',outcome:'all',controls:false,citedOnly:false,highlight:null};
let toastTimer;

/** All saved source/model content is inserted as text, never trusted HTML. */
function node(tag, className, text) {
  const element=document.createElement(tag);
  if (className) element.className=className;
  if (text!==undefined) element.textContent=text;
  return element;
}
function experiment() { return state.data.experiments.find(e=>e.id===state.experiment); }
function pair() { return pairFor(experiment(),state.model==='all'?state.sourceModel:state.model,state.representation,state.caseId); }
function sourceUrl(path) { return `${state.data.repository}/blob/${state.data.source_commit || 'main'}/${path}`; }
function tag(assessment) { return node('span',`assessment-tag ${tone(assessment)}`,label(assessment)); }
function notify(message) { clearTimeout(toastTimer); $('toast').textContent=message; $('toast').hidden=false; toastTimer=setTimeout(()=>$('toast').hidden=true,3500); }

function syncUrl() {
  const url=new URL(location.href);
  for (const [key,value] of Object.entries({experiment:state.experiment,model:state.model,representation:state.representation,case:state.caseId,order:state.order,source_model:state.model==='all'?state.sourceModel:state.model})) url.searchParams.set(key,value);
  history.replaceState(null,'',url);
}
function fillSelect(element, items, selected) {
  element.replaceChildren(...items.map(([value,text])=>{const option=node('option','',text);option.value=value;return option;}));
  element.value=selected;
}
function renderFilters() {
  const exp=experiment();
  $('experiment-tabs').replaceChildren(...[...state.data.experiments].sort((a,b)=>['direct_answer','model_matrix','direct_confirmation'].indexOf(a.id)-['direct_answer','model_matrix','direct_confirmation'].indexOf(b.id)).map((item,index)=>{
    const button=node('button','experiment-tab');button.type='button';button.setAttribute('aria-pressed',String(item.id===state.experiment));
    button.append(node('span','tab-number',String(index+1).padStart(2,'0')),node('span','',item.title));
    button.addEventListener('click',()=>{
      const params=new URLSearchParams({experiment:item.id,model:state.model});
      Object.assign(state,safeState(state.data,params),{outcome:'all',highlight:null,citedOnly:false,controls:false});
      $('include-controls').checked=false;$('cited-only').checked=false;renderAll();
    });return button;
  }));
  $('experiment-description').textContent=exp.description;
  $('experiment-review').href=sourceUrl(exp.records[0].review_path);
  fillSelect($('case-select'),exp.cases.map(c=>[c.id,c.question]),state.caseId);
  fillSelect($('model-select'),[...(exp.models.length>1?[['all','All models']]:[]),...exp.models.map(m=>[m,modelLabel(m)])],state.model);
  fillSelect($('representation-select'),exp.representations.map(r=>[r,r==='sentence_units'?'Text units':r==='passages'?'Whole passages':'Direct answer']),state.representation);
  const multiple=exp.representations.length>1;
  $('representation-field').hidden=!multiple;
  document.querySelector('.filter-grid').classList.toggle('has-representation',multiple);
  const outcomes=[...new Set(exp.records.filter(r=>(state.model==='all'||r.model===state.model) && r.representation===state.representation && (state.controls||r.order!=='no_context')).map(r=>r.assessment))].sort();
  if (!outcomes.includes(state.outcome)) state.outcome='all';
  fillSelect($('outcome-filter'),[['all','All assessments'],...outcomes.map(v=>[v,label(v)])],state.outcome);
}

function renderAnswerText(container, text, record) {
  const pattern=/\[([^\]]+)\]/g;
  let position=0;
  const known=new Set(record.context_ids);
  for (const match of text.matchAll(pattern)) {
    container.append(document.createTextNode(text.slice(position,match.index)));
    const ids=match[1].split(/[,\s]+/).filter(id=>known.has(id));
    if (ids.length) {
      const button=node('button','citation',match[0]);button.type='button';
      button.setAttribute('aria-label','Inspect cited source '+ids.join(', '));
      button.title=ids.length>1?'Open the first passage in this citation group. All passages remain available below.':'Open this source passage';
      button.addEventListener('click',()=>{
        state.sourceModel=record.model;state.order=record.order;state.highlight=ids[0];state.citedOnly=false;$('cited-only').checked=false;renderFilters();renderEvidence();syncUrl();
        const target=document.getElementById('passage-'+ids[0]);
        if (target) {target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'nearest'});target.focus({preventScroll:true});}
      });container.append(button);
    } else container.append(document.createTextNode(match[0]));
    position=match.index+match[0].length;
  }
  container.append(document.createTextNode(text.slice(position)));
}
function renderAnswer(record,order) {
  const card=node('article','answer-card');
  const heading=node('div','answer-card-header'), title=node('span','mono');
  title.append(node('span','order-glyph',order==='retrieved'?'↓':'↑'),document.createTextNode(order==='retrieved'?'ORIGINAL ORDER':'REVERSED ORDER'));
  heading.append(title,tag(record.assessment));card.append(heading);
  const body=node('div','answer-body');
  if (record.answer!==null) renderAnswerText(body,record.answer,record);
  else {
    body.append(node('p','','No completed answer was recorded.'));
    if (record.error) body.append(node('p','fine-print',record.error));
    if (record.raw_answer) {const details=node('details','incomplete-output');details.append(node('summary','','Inspect the preserved incomplete response'),node('pre','',record.raw_answer));body.append(details);}
  }
  card.append(body);
  const review=node('div','answer-review');review.append(node('strong','','SOURCE-BASED ASSESSMENT'),node('p','',record.notes));card.append(review);
  const checks=node('div','check-row');
  const completed=record.checks.completed ?? (record.status==='candidate_recorded');
  const idsValid=record.checks.citation_ids_valid ?? record.checks.rendered_citation_ids_valid;
  const noCitations=record.checks.has_citations===false || !(record.answer || '').includes('[');
  const idLabel=noCitations?'No citations':idsValid===true?'ID check: valid':idsValid===false?'ID check: flagged':'ID check: not recorded';
  for (const text of [completed?'Completed':'Incomplete',idLabel,`${record.seconds.toFixed(2)} s · model stage`]) checks.append(node('span','',text));
  const original=node('a','fine-link','Raw record ↗');original.href=sourceUrl(record.raw_path);original.target='_blank';original.rel='noopener noreferrer';checks.append(original);card.append(checks);
  if (record.group_parser_limitation) {const note=node('p','answer-review','Parser caveat: the saved check flags grouped brackets. Their individual IDs exist; this does not resolve semantic support.');card.append(note);}
  return card;
}
function renderPair() {
  const records=pair();
  $('selected-question').textContent=experiment().cases.find(c=>c.id===state.caseId).question;
  $('answer-grid').replaceChildren(...modelComparisons(experiment(),state.representation,state.caseId,state.model).map(({model,pair:records})=>{
    const group=node('section','model-comparison');
    const heading=node('div','model-comparison-heading');heading.append(node('h4','',modelLabel(model)));
    const inspect=node('button','text-link','Inspect this model’s sources ↓');inspect.type='button';
    inspect.addEventListener('click',()=>{state.sourceModel=model;state.highlight=null;renderEvidence();syncUrl();document.querySelector('.evidence-section').scrollIntoView({behavior:'smooth',block:'start'});});
    heading.append(inspect);const grid=node('div','answer-grid');
    grid.append(...['retrieved','reversed'].map(order=>records[order]?renderAnswer(records[order],order):node('p','load-state','This saved order is unavailable.')));
    group.append(heading,grid);return group;
  }));
  $('download-pair').textContent=state.model==='all'?'Download all model pairs ↓':'Download this model pair ↓';
  const same=records.retrieved && records.reversed && JSON.stringify(records.retrieved.context_ids)===JSON.stringify([...records.reversed.context_ids].reverse());
  $('pair-status').textContent=same?`${records.retrieved.context_ids.length} passages · exact reversal`:'Inspect the saved context';
}

function renderEvidence() {
  const record=pair()[state.order];
  $('evidence-original').setAttribute('aria-pressed',String(state.order==='retrieved'));
  $('evidence-reversed').setAttribute('aria-pressed',String(state.order==='reversed'));
  if (!record) {$('evidence-list').replaceChildren();return;}
  const cited=citationIds(record.answer,record.context_ids);
  const ids=state.citedOnly?record.context_ids.filter(id=>cited.has(id)):record.context_ids;
  $('evidence-count').textContent=`${modelLabel(record.model)} · ${ids.length} of ${record.context_ids.length} supplied passages · ${state.order==='retrieved'?'original':'reversed'} order`;
  const elements=ids.map(id=>{
    const passage=state.data.passages[id],article=node('article','passage'+(state.highlight===id?' highlighted':''));
    article.id='passage-'+id;article.tabIndex=-1;
    const content=node('div','passage-content'),meta=node('div','passage-meta');
    meta.append(node('strong','',passage.source),node('span','',passage.page?`PDF page ${passage.page}`:'Unpaginated text'),node('code','',id));
    if(cited.has(id))meta.append(node('span','cited-label','CITED'));
    content.append(meta,node('p','passage-text',passage.text));article.append(node('span','passage-rank',String(record.context_ids.indexOf(id)+1).padStart(2,'0')),content);
    return article;
  });
  if (!elements.length) elements.push(node('p','empty-state','No source citations were found in this saved answer. Turn off the filter to inspect the supplied passages.'));
  $('evidence-list').replaceChildren(...elements);
}

function renderSummary() {
  const exp=experiment(),calls=exp.records.filter(r=>r.order!=='no_context');
  $('result-metrics').replaceChildren(...[
    [String(exp.calls),'model calls'],[String(exp.controls),'separate code controls'],
    [String(exp.pairs),'exact order pairs'],[exp.models.length===1?'1':'3','local models'],
  ].map(([value,text])=>{const item=node('div','metric');item.append(node('strong','',value),node('span','',text));return item;}));
  $('distribution-title').textContent=exp.title+' · '+exp.calls+' model calls';
  $('distribution').replaceChildren(...assessmentDistribution(exp).map(item=>{
    const row=node('div','distribution-row '+item.tone),track=node('span','bar-track'),fill=node('span','bar-fill');
    fill.style.width=`${item.count/exp.calls*100}%`;track.append(fill);row.append(node('span','',item.name),track,node('span','bar-count',String(item.count)));return row;
  }));
  $('model-summary').replaceChildren(...exp.models.map(model=>{
    const rows=calls.filter(r=>r.model===model),completed=rows.filter(r=>(r.checks.completed??r.status==='candidate_recorded')===true).length;
    const row=node('div','model-row'),name=node('div','model-name');name.append(node('span','model-icon',model.startsWith('qwen')?'Q':'G'),node('strong','',modelLabel(model)));
    row.append(name,node('span','model-stats',`${completed}/${rows.length} completed · ${rows.reduce((n,r)=>n+r.seconds,0).toFixed(1)} s`));return row;
  }));
  const note=exp.id==='direct_confirmation'?'All 16 model calls completed and every citation ID exists. One order gives 12 credits; its reversed counterpart gives 8. Four other trials give correct core facts and then falsely abstain.':exp.id==='direct_answer'?'The direct baseline includes six output-limit failures. Qwen 8B still shows role reversal and unjustified abstention. Six Gemma responses expose a grouped-citation parser limitation; original checks are preserved.':'All 60 ID-selection calls passed structural checks. Only 4 of 24 absent-fact trials abstained correctly. Exact copied spans did not establish relevance or completeness.';
  $('result-notes').replaceChildren(node('strong','','Reading this experiment. '),document.createTextNode(note));
}

/** The overview always uses the three-model direct baseline, regardless of the selected detail tab. */
function renderModelOverview() {
  const baseline=state.data.experiments.find(e=>e.id==='direct_answer');
  const descriptions={
    'qwen3:4b':'Six outputs reached the generation limit. The other four placed analysis in the answer field.',
    'qwen3:8b':'Three supported answers and four justified abstentions. The remaining trials include one role reversal and two unjustified abstentions.',
    'gemma3:4b':'Three justified abstentions. The remaining trials contain contradictions, wrong facts, citation defects or unsupported extra text.'
  };
  $('model-overview').replaceChildren(...['qwen3:4b','qwen3:8b','gemma3:4b'].map(model=>{
    const records=baseline.records.filter(r=>r.model===model&&r.order!=='no_context');
    const completed=records.filter(r=>r.checks.completed??r.status==='candidate_recorded').length;
    const card=node('article','model-overview-card');card.append(node('h3','',modelLabel(model)),node('p','model-overview-count',`${records.length} model calls · ${completed} completed`),node('p','',descriptions[model]));
    const button=node('button','text-link','Inspect saved comparisons ↓');button.type='button';
    button.addEventListener('click',()=>{Object.assign(state,safeState(state.data,new URLSearchParams({experiment:'direct_answer',model})),{outcome:'all',highlight:null,controls:false,citedOnly:false});$('include-controls').checked=false;$('cited-only').checked=false;renderAll();$('explore').scrollIntoView({behavior:'smooth',block:'start'});});
    card.append(button);return card;
  }));
}

function tableRecords() {return filteredRecords(experiment(),state.model,state.representation,state.outcome,state.controls);}
function renderTable() {
  const records=tableRecords();
  $('table-caption').textContent=`${records.length} saved records · ${state.model==='all'?experiment().models.length+' tested models':modelLabel(state.model)}${state.representation==='direct'?'':' · '+(state.representation==='passages'?'whole passages':'text units')}${state.controls?' · controls included':' · code controls excluded'}. Figures above describe the entire selected experiment.`;
  $('records-body').replaceChildren(...records.map(record=>{
    const row=node('tr');
    row.append(node('td','',record.question),node('td','',modelLabel(record.model)),node('td','',record.order==='no_context'?'No context':record.order==='retrieved'?'Original':'Reversed'));
    const assessment=node('td');assessment.append(tag(record.assessment));row.append(assessment);
    const action=node('td');
    if (record.order==='no_context') {
      const link=node('a','','↗');link.href=sourceUrl(record.raw_path);link.target='_blank';link.rel='noopener noreferrer';link.setAttribute('aria-label','Inspect zero-model-call control record');action.append(link);
    } else {
      const button=node('button','','↗');button.type='button';button.setAttribute('aria-label','Inspect '+record.question+' in '+record.order+' order');
      button.addEventListener('click',()=>{state.model=record.model;state.sourceModel=record.model;state.caseId=record.case_id;state.order=record.order;state.highlight=null;state.outcome='all';renderAll();document.getElementById('explore').scrollIntoView({behavior:'smooth',block:'start'});});action.append(button);
    }
    row.append(action);return row;
  }));
  $('no-results').hidden=records.length>0;
}
function renderAll() {renderFilters();renderPair();renderEvidence();renderSummary();renderTable();syncUrl();}
function download(filename,content,type) {
  const url=URL.createObjectURL(new Blob([content],{type})),anchor=document.createElement('a');
  anchor.href=url;anchor.download=filename;document.body.append(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function initializeEvents() {
  $('case-select').addEventListener('change',event=>{state.caseId=event.target.value;state.highlight=null;renderPair();renderEvidence();syncUrl();});
  $('model-select').addEventListener('change',event=>{state.model=event.target.value;if(state.model!=='all')state.sourceModel=state.model;state.highlight=null;state.outcome='all';renderAll();});
  $('representation-select').addEventListener('change',event=>{state.representation=event.target.value;state.highlight=null;state.outcome='all';renderAll();});
  for (const [id,order] of [['evidence-original','retrieved'],['evidence-reversed','reversed']]) $(id).addEventListener('click',()=>{state.order=order;state.highlight=null;renderEvidence();syncUrl();});
  $('cited-only').addEventListener('change',event=>{state.citedOnly=event.target.checked;renderEvidence();});
  $('outcome-filter').addEventListener('change',event=>{state.outcome=event.target.value;renderTable();});
  $('include-controls').addEventListener('change',event=>{state.controls=event.target.checked;renderFilters();renderTable();});
  $('download-pair').addEventListener('click',()=>{
    const records=modelComparisons(experiment(),state.representation,state.caseId,state.model).flatMap(item=>Object.values(item.pair)),ids=new Set(records.flatMap(r=>r.context_ids));
    download(`evidenceshift-${state.experiment}-${state.caseId}-${state.model==='all'?'all-models':state.model.replace(':','-')}.json`,JSON.stringify({mode:'recorded_results',source_commit:state.data.source_commit,records,passages:[...ids].map(id=>state.data.passages[id])},null,2)+'\n','application/json');
  });
  $('download-results').addEventListener('click',()=>download(`evidenceshift-${state.experiment}-filtered.csv`,toCsv(tableRecords()),'text/csv;charset=utf-8'));
  $('share-comparison').addEventListener('click',async()=>{
    syncUrl();const url=new URL(location.href);url.hash='explore';
    try {await navigator.clipboard.writeText(url.toString());notify('Comparison link copied.');}
    catch {notify('Copy the comparison URL from your address bar.');}
  });
}

function applyTheme(value) {
  document.documentElement.dataset.theme=value;
  $('theme-toggle').setAttribute('aria-label',value==='dark'?'Switch to light theme':'Switch to dark theme');
  $('theme-toggle').setAttribute('aria-pressed',String(value==='dark'));
}
let savedTheme='light';try {savedTheme=localStorage.getItem('evidenceshift-theme') || 'light';}catch{/* Browsing works when local storage is disabled. */}
applyTheme(savedTheme==='dark'?'dark':'light');
$('theme-toggle').addEventListener('click',()=>{const value=document.documentElement.dataset.theme==='dark'?'light':'dark';applyTheme(value);try {localStorage.setItem('evidenceshift-theme',value);}catch{/* Theme stays active for this page. */}});

async function start() {
  try {
    const response=await fetch(new URL('data/experiments.json',import.meta.url));
    if (!response.ok) throw new Error('Dataset request failed');
    const data=await response.json();
    if (data.schema_version!==1 || !data.experiments?.length) throw new Error('Unexpected dataset schema');
    state.data=data;renderModelOverview();Object.assign(state,safeState(data,new URLSearchParams(location.search)));
    initializeEvents();renderAll();$('load-state').hidden=true;$('explorer-content').hidden=false;
  } catch {
    $('load-state').classList.add('error');$('load-state').textContent='The saved records could not be loaded. Reload this page, or inspect results/published in the GitHub repository.';
    for (const id of ['share-comparison','download-pair','download-results']) $(id).disabled=true;
  }
}
start();
