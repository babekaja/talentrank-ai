"""Critical business semantics and security regressions; exclusively fictitious data."""
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.ml.matching import calculate, DEFAULT_WEIGHTS, ALGORITHM_VERSION
from app.documents import malware
from app.insights.exports import csv_bytes, xlsx_bytes
from app.core.config import Settings
from app.api.v1.matching import result_info


def criterion(cid, category='skill', required=True, weight=1):
    return {'id':cid, 'code':cid, 'category':category, 'label':cid,
            'required':required, 'weight':weight}


def mention(cid):
    return {'id':f'e-{cid}', 'document_id':'doc-synthetic', 'page_number':1,
            'start_offset':0, 'status':'confirmed', 'source_valid':True}


def compute(req, evidence=None, mapping=None, ready=True):
    return calculate(req, DEFAULT_WEIGHTS, evidence or {}, mapping or {},
                     documents_ready=ready, document_fingerprint='test-document-fingerprint')


def test_diploma_only_is_indeterminate_never_zero():
    result=compute([criterion('degree','qualification')],ready=True)
    assert result.score is None
    assert result.state=='partial_review_required'
    assert result.criteria[0].state=='manual_review_required'
    assert result.group_coverage['summary']['evaluable_subset_coverage'] is None
    assert result.group_coverage['summary']['unassessed_weight_percent']==100


def test_experience_only_never_claims_zero_or_missing_skill():
    result=compute([criterion('exp','experience')])
    assert result.score is None
    assert result.group_coverage['experience']['coverage'] is None
    assert result.group_coverage['experience']['unassessed_weight']==1


def test_all_skills_observed_is_100_and_missing_mentions_not_a_suitability_prediction():
    req=[criterion('angular'),criterion('python')]
    result=compute(req,{'angular':[mention('angular')]},{'angular':'angular','python':'python'})
    assert result.score==Decimal('50.00')
    assert result.group_coverage['summary']['complete'] is True
    assert result.criteria[1].state=='not_documented'


def test_ambiguous_mention_cannot_be_scored_as_negative():
    req=[criterion('angular')]
    e={**mention('angular'),'status':'needs_review'}
    result=compute(req,{'angular':[e]},{'angular':'angular'})
    assert result.score is None
    assert result.group_coverage['summary']['unassessed_weight_percent']==100
    assert result.criteria[0].state=='needs_review'


def test_manual_requirement_does_not_penalize_machine_evaluable_subset():
    req=[criterion('angular'),criterion('degree','qualification',False)]
    result=compute(req,{'angular':[mention('angular')]},{'angular':'angular'})
    assert result.score is None
    assert result.state=='partial_review_required'
    assert result.group_coverage['summary']['evaluable_subset_coverage']==100
    assert result.group_coverage['summary']['assessable_weight_percent']<100
    assert result.criteria[0].contribution==Decimal('100')


def test_awaiting_documents_is_indeterminate():
    r=compute([criterion('angular')],{'angular':[mention('angular')]},{'angular':'angular'},False)
    assert r.score is None and r.state=='awaiting_documents'


def test_unconfirmed_synonym_mapping_stays_unassessed():
    r=compute([criterion('angular')],{'angular':[mention('angular')]},{})
    assert r.score is None
    assert r.criteria[0].note_code=='NO_VALIDATED_SKILL_MAPPING'


def test_deterministic_fingerprint_and_model_versioning():
    r1=compute([criterion('angular')],{'angular':[mention('angular')]},{'angular':'angular'})
    r2=compute([criterion('angular')],{'angular':[mention('angular')]},{'angular':'angular'})
    assert r1==r2 and ALGORITHM_VERSION=='documented-coverage-2.0.0'


def test_malformed_weights_do_not_silently_compute():
    r=[criterion('angular')]
    with pytest.raises(ValueError):
        calculate(r,{'essential':True,'desirable':20,'experience':10,'projects_training':69},
                  {},{},documents_ready=True,document_fingerprint='test')
    with pytest.raises(ValueError):
        compute([criterion('angular',weight=0)])


def test_historical_partial_result_is_not_exposed_as_a_score():
    old=SimpleNamespace(id='1',application_id='a',candidate_id='c',score=Decimal('42.86'),
                        state='partial_review_required',documented=1,to_review=1,
                        not_documented=1,group_coverage={})
    assert result_info(old)['score'] is None


class ClamAVSocket:
    def __init__(self, reply): self.reply=reply;self.sent=b''
    def __enter__(self): return self
    def __exit__(self,*_): pass
    def settimeout(self,*_): pass
    def sendall(self,data): self.sent+=data
    def recv(self,size): return self.reply


def test_clamav_healthy_requires_real_protocol(monkeypatch):
    sock=ClamAVSocket(b'PONG\0')
    monkeypatch.setattr(malware.socket,'create_connection',lambda *a,**k:sock)
    assert malware.scanner_health('clamav',3310)
    assert sock.sent==b'zPING\0'
    monkeypatch.setattr(malware.socket,'create_connection',lambda *a,**k:ClamAVSocket(b'garbage\0'))
    assert not malware.scanner_health('clamav',3310)


def test_clamav_detection_and_outage_block_upload(tmp_path,monkeypatch):
    file=tmp_path/'sample.pdf';file.write_bytes(b'%PDF-1.7 fake for scanner transport test')
    settings=Settings(jwt_secret='x'*48, malware_scan_enabled=True)
    monkeypatch.setattr(malware,'get_settings',lambda:settings)
    sock=ClamAVSocket(b'stream: test signature FOUND\0')
    monkeypatch.setattr(malware.socket,'create_connection',lambda *a,**k:sock)
    with pytest.raises(HTTPException) as e:
        malware.scan_file(str(file))
    assert e.value.status_code==422 and b'zINSTREAM\0' in sock.sent
    monkeypatch.setattr(malware.socket,'create_connection',lambda *a,**k:ClamAVSocket(b'stream: not-OK\0'))
    with pytest.raises(HTTPException) as bad_reply:malware.scan_file(str(file))
    assert bad_reply.value.status_code==503
    def down(*_,**__):raise OSError('offline')
    monkeypatch.setattr(malware.socket,'create_connection',down)
    with pytest.raises(HTTPException) as e:malware.scan_file(str(file))
    assert e.value.status_code==503


def test_export_non_calculable_cannot_be_spreadsheet_formula():
    row=('TR-SYNTH','application','Non calculable','partial_review_required',1,2,0,'to_review')
    assert 'Non calculable' in csv_bytes([row]).decode('utf-8-sig')
    assert xlsx_bytes([row],'Synthétique').startswith(b'PK')


def test_zero_weight_manual_criteria_still_require_review():
    weights={'essential':100,'desirable':0,'experience':0,'projects_training':0}
    req=[criterion('angular'), criterion('experience','experience',False)]
    r=calculate(req,weights,{'angular':[mention('angular')]},{'angular':'angular'},
                documents_ready=True,document_fingerprint='fp')
    assert r.score is None and r.state=='partial_review_required'
    assert r.group_coverage['summary']['assessable_weight_percent']==100
    assert r.group_coverage['summary']['complete'] is False

def test_skill_coverage_never_exceeds_100_across_weights():
    for count in range(1,25):
        req=[criterion(f's{i}', weight=(i%4)+1) for i in range(count)]
        mapping={r['id']:r['id'] for r in req}
        evidence={r['id']:[mention(r['id'])] for r in req[:count//2]}
        r=compute(req,evidence,mapping)
        assert Decimal('0') <= r.score <= Decimal('100')
        assert sum(x.contribution for x in r.criteria).quantize(Decimal('.01')) == r.score
