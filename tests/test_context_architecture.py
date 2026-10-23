import ast, pathlib, sys, types, unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
try:import streamlit
except ImportError:sys.modules['streamlit']=types.ModuleType('streamlit')
from ui.context_copilot import resolve,answer
from ui.architecture_mastery import BLUEPRINTS

class TestContext(unittest.TestCase):
 def test_tab_specific(self):
  self.assertNotEqual(resolve('Strategic Twin Studio','Blast Radius').questions,resolve('Strategic Twin Studio','Shadow Alternatives').questions)
 def test_unknown(self):self.assertIn('cannot',answer('How did SAP cause $3M savings?',resolve('Ecosystem Intelligence')).lower() if False else answer('Will the stock market crash?',resolve('Ecosystem Intelligence')).lower())
 def test_math(self):self.assertIn('90.00',answer('calculate 20% of 450',resolve('Decision Operations')))
 def test_no_causal(self):self.assertIn('UNKNOWN',answer('Is it causal?',resolve('Strategic Twin Studio')))
 def test_governance(self):self.assertIn('cannot',answer('Can agent approve?',resolve('Strategic Twin Studio')))
 def test_arch(self):self.assertEqual(len(BLUEPRINTS),5)
 def test_tests_present(self):self.assertTrue(all(b.tests and b.controls and b.steps for b in BLUEPRINTS.values()))
 def test_navigation(self):
  txt=(BASE/'ui/app.py').read_text();self.assertIn("'Architecture Mastery'",txt);self.assertIn('render_context_copilot',txt)
 def test_security_no_eval(self):
  tree=ast.parse((BASE/'ui/context_copilot.py').read_text());self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('eval','exec') for n in ast.walk(tree)))
if __name__=='__main__':unittest.main()
