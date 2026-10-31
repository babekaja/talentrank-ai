"""Measure 100–3000 REAL, freshly generated DOCX inputs through local parser/NLP/matching.

NO Docker, S3, Celery, Qdrant, OCR or HTTP. Never report these results as a
full-stack benchmark. Runs one CV at a time to bound process memory.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
from time import perf_counter
import io
import hashlib
from docx import Document
from app.documents.parsing import extract_docx
from app.documents.validation import inspect_cv, DOCX_MIME
from app.ml.recognition import extract_mentions, normalize
from app.ml.sections import extract_source_facts
from app.ml.matching import calculate, DEFAULT_WEIGHTS
from scripts.build_review_corpus_v25 import CONCEPTS


def one_cv(index:int)->bytes:
    concept=CONCEPTS[index%len(CONCEPTS)]
    lang='fr' if (index//len(CONCEPTS))%2==0 else 'en'
    positive=concept[2] if lang=='fr' else concept[3]
    negative=concept[4] if lang=='fr' else concept[5]
    d=Document()
    d.add_heading('CV FICTIF / FICTIONAL RESUME',0)
    d.add_paragraph(f'IDENTIFIANT TECHNIQUE : SYNTH-{index:05d}')
    d.add_heading('Projets' if lang=='fr' else 'Projects',level=1)
    d.add_paragraph(positive+f' Projet témoin {index:05d}.')
    d.add_heading('Objectifs' if lang=='fr' else 'Objectives',level=1)
    d.add_paragraph(negative+f' Cas expérimental {index:05d}.')
    data=io.BytesIO();d.save(data);return data.getvalue()


def perform(count:int, report:Path, checkpoints=(100,500,1000,3000)):
    if not 1<=count<=3000:raise ValueError('OUT_OF_RANGE')
    started=perf_counter(); stages={k:0.0 for k in ('generate','validate','extract','nlp','matching')}
    fails=[]; fail_count=0; total_bytes=0; pages=0; mentions=0; facts=0; match_complete=0
    hashes=set(); snapshots=[]
    req=[{'id':'criterion-1','category':'skill','required':True,'weight':1}]
    mapped={'criterion-1':'skill-1'}
    checkpoint_set=set(n for n in checkpoints if n<=count)|{count}
    for i in range(count):
        try:
            t=perf_counter();raw=one_cv(i);stages['generate']+=perf_counter()-t
            total_bytes+=len(raw)
            digest=hashlib.sha256(raw).hexdigest()
            if digest in hashes:raise ValueError('DUPLICATE_BINARY_DOCX')
            hashes.add(digest)
            with tempfile.NamedTemporaryFile(prefix='tr-v25-',suffix='.docx',delete=False) as tmp:
                tmp.write(raw);path=tmp.name
            try:
                t=perf_counter();mime=inspect_cv(path,'synthetic.docx');stages['validate']+=perf_counter()-t
                if mime!=DOCX_MIME:raise ValueError('INVALID_MIME')
                t=perf_counter();data=extract_docx(path);stages['extract']+=perf_counter()-t
            finally:
                os.unlink(path)
            pages+=len(data)
            concept=CONCEPTS[i%len(CONCEPTS)]
            aliases=[('skill-1',normalize(concept[0]),normalize(concept[0])),
                    ('skill-1',normalize(concept[1]),normalize(concept[0]))]
            t=perf_counter()
            detected=[m for page in data for m in extract_mentions(page.text,aliases)]
            facts +=sum(len(extract_source_facts(page.text)) for page in data)
            stages['nlp']+=perf_counter()-t
            mentions+=len(detected)
            evidences=[{'id':f'{i}-{j}','document_id':f'synth-{i}',
                        'page_number':1,'start_offset':m.start,'status':m.status,
                        'source_valid':True} for j,m in enumerate(detected)]
            t=perf_counter()
            score=calculate(req,DEFAULT_WEIGHTS,{'skill-1':evidences},mapped,
                  documents_ready=True,document_fingerprint=digest)
            stages['matching']+=perf_counter()-t
            if score.state=='documentary_coverage':match_complete+=1
        except Exception as e:
            fail_count+=1
            if len(fails)<20:fails.append({'index':i,'error_type':type(e).__name__,'code':str(e)[:120]})
        if i+1 in checkpoint_set:
            elapsed=perf_counter()-started
            snapshots.append({'documents':i+1,'seconds':round(elapsed,3),
                              'documents_per_second':round((i+1)/elapsed,2),
                              'failed_samples':fail_count,
                              'rss_megabytes':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024*1024 if sys.platform=='darwin' else 1024),1)})
            state={'kind':'offline_synthetic_docx_pipeline_only','documents_requested':count,'documents_processed':i+1,
              'error_samples':fails, 'failed_total':fail_count, 'successful_documents':i+1-fail_count,
              'total_input_bytes':total_bytes,'pages_extracted':pages,
              'lexical_mentions':mentions,'section_facts':facts,'matching_scores_computed':match_complete,
              'matching_calculations_attempted':i+1-fail_count,
              'review_required_or_incomplete':i+1-fail_count-match_complete,
              'checkpoint_measurements':snapshots,
              'stage_seconds':{k:round(v,3) for k,v in stages.items()},
              'date_utc':datetime.now(timezone.utc).isoformat(),
              'validated':False,'production_certified':False,
              'neural_inference_executed':False,'ocr_executed':False,
              'mysql_executed':False,'minio_executed':False,'celery_executed':False,
              'full_stack_3000_executed':False,
              'note':'Real docx parsing and local lexical analysis on synthetic inputs; NOT an API/Docker/OCR load test.'}
            report.parent.mkdir(parents=True,exist_ok=True)
            temp=report.with_suffix('.tmp');temp.write_text(json.dumps(state,ensure_ascii=False,indent=2));temp.replace(report)
    return state


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--count',type=int,default=3000)
    p.add_argument('--report',type=Path,required=True)
    args=p.parse_args()
    result=perform(args.count,args.report)
    print(json.dumps({'processed':result['documents_processed'],'checkpoints':result['checkpoint_measurements'],
                      'failures':len(result['error_samples']),'report':str(args.report)}))

if __name__=='__main__':main()
