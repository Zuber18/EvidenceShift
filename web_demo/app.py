"""Run with: streamlit run web_demo/app.py"""
import os
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
import streamlit as st
from web_demo.support import DemoBudget,MODELS,PROFILE,answer_document,parse_upload,retrieve,close_document

st.set_page_config(page_title='EvidenceShift — answers with evidence',page_icon='🔎',layout='wide')
st.title('EvidenceShift')
st.write('Upload a document. Ask a question. Inspect the evidence behind the answer.')
st.caption('Experimental document Q&A • Free-tier demo • Model checks are advisory')

@st.cache_resource
def budget():return DemoBudget(limit=8,window=3600)

def key():
    value=os.environ.get('GROQ_API_KEY','')
    if value:return value
    try:return st.secrets.get('GROQ_API_KEY','')
    except Exception:return ''

for name,value in [('document',None),('result',None),('bundle',None),('evidence',[]),('upload_epoch',0),('last_ask',0),('session_runs',0)]:
    if name not in st.session_state:st.session_state[name]=value

with st.sidebar:
    st.header('Run settings')
    model=st.selectbox('Cloud model',MODELS)
    variant=st.selectbox('Evidence order',['retrieved','reversed','no_context'])
    st.caption('Retrieval reuses the local API: MiniLM embeddings, token-aware splitting and Chroma cosine search. Cloud generation uses the selected hosted model.')
    st.caption('Public demo: up to 8 model runs/hour per server process, plus provider quotas. Each run makes up to 3 calls. No automatic retries or paid fallback.')
    if st.button('Clear session document and results'):
        close_document(st.session_state.document)
        for name in ('document','result','bundle'):st.session_state[name]=None
        st.session_state.evidence=[];st.session_state.upload_epoch+=1;st.rerun()
    st.divider()
    st.write('Local results')
    st.caption('Local benchmark results will be published after review. Demo outputs are separate from benchmark findings.')

st.info('When you click Ask, selected document evidence is sent to Groq. Use documents you can share with that service. Document text and the original upload are held in temporary session storage. Clear the session to remove its collection and temporary files.')

file=st.file_uploader('Upload PDF, DOCX, TXT or Markdown',type=['pdf','docx','txt','md'],key=f'upload_{st.session_state.upload_epoch}',help='5 MiB/file, 50 text-bearing pages, 100,000 extracted characters. Text-based PDFs only; no OCR.')
left,right=st.columns(2)
with left:ingest=st.button('Process uploaded document',disabled=file is None,type='primary')
with right:sample=st.button('Use sample policy document')
if ingest or sample:
    try:
        with st.spinner('Loading the shared embedding model and indexing the document…'):
            if sample:
                sample_file=ROOT/'evaluation/fixtures/travel_policy.txt'
                document=parse_upload(sample_file.name,sample_file.read_bytes())
            else:document=parse_upload(file.name,file.getvalue())
        close_document(st.session_state.document)
        st.session_state.document=document
        st.session_state.result=None;st.session_state.bundle=None;st.session_state.evidence=[]
    except Exception as exc:st.error(str(exc))

if st.session_state.document:
    document=st.session_state.document
    st.success(f"Processed {document['source']} · {document['chunk_count']} passages")
    for warning in document['warnings']:st.warning(warning)
    question=st.text_input('Your question',max_chars=1200,placeholder='Does the policy require advance approval for every journey?')
    preview,ask=st.columns(2)
    with preview:preview_clicked=st.button('Inspect retrieved evidence',disabled=not question.strip())
    with ask:ask_clicked=st.button('Ask with evidence',disabled=not question.strip(),type='primary')
    if preview_clicked:
        st.session_state.evidence=retrieve(document,question)
    if ask_clicked:
        now=time.time()
        if not key():st.error('Live inference is not configured on this instance yet. Evidence inspection and the sample upload still work.')
        elif now-st.session_state.last_ask<30:st.warning('Wait 30 seconds between runs in this session.')
        elif st.session_state.session_runs>=5:st.warning('This demo session has reached its five-run limit. Evidence inspection remains available.')
        elif not budget().reserve(now):st.warning('The demo has reached its hourly run allowance. Please try later; evidence inspection remains available.')
        else:
            st.session_state.last_ask=now;st.session_state.session_runs+=1
            try:
                with st.spinner('Selecting evidence, generating claims, and checking support…'):
                    result,bundle,evidence=answer_document(document,question,model,key(),variant)
                st.session_state.result=result;st.session_state.bundle=bundle;st.session_state.evidence=evidence
            except Exception as exc:st.error(str(exc))
    if st.session_state.evidence:
        with st.expander('Source evidence',expanded=True):
            for passage in st.session_state.evidence:
                location=f"PDF page {passage['page']}" if passage['page'] else 'Unpaginated text'
                st.caption(f"{passage['source']} · {location} · {passage['id']}")
                st.text(passage['text'])
    result=st.session_state.result
    if result:
        st.subheader('Answer and checks')
        st.caption(f"Question: {result['question']}")
        if result['status']=='blocked':
            st.error('Answer withheld: a validation or support check failed.')
            if result.get('error'):st.caption(result['error'])
            if result.get('candidate_answer'):
                with st.expander('Inspect the withheld candidate'):st.text(result['candidate_answer'])
        else:
            st.text(result['delivery_answer'])
            st.warning('Candidate passed structural/advisory checks. Factual review is still required.')
        if result.get('omitted_for_budget'):st.caption('Context omitted for budget: '+', '.join(result['omitted_for_budget']))
        with st.expander('Stage timings and advisory verdict'):
            st.table([{'stage':x['stage'],'status':x['status'],'seconds':x.get('seconds'),'tokens':x.get('generated_tokens')} for x in result['stages']])
            if result.get('advisory_verdict'):st.json(result['advisory_verdict'])
        st.download_button('Download this run and its evidence',data=st.session_state.bundle,file_name=result['run_id']+'.zip',mime='application/zip')
else:
    st.write('Start with your own document or the sample policy. Retrieval inspection makes no inference call.')

st.divider()
st.caption('Document isolation: each visitor has separate Streamlit session state. Clearing removes in-app state; hosting and inference-provider retention are governed by those services. Generation models differ from the local Ollama benchmark; retrieval uses the shared local implementation.')
