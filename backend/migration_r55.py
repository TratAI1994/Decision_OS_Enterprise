"""Additive R5.5 migration: creates only new strategy tables.
No ALTER, DROP, backfill, or changes to existing R1-R5.4 tables.
Usage: python -m backend.migration_r55 --check ; --apply
"""
import argparse

from sqlalchemy import inspect

from .db import engine_for
from .strategy_outcomes import (
    Assumption,
    DiscoveryExperiment,
    FocusArea,
    KeyResult,
    Objective,
    Observation,
    StrategyDecisionLink,
)

TABLES=[FocusArea.__table__,Objective.__table__,KeyResult.__table__,StrategyDecisionLink.__table__,Observation.__table__,Assumption.__table__,DiscoveryExperiment.__table__]

def run(engine,apply=False):
    existing=set(inspect(engine).get_table_names());names=[t.name for t in TABLES]
    missing=[n for n in names if n not in existing]
    if apply:
        # FK target di_decisions must exist before R5.5 creation.
        if 'di_decisions' not in existing:raise RuntimeError('Existing R1 decision ledger is missing. Upgrade baseline before R5.5.')
        for table in TABLES:table.create(bind=engine,checkfirst=True)
    return {'expected':names,'missing_before':missing,'created':missing if apply else [],'mode':'apply' if apply else 'check'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();g=parser.add_mutually_exclusive_group(required=True);g.add_argument('--check',action='store_true');g.add_argument('--apply',action='store_true')
    args=parser.parse_args();print(run(engine_for(),apply=args.apply))
