"""Phase 10 ML passage retrieval: offline, tenant-scoped, source-linked, abstaining."""
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
import pytest

from app.ml.hybrid_retrieval import (SourcePassage,bm25_scores,fuse_rrf,
        check_source,retrieve_passages,RETRIEVAL_VERSION)
from app.ml.hybrid_evaluation import (read_benchmark,evaluate_hybrid,
        validate_benchmark,suggest_difficult_annotations)
from app.ml.confidence_gate import choose_research_threshold
from app.ml.local_rerank import _model_directory

DATA=Path(__file__).resolve().parents[3]/'datasets'/'synthetic'/'hybrid-retrieval-v10.json'


class FakeEmbedder:
    def __init__(self): self.calls=[]
    def encode(self, texts):
        self.calls.append(list(texts))
        return [[1.,0.] if 'Angular' in item or 'angular' in item else [0.,1.]
                for item in texts]


class FakeReranker:
    def __init__(self):self.calls=[]
    def predict(self, pairs):
        self.calls.append(list(pairs))
        return [3.0 if 'developed' in item.lower() else -1.0 for _,item in pairs]


def test_benchmark_data_are_fictional_and_split_by_tenant():
    passages,queries=read_benchmark(DATA)
    assert len(passages)==31 and len(queries)==17
    assert {'fr','en'} == {q.language for q in queries}
    assert any(p.organization_id=='fictional_tenant_b' for p in passages)
    assert all(q.relevant_passage_ids for q in queries)
    assert all(q.relevant_passage_ids.isdisjoint(q.hard_negative_passage_ids) for q in queries)


def test_bm25_and_rrf_deterministic_without_hidden_scaling():
    scores=bm25_scores('Angular',['Angular en production','J’aime la musique'])
    assert scores[0]>scores[1]
    result=fuse_rrf({'lex':['a','b'],'sem':['b','a']})
    assert result[0][1]==result[1][1]
    assert result[0][0]=='a'
    with pytest.raises(ValueError,match='DUPLICATED_RANKING_ITEM'):
        fuse_rrf({'x':['a','a']})


def test_tenant_filtering_occurs_before_embeddings_and_reranking():
    permitted=SourcePassage('pass1','tenantA','docA',1,0,'developed an Angular application')
    foreign=SourcePassage('pass2','tenantB','docB',1,0,'SECRET PRIVATE TEXT Angular')
    unauthorized=SourcePassage('pass3','tenantA','docC',1,0,'SECRET RESTRICTED Angular')
    embedder=FakeEmbedder(); reranker=FakeReranker()
    report=retrieve_passages('Angular frontend', [permitted,foreign,unauthorized],
        organization_id='tenantA',authorized_documents=frozenset({'docA'}),
        embedder=embedder,reranker=reranker,top_k=1,rerank_top_n=1)
    assert report['candidate_count']==1
    assert report['items'][0]['passage_id']=='pass1'
    assert all('SECRET' not in s for batch in embedder.calls for s in batch)
    assert all('SECRET' not in txt for batch in reranker.calls for _,txt in batch)
    assert 'SECRET' not in str(report)


def test_no_source_text_or_auto_credit_in_retrieval_output():
    p=SourcePassage('id','org','doc',2,12,'I want to learn Angular')
    result=retrieve_passages('Angular skill',[p],organization_id='org',
                             authorized_documents=frozenset({'doc'}))
    r=result['items'][0]
    assert r['status']=='unverified_passage_for_human_review'
    assert r['supports_requirement'] is None
    assert r['start_offset']==12 and r['end_offset']==12+len(p.text)
    assert len(r['text_sha256'])==64
    assert p.text not in json.dumps(result)
    assert result['pipeline']==RETRIEVAL_VERSION


def test_source_span_must_match_exact_extracted_page():
    p=SourcePassage('x','tenant','doc',2,5,'Angular')
    assert check_source('01234Angular.',p)
    assert not check_source('01234React.',p)
    assert not check_source('Angular',p)


