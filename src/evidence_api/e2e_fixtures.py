"""Small deterministic text fixtures for testing actual document ingestion."""
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
from textwrap import wrap
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED


def pdf_bytes(text):
    """Put the shared heading on page 1 and operative evidence on page 2."""
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    heading,body=text.strip().split('\n\n',1)
    writer=PdfWriter()
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    for content in (heading,body):
        page=writer.add_blank_page(width=612,height=792)
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
        lines=wrap(content,width=84,break_long_words=False,break_on_hyphens=False)
        if len(lines)>45:raise ValueError('PDF fixture body exceeds one page')
        escaped=lambda line:line.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
        commands=['BT /F1 11 Tf 40 748 Td 15 TL']
        for i,line in enumerate(lines):
            if i:commands.append('T*')
            commands.append('('+escaped(line)+') Tj')
        commands.append('ET')
        stream=DecodedStreamObject();stream.set_data('\n'.join(commands).encode('ascii'))
        page[NameObject('/Contents')]=writer._add_object(stream)
    output=BytesIO();writer.write(output);return output.getvalue()


def docx_bytes(text):
    """Use ordinary paragraphs and stabilize ZIP timestamps for reproducible bytes."""
    from docx import Document
    document=Document()
    for paragraph in text.strip().split('\n\n'):document.add_paragraph(paragraph)
    fixed=datetime(2000,1,1,tzinfo=timezone.utc)
    document.core_properties.created=fixed;document.core_properties.modified=fixed
    output=BytesIO();document.save(output)
    stable=BytesIO()
    with ZipFile(BytesIO(output.getvalue())) as source,ZipFile(stable,'w',ZIP_DEFLATED) as target:
        for name in sorted(source.namelist()):
            info=ZipInfo(name,date_time=(2000,1,1,0,0,0));info.compress_type=ZIP_DEFLATED
            target.writestr(info,source.read(name))
    return stable.getvalue()


def make_files(plan,folder):
    folder=Path(folder);records=[]
    for fmt in ['txt','pdf','docx']:
        target=folder/fmt;target.mkdir(parents=True,exist_ok=True)
        for case in plan['cases']:
            for passage in case['context']:
                text=passage['text'];filename=Path(passage['source']).stem+'.'+fmt
                raw=text.encode('utf-8') if fmt=='txt' else pdf_bytes(text) if fmt=='pdf' else docx_bytes(text)
                path=target/filename;path.write_bytes(raw)
                records.append({'format':fmt,'case_id':case['id'],'fixture_id':passage['id'],
                                'filename':filename,'path':path,'expected_text':text})
    return records
