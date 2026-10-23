"""Additive R8 append-only outcome event table."""
import argparse
from sqlalchemy import inspect,text
from .db import engine_for
from .outcome_economics import OutcomeEvent

def run(engine,apply=False):
    tables=set(inspect(engine).get_table_names())
    if 'di_decisions' not in tables:raise RuntimeError('Apply Decision OS strategy migrations first')
    if apply:
        OutcomeEvent.__table__.create(bind=engine,checkfirst=True)
        if engine.dialect.name=='postgresql':
            with engine.begin() as c:
                c.execute(text("""CREATE OR REPLACE FUNCTION di_outcome_no_mutation() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Outcome financial event history is append-only'; END; $$"""))
                c.execute(text('DROP TRIGGER IF EXISTS outcome_immutable ON di_outcome_events'))
                c.execute(text('CREATE TRIGGER outcome_immutable BEFORE UPDATE OR DELETE ON di_outcome_events FOR EACH ROW EXECUTE FUNCTION di_outcome_no_mutation()'))
    return {'applied':apply,'already_present':'di_outcome_events' in tables,'postgreSQL_trigger':apply and engine.dialect.name=='postgresql'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();g=parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--check',action='store_true');g.add_argument('--apply',action='store_true')
    args=parser.parse_args();print(run(engine_for(),args.apply))
