from __future__ import annotations

import argparse
import os
from app.db import session_scope
from app.ingest.chunker import ChunkConfig, lc_recursive_ch_text
from app.ingest.store import insert_document_and_chunks
from app.ingest.pgvector_dim import get_db_vector_dim_session
from app.providers.embeddings.base import EmbeddingsProvider
from app.providers.embeddings.registry import supported_embeddings_provider_ids


def main():
    p = argparse.ArgumentParser(description="Ingest a TXT file into the vector DB")
    p.add_argument("--file", required=True, help="Path to the TXT file to ingest")
    p.add_argument(
        "--collection",
        default="default",
        help="collection ID to store the documentation",
    )
    p.add_argument("--chunk-chars", type=int, default=2000)
    p.add_argument("--overlap-chars", type=int, default=200)
    p.add_argument(
        "--embeddings-provider",
        dest="embeddings_provider",
        choices=sorted(supported_embeddings_provider_ids()),
        default="hash",
        help="Embeddings provider ID",
    )
    args = p.parse_args()

    path = args.file
    file_name = os.path.basename(path)
    mime_type = "text/plain"

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    cfg = ChunkConfig(chunk_chars=args.chunk_chars, overlap_chars=args.overlap_chars)
    chunks = lc_recursive_ch_text(text, cfg)
    if not chunks:
        raise SystemExit("No content found to ingest")

    with session_scope() as session:
        dim = get_db_vector_dim_session(session)

    print(f"DB vector dim: {dim}")
    print(
        f"Chunks: {len(chunks)} (chunk_chars={cfg.chunk_chars}, overlap_chars={cfg.overlap_chars})"
    )
    print(f"Embedding provider: {args.embeddings_provider}")

    embeddings_provider = EmbeddingsProvider(dim=dim, provider=args.embeddings_provider)
    embeddings = embeddings_provider.embed_documents(chunks)

    doc_id, num_chunks = insert_document_and_chunks(
        collection_id=args.collection,
        file_name=file_name,
        mime_type=mime_type,
        chunks=chunks,
        embeddings=embeddings,
    )
    print(f"Ingested document ID: {doc_id} with {num_chunks} chunks")


if __name__ == "__main__":
    main()
