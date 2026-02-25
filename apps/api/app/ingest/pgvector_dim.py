from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_db_vector_dim(cur) -> int:
    """
    Reliable: ask Postgres to describe the vector column type ("vector(dim)") and parse out dim
    """
    cur.execute(
        """
        SELECT format_type(a.atttypid, a.atttypmod) AS vector_type
        FROM pg_attribute a
        WHERE a.attrelid = 'chunks'::regclass
            AND a.attname = 'embedding'
            AND a.attnum > 0
            AND not a.attisdropped
        LIMIT 1; 
        """
    )
    type_str = cur.fetchone()[0]
    match = re.match(r"vector\((\d+)\)", type_str)
    if not match:
        raise RuntimeError(f"Could not parse vector type: {type_str}")
    return int(match.group(1))


def get_db_vector_dim_session(session: Session) -> int:
    type_str = session.execute(
        text(
            """
            SELECT format_type(a.atttypid, a.atttypmod) AS vector_type
            FROM pg_attribute a
            WHERE a.attrelid = 'chunks'::regclass
                AND a.attname = 'embedding'
                AND a.attnum > 0
                AND NOT a.attisdropped
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if type_str is None:
        raise RuntimeError("Could not determine vector type for chunks.embedding")

    match = re.match(r"vector\((\d+)\)", type_str)
    if not match:
        raise RuntimeError(f"Could not parse vector type: {type_str}")
    return int(match.group(1))
