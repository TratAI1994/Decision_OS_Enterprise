"""Idempotent additive schema; immutable-row triggers for PostgreSQL normal roles."""
import argparse
from sqlalchemy import inspect,text
from .db import engine_for
from .trust_foundation import TrustSnapshot,KillSignal

def run(engine,apply=False):
    tables=set(inspect(engine).get_table_names())
    if not {'di_decisions','di_decision_events'}.issubset(tables):
        raise RuntimeError('Apply strategy + R7 migrations first')
    if apply:
        for model in (TrustSnapshot,KillSignal):model.__table__.create(bind=engine,checkfirst=True)
        if engine.dialect.name=='postgresql':
            with engine.begin() as con:
                con.execute(text("""CREATE OR REPLACE FUNCTION di_r95_deny_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'Trust history is append-only'; END; $$"""))
                for table in ('di_trust_snapshots','di_kill_signal_events'):
                    con.execute(text(f'DROP TRIGGER IF EXISTS r95_append_only ON {table}'))
                    con.execute(text(f'CREATE TRIGGER r95_append_only BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION di_r95_deny_mutation()'))
    return {'apply':apply,'postgresql_triggers':apply and engine.dialect.name=='postgresql'}

if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--check',action='store_true');g.add_argument('--apply',action='store_true');a=p.parse_args()
    print(run(engine_for(),a.apply))
