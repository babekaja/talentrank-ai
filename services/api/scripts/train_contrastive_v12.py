"""Offline CPU contrastive passage-retrieval experiment (no model downloads).

Run from services/api:
 python -m scripts.train_contrastive_v12 \\
  ../../datasets/synthetic/hybrid-retrieval-v10.json \\
  --manifest ../../datasets/synthetic/ranking-families-v11.json \\
  --output ../../docs/benchmarks/ml-v12-synthetic.json \\
  --artifact ../../docs/benchmarks/contrastive-v12.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from app.ml.contrastive_v12 import run_contrastive_experiment


def run(dataset: Path, *, manifest: Path, output: Path | None = None,
        artifact: Path | None = None, epochs: int = 60) -> dict:
    report = run_contrastive_experiment(dataset,manifest,output=output,artifact=artifact,epochs=epochs)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report

if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('dataset',type=Path)
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--artifact',type=Path)
    ap.add_argument('--epochs',type=int,default=60)
    args=ap.parse_args()
    run(args.dataset,manifest=args.manifest,output=args.output,artifact=args.artifact,epochs=args.epochs)
