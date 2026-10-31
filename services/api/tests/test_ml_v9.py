"""Phase 9 research ML: split isolation, corroboration, abstention, retrieval."""
from pathlib import Path
from dataclasses import replace
import copy
import json
import numpy as np
import pytest

from app.ml.annotation import LABELS, load_gold, compile_gold, cohen_kappa
from app.ml.pair_classifier import (class_metrics, select_threshold,
       train_experiment, evaluate_selective, wilson_interval)
from app.ml.retrieval_eval import (rank_passages, evaluate_retrieval,
       RetrievalCase, propose_hard_negative_reviews)
from app.ml.robustness import Contrast,evaluate_contrasts

DATA=Path(__file__).resolve().parents[3] / 'datasets' / 'synthetic'


def read_raw():
    return [json.loads(s) for s in (DATA/'evidence-triage-annotations.jsonl').read_text('utf-8').splitlines() if s]


def test_annotation_integrity_and_corroboration():
    gold,report=load_gold(DATA/'evidence-triage-annotations.jsonl')
    assert len(gold)==72
    assert report['disagreements']==1
    assert report['cohen_kappa'] is not None
    assert {p.split for p in gold}=={'train','calibration','test'}
    assert {p.label for p in gold}==set(LABELS)
    assert {p.language for p in gold}=={'fr','en'}
    assert all(p.end_offset-p.start_offset==len(p.evidence) for p in gold)
    assert len(report['dataset_sha256'])==64


def test_missing_adjudication_blocked():
    rows=read_raw()
    candidate=next(r for r in rows if r.get('adjudication'))
    del candidate['adjudication']
    with pytest.raises(ValueError,match='ADJUDICATION_REQUIRED'):
        compile_gold(rows)


def test_same_reviewer_cannot_self_certify():
    rows=read_raw();rows[0]['reviews'][1]['reviewer']=rows[0]['reviews'][0]['reviewer']
    with pytest.raises(ValueError,match='INDEPENDENT'):
        compile_gold(rows)


def test_source_span_integrity_and_source_hash():
    rows=read_raw()
    rows[0]['evidence']+=' falsifié'
    with pytest.raises(ValueError,match='INVALID_SOURCE_PROVENANCE'):
        compile_gold(rows)


def test_group_or_template_cross_split_leakage_blocked():
    rows=read_raw()
    rows[-1]['candidate_group']=rows[0]['candidate_group']
    with pytest.raises(ValueError,match='CANDIDATE_OR_DOCUMENT_LEAKAGE'):
        compile_gold(rows)
    rows=read_raw()
    rows[-1]['template_group']=rows[0]['template_group']
    with pytest.raises(ValueError,match='TEMPLATE_FAMILY_LEAKAGE'):
        compile_gold(rows)


def test_duplicate_text_cross_split_blocked():
    rows=read_raw(); rows[-1]['requirement']=rows[0]['requirement']
    rows[-1]['evidence']=rows[0]['evidence']
    import hashlib
    rows[-1]['evidence_sha256']=hashlib.sha256(rows[-1]['evidence'].encode()).hexdigest()
    rows[-1]['end_offset']=len(rows[-1]['evidence'])
    with pytest.raises(ValueError,match='DUPLICATED_TEXT_LEAKAGE'):
        compile_gold(rows)


def test_train_validate_test_heldout():
    gold,_=load_gold(DATA/'evidence-triage-annotations.jsonl')
    estimator,report=train_experiment(gold,min_precision=.90)
    assert report['training_samples']==36
    assert report['calibration_samples']==18
    assert report['test_samples']==18
    assert report['train_only_fit']
    assert {'fr','en'} <= set(report['test']['by_language'])
    assert 0<=report['test']['classification']['macro_f1']<=1
    assert {'features','classifier'} <= set(estimator.named_steps)
    assert 'suggestion_precision_wilson95' in report['test']['selective']


def test_training_fails_if_three_class_or_split_missing():
    gold,_=load_gold(DATA/'evidence-triage-annotations.jsonl')
    with pytest.raises(ValueError,match='INSUFFICIENT_THREE_WAY_SPLIT'):
        train_experiment([g for g in gold if g.split!='test'])
    changed=[replace(g,label='supports') if g.split=='test' else g for g in gold]
    with pytest.raises(ValueError,match='THREE_CLASSES'):
        train_experiment(changed)
    changed=list(gold)
    changed[-1]=replace(changed[-1],candidate_group=gold[0].candidate_group)
    with pytest.raises(ValueError,match='GROUP_SPLIT_LEAKAGE'):
        train_experiment(changed)


def test_calibration_only_threshold_and_precision_requirement():
    classes=('supports','related','insufficient')
    cal=np.array([[.9,.05,.05],[.8,.1,.1],[.75,.1,.15], [.1,.8,.1]])
    truth=['supports','supports','related','related']
    cutoff=select_threshold(truth,cal,classes,min_precision=1.0)
    assert cutoff['selected'] and cutoff['support_threshold']==.8
    cutoff2=select_threshold(truth,cal,classes,min_precision=1.0,min_positive_predictions=3)
    assert not cutoff2['selected']
    with pytest.raises(ValueError,match='NON_FINITE_SCORES'):
        select_threshold(truth,[[float('nan'),0,0]]+cal.tolist()[1:],classes)


