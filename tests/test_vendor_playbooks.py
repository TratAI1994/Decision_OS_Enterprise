import ast
from pathlib import Path

MODULE=Path(__file__).resolve().parents[1] / 'ui' / 'vendor_playbooks.py'
TREE=ast.parse(MODULE.read_text())
NODES={node.name:node for node in TREE.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))}

def get_pure_functions():
    import sys
    import types
    st=types.ModuleType('streamlit');sys.modules.setdefault('streamlit',st)
    from dataclasses import dataclass
    namespace={'dataclass':dataclass,'datetime':__import__('datetime').datetime,'timezone':__import__('datetime').timezone}
    selected=[node for node in TREE.body if (isinstance(node,ast.ClassDef) and node.name=='Gate') or (isinstance(node,ast.FunctionDef) and node.name in ('summarize','build_brief'))]
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(MODULE),'exec'),namespace)
    return namespace

def test_all_three_pages_exist_and_reference_sources():
    source=MODULE.read_text()
    for title in ('Microsoft Transformation','AWS Operational Readiness','Google Evaluation & Safety'):
        assert title in source
    for url in ('learn.microsoft.com','docs.aws.amazon.com','saif.google'):
        assert url in source

def test_coverage_never_claims_certification():
    ns=get_pure_functions();g=ns['Gate']('x','S','Question','Why','Evidence')
    assert ns['summarize']([g],{})=={'reviewed':0,'gaps':0,'awaiting':0,'unknown':1,'total':1}
    text=ns['build_brief']('Test',[g],{},'', '')
    assert 'SELF-ASSESSED DRAFT' in text and 'Not assessed' in text
    assert 'not an independent verification' in text

def test_disclosed_gaps_preserved():
    ns=get_pure_functions();g=ns['Gate']('x','S','Question','Why','Evidence')
    result=ns['summarize']([g],{'x':'Gap identified'})
    assert result['gaps']==1 and result['reviewed']==0

def test_nav_and_existing_routes_preserved():
    text=(MODULE.parents[1]/'ui'/'app.py').read_text()
    for route in ('Strategy-to-Outcomes Review','Decision Academy','Decision Action Center','Executive Decision Ledger','AI Red Team Lab'):
        assert route in text
    assert "from ui.vendor_playbooks import render_vendor_playbook" in text
