"""Transparent, non-generative lexical evaluation on annotated JSONL.

The supplied synthetic examples are regression cases only; not ML validity.
Rows: {id,language,text,expected_codes}. No CVs included in this repository.
"""
import argparse
import json
from pathlib import Path
from app.ml.terminology import CURATED_SKILLS
from app.ml.recognition import extract_mentions, normalize


def run(dataset: Path):
    aliases=[(code,normalize(term),normalize(fr))
             for code,fr,_en,terms in CURATED_SKILLS for term in terms]
    totals = {'tp':0,'fp':0,'fn':0,'abstentions':0,'cases':0}
    by_language = {}
    rows=[]
    ids=set()
    for raw in dataset.read_text('utf-8').splitlines():
        if not raw.strip(): continue
        row=json.loads(raw)
        assert isinstance(row.get('text'),str) and row.get('language') in ('fr','en')
        assert isinstance(row.get('expected_codes'),list) and row.get('id') not in ids
        ids.add(row['id'])
        hits=extract_mentions(row['text'],aliases)
        found={h.skill_id for h in hits if h.status=='mentioned'}
        abstained={h.skill_id for h in hits if h.status=='needs_review'}
        expected=set(row['expected_codes'])
        tp=len(found & expected)
        fp=len(found - expected)
        fn=len(expected - found)
        counts=by_language.setdefault(row['language'],{'tp':0,'fp':0,'fn':0,'cases':0,'abstentions':0})
        for d in (totals, counts):
            d['tp'] += tp; d['fp'] += fp; d['fn'] += fn
            d['abstentions'] += len(abstained); d['cases'] += 1
        rows.append({'id':row['id'],'expected':sorted(expected),'detected':sorted(found),
                     'abstentions':sorted(abstained),'tp':tp,'fp':fp,'fn':fn})
    def statistics(x):
        tp,fp,fn=x['tp'],x['fp'],x['fn']
        precision=tp/(tp+fp) if tp+fp else 0
        recall=tp/(tp+fn) if tp+fn else 0
        f1=2*precision*recall/(precision+recall) if precision+recall else 0
        return {**x,'precision':round(precision,4),'recall':round(recall,4),'f1':round(f1,4)}
    result={'dataset_type':'CUSTOM_USER_ANNOTATED' if 'synthetic' not in dataset.parts else 'SYNTHETIC_REGRESSION_ONLY',
        'overall':statistics(totals),'by_language':{k:statistics(v) for k,v in by_language.items()},
        'details':rows, 'warning':'Scores descriptifs sur ce jeu; aucun benchmark clinique ou RH validé.'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result

if __name__=='__main__':
    cli=argparse.ArgumentParser()
    cli.add_argument('--dataset',type=Path,default=Path(__file__).resolve().parents[3] /
                     'datasets/synthetic/nlp-context-evaluation.jsonl')
    args=cli.parse_args()
    run(args.dataset)
