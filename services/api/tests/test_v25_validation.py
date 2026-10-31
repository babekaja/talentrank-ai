"""V25 annotation privacy, corpus and actual offline pipeline checks."""
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest
from scripts.build_review_corpus_v25 import build
from scripts.validate_dual_review_v25 import assess
from scripts.benchmark_offline_documents_v25 import perform, one_cv
from app.documents.validation import inspect_cv, DOCX_MIME
from app.documents.parsing import extract_docx


def make_review(path:Path, label='supports'):
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f));fields=rows[0].keys()
    for row in rows:row['reviewer_label']=label
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def test_40_real_synthetic_docs_2_blank_annotation_sheets():
    with TemporaryDirectory() as t:
        dest=Path(t)
        state=build(dest,count=40)
        assert state['cv_count']==40 and state['tasks']==80
        assert 'synthetic_engineering_corpus' in (dest/'MANIFEST-SYNTHETIC.json').read_text()
        assert 'reviewer_label' in (dest/'annotation-reviewer-A-BLANK.csv').read_text(encoding='utf-8-sig')
        assert (dest/'SYNTHETIC-CVs.zip').is_file()


def test_reviewer_files_reject_missing_human_labels():
    with TemporaryDirectory() as t:
        dest=Path(t);build(dest,count=20)
        a=dest/'annotation-reviewer-A-BLANK.csv';b=dest/'annotation-reviewer-B-BLANK.csv'
        with pytest.raises(ValueError,match='INCOMPLETE'):
            assess(a,b,reviewer_a='a',reviewer_b='b')


def test_reviewer_metrics_do_not_claim_independent_human_identity():
    with TemporaryDirectory() as t:
        dest=Path(t);build(dest,count=20)
        a=dest/'annotation-reviewer-A-BLANK.csv';b=dest/'annotation-reviewer-B-BLANK.csv'
        make_review(a,'supports');make_review(b,'supports')
        out=assess(a,b,reviewer_a='expert-1',reviewer_b='expert-2')
        assert out['agreement_rate']==1.0
        assert out['human_independence_certified'] is False
        assert out['requires_independent_identity_attestation']
        assert out['cohen_kappa'] is None  # Degenerate single label distribution


def test_reviewer_csv_mutation_detected():
    with TemporaryDirectory() as t:
        dest=Path(t);build(dest,count=20)
        a=dest/'annotation-reviewer-A-BLANK.csv';b=dest/'annotation-reviewer-B-BLANK.csv'
        make_review(a);make_review(b)
        s=b.read_text(encoding='utf-8-sig').replace('supports','PYTHON HACK',1)
        b.write_text(s,encoding='utf-8-sig')
        with pytest.raises(ValueError):assess(a,b,reviewer_a='a',reviewer_b='b')


def test_document_bytes_are_actual_docx_and_parse(tmp_path):
    raw=one_cv(11)
    target=tmp_path/'test.docx';target.write_bytes(raw)
    assert inspect_cv(str(target),'test.docx')==DOCX_MIME
    parts=extract_docx(str(target))
    assert len(parts)==1 and 'SYNTH-00011' in parts[0].text


def test_offline_end_to_end_5_docs(tmp_path):
    out=perform(5,tmp_path/'report.json')
    assert out['documents_processed']==5
    assert not out['error_samples']
    assert out['pages_extracted']==5
    assert out['lexical_mentions']>=5
    assert out['full_stack_3000_executed'] is False
    assert out['neural_inference_executed'] is False


def test_duplicate_reviewer_identity_rejected(tmp_path):
    build(tmp_path,count=20)
    with pytest.raises(ValueError,match='TWO_DISTINCT'):
        assess(tmp_path/'annotation-reviewer-A-BLANK.csv',tmp_path/'annotation-reviewer-B-BLANK.csv',reviewer_a='same',reviewer_b='same')
