"""Classement et exports sur des dossiers fictifs, sans données de production."""
import csv
from io import BytesIO
from zipfile import ZipFile

from sqlalchemy import select

from app.main import app
from app.core.database import get_db
from app.models import (OrganizationMember, Candidate, Application, MatchingRun,
                        MatchingResult, MatchingCriterionResult)
from app.ml.matching import group_of
from test_insights import create_sample
from test_recruitment import auth_headers


def seed_ranking(org_id):
    with next(app.dependency_overrides[get_db]()) as db:
        member=db.scalar(select(OrganizationMember).limit(1))
        sample=create_sample(db,org_id,member.user_id)
        run=db.get(MatchingRun,sample['run'])
        requirements=[
            {'id':'a','code':'a','label':'Compétence A','category':'skill','required':True,'weight':3},
            {'id':'b','code':'b','label':'Compétence B','category':'skill','required':True,'weight':1},
            {'id':'c','code':'c','label':'Compétence C','category':'skill','required':False,'weight':1},
            {'id':'e','code':'e','label':'Expérience','category':'experience','required':False,'weight':1},
        ]
        run.requirements_snapshot=requirements
        run.weights_snapshot={'essential':60,'desirable':20,'experience':20,'projects_training':0}
        run.skill_mapping_snapshot={'a':'skill-a','b':'skill-b','c':'skill-c','e':None}
        base=db.get(MatchingResult,sample['result'])
        base.state='awaiting_documents'
        base.score=None
        ids={}
        for reference,documented in [('Z-PREMIER',{'a','c'}),('A-SECOND',{'b','c'}),
                                     ('T-EX-AEQUO',{'a','c'}),('B-ZERO',set())]:
            candidate=Candidate(organization_id=org_id,reference=reference,full_name='Profil fictif '+reference)
            db.add(candidate);db.flush()
            application=Application(organization_id=org_id,campaign_id=run.campaign_id,candidate_id=candidate.id)
            db.add(application);db.flush()
            result=MatchingResult(run_id=run.id,application_id=application.id,candidate_id=candidate.id,
                state='partial_review_required',score=None,documented=len(documented),to_review=1,
                not_documented=3-len(documented),evidence_fingerprint='0'*64,group_coverage={})
            db.add(result);db.flush()
            ids[reference]=result.id
            for req in requirements:
                state=('manual_review_required' if req['id']=='e' else
                       'documented_mention' if req['id'] in documented else 'not_documented')
                db.add(MatchingCriterionResult(result_id=result.id,requirement_id=req['id'],
                    code=req['code'],label=req['label'],group_code=group_of(req),state=state,
                    weight=req['weight'],contribution=0,note_code='TEST'))
        run.total=5;run.processed=5
        db.commit()
        return sample,ids


def test_weighted_ranking_ties_zero_and_pagination(client_and_orgs):
    client,orgs=client_and_orgs
    sample,ids=seed_ranking(orgs['alpha'])
    headers=auth_headers(client)
    url=f'/api/v1/matching-runs/{sample["run"]}/results'
    response=client.get(url,headers=headers)
    assert response.status_code==200,response.text
    rows=response.json()['items']
    assert [row['candidate_reference'] for row in rows[:4]]==['T-EX-AEQUO','Z-PREMIER','A-SECOND','B-ZERO']
    assert [row['rank'] for row in rows]==[1,1,3,4,None]
    assert [row['matching_percentage'] for row in rows]==[81.25,81.25,43.75,0,None]
    assert all(row['score'] is None for row in rows)
    assert response.json()['ranking']['assessed_weight_percent']==80
    assert response.json()['ranking']['criteria_count']==3
    page=client.get(url,headers=headers,params={'offset':2,'limit':1}).json()
    assert page['items'][0]['rank']==3 and page['total']==5
    comparison=client.post(f'/api/v1/matching-runs/{sample["run"]}/compare',headers=headers,
        json={'result_ids':[ids['A-SECOND'],ids['Z-PREMIER']]}).json()['items']
    assert [row['matching_percentage'] for row in comparison]==[43.75,81.25]
    assert [row['rank'] for row in comparison]==[3,1]


