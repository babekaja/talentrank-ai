"""Fail-closed, non-deploying model-readiness audit over frozen annotated test data."""
import argparse
import json
from pathlib import Path
from app.ml.release_audit_v14 import audit_retrieval_model, write_audit


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('dataset',type=Path)
    cli.add_argument('--manifest',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--local-model',type=Path,help='Optional local Sentence Transformer; never downloaded')
    cli.add_argument('--strict',action='store_true',help='Exit with error if the research gate fails')
    args=cli.parse_args()
    encoder=None
    if args.local_model:
        from app.ml.neural_finetune_v13 import load_local_model, SafeEncoder
        model=load_local_model(args.local_model, device='cpu', max_length=192)
        encoder=SafeEncoder(model,batch_size=4)
    report=audit_retrieval_model(args.dataset,args.manifest,encoder=encoder)
    write_audit(args.output, report)
    print(json.dumps({'output':str(args.output),
                      'research_metric_gate_passed':report['research_metric_gate_passed'],
                      'failed_checks':[k for k,v in report['checks'].items() if not v]},ensure_ascii=False))
    if args.strict and not report['research_metric_gate_passed']:
        raise SystemExit(2)

if __name__ == '__main__':
    main()
