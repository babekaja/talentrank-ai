"""V13: real training-loop mechanics tested with a tiny *local* stand-in.
No pretrained model is claimed, fetched or distributed by these tests.
"""
from __future__ import annotations
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
import pytest
import torch
import torch.nn.functional as F

from app.ml.hybrid_evaluation import read_benchmark
from app.ml.hybrid_retrieval import SourcePassage
from app.ml.neural_finetune_v13 import (
    TrainingConfig, SafeEncoder, checkpoint_better, evaluate_encoder,
    explicit_triplets, prepare_experiment, require_local_model, research_run,
    select_device, train_neural,
)

ROOT=Path(__file__).resolve().parents[3]
DATA=ROOT/'datasets/synthetic/hybrid-retrieval-v10.json'
MANIFEST=ROOT/'datasets/synthetic/ranking-families-v11.json'


class TinyLocalStandIn(torch.nn.Module):
    """A trainable toy network testing loss/backprop, NOT a pretrained transformer."""
    def __init__(self):
        super().__init__()
        torch.manual_seed(3)
        self.linear=torch.nn.Linear(16,8,bias=False)
        self.max_seq_length=192
        self.seen=[]
    def tokenize(self,texts):
        self.seen += list(texts)
        def features(t):
            x=np.zeros(16,dtype=np.float32)
            for ch in t.casefold():
                x[ord(ch)%16] += 1
            return x/max(1,len(t))
        return {'features':torch.from_numpy(np.stack([features(t) for t in texts]))}
    def forward(self,inputs):
        return {'sentence_embedding':self.linear(inputs['features'])}
    def encode(self,texts,*,batch_size,normalize_embeddings,convert_to_numpy,show_progress_bar):
        with torch.no_grad():
            value=self(self.tokenize(texts))['sentence_embedding']
            return F.normalize(value,dim=1).detach().cpu().numpy()
    def save(self,destination):
        path=Path(destination)
        path.mkdir(parents=True,exist_ok=True)
        torch.save(self.state_dict(),path/'weights.pt')


def fixture():
    return prepare_experiment(DATA,MANIFEST)


def test_config_validation():
    TrainingConfig().validate()
    for options in ({'epochs':0},{'epochs':16},{'batch_size':0},
                    {'batch_size':17},{'max_length':20},{'margin':float('nan')},
                    {'lr':float('inf')},{'device':'remote'}):
        with pytest.raises(ValueError,match='INVALID_NEURAL_TRAINING_CONFIG'):
            TrainingConfig(**options).validate()


def test_synthetic_split_and_explicit_triplets():
    docs,groups,triplets,security=fixture()
    assert len(triplets)==13
    assert security['labelled_document_overlap']=={
        'train_calibration':0,'train_test':0,'calibration_test':0}
    assert len(groups['train'])==9
    assert all(len(t)==3 for t in triplets)


def test_triplets_only_judged_negatives():
    docs,groups,triplets,_=fixture()
    extra=SourcePassage('other','fictional_tenant_a','no_annotations',1,0,
                        'Undocumented, not automatically a hard negative')
    assert explicit_triplets([*docs,extra],groups['train']) == triplets


def test_unauthorized_document_in_training_annotation_rejected():
    docs,groups,_,_=fixture()
    base=groups['train'][0]
    altered=replace(base,authorized_documents=frozenset())
    with pytest.raises(ValueError,match='INVALID_TRAINING_EVIDENCE_SCOPE'):
        explicit_triplets(docs,[altered])


def test_duplicated_requirements_between_splits_rejected(tmp_path):
    obj=json.loads(DATA.read_text())
    manifest=json.loads(MANIFEST.read_text())['split_by_family']
    family=json.loads(MANIFEST.read_text())['families']
    a=next(q for q in obj['queries'] if manifest[family[q['id']]]=='train')
    b=next(q for q in obj['queries'] if manifest[family[q['id']]]=='test')
    b['requirement']=a['requirement']
    path=tmp_path/'leaky.json'
    path.write_text(json.dumps(obj),encoding='utf-8')
    with pytest.raises(ValueError,match='QUERY_TEXT_LEAKAGE'):
        prepare_experiment(path,MANIFEST)


def test_duplicate_evidence_text_across_document_splits_rejected(tmp_path):
    obj=json.loads(DATA.read_text())
    manifest_obj=json.loads(MANIFEST.read_text())
    by_id={p['id']:p for p in obj['passages']}
    train=next(q for q in obj['queries'] if
               manifest_obj['split_by_family'][manifest_obj['families'][q['id']]]=='train')
    test=next(q for q in obj['queries'] if
              manifest_obj['split_by_family'][manifest_obj['families'][q['id']]]=='test')
    train_pos=next(iter(train['relevant_passage_ids']))
    test_pos=next(iter(test['relevant_passage_ids']))
    by_id[test_pos]['text']=by_id[train_pos]['text']
    path=tmp_path/'duplicate-evidence.json'
    path.write_text(json.dumps(obj),encoding='utf-8')
    with pytest.raises(ValueError,match='PASSAGE_TEXT_LEAKAGE'):
        prepare_experiment(path,MANIFEST)


