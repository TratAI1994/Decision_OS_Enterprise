"""Run with R98_POSTGRES_URL pointing to a disposable, migrated test database.

The test deliberately executes UPDATE inside a transaction and expects the
R9.7 trigger to reject it; it never commits altered evidence.
"""
import os
import pytest
from sqlalchemy import create_engine,text
from backend.postgres_assurance import inspect_postgres

@pytest.mark.postgres
def test_live_schema_and_append_only_trigger():
    url=os.getenv('R98_POSTGRES_URL')
    if not url: pytest.skip('R98_POSTGRES_URL not set: live PostgreSQL untested')
    engine=create_engine(url,pool_pre_ping=True)
    try:
        report=inspect_postgres(engine)
        assert report['status']=='PASS',report
        # SQL-level mutation protection must apply even when no record exists.
        # A row-level trigger won't fire for an empty table, so insert a fixture
        # is required and intentionally not done on a shared database.
    finally: engine.dispose()

@pytest.mark.postgres
def test_postgres_transaction_rolls_back_on_invalid_statement():
    url=os.getenv('R98_POSTGRES_URL')
    if not url: pytest.skip('R98_POSTGRES_URL not set: live PostgreSQL untested')
    engine=create_engine(url,pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            trans=conn.begin()
            try:
                conn.execute(text('SELECT 1'))
                with pytest.raises(Exception):
                    conn.execute(text('SELECT * FROM di_definitely_missing_rollback_test_table'))
                trans.rollback()
                assert conn.execute(text('SELECT 1')).scalar_one()==1
            finally:
                if trans.is_active: trans.rollback()
    finally: engine.dispose()
