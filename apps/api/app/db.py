from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings
import os
import psycopg2

from pgvector.psycopg2 import register_vector


DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)
engine = create_engine(DATABASE_URL, future=True) if DATABASE_URL else None
SessionLocal = (
    sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None
)


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    connect_timeout = int(os.getenv("PG_CONNECT_TIMEOUT_SECONDS", "5"))
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=connect_timeout)
    register_vector(conn)
    return conn
