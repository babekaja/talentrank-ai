"""Run OFFLINE passage retrieval comparison; no applicant/CV data leaves machine.

From services/api:
  python -m scripts.benchmark_hybrid_v10 ../../datasets/synthetic/hybrid-retrieval-v10.json
  python -m scripts.benchmark_hybrid_v10 DATA --embedding-dir /preinstalled/local/model
  python -m scripts.benchmark_hybrid_v10 DATA --embedding-dir ... --crossencoder-dir ...
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from app.ml.hybrid_evaluation import read_benchmark,evaluate_hybrid


def run(path: Path, *, embedding_dir: str|None=None,
        crossencoder_dir: str|None=None, output: Path|None=None) -> dict:
    if crossencoder_dir and not embedding_dir:
        raise ValueError('CROSSENCODER_REQUIRES_EMBEDDER')
    docs,queries=read_benchmark(path)
    embedder=reranker=None
    if embedding_dir:
        from app.ml.local_rerank import LocalEmbeddingAdapter
        embedder=LocalEmbeddingAdapter(embedding_dir)
    if crossencoder_dir:
        from app.ml.local_rerank import LocalCrossEncoderAdapter
        reranker=LocalCrossEncoderAdapter(crossencoder_dir)
    report=evaluate_hybrid(docs,queries,embedder=embedder,reranker=reranker)
    report['config']={'embedding_model':'local_opt_in' if embedding_dir else None,
        'cross_encoder':'local_opt_in' if crossencoder_dir else None,
        'no_downloads_implicit':True,'no_person_level_outputs':True}
    if output is not None:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path)
    p.add_argument('--embedding-dir',type=str)
    p.add_argument('--crossencoder-dir',type=str)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    run(args.dataset,embedding_dir=args.embedding_dir,
        crossencoder_dir=args.crossencoder_dir,output=args.output)
