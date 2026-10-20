"""Local upload demo: python -m streamlit run web_demo/local_app_v2.py"""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
import streamlit as st
from evidence_api.local_upload_v2 import Workspace

st.set_page_config(page_title='EvidenceShift — local document evidence',page_icon='🔎',layout='wide')
st.title('EvidenceShift')
st.write('Upload documents. Ask a question. Inspect exact excerpts from the sources.')
st.caption('Local experimental demo · Ollama Qwen 3 8B · Semantic search')
st.info('Source-first mode displays copied excerpts. The model selects their relevance; exact copying does not guarantee that they completely answer your question.')

for key,value in [('source_v2_workspace',None),('source_v2_result',None),('source_v2_preview',None),('source_v2_bundle',None),('source_v2_upload_epoch',0),('source_v2_question_epoch',0)]:
    if key not in st.session_state:st.session_state[key]=value

with st.sidebar:
    st.header('Documents and runs')
    st.caption('Up to 8 PDF, DOCX, TXT or Markdown files. Each file: 5 MiB; combined: 20 MiB and 100,000 extracted characters. Text-based PDFs only.')
    st.caption('Runs and uploaded files are saved inside this project. Clearing removes the temporary search workspace; saved reports remain.')
    if st.button('Clear current workspace'):
        if st.session_state.source_v2_workspace:st.session_state.source_v2_workspace.close()
        for key in ['source_v2_workspace','source_v2_result','source_v2_preview','source_v2_bundle']:st.session_state[key]=None
        st.session_state.source_v2_upload_epoch+=1;st.session_state.source_v2_question_epoch+=1;st.rerun()
    st.divider()
    with st.expander('Evidence-order experiment'):
        variant=st.selectbox('Evidence sent to the generator',['retrieved','reversed','no_context'])
        st.caption('Reversed uses the same search hits in reverse order. No context produces a code abstention; it is not a reasoning test.')
    with st.expander('Known limitations'):
        st.write('The original generator and its failures are preserved. This revision copies source spans instead of paraphrasing. It can still select irrelevant or incomplete excerpts. Small corpora use complete passage coverage; larger corpora use semantic hits and neighboring passages. Context reservations are estimated conservatively and actual prompt tokens are logged.')

uploads=st.file_uploader('Choose your documents',type=['pdf','docx','txt','md'],accept_multiple_files=True,key='source_v2_upload_'+str(st.session_state.source_v2_upload_epoch))
if st.button('Process documents',disabled=not uploads,type='primary'):
    try:
        with st.spinner('Parsing documents and building the semantic search workspace…'):
            workspace=Workspace(ROOT,[(file.name,file.getvalue()) for file in uploads])
        old=st.session_state.source_v2_workspace
        st.session_state.source_v2_workspace=workspace
        st.session_state.source_v2_result=None;st.session_state.source_v2_preview=None;st.session_state.source_v2_bundle=None
        st.session_state.source_v2_question_epoch+=1
        if old:old.close()
    except Exception as exc:st.error(str(exc))

