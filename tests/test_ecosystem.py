import importlib.util
import sys
import types
from pathlib import Path

import pytest

sys.modules.setdefault("streamlit", types.ModuleType("streamlit"))
p=Path(__file__).parents[1]/'ui'/'ecosystem_intelligence.py'
spec=importlib.util.spec_from_file_location('ecosystem_intelligence',p)
m=importlib.util.module_from_spec(spec)
import sys

sys.modules[spec.name]=m
spec.loader.exec_module(m)

def test_six_pillars():
    assert len(m.PROVIDERS)==6
    assert sum(x.group=='Infrastructure AI' for x in m.PROVIDERS)==3
    assert sum(x.group=='Business Platform AI' for x in m.PROVIDERS)==3

def test_evidence_for_each_vendor():
    assert all(len(m.required_checks(p.key))>=3 for p in m.PROVIDERS)
    with pytest.raises(ValueError):m.required_checks('unknown')

def test_invalid_form_is_not_false_success():
    with pytest.raises(ValueError):m.make_draft('x','a','short','azure','unassessed')
    d=m.make_draft('Claims Assistant','VP Ops','AI will help claims agents review complicated customer requests.','salesforce','unassessed')
    assert d['type']=='LOCAL_PREVIEW_NOT_SUBMITTED'
    assert d['preliminary_risk_tier']=='unassessed'
    assert len(d['proposed_controls'])>=3

def test_signals_are_deterministic_and_not_monetary():
    a=[{'id':'a','decision_id':'d','statement':'Adoption over 60%','validation_status':'invalidated'}]
    p=[{'id':'p','decision_id':'d','title':'Review expansion','status':'draft'}]
    found=m.risk_signals(a,[],p,decision_id='d')
    assert found[0]['type']=='Assumption'
    assert len(found)==2
    assert not any('loss' in str(v).lower() for row in found for v in row.values())
    assert m.risk_signals(a,[],p,decision_id='other')==[]

def test_missing_api_is_reported_not_healthy():
    def fake(method,path,quiet=False):
        if 'assumptions' in path:return None
        return []
    *rows,error=m.safe_source_bundle(fake)
    assert error and 'assumptions' in error
    assert len(rows)==4

def test_navigation_preserves_legacy():
    s=(Path(__file__).parents[1]/'ui'/'app.py').read_text()
    assert "elif page=='Ecosystem Intelligence':" in s
    assert "'Decision Quality & Assumption Engine'" in s
    assert "'Decision Academy'" in s
    assert "'AI Red Team Lab'" in s