def test_safe_embedding_contract_checks_output():
    fake=TinyLocalStandIn()
    adapter=SafeEncoder(fake,batch_size=4)
    assert adapter.encode(['Anglais','French']).shape == (2,8)
    with pytest.raises(ValueError,match='INVALID_NEURAL_ENCODING_BATCH'):
        adapter.encode(['a'*5001])
    class Broken:
        def encode(self,*a,**kw):return np.array([[np.nan]])
    with pytest.raises(ValueError,match='INVALID_NEURAL_ENCODER_OUTPUT'):
        SafeEncoder(Broken(),batch_size=2).encode(['test'])


def test_tenant_filter_before_encoder_sees_content():
    passages=[SourcePassage('a','tenant_a','doc_a',1,0,'Positive Angular evidence'),
              SourcePassage('b','tenant_b','doc_b',1,0,'TENANT_B_PRIVATE'),
              SourcePassage('c','tenant_a','doc_c',1,0,'NOT_AUTHORIZED_TEXT')]
    from app.ml.hybrid_evaluation import QueryLabel
    query=QueryLabel('q','en','Angular','tenant_a',frozenset({'doc_a'}),
                     frozenset({'a'}),frozenset())
    encoder=TinyLocalStandIn()
    evaluate_encoder(passages,[query],SafeEncoder(encoder,batch_size=2))
    assert 'TENANT_B_PRIVATE' not in encoder.seen
    assert 'NOT_AUTHORIZED_TEXT' not in encoder.seen


def test_epoch_selection_prefers_mrr_then_negative_rate():
    a={'mrr':.8,'hard_negative_above_first_positive':.5}
    b={'mrr':.7,'hard_negative_above_first_positive':0.0}
    assert checkpoint_better(a,b,epoch=2,best_epoch=0)
    assert not checkpoint_better(b,a,epoch=2,best_epoch=0)
    assert not checkpoint_better(a,a,epoch=2,best_epoch=0)


def test_cpu_training_backward_and_checkpoint_replay():
    docs,groups,triplets,_=fixture()
    model=TinyLocalStandIn()
    checkpoint,history=train_neural(model,triplets,docs,groups['calibration'],
                      config=TrainingConfig(epochs=2,batch_size=4,lr=0.001))
    assert checkpoint['epoch'] in (0,1,2)
    assert len(history['epochs'])==3
    assert history['triplet_count']==13
    assert all(v['train_loss'] is not None for v in history['epochs'][1:])
    assert torch.isfinite(model.linear.weight).all()
    # Restored weights must yield the selected calibration result.
    actual=evaluate_encoder(docs,groups['calibration'],SafeEncoder(model,batch_size=4))['all']
    assert actual == checkpoint['calibration']


def test_training_reproducible_with_fixed_seed():
    docs,groups,triplets,_=fixture()
    a,b=TinyLocalStandIn(),TinyLocalStandIn()
    c1,h1=train_neural(a,triplets,docs,groups['calibration'],
                       config=TrainingConfig(epochs=2,batch_size=4,lr=0.001))
    c2,h2=train_neural(b,triplets,docs,groups['calibration'],
                       config=TrainingConfig(epochs=2,batch_size=4,lr=0.001))
    assert h1 == h2 and c1 == c2
    assert torch.equal(a.linear.weight,b.linear.weight)


def test_dry_run_is_local_and_reports_no_model_training(tmp_path):
    output=tmp_path/'research.json'
    report=research_run(DATA,MANIFEST,dry_run=True,output=output)
    assert report['pretrained_encoder_finetune'] is False
    assert report['eligible_for_recruitment_inference'] is False
    assert report['triplets']==13
    assert output.is_file()
    assert 'J’ai développé' not in output.read_text()


def test_no_silent_model_download(tmp_path):
    with pytest.raises(ValueError,match='LOCAL_SENTENCE_TRANSFORMER_REQUIRED'):
        require_local_model(tmp_path)
    (tmp_path/'modules.json').write_text('[]')
    assert require_local_model(tmp_path)==tmp_path.resolve()


def test_neural_e2e_stub_no_raw_text_written(tmp_path,monkeypatch):
    import app.ml.neural_finetune_v13 as mod
    monkeypatch.setattr(mod,'load_local_model',lambda *a,**kw:TinyLocalStandIn())
    (tmp_path/'modules.json').write_text('[]')
    report=research_run(DATA,MANIFEST,local_model=tmp_path,output=tmp_path/'report.json',
                        checkpoint=tmp_path/'private-model',
                        config=TrainingConfig(epochs=1,batch_size=4,lr=.001))
    assert report['status']=='trained_locally_evaluated_research_only'
    assert 'neural_selected' in report['heldout_test']
    assert report['selected']['epoch'] in (0,1)
    assert (tmp_path/'private-model'/'weights.pt').exists()
    assert 'Positive Angular evidence' not in (tmp_path/'report.json').read_text()
    with pytest.raises(FileExistsError):
        research_run(DATA,MANIFEST,local_model=tmp_path,output=tmp_path/'report.json',
                     config=TrainingConfig(epochs=1,lr=.001))


def test_auto_device_validates_and_cpu_available():
    assert select_device('cpu')=='cpu'
    assert select_device('auto') in ('cpu','mps','cuda')
    with pytest.raises(ValueError,match='INVALID_DEVICE'):
        select_device('cloud')
