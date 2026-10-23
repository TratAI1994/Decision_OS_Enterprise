"""Regression: render() must resolve stage before calling _pipeline_graph.

Stops at graph rendering to assert the previously broken runtime path
without requiring a running Streamlit server.
"""
import importlib.util
import pathlib
import sys
import types
import pytest

sys.modules.setdefault('streamlit', types.ModuleType('streamlit'))
path = pathlib.Path(__file__).resolve().parents[1] / 'ui' / 'outcome_economics.py'
spec = importlib.util.spec_from_file_location('r9_render_regression', path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ReachedGraph(Exception):
    pass

class Expander:
    def __enter__(self): return self
    def __exit__(self, *args): return False

class FakeStreamlit:
    def __init__(self, initial):
        self.session_state = initial
        self.graph = None
    def __getattr__(self, name):
        if name == 'expander': return lambda *a, **kw: Expander()
        if name == 'selectbox': return lambda *a, **kw: 'Test decision · dec-1'
        if name == 'graphviz_chart': return self.capture
        return lambda *a, **kw: None
    def capture(self, graph, **kwargs):
        self.graph = graph
        raise ReachedGraph

@pytest.mark.parametrize('initial,expected', [({}, 'Overview'), ({'r8_stage': 'does not exist'}, 'Overview'), ({'r8_stage': '2 · Measure'}, '2 · Measure')])
def test_render_resolves_stage_before_graph(monkeypatch, initial, expected):
    fake = FakeStreamlit(initial)
    monkeypatch.setattr(mod, 'st', fake)
    seen = []
    def fake_graph(stage, count):
        seen.append((stage,count))
        return 'graph'
    monkeypatch.setattr(mod, '_pipeline_graph', fake_graph)
    def api(method, endpoint, quiet=False):
        if endpoint == '/v1/intelligence/decisions':
            return [{'id':'dec-1','title':'Test decision'}]
        return {'state':{'plan':None,'claims':[],'verifications':[]},'summary':{},'events':[],'integrity':{'consistent':True}}
    with pytest.raises(ReachedGraph):
        mod.render(api)
    assert seen == [(expected,0)]
    assert fake.graph == 'graph'
    if initial.get('r8_stage') == 'does not exist':
        assert fake.session_state['r8_stage'] == 'Overview'
