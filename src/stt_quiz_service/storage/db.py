from __future__ import annotations

from pgvector.psycopg import register_vector
import psycopg
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, future=True, echo=False, connect_args=connect_args)
    if engine.dialect.name == "postgresql":
        @event.listens_for(engine, "connect")
        def _register_pgvector(dbapi_connection, _connection_record):  # pragma: no cover - integration only
            try:
                register_vector(dbapi_connection)
            except psycopg.ProgrammingError:
                # The extension may not exist on the first bootstrap connection yet.
                pass

    return engine


def build_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
