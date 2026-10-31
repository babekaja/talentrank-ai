"""Phase 3 integration with an in-memory private object store (no external services)."""
import io
import zipfile
from docx import Document
from reportlab.pdfgen import canvas
from app.main import app
from app.core.database import get_db
from app.documents.storage import get_storage
from app.documents.processing import process_document
from app.documents.validation import validate_zip
from app.api.v1 import uploads
from app.models import User, OrganizationMember
from app.core.security import hash_password
from test_recruitment import auth_headers, new_job, requirements


class Response:
    def __init__(self, data): self.content=data
    def stream(self, size):
        for i in range(0,len(self.content),size): yield self.content[i:i+size]
    def close(self): pass
    def release_conn(self): pass


class FakeStorage:
    def __init__(self): self.objects={}
    def ensure_bucket(self): pass
    def put(self,key,path,size,mime):
        with open(path,'rb') as f: self.objects[key]=f.read()
    def get(self,key): return Response(self.objects[key])
    def delete(self,key): self.objects.pop(key,None)


def docx_bytes(text='Développement d’une application avec Angular et TypeScript.'):
    d=Document();d.add_paragraph(text);f=io.BytesIO();d.save(f);return f.getvalue()


def pdf_bytes():
    f=io.BytesIO();c=canvas.Canvas(f);c.drawString(72,760,'Developpement backend Python FastAPI');c.save();return f.getvalue()


def create_batch(client,headers):
    job=new_job(client,headers).json()
    assert client.put(f'/api/v1/jobs/{job["id"]}/requirements', headers=headers, json=requirements()).status_code==200
    assert client.post(f'/api/v1/jobs/{job["id"]}/requirements/confirm', headers=headers,json={'expected_version':1}).status_code==200
    campaign=client.post('/api/v1/campaigns',headers=headers,json={'name':'Campagne CV test','job_id':job['id']}).json()
    assert client.patch(f'/api/v1/campaigns/{campaign["id"]}/status',headers=headers,json={'status':'active'}).status_code==200
    response=client.post('/api/v1/uploads/batches',headers=headers,json={'campaign_id':campaign['id']})
    assert response.status_code==201,response.text
    return response.json()['id']


def override_storage(store,monkeypatch):
    app.dependency_overrides[get_storage]=lambda:store
    monkeypatch.setattr(uploads,'enqueue',lambda document_id,db: True)


def test_pdf_docx_upload_extraction_idempotency_duplicates(client_and_orgs,monkeypatch):
    client,_=client_and_orgs
    store=FakeStorage();override_storage(store,monkeypatch)
    try:
        h=auth_headers(client);bid=create_batch(client,h)
        for filename,data in [('test.pdf',pdf_bytes()),('test.docx',docx_bytes())]:
            response=client.post(f'/api/v1/uploads/batches/{bid}/files',headers=h,files={'file':(filename,data)})
            assert response.status_code==201,response.text
            document=response.json()['items'][0]
            assert document['status']=='pending'
            db=next(app.dependency_overrides[get_db]())
            try:
                assert process_document(document['id'],db,store)=='completed'
                assert process_document(document['id'],db,store)=='completed'
            finally: db.close()
            pages=client.get(f'/api/v1/documents/{document["id"]}/pages',headers=h)
            assert pages.status_code==200,pages.text
            assert pages.json()['items'][0]['text'].strip()
            assert pages.json()['items'][0]['method'] in ('pdfplumber','python-docx')
            original=client.get(f'/api/v1/documents/{document["id"]}/download',headers=h)
            assert original.status_code==200 and original.content==data
            again=client.post(f'/api/v1/uploads/batches/{bid}/files',headers=h,files={'file':(filename,data)})
            assert again.json()['items'][0]['status']=='duplicate'
        progress=client.get(f'/api/v1/uploads/batches/{bid}/progress',headers=h).json()
        assert progress['total']==2 and progress['processed']==2 and progress['failed']==0
        assert len(store.objects)==2
    finally:app.dependency_overrides.pop(get_storage,None)


