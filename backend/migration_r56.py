"""R5.6 safe additive migration: create only di_evaluations; no existing tables altered."""
import argparse

from sqlalchemy import inspect

from .db import engine_for
from .decision_evaluation import DecisionEvaluation


def run(engine,apply=False):
    present=set(inspect(engine).get_table_names())
    if 'di_decisions' not in present:
        raise RuntimeError('Existing canonical Decision Ledger is missing; apply prior migrations first.')
    existed=DecisionEvaluation.__tablename__ in present
    if apply:DecisionEvaluation.__table__.create(bind=engine,checkfirst=True)
    return {'mode':'apply' if apply else 'check','table':'di_evaluations','already_present':existed,'created':bool(apply and not existed)}

if __name__=='__main__':
    p=argparse.ArgumentParser();mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true');mode.add_argument('--apply',action='store_true')
    opts=p.parse_args();print(run(engine_for(),apply=opts.apply))
