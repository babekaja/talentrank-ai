"""Offline reproducible scientific baseline. No access to real CV records."""
import argparse,json
from pathlib import Path
from app.ml.africa_evaluation import run_benchmark

def main():
    parser=argparse.ArgumentParser(description='ProofLab v23 — synthetic benchmark only')
    parser.add_argument('--output',type=Path,default=None)
    args=parser.parse_args()
    result=run_benchmark()
    output=json.dumps(result,indent=2,ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(output+'\n',encoding='utf8')
    else:print(output)
if __name__=='__main__':main()