def test_empty_organization_result_does_not_send_text_to_models():
    p=SourcePassage('x','org2','doc',1,0,'Private text')
    emb=FakeEmbedder()
    report=retrieve_passages('Angular',[p],organization_id='org1',
        authorized_documents=frozenset({'doc'}),embedder=emb)
    assert report['items']==[] and emb.calls==[]


def test_bad_inputs_fail_closed():
    p=SourcePassage('x','org','doc',1,0,'Angular')
    with pytest.raises(ValueError,match='INVALID_RETRIEVAL_SCOPE'):
        retrieve_passages('Angular',[p],organization_id='org',authorized_documents=frozenset())
    with pytest.raises(ValueError,match='INVALID_PASSAGE'):
        retrieve_passages('Angular',[p,p],organization_id='org',authorized_documents=frozenset({'doc'}))
    with pytest.raises(ValueError,match='INVALID_QUERY'):
        retrieve_passages('',[p],organization_id='org',authorized_documents=frozenset({'doc'}))


def test_invalid_dense_embeddings_rejected():
    p=SourcePassage('x','org','doc',1,0,'Angular')
    class Bad:
        def encode(self,x):return [[1.,0.],[float('nan'),0.]]
    with pytest.raises(ValueError,match='INVALID_EMBEDDING_VALUES'):
        retrieve_passages('Angular',[p],organization_id='org',
           authorized_documents=frozenset({'doc'}),embedder=Bad())


def test_optional_semantic_and_reranker_use_raw_ordering_not_probabilities():
    p1=SourcePassage('z','org','doc',1,0,'developed Angular application')
    p2=SourcePassage('a','org','doc',1,30,'want to learn Angular')
    result=retrieve_passages('Angular frontend',[p2,p1],organization_id='org',
       authorized_documents=frozenset({'doc'}),embedder=FakeEmbedder(),
       reranker=FakeReranker(),top_k=2,rerank_top_n=2)
    assert result['items'][0]['passage_id']=='z'
    assert result['items'][0]['reranker_raw_score']==3.0
    assert result['items'][0]['supports_requirement'] is None
    assert result['methods']==['bm25','tfidf_char','dense','cross_encoder']


def test_reject_rerank_length_or_nonfinite_scores():
    p=SourcePassage('x','org','doc',1,0,'Angular skill')
    class Short:
        def predict(self, pairs):return []
    class NonFinite:
        def predict(self, pairs):return [np.nan]
    for re, label in ((Short(),'INVALID_RERANK_COUNT'),(NonFinite(),'INVALID_RERANK_SCORE')):
        with pytest.raises(ValueError,match=label):
            retrieve_passages('Angular',[p],organization_id='org',
                authorized_documents=frozenset({'doc'}),embedder=FakeEmbedder(),
                reranker=re,rerank_top_n=1,top_k=1)


def test_reproducible_benchmark_without_actual_model_download():
    docs,queries=read_benchmark(DATA)
    a=evaluate_hybrid(docs,queries)
    b=evaluate_hybrid(docs,queries)
    assert a==b
    assert list(a['methods'])==['bm25','tfidf_char','hybrid_rrf']
    assert a['methods']['bm25']['all']['queries']==17
    assert 0 <= a['methods']['hybrid_rrf']['all']['mrr'] <= 1
    assert {'fr','en'}==set(a['methods']['hybrid_rrf']['by_language'])
    assert len(a['methods']['hybrid_rrf']['hit_at_1_bootstrap95'])==2
    assert 'J’ai' not in str(a) and 'SECRET' not in str(a)


def test_benchmark_with_fake_dense_and_cross_encoder():
    docs,queries=read_benchmark(DATA)
    report=evaluate_hybrid(docs,queries[:2],embedder=FakeEmbedder(),reranker=FakeReranker(),
                           k_values=(1,3))
    assert {'dense','hybrid_crossencoder'}<=report['methods'].keys()
    assert report['methods']['hybrid_crossencoder']['all']['queries']==2
    with pytest.raises(ValueError,match='INVALID_EVALUATION_CONFIG'):
        evaluate_hybrid(docs,queries[:2],reranker=FakeReranker())


