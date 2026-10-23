"""Reusable UI-side validation. The API remains the authoritative validator."""
from __future__ import annotations

def errors_for_assessment(data:dict)->dict[str,str]:
    rules={'title':(3,'Enter an AI system name with at least 3 characters.'),
           'intended_use':(20,'Describe intended use, affected people and business process (minimum 20 characters).'),
           'owner':(2,'Enter an accountable risk owner (at least 2 characters).'),
           'geography':(2,'Enter the jurisdictions where the AI system will operate.'),
           'assessment_source':(3,'Provide an assessment source or technical document reference.')}
    issues={}
    for field,(minimum,message) in rules.items():
        value=data.get(field,'')
        if not isinstance(value,str) or len(value.strip())<minimum:issues[field]=message
    if not data.get('decision_id'):issues['decision_id']='Select an existing decision linked to the initiative.'
    return issues

def autofill_from_context(initiative:dict,decision:dict|None)->dict:
    # Deterministic context only. Do not invent affected populations or capabilities.
    name=str(initiative.get('name') or '')
    detail=str(initiative.get('description') or '').strip()
    rationale=str((decision or {}).get('rationale') or '').strip()
    intended=detail if len(detail)>=20 else rationale if len(rationale)>=20 else ''
    return {'title':name,'owner':str(initiative.get('owner') or ''),'intended_use':intended}

def regulatory_details_required(geography:str,system_type:str,role:str,intended_use:str)->bool:
    geo=geography.casefold()
    return (any(s in geo for s in ('eu','europe','eea','germany','france','italy','spain','netherlands','ireland'))
            or system_type in ('autonomous_agent','general_purpose','decision_support')
            or role in ('provider','deployer')
            or any(s in intended_use.casefold() for s in ('employment','recruitment','credit','health','biometric','education')))
