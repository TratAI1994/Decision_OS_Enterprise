"""Conservative idempotent expand-only migration for existing R1/R5 tables.

Apply with `python -m backend.migration_r511` inside API container *before* rebuilding API.
No existing rows are deleted/rewritten except necessary NULL-to-unknown for new metadata.
Never infer historical risk classification or confidence basis.
"""
from __future__ import annotations
import os
from sqlalchemy import create_engine, inspect, text
from .db import engine_for

DECISION_COLUMNS={
 'risk_tier':'VARCHAR(24)',
 'confidence_basis':'VARCHAR(40)',
 'supersedes_id':'VARCHAR(48)',
 'review_started_at':'TIMESTAMP WITH TIME ZONE',
 'approved_at':'TIMESTAMP WITH TIME ZONE',
 'execution_started_at':'TIMESTAMP WITH TIME ZONE',
 'closed_at':'TIMESTAMP WITH TIME ZONE',
}

def migrate(engine):
 """Transactional and repeatable on PostgreSQL; SQLite supports simple ALTER TABLE."""
 dialect=engine.dialect.name
 if dialect not in ('postgresql','sqlite'):raise RuntimeError('Unsupported migration dialect')
 with engine.begin() as con:
  inspector=inspect(con)
  if not inspector.has_table('di_decisions') or not inspector.has_table('r5_ai_risk_assessments'):
   raise RuntimeError('R1/R5 tables missing: apply only after the existing R5 deployment')
  decision_fields={x['name'] for x in inspector.get_columns('di_decisions')}
  # tenant_id and version already exist in R1; never overwrite them.
  if not {'tenant_id','version'}.issubset(decision_fields):raise RuntimeError('Unexpected legacy decision schema; manual review required')
  for name,typ in DECISION_COLUMNS.items():
   if name not in decision_fields:
    if dialect=='sqlite' and 'TIMESTAMP' in typ:typ='DATETIME'
    con.execute(text(f'ALTER TABLE di_decisions ADD COLUMN {name} {typ} NULL'))
  # Missing legacy metadata represents *unknown*, not an invented classification.
  con.execute(text("UPDATE di_decisions SET confidence_basis='unknown' WHERE confidence_basis IS NULL"))
  con.execute(text("UPDATE di_decisions SET risk_tier='unassessed' WHERE risk_tier IS NULL"))
  risk_fields={x['name'] for x in inspector.get_columns('r5_ai_risk_assessments')}
  if 'request_id' not in risk_fields:
   con.execute(text('ALTER TABLE r5_ai_risk_assessments ADD COLUMN request_id VARCHAR(100) NULL'))
  con.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ux_r511_assessment_retry ON r5_ai_risk_assessments (tenant_id, request_id)'))
  # New FK remains nullable; do not alter existing execution/risk FKs.
  if dialect=='postgresql':
   con.execute(text('''DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_r511_decision_supersedes') THEN ALTER TABLE di_decisions ADD CONSTRAINT fk_r511_decision_supersedes FOREIGN KEY (supersedes_id) REFERENCES di_decisions(id); END IF; END $$'''))
 return {'status':'ok','migration':'r5.1.1','dialect':dialect}

if __name__=='__main__':
 engine=engine_for(os.getenv('DATABASE_URL'))
 print(migrate(engine))
