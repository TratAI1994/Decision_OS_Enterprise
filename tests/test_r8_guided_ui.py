"""No application server required: bounded copilot and workflow invariants."""
import importlib.util
import pathlib
import sys
import types

root=pathlib.Path(__file__).resolve().parents[1]
sys.modules.setdefault('streamlit',types.ModuleType('streamlit'))
spec=importlib.util.spec_from_file_location('r8_guided',root/'ui'/'outcome_economics.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def test_stages(): assert len(mod.STAGES)==5 and len(mod.HELP)==5

def test_missing_finance_var_withheld(): assert mod.progress({'period':'2026-12'},[{'id':'x'}],[])[0]==2

def test_finance_attested(): assert mod.progress({'period':'2026-12'},[{'id':'x'}],[{'id':'y'}])[0]==3

def test_plan_start(): assert mod.progress(None,[],[])[0]==0

def test_money_parsing():
    for valid in ['0','12000000.00','-30.50']:
        assert mod.validate_amount(valid) is None
    for bad in ['NaN','Infinity','1e10','12.345','1,000','']:
        assert mod.validate_amount(bad)

def test_no_causal_overclaim(): assert 'does not establish causality' in mod.explain('Overview','Does this prove causality?')

def test_identity_gate_answer(): assert 'FastAPI' in mod.explain('3 · Finance review','Who can approve?')

def test_gl_disclosure(): assert 'NOT automatically' in mod.explain('3 · Finance review','Does it validate GL automatically?')

def test_hash_disclosure(): assert 'privileged' in mod.explain('4 · Audit trail','Can a database admin tamper?')

def test_suggestion_scope():
    assert all(mod.HELP[s]['questions'] for s in mod.STAGES)