def test_metrics_refuse_leaking_ground_truth_from_foreign_tenant():
    docs,queries=read_benchmark(DATA)
    wrong=replace(queries[0],relevant_passage_ids=frozenset({'foreign01'}))
    with pytest.raises(ValueError,match='INVALID_BENCHMARK_GROUND_TRUTH'):
        validate_benchmark(docs,[wrong])


def test_unknown_passages_are_never_automatically_labelled_negative():
    docs,queries=read_benchmark(DATA)
    proposals=suggest_difficult_annotations(docs,queries[:2],limit_per_query=2)
    assert len(proposals)==4
    assert all(x['suggested_label'] is None for x in proposals)
    assert all(x['status']=='requires_two_independent_annotators' for x in proposals)
    assert all(x['passage_id'] != 'foreign01' for x in proposals)


def test_wilson_bound_blocks_underpowered_ml():
    output=choose_research_threshold(['supports']*12,[.95]*12,min_selected=30)
    assert not output['enabled'] and output['threshold'] is None


def test_wilson_bound_accepts_only_when_enough_reviewed_positives():
    labels=['supports']*100+['insufficient']*25
    scores=[.99]*100+[.2]*25
    report=choose_research_threshold(labels,scores,min_selected=40,
                                     min_precision_lower_bound=.90)
    assert report['enabled'] and report['threshold']==.99
    assert report['precision_wilson95'][0]>.90
    bad=choose_research_threshold(['supports']*75+['insufficient']*25,
                    [.99]*100,min_selected=30,min_precision_lower_bound=.90)
    assert not bad['enabled']


def test_local_only_model_requires_already_existing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        _model_directory(str(tmp_path/'not-downloaded'))
    with pytest.raises(ValueError,match='INVALID_LOCAL_MODEL_DIRECTORY'):
        _model_directory(str(tmp_path))
    (tmp_path/'config.json').write_text('{}')
    assert _model_directory(str(tmp_path))==str(tmp_path)


def test_benchmark_cli_outputs_only_aggregate(tmp_path,capsys):
    from scripts.benchmark_hybrid_v10 import run
    out=tmp_path/'summary.json'
    result=run(DATA,output=out)
    assert result['total_queries']==17
    summary=out.read_text()
    assert 'J’ai développé' not in summary and 'CONTACT EXAMPLE RESTRICTED' not in summary
    with pytest.raises(ValueError,match='CROSSENCODER_REQUIRES_EMBEDDER'):
        run(DATA,crossencoder_dir='unused')


def test_v10_calibration_guard_does_not_leak_test_data(tmp_path,capsys):
    from scripts.evaluate_gate_v10 import run
    dataset=DATA.with_name('evidence-triage-annotations.jsonl')
    output=tmp_path/'guard.json'
    result=run(dataset,output=output)
    assert result['calibration_samples']==18 and result['test_samples']==18
    assert not result['v10_wilson_guard']['enabled']
    assert result['test_suggestions']==0 and result['test_abstentions']==18
    assert 'J’ai créé' not in output.read_text('utf-8')
    assert len(result['dataset_sha256'])==64


def test_no_model_auto_download_from_research_scripts(monkeypatch,tmp_path):
    from scripts.benchmark_hybrid_v10 import run
    def forbid_adapter(*args,**kwargs):
        raise AssertionError('No neural model should load by default')
    monkeypatch.setattr('app.ml.local_rerank.LocalEmbeddingAdapter',forbid_adapter)
    monkeypatch.setattr('app.ml.local_rerank.LocalCrossEncoderAdapter',forbid_adapter)
    report=run(DATA, output=tmp_path/'plain.json')
    assert report['config']['no_downloads_implicit']
    assert 'dense' not in report['methods']
