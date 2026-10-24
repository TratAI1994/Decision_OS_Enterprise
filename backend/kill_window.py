"""R9.7 pure decision-window engine. Never treats submitted samples as trusted telemetry."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

OPERATORS = {'lt', 'lte', 'gt', 'gte'}
TRUSTED = 'SOURCE_VERIFIED'

@dataclass(frozen=True)
class Observation:
    observed_at: datetime
    value: Decimal
    source_ref: str
    verification: str = 'SUBMITTED_UNVERIFIED'
    source_identity: str = ''


def as_decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError('Metric must be numeric') from exc
    if not result.is_finite():
        raise ValueError('Metric must be finite')
    return result


def breaches(op: str, value: Decimal, threshold: Decimal) -> bool:
    if op not in OPERATORS:
        raise ValueError('Unknown comparison operator')
    return {'lt': lambda: value < threshold, 'lte': lambda: value <= threshold,
            'gt': lambda: value > threshold, 'gte': lambda: value >= threshold}[op]()


def evaluate_window(criterion: Mapping, observations: Sequence[Observation], *,
                    evaluated_at: datetime, verified_source_ids: frozenset[str] = frozenset()) -> dict:
    """Window proof uses verified, ordered samples covering start and end of entire interval.

    Never concludes continuous breach between point samples. Its result is a sampled-window
    candidate for reviewer scrutiny, not a kill-criterion trigger or execution permission.
    """
    if evaluated_at.tzinfo is None:
        raise ValueError('evaluated_at must be timezone aware')
    op = criterion.get('operator')
    if op not in OPERATORS:
        raise ValueError('Unsupported operator')
    days = criterion.get('window_days')
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError('window_days must be 1..365')
    threshold = as_decimal(criterion.get('threshold'))
    latest_allowed_hours = criterion.get('max_gap_hours', 24)
    if type(latest_allowed_hours) is not int or not 1 <= latest_allowed_hours <= 168:
        raise ValueError('max_gap_hours must be 1..168')
    time_end = evaluated_at.astimezone(timezone.utc)
    start = time_end - timedelta(days=days)
    if any(obs.observed_at.tzinfo is None for obs in observations):
        raise ValueError('Observed timestamp must be timezone aware')
    series = sorted(observations, key=lambda x: x.observed_at)
    proof = []
    for obs in series:
        if obs.observed_at.tzinfo is None:
            raise ValueError('Observed timestamp must be timezone aware')
        t = obs.observed_at.astimezone(timezone.utc)
        if start <= t <= time_end:
            proof.append((t, obs))
    result = {'metric':criterion.get('metric'), 'window_days':days,
              'sample_count':len(proof), 'status':'INSUFFICIENT_EVIDENCE',
              'candidate_only':True, 'continuous_condition_proven':False,
              'source_verified':False, 'reason':'Missing samples in assessment window'}
    if len(proof) < 2:
        return result
    if any(obs.verification != TRUSTED or not obs.source_identity or obs.source_identity not in verified_source_ids
           for _, obs in proof):
        return {**result, 'reason':'Unverified observation or source identity'}
    result['source_verified'] = True
    gap = timedelta(hours=latest_allowed_hours)
    if proof[0][0] - start > gap or time_end - proof[-1][0] > gap or any(
        proof[i+1][0] - proof[i][0] > gap for i in range(len(proof)-1)):
        return {**result, 'reason':'Sampling gaps or incomplete time coverage'}
    if all(breaches(op, obs.value, threshold) for _, obs in proof):
        return {**result, 'status':'SAMPLED_BREACH_REVIEW', 'reason':'All verified sampled observations breach; continuity and causality not established'}
    return {**result, 'status':'SAMPLED_WITHIN_OR_MIXED', 'reason':'At least one verified sample does not breach'}
