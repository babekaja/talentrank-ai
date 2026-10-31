"""REAL HTTP load test: 100/500/1000/3000 synthetic CVs on a running stack.

The real pipeline runs MySQL -> MinIO -> Redis/Celery -> extraction, then optional
NLP. No fabricated success or timing. Creates and retains DEMO test records.

Required env: TR_SMOKE_URL, TR_SMOKE_ORG, TR_SMOKE_EMAIL, TR_SMOKE_PASSWORD.
Run only in an isolated testing environment; never on real candidates.
"""
from __future__ import annotations
import argparse
import io
import json
import os
from pathlib import Path
import random
import secrets
import time
import zipfile
from datetime import date, timedelta
from docx import Document
import httpx


def synthetic_docx(n:int) -> bytes:
    rng = random.Random(45000+n)
    doc = Document()
    doc.add_heading(f'CANDIDATURE TOTALEMENT FICTIVE — CV-{n:05d}',0)
    # Non-identifying deterministic noise prevents artificially high ZIP ratios.
    doc.add_paragraph('Projet personnel : application Angular TypeScript et API FastAPI MySQL.')
    doc.add_paragraph('Stage : inventaire et organisation de stock, dates fictives.')
    doc.add_paragraph('Reference de test : ' + ''.join(rng.choice('abcdefghijkmnopqrstuvwxyz0123456789') for _ in range(450)))
    result=io.BytesIO(); doc.save(result)
    return result.getvalue()


def archive_chunk(start:int,end:int)->bytes:
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=2) as z:
        for i in range(start,end):
            z.writestr(f'fictional-cv-{i:05d}.docx',synthetic_docx(i))
    return stream.getvalue()


def api(reply:httpx.Response, expected:int=200):
    if reply.status_code != expected:
        raise RuntimeError(f'HTTP_{reply.status_code}:{reply.request.url.path}')
    return reply.json()


