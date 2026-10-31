"""Scientific retrieval benchmark: local pretrained encoders vs lexical baselines.

Requires independently annotated corpus. Never turns a retrieval rank into a hiring
probability or a verified skill. No network, no access to other tenants' documents.
"""
from __future__ import annotations
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import json
import math
import random
from statistics import mean
import numpy as np
from app.ml.hybrid_retrieval import bm25_scores, _tfidf_scores
from app.ml.africa_evaluation import metrics


def validate_corpus(data: dict) -> dict:
    passages = data.get('passages',[])
    queries = data.get('queries',[])
    if not passages or not queries or len(passages)>20000 or len(queries)>4000:
        raise ValueError('BOUNDED_CORPUS_REQUIRED')
    by_id = {}
    cross = defaultdict(set)
    owners = defaultdict(set)
    for p in passages:
        if p['id'] in by_id or not 2<=len(p['text'])<=5000:
            raise ValueError('DUPLICATE_OR_INVALID_PASSAGE')
        if p.get('split') not in ('train','validation','test'):
            raise ValueError('SPLIT_REQUIRED_ON_PASSAGES')
        by_id[p['id']]=p
        cross[p['document_id']].add(p['split'])
        owners[p['document_id']].add(p['organization_id'])
    if any(len(v)>1 for v in cross.values()):
        raise ValueError('DOCUMENT_SPLIT_LEAKAGE')
    if any(len(v)>1 for v in owners.values()):
        raise ValueError('DOCUMENT_TENANT_COLLISION')
    query_ids = set()
    family_splits = defaultdict(set)
    for q in queries:
        if q['id'] in query_ids:
            raise ValueError('DUPLICATE_QUERY')
        query_ids.add(q['id'])
        if q.get('split') not in ('train','validation','test') or q.get('language') not in ('fr','en'):
            raise ValueError('UNSUPPORTED_LANGUAGE_OR_SPLIT')
        family_splits[q.get('family_id',q['id'])].add(q['split'])
        if not 2<=len(q.get('requirement',''))<=5000:
            raise ValueError('INVALID_QUERY')
        if not len(q.get('annotator_ids',[]))>=2 or len(set(q['annotator_ids']))<2:
            raise ValueError('INDEPENDENT_ANNOTATION_REQUIRED')
        permitted = {p['id'] for p in passages if p['split']==q['split'] and
                     p['organization_id']==q['organization_id'] and
                     p['document_id'] in q['authorized_documents']}
        if not set(q.get('relevant_passage_ids',[])) or not set(q['relevant_passage_ids']) <= permitted:
            raise ValueError('ANNOTATION_OUTSIDE_AUTHORIZED_SCOPE')
    if any(len(v)>1 for v in family_splits.values()):
        raise ValueError('QUERY_FAMILY_SPLIT_LEAKAGE')
    # Exact text duplicates cannot appear across splits, even under different IDs.
    fingerprint_splits = defaultdict(set)
    for p in passages:
        fingerprint_splits[sha256(p['text'].strip().casefold().encode()).hexdigest()].add(p['split'])
    if any(len(v)>1 for v in fingerprint_splits.values()):
        raise ValueError('EXACT_PASSAGE_SPLIT_LEAKAGE')
    return {'documents':len(cross),'queries':len(queries),'test_queries':sum(q['split']=='test' for q in queries)}


