"""Additive R7 table migration; PostgreSQL rejects UPDATE/DELETE at database level."""
import argparse

from sqlalchemy import inspect, text

from .db import engine_for
from .decision_events import DecisionEvent


def run(engine, apply=False):
    existing=set(inspect(engine).get_table_names())
    if 'di_decisions' not in existing:raise RuntimeError('Apply existing Decision OS migrations first')
    if apply:
        DecisionEvent.__table__.create(bind=engine,checkfirst=True)
        if engine.dialect.name=='postgresql':
            with engine.begin() as conn:
                conn.execute(text("""CREATE OR REPLACE FUNCTION decision_event_reject_mutation() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Event stream is append-only'; END; $$"""))
                conn.execute(text("""DROP TRIGGER IF EXISTS decision_events_immutable ON di_decision_events"""))
                conn.execute(text("""CREATE TRIGGER decision_events_immutable BEFORE UPDATE OR DELETE ON di_decision_events
                FOR EACH ROW EXECUTE FUNCTION decision_event_reject_mutation()"""))
    return {'mode':'apply' if apply else 'check','table':'di_decision_events',
            'already_present':'di_decision_events' in existing,'postgresql_mutation_trigger':apply and engine.dialect.name=='postgresql'}

if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--check',action='store_true');g.add_argument('--apply',action='store_true');a=p.parse_args()
    print(run(engine_for(),apply=a.apply))
