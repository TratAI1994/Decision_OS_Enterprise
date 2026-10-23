import importlib.util
import pathlib
import sys
import types

sys.modules.setdefault('streamlit',types.ModuleType('streamlit'))
spec=importlib.util.spec_from_file_location('decision_operations',pathlib.Path(__file__).resolve().parents[1]/'ui'/'decision_operations.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
from decimal import Decimal


def test_no_finance_attestation_no_realized_gap():
    f=m.parse_financial_evidence({'financial_lifecycle':{'projected_value':{'amount':100,'currency':'USD','period':'2026'},'realized_value':{'amount':30,'currency':'USD','period':'2026'}}})
    assert f.realized is None and m.financial_variance(f) is None

def test_verified_variance_and_currency_guard():
    x={'financial_lifecycle':{'projected_value':{'amount':100,'currency':'USD','period':'2026'},'realized_value':{'amount':30,'currency':'USD','period':'2026','verified_by':'finance1','verified_at':'2026-10-22','verification_reference':'GL-15'}}}
    assert m.financial_variance(m.parse_financial_evidence(x)) == Decimal(70)
    x['financial_lifecycle']['realized_value']['currency']='INR'
    assert m.financial_variance(m.parse_financial_evidence(x)) is None

def test_debt_only_explicit():
    r=m.debt_signals([{'id':'a','validation_status':'invalidated'}],[{'id':'k','status':'STALE'}],[{'id':'p','status':'draft'}])
    assert len(r)==3 and r[0]['severity']=='Critical'

def test_unknown_advisor_refuses():
    assert m.evidence_advisor('What happened to SAP profits?',[])['status']=='NO_EVIDENCE'
    assert m.evidence_advisor('Tell me a joke', [{'ref':'x','kind':'Review','label':'Review','reason':'Pending'}])['status']=='NO_EVIDENCE'

def test_packet_is_not_approved_or_executed():
    a=m.prepare_action_packet('How to recover?',[{'ref':'a','kind':'Assumption','label':'Revenue','reason':'invalidated'}],{'id':'d','title':'Decision'})
    assert a['approval_state']=='NOT_SUBMITTED' and a['execution_state']=='PROHIBITED'
    assert a['evidence_refs']==['a'] and len(a['alternatives'])==2

def test_requires_source():
    import pytest
    with pytest.raises(ValueError):m.prepare_action_packet('recover',[{'ref':'','label':'bad'}],{'id':'d'})

def test_navigation_and_tabs():
    root=pathlib.Path(__file__).resolve().parents[1]/'ui'
    app=(root/'app.py').read_text();eco=(root/'ecosystem_intelligence.py').read_text()
    assert "elif page=='Decision Operations':" in app
    assert "'Integration Connections','Evidence Advisor'" in eco
    assert "st.toggle('Plan connection'" in eco
