"""Additive R9.7 sample table and PostgreSQL mutation-denial trigger."""
import argparse
from sqlalchemy import inspect, text
from .db import engine_for
from .kill_window_api import KillWindowSample

def run(engine,apply=False):
    present=set(inspect(engine).get_table_names())
    if not {'di_decisions','di_trust_snapshots'}.issubset(present):
        raise RuntimeError('Apply R9.5 migration before R9.7')
    if apply:
        KillWindowSample.__table__.create(bind=engine,checkfirst=True)
        if engine.dialect.name=='postgresql':
            with engine.begin() as con:
                con.execute(text('''CREATE OR REPLACE FUNCTION di_r97_deny_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'R9.7 observation ledger is append-only'; END; $$'''))
                con.execute(text('DROP TRIGGER IF EXISTS r97_append_only ON di_kill_window_samples'))
                con.execute(text('''CREATE TRIGGER r97_append_only BEFORE UPDATE OR DELETE ON di_kill_window_samples
                        FOR EACH ROW EXECUTE FUNCTION di_r97_deny_mutation()'''))
    return {'mode':'apply' if apply else 'check','postgresql_trigger':apply and engine.dialect.name=='postgresql'}

if __name__=='__main__':
    p=argparse.ArgumentParser(); grp=p.add_mutually_exclusive_group(required=True)
    grp.add_argument('--check',action='store_true');grp.add_argument('--apply',action='store_true')
    args=p.parse_args(); print(run(engine_for(),apply=args.apply))
