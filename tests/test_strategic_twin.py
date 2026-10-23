import ast
from pathlib import Path
from datetime import datetime, timezone, timedelta
import sys, types, importlib.util

p=Path(__file__).resolve().parents[1]/'ui'/'strategic_twin.py'
# Module import is safe without streamlit installed; scoring must not depend on it.
sys.modules.setdefault('streamlit',types.ModuleType('streamlit'))
spec=importlib.util.spec_from_file_location('strategic_twin',p)
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

def test_blast_radius_no_causal_claim():
    found=m.blast_radius('azure',m.DEMO_NODES,m.DEMO_EDGES)
    assert len(found)==4
    assert max(x['depth'] for x in found)==3
    assert all(x['status']=='dependency hypothesis' for x in found)

def test_graph_cycle_safe():
    e=m.DEMO_EDGES+(m.Dependency('margin','azure','cyclic'),)
    assert len(m.blast_radius('azure',m.DEMO_NODES,e))==4

def test_invalid_node():
    assert m.blast_radius('not_found',m.DEMO_NODES,m.DEMO_EDGES)==[]

def test_scenario_reproducible():
    a=m.simulate_shadow(50,80,48,82,15,1000,42)
    b=m.simulate_shadow(50,80,48,82,15,1000,42)
    assert a==b and a['modeled_delta']==4
    assert a['p10'] <= a['p50'] <= a['p90']

def test_scenario_rejects_negative():
    import pytest
    with pytest.raises(ValueError):m.compare_alternatives(-5,1,2,3)

def test_unverified_signal():
    sig=m.Signal('Cost',datetime.now(timezone.utc),128,'USD','',False)
    assert m.evaluate_signal(sig,120,7)['status']=='UNVERIFIED'

def test_stale_overrides_breach():
    now=datetime.now(timezone.utc)
    sig=m.Signal('Cost',now-timedelta(days=31),128,'USD','ledger:12',True)
    assert m.evaluate_signal(sig,120,7,now)['status']=='STALE'

def test_breach_requires_review_not_invalidation():
    now=datetime.now(timezone.utc)
    sig=m.Signal('Cost',now,128,'USD','ledger:12',True)
    assert m.evaluate_signal(sig,120,7,now)['status']=='REVIEW REQUIRED'

def test_autonomy_blocks_broadening():
    r=m.autonomy_gate('change_budget',{'prepare_review'},True,True,True)
    assert not r['permitted'] and 'outside approved scope' in r['blockers'][0]

def test_policy_recheck_required():
    r=m.autonomy_gate('prepare_review',{'prepare_review'},True,True,False)
    assert not r['permitted']

def test_draft_not_executable():
    p=m.proposal_packet('example',[],{})
    assert 'NOT EXECUTABLE' in p['status']
    assert p['human_review_required'] is True
    assert len(p['draft_sha256'])==64

def test_navigation_and_clean_source():
    s=(p.parents[1]/'ui'/'app.py').read_text()
    assert "'Strategic Twin Studio'" in s
    assert "from ui.strategic_twin import render" in s
    assert 'st.form_submit_button(' not in p.read_text()
