"""Read-only PostgreSQL assurance inspections for R7/R8/R9.5/R9.7.

No silent setup or migrations; returns failures for missing schema/trigger.
"""
from __future__ import annotations
from sqlalchemy import inspect, text

REQUIRED_TABLES=('di_kill_window_samples','di_trust_snapshots')

def inspect_postgres(engine):
    if engine.dialect.name != 'postgresql':
        return {'status':'NOT_TESTED','reasons':['PostgreSQL required; SQLite is not equivalent']}
    result={'status':'PASS','reasons':[],'tests':{}}
    with engine.connect() as conn:
        tables=set(inspect(conn).get_table_names())
        for name in REQUIRED_TABLES:
            ok=name in tables
            result['tests'][f'table:{name}']=ok
            if not ok: result['reasons'].append(f'missing table: {name}')
        if 'di_kill_window_samples' in tables:
            record=conn.execute(text("""SELECT t.tgenabled FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
              JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relname='di_kill_window_samples'
              AND t.tgname='r97_append_only' AND NOT t.tgisinternal AND n.nspname=current_schema()""")).fetchone()
            ok=bool(record and record[0] in ('O','A'))
            result['tests']['mutation_trigger_enabled']=ok
            if not ok: result['reasons'].append('append-only trigger missing or disabled')
    if result['reasons']:result['status']='FAIL'
    return result
