import importlib.util, sys, types, pathlib
sys.modules.setdefault('streamlit',types.ModuleType('streamlit'))
spec=importlib.util.spec_from_file_location('r9',str(pathlib.Path(__file__).resolve().parents[1]/'ui'/'outcome_economics.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_progress_and_separation():
    assert m.progress(None,[],[])[0]==0
    assert m.progress({'expected':1},[],[])[0]==1
    assert m.progress({'expected':1},[{}],[])[0]==2
    assert m.progress({'expected':1},[{}],[{}])[0]==3

def test_missing_prerequisites_not_trusted():
    data=m.workflow_readiness(None,[],[],{})
    assert data['Approval-time snapshot']=='Not verified'
    assert data['Preapproved kill criteria']=='Not verified'
    assert data['Event integrity']=='Not verified'
    assert data['ERP/GL source authentication']=='Not independently verified'

def test_event_chain_status_requires_explicit_true():
    assert m.workflow_readiness(None,[],[],{'consistent':False})['Event integrity']=='Not verified'
    assert m.workflow_readiness(None,[],[],{'consistent':True})['Event integrity']=='Locally consistent'

def test_finance_attestation_does_not_imply_erp_proof():
    data=m.workflow_readiness({},[{}],[{}],{'consistent':True})
    assert data['Finance review']=='Attested'
    assert data['ERP/GL source authentication']=='Not independently verified'

def test_financial_input_validation():
    assert m.validate_amount('1000.00') is None
    for bad in ('1e6','NaN','Infinity','100.123','<script>','99999999999999999'):
        assert m.validate_amount(bad) is not None

def test_contextual_advisor_does_not_claim_causality():
    answer=m.explain('3 · Finance review','Did AI cause the savings?')
    assert 'does not establish causality' in answer

def test_stages_and_navigation_exist():
    src=pathlib.Path(m.__file__).read_text()
    assert '_workflow_navigation(stage,count)' in src
    assert 'st.session_state[\'r8_stage\']' in src
    assert 'r9-rail' in src

def test_source_html_escaped_in_workflow_card():
    import inspect
    assert 'html.escape(label)' in inspect.getsource(m._workflow_card)
