"""Versioned advisory templates. They are not official provider certifications."""
from dataclasses import dataclass
from typing import Mapping

STEPS=('Assess','Strategize','Architect','Plan','Execute','Assure','Measure','Learn')
INDUSTRIES={
 'Pharma & Life Sciences':('GxP impact assessment','Model/data lineage','Independent quality oversight'),
 'Banking & Insurance':('Model risk assessment','Data rights and customer protection','Human decision oversight'),
 'Manufacturing':('Process safety','Quality and downtime baselines','Change approval'),
 'Retail & Supply Chain':('Demand and inventory baselines','Customer impact','Fulfillment trade-offs'),
 'Cross-industry':('AI inventory','Enterprise risk assessment','Value baseline')}
FRAMEWORKS={
 'AWS CAF':('Business','People','Governance','Platform','Security','Operations'),
 'Microsoft CAF':('Strategy','Plan','Ready','Adopt','Govern','Secure','Manage'),
 'Google Cloud Adoption':('Lead','Learn','Scale','Secure'),
 'Vendor neutral':('Strategy','Architecture','Execution','Risk','Value')}

@dataclass(frozen=True)
class Journey:
 industry:str;framework:str;objective:str
 def __post_init__(self):
  if self.industry not in INDUSTRIES:raise ValueError('unknown industry')
  if self.framework not in FRAMEWORKS:raise ValueError('unknown framework')
  if not 4<=len(self.objective.strip())<=300:raise ValueError('objective required')
 def checklist(self)->tuple[Mapping[str,object],...]:
  tasks={
   'Assess':('Document existing capabilities',*INDUSTRIES[self.industry]),
   'Strategize':('Rank use cases with human sponsor','Record baseline assumptions'),
   'Architect':('Compare solution options','Document data boundaries and threat model'),
   'Plan':('Approve funding and measurable OKRs','Assign accountable owners'),
   'Execute':('Record authenticated build/deployment evidence','Run security and quality gates'),
   'Assure':('Independent risk review','Preserve decision and evidence history'),
   'Measure':('Capture measurements separately from finance attestation','Record limitations in attribution'),
   'Learn':('Record qualified lessons','Human review before playbook changes')}
  return tuple({'step':s,'requirements':tasks[s],'human_gate':s in ('Strategize','Plan','Execute','Assure','Measure','Learn'),'status':'NOT_ASSESSED'} for s in STEPS)