def test_same_criteria_for_each_candidate_and_immutable_weights(client_and_orgs):
    client,orgs=client_and_orgs
    sample,ids=seed_ranking(orgs['alpha'])
    headers=auth_headers(client)
    # Une ambiguïté retire ce critère du périmètre commun, pour tous les dossiers.
    with next(app.dependency_overrides[get_db]()) as db:
        criterion=db.scalar(select(MatchingCriterionResult).where(
            MatchingCriterionResult.result_id==ids['A-SECOND'],MatchingCriterionResult.requirement_id=='c'))
        criterion.state='needs_review';db.commit()
    url=f'/api/v1/matching-runs/{sample["run"]}/results'
    before=client.get(url,headers=headers).json()
    assert before['ranking']['criteria_count']==2
    assert before['ranking']['assessed_weight_percent']==60
    assert [row['matching_percentage'] for row in before['items']]==[75,75,25,0,None]
    assert client.post('/api/v1/matching/configuration',headers=headers,json={
        'essential':80,'desirable':10,'experience':10,'projects_training':0}).status_code==201
    assert client.get(url,headers=headers).json()['items']==before['items']


def test_exports_repeat_the_screen_order_and_reject_foreign_organization(client_and_orgs):
    client,orgs=client_and_orgs
    own,ids=seed_ranking(orgs['alpha'])
    foreign,_=seed_ranking(orgs['beta'])
    headers=auth_headers(client)
    screen=client.get(f'/api/v1/matching-runs/{own["run"]}/results',headers=headers).json()['items']
    url=f'/api/v1/reports/campaigns/{own["campaign"]}'
    response=client.get(url,headers=headers,params={'format':'csv','run_id':own['run']})
    assert response.status_code==200
    rows=list(csv.DictReader(response.content.decode('utf-8-sig').splitlines(),delimiter=';'))
    assert [row['Référence dossier'] for row in rows]==[row['candidate_reference'] for row in screen]
    assert rows[0]['Rang']=='1' and rows[0]['Correspondance pondérée (%)']=='81.25'
    assert rows[-1]['Rang']=='Non classé' and rows[-1]['Correspondance pondérée (%)']=='Non calculable'
    xlsx=client.get(url,headers=headers,params={'format':'xlsx'}).content
    with ZipFile(BytesIO(xlsx)) as archive:
        assert b'81.25' in archive.read('xl/worksheets/sheet1.xml')
        assert b'Classement' in archive.read('xl/workbook.xml')
    pdf=client.get(url,headers=headers,params={'format':'pdf'}).content
    assert pdf.startswith(b'%PDF')
    assert client.get(f'/api/v1/matching-runs/{foreign["run"]}/results',headers=headers).status_code==404
    assert client.get(f'/api/v1/reports/campaigns/{foreign["campaign"]}',headers=headers).status_code==404
    assert client.get(url,headers=headers,params={'run_id':foreign['run']}).status_code==409


def test_no_shared_assessable_criterion_never_creates_a_zero_score(client_and_orgs):
    client,orgs=client_and_orgs
    sample,ids=seed_ranking(orgs['alpha'])
    with next(app.dependency_overrides[get_db]()) as db:
        criteria=db.scalars(select(MatchingCriterionResult).where(
            MatchingCriterionResult.result_id==ids['A-SECOND'])).all()
        for criterion in criteria:criterion.state='needs_review'
        db.commit()
    data=client.get(f'/api/v1/matching-runs/{sample["run"]}/results',headers=auth_headers(client)).json()
    assert data['ranking']['ranked_count']==0
    assert all(row['rank'] is None and row['matching_percentage'] is None for row in data['items'])
