"""Offline adversarial passage ordering, model loaded from strict bounded JSON only."""
import argparse
import json
from pathlib import Path
from app.ml.pairwise_ranker import load_ranker
from app.ml.ranking_experiment import evaluate_adversarial_challenges


def run(dataset: Path, *, artifact: Path, output: Path | None = None) -> dict:
    result = evaluate_adversarial_challenges(dataset, load_ranker(artifact))
    if output is not None:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',type=Path)
    parser.add_argument('--artifact',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    run(args.dataset,artifact=args.artifact,output=args.output)
