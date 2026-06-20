import pytest
from sqlalchemy import create_engine, ARRAY
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

# SQLite compat shims
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "TEXT"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"

@compiles(ARRAY, "sqlite")
def compile_array_sqlite(element, compiler, **kw):
    return "TEXT"

from app.db.base import Base
import app.models  # noqa — ensures all models are registered on Base
import app.models.integration_provider_cooldown  # noqa — ensure cooldown model is registered

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    
    # Deduplicate indexes to avoid sqlite3.OperationalError: index already exists
    for table in Base.metadata.tables.values():
        seen_names = set()
        to_remove = []
        for index in table.indexes:
            if index.name in seen_names:
                to_remove.append(index)
            else:
                seen_names.add(index.name)
        for index in to_remove:
            table.indexes.remove(index)
            
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
