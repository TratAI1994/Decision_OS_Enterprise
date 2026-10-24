from sqlalchemy import create_engine
from backend.postgres_assurance import inspect_postgres

def test_sqlite_is_not_postgres_proof():
 result=inspect_postgres(create_engine('sqlite://'))
 assert result['status']=='NOT_TESTED'
