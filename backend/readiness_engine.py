"""R9.6 bounded, deterministic release-readiness checks. No network or mutations.
Evidence is an externally supplied, reviewed manifest—not a claim that checks ran.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

SCHEMA = 'decision-os/proof-manifest/v1'
CONTROLS = (
 ('identity', 'Identity & tenant boundary'),
 ('approval', 'Independent approval & atomic snapshot'),
 ('policy', 'Versioned policy evaluation'),
 ('ci', 'CI tests and pipeline results'),
 ('security', 'Security gate results'),
 ('deploy', 'Deployment and rollback evidence'),
 ('aiops', 'Post-deployment AIOps observations'),
 ('outcomes', 'Outcome observations with provenance'),
 ('finance', 'Independent finance reconciliation'),
 ('operator', 'Intervention draft and independent authorization'),
 ('verification', 'Measured intervention outcome'),
 ('replay', 'End-to-end audit replay'),
 ('anchoring', 'Independent signature or anchor verification'),
)
VALID_STATUSES = {'PASS','FAIL','NOT_TESTED','NOT_IMPLEMENTED'}

@dataclass(frozen=True)
class Finding:
    control: str
    title: str
    status: str
    reason: str
    evidence_ref: str | None
    verified_by: str | None


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def validate_manifest(manifest: dict) -> None:
    if not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA:
        raise ValueError('Unsupported manifest schema')
    if not isinstance(manifest.get('decision_id'), str) or not manifest['decision_id'].strip():
        raise ValueError('A nonempty decision_id is required')
    controls = manifest.get('controls')
    if not isinstance(controls, dict):
        raise ValueError('controls must be an object')
    unknown = set(controls) - {name for name, _ in CONTROLS}
    if unknown: raise ValueError('Unknown control keys: ' + ', '.join(sorted(unknown)))
    for name, payload in controls.items():
        if not isinstance(payload, dict): raise ValueError(f'{name} must be an object')
        if payload.get('status') not in VALID_STATUSES: raise ValueError(f'{name} has invalid status')
        if payload['status'] == 'PASS':
            # Self-report does not constitute verification. See findings below.
            if not isinstance(payload.get('evidence_ref'), str) or len(payload['evidence_ref'].strip()) < 8:
                raise ValueError(f'{name} PASS requires evidence_ref')
            if not isinstance(payload.get('verified_by'), str) or len(payload['verified_by'].strip()) < 3:
                raise ValueError(f'{name} PASS requires verified_by')


def evaluate(manifest: dict, *, authenticated_verifiers: set[str] | None = None, validated_evidence_refs: set[str] | None = None) -> dict:
    """A PASS is only eligible if the verifier was independently authenticated.

    authenticated_verifiers must come from trusted backend authorization, never from UI input.
    When absent, all submitted PASS values are withheld as NOT_TESTED.
    This does NOT verify the evidence contents; production must add source adapters.
    """
    validate_manifest(manifest)
    verifier_set = authenticated_verifiers or set()
    evidence_set = validated_evidence_refs or set()
    findings = []
    for key, title in CONTROLS:
        item = manifest['controls'].get(key, {})
        original = item.get('status', 'NOT_TESTED')
        verifier = item.get('verified_by')
        status = original if original != 'PASS' or (verifier in verifier_set and item.get('evidence_ref') in evidence_set) else 'NOT_TESTED'
        if original == 'PASS' and status != 'PASS':
            reason = 'Submitted PASS withheld: verifier identity or underlying evidence reference has not been independently verified by the server.'
        else:
            reason = str(item.get('reason') or ('Evidence provided; source validation is separately required.' if status == 'PASS' else 'No verified result recorded.'))[:500]
        findings.append(Finding(key, title, status, reason, item.get('evidence_ref'), verifier).__dict__)
    certified = all(row['status'] == 'PASS' for row in findings)
    summary = {state: sum(row['status'] == state for row in findings) for state in sorted(VALID_STATUSES)}
    report = {'schema':'decision-os/readiness-report/v1','decision_id':manifest['decision_id'],
              'certified':certified,'findings':findings,'summary':summary,
              'limitations':['Authentication of a reviewer is not validation of external source bytes.',
                             'Signed/WORM anchors and real integrations require separate live tests.',
                             'This report is advisory unless issued by the authoritative server.']}
    report['sha256'] = sha256(canonical(report)).hexdigest()
    return report


def from_trust_response(response: dict) -> dict:
    """Map actual R9.5 status into a candidate manifest without claiming PASS.
    The existing R9.5 API exposes consistency results, not authoritative verified evidence.
    """
    checks = response.get('checks', {}) if isinstance(response, dict) else {}
    controls = {}
    mapping = {'approval':'approval_time_atomic_business_record', 'ci':'production_devsecops_deployment',
               'aiops':'aiops_live_observation', 'finance':'independent_erp_gl_reconciliation',
               'operator':'governed_operator_execution_and_rollback',
               'replay':'end_to_end_replay', 'anchoring':'external_anchor_or_worm'}
    for name, original in mapping.items():
        raw = checks.get(original, 'NOT_TESTED')
        status = 'FAIL' if raw is False else 'NOT_IMPLEMENTED' if raw == 'NOT_IMPLEMENTED' else 'NOT_TESTED'
        controls[name] = {'status':status, 'reason':f'R9.5 upstream: {raw}'}
    return {'schema':SCHEMA,'decision_id':str(response.get('decision_id') or 'UNKNOWN'), 'controls':controls}


def sample_manifest(decision_id='DEMO-ONLY') -> dict:
    """An explicitly non-certifiable template. No invented passing evidence."""
    return {'schema':SCHEMA,'decision_id':decision_id, 'controls':{key:{'status':'NOT_TESTED','reason':'Not yet independently verified'} for key,_ in CONTROLS}}