def test_zip_safe_and_reject_bad_signature(client_and_orgs,monkeypatch):
    client,_=client_and_orgs;store=FakeStorage();override_storage(store,monkeypatch)
    try:
        h=auth_headers(client);bid=create_batch(client,h)
        fake=client.post(f'/api/v1/uploads/batches/{bid}/files',headers=h,files={'file':('evil.pdf',b'NOT_A_PDF')})
        assert fake.status_code==415
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('folder/cv.docx',docx_bytes('Travail sur MySQL'))
        good=client.post(f'/api/v1/uploads/batches/{bid}/files',headers=h,files={'file':('group.zip',buf.getvalue())})
        assert good.status_code==201,good.text
        assert len(good.json()['items'])==1
        for bad_path in ['../escaped.docx','/absolute.docx']:
            buff=io.BytesIO()
            with zipfile.ZipFile(buff,'w') as z:z.writestr(bad_path,docx_bytes())
            failed=client.post(f'/api/v1/uploads/batches/{bid}/files',headers=h,files={'file':('group.zip',buff.getvalue())})
            assert failed.status_code==422,failed.text
        assert len(store.objects)==1
    finally:app.dependency_overrides.pop(get_storage,None)


def test_org_separation_and_worker_failure(client_and_orgs,monkeypatch):
    client,orgs=client_and_orgs;store=FakeStorage();override_storage(store,monkeypatch)
    try:
        h=auth_headers(client);bid=create_batch(client,h)
        uploaded=client.post(f'/api/v1/uploads/batches/{bid}/files',headers=h,files={'file':('note.docx',docx_bytes())})
        docid=uploaded.json()['items'][0]['id']
        db=next(app.dependency_overrides[get_db]())
        try:
            row=db.execute(__import__('sqlalchemy').select(__import__('app.models',fromlist=['CVDocument']).CVDocument).where(__import__('app.models',fromlist=['CVDocument']).CVDocument.id==docid)).scalar_one()
            store.objects.pop(row.object_key)
            assert process_document(docid,db,store)=='failed'
        finally:db.close()
        detail=client.get(f'/api/v1/documents/{docid}',headers=h).json()
        assert detail['error_code']=='EXTRACTION_FAILED'
        assert client.get(f'/api/v1/documents/{docid}/pages',headers=h).json()['items']==[]
        db=next(app.dependency_overrides[get_db]())
        try:
            user=User(email='beta.cv@example.org',full_name='Admin Beta',password_hash=hash_password('beta-cv-password-123'))
            db.add(user);db.flush()
            db.add(OrganizationMember(user_id=user.id,organization_id=orgs['beta'],role='org_admin'))
            db.commit()
        finally:db.close()
        token=client.post('/api/v1/auth/login',json={'organization_slug':'beta','email':'beta.cv@example.org','password':'beta-cv-password-123'}).json()['access_token']
        bh={'Authorization':f'Bearer {token}'}
        for path in [f'/api/v1/uploads/batches/{bid}',f'/api/v1/uploads/batches/{bid}/progress',f'/api/v1/documents/{docid}',f'/api/v1/documents/{docid}/pages',f'/api/v1/documents/{docid}/download']:
            assert client.get(path,headers=bh).status_code==404
        assert client.post(f'/api/v1/uploads/batches/{bid}/files',headers=bh,files={'file':('x.pdf',pdf_bytes())}).status_code==404
    finally:app.dependency_overrides.pop(get_storage,None)


def test_scanned_pdf_uses_local_ocr(tmp_path):
    """Image-only PDF -> local OCR, without a generative model."""
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader
    from app.documents.parsing import extract_pdf
    img=Image.new('RGB',(1400,260),'white')
    draw=ImageDraw.Draw(img)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',34)
    draw.text((40,50),'Developpeur logiciel avec projets Angular et Python.',font=font,fill='black')
    draw.text((40,120),'API REST et gestion de bases de donnees MySQL.',font=font,fill='black')
    output=tmp_path/'scan.pdf'
    c=canvas.Canvas(str(output),pagesize=(700,300))
    c.drawImage(ImageReader(img),0,75,width=700,height=150)
    c.save()
    result=extract_pdf(str(output))
    assert len(result)==1
    assert result[0].method=='tesseract',result
    assert 'Python' in result[0].text and 'Angular' in result[0].text


def test_zip_bomb_ratio_rejected(tmp_path):
    from fastapi import HTTPException
    path=tmp_path/'oversized.zip'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('mostly-compressible.pdf',b'%PDF-'+b'A'*2_000_000)
    import pytest
    with pytest.raises(HTTPException) as info:
        validate_zip(str(path),3000,15_728_640,1_000_000_000)
    assert info.value.status_code==413
