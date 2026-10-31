"""Run real local-model inference on independently annotated private passages.

Example: python -m scripts.neural_benchmark_v24 --corpus /private/annotated.json --local-encoder /models/multilingual --output /private/eval.json
Models must already be downloaded. No automatic network calls or public uploads.
"""
import argparse
import json
from pathlib import Path
from app.ml.neural_eval_v24 import benchmark, load_private_encoder, load_private_reranker

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--local-encoder',type=Path)
    parser.add_argument('--local-reranker',type=Path)
    parser.add_argument('--device',choices=('cpu','mps','cuda'),default='cpu')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.corpus.is_file():parser.error('Private corpus not found')
    data=json.loads(args.corpus.read_text(encoding='utf8'))
    # Fail validation before loading expensive models.
    from app.ml.neural_eval_v24 import validate_corpus
    validate_corpus(data)
    encoder=load_private_encoder(args.local_encoder,device=args.device) if args.local_encoder else None
    reranker=load_private_reranker(args.local_reranker,device=args.device) if args.local_reranker else None
    result=benchmark(data,encoder=encoder,reranker=reranker)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'report':str(args.output),'neural_inference_executed':result['neural_inference_executed'],
                      'scientific_readiness':result['scientific_readiness']},ensure_ascii=False))

if __name__=='__main__':main()
