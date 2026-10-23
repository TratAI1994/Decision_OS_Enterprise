import ast
import importlib.util
from pathlib import Path

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('decision_academy',root/'ui'/'decision_academy.py')
module=importlib.util.module_from_spec(spec)
import sys

sys.modules[spec.name]=module
spec.loader.exec_module(module)

def test_all_sources_and_quizzes():
    assert len(module.LESSONS)==5
    assert len({x.slug for x in module.LESSONS})==5
    assert all(x.source_url.startswith('https://') and x.correct < len(x.alternatives) for x in module.LESSONS)
    assert all(module.skill_check(x.correct,x.correct) for x in module.LESSONS)

def test_playbook_does_not_invent_actuals():
    doc=module.playbook_markdown('Principal Product Manager','Claims Triage Copilot')
    assert 'Unknown until measured' in doc
    assert 'not a verified business case' in doc
    assert 'NIST' in doc

def test_ui_routing_and_compile():
    app=(root/'ui'/'app.py').read_text()
    assert "elif page=='Decision Academy':" in app
    assert "'Decision Academy'" in app
    ast.parse(app)
    ast.parse((root/'ui'/'decision_academy.py').read_text())

def test_case_scaffolds():
    for item in module.CASE_STUDIES.values():
        review=module.framework_review(item)
        assert review.facts and review.controls and review.next_decision
