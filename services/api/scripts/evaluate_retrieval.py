"""Research-only retrieval benchmark, source passages and expert relevance only."""
import argparse
import json
from pathlib import Path
from app.ml.retrieval_eval import RetrievalCase,evaluate_retrieval


def run(path: Path):
    payload=json.loads(path.read_text('utf-8'))
    corpus=[(row['id'],row['text']) for row in payload['passages']]
    queries=[RetrievalCase(row['id'],row['language'],row['requirement'],
                           frozenset(row['relevant_passage_ids'])) for row in payload['queries']]
    result=evaluate_retrieval(queries,corpus)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('dataset',type=Path)
    a=p.parse_args();run(a.dataset)
