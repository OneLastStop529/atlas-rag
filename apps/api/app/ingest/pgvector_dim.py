from __future__ import annotations

import re


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
