from app.rag.retriever import retrieve_top_k, to_citations


def main():
    query = "I pissed my pants"
    collection_id = "default"
    k = 3

    chunks = retrieve_top_k(query, k, collection_id, embedder_provider="hash")
    citations = to_citations(chunks)

    print(f"Query: {query}")
    print("Top-k Results:")
    for chunk in chunks:
        print(
            f"- Chunk ID: {chunk.chunk_id}, Chunk Index: {chunk.chunk_index} Similarity: {chunk.similarity:.4f}"
        )

    print("\nCitations:")
    for citation in citations:
        print(citation)


if __name__ == "__main__":
    main()
