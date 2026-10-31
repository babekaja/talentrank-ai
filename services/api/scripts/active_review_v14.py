"""Prepare an authorized, private, UNLABELLED active review queue from train split."""
import argparse
import json
from pathlib import Path
from app.ml.active_review_v14 import generate_training_queue, write_private_queue


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('dataset',type=Path)
    cli.add_argument('--manifest',type=Path,required=True)
    cli.add_argument('--organization-id',required=True,help='Tenant whose training split may be queued')
    cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--per-query',type=int,default=3)
    cli.add_argument('--max-items',type=int,default=100)
    args=cli.parse_args()
    queue=generate_training_queue(args.dataset,args.manifest,
           organization_id=args.organization_id,per_query=args.per_query,max_items=args.max_items)
    write_private_queue(args.output,queue)
    print(json.dumps({'output':str(args.output),'items':queue['item_count'],
                      'state':'requires_two_independent_annotators'},ensure_ascii=False))

if __name__ == '__main__':
    main()
