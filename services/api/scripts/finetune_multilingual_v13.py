"""Offline V13 neural SentenceTransformer fine-tune.  Does not deploy a model.

First run --dry-run (no model dependency) to validate annotation/split embargo.
Fine-tuning requires a local, already downloaded Sentence Transformer directory.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from app.ml.neural_finetune_v13 import TrainingConfig, research_run, select_device


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('dataset',type=Path)
    cli.add_argument('--manifest',type=Path,required=True)
    cli.add_argument('--local-model',type=Path)
    cli.add_argument('--dry-run',action='store_true')
    cli.add_argument('--output',type=Path)
    cli.add_argument('--checkpoint',type=Path)
    cli.add_argument('--epochs',type=int,default=3)
    cli.add_argument('--batch-size',type=int,default=4)
    cli.add_argument('--learning-rate',type=float,default=2e-5)
    cli.add_argument('--device',choices=('auto','cpu','mps','cuda'),default='cpu')
    args = cli.parse_args()
    if not args.dry_run and not args.local_model:
        cli.error('--local-model is required unless --dry-run is given')
    device = select_device(args.device)
    result = research_run(args.dataset,args.manifest,local_model=args.local_model,
            output=args.output,checkpoint=args.checkpoint,dry_run=args.dry_run,
            config=TrainingConfig(epochs=args.epochs,batch_size=args.batch_size,
                                  lr=args.learning_rate,device=device))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
