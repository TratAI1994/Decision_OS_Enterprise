import importlib.util
from pathlib import Path

p=Path(__file__).parents[1]/'ui'/'decision_ledger.py'
spec=importlib.util.spec_from_file_location('decision_ledger_under_test',p)
m=importlib.util.module_from_spec(spec)
import sys

sys.modules[spec.name]=m
spec.loader.exec_module(m)

def test_digest_order_invariant():
    assert m.canonical_digest({'a':1,'b':2})==m.canonical_digest({'b':2,'a':1})

def test_digest_changes_on_mutation():
    assert m.canonical_digest({'status':'approved'})!=m.canonical_digest({'status':'draft'})

def test_version_increment():
    assert m.next_draft_version('v1.0')=='v1.1'

def test_version_rejects_invalid():
    import pytest
    with pytest.raises(ValueError):m.next_draft_version('junk')

def test_unreviewed_reference_never_verified():
    out=m.decision_graph_for_record({'title':'D','evidence':[{'status':'verified','claim':'Savings','source':'ERP'}]})
    assert out[0].evidence_status=='submitted'

def test_verified_requires_identity_source():
    out=m.decision_graph_for_record({'evidence':[{'status':'verified','source_id':'X','verified_by':'reviewer','claim':'C'}]})
    assert out[0].evidence_status=='verified'

def test_missing_is_zero_coverage():
    links=[m.EvidenceLink('a','claim','', 'ERP','missing')]
    assert m.evidence_coverage(links)==(0,1)

def test_unknown_response_does_not_generate_fake_evidence():
    assert m.decision_graph_for_record({'id':'1','title':'T'})==[]

def test_escape():
    assert '<script>' not in m._safe('<script>')

def test_api_result_normalization():
    assert m.normalize_items({'items':[{'id':'x'}]})==[{'id':'x'}]
