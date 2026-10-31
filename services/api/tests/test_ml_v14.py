"""Phase 14 tests: active-review safety + fail-closed experiment governance."""
from __future__ import annotations
from dataclasses import replace
import json
from pathlib import Path
import os
import pytest
import numpy as np

from app.ml.active_review_v14 import (select_review_items, generate_training_queue,
                                     write_private_queue, VERSION as QUEUE_VERSION)
from app.ml.release_audit_v14 import (audit_retrieval_model, write_audit,
                                       _paired_bootstrap_delta, VERSION as AUDIT_VERSION)
from app.ml.hybrid_evaluation import read_benchmark
from app.ml.ranking_experiment import read_family_manifest

ROOT=Path(__file__).resolve().parents[3]
DATA=ROOT/'datasets/synthetic/hybrid-retrieval-v10.json'
MANIFEST=ROOT/'datasets/synthetic/ranking-families-v11.json'


def fixture():
    p,q=read_benchmark(DATA)
    families,splits=read_family_manifest(MANIFEST,q)
    allowed=frozenset(x.query_id for x in q if splits[families[x.query_id]]=='train')
    return p,q,allowed


def test_review_queue_only_training_queries():
    p,q,allowed=fixture()
    result=generate_training_queue(DATA,MANIFEST,organization_id='fictional_tenant_a')
    assert result['frozen_split']=='train'
    assert result['no_auto_labels'] and result['eligible_for_rh_scoring'] is False
    assert all(item['query_id'] in allowed for item in result['items'])


def test_review_queue_only_unjudged_items_and_valid_source_offsets():
    p,q,allowed=fixture()
    queue=select_review_items(p,q,allowed_query_ids=allowed)
    index={x.passage_id:x for x in p}
    index_q={x.query_id:x for x in q}
    for i in queue['items']:
        query=index_q[i['query_id']]
        source=index[i['passage_id']]
        assert i['passage_id'] not in query.relevant_passage_ids|query.hard_negative_passage_ids
        assert source.organization_id==query.organization_id
        assert source.document_id in query.authorized_documents
        assert i['text_sha256']==source.text_sha256
        assert (i['start_offset'],i['end_offset'])==(source.start_offset,source.end_offset)
        assert i['human_label'] is None


def test_review_never_includes_any_raw_cv_passage():
    p,q,allowed=fixture()
    output=json.dumps(select_review_items(p,q,allowed_query_ids=allowed),ensure_ascii=False)
    assert all(src.text not in output for src in p if len(src.text)>=24)
    assert 'source_review_priority' in output
    assert 'two_independent_annotators_required' in output


def test_review_selection_is_deterministic_on_shuffled_passages():
    p,q,allowed=fixture()
    # BM25/TF-IDF ties resolve via passage ID, independent of input order.
    a=select_review_items(p,q,allowed_query_ids=allowed)
    b=select_review_items(list(reversed(p)),list(reversed(q)),allowed_query_ids=allowed)
    assert a==b


def test_review_rejects_broad_scope():
    p,q,allowed=fixture()
    with pytest.raises(ValueError,match='INVALID_ACTIVE_REVIEW_CONFIG'):
        select_review_items(p,q,allowed_query_ids=frozenset({'made_up'}))
    with pytest.raises(ValueError,match='INVALID_ACTIVE_REVIEW_CONFIG'):
        select_review_items(p,q,allowed_query_ids=allowed,per_query=0)
    with pytest.raises(ValueError,match='INVALID_ACTIVE_REVIEW_CONFIG'):
        select_review_items(p,q,allowed_query_ids=allowed,max_items=900)


def test_review_limited_output_size():
    p,q,allowed=fixture()
    result=select_review_items(p,q,allowed_query_ids=allowed,max_items=2)
    assert len(result['items'])==2
    assert result['item_count']==2


def test_review_does_not_score_unauthorized_text(monkeypatch):
    p,q,allowed=fixture()
    query=next(x for x in q if x.query_id in allowed)
    query_q=[query]
    outsider=next(x for x in p if x.organization_id!=query.organization_id)
    from app.ml import active_review_v14 as mod
    original=mod._tfidf_scores
    observed=[]
    def wrapper(req,texts):
        observed.extend(texts)
        return original(req,texts)
    monkeypatch.setattr(mod,'_tfidf_scores',wrapper)
    select_review_items(p,query_q,allowed_query_ids=frozenset({query.query_id}))
    assert outsider.text not in observed
    assert all(t in {x.text for x in p if x.organization_id==query.organization_id
                     and x.document_id in query.authorized_documents} for t in observed)


