"""Train + evaluate a TEXT-FREE research artifact; never modify hiring scoring.

python -m scripts.learn_to_rank_v11 ../../datasets/synthetic/hybrid-retrieval-v10.json \\
 --manifest ../../datasets/synthetic/ranking-families-v11.json \\
 --output ../../docs/benchmarks/ml-v11-synthetic.json \\
 --artifact ../../docs/benchmarks/linear-ranker-v11.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from app.ml.ranking_experiment import run_grouped_experiment


def run(dataset: Path, *, manifest: Path, output: Path | None = None,
        artifact: Path | None = None) -> dict:
    result = run_grouped_experiment(dataset, manifest, output=output, artifact=artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--artifact', type=Path)
    args = parser.parse_args()
    run(args.dataset, manifest=args.manifest, output=args.output, artifact=args.artifact)
