"""LIVE tests require a disposable PostgreSQL database; never run against production."""
import os
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DBAPIError
from backend.authenticated_ingestion import AuthenticatedEvidence
from backend.migration_r99 import run

pytestmark=pytest.mark.postgres

@pytest.fixture
def pg():
    url=os.getenv('R99_POSTGRES_URL')
    if not url: pytest.skip('R99_POSTGRES_URL absent: no live PostgreSQL proof')
    engine=create_engine(url,pool_pre_ping=True)
    if engine.dialect.name!='postgresql': pytest.skip('Requires PostgreSQL')
    if os.getenv('R99_DISPOSABLE_DB_ACK') != 'YES':
        pytest.skip('Requires R99_DISPOSABLE_DB_ACK=YES; tests create tables and insert rows')
    try:yield engine
    finally:engine.dispose()

def test_live_migration_and_mutation_trigger(pg):
    run(pg,apply=True)
    assert run(pg,apply=False)['table_present']
    with pg.begin() as c:
        c.execute(text('''INSERT INTO di_authenticated_evidence
            (id, tenant_id, source_system, source_record, key_id, nonce, collected_at,
             payload_bytes, payload_sha256, envelope_json, envelope_sha256)
            VALUES (:id,'test-tenant','jenkins','run-1','test-key',:nonce,now(),
                    :payload,'somehash','{}','somehash')'''),
                  {'id':'r99-test-trigger-1','nonce':'r99-test-nonce-1','payload':b'test'})
    with pytest.raises(DBAPIError):
        with pg.begin() as c:
            c.execute(text("UPDATE di_authenticated_evidence SET source_record='tampered' WHERE id='r99-test-trigger-1'"))
    with pytest.raises(DBAPIError):
        with pg.begin() as c:
            c.execute(text("DELETE FROM di_authenticated_evidence WHERE id='r99-test-trigger-1'"))

def test_live_concurrent_nonce_uniqueness(pg):
    run(pg,apply=True)
    def insert(n):
        try:
            with pg.begin() as c:
                c.execute(text('''INSERT INTO di_authenticated_evidence
                    (id, tenant_id, source_system, source_record, key_id, nonce, collected_at,
                     payload_bytes, payload_sha256, envelope_json, envelope_sha256)
                    VALUES (:id,'r99-concurrent-tenant','jenkins','run-2','test-key',
                            'r99-common-nonce',now(),:payload,'h','{}','h')'''),
                          {'id':f'r99-race-{n}','payload':b'data'})
            return True
        except DBAPIError:return False
    with ThreadPoolExecutor(max_workers=2) as ex:
        results=list(ex.map(insert,range(2)))
    assert results.count(True)==1 and results.count(False)==1
