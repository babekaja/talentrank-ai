"""Deterministic CPU microbenchmark of the matching formula, NOT 3000 CV parsing.

Run: python -m scripts.benchmark_matching --sizes 100 500 1000 3000 --output /tmp/matching-benchmark.json
"""
import argparse
import json
import time
import tracemalloc
from pathlib import Path
from app.ml.matching import calculate, DEFAULT_WEIGHTS

REQUIREMENTS = [
    {'id':'r-angular','label':'Angular','category':'skill','required':True,'weight':3},
    {'id':'r-python','label':'Python','category':'skill','required':True,'weight':2},
    {'id':'r-docker','label':'Docker','category':'skill','required':False,'weight':1},
    {'id':'r-experience','label':'Expérience','category':'experience','required':False,'weight':1},
]
MAPPING={'r-angular':'angular','r-python':'python','r-docker':'docker'}


def run_batch(n:int):
    tracemalloc.start()
    started=time.perf_counter()
    completed=0
    diagnostic=0
    for index in range(n):
        evidences={}
        for skill,number in [('angular',2),('python',3),('docker',5)]:
            if index%number==0:
                evidences[skill]=[{'status':'mentioned','source_valid':True,
                                  'document_id':f'doc-{index}', 'page_number':1,
                                  'start_offset':0,'id':f'ev-{index}-{skill}'}]
        result=calculate(REQUIREMENTS,DEFAULT_WEIGHTS,evidences,MAPPING,
                         documents_ready=True,document_fingerprint=f'synthetic-{index}')
        completed += result.score is not None
        diagnostic += result.group_coverage['summary']['evaluable_subset_coverage'] is not None
    duration=time.perf_counter()-started
    _,peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {'items':n,'success':n,'complete_scores':completed,
            'diagnostic_subsets':diagnostic,'seconds':round(duration,4),
            'per_second':round(n/max(duration,0.00001),1),'peak_tracemalloc_bytes':peak}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sizes',nargs='+',type=int,default=[100,500,1000,3000])
    ap.add_argument('--output',type=Path,default=None)
    args=ap.parse_args()
    if any(x<1 or x>100000 for x in args.sizes):ap.error('sizes must be in [1, 100000]')
    result={'kind':'synthetic_matching_only',
            'disclaimer':'Only the pure scoring formula is timed; success means computed without exception, not a full score or CV ingestion. Experience requirements stay unassessed.',
            'results':[run_batch(n) for n in args.sizes]}
    raw=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(raw+'\n',encoding='utf-8')
    print(raw)

if __name__=='__main__':main()
