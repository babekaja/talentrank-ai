"""Three-way, abstaining supervised experiment. NO persistence, NO production deployment.

Run locally: python -m scripts.train_evidence_triage dataset.jsonl --output results.json
Only aggregate evaluation + source-free metadata are written. No CV text in report.
"""
import argparse
import json
from pathlib import Path
from app.ml.annotation import load_gold
from app.ml.pair_classifier import train_experiment


def run(dataset: Path, output: Path | None = None, min_precision: float = 0.9):
    pairs, annotation_report = load_gold(dataset)
    _, report = train_experiment(pairs,min_precision=min_precision)
    result={'dataset_type':'SYNTHETIC_RESEARCH_ONLY' if '/synthetic/' in dataset.resolve().as_posix() else 'EXTERNALLY_ANNOTATED_UNVERIFIED',
            'annotation':annotation_report,'experiment':report,
            'important':'N’utiliser ces résultats ni pour rejeter, ni pour recruter automatiquement. Modèle non déployé.'}
    serialized=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)
    if output is not None:
        if output.resolve() == dataset.resolve():
            raise ValueError('CANNOT_OVERWRITE_ANNOTATIONS')
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(serialized+'\n',encoding='utf-8')
    print(serialized)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('dataset',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--min-precision',type=float,default=0.9)
    opts=parser.parse_args()
    run(opts.dataset,opts.output,opts.min_precision)
