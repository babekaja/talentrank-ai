"""Phase 6 synthetic tests: never involve real candidate data."""
from io import BytesIO
import csv
from zipfile import ZipFile
from sqlalchemy import select
from app.main import app
from app.core.database import get_db
from app.models import (Job,RecruitmentCampaign,Candidate,Application,UploadBatch,CVDocument,
    DocumentPage,Skill,SkillEvidence,MatchingRun,MatchingResult,MatchingCriterionResult,
    MatchingEvidence,ReportExport,Organization)
from app.insights.quality import inspect_pages
from app.insights.exports import csv_bytes,safe_cell,xlsx_bytes,pdf_bytes
from test_recruitment import auth_headers


def create_sample(db,org_id,user_id):
    job=Job(organization_id=org_id,title='Poste démonstration',description='Exigences configurées',
            status='open',created_by=user_id)
    db.add(job);db.flush()
    campaign=RecruitmentCampaign(organization_id=org_id,job_id=job.id,name='Campagne test',
            status='active',created_by=user_id)
    db.add(campaign);db.flush()
    cand=Candidate(organization_id=org_id,reference='DOSSIER-1',full_name='Personne fictive')
    db.add(cand);db.flush()
    application=Application(organization_id=org_id,campaign_id=campaign.id,candidate_id=cand.id)
    db.add(application);db.flush()
    batch=UploadBatch(organization_id=org_id,campaign_id=campaign.id,created_by=user_id)
    db.add(batch);db.flush()
    document=CVDocument(organization_id=org_id,batch_id=batch.id,campaign_id=campaign.id,
       application_id=application.id,filename='cv.pdf',sha256='a'*64,content_type='application/pdf',
       byte_size=100,object_key=f'{org_id}/test/sample.pdf',status='completed',page_count=1)
    db.add(document);db.flush()
    page=DocumentPage(document_id=document.id,page_number=1,text='Projet Angular 31/02/2025 exécuté.',
       extraction_method='pdfplumber',version='1')
    db.add(page);db.flush()
    skill=Skill(code=f'angular-test-{org_id[:8]}',label_fr='Angular',label_en='Angular',
        taxonomy='test',version='1',active=True)
    db.add(skill);db.flush()
    mention=SkillEvidence(organization_id=org_id,document_id=document.id,page_id=page.id,
           skill_id=skill.id,start_offset=7,end_offset=14,matched_text='Angular',
           match_method='lexical',status='confirmed',rules_version='test')
    db.add(mention);db.flush()
    run=MatchingRun(organization_id=org_id,campaign_id=campaign.id,job_id=job.id,
      criteria_version=1,config_version=0,algorithm_version='test',
      weights_snapshot={'essential':100},requirements_snapshot=[],application_ids_snapshot=[application.id],
      skill_mapping_snapshot={},status='completed',total=1,processed=1,created_by=user_id)
    db.add(run);db.flush()
    result=MatchingResult(run_id=run.id,application_id=application.id,candidate_id=cand.id,
      score=100,state='review_required',documented=1,to_review=0,not_documented=0,
      evidence_fingerprint='a'*64,group_coverage={})
    db.add(result);db.flush()
    criterion=MatchingCriterionResult(result_id=result.id,requirement_id='req-1',code='angular',
      label='Angular',group_code='essential',state='documented_mention',weight=1,
      contribution=100,note_code='test')
    db.add(criterion);db.flush()
    proof=MatchingEvidence(criterion_result_id=criterion.id,evidence_id=mention.id,
      document_id=document.id,page_id=page.id,page_number=1,start_offset=7,end_offset=14,
      matched_text='Angular',verification_status='confirmed')
    db.add(proof);db.commit()
    return {'campaign':campaign.id,'document':document.id,'run':run.id,'result':result.id,'org':org_id}


def test_quality_date_detection_with_exact_excerpt():
    class Page: page_number=2; text='Dates du test : 31/02/2025 et 28/02/2025.'
    flagged=inspect_pages([Page()]);assert len(flagged)==1
    assert flagged[0]['code']=='INVALID_CALENDAR_DATE'
    assert '31/02/2025' in flagged[0]['source_excerpt']
    assert '28/02/2025' not in flagged[0]['message']


