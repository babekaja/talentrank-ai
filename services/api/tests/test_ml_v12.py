"""V12 offline research regression and safety tests; never require model downloads."""
from __future__ import annotations
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from app.ml.contrastive_v12 import (
    INPUT_DIM, OUTPUT_DIM, ContrastiveProjection, HashBaseline, _hashed,
    _partition, _triples, _evaluator, load_projection, save_projection,
    train_projection, run_contrastive_experiment,
)
from app.ml.hybrid_evaluation import read_benchmark
from app.ml.hybrid_retrieval import SourcePassage, retrieve_passages

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT/'datasets/synthetic/hybrid-retrieval-v10.json'
MANIFEST = ROOT/'datasets/synthetic/ranking-families-v11.json'


def fixture():
    docs, qs = read_benchmark(DATA)
    parts, meta = _partition(docs,qs,MANIFEST)
    return docs, qs, parts, meta


def test_hash_encoder_is_local_stateless_and_stable():
    a = _hashed(['Développement API REST', 'Built a Docker service'])
    b = _hashed(['Développement API REST', 'Built a Docker service'])
    assert a.shape == (2, INPUT_DIM)
    assert np.array_equal(a,b)
    assert np.allclose(np.linalg.norm(a, axis=1), 1)
    assert HashBaseline().encode(['API REST']).shape == (1, INPUT_DIM)


def test_hash_batch_validation():
    assert _hashed([]).shape == (0,INPUT_DIM)
    with pytest.raises(ValueError,match='INVALID_TEXT_BATCH'):
        _hashed(['a'*5001])
    with pytest.raises(ValueError,match='INVALID_TEXT_BATCH'):
        _hashed(['a']*2001)


def test_projection_rejects_wrong_shape_and_nan():
    with pytest.raises(ValueError,match='INVALID_CONTRASTIVE_WEIGHTS'):
        ContrastiveProjection(np.ones((10,10),dtype=np.float32))
    bad=np.zeros((INPUT_DIM,OUTPUT_DIM),dtype=np.float32)
    bad[0,0]=np.nan
    with pytest.raises(ValueError,match='INVALID_CONTRASTIVE_WEIGHTS'):
        ContrastiveProjection(bad)


def test_projection_is_immutable_after_construction():
    source=np.ones((INPUT_DIM,OUTPUT_DIM),dtype=np.float32)
    model=ContrastiveProjection(source)
    source[0,0]=9.0
    assert model.weights[0,0] == 1.0
    with pytest.raises(ValueError):
        model.weights[0,0]=9.0
    embeddings=model.encode(['Angular', 'No experience in Angular'])
    assert embeddings.shape == (2,OUTPUT_DIM)
    assert np.isfinite(embeddings).all()


def test_partition_embargo_all_labelled_docs_and_families():
    docs,qs,parts,info=fixture()
    assert (len(parts['train']),len(parts['calibration']),len(parts['test'])) == (9,3,3)
    assert info['embargoed_training_judgments'] == 6
    assert set(info['labelled_document_overlap'].values()) == {0}
    _,_,_,count=_triples(docs,parts['train'])
    assert count == 13


def test_cross_split_calibration_test_doc_leakage_rejected():
    docs,qs,parts,info=fixture()
    victim=parts['test'][0]
    calibration=parts['calibration'][0]
    # Make one test positive an explicit calibration positive: this must fail.
    modified=[replace(q,relevant_passage_ids=victim.relevant_passage_ids)
              if q.query_id == calibration.query_id else q for q in qs]
    with pytest.raises(ValueError,match='DOCUMENT_LABEL_LEAKAGE'):
        _partition(docs,modified,MANIFEST)


def test_only_explicit_hard_negatives_not_unjudged_texts():
    docs,qs,parts,info=fixture()
    q=parts['train'][0]
    indexed={p.passage_id:p for p in docs}
    _,_,_,count=_triples(docs,parts['train'])
    assert count == sum(len(query.relevant_passage_ids)*len(query.hard_negative_passage_ids)
                        for query in parts['train'])
    # A malicious addition of an unjudged source does NOT create a new training pair.
    unseen=SourcePassage('new-unjudged','fictional_tenant_a','synthetic_new_doc',1,0,
                          'Not labelled, so must not be assumed negative')
    _,_,_,again=_triples([*docs,unseen],parts['train'])
    assert again == count


def test_training_has_measured_gradient_learning_but_no_generalization_claim():
    docs,qs,parts,_=fixture()
    model,diag=train_projection(docs,parts['train'],parts['calibration'],epochs=20)
    assert diag['training_explicit_positive_negative_triples'] == 13
    assert diag['negative_labels_from_humans_only'] is True
    assert diag['training_loss_final'] < diag['training_loss_initial']
    assert diag['selected_epoch_from_calibration'] in {0,10,20}
    assert model.encode(['Angular']).shape==(1,OUTPUT_DIM)


def test_training_reproducible_across_repeated_runs():
    docs,qs,parts,_=fixture()
    a,meta_a=train_projection(docs,parts['train'],parts['calibration'],epochs=20)
    b,meta_b=train_projection(docs,parts['train'],parts['calibration'],epochs=20)
    assert np.array_equal(a.weights,b.weights)
    assert meta_a == meta_b