def test_review_queue_private_and_non_overwriting(tmp_path):
    target=tmp_path/'unlabelled.json'
    payload=generate_training_queue(DATA,MANIFEST,organization_id='fictional_tenant_a')
    write_private_queue(target,payload)
    assert target.is_file()
    assert os.stat(target).st_mode & 0o777==0o600
    assert json.loads(target.read_text())['version']==QUEUE_VERSION
    with pytest.raises(FileExistsError):
        write_private_queue(target,payload)


def test_invalid_review_payload_never_written(tmp_path):
    with pytest.raises(ValueError,match='INVALID_REVIEW_QUEUE'):
        write_private_queue(tmp_path/'bad.json',{'no_auto_labels':False,'version':QUEUE_VERSION})


def test_release_gate_fails_closed_on_tiny_synthetic_sample():
    report=audit_retrieval_model(DATA,MANIFEST)
    assert report['version']==AUDIT_VERSION
    assert report['research_only']
    assert not report['eligible_for_recruitment_inference']
    assert not report['research_metric_gate_passed']
    assert report['checks']['candidate_encoder_was_executed'] is False
    assert report['checks']['test_sample_size'] is False
    assert report['metrics']['test_queries'] < report['policy']['min_test_queries']


def test_release_audit_never_exports_raw_passages():
    result=audit_retrieval_model(DATA,MANIFEST)
    text=json.dumps(result,ensure_ascii=False)
    passages,_=read_benchmark(DATA)
    assert all(p.text not in text for p in passages if len(p.text)>=24)
    assert 'bootstrap' in text


class ShortEncoder:
    def __init__(self):
        self.observed=[]
    def encode(self,texts):
        self.observed.extend(texts)
        # Deliberately non-neural: tests the scoring contract only.
        return np.array([[float(len(t)%17+1),float(sum(map(ord,t))%31+1)] for t in texts])


def test_release_audit_with_encoder_remains_research_only():
    enc=ShortEncoder()
    result=audit_retrieval_model(DATA,MANIFEST,encoder=enc)
    assert result['checks']['candidate_encoder_was_executed']
    assert not result['eligible_for_recruitment_inference']
    assert not result['research_metric_gate_passed']
    assert result['metrics']['candidate_mrr']>=0


def test_release_encoder_cannot_read_cross_tenant_or_unauthorized_passages():
    enc=ShortEncoder()
    audit_retrieval_model(DATA,MANIFEST,encoder=enc)
    passages,queries=read_benchmark(DATA)
    families,splits=read_family_manifest(MANIFEST,queries)
    test_queries=[q for q in queries if splits[families[q.query_id]]=='test']
    visible={p.text for q in test_queries for p in passages
             if p.organization_id==q.organization_id and p.document_id in q.authorized_documents}
    assert set(enc.observed)<=visible|{q.requirement for q in test_queries}


def test_paired_bootstrap_is_reproducible_and_rejects_mismatch():
    one=_paired_bootstrap_delta([1.,.8,.7,.9],[.6,.7,.7,.4])
    assert one==_paired_bootstrap_delta([1.,.8,.7,.9],[.6,.7,.7,.4])
    assert one[0]<=one[1]
    with pytest.raises(ValueError,match='INVALID_PAIRED_METRICS'):
        _paired_bootstrap_delta([1.],[])


def test_private_report_does_not_overwrite(tmp_path):
    report=audit_retrieval_model(DATA,MANIFEST)
    path=tmp_path/'audit.json'
    write_audit(path,report)
    assert os.stat(path).st_mode & 0o777==0o600
    assert json.loads(path.read_text())['automatic_promotion'] is False
    with pytest.raises(FileExistsError):
        write_audit(path,report)


def test_queue_requires_explicit_tenant():
    with pytest.raises(ValueError,match='ORGANIZATION_SCOPE_REQUIRED'):
        generate_training_queue(DATA,MANIFEST,organization_id='')
    with pytest.raises(ValueError,match='INVALID_ACTIVE_REVIEW_CONFIG'):
        generate_training_queue(DATA,MANIFEST,organization_id='other_tenant')
