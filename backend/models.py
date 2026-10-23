"""R5 additive SQLAlchemy tables. Existing database models are in backend.db.
Import this module before Base.metadata.create_all(); deploy migrations in production.
"""
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.types import JSON

from .db import Base


def utcnow(): return datetime.now(UTC)

class AIRiskAssessment(Base):
    __tablename__='r5_ai_risk_assessments'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    initiative_id=Column(String(48),ForeignKey('initiatives.id'),nullable=False,index=True)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False,index=True)
    request_id=Column(String(100),nullable=True) # R5.1.1 retry-safe submission token
    title=Column(String(180),nullable=False)
    ai_role=Column(String(30),nullable=False) # provider/deployer/other/unknown
    geography=Column(String(100),nullable=False)
    intended_use=Column(Text,nullable=False)
    risk_factors=Column(JSON,nullable=False)
    classification=Column(String(40),nullable=False,default='review_required')
    owner=Column(String(120),nullable=False)
    assessment_source=Column(String(500),nullable=False)
    review_status=Column(String(24),nullable=False,default='draft')
    reviewed_by=Column(String(120),nullable=True)
    review_note=Column(Text,nullable=True)
    version=Column(Integer,nullable=False,default=1)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)

class AIControlEvidence(Base):
    __tablename__='r5_control_evidence'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    assessment_id=Column(String(48),ForeignKey('r5_ai_risk_assessments.id'),nullable=False,index=True)
    framework=Column(String(40),nullable=False)
    control_id=Column(String(90),nullable=False)
    evidence_reference=Column(Text,nullable=False)
    evidence_quality=Column(String(24),nullable=False,default='self_reported')
    submitted_by=Column(String(120),nullable=False)
    verified_by=Column(String(120),nullable=True)
    status=Column(String(24),nullable=False,default='submitted')
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)

class RedTeamFinding(Base):
    __tablename__='r5_redteam_findings'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    assessment_id=Column(String(48),ForeignKey('r5_ai_risk_assessments.id'),nullable=False,index=True)
    initiative_id=Column(String(48),ForeignKey('initiatives.id'),nullable=False,index=True)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False,index=True)
    source_tool=Column(String(32),nullable=False)
    source_run_id=Column(String(180),nullable=False)
    source_finding_id=Column(String(180),nullable=False)
    category=Column(String(100),nullable=False)
    severity=Column(String(16),nullable=False)
    title=Column(String(220),nullable=False)
    evidence_reference=Column(Text,nullable=False)
    observed_result=Column(Text,nullable=False)
    remediation=Column(Text,nullable=False,default='')
    status=Column(String(24),nullable=False,default='open')
    verified_by=Column(String(120),nullable=True)
    version=Column(Integer,nullable=False,default=1)
    reported_by=Column(String(120),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utcnow)
    __table_args__=(UniqueConstraint('tenant_id','assessment_id','source_tool','source_run_id','source_finding_id',name='uq_r5_finding_origin'),)
