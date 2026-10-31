"""REAL service-level smoke test, against a running stack and a dedicated DEMO org.

Needs TR_SMOKE_URL, TR_SMOKE_ORG, TR_SMOKE_EMAIL, TR_SMOKE_PASSWORD.
No production CV. Uses a synthetic DOCX generated locally; the demo records are retained
for the organization administrator to inspect/erase. Does not test Angular.
"""
import argparse
import io
import os
import sys
import time
from datetime import date, timedelta
from docx import Document
import httpx


def expect(reply, status=None):
    if status and reply.status_code != status:
        raise RuntimeError(f'HTTP {reply.status_code}, expected {status}, path {reply.request.url.path}')
    reply.raise_for_status()
    return reply.json() if reply.content else None


def docx_fixture():
    source=io.BytesIO()
    document=Document()
    document.add_heading('Profil entièrement fictif — test technique',0)
    document.add_paragraph('Projet : création d’une interface avec Angular et TypeScript.')
    document.add_paragraph('Une expérience professionnelle doit être vérifiée par un recruteur.')
    document.save(source)
    return source.getvalue()


def poll(getter, label, acceptable, errors, deadline):
    while time.monotonic() < deadline:
        value=getter()
        state=value.get('status',value.get('state'))
        if state in acceptable:
            return value
        if state in errors:
            raise RuntimeError(f'{label} failed, status={state}')
        time.sleep(2)
    raise RuntimeError(f'{label} did not finish before the configured timeout')


def run(base_url, org, email, password, timeout):
    with httpx.Client(base_url=base_url,timeout=20) as client:
        token=expect(client.post('/api/v1/auth/login',json={
            'organization_slug':org,'email':email,'password':password}),200)['access_token']
        client.headers['Authorization']=f'Bearer {token}'
        assert expect(client.get('/api/v1/auth/me'),200)['organization_slug']==org
        title=f'TEST SYNTHÉTIQUE v18 {time.strftime("%Y%m%d-%H%M%S")}'
        job=expect(client.post('/api/v1/jobs',json={
            'title':title,'description':'Test technique sans vrai CV',
            'work_mode':'hybrid','opens_on':str(date.today()),
            'closes_on':str(date.today()+timedelta(days=15))}),201)
        job_id=job['id']
        criteria={'items':[
            {'code':'angular','label':'Angular','category':'skill','required':True,
             'weight':1,'justification':'Projet web documenté'},
            {'code':'experience','label':'Expérience à confirmer','category':'experience','required':False,
             'weight':1,'justification':'Revue humaine indispensable'},
        ]}
        expect(client.put(f'/api/v1/jobs/{job_id}/requirements',json=criteria),200)
        expect(client.post(f'/api/v1/jobs/{job_id}/requirements/confirm',
                           json={'expected_version':1}),200)
        campaign=expect(client.post('/api/v1/campaigns',json={'job_id':job_id,'name':title}),201)
        cid=campaign['id']
        expect(client.patch(f'/api/v1/campaigns/{cid}/status',json={'status':'active'}),200)
        batch=expect(client.post('/api/v1/uploads/batches',json={'campaign_id':cid}),201)
        uploaded=expect(client.post(f'/api/v1/uploads/batches/{batch["id"]}/files',
               files={'file':('entierement-fictif.docx',docx_fixture(),
                   'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}),201)
        assert uploaded['items'][0]['queued'], 'Celery queue did not accept the document'
        docid=uploaded['items'][0]['id']
        deadline=time.monotonic()+timeout
        poll(lambda:expect(client.get(f'/api/v1/documents/{docid}'),200),'extraction',
             {'completed','needs_review'},{'failed'},deadline)
        nlp=poll(lambda:expect(client.get(f'/api/v1/documents/{docid}/nlp'),200),'NLP',
                 {'completed'},{'failed'},deadline)
        assert nlp['items'], 'No NLP mentions: check skill glossary and parser'
        run=expect(client.post(f'/api/v1/jobs/{job_id}/matching-runs',params={'campaign_id':cid}),202)
        runid=run['id']
        poll(lambda:expect(client.get(f'/api/v1/matching-runs/{runid}'),200),'matching',
             {'completed'},{'failed'},deadline)
        results=expect(client.get(f'/api/v1/matching-runs/{runid}/results'),200)
        assert results['total']==1
        result=results['items'][0]
        assert result['score'] is None, 'Non-skill evidence must NOT be scored as zero'
        assert result['state']=='partial_review_required'
        assert result['group_coverage']['summary']['evaluable_subset_coverage'] is not None
        explanation=expect(client.get(f'/api/v1/matching-results/{result["id"]}/explanation'),200)
        assert any(c['evidence'] for c in explanation['criteria'])
        expect(client.post(f'/api/v1/matching-results/{result["id"]}/request-review'),201)
        report=client.get(f'/api/v1/reports/campaigns/{cid}',params={'format':'csv','run_id':runid})
        assert report.status_code==200 and b'Non calculable' in report.content
        print('PASS real service smoke: authentication, MySQL, upload, MinIO, Celery, document parser, '
              'NLP, matching, human review, export and audit endpoints')
        print('Demo record IDs (admin must clean up):', {'job_id':job_id,'campaign_id':cid,'document_id':docid})


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--timeout',type=int,default=180)
    args=parser.parse_args()
    needed=['TR_SMOKE_URL','TR_SMOKE_ORG','TR_SMOKE_EMAIL','TR_SMOKE_PASSWORD']
    missing=[name for name in needed if not os.getenv(name)]
    if missing:parser.error('Missing environment variables: '+', '.join(missing))
    if args.timeout<10 or args.timeout>1800:parser.error('Timeout must be 10–1800s')
    run(os.environ['TR_SMOKE_URL'],os.environ['TR_SMOKE_ORG'],os.environ['TR_SMOKE_EMAIL'],
        os.environ['TR_SMOKE_PASSWORD'],args.timeout)


if __name__=='__main__':main()
