"""Additive migration; applying requires explicit --apply. Check-only is non-mutating."""
import argparse
from sqlalchemy import inspect, text
from .authenticated_ingestion import AuthenticatedEvidence

def run(engine, apply=False):
    if not apply:
        return {'table_present': 'di_authenticated_evidence' in inspect(engine).get_table_names(),
                'applied':False, 'postgresql':engine.dialect.name=='postgresql'}
    if engine.dialect.name != 'postgresql':
        raise RuntimeError('Persistent R9.9 ingestion requires PostgreSQL')
    AuthenticatedEvidence.__table__.create(bind=engine,checkfirst=True)
    with engine.begin() as conn:
        conn.execute(text('''CREATE OR REPLACE FUNCTION di_r99_reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'R9.9 evidence is append-only'; END; $$'''))
        conn.execute(text('DROP TRIGGER IF EXISTS r99_append_only ON di_authenticated_evidence'))
        conn.execute(text('''CREATE TRIGGER r99_append_only BEFORE UPDATE OR DELETE ON di_authenticated_evidence
                            FOR EACH ROW EXECUTE FUNCTION di_r99_reject_mutation()'''))
    return {'table_present':True,'applied':True,'postgresql':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--check',action='store_true');g.add_argument('--apply',action='store_true')
    a=p.parse_args()
    from .db import engine_for
    print(run(engine_for(),apply=a.apply))