def perform(base:str,org:str,email:str,password:str,count:int,chunk_size:int,
            poll_interval:int,max_poll_minutes:int,report_path:Path):
    events=[]
    started=time.monotonic()
    with httpx.Client(base_url=base,timeout=httpx.Timeout(600.0,connect=10.0)) as client:
        token=api(client.post('/api/v1/auth/login',json={'organization_slug':org,'email':email,'password':password}))['access_token']
        client.headers['Authorization']=f'Bearer {token}'
        api(client.get('/health/ready'))
        title=f'TEST-CHARGE-SYNTHETIQUE-{count}-{secrets.token_hex(3)}'
        job=api(client.post('/api/v1/jobs',json={'title':title,'description':'CV FICTIFS POUR BENCHMARK — ne pas utiliser en RH',
            'opens_on':str(date.today()),'closes_on':str(date.today()+timedelta(days=7))}),201)
        jobid=job['id']
        api(client.put(f'/api/v1/jobs/{jobid}/requirements',json={'items':[
            {'code':'angular','label':'Angular','category':'skill','required':True,'weight':1,
             'justification':'Essai technique; aucune décision RH.'}]}))
        api(client.post(f'/api/v1/jobs/{jobid}/requirements/confirm',json={'expected_version':1}))
        campaign=api(client.post('/api/v1/campaigns',json={'job_id':jobid,'name':title}),201)
        cid=campaign['id'];api(client.patch(f'/api/v1/campaigns/{cid}/status',json={'status':'active'}))
        batch=api(client.post('/api/v1/uploads/batches',json={'campaign_id':cid}),201)
        bid=batch['id']
        # Persist metadata immediately: permits manual recovery and cleanup on failure.
        report={'status':'running','requested':count,'job_id':jobid,'campaign_id':cid,'batch_id':bid,
                'documents_uploaded':0,'chunks':[],'results':{},'environment':'actual_http_service_stack',
                'warning':'Test synthétique; supprimer les enregistrements et objets après validation.'}
        def checkpoint():
            report_path.parent.mkdir(parents=True,exist_ok=True)
            tmp=report_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2))
            tmp.replace(report_path)
        checkpoint()
        for start in range(0,count,chunk_size):
            end=min(count,start+chunk_size)
            content=archive_chunk(start,end)
            upload_start=time.monotonic()
            response=api(client.post(f'/api/v1/uploads/batches/{bid}/files',files={
                'file':(f'synthetic-{start}-{end}.zip',content,'application/zip')}),201)
            items=response['items']
            queued=sum(item.get('queued',False) for item in items)
            duplicates=sum(item.get('status')=='duplicate' for item in items)
            report['documents_uploaded']+=len(items)
            report['chunks'].append({'start':start,'end':end,'seconds':round(time.monotonic()-upload_start,3),
                'bytes':len(content),'queued':queued,'duplicates':duplicates})
            checkpoint()
            if len(items)!=end-start or queued != end-start or duplicates:
                report['status']='incomplete_queue_or_deduplication'
                checkpoint()
                raise RuntimeError('Document upload returned incomplete/duplicate/unqueued items')
        deadline=time.monotonic()+max_poll_minutes*60
        while time.monotonic()<deadline:
            stats=api(client.get(f'/api/v1/uploads/batches/{bid}/progress'))
            report['results']=stats
            report['elapsed_seconds']=round(time.monotonic()-started,2)
            checkpoint()
            if stats['total']==count and stats['processed']+stats['failed']==count:
                report['extraction_status']='completed_with_errors' if stats['failed'] else 'completed'
                break
            time.sleep(poll_interval)
        else:
            report['status']='timeout_extraction'
            checkpoint()
            return report
        # NLP runs automatically after extraction in Celery, independently of HTTP.
        # Complete only when the pipeline is truly done, not when files are uploaded.
        while time.monotonic()<deadline:
            nlp=api(client.get(f'/api/v1/uploads/batches/{bid}/pipeline-progress'))
            report['nlp_progress']=nlp
            report['elapsed_seconds']=round(time.monotonic()-started,2)
            checkpoint()
            if nlp['nlp_completed']+nlp['nlp_failed']+stats['failed']==count:
                break
            time.sleep(poll_interval)
        else:
            report['status']='timeout_nlp'
            checkpoint()
            return report
        # Complete campaign matching after all NLP runs have finished.
        matching=api(client.post(f'/api/v1/jobs/{jobid}/matching-runs',params={'campaign_id':cid}),202)
        mid=matching['id'];report['matching_run_id']=mid;checkpoint()
        while time.monotonic()<deadline:
            state=api(client.get(f'/api/v1/matching-runs/{mid}'))
            report['matching_progress']={key:state.get(key) for key in ('status','total','processed')}
            report['elapsed_seconds']=round(time.monotonic()-started,2)
            checkpoint()
            if state['status'] in ('completed','failed'):
                break
            time.sleep(poll_interval)
        else:
            report['status']='timeout_matching'
            checkpoint()
            return report
        if (stats['failed'] or nlp['nlp_failed'] or state['status']!='completed'
                or state.get('processed')!=count):
            report['status']='completed_with_errors'
        else:
            report['status']='completed'
        report['documents_per_second']=round(count/report['elapsed_seconds'],3) if report['elapsed_seconds'] else None
        checkpoint()
        return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=3000,choices=(100,500,1000,3000))
    parser.add_argument('--chunk-size',type=int,default=100)
    parser.add_argument('--poll-seconds',type=int,default=5)
    parser.add_argument('--max-poll-minutes',type=int,default=60)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.chunk_size<=200 or not 1<=args.poll_seconds<=60 or not 1<=args.max_poll_minutes<=480:
        parser.error('Invalid batch or poll parameters')
    keys=('TR_SMOKE_URL','TR_SMOKE_ORG','TR_SMOKE_EMAIL','TR_SMOKE_PASSWORD')
    missing=[k for k in keys if not os.getenv(k)]
    if missing:parser.error('Missing real service credentials: '+', '.join(missing))
    url=os.environ['TR_SMOKE_URL']
    if not (url.startswith('http://127.0.0.1:') or url.startswith('http://localhost:') or url.startswith('https://')):
        parser.error('Use localhost or HTTPS for the real stack')
    result=perform(url,*[os.environ[k] for k in keys[1:]],args.count,
                   args.chunk_size,args.poll_seconds,args.max_poll_minutes,args.report)
    print(json.dumps({'status':result['status'],'report':str(args.report),
                      'processed':result.get('results',{}).get('processed')},ensure_ascii=False))
    if result['status']!='completed':raise SystemExit(2)

if __name__=='__main__':main()
