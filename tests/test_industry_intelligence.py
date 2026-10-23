import importlib.util
import pathlib
import sys
import types
import unittest

sys.modules.setdefault('streamlit',types.ModuleType('streamlit'))
path=pathlib.Path(__file__).resolve().parents[1]/'ui'/'industry_intelligence.py'
spec=importlib.util.spec_from_file_location('industry_intelligence',path)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

class IndustryTests(unittest.TestCase):
    def test_all_industries_and_exact_vision(self):
        self.assertEqual(len(mod.INDUSTRIES),12)
        self.assertIn('quantify decision debt',mod.VISION)
        for industry in mod.INDUSTRIES.values():
            self.assertTrue(industry.kpis and industry.decisions and industry.evidence)
    def test_math_no_causal_claim(self):
        res=mod.calculate_gap(20,15)
        self.assertEqual(res['signed_gap'],'-5')
        self.assertEqual(res['gap_pct'],'-25.00')
        self.assertIn('no causal',res['caveat'])
        self.assertIsNone(mod.decimal_number('NaN'))
        self.assertEqual(mod.calculate_gap(None,8)['status'],'UNAVAILABLE')
    def test_deterministic_copilot_refuses_unsupported(self):
        industry=mod.INDUSTRIES['Retail']
        r=mod.decision_copilot_response('Give a verified margin gain and its cause',industry)
        self.assertEqual(r['kind'],'REFUSAL')
        self.assertEqual(mod.decision_copilot_response('Calculate 20% of 4500000',industry)['kind'],'CALCULATION')
        self.assertEqual(mod.decision_copilot_response('What evidence is missing?',industry)['kind'],'GUIDANCE')
    def test_simulation_reproducibility(self):
        a=mod.monte_carlo_scenario(0,2,8,15)
        self.assertEqual(a,mod.monte_carlo_scenario(0,2,8,15))
        self.assertLessEqual(a['p10'],a['p50'])
        with self.assertRaises(ValueError): mod.monte_carlo_scenario(0,10,5,20)
    def test_api_read_only_scoping(self):
        calls=[]
        def api(method,path,quiet=False):
            calls.append((method,path,quiet))
            return [{'id':'tenant-safe'}]
        data,warnings=mod.load_authorized(api)
        self.assertEqual(data,[{'id':'tenant-safe'}])
        self.assertEqual(calls,[('GET','/v1/intelligence/decisions',True)])
        self.assertFalse(warnings)
    def test_draft_never_claims_approved(self):
        ind=mod.INDUSTRIES['Manufacturing']
        d=mod.draft_industry_case(ind,ind.decisions[0],'VP Factory','Reduce line downtime with measured baselines',{})
        self.assertEqual(d['status'],'LOCAL_PREVIEW_NOT_SUBMITTED')
        self.assertIsNone(d['observed_outcomes'])
        self.assertIsNone(d['decision_quality_score'])
        self.assertFalse(d['finance_verified'])
        self.assertEqual(d['attribution'],'UNKNOWN')
        with self.assertRaises(ValueError): mod.draft_industry_case(ind,'Imaginary','VP Factory','Business objective over fifteen',{})
    def test_navigation_is_added_once(self):
        app=(pathlib.Path(__file__).resolve().parents[1]/'ui'/'app.py').read_text()
        self.assertIn("'Industry Transformation':['Industry Intelligence']",app)
        self.assertIn("elif page=='Industry Intelligence':",app)

if __name__=='__main__': unittest.main()
