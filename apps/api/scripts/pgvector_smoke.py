import uuid
import traceback
from psycopg2.extras import Json

from app.db import get_conn

DIM = 384  # Set this to the expected embedding dimension


def get_vector_dimension(cur):
    cur.execute(
        """
        select attnum, atttypmod
        from pg_attribute
        where attrelid = 'chunks'::regclass
        and attname = 'embedding';
        """
    )
    typmod = cur.fetchone()[0]
    return typmod - 4


def main():
    print("=== PGVector Smoke Test ===")
    conn = get_conn()
    print("Connected to database.")

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("select extname from pg_extension where extname='vector';")
                print("vector extension installed:", cur.fetchone() is not None)

                cur.execute("select 1;")
                print("select 1 ->", cur.fetchone())
                dim = get_vector_dimension(cur)
                print("vector dimension ->", dim)

                cur.execute("select '[1,2,3]'::vector;")
                print("vector cast ->", cur.fetchone())

                doc_id = uuid.uuid4()
                chunk_id = uuid.uuid4()
                emb = [0.01] * 384

                cur.execute(
                    "insert into documents (id, collection_id, file_name) values (%s, %s, %s)",
                    (str(doc_id), "default", "smoke_test_file.txt"),
                )
                cur.execute(
                    "insert into chunks (id, document_id, chunk_index, content, embedding, meta) values (%s, %s, %s, %s, %s, %s)",
                    (
                        str(chunk_id),
                        str(doc_id),
                        0,
                        "This is a test chunk.",
                        emb,
                        Json({}),
                    ),
                )
                print("Inserted test document and chunk.", doc_id, chunk_id)
                conn.commit()

                cur.execute(
                    """
                    select id, content, (embedding <=> (%s)::vector) as distance
                    from chunks
                    order by embedding <=> (%s)::vector
                    limit 3
                    """,
                    (emb, emb),
                )
                rows = cur.fetchall()
                print("Retrieved rows:", rows)
            print("PGVector smoke test completed successfully.")

    except Exception as e:
        print("An error occurred during the PGVector smoke test:", e)
        traceback.print_exc()
        raise
    finally:
        conn.close()
        print("Database connection closed.")


if __name__ == "__main__":
    main()
