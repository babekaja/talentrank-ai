"""Phase 11 offline pairwise learning-to-rank: no HR scoring integration."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from app.ml.hybrid_evaluation import read_benchmark
from app.ml.hybrid_retrieval import SourcePassage, retrieve_passages
from app.ml.pairwise_ranker import (
    FEATURE_NAMES, LinearPassageReranker, pair_features,
    train_pairwise, save_ranker, load_ranker,
)
from app.ml.ranking_experiment import read_family_manifest, run_grouped_experiment

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'datasets/synthetic/hybrid-retrieval-v10.json'
MANIFEST = ROOT / 'datasets/synthetic/ranking-families-v11.json'


def test_features_are_bounded_fixed_and_french_english():
    a = pair_features('développement Angular', 'Développé une application Angular')
    b = pair_features('Angular development', 'Built an Angular application')
    assert len(a) == len(b) == len(FEATURE_NAMES)
    assert all(0 <= z <= 1 for z in a+b)
    assert a[FEATURE_NAMES.index('documented_action_cue')] == 1
    assert b[FEATURE_NAMES.index('documented_action_cue')] == 1


def test_negative_learning_and_job_ad_signals_are_not_evidence():
    for phrase, expected in [
        ('Sans expérience en Angular', 'negation_cue'),
        ('I want to learn Angular', 'learning_cue'),
        ('Job requirements: Angular development', 'job_requirement_cue'),
        ('If I knew Angular it would help', 'conditional_cue'),
    ]:
        data = dict(zip(FEATURE_NAMES, pair_features('Angular', phrase)))
        assert data[expected] == 1
    assert dict(zip(FEATURE_NAMES, pair_features('Angular', 'Built Angular application')))['documented_action_cue'] == 1


def test_bad_pair_inputs_rejected():
    for q, p in [('', 'Angular skill'), ('Angular', ''), ('Angular', 'p'*5001)]:
        with pytest.raises(ValueError, match='INVALID_PAIR_TEXT'):
            pair_features(q,p)


def test_training_is_deterministic_only_expert_labels():
    passages, qs = read_benchmark(DATA)
    family, splits = read_family_manifest(MANIFEST, qs)
    train = [q for q in qs if splits[family[q.query_id]] == 'train']
    model, diag = train_pairwise(passages, train)
    again, _ = train_pairwise(passages, train)
    assert model.coefficients == again.coefficients
    assert diag['judged_preference_pairs'] == sum(len(q.relevant_passage_ids)*len(q.hard_negative_passage_ids) for q in train)
    assert diag['unjudged_passages_as_negatives'] is False
    assert any(abs(w) > .01 for w in model.coefficients)
    with pytest.raises(ValueError, match='INVALID_REGULARIZATION'):
        train_pairwise(passages, train, regularization=0)
    with pytest.raises(ValueError, match='INSUFFICIENT_JUDGED_PAIRS'):
        train_pairwise(passages, train[:1])


def test_research_ranker_cannot_be_read_as_employment_probability():
    model = LinearPassageReranker((.2,) * len(FEATURE_NAMES))
    out = model.predict([('Angular','Developed Angular app')])
    assert len(out) == 1 and isinstance(out[0],float)
    with pytest.raises(ValueError, match='INVALID_RANKER_PARAMETERS'):
        LinearPassageReranker((float('nan'),) * len(FEATURE_NAMES))
    with pytest.raises(ValueError, match='RERANK_BATCH_TOO_LARGE'):
        model.predict([('Angular','A CV snippet')]*1001)


def test_group_manifest_is_frozen_and_complete(tmp_path):
    docs, qs = read_benchmark(DATA)
    families, splits = read_family_manifest(MANIFEST, qs)
    assert len(families) == len(qs)
    assert set(splits.values()) == {'train','calibration','test'}
    bad = json.loads(MANIFEST.read_text())
    del bad['families']['q01']
    p = tmp_path/'incomplete.json'
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match='INCOMPLETE_GROUP_MANIFEST'):
        read_family_manifest(p,qs)
    bad = json.loads(MANIFEST.read_text())
    bad['split_by_family']['angular']='unknown'
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match='INVALID_THREE_WAY_SPLIT'):
        read_family_manifest(p,qs)


def test_frozen_grouped_train_validation_test_and_labelled_doc_embargo(tmp_path):
    output = tmp_path/'aggregate.json'
    artifact = tmp_path/'weights.json'
    report = run_grouped_experiment(DATA,MANIFEST,output=output,artifact=artifact)
    assert (report['train_queries'],report['calibration_queries'],report['test_queries'])==(11,3,3)
    assert report['train_queries_retained_after_document_embargo'] == 9
    assert report['embargoed_training_judgments'] > 0
    assert set(report['judged_document_overlap_between_splits'].values()) == {0}
    assert set(report['heldout_test_results']) == {'bm25','tfidf_char','rrf_lexical','learned_pairwise'}
    assert report['threshold_or_competence_probability'] is None
    assert report['heldout_test_results']['tfidf_char']['all']['mrr'] > report['heldout_test_results']['learned_pairwise']['all']['mrr']
    assert all('document_id' not in r for r in report['heldout_test_results'])
    assert 'Job requirements:' not in output.read_text()
    assert 'Angular front-end development' not in output.read_text()
    assert 'supports_requirement' not in artifact.read_text()
    loaded = load_ranker(artifact)
    assert len(loaded.coefficients) == len(FEATURE_NAMES)
    assert 'weights' not in output.read_text()
    # Model has no access to candidate identity, personal contact or an HTTP endpoint.
    assert 'test_queries' in report


def test_research_experiment_reproducible(tmp_path):
    a = run_grouped_experiment(DATA, MANIFEST)
    b = run_grouped_experiment(DATA, MANIFEST)
    assert a == b


def test_no_untrusted_model_pickle_or_corrupt_json(tmp_path):
    model = LinearPassageReranker((.2,) * len(FEATURE_NAMES))
    path = tmp_path/'model.json'
    save_ranker(path, model, training_sha256='a'*64, split_sha256='b'*64,
                training_info={'judged_preference_pairs':24})
    assert load_ranker(path) == model
    tampered = json.loads(path.read_text())
    tampered['payload']['coefficients'][0] = 77777
    path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match='RANKER_INTEGRITY_MISMATCH'):
        load_ranker(path)
    with pytest.raises(ValueError, match='INVALID_TRAINING_DIGEST'):
        save_ranker(path,model,training_sha256='bad',split_sha256='b'*64,
                    training_info={})


def test_real_ranker_not_shown_private_text_before_sql_authorization():
    docs, qs=read_benchmark(DATA)
    model,_ = train_pairwise(docs,qs[:6])
    p1 = SourcePassage('okay', 'organization1', 'doc1', 1, 0, 'Developed Angular project')
    p2 = SourcePassage('secret', 'organization2', 'doc2', 1, 0, 'TOP SECRET Angular project')
    p3 = SourcePassage('private', 'organization1', 'doc3', 1, 0, 'PRIVATE PHONE +243999 Angular')
    output = retrieve_passages('Angular development',[p1,p2,p3],
         organization_id='organization1', authorized_documents=frozenset({'doc1'}),
         reranker=model, top_k=1, rerank_top_n=1)
    assert [x['passage_id'] for x in output['items']] == ['okay']
    assert output['items'][0]['supports_requirement'] is None
    assert 'TOP SECRET' not in json.dumps(output)
    assert 'PRIVATE PHONE' not in json.dumps(output)


def test_cli_is_research_only(tmp_path, capsys):
    from scripts.learn_to_rank_v11 import run
    out = tmp_path/'summary.json'
    artifact=tmp_path/'model.json'
    result=run(DATA,manifest=MANIFEST,output=out,artifact=artifact)
    assert result['research_only'] is True
    assert artifact.exists()
    assert 'SECRET' not in capsys.readouterr().out


def test_adversarial_challenge_only_reports_aggregate(tmp_path):
    from app.ml.ranking_experiment import evaluate_adversarial_challenges
    docs, qs = read_benchmark(DATA)
    model,_ = train_pairwise(docs,qs[:6])
    challenge = ROOT/'datasets/synthetic/ranking-challenges-v11.json'
    report = evaluate_adversarial_challenges(challenge,model)
    assert report['synthetic_pairs']==12
    assert sum(report['method_group_diagnostics']['learned_pairwise/all'].values())==12
    assert 'Angular components' not in str(report)
    assert 'MySQL administration' not in str(report)
    bad=tmp_path/'bad.json'
    bad.write_text(json.dumps({'dataset_type':'wrong','cases':[]}))
    with pytest.raises(ValueError,match='INVALID_CHALLENGE_FORMAT'):
        evaluate_adversarial_challenges(bad,model)


def test_challenge_cli_has_no_raw_data_in_result(tmp_path, capsys):
    from scripts.evaluate_challenges_v11 import run
    source = ROOT/'datasets/synthetic/ranking-challenges-v11.json'
    output=tmp_path/'metrics.json'
    artifact=tmp_path/'weights.json'
    run_grouped_experiment(DATA,MANIFEST,artifact=artifact)
    report=run(source,artifact=artifact,output=output)
    assert report['synthetic_pairs']==12
    assert 'Never worked' not in output.read_text()
    assert 'Developed Angular' not in capsys.readouterr().out
