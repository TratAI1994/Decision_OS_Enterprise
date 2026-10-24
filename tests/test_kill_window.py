from datetime import datetime,timedelta,timezone
from decimal import Decimal
import pytest
from backend.kill_window import Observation,as_decimal,breaches,evaluate_window
NOW=datetime(2026,10,23,12,tzinfo=timezone.utc)
RULE={'metric':'realized_value','operator':'lt','threshold':'50','window_days':2,'max_gap_hours':24}

def obs(h,v='40',verification='SOURCE_VERIFIED',identity='source:erp'):
    return Observation(NOW-timedelta(hours=h),Decimal(v),'GL:001',verification,identity)

def run(data,ids=frozenset({'source:erp'}),rule=RULE):
    return evaluate_window(rule,data,evaluated_at=NOW,verified_source_ids=ids)

def test_nonfinite_denied():
    for s in ('NaN','Infinity','-Infinity'):
        with pytest.raises(ValueError):as_decimal(s)

def test_operators():
    assert breaches('lt',Decimal(2),Decimal(3))
    assert not breaches('gt',Decimal(2),Decimal(3))
    with pytest.raises(ValueError):breaches('eq',Decimal(2),Decimal(3))

def test_empty_not_verified():assert run([])['status']=='INSUFFICIENT_EVIDENCE'

def test_one_sample_insufficient():assert run([obs(0)])['status']=='INSUFFICIENT_EVIDENCE'

def test_unverified_forces_insufficient():
    x=run([obs(48,verification='SUBMITTED_UNVERIFIED'),obs(24),obs(0)])
    assert x['status']=='INSUFFICIENT_EVIDENCE' and not x['source_verified']

def test_attested_but_no_source_identity_denied():
    assert run([obs(48,identity=''),obs(24),obs(0)])['status']=='INSUFFICIENT_EVIDENCE'

def test_unknown_source_denied():assert run([obs(48),obs(24),obs(0)],ids=frozenset())['status']=='INSUFFICIENT_EVIDENCE'

def test_gaps_fail_closed():assert run([obs(48),obs(0)])['status']=='INSUFFICIENT_EVIDENCE'

def test_all_samples_breach_yields_candidate_not_halt():
    x=run([obs(48),obs(24),obs(0)])
    assert x['status']=='SAMPLED_BREACH_REVIEW' and x['candidate_only'] and not x['continuous_condition_proven']

def test_mixed_samples_not_triggered():assert run([obs(48),obs(24,'70'),obs(0)])['status']=='SAMPLED_WITHIN_OR_MIXED'

def test_future_samples_ignored():assert run([obs(48),obs(24),obs(0),obs(-5,'70')])['status']=='SAMPLED_BREACH_REVIEW'

def test_bad_window_validation():
    with pytest.raises(ValueError):run([obs(48),obs(24),obs(0)],rule={**RULE,'window_days':0})

def test_naive_time_denied():
    with pytest.raises(ValueError):evaluate_window(RULE,[obs(48),obs(0)],evaluated_at=NOW.replace(tzinfo=None))

def test_sample_time_naive_denied():
    bad=Observation(NOW.replace(tzinfo=None),Decimal('20'),'ref','SOURCE_VERIFIED','source:erp')
    with pytest.raises(ValueError):run([bad,obs(48)])

def test_negative_decimal_valid():assert as_decimal('-2.57')==Decimal('-2.57')