def test_safe_spreadsheet_formats():
    assert safe_cell(' =HYPERLINK("bad")').startswith("'")
    assert safe_cell('+SUM(1,2)').startswith("'")
    assert safe_cell('DOSSIER-SANS-FORMULE')=='DOSSIER-SANS-FORMULE'
    rows=[('=HYPERLINK("evil")','ID',85.50,'documented',2,1,0,'to_review')]
    text=csv_bytes(rows).decode('utf-8-sig')
    assert next(csv.reader(text.splitlines()[1:],delimiter=';'))[0].startswith("'")
    xlsx=xlsx_bytes(rows,'Rapport test')
    with ZipFile(BytesIO(xlsx)) as archive:
        assert '[Content_Types].xml' in archive.namelist()
        assert b'HYPERLINK' in archive.read('xl/worksheets/sheet1.xml') or any(
            b'HYPERLINK' in archive.read(n) for n in archive.namelist() if n.endswith('.xml'))
    assert pdf_bytes(rows,'Rapport test').startswith(b'%PDF')


def test_insights_routes_tenant_scope_and_exports(client_and_orgs):
    client,orgs=client_and_orgs;headers=auth_headers(client)
    db=next(app.dependency_overrides[get_db]())
    try:
        org=db.get(Organization,orgs['alpha'])
        from app.models import OrganizationMember
        member=db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id==orgs['alpha']))
        item=create_sample(db,org.id,member.user_id)
        # Foreign tenant data should never leak into Alpha's counters.
        extra=Job(organization_id=orgs['beta'],title='Autre offre',description='Privé',created_by=member.user_id)
        db.add(extra);db.commit()
    finally:db.close()
    dash=client.get('/api/v1/dashboard/overview',headers=headers)
    assert dash.status_code==200,dash.text
    assert dash.json()['cards']['jobs']==1
    assert dash.json()['cards']['applications']==1
    assert dash.json()['cards']['documents']==1
    viewed=client.get(f'/api/v1/documents/{item["document"]}/viewer',headers=headers)
    assert viewed.status_code==200,viewed.text
    assert viewed.json()['pages'][0]['mentions'][0]['text']=='Angular'
    assert viewed.json()['pages'][0]['mentions'][0]['start']==7
    quality=client.get(f'/api/v1/documents/{item["document"]}/quality',headers=headers)
    assert quality.status_code==200
    assert any(flag['code']=='INVALID_CALENDAR_DATE' for flag in quality.json()['flags'])
    gaps=client.get(f'/api/v1/matching-results/{item["result"]}/gaps',headers=headers)
    assert gaps.status_code==200
    assert gaps.json()['documented'][0]['has_source'] is True
    for format,signature in [('csv',b'\xef\xbb\xbf'),('xlsx',b'PK'),('pdf',b'%PDF')]:
        response=client.get(f'/api/v1/reports/campaigns/{item["campaign"]}',headers=headers,params={'format':format})
        assert response.status_code==200,response.text[:300] if response.status_code!=200 else ''
        assert response.content.startswith(signature)
        assert response.headers['cache-control']=='private, no-store'
    history=client.get('/api/v1/reports/history',headers=headers)
    assert history.status_code==200 and len(history.json()['items'])==3
    assert all(x['row_count']==1 for x in history.json()['items'])
    # Cross-tenant access (including download and quality inspection) must be rejected.
    db=next(app.dependency_overrides[get_db]())
    try:
        member=db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id==orgs['alpha']))
        beta=create_sample(db,orgs['beta'],member.user_id)
    finally:db.close()
    assert client.get(f'/api/v1/reports/campaigns/{beta["campaign"]}',headers=headers).status_code==404
    assert client.get(f'/api/v1/documents/{beta["document"]}/viewer',headers=headers).status_code==404
    assert client.get(f'/api/v1/documents/{beta["document"]}/quality',headers=headers).status_code==404
    assert client.get(f'/api/v1/matching-results/{beta["result"]}/gaps',headers=headers).status_code==404
    assert client.get(f'/api/v1/reports/campaigns/{item["campaign"]}',headers=headers,
                      params={'run_id':beta['run']}).status_code==409
