"""SQLAlchemy PostgreSQL schema; SQLite allowed for isolated unit testing only."""
import os
from sqlalchemy import create_engine, Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Text, Float, CheckConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from sqlalchemy.types import JSON
Base = declarative_base()

class Initiative(Base):
    __tablename__='initiatives'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    name=Column(String(180),nullable=False)
    owner=Column(String(120),nullable=False)
    description=Column(Text,nullable=False,default='')
    version=Column(Integer,nullable=False,default=1)
    created_at=Column(DateTime(timezone=True),nullable=False,server_default=func.now())

class Evidence(Base):
    __tablename__='evidence'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    initiative_id=Column(String(48),ForeignKey('initiatives.id'),nullable=False)
    stage=Column(String(48),nullable=False)
    key=Column(String(72),nullable=False)
    reference=Column(Text,nullable=False)
    content_hash=Column(String(64),nullable=False)
    submitted_by=Column(String(120),nullable=False)
    verified_by=Column(String(120),nullable=True)
    status=Column(String(24),nullable=False,default='submitted')
    __table_args__=(UniqueConstraint('initiative_id','stage','key',name='uq_evidence_stage_key'),)

class Approval(Base):
    __tablename__='approvals'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False)
    initiative_id=Column(String(48),ForeignKey('initiatives.id'),nullable=False)
    stage=Column(String(48),nullable=False)
    actor=Column(String(120),nullable=False)
    scope_hash=Column(String(64),nullable=False)
    __table_args__=(UniqueConstraint('initiative_id','stage',name='uq_approval_stage'),)

class Benefit(Base):
    __tablename__='benefits'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False)
    initiative_id=Column(String(48),ForeignKey('initiatives.id'),nullable=False)
    period=Column(String(7),nullable=False)
    planned=Column(Float,nullable=False)
    reported=Column(Float,nullable=False)
    run_cost=Column(Float,nullable=False)
    evidence_reference=Column(Text,nullable=False)
    classification=Column(String(32),nullable=False,default='self_reported')
    __table_args__=(UniqueConstraint('initiative_id','period',name='uq_benefit_period'),)

class Audit(Base):
    __tablename__='audit_events'
    id=Column(Integer,primary_key=True,autoincrement=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    actor=Column(String(120),nullable=False)
    event=Column(String(80),nullable=False)
    entity_id=Column(String(48),nullable=False)
    detail=Column(JSON,nullable=False)
    prev_hash=Column(String(64),nullable=False)
    event_hash=Column(String(64),nullable=False)
    created_at=Column(DateTime(timezone=True),server_default=func.now())

class WorkspaceDocument(Base):
    __tablename__='workspace_documents'
    tenant_id=Column(String(64),primary_key=True)
    workspace_id=Column(String(100),primary_key=True)
    payload=Column(JSON,nullable=False)
    version=Column(Integer,nullable=False,default=1)
    updated_at=Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())

def engine_for(url=None):
    url=url or os.environ.get('DATABASE_URL','postgresql+psycopg://decision:decision@localhost:5432/decision_os')
    opts={'pool_pre_ping':True}
    if url.startswith('sqlite'):
        opts['connect_args']={'check_same_thread':False}
        if ':memory:' in url:
            from sqlalchemy.pool import StaticPool
            opts['poolclass']=StaticPool
    else: opts.update(pool_size=8,max_overflow=8,pool_timeout=20)
    return create_engine(url,**opts)

def session_factory(engine): return sessionmaker(bind=engine,expire_on_commit=False)
