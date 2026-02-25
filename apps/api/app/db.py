import atexit
import os
from contextlib import contextmanager
from functools import lru_cache

from pgvector.psycopg2 import register_vector
from psycopg2.pool import ThreadedConnectionPool
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)
engine = create_engine(DATABASE_URL, future=True) if DATABASE_URL else None
SessionLocal = (
    sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None
)


def get_session():
    with session_scope() as db:
        yield db


@contextmanager
def session_scope():
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not set")

    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@lru_cache(maxsize=1)
def _get_pool() -> ThreadedConnectionPool:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")

    min_conn = int(os.getenv("PG_POOL_MIN_CONN", "1"))
    max_conn = int(os.getenv("PG_POOL_MAX_CONN", "10"))
    connect_timeout = int(os.getenv("PG_CONNECT_TIMEOUT_SECONDS", "5"))
    return ThreadedConnectionPool(
        minconn=max(1, min_conn),
        maxconn=max(1, max_conn),
        dsn=DATABASE_URL,
        connect_timeout=connect_timeout,
    )


@atexit.register
def _close_pool() -> None:
    try:
        _get_pool().closeall()
    except Exception:
        # Best-effort cleanup during interpreter shutdown.
        pass


@contextmanager
def get_conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        # Idempotent per-connection registration for pgvector adaptation.
        register_vector(conn)
        with conn:
            yield conn
    finally:
        pool.putconn(conn)