workspace=st.session_state.source_v2_workspace
if workspace:
    st.success('Processed '+str(len(workspace.documents))+' unique document(s).')
    with st.sidebar:
        if st.button('Prepare complete session export',key='export_sidebar_v2'):
            st.session_state.source_v2_bundle=workspace.export().read_bytes()
        if st.session_state.source_v2_bundle:
            st.download_button('Download session ZIP',data=st.session_state.source_v2_bundle,file_name='local_upload_smoke_bundle.zip',mime='application/zip',key='download_sidebar_v2')
    with st.expander('Document list'):
        for document in workspace.documents:
            st.write(document['source']+' · '+str(document['chunks'])+' passages')
            for warning in document.get('warnings',[]):st.warning(warning)
    question=st.text_input('Question about these documents',max_chars=1200,key='source_v2_question_'+str(st.session_state.source_v2_question_epoch))
    preview_col,ask_col=st.columns(2)
    with preview_col:preview=st.button('Inspect search results',disabled=not question.strip())
    with ask_col:ask=st.button('Generate answer',disabled=not question.strip(),type='primary')
    if preview:
        try:st.session_state.source_v2_preview={'question':question,'hits':workspace.search(question)}
        except Exception as exc:st.error(str(exc))
    if ask:
        try:
            with st.spinner('Selecting evidence and generating an answer with local Ollama…'):
                run=workspace.ask(question,variant)
                st.session_state.source_v2_result=run
                bundle=workspace.export()
                st.session_state.source_v2_bundle=bundle.read_bytes()
        except Exception as exc:st.error(str(exc))
    if st.session_state.source_v2_preview:
        preview_data=st.session_state.source_v2_preview
        with st.expander('Search preview for: '+preview_data['question']):
            for passage in preview_data['hits']:
                location='PDF page '+str(passage['page']) if passage['page'] else 'Unpaginated text'
                st.caption(passage['source']+' · '+location+' · '+passage['id']);st.text(passage['text'])
    run=st.session_state.source_v2_result
    if run:
        st.subheader('Source excerpts selected for your question')
        st.caption('Saved question: '+run['question']+' · evidence order: '+run['variant'])
        result=run.get('result',{})
        if result.get('candidate_answer') is not None:
            st.text(result['candidate_answer'])
            if run['variant']=='no_context':st.caption('Evidence was disabled for this control. The abstention was rendered by code.')
            else:st.caption('Quotation spans and citation IDs were checked by code. Relevance and completeness remain unverified model judgments.')
        else:
            st.error('No mechanically valid candidate was recorded for this run.')
            st.write(run.get('error') or result.get('error') or 'Inspect the saved trace.')
        if result.get('unanswered_parts'):
            st.warning('Parts marked unanswered by the model: ' + '; '.join(result['unanswered_parts']))
        if run.get('retrieval_plan'):
            plan=run['retrieval_plan']
            st.caption('Context: '+str(len(run.get('used_context',[])))+' of '+str(plan['corpus_chunks'])+' indexed passages; complete corpus coverage: '+str(plan['complete_corpus_coverage']))
        with st.expander('Original source passages used',expanded=False):
            for passage in run.get('used_context',[]):
                location='PDF page '+str(passage['page']) if passage['page'] else 'Unpaginated text'
                st.caption(passage['source']+' · '+location+' · '+passage['id']);st.text(passage['text'])
        if result.get('claim_source_records'):
            with st.expander('Excerpt-to-source mapping'):
                for claim in result['claim_source_records']:
                    st.write(claim['claim_text'])
                    st.caption('Citation IDs: '+', '.join(claim['passage_ids']))
                    for quote in claim['selected_quotations']:st.text(quote)
        with st.expander('Run trace'):
            st.write('Status: '+run['status'])
            st.table([{'stage':stage['stage'],'status':stage['status'],'seconds':stage.get('seconds'),'tokens':stage.get('generated_tokens')} for stage in result.get('stages',[])])
            if result.get('structured_answer') and result.get('candidate_answer') is None:st.json(result['structured_answer'])
    st.divider()
    st.caption('Saved session: '+str(workspace.folder.relative_to(ROOT)))
    with st.expander('Embedding identity and retrieval settings'):
        st.caption('Measured from the installed weights, tokenizer and configuration. This fingerprint does not infer a Hub revision.')
        st.json(workspace.identity)
    if st.button('Prepare complete session export'):
        st.session_state.source_v2_bundle=workspace.export().read_bytes()
    if st.session_state.source_v2_bundle:
        st.download_button('Download documents, answers and evidence report',data=st.session_state.source_v2_bundle,file_name='local_upload_smoke_bundle.zip',mime='application/zip')
else:
    st.write('Process one or more documents to start. Semantic search uses the existing MiniLM and Chroma pipeline.')
