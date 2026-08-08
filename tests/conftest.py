"""Test fixtures for VeriScope test suite.

Note: These fixtures are simplified for unit testing. For integration tests
that require full database setup, use the existing test patterns in the codebase
that use raw DDL for SQLite compatibility.
"""

import pytest
from datetime import datetime
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.types import UUID as BaseUUID
UUID = PG_UUID

orig_pg_bind = PG_UUID.bind_processor
def patched_pg_bind(self, dialect):
    proc = orig_pg_bind(self, dialect)
    if proc:
        def process(value):
            if isinstance(value, str):
                return value
            return proc(value)
        return process
    return proc
PG_UUID.bind_processor = patched_pg_bind

orig_base_bind = BaseUUID.bind_processor
def patched_base_bind(self, dialect):
    proc = orig_base_bind(self, dialect)
    if proc:
        def process(value):
            if isinstance(value, str):
                return value
            return proc(value)
        return process
    return proc
BaseUUID.bind_processor = patched_base_bind

# Register custom SQLite type compilers for PostgreSQL-specific types
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "TEXT"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"

# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_engine():
    """Create a test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create a test database session.
    
    Note: This is a minimal fixture. Tests that require actual database tables
    should create them using raw DDL or use the existing test patterns.
    """
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
