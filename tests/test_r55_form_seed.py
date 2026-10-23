import ast
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import seed

def test_every_r55_form_submit_unlocked():
    tree=ast.parse((ROOT/'ui/app.py').read_text())
    targets={'Create Focus Area','Create Objective','Create outcome contract','Record measurement','Register assumption','Pre-register experiment','Evaluate against original threshold'}
    seen=set()
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='form_submit_button' and node.args and isinstance(node.args[0],ast.Constant):
            if node.args[0].value in targets:
                seen.add(node.args[0].value)
                assert not any(k.arg=='disabled' for k in node.keywords)
    assert seen==targets

def test_validations_preserved():
    contents=(ROOT/'ui/app.py').read_text()
    for phrase in ['len(name.strip())<5','len(title.strip())<5','not good','len(ref.strip())<3','len(statement.strip())<10','not enabled','len(source.strip())<3']:
        assert phrase in contents

class FakeClient:
    def __init__(self, decisions=()):
        self.store={'/v1/strategy/focus-areas':[],'/v1/strategy/objectives':[],'/v1/strategy/key-results':[],'/v1/strategy/assumptions':[],'/v1/strategy/experiments':[],'/v1/strategy/decision-links':[],'/v1/intelligence/decisions':list(decisions)}
        self.calls=[]
    def get(self,path):
        if path=='/v1/me':return {'role':'lead','tenant':'t1','user':'u1'}
        return self.store[path]
    def post(self,path,data):
        self.calls.append((path,data))
        row={'id':str(len(self.calls)),**data}
        self.store[path].append(row)
        return row

def test_dry_run_no_writes():
    c=FakeClient()
    seed.seed(c,False)
    assert c.calls==[]

def test_apply_repeat_safe_without_decision():
    c=FakeClient()
    seed.seed(c,True)
    first=len(c.calls)
    assert first==3
    seed.seed(c,True)
    assert len(c.calls)==first

def test_apply_repeat_safe_with_decision():
    c=FakeClient([{'id':'decision1','title':'Claims Triage Copilot'}])
    seed.seed(c,True)
    first=len(c.calls)
    assert first==6
    seed.seed(c,True)
    assert len(c.calls)==first
    assert all(path!='/v1/strategy/observations' for path,_ in c.calls)