def test_unselected_always_abstains():
    gold,_=load_gold(DATA/'evidence-triage-annotations.jsonl')
    rows=gold[:2]
    result=evaluate_selective(rows,[[.99,.005,.005],[.98,.01,.01]],list(LABELS),None)
    assert result['suggestions']==0 and result['abstentions']==2
    assert result['suggestion_precision'] is None
    assert wilson_interval(2,2)[0] < 1
    assert wilson_interval(0,0) is None


def test_retrieval_and_hard_negative_proposals():
    data=json.loads((DATA/'evidence-retrieval-benchmark.json').read_text())
    corpus=[(x['id'],x['text']) for x in data['passages']]
    queries=[RetrievalCase(x['id'],x['language'],x['requirement'],
                           frozenset(x['relevant_passage_ids'])) for x in data['queries']]
    result=evaluate_retrieval(queries,corpus,(1,3))
    assert 0<=result['all']['mrr']<=1
    assert 0<=result['all']['recall_at_3']<=1
    assert len(rank_passages('Angular',corpus,limit=2))==2
    proposals=propose_hard_negative_reviews(queries,corpus,limit_per_query=2)
    assert proposals and all(p['label'] is None for p in proposals)
    assert all(p['state']=='needs_expert_annotation' for p in proposals)
    assert all(not(p['passage_id'] in next(q.relevant_passage_ids for q in queries if q.query_id==p['query_id']))
               for p in proposals)
    with pytest.raises(ValueError,match='INVALID_GROUND_TRUTH'):
        evaluate_retrieval([RetrievalCase('x','fr','Angular',frozenset({'missing'}))],corpus)


class FakeInvariantModel:
    classes_=np.array(LABELS)
    def predict_proba(self,phrases):
        return np.array([[.6,.2,.2] for _ in phrases])


def test_controlled_counterfactual_metrics_no_traces():
    c=Contrast('Angular','J’ai développé une application Angular. Je suis Alex.',
               'J’ai développé une application Angular. Je suis Sam.', 'synthetic_name')
    report=evaluate_contrasts(FakeInvariantModel(),[c])
    assert report['max_score_change']==0 and report['decision_flips_at_0_5']==0
    assert 'Alex' not in str(report)
    with pytest.raises(ValueError,match='INVALID_CONTRASTS'):
        evaluate_contrasts(FakeInvariantModel(),[replace(c,changed_evidence=c.original_evidence)])


def test_persist_report_contains_aggregates_not_evidence(tmp_path):
    from scripts.train_evidence_triage import run
    path=tmp_path/'result.json'
    result=run(DATA/'evidence-triage-annotations.jsonl',path)
    report=path.read_text('utf-8')
    assert 'source_hash' not in report and 'J’ai créé des composants' not in report
    assert result['annotation']['pairs']==72


def test_research_inference_abstains_without_calibration():
    from app.ml.pair_classifier import propose_pair_review
    class FailIfUsed:
        def predict_proba(self, _):
            raise AssertionError('uncalibrated ML must not run')
    result=propose_pair_review(FailIfUsed(),{'selected':False},'Angular','Code Angular sur projet')
    assert result['status']=='human_review'
    with pytest.raises(ValueError,match='INVALID_PAIR_INPUT'):
        propose_pair_review(FailIfUsed(),{'selected':False},'', '')


def test_research_inference_gated_to_review_only():
    from app.ml.pair_classifier import propose_pair_review
    class StubModel:
        classes_=list(LABELS)
        def predict_proba(self, samples):
            assert len(samples)==1
            return np.array([[0.99,0.005,0.005]])
    proposal=propose_pair_review(StubModel(),{'selected':True,'support_threshold':.92},
                                'Angular','J’ai créé une application Angular.')
    assert proposal['status']=='supports_suggestion_to_review'
    assert 'candidate' not in proposal and 'employability' not in proposal


def test_probability_reliability_diagnostics():
    from app.ml.pair_classifier import probability_diagnostics
    scores=np.array([[.9,.08,.02],[.15,.75,.10],[.12,.18,.70]])
    labels=list(LABELS)
    result=probability_diagnostics(labels,scores,labels)
    assert result['multiclass_brier']>=0
    assert 0<=result['expected_calibration_error']<=1
    with pytest.raises(ValueError,match='INVALID_PROBABILITIES'):
        probability_diagnostics(labels,[[float('nan'),.0,.0]]+scores[1:].tolist(),labels)


def test_verify_document_source_span_without_paraphrase():
    from app.ml.annotation import verify_source_span
    pairs,_=load_gold(DATA/'evidence-triage-annotations.jsonl')
    first=pairs[0]
    assert verify_source_span(first.evidence,first)
    assert not verify_source_span('Texte différent du passage',first)
    assert not verify_source_span(first.evidence+' (modifié)',replace(first,start_offset=8))