def _rank(query:dict, permitted:list[dict], *, encoder=None, reranker=None) -> dict[str,list[str]]:
    texts=[p['text'] for p in permitted]
    ids=[p['id'] for p in permitted]
    scores={'bm25':bm25_scores(query['requirement'], texts),
            'tfidf':_tfidf_scores(query['requirement'],texts)}
    if encoder is not None:
        vectors=np.asarray(encoder.encode([query['requirement']]+texts),dtype=float)
        if vectors.shape[0] != len(ids)+1 or vectors.ndim!=2 or not np.isfinite(vectors).all():
            raise ValueError('INVALID_NEURAL_EMBEDDINGS')
        norms=np.linalg.norm(vectors,axis=1)
        safe=vectors / np.maximum(norms[:,None],1e-10)
        scores['neural']=(safe[1:] @ safe[0]).tolist()
    if reranker is not None:
        # Reranker considers at most 30 top passages based on TF-IDF + BM25
        # for predictable CPU/GPU memory; its ranking is among these top 30.
        candidates=sorted(range(len(ids)),key=lambda i:(-float(scores['tfidf'][i]+scores['bm25'][i]),ids[i]))[:30]
        pairs=[(query['requirement'],texts[i]) for i in candidates]
        ranks=np.asarray(reranker.predict(pairs),dtype=float).reshape(-1)
        if len(ranks)!=len(candidates) or not np.isfinite(ranks).all():
            raise ValueError('INVALID_RERANKER_OUTPUT')
        scores['reranker']={ids[idx]:float(score) for idx,score in zip(candidates,ranks)}
    output={}
    for method, values in scores.items():
        if method=='reranker':
            output[method]=sorted(values,key=lambda pid:(-values[pid],pid))
        else:
            if len(values)!=len(ids): raise ValueError('INVALID_SCORE_LENGTH')
            output[method]=[ids[i] for i in sorted(range(len(ids)),key=lambda i:(-float(values[i]),ids[i]))]
    return output


def ci95(values:list[float],seed:int=124,reps:int=500) -> list[float] | None:
    if len(values)<10:return None
    rng=random.Random(seed)
    measurements=[]
    for _ in range(reps):
        measurements.append(mean(values[rng.randrange(len(values))] for _ in values))
    measurements.sort()
    return [round(measurements[int(.025*reps)],4),round(measurements[int(.975*reps)],4)]


def benchmark(data:dict, *, encoder=None, reranker=None) -> dict:
    facts=validate_corpus(data)
    test=[q for q in data['queries'] if q['split']=='test']
    outputs=defaultdict(list)
    for q in test:
        permitted=[p for p in data['passages'] if p['split']=='test' and
                   p['organization_id']==q['organization_id'] and
                   p['document_id'] in q['authorized_documents']]
        for method, ranked in _rank(q,permitted,encoder=encoder,reranker=reranker).items():
            m=metrics(ranked,set(q['relevant_passage_ids']))
            outputs[(method,q['language'])].append(m)
    metrics_out={}
    for (method,lang), rows in sorted(outputs.items()):
        vals = [r['ndcg_10'] for r in rows]
        metrics_out.setdefault(method,{})[lang] = {
            'queries':len(rows),
            **{k:round(mean(r[k] for r in rows),4) for k in ('hit_1','recall_10','ndcg_10','mrr_10')},
            'ndcg_10_ci95':ci95(vals)}
    test_languages={lang:sum(q['language']==lang for q in test) for lang in ('fr','en')}
    # Gate for VALIDATION ONLY. Does not deploy or enable neural ranking.
    enough=facts['documents']>=300 and len(test)>=50 and all(n>=20 for n in test_languages.values())
    neural_ran=encoder is not None
    digest=sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'corpus_sha256':digest, 'corpus_metadata':facts,'test_languages':test_languages,
            'methods_executed':sorted(metrics_out), 'metrics':metrics_out,
            'neural_inference_executed':neural_ran,
            'scientific_readiness':'requires_independent_reviewer' if enough and neural_ran else 'insufficient_evidence',
            'deployment_enabled':False,
            'limitations':['Les extraits du jeu de données ne sont pas enregistrés dans le rapport.',
                           'La récupération d’un passage ne démontre pas sa valeur comme preuve professionnelle.',
                           'La validation nécessite aussi un audit humain, biais indirects et essais en infrastructure réelle.']}


def load_private_encoder(path:Path, *,device:str='cpu'):
    from app.ml.neural_finetune_v13 import require_local_model
    from sentence_transformers import SentenceTransformer
    root=require_local_model(path)
    return SentenceTransformer(str(root), device=device, local_files_only=True,trust_remote_code=False)


def load_private_reranker(path:Path, *,device:str='cpu'):
    from sentence_transformers import CrossEncoder
    root=path.expanduser().resolve(strict=True)
    # CrossEncoder uses a Hugging Face transformer directory, unlike
    # SentenceTransformer's modules.json structure.
    if (not root.is_dir() or not (root/'config.json').is_file() or
        not any((root/name).is_file() for name in ('model.safetensors','pytorch_model.bin'))):
        raise ValueError('LOCAL_CROSS_ENCODER_REQUIRED')
    return CrossEncoder(str(root), device=device,local_files_only=True,trust_remote_code=False)
