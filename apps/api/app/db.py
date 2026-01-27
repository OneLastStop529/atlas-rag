from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings
import os
import psycopg2

from pgvector.psycopg2 import register_vector


DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    register_vector(conn)
    return conn