def test_invalid_training_config_rejected():
    docs,qs,parts,_=fixture()
    for opts in ({'epochs':9},{'epochs':201},{'epochs':15},
                 {'learning_rate':float('nan')},{'margin':0.0}):
        with pytest.raises(ValueError,match='INVALID_CONTRASTIVE_CONFIG'):
            train_projection(docs,parts['train'],parts['calibration'],**opts)


def test_retrieval_scopes_embedded_text_before_inference(monkeypatch):
    import app.ml.contrastive_v12 as c
    seen=[]
    genuine=c._hashed
    def trace(texts):
        seen.extend(texts)
        return genuine(texts)
    monkeypatch.setattr(c,'_hashed',trace)
    passage=[SourcePassage('one','tenant-a','doc-a',1,0,'Developed Angular service'),
             SourcePassage('two','tenant-b','doc-b',1,0,'SECRET_OTHER_TENANT'),
             SourcePassage('three','tenant-a','doc-c',1,0,'SECRET_UNAUTHORIZED_DOC')]
    out=retrieve_passages('Angular development',passage,organization_id='tenant-a',
                          authorized_documents=frozenset({'doc-a'}),
                          embedder=HashBaseline(),top_k=1)
    assert out['items'][0]['passage_id'] == 'one'
    assert 'SECRET_OTHER_TENANT' not in repr(seen)
    assert 'SECRET_UNAUTHORIZED_DOC' not in repr(seen)
    assert out['items'][0]['supports_requirement'] is None


def test_benchmark_runs_and_does_not_claim_a_skill(tmp_path):
    report=run_contrastive_experiment(DATA,MANIFEST,epochs=20,
                      output=tmp_path/'metrics.json',artifact=tmp_path/'projection.json')
    assert set(report['heldout_test']) == {'tfidf_char','bm25','hash_baseline','contrastive_hash'}
    assert report['test_queries'] == 3
    assert report['eligible_for_recruitment_inference'] is False
    assert report['is_pretrained_transformer'] is False
    assert report['calibration_strict_gain_over_hash_baseline'] is False
    assert report['heldout_test']['tfidf_char']['all']['mrr'] >= report['heldout_test']['contrastive_hash']['all']['mrr']
    report_text=(tmp_path/'metrics.json').read_text()
    artifact_text=(tmp_path/'projection.json').read_text()
    for text in ('SECRET_OTHER_TENANT', 'Oversaw inventory management', 'Developed an Angular',
                 'Sans expérience en', 'Job requirements:'):
        assert text not in report_text+artifact_text
    assert 'supports_requirement' not in artifact_text


def test_artifact_roundtrip_without_pickle_and_integrity(tmp_path):
    model=ContrastiveProjection(np.ones((INPUT_DIM,OUTPUT_DIM),dtype=np.float32)*.1)
    target=tmp_path/'projection.json'
    save_projection(target,model,dataset_sha='a'*64,manifest_sha='b'*64,selected_epoch=20)
    loaded=load_projection(target)
    assert np.allclose(model.weights,loaded.weights)
    assert 'Angular' not in target.read_text()
    corrupted=json.loads(target.read_text())
    corrupted['payload']['weights'][0][0]=999.0
    target.write_text(json.dumps(corrupted))
    with pytest.raises(ValueError,match='PROJECTION_INTEGRITY_MISMATCH'):
        load_projection(target)


def test_artifact_rejects_shape_and_untrusted_format(tmp_path):
    target=tmp_path/'data.pkl'
    target.write_bytes(b'cos\x80pickle')
    with pytest.raises(ValueError,match='INVALID_PROJECTION_ARTIFACT'):
        load_projection(target)
    bad=tmp_path/'bad.json'
    bad.write_text('{}')
    with pytest.raises(ValueError,match='INVALID_PROJECTION_ARTIFACT'):
        load_projection(bad)
    model=ContrastiveProjection(np.zeros((INPUT_DIM,OUTPUT_DIM),dtype=np.float32))
    with pytest.raises(ValueError,match='INVALID_PROJECTION_METADATA'):
        save_projection(tmp_path/'a.json',model,dataset_sha='bad',manifest_sha='b'*64,selected_epoch=20)


def test_experiment_is_deterministic_and_no_test_labels_in_training(monkeypatch):
    # If training accidentally receives test queries, abort before any gradient updates.
    import app.ml.contrastive_v12 as c
    original=c.train_projection
    docs,qs,parts,_=fixture()
    test_ids={q.query_id for q in parts['test']}
    def sentinel(passages, train, calibration, **kwargs):
        assert not test_ids & {q.query_id for q in train+calibration}
        return original(passages,train,calibration,**kwargs)
    monkeypatch.setattr(c,'train_projection',sentinel)
    r=c.run_contrastive_experiment(DATA,MANIFEST,epochs=20)
    assert r['test_queries'] == 3


def test_cli_produces_only_aggregated_metrics(tmp_path,capsys):
    from scripts.train_contrastive_v12 import run
    output=tmp_path/'results.json'
    run(DATA,manifest=MANIFEST,output=output,epochs=20)
    out=capsys.readouterr().out
    assert 'Oversaw inventory management' not in out
    assert 'Interested in an inventory management' not in output.read_text()
    assert json.loads(out)['research_only'] is True
