"""Reproducible offline passage retrieval evidence; no claims of hiring ability."""
import hashlib
import json
import math
from pathlib import Path
from app.ml.hybrid_retrieval import bm25_scores, _tfidf_scores, fuse_rrf

DEFAULT_CORPUS=Path(__file__).resolve().parents[1]/'data'/'prooflab_synthetic.json'

def metrics(ranked: list[str], relevant: set[str], k: int=10)->dict:
    if not relevant: raise ValueError('Labels requis')
    subset=ranked[:k]
    hits=[i for i,key in enumerate(subset) if key in relevant]
    dcg=sum(1/math.log2(i+2) for i in hits)
    ideal=sum(1/math.log2(i+2) for i in range(min(k,len(relevant))))
    return {'hit_1':int(bool(ranked) and ranked[0] in relevant),
            'recall_10':len(hits)/len(relevant),
            'ndcg_10':dcg/ideal if ideal else 0.,
            'mrr_10':1/(hits[0]+1) if hits else 0.}

def benchmark(dataset:dict)->dict:
    texts={p['id']:p['text'] for p in dataset['passages']}
    per={}
    for q in dataset['queries']:
        allowed=set(q['authorized_documents'])
        pool=[p for p in dataset['passages'] if p['organization_id']==q['organization_id'] and p['document_id'] in allowed]
        if not pool:continue
        labels={p['id'] for p in pool}
        relevant=set(q['relevant_passage_ids']) & labels
        if not relevant:continue
        ids=[p['id'] for p in pool]
        bm=bm25_scores(q['requirement'],[texts[p] for p in ids]);tf=_tfidf_scores(q['requirement'],[texts[p] for p in ids])
        rankings={
            'bm25':sorted(ids,key=lambda i:(-bm[ids.index(i)],i)),
            'tfidf':sorted(ids,key=lambda i:(-tf[ids.index(i)],i)),
        }
        rankings['rrf']=[pid for pid,_ in fuse_rrf(rankings)]
        lang=q['language']
        if lang not in ('fr','en'):continue
        per.setdefault(lang,[]).append({m:metrics(rank,relevant) for m,rank in rankings.items()})
    def summarize(rows):
        if not rows:return None
        return {m:{metric:round(sum(row[m][metric] for row in rows)/len(rows),4) for metric in ('hit_1','recall_10','ndcg_10','mrr_10')}
                for m in ('bm25','tfidf','rrf')}
    allrows=[row for group in per.values() for row in group]
    if not allrows:raise ValueError('Aucun cas annoté exploitable')
    canonical=json.dumps(dataset,sort_keys=True,ensure_ascii=False).encode('utf8')
    return {'dataset_sha256':hashlib.sha256(canonical).hexdigest(),
            'scope':'fictional_passage_retrieval_only','model_type':'lexical_baselines_no_neural_inference',
            'queries':len(allrows),'by_language':{lang:{'queries':len(rows),'metrics':summarize(rows)} for lang,rows in sorted(per.items())},
            'overall':summarize(allrows),'validation_status':'synthetic_only_not_validated_for_recruitment',
            'limitations':['Jeu entièrement fictif et de petite taille.','Les labels ne sont pas des décisions d’embauche.',
                           'Un classement de passages ne prouve pas une compétence.','Aucun résultat n’autorise une décision RH automatique.']}

def run_benchmark(path:Path=DEFAULT_CORPUS):
    return benchmark(json.loads(path.read_text(encoding='utf8')))
